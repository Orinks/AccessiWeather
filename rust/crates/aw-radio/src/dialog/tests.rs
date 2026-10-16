//! Ported from `tests/test_noaa_radio_dialog.py` and
//! `tests/test_noaa_radio_dialog_integration.py`, driving the real session
//! with a fake audio backend.

use std::sync::atomic::Ordering;
use std::time::Instant;

use aw_providers::http::FixtureClient;
use serde_json::json;

use super::*;
use crate::availability::AVAILABILITY_FILE_NAME;
use crate::player::fake::FakeBackend;
use crate::RadioContext;

fn aaa11() -> Station {
    Station::new("AAA11", 162.55, "New York", 40.75, -73.98, "NY")
}

fn bbb22() -> Station {
    Station::new("BBB22", 162.4, "Philadelphia, PA", 39.95, -75.17, "PA")
}

fn ccc33() -> Station {
    Station::new("CCC33", 162.475, "Austin", 30.2672, -97.7431, "TX")
}

struct Env {
    ctx: RadioContext,
    backend: Arc<FakeBackend>,
    dir: tempfile::TempDir,
    events: Arc<Mutex<Vec<DialogEvent>>>,
    /// Every distinct status the last opened dialog showed, in order.
    statuses: Arc<Mutex<Vec<String>>>,
}

fn feed(urls: &[&str]) -> serde_json::Value {
    json!({"feeds": urls.iter().map(|u| json!({"stream_url": u})).collect::<Vec<_>>()})
}

/// AAA11 has two streams, BBB22 one, CCC33 one; play results are queued.
fn env(results: &[bool]) -> Env {
    let http = FixtureClient::new()
        .with(
            "https://api.wxindex.org/v1/stations/AAA11",
            feed(&["http://a1", "http://a2"]),
        )
        .with(
            "https://api.wxindex.org/v1/stations/BBB22",
            feed(&["http://b1"]),
        )
        .with(
            "https://api.wxindex.org/v1/stations/CCC33",
            feed(&["http://c1"]),
        );
    let dir = tempfile::tempdir().unwrap();
    let backend = FakeBackend::with_results(results);
    let mut ctx = RadioContext::new(dir.path(), Arc::new(http), backend.clone());
    ctx.stations = Arc::new(StationDatabase::with_stations(vec![
        aaa11(),
        bbb22(),
        ccc33(),
    ]));
    Env {
        ctx,
        backend,
        dir,
        events: Arc::default(),
        statuses: Arc::default(),
    }
}

impl Env {
    fn open(
        &self,
        lat: Option<f64>,
        lon: Option<f64>,
        locations: Vec<Location>,
    ) -> Arc<RadioDialog> {
        let (sink, statuses) = (self.events.clone(), self.statuses.clone());
        let this: Arc<OnceLock<Weak<RadioDialog>>> = Arc::default();
        let handle = this.clone();
        let dialog = self.ctx.open_dialog(
            lat,
            lon,
            locations,
            Arc::new(move |e| {
                sink.lock().unwrap().push(e);
                if let Some(dialog) = handle.get().and_then(Weak::upgrade) {
                    let status = dialog.view().status;
                    let mut seen = statuses.lock().unwrap();
                    if seen.last() != Some(&status) {
                        seen.push(status);
                    }
                }
            }),
        );
        let _ = this.set(Arc::downgrade(&dialog));
        wait_for(&dialog, |v| v.status != "Finding stations...");
        self.statuses.lock().unwrap().clear();
        dialog
    }

    fn statuses(&self) -> Vec<String> {
        self.statuses.lock().unwrap().clone()
    }

    fn messages(&self) -> Vec<DialogEvent> {
        self.events
            .lock()
            .unwrap()
            .iter()
            .filter(|e| **e != DialogEvent::Changed)
            .cloned()
            .collect()
    }
}

/// Generous: only a failing test waits this long, and loaded CI runners are slow.
const TIMEOUT: Duration = Duration::from_secs(60);

/// Poll the view until `done`, then let the job that got there finish, so
/// the returned view and the recorded statuses include all of its updates.
fn wait_for(dialog: &RadioDialog, done: impl Fn(&DialogView) -> bool) -> DialogView {
    let deadline = Instant::now() + TIMEOUT;
    loop {
        settle(dialog);
        let view = dialog.view();
        if done(&view) {
            // `view` may have been read halfway through a worker job (status
            // set, labels and events still to come).
            settle(dialog);
            return dialog.view();
        }
        assert!(Instant::now() < deadline, "timed out; last view: {view:#?}");
        std::thread::sleep(Duration::from_millis(5));
    }
}

