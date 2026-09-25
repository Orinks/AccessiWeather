//! Play/stop NOAA Weather Radio without the dialog (the system-wide
//! hotkey). Every outcome is reported through `notify` (a desktop
//! notification in the app) because the window is usually hidden.
//!
//! Ports `noaa_radio/toggle.py`.

use std::sync::Arc;

use crate::auto_tune::AlertRadioAutoTuner;
use crate::preferences::SharedPreferences;
use crate::session::RadioSession;
use crate::stations::{Station, StationDatabase};
use crate::stream_url::StreamUrls;
use crate::Spawner;

pub const NO_STATION_MESSAGE: &str = "No station to play yet. Open NOAA Weather Radio and play a \
                                      station once, then this hotkey will resume it.";

pub type NotifyCallback = Arc<dyn Fn(String) + Send + Sync>;

pub struct RadioToggleController {
    session: Arc<RadioSession>,
    preferences: SharedPreferences,
    station_database: Arc<StationDatabase>,
    url_provider: Arc<dyn StreamUrls>,
    notify: Option<NotifyCallback>,
    auto_tuner: Option<Arc<AlertRadioAutoTuner>>,
    spawn: Spawner,
}

impl RadioToggleController {
    pub fn new(
        session: Arc<RadioSession>,
        preferences: SharedPreferences,
        station_database: Arc<StationDatabase>,
        url_provider: Arc<dyn StreamUrls>,
        notify: Option<NotifyCallback>,
        auto_tuner: Option<Arc<AlertRadioAutoTuner>>,
        spawn: Spawner,
    ) -> Arc<Self> {
        Arc::new(Self {
            session,
            preferences,
            station_database,
            url_provider,
            notify,
            auto_tuner,
            spawn,
        })
    }

    /// Stop if the radio is on; otherwise resume the last station on a
    /// worker thread.
    pub fn toggle(self: &Arc<Self>) {
        if self.session.is_playing() {
            self.stop();
            return;
        }
        let this = self.clone();
        (self.spawn)(Box::new(move || this.start()));
    }

    fn stop(&self) {
        // Keep a pending alert auto-tune from restarting what was just stopped.
        if let Some(tuner) = &self.auto_tuner {
            tuner.stop();
        }
        self.session.stop(true);
        // The silence is the confirmation; no notification on stop.
        tracing::info!("NOAA Weather Radio hotkey: stopped.");
    }

    fn start(&self) {
        let Some(call_sign) = self.resolve_call_sign() else {
            self.announce(NO_STATION_MESSAGE.to_string());
            return;
        };
        let Some(station) = self
            .station_database
            .get_stations_by_call_signs(&[&call_sign])
            .into_iter()
            .next()
        else {
            self.announce(format!("{call_sign} is no longer in the station list."));
            return;
        };
        let found = self.url_provider.get_stream_urls(&station.call_sign);
        let urls = self
            .preferences
            .lock()
            .unwrap()
            .reorder_urls(&station.call_sign, &found);
        if urls.is_empty() {
            self.announce(format!("No stream is available for {}.", station.call_sign));
            return;
        }
        self.play(station, urls);
    }

    /// The last station played, else the first favorite.
    fn resolve_call_sign(&self) -> Option<String> {
        let prefs = self.preferences.lock().unwrap();
        prefs
            .get_last_station()
            .or_else(|| prefs.get_favorite_stations().into_iter().next())
    }

    fn play(&self, station: Station, urls: Vec<String>) {
        self.session.update(|s| {
            s.playing_station = Some(station.clone());
            s.current_urls = urls.clone();
            s.current_url_index = 0;
        });
        for (index, url) in urls.iter().enumerate() {
            self.session.update(|s| s.current_url_index = index);
            if self.session.player.play(url) {
                // Station names already end in the state ("Mobile, AL").
                self.announce(format!("Playing {}, {}.", station.call_sign, station.name));
                return;
            }
        }
        self.session.update(|s| s.playing_station = None);
        self.announce(format!("Could not start {}.", station.call_sign));
    }

