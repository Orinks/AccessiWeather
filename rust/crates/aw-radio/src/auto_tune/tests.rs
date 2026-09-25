//! Ported from `tests/test_alert_radio_auto_tune.py`.

use std::collections::VecDeque;
use std::sync::atomic::{AtomicUsize, Ordering};

use aw_providers::http::FixtureClient;
use serde_json::json;

use super::*;
use crate::player::fake::FakeBackend;
use crate::preferences::RadioPreferences;

fn alert() -> WeatherAlert {
    let mut alert = WeatherAlert::new("Tornado Warning", "Take shelter now.");
    alert.id = Some("alert-1".into());
    alert.severity = "Extreme".into();
    alert.event = Some("Tornado Warning".into());
    alert.affected_zones = vec!["TXC453".into()];
    alert.same_codes = vec!["048453".into()];
    alert.same_event_codes = vec!["TOR".into()];
    alert
}

fn forecast_zone_alert() -> WeatherAlert {
    let mut alert = alert();
    alert.affected_zones = vec!["TXZ192".into()];
    alert.same_codes.clear();
    alert
}

fn county_alert_without_same_codes() -> WeatherAlert {
    let mut alert = alert();
    alert.same_codes.clear();
    alert
}

fn air_quality_alert() -> WeatherAlert {
    let mut alert = alert();
    alert.title = "Air Quality Alert".into();
    alert.event = Some("Air Quality Alert".into());
    alert.same_event_codes = vec!["NWS".into()];
    alert
}

fn coded(event_codes: &[&str], same_codes: &[&str]) -> WeatherAlert {
    let mut alert = WeatherAlert::new("T", "body");
    alert.same_event_codes = event_codes.iter().map(|s| s.to_string()).collect();
    alert.same_codes = same_codes.iter().map(|s| s.to_string()).collect();
    alert
}

fn settings(enabled: bool, duration: i64) -> AppSettings {
    AppSettings {
        auto_tune_weather_radio_alerts: enabled,
        auto_tune_weather_radio_duration_minutes: duration,
        ..AppSettings::default()
    }
}

fn austin_location() -> Location {
    Location::new("Austin", 30.2672, -97.7431)
}

fn wxk27() -> Station {
    Station::new("WXK27", 162.4, "Austin, TX", 30.2672, -97.7431, "TX")
}

#[derive(Default)]
struct MappedResolver {
    station: Option<Station>,
    calls: Mutex<Vec<(Vec<WeatherAlert>, Option<Location>)>>,
}

impl AlertStationResolver for MappedResolver {
    fn resolve_station(
        &self,
        alerts: &[WeatherAlert],
        location: Option<&Location>,
    ) -> Option<Station> {
        self.calls
            .lock()
            .unwrap()
            .push((alerts.to_vec(), location.cloned()));
        self.station.clone()
    }
}

#[derive(Default)]
struct FakeUrls {
    urls: Mutex<Vec<String>>,
    calls: AtomicUsize,
}

impl StreamUrls for FakeUrls {
    fn get_stream_urls(&self, _: &str) -> Vec<String> {
        self.calls.fetch_add(1, Ordering::SeqCst);
        self.urls.lock().unwrap().clone()
    }
}

type Pending = Arc<Mutex<Vec<crate::Work>>>;

struct Harness {
    tuner: Arc<AlertRadioAutoTuner>,
    session: Arc<RadioSession>,
    backend: Arc<FakeBackend>,
    started: Pending,
    urls: Arc<FakeUrls>,
    resolver: Arc<MappedResolver>,
    statuses: Arc<Mutex<Vec<String>>>,
}

impl Harness {
    fn started_count(&self) -> usize {
        self.started.lock().unwrap().len()
    }

    /// Run the first scheduled worker inline.
    fn run_worker(&self) {
        let work = self.started.lock().unwrap().remove(0);
        work();
    }

    fn statuses(&self) -> Vec<String> {
        self.statuses.lock().unwrap().clone()
    }

    fn stopped_once(&self) -> bool {
        let streams = self.backend.streams.lock().unwrap();
        streams.len() == 1 && streams[0].stopped.load(Ordering::SeqCst)
    }
}

