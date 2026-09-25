//! Automatic NOAA Weather Radio tuning for newly issued alerts.
//!
//! Ports `noaa_radio/alert_auto_tune.py` (plus the tiny eligibility check
//! from `alert_notification_system.py` that decides which notifications
//! reach it).

use std::collections::BTreeSet;
use std::sync::{Arc, Condvar, Mutex, OnceLock};
use std::time::Instant;

use aw_core::model::WeatherAlert;
use aw_core::{AppSettings, Location};

use crate::preferences::SharedPreferences;
use crate::session::RadioSession;
use crate::stations::{Station, StationDatabase};
use crate::stream_url::StreamUrls;
use crate::weatherindex::{normalize_same_code, WeatherIndexClient};
use crate::Spawner;

/// NWS puts this placeholder in `eventCode.SAME` when a product has no
/// SAME/EAS event code at all; no physical radio wakes for it.
const GENERIC_SAME_EVENT_CODE: &str = "NWS";

const STATE_FIPS: &[(&str, &str)] = &[
    ("AL", "01"),
    ("AK", "02"),
    ("AZ", "04"),
    ("AR", "05"),
    ("CA", "06"),
    ("CO", "08"),
    ("CT", "09"),
    ("DE", "10"),
    ("DC", "11"),
    ("FL", "12"),
    ("GA", "13"),
    ("HI", "15"),
    ("ID", "16"),
    ("IL", "17"),
    ("IN", "18"),
    ("IA", "19"),
    ("KS", "20"),
    ("KY", "21"),
    ("LA", "22"),
    ("ME", "23"),
    ("MD", "24"),
    ("MA", "25"),
    ("MI", "26"),
    ("MN", "27"),
    ("MS", "28"),
    ("MO", "29"),
    ("MT", "30"),
    ("NE", "31"),
    ("NV", "32"),
    ("NH", "33"),
    ("NJ", "34"),
    ("NM", "35"),
    ("NY", "36"),
    ("NC", "37"),
    ("ND", "38"),
    ("OH", "39"),
    ("OK", "40"),
    ("OR", "41"),
    ("PA", "42"),
    ("RI", "44"),
    ("SC", "45"),
    ("SD", "46"),
    ("TN", "47"),
    ("TX", "48"),
    ("UT", "49"),
    ("VT", "50"),
    ("VA", "51"),
    ("WA", "53"),
    ("WV", "54"),
    ("WI", "55"),
    ("WY", "56"),
    ("AS", "60"),
    ("GU", "66"),
    ("MP", "69"),
    ("PR", "72"),
    ("VI", "78"),
];

/// SAME county codes NWS published for an alert (`geocode.SAME` only; a
/// county zone id is never turned into a SAME code).
pub fn alert_same_codes(alert: &WeatherAlert) -> BTreeSet<String> {
    alert
        .same_codes
        .iter()
        .filter_map(|v| normalize_same_code(v))
        .collect()
}

/// SAME/EAS event codes in the alert's radio header, minus the generic
/// `NWS` placeholder.
pub fn same_event_codes(alert: &WeatherAlert) -> BTreeSet<String> {
    alert
        .same_event_codes
        .iter()
        .map(|v| v.trim().to_uppercase())
        .filter(|v| !v.is_empty() && v != GENERIC_SAME_EVENT_CODE)
        .collect()
}

/// Whether a real SAME weather radio would wake: it needs both an event code
/// and county codes.
pub fn would_wake_same_radio(alert: &WeatherAlert) -> bool {
    !same_event_codes(alert).is_empty() && !alert_same_codes(alert).is_empty()
}

/// `alert_notification_system._should_auto_tune_for_alert_notification`:
/// only a first issuance (`messageType` Alert or missing) or a severity
/// escalation tunes the radio. `reason` is the AlertManager's notification
/// reason (`"new_alert"`, `"severity_escalated"`, ...).
pub fn should_auto_tune_for_alert_notification(alert: &WeatherAlert, reason: &str) -> bool {
    match reason {
        "new_alert" => alert
            .message_type
            .as_deref()
            .is_none_or(|t| matches!(t.trim().to_lowercase().as_str(), "" | "alert")),
        _ => reason == "severity_escalated",
    }
}

/// Resolves an alert batch to a station that reliably covers it.
pub trait AlertStationResolver: Send + Sync {
    fn resolve_station(
        &self,
        alerts: &[WeatherAlert],
        location: Option<&Location>,
    ) -> Option<Station>;
}

/// Always skips: nearest or favorite would be a guess without coverage data.
pub struct NoReliableAlertStationResolver;

