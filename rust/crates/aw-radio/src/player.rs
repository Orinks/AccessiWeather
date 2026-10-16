//! Stream player with reconnect-on-stall and silence detection.
//!
//! Ports `noaa_radio/player.py`. Python drives BASS (`sound_lib.URLStream`);
//! here the audio side is an [`AudioBackend`] ([`crate::RodioBackend`] in
//! the app, a fake in tests).
//!
//! `play` blocks while the stream connects (like `URLStream(url=...)`), so
//! call it from a worker thread. The player's lock is never held while
//! connecting, so `is_playing`, `stop` and `set_volume` stay instant from
//! any thread.

use std::sync::{Arc, Mutex};

/// Opens network audio streams.
pub trait AudioBackend: Send + Sync {
    /// Connect to `url` and start playing at `volume` (0.0–1.0). Blocks until
    /// audio is flowing or the stream failed.
    fn open(&self, url: &str, volume: f32) -> Result<Box<dyn AudioStream>, String>;
}

/// A playing stream (BASS channel equivalent).
pub trait AudioStream: Send {
    fn set_volume(&self, volume: f32);
    /// Actively playing: not stopped, not ended and not stalled.
    fn is_playing(&self) -> bool;
    /// Playback is starved for data.
    fn is_stalled(&self) -> bool;
    /// Recent peak level before volume; 0 means digital silence.
    fn level(&self) -> u32;
    /// Stop and release the stream.
    fn stop(&self);
}

/// Player notifications (Python's `on_playing` … `on_reconnecting`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PlayerEvent {
    Playing,
    Stopped,
    Error(String),
    Stalled,
    Reconnecting(u32),
}

pub type PlayerEventHandler = Arc<dyn Fn(PlayerEvent) + Send + Sync>;

/// Automatic reconnection attempts on a stall.
pub const MAX_RETRIES: u32 = 2;
/// Consecutive silent health checks before auto-advancing (3 × 5 s timer).
pub const SILENCE_THRESHOLD: u32 = 3;

struct PlayerState {
    stream: Option<Box<dyn AudioStream>>,
    volume: f64,
    current_url: Option<String>,
    retry_count: u32,
    silence_count: u32,
    /// Bumped by every play/retry/stop so a connect that finishes after a
    /// newer request is discarded instead of playing over it.
    generation: u64,
}

pub struct RadioPlayer {
    backend: Arc<dyn AudioBackend>,
    state: Mutex<PlayerState>,
    on_event: PlayerEventHandler,
}

impl RadioPlayer {
    pub fn new(backend: Arc<dyn AudioBackend>, on_event: PlayerEventHandler) -> Self {
        Self {
            backend,
            state: Mutex::new(PlayerState {
                stream: None,
                volume: 1.0,
                current_url: None,
                retry_count: 0,
                silence_count: 0,
                generation: 0,
            }),
            on_event,
        }
    }

    /// Stop anything playing, then stream `url`. Returns whether playback
    /// started. Blocks while connecting.
    pub fn play(&self, url: &str) -> bool {
        self.stop(true);
        let generation = {
            let mut state = self.state.lock().unwrap();
            state.current_url = Some(url.to_string());
            state.retry_count = 0;
            state.generation
        };
        self.start_stream(url, generation)
    }

    fn start_stream(&self, url: &str, generation: u64) -> bool {
        let volume = self.state.lock().unwrap().volume as f32;
        match self.backend.open(url, volume) {
            Ok(stream) => {
                {
                    let mut state = self.state.lock().unwrap();
                    if state.generation != generation {
                        drop(state);
                        stream.stop();
                        return false;
                    }
                    // Volume may have moved while connecting.
                    stream.set_volume(state.volume as f32);
                    state.stream = Some(stream);
                    state.current_url = Some(url.to_string());
                    state.silence_count = 0;
                }
                tracing::info!("Started streaming: {url}");
                (self.on_event)(PlayerEvent::Playing);
                true
            }
            Err(e) => {
                let message = format!("Failed to start stream: {e}");
                tracing::error!("{message}");
                if self.state.lock().unwrap().generation != generation {
                    return false;
                }
                (self.on_event)(PlayerEvent::Error(message));
                false
            }
        }
    }

    /// Reconnect the current URL after a stall. `false` once retries are
    /// exhausted (reported as an error) or when nothing was playing.
    pub fn retry(&self) -> bool {
        let (url, attempt, generation, old) = {
            let mut state = self.state.lock().unwrap();
            let Some(url) = state.current_url.clone() else {
                return false;
            };
            state.retry_count += 1;
            if state.retry_count > MAX_RETRIES {
                drop(state);
                let message = "Stream unavailable after multiple attempts".to_string();
                tracing::error!("{message}");
                (self.on_event)(PlayerEvent::Error(message));
                return false;
            }
            state.generation += 1;
            (
                url,
                state.retry_count,
                state.generation,
                state.stream.take(),
            )
        };
        tracing::info!("Reconnecting (attempt {attempt}/{MAX_RETRIES})");
        (self.on_event)(PlayerEvent::Reconnecting(attempt));
        // Drop the old stream without an on_stopped notification.
        if let Some(old) = old {
            old.stop();
        }
        self.start_stream(&url, generation)
    }