struct Options {
    settings: Option<AppSettings>,
    station: Option<Station>,
    clock: Option<Vec<f64>>,
    location: Option<Location>,
    resolver: Option<Arc<dyn AlertStationResolver>>,
}

impl Default for Options {
    fn default() -> Self {
        Self {
            settings: Some(settings(true, 5)),
            station: Some(wxk27()),
            clock: None,
            location: Some(austin_location()),
            resolver: None,
        }
    }
}

fn make_tuner(options: Options) -> Harness {
    let backend = Arc::new(FakeBackend::default());
    let session = RadioSession::new(backend.clone(), None);
    let started: Pending = Arc::default();
    let pending = started.clone();
    let urls = Arc::new(FakeUrls::default());
    *urls.urls.lock().unwrap() = vec!["https://example.test/wxk27".into()];
    let resolver = Arc::new(MappedResolver {
        station: options.station,
        ..Default::default()
    });
    let statuses = Arc::new(Mutex::new(Vec::new()));
    let sink = statuses.clone();
    let monotonic: MonotonicClock = match options.clock {
        Some(times) => {
            let times = Mutex::new(VecDeque::from(times));
            Arc::new(move || times.lock().unwrap().pop_front().expect("clock exhausted"))
        }
        None => Arc::new(monotonic),
    };
    let settings = options.settings;
    let location = options.location;
    let tuner = AlertRadioAutoTuner::new(AutoTunerDeps {
        settings_provider: Box::new(move || settings.clone()),
        location_provider: Box::new(move || location.clone()),
        status_callback: Some(Arc::new(move |m| sink.lock().unwrap().push(m))),
        session: session.clone(),
        preferences: RadioPreferences::new(None).shared(),
        station_resolver: options.resolver.unwrap_or_else(|| resolver.clone()),
        url_provider: urls.clone(),
        spawn: Arc::new(move |work| pending.lock().unwrap().push(work)),
        monotonic,
    });
    Harness {
        tuner,
        session,
        backend,
        started,
        urls,
        resolver,
        statuses,
    }
}

const NO_MATCH: &str = "Weather radio auto-tune skipped: AccessiWeather does not have a reliable \
                        station match for this alert.";

#[test]
fn disabled_does_not_schedule_worker() {
    let h = make_tuner(Options {
        settings: Some(settings(false, 5)),
        ..Default::default()
    });
    h.tuner.tune_for_alerts(&[alert()]);
    assert_eq!(h.started_count(), 0);
}

#[test]
fn without_reliable_station_match_does_not_play() {
    let h = make_tuner(Options {
        station: None,
        ..Default::default()
    });
    h.tuner.tune_for_alerts(&[alert()]);
    assert_eq!(h.started_count(), 1);
    h.run_worker();
    assert_eq!(h.urls.calls.load(Ordering::SeqCst), 0);
    assert_eq!(h.statuses(), [NO_MATCH]);
}

#[test]
fn skips_non_nwr_same_event_without_worker() {
    let h = make_tuner(Options::default());
    h.tuner.tune_for_alerts(&[air_quality_alert()]);
    assert_eq!(h.started_count(), 0);
    assert!(h.resolver.calls.lock().unwrap().is_empty());
}

#[test]
fn filters_mixed_batch_to_nwr_same_events_only() {
    let h = make_tuner(Options::default());
    h.tuner.tune_for_alerts(&[air_quality_alert(), alert()]);
    assert_eq!(h.started_count(), 1);
    h.urls.urls.lock().unwrap().clear();
    h.run_worker();
    let calls = h.resolver.calls.lock().unwrap();
    let events: Vec<_> = calls[0]
        .0
        .iter()
        .map(|a| a.event.clone().unwrap())
        .collect();
    assert_eq!(events, ["Tornado Warning"]);
    assert_eq!(
        h.statuses(),
        ["Weather radio auto-tune skipped: no stream is available for WXK27."]
    );
}

#[test]
fn same_event_codes_drop_the_generic_nws_placeholder() {
    let codes = |c: &[&str]| same_event_codes(&coded(c, &[]));
    assert_eq!(codes(&["TOR"]), BTreeSet::from(["TOR".to_string()]));
    assert_eq!(codes(&["smw"]), BTreeSet::from(["SMW".to_string()]));
    assert!(codes(&["NWS"]).is_empty());
    assert!(codes(&[]).is_empty());
}