/// Wait until every job queued so far has run.
fn settle(dialog: &RadioDialog) {
    let (tx, rx) = mpsc::channel();
    dialog.enqueue(Box::new(move |_| {
        let _ = tx.send(());
    }));
    rx.recv_timeout(TIMEOUT)
        .expect("dialog worker did not drain its queue");
}

fn status_is(expected: &str) -> impl Fn(&DialogView) -> bool + '_ {
    move |v| v.status == expected
}

#[test]
fn opens_in_search_mode_and_lists_stations_with_feeds() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    let view = dialog.view();
    assert_eq!(view.finder_mode, 0);
    assert_eq!(
        view.search_label,
        "Search text (call sign, city, or state):"
    );
    assert_eq!(view.search_hint, "Call sign, city, or state");
    assert!(view.search_visible && !view.state_visible && !view.saved_location_visible);
    assert_eq!(
        view.state_choices,
        [
            "All states and territories",
            "New York (NY)",
            "Pennsylvania (PA)",
            "Texas (TX)"
        ]
    );
    assert_eq!(
        view.station_choices,
        [
            "AAA11 - New York, NY - 162.550 MHz - Available",
            "BBB22 - Philadelphia, PA - 162.400 MHz - Available",
            "CCC33 - Austin, TX - 162.475 MHz - Available",
        ]
    );
    assert_eq!(view.station_selection, Some(0));
    assert_eq!(view.status, "Ready");
    assert_eq!(view.station_limit_selection, 0);
    assert_eq!(
        (view.play_label.as_str(), view.play_enabled),
        ("Play", true)
    );
    assert!(!view.next_stream_enabled && !view.prefer_enabled);
    assert_eq!(
        (view.favorite_label.as_str(), view.favorite_enabled),
        ("Favorite", true)
    );
    assert_eq!(view.volume, 100);
}

#[test]
fn opening_for_a_point_uses_nearest_mode() {
    let env = env(&[]);
    let dialog = env.open(Some(30.2672), Some(-97.7431), vec![]);
    let view = dialog.view();
    assert_eq!(view.finder_mode, FinderMode::Nearest.index());
    assert_eq!(view.search_text, "30.2672, -97.7431");
    assert_eq!(view.search_label, "Coordinates (latitude, longitude):");
    assert_eq!(view.search_hint, "Example: 30.2672, -97.7431");
    assert!(view.station_choices[0].starts_with("CCC33"));
}

#[test]
fn play_stop_cycle_updates_every_control_and_remembers_the_station() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    dialog.play_stop();
    let view = wait_for(&dialog, status_is("Playing: AAA11 (stream 1 of 2)"));
    assert_eq!(
        env.statuses(),
        [
            "Connecting to AAA11 (stream 1 of 2)...",
            "Playing: AAA11 (stream 1 of 2)"
        ]
    );
    assert_eq!(env.backend.opened(), ["http://a1"]);
    assert_eq!(
        (view.play_label.as_str(), view.play_enabled),
        ("Stop", true)
    );
    assert!(view.next_stream_enabled && view.prefer_enabled);
    assert_eq!(
        env.ctx
            .preferences
            .lock()
            .unwrap()
            .get_last_station()
            .as_deref(),
        Some("AAA11")
    );
    assert_eq!(env.ctx.session.playing_station(), Some(aaa11()));

    dialog.play_stop();
    let view = wait_for(&dialog, status_is("Stopped"));
    assert_eq!(view.play_label, "Play");
    assert!(!view.next_stream_enabled && !view.prefer_enabled);
    assert!(!env.ctx.session.is_playing());
}

#[test]
fn selecting_another_station_switches_without_a_second_press() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    dialog.play_stop();
    wait_for(&dialog, status_is("Playing: AAA11 (stream 1 of 2)"));
    dialog.select_station(Some(1));
    assert_eq!(dialog.view().play_label, "Switch");
    dialog.select_station(Some(0));
    assert_eq!(dialog.view().play_label, "Stop");
    dialog.select_station(Some(1));
    dialog.play_stop();
    let view = wait_for(&dialog, status_is("Playing: BBB22"));
    assert_eq!(view.play_label, "Stop");
    assert!(!view.next_stream_enabled);
    assert_eq!(env.backend.opened(), ["http://a1", "http://b1"]);
    assert!(env.messages().is_empty());
}