    /// Stop and release the stream; `notify` fires `Stopped` if it was
    /// playing (callers switching streams pass `false` to avoid flicker).
    pub fn stop(&self, notify: bool) {
        let was_playing = self.is_playing();
        let stream = {
            let mut state = self.state.lock().unwrap();
            state.generation += 1;
            state.stream.take()
        };
        if let Some(stream) = stream {
            stream.stop();
        }
        if notify && was_playing {
            (self.on_event)(PlayerEvent::Stopped);
        }
    }

    /// Volume 0.0–1.0, clamped; applies to the live stream too.
    pub fn set_volume(&self, level: f64) {
        let mut state = self.state.lock().unwrap();
        state.volume = level.clamp(0.0, 1.0);
        if let Some(stream) = &state.stream {
            stream.set_volume(state.volume as f32);
        }
    }

    pub fn get_volume(&self) -> f64 {
        self.state.lock().unwrap().volume
    }

    pub fn is_playing(&self) -> bool {
        let state = self.state.lock().unwrap();
        state.stream.as_ref().is_some_and(|s| s.is_playing())
    }

    pub fn is_stalled(&self) -> bool {
        let state = self.state.lock().unwrap();
        state.stream.as_ref().is_some_and(|s| s.is_stalled())
    }

    pub fn get_level(&self) -> u32 {
        let state = self.state.lock().unwrap();
        state.stream.as_ref().map_or(0, |s| s.level())
    }

    fn has_stream(&self) -> bool {
        self.state.lock().unwrap().stream.is_some()
    }

    /// Periodic health check (every 5 s while the dialog is open): reconnect
    /// on a stall, and after [`SILENCE_THRESHOLD`] silent checks call
    /// `on_auto_advance`.
    pub fn check_health(&self, on_auto_advance: impl FnOnce()) {
        if !self.has_stream() {
            return;
        }
        if self.is_stalled() {
            tracing::warn!("Stream stalled, attempting reconnect");
            (self.on_event)(PlayerEvent::Stalled);
            self.retry();
            return;
        }
        if self.is_playing() && self.get_level() == 0 {
            let advance = {
                let mut state = self.state.lock().unwrap();
                state.silence_count += 1;
                let count = state.silence_count;
                if count >= SILENCE_THRESHOLD {
                    tracing::warn!("Stream silent for {count} checks, auto-advancing");
                    state.silence_count = 0;
                }
                count >= SILENCE_THRESHOLD
            };
            if advance {
                on_auto_advance();
            }
        } else {
            self.state.lock().unwrap().silence_count = 0;
        }
    }
}

