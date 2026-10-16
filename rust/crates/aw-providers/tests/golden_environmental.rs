//! Parity with `rust/tools/golden/environmental.py`.

mod common;

use std::sync::Arc;

use aw_core::model::Location;
use aw_providers::environmental::airnow::{parse_observations, AirNowClient, AirNowObservation};
use aw_providers::environmental::{EnvironmentalDataClient, FetchOptions};
use aw_providers::http::FixtureClient;
use common::{assert_matches, assert_requests, cases, fixture_from_exchanges, timestamp};
use serde_json::{json, to_value, Value};

fn options(value: &Value) -> FetchOptions {
    let mut options = FetchOptions::default();
    let flag =
        |key: &str, default: bool| value.get(key).and_then(Value::as_bool).unwrap_or(default);
    options.include_air_quality = flag("include_air_quality", true);
    options.include_pollen = flag("include_pollen", true);
    options.include_hourly_air_quality = flag("include_hourly_air_quality", true);
    options.include_hourly_uv = flag("include_hourly_uv", true);
    options.prefer_airnow = flag("prefer_airnow", false);
    if let Some(hours) = value.get("hourly_hours").and_then(Value::as_u64) {
        options.hourly_hours = hours as usize;
    }
    options
}

#[test]
fn fetch_matches_python() {
    let location = Location::new("Philadelphia", 39.9526, -75.1652).with_country("US");
    for (name, case) in cases("environmental", "fetch_") {
        let http = Arc::new(fixture_from_exchanges(&case["exchanges"]));
        let client = EnvironmentalDataClient::new(
            http.clone(),
            "AccessiWeather/2.0",
            case["airnow_key"].as_str().unwrap(),
        );
        let result = client.fetch(
            &location,
            options(&case["options"]),
            timestamp(&case["now"]),
        );
        assert_requests(&case["exchanges"], &http, &name);
        assert_matches(&case["output"], &to_value(result).unwrap(), &name, &[]);
    }
}

fn observation_json(o: Option<AirNowObservation>) -> Value {
    o.map_or(Value::Null, |o| {
        json!({
            "aqi": o.aqi,
            "category": o.category,
            "pollutant": o.pollutant,
            "observed_at": o.observed_at,
            "reporting_area": o.reporting_area,
        })
    })
}

#[test]
fn airnow_parsing_matches_python() {
    for (name, case) in cases("environmental", "airnow_parse_") {
        let actual = observation_json(parse_observations(&case["input"]));
        assert_matches(&case["output"], &actual, &name, &[]);
    }
}

#[test]
fn airnow_key_validation_matches_python() {
    for (name, case) in cases("environmental", "airnow_validate_") {
        let http = Arc::new(fixture_from_exchanges(&case["exchanges"]));
        let (valid, reason) =
            AirNowClient::new(http.clone(), " key ", "AccessiWeather/2.0").validate_api_key();
        assert_requests(&case["exchanges"], &http, &name);
        assert_eq!(
            json!([valid, reason]),
            json!([case["valid"], case["reason"]]),
            "{name}"
        );
    }
    let _ = FixtureClient::new();
}