#[test]
fn only_event_codes_decide_whether_a_radio_wakes() {
    // Special Marine Warnings come with and without a SAME header.
    assert!(would_wake_same_radio(&coded(&["SMW"], &["048453"])));
    assert!(!would_wake_same_radio(&coded(&["NWS"], &["048453"])));
    // Fire Warning / FRW tunes though no curated list names it.
    assert!(would_wake_same_radio(&coded(&["FRW"], &["048453"])));
    // County codes are required too.
    assert!(!would_wake_same_radio(&coded(&["TOR"], &[])));
    assert!(would_wake_same_radio(&alert()));
    assert!(!would_wake_same_radio(&county_alert_without_same_codes()));
    assert!(!would_wake_same_radio(&air_quality_alert()));
}

fn metadata(call_sign: &str, codes: &[&str]) -> serde_json::Value {
    let counties: Vec<_> = codes
        .iter()
        .enumerate()
        .map(|(i, c)| json!({"county": format!("County {i}"), "same_code": c, "state": "TX", "area": "All"}))
        .collect();
    json!({"callsign": call_sign, "wfo": "Austin/San Antonio TX", "latitude": 30.3219,
           "longitude": -97.8033, "served_counties": counties})
}

fn weatherindex_resolver(
    stations: Vec<Station>,
    metadata_by_call_sign: &[(&str, serde_json::Value)],
) -> (WeatherIndexAlertStationResolver, Arc<FixtureClient>) {
    let mut fixture = FixtureClient::new();
    for (call_sign, body) in metadata_by_call_sign {
        fixture = fixture.with(
            &format!("https://api.wxindex.org/v1/stations/{call_sign}"),
            body.clone(),
        );
    }
    let http = Arc::new(fixture);
    let resolver = WeatherIndexAlertStationResolver::new(
        Arc::new(StationDatabase::with_stations(stations)),
        Arc::new(WeatherIndexClient::new(http.clone())),
    );
    (resolver, http)
}

fn requested(http: &FixtureClient) -> Vec<String> {
    http.request_log()
        .iter()
        .map(|u| u.rsplit('/').next().unwrap().to_string())
        .collect()
}

#[test]
fn real_nws_flood_warning_shape_still_auto_tunes() {
    // Burlington County NJ flood warning: SAME event FLS, counties 034005...
    let alert = coded(&["FLS"], &["034005", "034007", "034015"]);
    assert!(would_wake_same_radio(&alert));
    let station = Station::new("KHB37", 162.475, "Philadelphia, PA", 40.04, -75.07, "PA");
    let (resolver, _) = weatherindex_resolver(
        vec![station.clone()],
        &[("KHB37", metadata("KHB37", &["034005"]))],
    );
    assert_eq!(resolver.resolve_station(&[alert], None), Some(station));
}

#[test]
fn skips_county_alert_without_same_codes_and_never_carries_them() {
    let h = make_tuner(Options::default());
    h.tuner
        .tune_for_alerts(&[county_alert_without_same_codes()]);
    assert_eq!(h.started_count(), 0);

    h.tuner
        .tune_for_alerts(&[county_alert_without_same_codes(), alert()]);
    assert_eq!(h.started_count(), 1);
    h.urls.urls.lock().unwrap().clear();
    h.run_worker();
    let calls = h.resolver.calls.lock().unwrap();
    let codes: Vec<_> = calls[0].0.iter().map(|a| a.same_codes.clone()).collect();
    assert_eq!(codes, [vec!["048453".to_string()]]);
}

#[test]
fn window_is_not_extended_by_a_same_less_alert() {
    let h = make_tuner(Options {
        clock: Some(vec![100.0, 150.0]),
        ..Default::default()
    });
    h.tuner.tune_for_alerts(&[alert()]);
    assert_eq!(h.tuner.state.lock().unwrap().stop_at, Some(400.0));
    h.tuner
        .tune_for_alerts(&[county_alert_without_same_codes()]);
    assert_eq!(h.started_count(), 1);
    assert_eq!(h.tuner.state.lock().unwrap().stop_at, Some(400.0));
}

#[test]
fn no_reliable_resolver_never_selects_a_station() {
    assert_eq!(
        NoReliableAlertStationResolver.resolve_station(&[alert()], Some(&austin_location())),
        None
    );
}

