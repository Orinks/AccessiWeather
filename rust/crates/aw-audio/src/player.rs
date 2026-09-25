//! Sound playback (`notifications/sound_player.py`).
//!
//! Python plays through sound_lib (BASS); this uses rodio with symphonia
//! decoders (wav, mp3, ogg/vorbis, flac). Every sound gets its own player on
//! a shared mixer, so sounds overlap the way BASS streams do, and nothing
//! blocks the caller. When playback fails the output device is reopened and
//! the sound retried once, like `_reinitialize_sound_lib_output`.

use std::fs::File;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex, MutexGuard, OnceLock};

use rodio::mixer::Mixer;
use rodio::{Decoder, DeviceSinkBuilder, Player};

use crate::events::is_sound_event_muted;
use crate::pack::{self, DEFAULT_EVENT};

/// The process-wide player (Python's module-level state), reading packs
/// from [`pack::soundpacks_dir`].
pub fn player() -> &'static SoundPlayer {
    static PLAYER: OnceLock<SoundPlayer> = OnceLock::new();
    PLAYER.get_or_init(|| SoundPlayer::new(pack::soundpacks_dir()))
}

/// An open output device. The device handle is not `Send` on every
/// platform, so a parked thread owns it; dropping `_keep_open` closes it.
struct Output {
    mixer: Mixer,
    failed: Arc<AtomicBool>,
    _keep_open: mpsc::Sender<()>,
}

fn open_output() -> Result<Output, String> {
    let (result_tx, result_rx) = mpsc::channel();
    let (keep_tx, keep_rx) = mpsc::channel::<()>();
    let failed = Arc::new(AtomicBool::new(false));
    let flag = Arc::clone(&failed);
    std::thread::Builder::new()
        .name("aw-audio-output".into())
        .spawn(move || {
            let opened = DeviceSinkBuilder::from_default_device()
                .and_then(|builder| {
                    builder
                        .with_error_callback(move |err| {
                            tracing::warn!("audio output error: {err}");
                            flag.store(true, Ordering::SeqCst);
                        })
                        .open_sink_or_fallback()
                })
                .or_else(|_| DeviceSinkBuilder::open_default_sink());
            match opened {
                Ok(mut sink) => {
                    sink.log_on_drop(false);
                    let _ = result_tx.send(Ok(sink.mixer().clone()));
                    // Park until the Output is dropped.
                    let _ = keep_rx.recv();
                }
                Err(e) => {
                    let _ = result_tx.send(Err(e.to_string()));
                }
            }
        })
        .map_err(|e| e.to_string())?;
    let mixer = result_rx
        .recv()
        .map_err(|_| "audio output thread exited".to_string())??;
    Ok(Output {
        mixer,
        failed,
        _keep_open: keep_tx,
    })
}

#[derive(Default)]
struct Backend {
    output: Option<Output>,
    /// Python's `SOUND_LIB_AVAILABLE` turned false: opening the device failed.
    unavailable: bool,
    /// Streams kept alive while they play (`_active_streams`).
    active: Vec<Player>,
    /// The preview player's current stream.
    preview: Option<Player>,
}

impl Backend {
    fn mixer(&mut self) -> Option<Mixer> {
        if self.unavailable {
            return None;
        }
        if self.output.is_none() {
            match open_output() {
                Ok(output) => self.output = Some(output),
                Err(e) => {
                    tracing::debug!("audio output initialization failed: {e}");
                    self.unavailable = true;
                    return None;
                }
            }
        }
        self.output.as_ref().map(|o| o.mixer.clone())
    }

    /// `_reinitialize_sound_lib_output`.
    fn reinitialize(&mut self) -> bool {
        if self.unavailable {
            return false;
        }
        for stream in self.active.drain(..) {
            stream.stop();
        }
        self.output = None;
        match open_output() {
            Ok(output) => {
                self.output = Some(output);
                tracing::info!("Reinitialized audio output device");
                true
            }
            Err(e) => {
                tracing::warn!("audio output reinitialization failed: {e}");
                self.unavailable = true;
                false
            }
        }
    }
}