#[cfg(test)]
pub(crate) mod fake {
    //! A scriptable backend for tests.
    use super::*;
    use std::collections::VecDeque;
    use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};

    #[derive(Default)]
    pub struct FakeStreamState {
        pub playing: AtomicBool,
        pub stalled: AtomicBool,
        pub level: AtomicU32,
        pub volume: Mutex<f32>,
        pub stopped: AtomicBool,
    }

    struct FakeStream(Arc<FakeStreamState>);

    impl AudioStream for FakeStream {
        fn set_volume(&self, volume: f32) {
            *self.0.volume.lock().unwrap() = volume;
        }
        fn is_playing(&self) -> bool {
            self.0.playing.load(Ordering::SeqCst)
        }
        fn is_stalled(&self) -> bool {
            self.0.stalled.load(Ordering::SeqCst)
        }
        fn level(&self) -> u32 {
            self.0.level.load(Ordering::SeqCst)
        }
        fn stop(&self) {
            self.0.stopped.store(true, Ordering::SeqCst);
            self.0.playing.store(false, Ordering::SeqCst);
        }
    }

    /// Opens succeed unless a result was queued with [`FakeBackend::results`].
    #[derive(Default)]
    pub struct FakeBackend {
        pub opened: Mutex<Vec<String>>,
        pub results: Mutex<VecDeque<Result<(), String>>>,
        pub streams: Mutex<Vec<Arc<FakeStreamState>>>,
        /// Streams start but report not playing (stale backend state).
        pub stale: AtomicBool,
    }

    impl FakeBackend {
        pub fn with_results(results: &[bool]) -> Arc<Self> {
            let backend = Self::default();
            *backend.results.lock().unwrap() = results
                .iter()
                .map(|ok| {
                    if *ok {
                        Ok(())
                    } else {
                        Err("refused".to_string())
                    }
                })
                .collect();
            Arc::new(backend)
        }

        pub fn opened(&self) -> Vec<String> {
            self.opened.lock().unwrap().clone()
        }

        pub fn last_stream(&self) -> Arc<FakeStreamState> {
            self.streams.lock().unwrap().last().unwrap().clone()
        }
    }

    impl AudioBackend for FakeBackend {
        fn open(&self, url: &str, volume: f32) -> Result<Box<dyn AudioStream>, String> {
            self.opened.lock().unwrap().push(url.to_string());
            self.results.lock().unwrap().pop_front().unwrap_or(Ok(()))?;
            let state = Arc::new(FakeStreamState::default());
            state
                .playing
                .store(!self.stale.load(Ordering::SeqCst), Ordering::SeqCst);
            state.level.store(100, Ordering::SeqCst);
            *state.volume.lock().unwrap() = volume;
            self.streams.lock().unwrap().push(state.clone());
            Ok(Box::new(FakeStream(state)))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::fake::FakeBackend;
    use super::*;
    use std::sync::atomic::Ordering;

    fn player(backend: Arc<FakeBackend>) -> (RadioPlayer, Arc<Mutex<Vec<PlayerEvent>>>) {
        let events = Arc::new(Mutex::new(Vec::new()));
        let sink = events.clone();
        let player = RadioPlayer::new(backend, Arc::new(move |e| sink.lock().unwrap().push(e)));
        (player, events)
    }

    #[test]
    fn defaults_and_volume_clamping() {
        let (player, _) = player(Arc::new(FakeBackend::default()));
        assert_eq!(player.get_volume(), 1.0);
        assert!(!player.is_playing() && !player.is_stalled());
        assert_eq!(player.get_level(), 0);
        player.set_volume(1.5);
        assert_eq!(player.get_volume(), 1.0);
        player.set_volume(-0.5);
        assert_eq!(player.get_volume(), 0.0);
        player.set_volume(0.75);
        assert_eq!(player.get_volume(), 0.75);
        assert!(!player.retry());
        player.stop(true);
        player.check_health(|| panic!("no stream, no advance"));
    }

    #[test]
    fn play_success_error_and_restart() {
        let backend = FakeBackend::with_results(&[true, false]);
        let (player, events) = player(backend.clone());
        player.set_volume(0.5);
        assert!(player.play("http://a"));
        assert!(player.is_playing());
        assert_eq!(*backend.last_stream().volume.lock().unwrap(), 0.5);
        player.set_volume(0.25);
        assert_eq!(*backend.last_stream().volume.lock().unwrap(), 0.25);
        let first = backend.last_stream();

        // A second play stops (and reports) the first stream.
        assert!(!player.play("http://b"));
        assert!(first.stopped.load(Ordering::SeqCst));
        assert_eq!(
            *events.lock().unwrap(),
            [
                PlayerEvent::Playing,
                PlayerEvent::Stopped,
                PlayerEvent::Error("Failed to start stream: refused".into())
            ]
        );
        assert!(!player.is_playing());
    }

    #[test]
    fn stop_without_notify_is_silent() {
        let backend = Arc::new(FakeBackend::default());
        let (player, events) = player(backend.clone());
        player.play("http://a");
        player.stop(false);
        assert!(backend.last_stream().stopped.load(Ordering::SeqCst));
        assert_eq!(*events.lock().unwrap(), [PlayerEvent::Playing]);
    }

    #[test]
    fn stall_retries_until_exhausted() {
        let backend = Arc::new(FakeBackend::default());
        let (player, events) = player(backend.clone());
        player.play("http://a");
        for _ in 0..3 {
            backend.last_stream().stalled.store(true, Ordering::SeqCst);
            player.check_health(|| panic!("stall is not silence"));
        }
        assert_eq!(backend.opened(), ["http://a", "http://a", "http://a"]);
        assert_eq!(
            *events.lock().unwrap(),
            [
                PlayerEvent::Playing,
                PlayerEvent::Stalled,
                PlayerEvent::Reconnecting(1),
                PlayerEvent::Playing,
                PlayerEvent::Stalled,
                PlayerEvent::Reconnecting(2),
                PlayerEvent::Playing,
                PlayerEvent::Stalled,
                PlayerEvent::Error("Stream unavailable after multiple attempts".into()),
            ]
        );
    }

    #[test]
    fn silence_advances_after_three_checks_and_resets_on_sound() {
        let backend = Arc::new(FakeBackend::default());
        let (player, _) = player(backend.clone());
        player.play("http://a");
        let stream = backend.last_stream();
        let advanced = std::cell::Cell::new(0);
        stream.level.store(0, Ordering::SeqCst);
        player.check_health(|| advanced.set(advanced.get() + 1));
        player.check_health(|| advanced.set(advanced.get() + 1));
        stream.level.store(5, Ordering::SeqCst);
        player.check_health(|| advanced.set(advanced.get() + 1));
        stream.level.store(0, Ordering::SeqCst);
        for _ in 0..3 {
            player.check_health(|| advanced.set(advanced.get() + 1));
        }
        assert_eq!(advanced.get(), 1);
        // Not playing resets the count too.
        player.check_health(|| {});
        stream.playing.store(false, Ordering::SeqCst);
        player.check_health(|| {});
        stream.playing.store(true, Ordering::SeqCst);
        player.check_health(|| {});
        player.check_health(|| advanced.set(advanced.get() + 1));
        assert_eq!(advanced.get(), 1);
    }
}