    fn announce(&self, message: String) {
        tracing::info!("NOAA Weather Radio hotkey: {message}");
        if let Some(notify) = &self.notify {
            notify(message);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::player::fake::FakeBackend;
    use crate::preferences::RadioPreferences;
    use std::sync::Mutex;

    fn wxk27() -> Station {
        Station::new("WXK27", 162.4, "Austin", 30.2672, -97.7431, "TX")
    }

    fn wxl58() -> Station {
        Station::new("WXL58", 162.55, "Dallas", 32.7767, -96.797, "TX")
    }

    struct Setup {
        last_station: Option<&'static str>,
        favorites: Vec<&'static str>,
        stations: Vec<Station>,
        urls: Vec<&'static str>,
        play_results: Vec<bool>,
    }

    impl Default for Setup {
        fn default() -> Self {
            Self {
                last_station: Some("WXK27"),
                favorites: vec![],
                stations: vec![wxk27(), wxl58()],
                urls: vec!["http://a", "http://b"],
                play_results: vec![true],
            }
        }
    }

    struct Harness {
        controller: Arc<RadioToggleController>,
        session: Arc<RadioSession>,
        backend: Arc<FakeBackend>,
        prefs: SharedPreferences,
        lookups: Arc<Mutex<Vec<String>>>,
        notes: Arc<Mutex<Vec<String>>>,
    }

    fn harness(setup: Setup, auto_tuner: Option<Arc<AlertRadioAutoTuner>>) -> Harness {
        let backend = FakeBackend::with_results(&setup.play_results);
        let prefs = RadioPreferences::new(None).shared();
        {
            let mut p = prefs.lock().unwrap();
            p.set_last_station(setup.last_station);
            p.set_favorite_stations(&setup.favorites);
        }
        let session = RadioSession::new(backend.clone(), Some(prefs.clone()));
        let lookups = Arc::new(Mutex::new(Vec::new()));
        let log = lookups.clone();
        let urls: Vec<String> = setup.urls.iter().map(|u| u.to_string()).collect();
        let notes = Arc::new(Mutex::new(Vec::new()));
        let sink = notes.clone();
        let controller = RadioToggleController::new(
            session.clone(),
            prefs.clone(),
            Arc::new(StationDatabase::with_stations(setup.stations)),
            Arc::new(move |cs: &str| {
                log.lock().unwrap().push(cs.to_string());
                urls.clone()
            }),
            Some(Arc::new(move |m| sink.lock().unwrap().push(m))),
            auto_tuner,
            Arc::new(|work| work()),
        );
        Harness {
            controller,
            session,
            backend,
            prefs,
            lookups,
            notes,
        }
    }

    impl Harness {
        fn last_note(&self) -> String {
            self.notes
                .lock()
                .unwrap()
                .last()
                .cloned()
                .unwrap_or_default()
        }
    }

    #[test]
    fn stops_playback_without_a_notification() {
        let h = harness(Setup::default(), None);
        h.session.player.play("http://x");
        h.controller.toggle();
        assert!(!h.session.is_playing());
        assert!(h.lookups.lock().unwrap().is_empty());
        assert!(h.notes.lock().unwrap().is_empty());
    }

    #[test]
    fn stopping_cancels_pending_alert_auto_tune() {
        use crate::auto_tune::{AlertStationResolver, AutoTunerDeps};
        use aw_core::model::WeatherAlert;
        use aw_core::{AppSettings, Location};

        struct Fixed;
        impl AlertStationResolver for Fixed {
            fn resolve_station(&self, _: &[WeatherAlert], _: Option<&Location>) -> Option<Station> {
                Some(wxk27())
            }
        }

        let backend = Arc::new(FakeBackend::default());
        let session = RadioSession::new(backend.clone(), None);
        let pending: Arc<Mutex<Vec<crate::Work>>> = Arc::default();
        let queue = pending.clone();
        let tuner = AlertRadioAutoTuner::new(AutoTunerDeps {
            settings_provider: Box::new(|| {
                Some(AppSettings {
                    auto_tune_weather_radio_alerts: true,
                    ..AppSettings::default()
                })
            }),
            location_provider: Box::new(|| None),
            status_callback: None,
            session: session.clone(),
            preferences: RadioPreferences::new(None).shared(),
            station_resolver: Arc::new(Fixed),
            url_provider: Arc::new(|_: &str| vec!["http://auto".to_string()]),
            spawn: Arc::new(move |work| queue.lock().unwrap().push(work)),
            monotonic: Arc::new(crate::auto_tune::monotonic),
        });
        let mut alert = WeatherAlert::new("Tornado Warning", "body");
        alert.same_codes = vec!["048453".into()];
        alert.same_event_codes = vec!["TOR".into()];
        tuner.tune_for_alerts(&[alert]);

        let controller = RadioToggleController::new(
            session.clone(),
            RadioPreferences::new(None).shared(),
            Arc::new(StationDatabase::new()),
            Arc::new(|_: &str| Vec::new()),
            None,
            Some(tuner),
            Arc::new(|work| work()),
        );
        session.player.play("http://manual");
        controller.toggle();
        assert!(!session.is_playing());

        // The cancelled worker must not put the station back on the air.
        let work = pending.lock().unwrap().remove(0);
        work();
        assert_eq!(backend.opened(), ["http://manual"]);
    }

    #[test]
    fn plays_last_station() {
        let h = harness(Setup::default(), None);
        h.controller.toggle();
        assert_eq!(*h.lookups.lock().unwrap(), ["WXK27"]);
        assert_eq!(h.backend.opened(), ["http://a"]);
        let state = h.session.state();
        assert_eq!(state.playing_station, Some(wxk27()));
        assert_eq!(state.current_urls, ["http://a", "http://b"]);
        assert_eq!(state.current_url_index, 0);
        assert_eq!(h.last_note(), "Playing WXK27, Austin.");
    }

    #[test]
    fn falls_back_to_first_favorite_without_history() {
        let h = harness(
            Setup {
                last_station: None,
                favorites: vec!["WXL58", "WXK27"],
                ..Default::default()
            },
            None,
        );
        h.controller.toggle();
        assert_eq!(*h.lookups.lock().unwrap(), ["WXL58"]);
        // Once it plays, the session remembers it for the next toggle.
        assert_eq!(
            h.prefs.lock().unwrap().get_last_station().as_deref(),
            Some("WXL58")
        );
    }

    #[test]
    fn announces_missing_station_stream_or_history() {
        let h = harness(
            Setup {
                last_station: None,
                ..Default::default()
            },
            None,
        );
        h.controller.toggle();
        assert_eq!(h.last_note(), NO_STATION_MESSAGE);
        assert!(h.backend.opened().is_empty());

        let h = harness(
            Setup {
                stations: vec![],
                ..Default::default()
            },
            None,
        );
        h.controller.toggle();
        assert_eq!(h.last_note(), "WXK27 is no longer in the station list.");

        let h = harness(
            Setup {
                urls: vec![],
                ..Default::default()
            },
            None,
        );
        h.controller.toggle();
        assert_eq!(h.last_note(), "No stream is available for WXK27.");
        assert_eq!(h.session.playing_station(), None);
    }

    #[test]
    fn falls_through_failed_streams() {
        let h = harness(
            Setup {
                play_results: vec![false, true],
                ..Default::default()
            },
            None,
        );
        h.controller.toggle();
        assert_eq!(h.backend.opened(), ["http://a", "http://b"]);
        assert_eq!(h.session.state().current_url_index, 1);
        assert_eq!(h.last_note(), "Playing WXK27, Austin.");

        let h = harness(
            Setup {
                play_results: vec![false, false],
                ..Default::default()
            },
            None,
        );
        h.controller.toggle();
        assert_eq!(h.session.playing_station(), None);
        assert_eq!(h.last_note(), "Could not start WXK27.");
    }

    #[test]
    fn honors_preferred_stream_ordering() {
        let h = harness(Setup::default(), None);
        h.prefs
            .lock()
            .unwrap()
            .set_preferred_url("WXK27", "http://b");
        h.controller.toggle();
        assert_eq!(h.backend.opened(), ["http://b"]);
    }
}