impl AlertStationResolver for NoReliableAlertStationResolver {
    fn resolve_station(&self, _: &[WeatherAlert], _: Option<&Location>) -> Option<Station> {
        None
    }
}

/// Matches alert SAME county codes against WeatherIndex station coverage.
pub struct WeatherIndexAlertStationResolver {
    station_database: Arc<StationDatabase>,
    weatherindex: Arc<WeatherIndexClient>,
}

impl WeatherIndexAlertStationResolver {
    pub fn new(
        station_database: Arc<StationDatabase>,
        weatherindex: Arc<WeatherIndexClient>,
    ) -> Self {
        Self {
            station_database,
            weatherindex,
        }
    }

    /// Nearest-first with a location; otherwise stations in the affected
    /// states first, then by call sign.
    fn candidate_stations(
        &self,
        location: Option<&Location>,
        states: &BTreeSet<String>,
    ) -> Vec<Station> {
        if let Some(location) = location {
            return self
                .station_database
                .find_nearest(location.latitude, location.longitude, None)
                .into_iter()
                .map(|r| r.station)
                .collect();
        }
        let mut stations = self.station_database.get_all_stations();
        stations.sort_by_key(|s| {
            (
                !states.contains(&s.state.to_uppercase()),
                s.call_sign.to_uppercase(),
            )
        });
        stations
    }
}

fn county_zone_state(zone_id: &str) -> Option<String> {
    let normalized = zone_id.rsplit('/').next()?.trim().to_uppercase();
    let b = normalized.as_bytes();
    let matches = b.len() == 6
        && b[..2].iter().all(u8::is_ascii_uppercase)
        && b[2] == b'C'
        && b[3..].iter().all(u8::is_ascii_digit);
    matches.then(|| normalized[..2].to_string())
}

fn same_code_to_state(same_code: &str) -> Option<&'static str> {
    if same_code.len() != 6 {
        return None;
    }
    let fips = &same_code[1..3];
    STATE_FIPS.iter().find(|(_, f)| *f == fips).map(|(s, _)| *s)
}

pub(crate) fn alert_states(alerts: &[WeatherAlert]) -> BTreeSet<String> {
    let mut states = BTreeSet::new();
    for alert in alerts {
        states.extend(
            alert
                .affected_zones
                .iter()
                .filter_map(|z| county_zone_state(z)),
        );
        states.extend(
            alert_same_codes(alert)
                .iter()
                .filter_map(|c| same_code_to_state(c))
                .map(str::to_string),
        );
    }
    states
}

impl AlertStationResolver for WeatherIndexAlertStationResolver {
    fn resolve_station(
        &self,
        alerts: &[WeatherAlert],
        location: Option<&Location>,
    ) -> Option<Station> {
        let same_codes: BTreeSet<String> = alerts.iter().flat_map(alert_same_codes).collect();
        if same_codes.is_empty() {
            tracing::info!(
                "Weather radio auto-tune skipped: alert carries no NWS SAME county coding"
            );
            return None;
        }
        for station in self.candidate_stations(location, &alert_states(alerts)) {
            let Some(metadata) = self.weatherindex.get_station_metadata(&station.call_sign) else {
                continue;
            };
            if metadata
                .served_counties
                .iter()
                .any(|c| same_codes.contains(&c.same_code))
            {
                tracing::info!(
                    "Matched alert SAME coverage to WeatherIndex station {}",
                    station.call_sign
                );
                return Some(station);
            }
        }
        tracing::info!(
            "Weather radio auto-tune skipped: WeatherIndex has no matching station coverage"
        );
        None
    }
}

/// Seconds on a monotonic clock (Python `time.monotonic`).
pub fn monotonic() -> f64 {
    static START: OnceLock<Instant> = OnceLock::new();
    START.get_or_init(Instant::now).elapsed().as_secs_f64()
}

/// Python `threading.Event`: `set` wakes a waiter early.
#[derive(Default)]
struct WakeEvent {
    flag: Mutex<bool>,
    cv: Condvar,
    #[cfg(test)]
    waits: Mutex<Vec<f64>>,
    #[cfg(test)]
    sets: std::sync::atomic::AtomicUsize,
}

impl WakeEvent {
    fn set(&self) {
        #[cfg(test)]
        self.sets.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        *self.flag.lock().unwrap() = true;
        self.cv.notify_all();
    }

    fn clear(&self) {
        *self.flag.lock().unwrap() = false;
    }