#[test]
fn failed_streams_advance_then_suppress_the_station() {
    let env = env(&[false, false]);
    let dialog = env.open(None, None, vec![]);
    dialog.play_stop();
    let view = wait_for(&dialog, status_is("All streams failed for AAA11"));
    assert_eq!(
        env.statuses(),
        [
            "Connecting to AAA11 (stream 1 of 2)...",
            "Error: Failed to start stream: refused",
            "Connecting to AAA11 (stream 2 of 2)...",
            "Error: Failed to start stream: refused",
            "All streams failed for AAA11"
        ]
    );
    assert_eq!(env.backend.opened(), ["http://a1", "http://a2"]);
    assert_eq!(view.play_label, "Play");
    let mut cache = StationAvailabilityCache::new(env.dir.path().join(AVAILABILITY_FILE_NAME));
    let record = cache.get_record("AAA11").unwrap();
    assert_eq!(record.reason, "all_streams_failed");

    // Suppressed stations are hidden unless asked for.
    dialog.find();
    let view = wait_for(&dialog, |v| v.status == "Ready");
    assert!(view.station_choices[0].starts_with("BBB22"));
    dialog.set_show_unavailable(true);
    let view = wait_for(&dialog, |v| {
        v.status == "Ready" && v.station_choices.len() == 3
    });
    assert_eq!(
        view.station_choices[0],
        "AAA11 - New York, NY - 162.550 MHz - Temporarily unavailable"
    );
}

#[test]
fn single_stream_failure_and_fallback_success() {
    let env = env(&[false]);
    let dialog = env.open(None, None, vec![]);
    dialog.select_station(Some(1));
    dialog.play_stop();
    let view = wait_for(&dialog, status_is("Stream failed for BBB22"));
    assert_eq!(view.play_label, "Play");

    // First stream fails, the second plays and lifts any suppression.
    let env = env_with_suppressed_aaa11(&[false, true]);
    let dialog = env.open(None, None, vec![]);
    dialog.set_show_unavailable(true);
    wait_for(&dialog, |v| {
        v.status == "Ready" && v.station_choices.len() == 3
    });
    dialog.play_stop();
    let view = wait_for(&dialog, status_is("Playing: AAA11 (stream 2 of 2)"));
    assert_eq!(view.play_label, "Stop");
    let mut cache = StationAvailabilityCache::new(env.dir.path().join(AVAILABILITY_FILE_NAME));
    assert!(!cache.is_suppressed("AAA11"));
    // Divergence from Python, which loses the station here: the session
    // knows what the fallback stream is, and the hotkey remembers it.
    assert_eq!(env.ctx.session.playing_station(), Some(aaa11()));
    assert_eq!(
        env.ctx
            .preferences
            .lock()
            .unwrap()
            .get_last_station()
            .as_deref(),
        Some("AAA11")
    );
}

fn env_with_suppressed_aaa11(results: &[bool]) -> Env {
    let env = env(results);
    StationAvailabilityCache::new(env.dir.path().join(AVAILABILITY_FILE_NAME)).suppress(
        "AAA11",
        1800,
        "all_streams_failed",
    );
    env
}

#[test]
fn next_stream_preferred_stream_and_health_auto_advance() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    dialog.play_stop();
    wait_for(&dialog, status_is("Playing: AAA11 (stream 1 of 2)"));

    dialog.next_stream();
    wait_for(&dialog, status_is("Playing: AAA11 (stream 2 of 2)"));
    assert_eq!(env.backend.opened(), ["http://a1", "http://a2"]);

    dialog.set_preferred();
    wait_for(
        &dialog,
        status_is("Preferred stream 2 of 2 saved for AAA11"),
    );
    assert_eq!(
        env.ctx
            .preferences
            .lock()
            .unwrap()
            .get_preferred_url("AAA11")
            .as_deref(),
        Some("http://a2")
    );

    // Three silent health checks move on to the next stream.
    env.backend.last_stream().level.store(0, Ordering::SeqCst);
    for _ in 0..3 {
        dialog.enqueue(Box::new(|d| d.on_health_check()));
    }
    wait_for(&dialog, status_is("Playing: AAA11 (stream 1 of 2)"));
    assert_eq!(
        env.backend.opened(),
        ["http://a1", "http://a2", "http://a1"]
    );

    // Preferred stream is tried first next time.
    dialog.play_stop();
    wait_for(&dialog, status_is("Stopped"));
    dialog.play_stop();
    wait_for(&dialog, status_is("Playing: AAA11 (stream 1 of 2)"));
    assert_eq!(
        env.backend.opened().last().map(String::as_str),
        Some("http://a2")
    );
}

