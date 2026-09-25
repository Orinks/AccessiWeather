//! Alert and event notifications for AccessiWeather (no UI).
//!
//! Decisions are pure and take `now` explicitly; they return [`Toast`]s
//! (plus popup / radio / Event Center requests) for the app to deliver:
//!
//! * [`alert_notifications::AlertNotificationSystem`] — alert toasts
//!   (`process_and_notify` after every refresh, `on_event_poll` for the
//!   60-second poll), backed by [`alert_manager::AlertManager`].
//! * [`events::window::process_notification_events`] — discussion, severe
//!   risk, minutely precipitation, HWO, SPS and daily climate report
//!   notifications after a full refresh, backed by
//!   [`events::NotificationEventManager`].
//! * [`toast::Notifier`] — shows a toast; [`Toast::sound_keys`] is the
//!   sound cue for the audio layer; [`activation`] handles clicks.
//! * [`runtime_state::RuntimeState`] — the `state/runtime_state.json` file
//!   shared with the Python app. Give both managers the same handle.
//! * [`debug`] — test-alert presets and notification diagnostics.

pub mod activation;
pub mod alert_manager;
pub mod alert_notifications;
pub mod debug;
pub mod events;
pub mod py;
pub mod runtime_state;
pub mod sound;
pub mod toast;

use aw_core::settings::AppSettings;

pub use activation::{ActivationKind, ActivationRequest, ActivationRoute};
pub use alert_manager::{AlertManager, AlertSettings};
pub use alert_notifications::{AlertDispatch, AlertNotificationSystem};
pub use events::window::{
    process_notification_events, CachedProducts, EventCenterEntry, EventDispatch,
};
pub use events::{NotificationEvent, NotificationEventManager};
pub use runtime_state::RuntimeState;
pub use toast::{ensure_windows_toast_identity, Notifier};

/// One desktop notification, with the arguments Python passes to
/// `send_notification(title, message, timeout, sound_event=,
/// sound_candidates=, play_sound=, activation_arguments=)`.
#[derive(Debug, Clone, PartialEq)]
pub struct Toast {
    pub title: String,
    pub message: String,
    /// Seconds.
    pub timeout: u32,
    pub sound_event: Option<String>,
    pub sound_candidates: Option<Vec<String>>,
    pub play_sound: bool,
    pub activation: Option<ActivationRequest>,
}

impl Toast {
    /// The sound keys to try in the current pack, in order, or `None` for
    /// silence (sound off, `play_sound` false, or muted).
    pub fn sound_keys(&self, settings: &AppSettings) -> Option<Vec<String>> {
        if !(settings.sound_enabled && self.play_sound) {
            return None;
        }
        sound::sound_keys_to_try(
            self.sound_event.as_deref(),
            self.sound_candidates.as_deref(),
            &settings.muted_sound_events,
        )
    }

    /// `activation_arguments` as Python passes it to the notifier.
    pub fn activation_arguments(&self) -> Option<String> {
        self.activation.as_ref().map(ActivationRequest::serialize)
    }
}