#[test]
fn empty_batch_and_missing_settings_do_nothing() {
    let h = make_tuner(Options::default());
    h.tuner.tune_for_alerts(&[]);
    assert_eq!(h.started_count(), 0);

    let h = make_tuner(Options {
        settings: None,
        ..Default::default()
    });
    h.tuner.tune_for_alerts(&[alert()]);
    assert_eq!(h.started_count(), 0);
    assert!(h.resolver.calls.lock().unwrap().is_empty());
}

#[test]
fn default_resolver_never_starts_work_for_an_alert_without_same_coding() {
    let h = make_tuner(Options {
        resolver: Some(Arc::new(NoReliableAlertStationResolver)),
        ..Default::default()
    });
    h.tuner.tune_for_alerts(&[forecast_zone_alert()]);
    assert_eq!(h.started_count(), 0);
    assert_eq!(h.urls.calls.load(Ordering::SeqCst), 0);
}

#[test]
fn missing_location_still_resolves_without_one() {
    let h = make_tuner(Options {
        location: None,
        ..Default::default()
    });
    h.urls.urls.lock().unwrap().clear();
    h.tuner.tune_for_alerts(&[alert()]);
    h.run_worker();
    assert_eq!(h.resolver.calls.lock().unwrap()[0].1, None);
}

#[test]
fn weatherindex_resolver_matches_alert_same_code_to_station_coverage() {
    let (resolver, http) =
        weatherindex_resolver(vec![wxk27()], &[("WXK27", metadata("WXK27", &["048453"]))]);
    let mut alert = alert();
    alert.affected_zones.clear();
    assert_eq!(
        resolver.resolve_station(&[alert], Some(&austin_location())),
        Some(wxk27())
    );
    assert_eq!(requested(&http), ["WXK27"]);
}

#[test]
fn weatherindex_resolver_needs_published_same_codes() {
    for alert in [county_alert_without_same_codes(), forecast_zone_alert()] {
        let (resolver, http) =
            weatherindex_resolver(vec![wxk27()], &[("WXK27", metadata("WXK27", &["048453"]))]);
        assert_eq!(
            resolver.resolve_station(&[alert], Some(&austin_location())),
            None
        );
        assert!(requested(&http).is_empty());
    }
}

#[test]
fn weatherindex_resolver_skips_station_without_coverage() {
    let (resolver, http) =
        weatherindex_resolver(vec![wxk27()], &[("WXK27", metadata("WXK27", &[]))]);
    assert_eq!(
        resolver.resolve_station(&[alert()], Some(&austin_location())),
        None
    );
    assert_eq!(requested(&http), ["WXK27"]);
}

#[test]
fn weatherindex_resolver_tie_breakers() {
    let far = Station::new("AAAAA", 162.4, "Far, TX", 35.0, -101.0, "TX");
    let near = Station::new("ZZZZZ", 162.4, "Near, TX", 30.3, -97.8, "TX");
    let both = [
        ("AAAAA", metadata("AAAAA", &["048453"])),
        ("ZZZZZ", metadata("ZZZZZ", &["048453"])),
    ];
    // Nearest first with a location.
    let (resolver, http) = weatherindex_resolver(vec![far.clone(), near.clone()], &both);
    assert_eq!(
        resolver.resolve_station(&[alert()], Some(&austin_location())),
        Some(near.clone())
    );
    assert_eq!(requested(&http), ["ZZZZZ"]);
    // Call sign order without one.
    let (resolver, http) = weatherindex_resolver(vec![near.clone(), far.clone()], &both);
    assert_eq!(resolver.resolve_station(&[alert()], None), Some(far));
    assert_eq!(requested(&http), ["AAAAA"]);
    // ...but stations in the alert's SAME state come first.
    let kansas = Station::new("AAAAA", 162.4, "Kansas, KS", 39.0, -96.0, "KS");
    let (resolver, http) = weatherindex_resolver(vec![kansas, near.clone()], &both);
    let mut alert = alert();
    alert.affected_zones.clear();
    assert_eq!(resolver.resolve_station(&[alert], None), Some(near));
    assert_eq!(requested(&http), ["ZZZZZ"]);
}

