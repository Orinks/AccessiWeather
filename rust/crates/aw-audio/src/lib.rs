//! Sounds for AccessiWeather: playback, sound packs, the Sound Pack
//! Manager/wizard logic and community pack sharing. No UI.
//!
//! # Integration
//!
//! App sounds go through the process-wide [`player()`]. As in Python,
//! callers check `settings.sound_enabled` first and pass
//! `settings.sound_pack` and `settings.muted_sound_events`:
//!
//! ```no_run
//! # let settings = aw_core::settings::AppSettings::default();
//! let player = aw_audio::player();
//! if settings.sound_enabled {
//!     // startup, exit, data_updated, fetch_error, discussion_update,
//!     // severe_risk, alert, notify, error, success ...
//!     player.play_event(&settings.sound_pack, "startup", &settings.muted_sound_events);
//! }
//! ```
//!
//! Weather alerts: build candidates with
//! [`alert_sounds::get_candidate_sound_events`] (`include_specific_events`
//! is true when the pack is in `settings.specific_alert_sound_packs` or
//! [`SoundPlayer::uses_specific_alert_sounds`]) and play them with
//! [`SoundPlayer::play_candidates`]. Toasts without candidates play
//! `"alert"` (urgent) or `"notify"`.
//!
//! Playback never blocks. Settings > Audio lists [`SoundPlayer::available_packs`]
//! and its "Play sample sound" is [`SoundPlayer::play_sample`]; the Sound
//! Pack Manager previews with `preview_play`/`preview_stop`/`preview_is_playing`
//! and uses [`manager`], [`installer`], [`community`] and [`submission`]
//! (blocking network calls: run them on a worker thread).
//!
//! The bundled default pack is the repository's `soundpacks/default`;
//! `packaging/package.sh` copies it beside the executable exactly like the
//! Python build, and source runs read it in place (see [`pack::soundpacks_dir`]).

pub mod alert_sounds;
pub mod community;
pub mod events;
pub mod http;
pub mod installer;
pub mod manager;
pub mod pack;
pub mod player;
mod py;
pub mod submission;

#[cfg(test)]
mod golden_tests;

pub use pack::{soundpacks_dir, validate_sound_pack, DEFAULT_EVENT, DEFAULT_PACK};
pub use player::{player, SoundPlayer};