#[test]
fn stall_reports_and_reconnects() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    dialog.play_stop();
    wait_for(&dialog, status_is("Playing: AAA11 (stream 1 of 2)"));
    env.statuses.lock().unwrap().clear();
    env.backend
        .last_stream()
        .stalled
        .store(true, Ordering::SeqCst);
    dialog.enqueue(Box::new(|d| d.on_health_check()));
    wait_for(&dialog, status_is("Playing: AAA11 (stream 1 of 2)"));
    assert_eq!(
        env.statuses(),
        [
            "Stream stalled, reconnecting...",
            "Reconnecting (attempt 1)...",
            "Playing: AAA11 (stream 1 of 2)"
        ]
    );
    assert_eq!(env.backend.opened(), ["http://a1", "http://a1"]);
}

#[test]
fn favorites_toggle_label_and_favorites_mode() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    dialog.toggle_favorite();
    let view = dialog.view();
    assert_eq!(view.status, "AAA11 added to favorites");
    assert_eq!(
        view.station_choices[0],
        "Favorite - AAA11 - New York, NY - 162.550 MHz - Available"
    );
    assert_eq!(view.station_selection, Some(0));
    assert_eq!(view.favorite_label, "Remove Favorite");
    assert!(env
        .ctx
        .preferences
        .lock()
        .unwrap()
        .is_favorite_station("AAA11"));

    dialog.set_finder_mode(FinderMode::Favorites.index());
    let view = wait_for(&dialog, status_is("Ready"));
    assert!(!view.search_visible && !view.state_visible && !view.saved_location_visible);
    assert_eq!(view.station_choices.len(), 1);

    dialog.toggle_favorite();
    let view = wait_for(&dialog, status_is("No favorite stations yet"));
    assert!(view.station_choices.is_empty());
    assert_eq!(
        (view.favorite_label.as_str(), view.favorite_enabled),
        ("Favorite", false)
    );
    dialog.toggle_favorite();
    assert_eq!(dialog.view().status, "No station selected");
}

#[test]
fn finder_modes_state_saved_location_and_limits() {
    let env = env(&[]);
    let locations = vec![
        Location::new("Austin", 30.2672, -97.7431),
        Location::new("Boston", 42.36, -71.06),
    ];
    let dialog = env.open(None, None, locations);

    dialog.set_finder_mode(FinderMode::BrowseState.index());
    wait_for(&dialog, status_is("Ready"));
    assert!(dialog.view().state_visible);
    dialog.set_state_selection(2);
    dialog.find();
    let view = wait_for(&dialog, status_is("Ready"));
    assert_eq!(view.station_choices.len(), 1);
    assert!(view.station_choices[0].starts_with("BBB22"));

    dialog.set_finder_mode(FinderMode::SavedLocation.index());
    let view = wait_for(&dialog, status_is("Ready"));
    assert!(view.saved_location_visible);
    assert_eq!(view.saved_location_choices, ["Austin", "Boston"]);
    assert!(view.station_choices[0].starts_with("CCC33"));
    dialog.set_saved_location_selection(Some(1));
    dialog.find();
    let view = wait_for(&dialog, |v| {
        v.status == "Ready" && v.station_choices[0].starts_with("AAA11")
    });
    assert_eq!(view.station_choices.len(), 3);

    dialog.set_station_limit_selection(4);
    wait_for(&dialog, status_is("Ready"));
    assert_eq!(
        env.ctx.preferences.lock().unwrap().get_station_limit(),
        None
    );

    dialog.set_finder_mode(FinderMode::Nearest.index());
    dialog.set_search_text("Austin");
    dialog.find();
    let view = wait_for(&dialog, status_is("No stations with streams available"));
    assert!(view.station_choices.is_empty());
    assert!(!view.favorite_enabled);

    dialog.clear_search();
    let view = wait_for(&dialog, status_is("Ready"));
    assert_eq!(view.finder_mode, 0);
    assert_eq!(view.state_selection, 0);
    assert_eq!(view.saved_location_selection, Some(0));
    assert_eq!(view.search_text, "");
    assert_eq!(view.station_choices.len(), 3);
}

#[test]
fn saved_location_mode_without_locations_says_so() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    dialog.set_finder_mode(FinderMode::SavedLocation.index());
    let view = wait_for(&dialog, status_is("No saved locations available"));
    assert!(view.station_choices.is_empty());
}