#[test]
fn weatherindex_resolver_ignores_malformed_same_codes_and_unknown_states() {
    let (resolver, http) =
        weatherindex_resolver(vec![wxk27()], &[("WXK27", metadata("WXK27", &["048453"]))]);
    let mut alert = alert();
    alert.affected_zones = vec!["XXC001".into()];
    alert.same_codes = vec!["abc".into()];
    assert_eq!(resolver.resolve_station(&[alert], None), None);
    assert!(requested(&http).is_empty());
}

#[test]
fn schedules_worker_that_resolves_with_alerts_and_location() {
    let h = make_tuner(Options::default());
    h.tuner.tune_for_alerts(&[alert()]);
    assert_eq!(h.started_count(), 1);
    assert!(h.resolver.calls.lock().unwrap().is_empty());
    h.urls.urls.lock().unwrap().clear();
    h.run_worker();
    let calls = h.resolver.calls.lock().unwrap();
    assert_eq!(calls[0].0[0].event.as_deref(), Some("Tornado Warning"));
    assert_eq!(calls[0].1.as_ref().unwrap().name, "Austin");
}

#[test]
fn invalid_duration_defaults_to_five_minutes_and_stops_playback() {
    let h = make_tuner(Options {
        settings: Some(settings(true, 0)),
        clock: Some(vec![100.0, 401.0]),
        ..Default::default()
    });
    h.tuner.tune_for_alerts(&[alert()]);
    h.run_worker();
    assert!(h.stopped_once());
    assert!(!h.session.is_playing());
    assert_eq!(
        h.statuses(),
        [
            "Weather radio auto-tune started WXK27 for active alerts.",
            "Weather radio auto-tune stopped WXK27."
        ]
    );
    let state = h.tuner.state.lock().unwrap();
    assert!(!state.worker_scheduled && state.stop_at.is_none());
}

#[test]
fn uses_configured_duration_for_stop_deadline() {
    let h = make_tuner(Options {
        settings: Some(settings(true, 8)),
        clock: Some(vec![100.0, 579.0, 580.0]),
        ..Default::default()
    });
    h.tuner.tune_for_alerts(&[alert()]);
    h.run_worker();
    assert_eq!(*h.tuner.wake.waits.lock().unwrap(), [1.0]);
    assert!(h.stopped_once());
}

#[test]
fn timer_stops_even_when_backend_play_state_is_stale() {
    let h = make_tuner(Options {
        clock: Some(vec![100.0, 101.0, 401.0]),
        ..Default::default()
    });
    h.backend.stale.store(true, Ordering::SeqCst);
    h.tuner.tune_for_alerts(&[alert()]);
    h.run_worker();
    assert_eq!(*h.tuner.wake.waits.lock().unwrap(), [1.0]);
    assert!(h.stopped_once());
    assert_eq!(h.session.playing_station(), None);
}

#[test]
fn stop_cancels_pending_auto_tune_before_stream_starts() {
    let h = make_tuner(Options::default());
    h.tuner.tune_for_alerts(&[alert()]);
    h.tuner.stop();
    h.run_worker();
    assert_eq!(h.urls.calls.load(Ordering::SeqCst), 0);
    assert_eq!(h.session.playing_station(), None);
}

fn start_manual(session: &RadioSession, station: Station) {
    session.update(|s| s.playing_station = Some(station));
    assert!(session.player.play("https://manual"));
}

#[test]
fn manual_playback_starting_during_resolution_prevents_auto_tune() {
    let manual = Station::new("KHB40", 162.55, "Manual, TX", 30.0, -97.0, "TX");
    let h = make_tuner(Options::default());
    h.tuner.tune_for_alerts(&[alert()]);
    start_manual(&h.session, manual.clone());
    h.run_worker();
    assert_eq!(h.urls.calls.load(Ordering::SeqCst), 0);
    assert_eq!(h.session.playing_station(), Some(manual));
    assert_eq!(
        h.statuses(),
        ["Weather radio auto-tune skipped because NOAA Weather Radio is already playing KHB40."]
    );
}

