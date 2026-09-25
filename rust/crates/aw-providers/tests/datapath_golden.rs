//! End to end against `rust/tools/golden/datapath.py`: recorded cassette
//! bodies served by `FixtureClient` -> the live source adapters -> the
//! orchestrator -> `WeatherPresenter`, with a frozen clock, compared with
//! what the Python `WeatherClient` and presenter produced from the same
//! bodies.

mod common;

use std::sync::Arc;
use std::time::Duration;

use aw_core::display::{Clock, WeatherPresenter};
use aw_core::model::{Location, WeatherData};
use aw_core::settings::AppSettings;
use aw_providers::client::live::Live;
use aw_providers::client::WeatherClient;
use aw_providers::http::FixtureClient;
use chrono::{DateTime, Utc};
use common::{assert_matches, cases};
use serde_json::Value;

/// The routes as `FixtureClient` prefixes (longest prefix wins, as in the
/// Python mock).
fn fixture(routes: &Value) -> FixtureClient {
    let mut http = FixtureClient::new();
    for route in routes.as_array().unwrap() {
        let prefix = route["prefix"].as_str().unwrap();
        let status = route["status"].as_u64().unwrap() as u16;
        let body = route["body"].as_str().unwrap();
        http = if body.is_empty() && status >= 400 {
            http.with_status(prefix, status)
        } else {
            http.with_response(prefix, status, body)
        };
    }
    http
}

fn settings(overrides: &Value) -> AppSettings {
    let mut value = serde_json::to_value(AppSettings::default()).unwrap();
    for (key, v) in overrides.as_object().unwrap() {
        value[key] = v.clone();
    }
    serde_json::from_value(value).unwrap()
}

fn run(case: &Value) -> (Arc<FixtureClient>, WeatherData, AppSettings, Clock) {
    let now: DateTime<Utc> = common::timestamp(&case["now"]).with_timezone(&Utc);
    let http = Arc::new(fixture(&case["routes"]));
    let mut live = Live::new(http.clone());
    live.clock = Arc::new(move || now);
    live.retry_delay = Duration::ZERO;
    let settings = settings(&case["settings"]);
    let client = WeatherClient::new(
        live.sources(&settings),
        settings.clone(),
        &settings.data_source,
        None,
    )
    .with_clock(Arc::new(move || now));
    let location: Location = serde_json::from_value(case["location"].clone()).unwrap();
    let weather = client.get_weather_data(&location, false);
    let tz = case["local_tz"].as_str().unwrap().parse().unwrap();
    (http, weather, settings, Clock::fixed(now, tz))
}

#[test]
fn cassettes_to_presentation_match_python() {
    for (name, case) in cases("datapath", "") {
        let (http, weather, settings, clock) = run(&case);

        let mut expected_urls: Vec<&str> = case["requests"]
            .as_array()
            .unwrap()
            .iter()
            .map(|u| u.as_str().unwrap())
            .collect();
        let mut urls = http.request_log();
        expected_urls.sort_unstable();
        urls.sort_unstable();
        assert_eq!(urls, expected_urls, "{name}: requests");

        let presentation = WeatherPresenter::with_clock(&settings, clock).present(&weather);
        assert_matches(
            &case["presentation"],
            &serde_json::to_value(&presentation).unwrap(),
            &name,
            &[],
        );
    }
}
