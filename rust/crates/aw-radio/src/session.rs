//! The app-wide NOAA Weather Radio playback session, shared by the dialog,
//! the global hotkey and alert auto-tune. It outlives any one dialog.
//!
//! Ports `noaa_radio/session.py`. Python keeps one module-level session
//! (`get_shared_radio_session`); the Rust app creates one `Arc<RadioSession>`
//! (see [`crate::RadioContext`]).

use std::sync::{Arc, Mutex, Weak};

use crate::player::{AudioBackend, PlayerEvent, RadioPlayer};
use crate::preferences::SharedPreferences;
use crate::stations::Station;

/// Session callback for whoever is showing playback (the open dialog).
/// Called on the thread that produced the event; the receiver is
/// responsible for getting onto its UI thread.
pub type SessionCallback = Arc<dyn Fn(PlayerEvent) + Send + Sync>;

/// What is on the air.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct SessionState {
    pub playing_station: Option<Station>,
    pub current_urls: Vec<String>,
    pub current_url_index: usize,
}

pub struct RadioSession {
    pub player: RadioPlayer,
    preferences: Option<SharedPreferences>,
    state: Mutex<SessionState>,
    callback: Mutex<Option<SessionCallback>>,
}

impl RadioSession {
    pub fn new(
        backend: Arc<dyn AudioBackend>,
        preferences: Option<SharedPreferences>,
    ) -> Arc<Self> {
        Arc::new_cyclic(|weak: &Weak<RadioSession>| {
            let weak = weak.clone();
            let on_event = Arc::new(move |event: PlayerEvent| {
                if let Some(session) = weak.upgrade() {
                    session.handle_player_event(event);
                }
            });
            Self {
                player: RadioPlayer::new(backend, on_event),
                preferences,
                state: Mutex::default(),
                callback: Mutex::new(None),
            }
        })
    }

    /// Attach the visible dialog's callback.
    pub fn bind_callbacks(&self, callback: SessionCallback) {
        *self.callback.lock().unwrap() = Some(callback);
    }

    /// Detach it when the dialog closes (playback keeps going).
    pub fn unbind_callbacks(&self) {
        *self.callback.lock().unwrap() = None;
    }

    pub fn is_playing(&self) -> bool {
        self.player.is_playing()
    }

    /// Stop playback and forget the station.
    pub fn stop(&self, notify: bool) {
        self.player.stop(notify);
        self.state.lock().unwrap().playing_station = None;
    }

    pub fn state(&self) -> SessionState {
        self.state.lock().unwrap().clone()
    }

    pub fn playing_station(&self) -> Option<Station> {
        self.state.lock().unwrap().playing_station.clone()
    }

    /// Change session state atomically. Do not call player methods inside.
    pub fn update<R>(&self, change: impl FnOnce(&mut SessionState) -> R) -> R {
        change(&mut self.state.lock().unwrap())
    }

    fn handle_player_event(&self, event: PlayerEvent) {
        match &event {
            // Both the dialog and auto-tune set the station before starting
            // the player, so recording it here covers every path on the air.
            PlayerEvent::Playing => self.remember_last_station(),
            PlayerEvent::Stopped | PlayerEvent::Error(_) => {
                self.state.lock().unwrap().playing_station = None;
            }
            PlayerEvent::Stalled | PlayerEvent::Reconnecting(_) => {}
        }
        let callback = self.callback.lock().unwrap().clone();
        if let Some(callback) = callback {
            callback(event);
        }
    }

    /// Persist the station so the hotkey can resume it later.
    fn remember_last_station(&self) {
        let (Some(prefs), Some(station)) = (&self.preferences, self.playing_station()) else {
            return;
        };
        prefs
            .lock()
            .unwrap()
            .set_last_station(Some(&station.call_sign));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::player::fake::FakeBackend;
    use crate::preferences::RadioPreferences;

    fn wxk27() -> Station {
        Station::new("WXK27", 162.4, "Austin", 30.2672, -97.7431, "TX")
    }

    #[test]
    fn records_last_station_and_forwards_events() {
        let prefs = RadioPreferences::new(None).shared();
        let session = RadioSession::new(Arc::new(FakeBackend::default()), Some(prefs.clone()));
        let events = Arc::new(Mutex::new(Vec::new()));
        let sink = events.clone();
        session.bind_callbacks(Arc::new(move |e| sink.lock().unwrap().push(e)));

        // No station: nothing recorded.
        assert!(session.player.play("http://a"));
        assert_eq!(prefs.lock().unwrap().get_last_station(), None);

        // Callers switching streams stop quietly first, as the dialog does.
        session.player.stop(false);
        session.update(|s| s.playing_station = Some(wxk27()));
        assert!(session.player.play("http://b"));
        assert_eq!(
            prefs.lock().unwrap().get_last_station().as_deref(),
            Some("WXK27")
        );
        assert_eq!(session.playing_station(), Some(wxk27()));
        assert!(session.is_playing());

        session.stop(true);
        assert_eq!(session.playing_station(), None);
        assert!(!session.is_playing());
        assert_eq!(
            *events.lock().unwrap(),
            [
                PlayerEvent::Playing,
                PlayerEvent::Playing,
                PlayerEvent::Stopped
            ]
        );
    }

    #[test]
    fn error_clears_station_and_unbind_keeps_playing() {
        let session = RadioSession::new(FakeBackend::with_results(&[false, true]), None);
        session.update(|s| s.playing_station = Some(wxk27()));
        assert!(!session.player.play("http://a"));
        assert_eq!(session.playing_station(), None);

        let events = Arc::new(Mutex::new(0));
        let sink = events.clone();
        session.bind_callbacks(Arc::new(move |_| *sink.lock().unwrap() += 1));
        session.unbind_callbacks();
        assert!(session.player.play("http://b"));
        assert!(session.is_playing());
        assert_eq!(*events.lock().unwrap(), 0);
    }
}