#[test]
fn clears_station_when_all_stream_urls_fail() {
    let backend = FakeBackend::with_results(&[false, false]);
    let h = make_tuner(Options::default());
    // Swap in a failing backend by building the tuner around a new session.
    let session = RadioSession::new(backend.clone(), None);
    let statuses = h.statuses.clone();
    let urls = h.urls.clone();
    *urls.urls.lock().unwrap() = vec![
        "https://example.test/primary".into(),
        "https://example.test/backup".into(),
    ];
    let pending: Pending = Arc::default();
    let queue = pending.clone();
    let tuner = AlertRadioAutoTuner::new(AutoTunerDeps {
        settings_provider: Box::new(|| Some(settings(true, 5))),
        location_provider: Box::new(|| None),
        status_callback: Some(Arc::new(move |m| statuses.lock().unwrap().push(m))),
        session: session.clone(),
        preferences: RadioPreferences::new(None).shared(),
        station_resolver: h.resolver.clone(),
        url_provider: urls,
        spawn: Arc::new(move |work| queue.lock().unwrap().push(work)),
        monotonic: Arc::new(monotonic),
    });
    tuner.tune_for_alerts(&[alert()]);
    let work = pending.lock().unwrap().remove(0);
    work();
    assert_eq!(
        backend.opened(),
        [
            "https://example.test/primary",
            "https://example.test/backup"
        ]
    );
    assert_eq!(session.playing_station(), None);
    assert_eq!(
        h.statuses(),
        ["Weather radio auto-tune could not start WXK27."]
    );
}

#[test]
fn duplicate_batches_extend_the_window_without_overlap() {
    let h = make_tuner(Options::default());
    h.tuner.tune_for_alerts(&[alert()]);
    h.tuner.tune_for_alerts(&[alert()]);
    assert_eq!(h.started_count(), 1);

    let h = make_tuner(Options {
        clock: Some(vec![100.0, 150.0, 399.0, 450.0]),
        ..Default::default()
    });
    h.tuner.tune_for_alerts(&[alert()]);
    h.tuner.tune_for_alerts(&[alert()]);
    h.run_worker();
    assert_eq!(h.started_count(), 0);
    assert_eq!(h.tuner.wake.sets.load(Ordering::SeqCst), 1);
    assert_eq!(*h.tuner.wake.waits.lock().unwrap(), [1.0]);
    assert!(h.stopped_once());
}

#[test]
fn manual_playback_is_respected_and_not_interrupted() {
    let h = make_tuner(Options::default());
    start_manual(&h.session, wxk27());
    h.tuner.tune_for_alerts(&[alert()]);
    assert_eq!(h.started_count(), 0);
    assert!(h.session.is_playing());
    assert_eq!(
        h.statuses(),
        ["Weather radio auto-tune skipped because NOAA Weather Radio is already playing WXK27."]
    );
}

#[test]
fn notification_reasons_that_tune() {
    let mut a = alert();
    assert!(should_auto_tune_for_alert_notification(&a, "new_alert"));
    a.message_type = Some(" Alert ".into());
    assert!(should_auto_tune_for_alert_notification(&a, "new_alert"));
    a.message_type = Some("Update".into());
    assert!(!should_auto_tune_for_alert_notification(&a, "new_alert"));
    assert!(should_auto_tune_for_alert_notification(
        &a,
        "severity_escalated"
    ));
    assert!(!should_auto_tune_for_alert_notification(&a, "reminder"));
}

fn golden_alert(spec: &serde_json::Value) -> WeatherAlert {
    let list = |key: &str| -> Vec<String> {
        spec.get(key)
            .map(|v| serde_json::from_value(v.clone()).unwrap())
            .unwrap_or_default()
    };
    let mut alert = WeatherAlert::new(
        spec.get("title")
            .and_then(|v| v.as_str())
            .unwrap_or("Alert"),
        "body",
    );
    alert.event = spec
        .get("event")
        .and_then(|v| v.as_str())
        .map(str::to_string);
    alert.message_type = spec
        .get("message_type")
        .and_then(|v| v.as_str())
        .map(str::to_string);
    alert.affected_zones = list("affected_zones");
    alert.same_codes = list("same_codes");
    alert.same_event_codes = list("same_event_codes");
    alert
}

fn sorted_strings(set: BTreeSet<String>) -> serde_json::Value {
    json!(set.into_iter().collect::<Vec<_>>())
}