    fn wait(&self, seconds: f64) {
        // Tests drive time with a fake clock; only record the wait.
        #[cfg(test)]
        {
            self.waits.lock().unwrap().push(seconds);
        }
        #[cfg(not(test))]
        {
            let flag = self.flag.lock().unwrap();
            let _ = self.cv.wait_timeout_while(
                flag,
                std::time::Duration::from_secs_f64(seconds.max(0.0)),
                |set| !*set,
            );
        }
    }
}

pub type SettingsProvider = Box<dyn Fn() -> Option<AppSettings> + Send + Sync>;
pub type LocationProvider = Box<dyn Fn() -> Option<Location> + Send + Sync>;
/// Receives status-bar messages; called from a worker thread.
pub type StatusCallback = Arc<dyn Fn(String) + Send + Sync>;
pub type MonotonicClock = Arc<dyn Fn() -> f64 + Send + Sync>;

#[derive(Default)]
struct TunerState {
    generation: u64,
    worker_scheduled: bool,
    auto_station_call_sign: Option<String>,
    stop_at: Option<f64>,
}

impl TunerState {
    fn clear(&mut self) {
        self.worker_scheduled = false;
        self.auto_station_call_sign = None;
        self.stop_at = None;
    }
}

/// Plays the station covering a qualifying alert batch for the configured
/// number of minutes, then stops it (unless the user took over).
pub struct AlertRadioAutoTuner {
    settings_provider: SettingsProvider,
    location_provider: LocationProvider,
    status_callback: Option<StatusCallback>,
    session: Arc<RadioSession>,
    preferences: SharedPreferences,
    station_resolver: Arc<dyn AlertStationResolver>,
    url_provider: Arc<dyn StreamUrls>,
    spawn: Spawner,
    monotonic: MonotonicClock,
    state: Mutex<TunerState>,
    wake: WakeEvent,
}

/// Dependencies for [`AlertRadioAutoTuner::new`].
pub struct AutoTunerDeps {
    pub settings_provider: SettingsProvider,
    pub location_provider: LocationProvider,
    pub status_callback: Option<StatusCallback>,
    pub session: Arc<RadioSession>,
    pub preferences: SharedPreferences,
    pub station_resolver: Arc<dyn AlertStationResolver>,
    pub url_provider: Arc<dyn StreamUrls>,
    pub spawn: Spawner,
    pub monotonic: MonotonicClock,
}

impl AlertRadioAutoTuner {
    pub fn new(deps: AutoTunerDeps) -> Arc<Self> {
        Arc::new(Self {
            settings_provider: deps.settings_provider,
            location_provider: deps.location_provider,
            status_callback: deps.status_callback,
            session: deps.session,
            preferences: deps.preferences,
            station_resolver: deps.station_resolver,
            url_provider: deps.url_provider,
            spawn: deps.spawn,
            monotonic: deps.monotonic,
            state: Mutex::default(),
            wake: WakeEvent::default(),
        })
    }

    /// Schedule playback for an alert notification batch. Returns at once;
    /// station lookup and streaming happen on a worker thread.
    pub fn tune_for_alerts(self: &Arc<Self>, alerts: &[WeatherAlert]) {
        if alerts.is_empty() {
            return;
        }
        let eligible: Vec<WeatherAlert> = alerts
            .iter()
            .filter(|a| would_wake_same_radio(a))
            .cloned()
            .collect();
        if eligible.is_empty() {
            tracing::info!(
                "Weather radio auto-tune skipped: no alert in the batch would wake a SAME radio"
            );
            return;
        }
        let Some(settings) = (self.settings_provider)() else {
            return;
        };
        if !settings.auto_tune_weather_radio_alerts {
            return;
        }
        let duration_minutes = validated_duration_minutes(&settings);
        let now = (self.monotonic)();
        let stop_at = now + duration_minutes as f64 * 60.0;

        let mut state = self.state.lock().unwrap();
        // Duplicate batches extend the pending/active window instead of
        // starting overlapping resolution or audio.
        if state.worker_scheduled && state.stop_at.is_some_and(|at| at > now) {
            state.stop_at = Some(state.stop_at.unwrap_or(stop_at).max(stop_at));
            self.wake.set();
            tracing::info!(
                "Extended pending or active weather radio auto-tune for alert batch of {} alert(s)",
                eligible.len()
            );
            return;
        }
        if self.session.is_playing() {
            drop(state);
            self.emit_already_playing();
            return;
        }
        state.generation += 1;
        let generation = state.generation;
        state.auto_station_call_sign = None;
        state.stop_at = Some(stop_at);
        state.worker_scheduled = true;
        self.wake.clear();
        drop(state);

        let tuner = self.clone();
        (self.spawn)(Box::new(move || tuner.worker_loop(&eligible, generation)));
        tracing::info!(
            "Scheduled weather radio auto-tune resolution for {duration_minutes} minute(s)"
        );
    }