#[test]
fn volume_goes_to_the_player() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    dialog.set_volume(75);
    assert_eq!(env.ctx.session.player.get_volume(), 0.75);
    dialog.set_volume(0);
    assert_eq!(env.ctx.session.player.get_volume(), 0.0);
    // A reopened dialog shows the session's volume.
    dialog.close();
    let dialog = env.open(None, None, vec![]);
    assert_eq!(dialog.view().volume, 0);
}

#[test]
fn closing_keeps_playing_and_reopening_syncs_state() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    dialog.select_station(Some(0));
    dialog.play_stop();
    wait_for(&dialog, status_is("Playing: AAA11 (stream 1 of 2)"));
    dialog.next_stream();
    wait_for(&dialog, status_is("Playing: AAA11 (stream 2 of 2)"));
    dialog.close();
    assert!(env.ctx.session.is_playing());
    let events_after_close = env.events.lock().unwrap().len();
    env.ctx.session.player.set_volume(0.5);
    assert_eq!(env.events.lock().unwrap().len(), events_after_close);

    let dialog = env.open(None, None, vec![]);
    let view = wait_for(&dialog, |v| v.status == "Playing: AAA11 (stream 2 of 2)");
    assert_eq!(view.play_label, "Stop");
    assert!(view.next_stream_enabled && view.prefer_enabled);
    assert_eq!(view.station_selection, Some(0));
    assert_eq!(view.volume, 50);
}

#[test]
fn hotkey_playback_while_open_is_reflected() {
    let env = env(&[]);
    let dialog = env.open(None, None, vec![]);
    dialog.select_station(Some(2));
    // Something else (hotkey, auto-tune) starts a station on another thread.
    env.ctx.session.update(|s| {
        s.playing_station = Some(bbb22());
        s.current_urls = vec!["http://b1".into()];
        s.current_url_index = 0;
    });
    let session = env.ctx.session.clone();
    std::thread::spawn(move || session.player.play("http://b1"))
        .join()
        .unwrap();
    let view = wait_for(&dialog, status_is("Playing: BBB22"));
    assert_eq!(view.play_label, "Stop");
    env.ctx.session.stop(true);
    wait_for(&dialog, status_is("Stopped"));
}

#[test]
fn missing_stream_shows_the_python_message_box() {
    let env = env(&[]);
    let empty_http: Arc<dyn aw_providers::HttpClient> = Arc::new(FixtureClient::new());
    let cache = Arc::new(Mutex::new(StationAvailabilityCache::new(
        env.dir.path().join(AVAILABILITY_FILE_NAME),
    )));
    let deps = DialogDeps {
        session: env.ctx.session.clone(),
        preferences: env.ctx.preferences.clone(),
        url_provider: Arc::new(StreamUrlProvider::new(
            Default::default(),
            false,
            None,
            Some(Arc::new(crate::weatherindex::WeatherIndexClient::new(
                empty_http,
            ))),
        )),
        availability: Arc::new(StationAvailabilityService::new(
            env.ctx.weatherindex.clone(),
            cache.clone(),
        )),
        availability_cache: cache,
        station_database: env.ctx.stations.clone(),
    };
    let events = env.events.clone();
    let dialog = RadioDialog::open(
        deps,
        None,
        None,
        vec![],
        Arc::new(move |e| events.lock().unwrap().push(e)),
    );
    wait_for(&dialog, status_is("Ready"));
    dialog.play_stop();
    wait_for(&dialog, status_is("No stream available for AAA11"));
    assert!(env.backend.opened().is_empty());
    assert_eq!(
        env.messages(),
        [DialogEvent::ShowMessage {
            title: "Stream Not Available".into(),
            message: "No online stream is available for station AAA11 (New York).\n\nNot all NOAA \
                      Weather Radio stations have online streams."
                .into(),
        }]
    );
}

#[test]
fn pure_helpers() {
    assert_eq!(
        parse_coordinate_query("30.2672, -97.7431"),
        Some((30.2672, -97.7431))
    );
    assert_eq!(parse_coordinate_query("Austin"), None);
    assert_eq!(parse_coordinate_query("91, 0"), None);
    assert_eq!(state_choice_code("Pennsylvania (PA)"), "PA");
    assert_eq!(state_choice_code("NY"), "NY");
    assert_eq!(station_limit_choice_index(Some(50)), 2);
    assert_eq!(station_limit_choice_index(None), 4);
    assert_eq!(station_limit_choice_index(Some(7)), 0);
    assert_eq!(
        format_station_choice_label(true, "Favorite - X"),
        "Favorite - X"
    );
    assert_eq!(FinderMode::from_index(9), FinderMode::SearchAll);
}