#[test]
fn golden_same_logic_and_resolution() {
    let golden = crate::golden("same.json");
    for (input, expected) in golden["normalize"].as_object().unwrap() {
        assert_eq!(
            normalize_same_code(input).as_deref(),
            expected.as_str(),
            "{input:?}"
        );
    }
    let alerts: Vec<(String, WeatherAlert)> = golden["alerts"]
        .as_array()
        .unwrap()
        .iter()
        .map(|a| (a["name"].as_str().unwrap().to_string(), golden_alert(a)))
        .collect();
    for (spec, (_, alert)) in golden["alerts"].as_array().unwrap().iter().zip(&alerts) {
        assert_eq!(
            sorted_strings(alert_same_codes(alert)),
            spec["same_codes_normalized"],
            "{spec}"
        );
        assert_eq!(
            sorted_strings(same_event_codes(alert)),
            spec["event_codes"],
            "{spec}"
        );
        assert_eq!(
            json!(would_wake_same_radio(alert)),
            spec["would_wake"],
            "{spec}"
        );
        assert_eq!(
            sorted_strings(alert_states(std::slice::from_ref(alert))),
            spec["states"],
            "{spec}"
        );
    }
    for row in golden["notification_reasons"].as_array().unwrap() {
        let mut alert = WeatherAlert::new("Alert", "body");
        alert.message_type = row[0].as_str().map(str::to_string);
        assert_eq!(
            should_auto_tune_for_alert_notification(&alert, row[1].as_str().unwrap()),
            row[2].as_bool().unwrap(),
            "{row}"
        );
    }
    for case in golden["resolver"].as_array().unwrap() {
        let coverage: Vec<(String, serde_json::Value)> = case["coverage"]
            .as_object()
            .unwrap()
            .iter()
            .map(|(cs, codes)| {
                let codes: Vec<String> = serde_json::from_value(codes.clone()).unwrap();
                let codes: Vec<&str> = codes.iter().map(String::as_str).collect();
                (cs.clone(), metadata(cs, &codes))
            })
            .collect();
        let refs: Vec<(&str, serde_json::Value)> = coverage
            .iter()
            .map(|(cs, v)| (cs.as_str(), v.clone()))
            .collect();
        let (resolver, http) =
            weatherindex_resolver(StationDatabase::new().get_all_stations(), &refs);
        let batch: Vec<WeatherAlert> = case["alerts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|n| {
                alerts
                    .iter()
                    .find(|(name, _)| name == n.as_str().unwrap())
                    .unwrap()
                    .1
                    .clone()
            })
            .collect();
        let location = case["location"]
            .as_array()
            .map(|l| Location::new("Here", l[0].as_f64().unwrap(), l[1].as_f64().unwrap()));
        let station = resolver.resolve_station(&batch, location.as_ref());
        assert_eq!(
            station.map(|s| s.call_sign).as_deref(),
            case["station"].as_str(),
            "{}",
            case["name"]
        );
        let calls: Vec<String> = serde_json::from_value(case["calls"].clone()).unwrap();
        assert_eq!(requested(&http), calls, "{}", case["name"]);
    }
}