    /// Cancel pending auto-tune timing without stopping manual playback.
    pub fn stop(&self) {
        let mut state = self.state.lock().unwrap();
        state.generation += 1;
        state.clear();
        self.wake.set();
    }

    fn emit_already_playing(&self) {
        let label = self
            .session
            .playing_station()
            .map_or_else(|| "unknown station".to_string(), |s| s.call_sign);
        self.emit_status(format!(
            "Weather radio auto-tune skipped because NOAA Weather Radio is already playing {label}."
        ));
    }

    fn worker_loop(&self, alerts: &[WeatherAlert], generation: u64) {
        self.run_worker(alerts, generation);
        let mut state = self.state.lock().unwrap();
        if state.generation == generation {
            state.clear();
        }
    }

    fn run_worker(&self, alerts: &[WeatherAlert], generation: u64) {
        let location = (self.location_provider)();
        let Some(station) = self
            .station_resolver
            .resolve_station(alerts, location.as_ref())
        else {
            self.emit_status(
                "Weather radio auto-tune skipped: AccessiWeather does not have a reliable station \
                 match for this alert."
                    .into(),
            );
            return;
        };

        {
            let mut state = self.state.lock().unwrap();
            if state.generation != generation {
                return;
            }
            if self.session.is_playing() {
                drop(state);
                self.emit_already_playing();
                return;
            }
            state.auto_station_call_sign = Some(station.call_sign.clone());
        }

        if !self.play_station(&station, generation) {
            return;
        }

        loop {
            let stop_at = {
                let state = self.state.lock().unwrap();
                if state.generation != generation {
                    return;
                }
                state.stop_at
            };
            let Some(stop_at) = stop_at else { return };
            let remaining = stop_at - (self.monotonic)();
            if remaining <= 0.0 {
                break;
            }
            self.wake.wait(remaining.min(1.0));
            self.wake.clear();

            match self.session.playing_station() {
                None => {
                    tracing::info!("Weather radio auto-tune ended because playback stopped");
                    return;
                }
                Some(playing) if playing.call_sign != station.call_sign => {
                    tracing::info!(
                        "Weather radio auto-tune relinquished control to manual playback"
                    );
                    return;
                }
                Some(_) => {}
            }
        }

        if self
            .session
            .playing_station()
            .is_some_and(|p| p.call_sign == station.call_sign)
        {
            // Stop what auto-tune owns without trusting backend play state.
            self.session.stop(true);
            self.emit_status(format!(
                "Weather radio auto-tune stopped {}.",
                station.call_sign
            ));
        }
    }

    fn play_station(&self, station: &Station, generation: u64) -> bool {
        let found = self.url_provider.get_stream_urls(&station.call_sign);
        let urls = self
            .preferences
            .lock()
            .unwrap()
            .reorder_urls(&station.call_sign, &found);
        if urls.is_empty() {
            self.emit_status(format!(
                "Weather radio auto-tune skipped: no stream is available for {}.",
                station.call_sign
            ));
            return false;
        }

        {
            let state = self.state.lock().unwrap();
            if state.generation != generation {
                return false;
            }
            self.session.update(|s| {
                s.playing_station = Some(station.clone());
                s.current_urls = urls.clone();
                s.current_url_index = 0;
            });
        }

        for (index, url) in urls.iter().enumerate() {
            {
                let state = self.state.lock().unwrap();
                if state.generation != generation {
                    return false;
                }
                self.session.update(|s| s.current_url_index = index);
            }
            if self.session.player.play(url) {
                self.emit_status(format!(
                    "Weather radio auto-tune started {} for active alerts.",
                    station.call_sign
                ));
                return true;
            }
        }

        if self.state.lock().unwrap().generation == generation {
            self.session.update(|s| s.playing_station = None);
        }
        self.emit_status(format!(
            "Weather radio auto-tune could not start {}.",
            station.call_sign
        ));
        false
    }

    fn emit_status(&self, message: String) {
        tracing::info!("{message}");
        if let Some(callback) = &self.status_callback {
            callback(message);
        }
    }
}

/// `auto_tune_weather_radio_duration_minutes`, falling back to 5 outside 1–60.
fn validated_duration_minutes(settings: &AppSettings) -> i64 {
    let value = settings.auto_tune_weather_radio_duration_minutes;
    if (1..=60).contains(&value) {
        value
    } else {
        5
    }
}

#[cfg(test)]
mod tests;