fn strings(value: &serde_json::Value) -> Vec<String> {
    serde_json::from_value(value.clone()).unwrap()
}

#[test]
fn golden_state_choices_codes_and_limits() {
    let golden = crate::golden("stations.json");
    assert_eq!(
        state_choices(&StationDatabase::new()),
        strings(&golden["state_choices"])
    );
    for (label, code) in golden["state_choice_codes"].as_object().unwrap() {
        assert_eq!(state_choice_code(label), code.as_str().unwrap(), "{label}");
    }
    for pair in golden["station_limit_indexes"].as_array().unwrap() {
        let limit = pair[0].as_u64().map(|n| n as usize);
        assert_eq!(
            station_limit_choice_index(limit) as u64,
            pair[1].as_u64().unwrap(),
            "{pair}"
        );
    }
}

#[test]
fn golden_finder_modes() {
    let golden = crate::golden("finder.json");
    let db = StationDatabase::new();
    let dir = tempfile::tempdir().unwrap();
    for case in golden["cases"].as_array().unwrap() {
        let name = case["name"].as_str().unwrap();
        let mut fixture = FixtureClient::new();
        for cs in strings(&case["feeds"]) {
            fixture = fixture.with(
                &format!("https://api.wxindex.org/v1/stations/{cs}"),
                json!({"feeds": [{"stream_url": format!("https://feed/{cs}")}]}),
            );
        }
        let mut cache = StationAvailabilityCache::with_clock(
            dir.path().join(format!("avail-{name}.json")),
            Box::new(|| 1_750_000_000.0),
        );
        for cs in strings(&case["suppressed"]) {
            cache.suppress(&cs, 600, "all_streams_failed");
        }
        let service = StationAvailabilityService::new(
            Arc::new(crate::weatherindex::WeatherIndexClient::new(Arc::new(
                fixture,
            ))),
            Arc::new(Mutex::new(cache)),
        );
        let saved: Vec<Location> = case["saved_locations"]
            .as_array()
            .unwrap()
            .iter()
            .map(|l| {
                Location::new(
                    l[0].as_str().unwrap(),
                    l[1].as_f64().unwrap(),
                    l[2].as_f64().unwrap(),
                )
            })
            .collect();
        let favorites = strings(&case["favorites"]);
        let mode = FinderMode::from_index(case["mode"].as_u64().unwrap() as usize);
        let query = FinderQuery {
            mode,
            search_query: case["query"].as_str().unwrap().to_string(),
            state_code: case["state_code"].as_str().unwrap().to_string(),
            saved_location: case["saved_index"]
                .as_u64()
                .map(|i| saved[i as usize].clone()),
            station_limit: case["limit"].as_u64().map(|n| n as usize),
            favorites: favorites.clone(),
            origin: case["origin"]
                .as_array()
                .map(|o| (o[0].as_f64().unwrap(), o[1].as_f64().unwrap())),
        };
        let candidates = find_candidates(&db, &query);
        let entries =
            service.build_entries(&candidates, case["show_unavailable"].as_bool().unwrap());
        let stations: Vec<String> = entries
            .iter()
            .map(|e| e.station.call_sign.clone())
            .collect();
        let choices: Vec<String> = entries.iter().map(|e| e.label.clone()).collect();
        let display: Vec<String> = entries
            .iter()
            .map(|e| {
                format_station_choice_label(favorites.contains(&e.station.call_sign), &e.label)
            })
            .collect();
        assert_eq!(stations, strings(&case["stations"]), "{name}");
        assert_eq!(choices, strings(&case["choices"]), "{name}");
        assert_eq!(display, strings(&case["display"]), "{name}");
        assert_eq!(
            empty_station_status(mode, !favorites.is_empty(), !saved.is_empty()),
            case["empty_status"].as_str().unwrap(),
            "{name}"
        );
    }

    for (query, expected) in golden["coordinate_queries"].as_object().unwrap() {
        let parsed = parse_coordinate_query(query).map(|(a, b)| json!([a, b]));
        assert_eq!(
            parsed.unwrap_or(serde_json::Value::Null),
            *expected,
            "{query}"
        );
    }
    for case in golden["initial_search_text"].as_array().unwrap() {
        let (lat, lon) = (case[0].as_f64().unwrap(), case[1].as_f64().unwrap());
        assert_eq!(format!("{lat:.4}, {lon:.4}"), case[2].as_str().unwrap());
    }
}