#[test]
fn golden_auto_tune_scenarios() {
    let same = crate::golden("same.json");
    let alert_by_name = |name: &str| {
        golden_alert(
            same["alerts"]
                .as_array()
                .unwrap()
                .iter()
                .find(|a| a["name"] == name)
                .unwrap(),
        )
    };
    let db = StationDatabase::new();
    let station_by = |cs: Option<&str>| {
        cs.map(|cs| {
            db.get_stations_by_call_signs(&[cs])
                .into_iter()
                .next()
                .unwrap_or_else(|| {
                    Station::new(cs, 162.4, &format!("{cs} City, TX"), 30.0, -97.0, "TX")
                })
        })
    };
    for case in crate::golden("auto_tune.json").as_array().unwrap() {
        let name = case["name"].as_str().unwrap();
        let before = case["playing_before"].as_str();
        let unknown = case["playing_unknown"].as_bool().unwrap();
        let manual = case["manual_during_resolution"].as_str();
        let mut results: Vec<bool> = case["play_results"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_bool().unwrap())
            .collect();
        if before.is_some() || unknown || manual.is_some() {
            results.insert(0, true);
        }
        let backend = FakeBackend::with_results(&results);
        let prefs = RadioPreferences::new(None).shared();
        for (cs, url) in case["preferred"].as_object().unwrap() {
            prefs
                .lock()
                .unwrap()
                .set_preferred_url(cs, url.as_str().unwrap());
        }
        let session = RadioSession::new(backend.clone(), Some(prefs.clone()));
        if before.is_some() || unknown {
            session.update(|s| s.playing_station = station_by(before));
            session.player.play("manual");
        }
        let urls = Arc::new(FakeUrls::default());
        *urls.urls.lock().unwrap() = serde_json::from_value(case["urls"].clone()).unwrap();
        let clock: Vec<f64> = serde_json::from_value(case["clock"].clone()).unwrap();
        let clock = Mutex::new(VecDeque::from(clock));
        let statuses = Arc::new(Mutex::new(Vec::<String>::new()));
        let sink = statuses.clone();
        let pending: Pending = Arc::default();
        let queue = pending.clone();
        let (enabled, duration) = (
            case["enabled"].as_bool().unwrap(),
            case["duration"].as_i64().unwrap(),
        );
        let resolved = station_by(case["resolved"].as_str());
        let tuner = AlertRadioAutoTuner::new(AutoTunerDeps {
            settings_provider: Box::new(move || Some(settings(enabled, duration))),
            location_provider: Box::new(|| None),
            status_callback: Some(Arc::new(move |m| sink.lock().unwrap().push(m))),
            session: session.clone(),
            preferences: prefs.clone(),
            station_resolver: Arc::new(MappedResolver {
                station: resolved,
                ..Default::default()
            }),
            url_provider: urls.clone(),
            spawn: Arc::new(move |work| queue.lock().unwrap().push(work)),
            monotonic: Arc::new(move || clock.lock().unwrap().pop_front().unwrap_or(0.0)),
        });
        for batch in case["batches"].as_array().unwrap() {
            let alerts: Vec<WeatherAlert> = batch
                .as_array()
                .unwrap()
                .iter()
                .map(|n| alert_by_name(n.as_str().unwrap()))
                .collect();
            tuner.tune_for_alerts(&alerts);
        }
        if manual.is_some() {
            session.update(|s| s.playing_station = station_by(manual));
            session.player.play("manual");
        }
        if case["cancel_before_run"].as_bool().unwrap() {
            tuner.stop();
        }
        let workers: Vec<crate::Work> = std::mem::take(&mut *pending.lock().unwrap());
        let worker_count = workers.len();
        for work in workers {
            work();
        }

        let opened = backend.opened();
        let played: Vec<String> = opened.iter().filter(|u| *u != "manual").cloned().collect();
        // Python counts session.stop() calls; here, streams that were stopped.
        let auto_stops = backend
            .streams
            .lock()
            .unwrap()
            .iter()
            .filter(|s| s.stopped.load(Ordering::SeqCst))
            .count();
        assert_eq!(
            worker_count as u64,
            case["workers"].as_u64().unwrap(),
            "{name}"
        );
        assert_eq!(
            *statuses.lock().unwrap(),
            serde_json::from_value::<Vec<String>>(case["statuses"].clone()).unwrap(),
            "{name}"
        );
        assert_eq!(
            played,
            serde_json::from_value::<Vec<String>>(case["played"].clone()).unwrap(),
            "{name}"
        );
        let waits: Vec<f64> = serde_json::from_value(case["waits"].clone()).unwrap();
        assert_eq!(*tuner.wake.waits.lock().unwrap(), waits, "{name}");
        assert_eq!(
            tuner.wake.sets.load(Ordering::SeqCst) as u64,
            case["wake_sets"].as_u64().unwrap(),
            "{name}"
        );
        assert_eq!(auto_stops as u64, case["stops"].as_u64().unwrap(), "{name}");
        assert_eq!(
            urls.calls.load(Ordering::SeqCst) as u64,
            case["url_lookups"].as_u64().unwrap(),
            "{name}"
        );
        assert_eq!(
            session.playing_station().map(|s| s.call_sign).as_deref(),
            case["final_station"].as_str(),
            "{name}"
        );
        assert_eq!(
            prefs.lock().unwrap().get_last_station().as_deref(),
            case["last_station"].as_str(),
            "{name}"
        );
    }
}