fn start(mixer: &Mixer, file: &Path, volume: f64) -> Result<Player, String> {
    let decoder = Decoder::try_from(File::open(file).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    let player = Player::connect_new(mixer);
    player.set_volume(volume as f32);
    player.append(decoder);
    Ok(player)
}

pub struct SoundPlayer {
    soundpacks_dir: PathBuf,
    backend: Mutex<Backend>,
}

impl SoundPlayer {
    /// A player reading packs from `soundpacks_dir`. The output device is
    /// opened on first playback.
    pub fn new(soundpacks_dir: PathBuf) -> Self {
        Self {
            soundpacks_dir,
            backend: Mutex::new(Backend::default()),
        }
    }

    pub fn soundpacks_dir(&self) -> &Path {
        &self.soundpacks_dir
    }

    fn backend(&self) -> MutexGuard<'_, Backend> {
        self.backend.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// `_play_sound_file`: play without blocking at `volume` (clamped to
    /// 0.0-1.0). Silent volume is a successful no-op. Returns whether the
    /// sound started.
    pub fn play_file(&self, file: &Path, volume: f64) -> bool {
        self.play_file_inner(file, volume, false)
    }

    /// `_play_sound_file(block=True)`: play and wait for the sound to end.
    pub fn play_file_blocking(&self, file: &Path, volume: f64) -> bool {
        self.play_file_inner(file, volume, true)
    }

    fn play_file_inner(&self, file: &Path, volume: f64, block: bool) -> bool {
        let volume = crate::py::clamp_volume(volume);
        if volume <= 0.0 {
            tracing::debug!("Skipping silent sound playback: {}", file.display());
            return true;
        }
        let device_failed = {
            let backend = self.backend();
            backend
                .output
                .as_ref()
                .is_some_and(|o| o.failed.load(Ordering::SeqCst))
        };
        if device_failed && !self.backend().reinitialize() {
            return false;
        }
        if self.try_play(file, volume, block) {
            return true;
        }
        if self.backend().reinitialize() {
            tracing::info!("Retrying sound playback after audio output reinitialization");
            return self.try_play(file, volume, block);
        }
        false
    }

    fn try_play(&self, file: &Path, volume: f64, block: bool) -> bool {
        let mixer = {
            let mut backend = self.backend();
            backend.active.retain(|p| !p.empty());
            match backend.mixer() {
                Some(m) => m,
                None => {
                    tracing::warn!("audio backend unavailable");
                    return false;
                }
            }
        };
        match start(&mixer, file, volume) {
            Ok(player) => {
                tracing::debug!("Played sound at volume {volume}: {}", file.display());
                if block {
                    player.sleep_until_end();
                } else {
                    self.backend().active.push(player);
                }
                true
            }
            Err(e) => {
                tracing::warn!("sound playback failed: {e}");
                false
            }
        }
    }

    /// `play_notification_sound`: play `event` from `pack` unless muted,
    /// with the default-pack and `notify` fallbacks of [`pack::get_sound_entry`].
    /// Use it for app sounds: `startup`, `exit`, `data_updated`,
    /// `fetch_error`, `discussion_update`, `severe_risk`, `alert`, `notify`...
    pub fn play_event<S: AsRef<str>>(&self, pack: &str, event: &str, muted_events: &[S]) {
        if let Some((file, volume)) = self.resolve_event(pack, event, muted_events) {
            if !self.play_file(&file, volume) {
                tracing::warn!("Sound playback not available or all methods failed.");
            }
        }
    }

    /// The file and volume [`Self::play_event`] would play; `None` when the
    /// event is muted or no file exists.
    pub fn resolve_event<S: AsRef<str>>(
        &self,
        pack: &str,
        event: &str,
        muted_events: &[S],
    ) -> Option<(PathBuf, f64)> {
        if is_sound_event_muted(event, muted_events) {
            tracing::debug!("Skipping muted sound event: {event}");
            return None;
        }
        match pack::get_sound_entry(event, pack, &self.soundpacks_dir) {
            (Some(file), volume) => Some((file, volume)),
            (None, _) => {
                tracing::warn!("Sound file not found.");
                None
            }
        }
    }

    /// `play_notification_sound_candidates`: play the first available of
    /// `candidates` (see [`crate::alert_sounds::get_candidate_sound_events`]).
    /// Nothing plays when `logical_event` (default: the first candidate) is
    /// muted; muted candidates are skipped.
    pub fn play_candidates<S: AsRef<str>>(
        &self,
        candidates: &[String],
        pack: &str,
        logical_event: Option<&str>,
        muted_events: &[S],
    ) {
        if let Some((file, volume)) =
            self.resolve_candidates(candidates, pack, logical_event, muted_events)
        {
            if !self.play_file(&file, volume) {
                tracing::warn!("Sound playback not available or all methods failed.");
            }
        }
    }

    /// The file and volume [`Self::play_candidates`] would play.
    pub fn resolve_candidates<S: AsRef<str>>(
        &self,
        candidates: &[String],
        pack: &str,
        logical_event: Option<&str>,
        muted_events: &[S],
    ) -> Option<(PathBuf, f64)> {
        let effective = logical_event.or(candidates.first().map(String::as_str));
        if let Some(event) = effective.filter(|e| is_sound_event_muted(e, muted_events)) {
            tracing::debug!("Skipping muted sound event: {event}");
            return None;
        }
        let filtered: Vec<String> = candidates
            .iter()
            .filter(|c| !is_sound_event_muted(c, muted_events))
            .cloned()
            .collect();
        if filtered.is_empty() {
            tracing::debug!("All candidate sound events are muted; skipping playback");
            return None;
        }
        match pack::get_sound_entry_for_candidates(&filtered, pack, &self.soundpacks_dir) {
            (Some(file), volume) => Some((file, volume)),
            (None, _) => {
                tracing::warn!("No candidate sound file found.");
                None
            }
        }
    }

    /// `play_sample_sound`: the pack's `alert` sound, ignoring mutes
    /// (Settings > Audio "Play sample sound").
    pub fn play_sample(&self, pack: &str) {
        self.play_event::<&str>(pack, DEFAULT_EVENT, &[]);
    }

    /// `sound_pack_uses_specific_alert_sounds`.
    pub fn uses_specific_alert_sounds(&self, pack: &str) -> bool {
        pack::sound_pack_uses_specific_alert_sounds(pack, &self.soundpacks_dir)
    }

    /// `get_available_sound_packs`.
    pub fn available_packs(&self) -> Vec<pack::AvailablePack> {
        pack::get_available_sound_packs(&self.soundpacks_dir)
    }

    // --- PreviewPlayer (get_preview_player()) -----------------------------

    /// `PreviewPlayer.play`: stop the current preview and play `file`.
    pub fn preview_play(&self, file: &Path, volume: f64) -> bool {
        self.preview_stop();
        if !file.exists() {
            tracing::warn!("Sound file not found: {}", file.display());
            return false;
        }
        let volume = crate::py::clamp_volume(volume);
        let mut backend = self.backend();
        let Some(mixer) = backend.mixer() else {
            tracing::warn!("audio backend unavailable");
            return false;
        };
        match start(&mixer, file, volume) {
            Ok(player) => {
                backend.preview = Some(player);
                true
            }
            Err(e) => {
                tracing::warn!("sound playback failed: {e}");
                false
            }
        }
    }

    /// `PreviewPlayer.stop`.
    pub fn preview_stop(&self) {
        if let Some(player) = self.backend().preview.take() {
            player.stop();
        }
    }

    /// `PreviewPlayer.is_playing`: false once the preview has finished.
    pub fn preview_is_playing(&self) -> bool {
        self.backend().preview.as_ref().is_some_and(|p| !p.empty())
    }

    /// `PreviewPlayer.toggle`: stop a playing preview (returns false) or
    /// start `file` at full volume (returns true, even if it failed to start).
    pub fn preview_toggle(&self, file: &Path) -> bool {
        if self.preview_is_playing() {
            self.preview_stop();
            return false;
        }
        self.preview_play(file, 1.0);
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn default_pack_player() -> SoundPlayer {
        SoundPlayer::new(pack::repo_soundpacks_dir())
    }

    #[test]
    fn silent_volume_never_opens_the_device() {
        let player = default_pack_player();
        assert!(player.play_file(Path::new("missing.wav"), 0.0));
        assert!(player.backend().output.is_none());
    }

    #[test]
    fn muted_events_never_resolve() {
        let player = default_pack_player();
        assert!(player
            .resolve_event("default", "data_updated", &["data_updated"])
            .is_none());
        assert!(player
            .resolve_event::<&str>("default", "data_updated", &[])
            .is_some());
        let candidates: Vec<String> = ["discussion_update", "notify"].map(String::from).into();
        assert!(player
            .resolve_candidates(
                &candidates,
                "default",
                Some("discussion_update"),
                &["discussion_update"]
            )
            .is_none());
        // A muted primary candidate must not fall through to the fallbacks.
        let candidates: Vec<String> = ["unknown", "alert", "notify"].map(String::from).into();
        assert!(player
            .resolve_candidates(&candidates, "default", None, &["unknown"])
            .is_none());
        assert!(player
            .resolve_candidates(&candidates, "default", None, &["alert"])
            .is_some());
    }

    #[test]
    fn preview_of_missing_file_fails_without_a_device() {
        let player = default_pack_player();
        assert!(!player.preview_play(Path::new("missing.ogg"), 1.0));
        assert!(!player.preview_is_playing());
        assert!(player.backend().output.is_none());
    }
}
