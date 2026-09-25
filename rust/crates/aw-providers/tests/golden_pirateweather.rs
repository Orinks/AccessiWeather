//! Parity with `rust/tools/golden/pirateweather.py` (Pirate Weather and the
//! Open-Meteo Marine surf summary).

mod common;

use std::sync::Arc;

use aw_core::model::{Location, TextProduct};
use aw_providers::http::FixtureClient;
use aw_providers::pirateweather::{self, PirateWeatherClient};
use aw_providers::surf_conditions;
use common::{assert_matches, assert_requests, cases, fixture_from_exchanges, timestamp};
use serde_json::{json, to_value, Value};

#[test]
fn parsers_match_python_for_every_unit_bundle() {
    for (name, case) in cases("pirateweather", "parse_") {
        let input = &case["input"];
        let now = timestamp(&case["now"]);
        let client = PirateWeatherClient::new(
            Arc::new(FixtureClient::new()),
            "k",
            "UA",
            case["units"].as_str().unwrap(),
        );
        let units = client.units.as_str();
        let beach = Location::new("Beach", 40.0, -74.0);
        let checks: [(&str, Value); 6] = [
            (
                "current",
                to_value(pirateweather::parse_current_conditions(units, input)).unwrap(),
            ),
            (
                "forecast",
                to_value(pirateweather::parse_forecast(units, input, now)).unwrap(),
            ),
            (
                "hourly",
                to_value(pirateweather::parse_hourly_forecast(units, input, now)).unwrap(),
            ),
            (
                "alerts",
                to_value(pirateweather::parse_alerts(input)).unwrap(),
            ),
            (
                "minutely",
                to_value(pirateweather::parse_minutely_block(input, units)).unwrap(),
            ),
            (
                "beach",
                to_value(surf_conditions::pirate_weather_beach_conditions(
                    input, &beach, now,
                ))
                .unwrap(),
            ),
        ];
        for (key, actual) in checks {
            assert_matches(&case[key], &actual, &format!("{name}.{key}"), &[]);
        }
    }
}

/// Naive marine times are local wall-clock in both apps; compare them as
/// wall-clock so the test does not depend on this machine's time zone.
fn assert_marine_product(expected: &Value, actual: Option<TextProduct>, context: &str) {
    let actual = to_value(actual).unwrap();
    assert_matches(expected, &actual, context, &["issuance_time"]);
    let wall = |v: &Value| v["issuance_time"].as_str().map(|s| s[..19].to_string());
    assert_eq!(
        wall(expected),
        wall(&actual),
        "{context}: issuance wall-clock"
    );
}

fn porto() -> Location {
    Location::new("Porto", 41.15, -8.63).with_country("PT")
}

#[test]
fn marine_reports_match_python() {
    for (name, case) in cases("pirateweather", "marine_") {
        let report = surf_conditions::format_openmeteo_marine_report(
            &case["input"],
            &porto(),
            timestamp(&case["now"]),
        );
        assert_marine_product(&case["product"], report.map(|r| r.to_text_product()), &name);
    }
    let (name, case) = cases("pirateweather", "fetch_marine").remove(0);
    let http = fixture_from_exchanges(&case["exchanges"]);
    let product = surf_conditions::fetch_openmeteo_marine_surf_conditions(
        &http,
        &porto(),
        surf_conditions::OPENMETEO_MARINE_BASE_URL,
        surf_conditions::DEFAULT_USER_AGENT,
    );
    assert_requests(&case["exchanges"], &http, &name);
    assert_marine_product(&case["output"], product, &name);
}

#[test]
fn http_statuses_match_python() {
    for (name, case) in cases("pirateweather", "fetch_status_") {
        let http = Arc::new(fixture_from_exchanges(&case["exchanges"]));
        let client = PirateWeatherClient::new(http.clone(), "secret", "AccessiWeather/2.0", "uk");
        let result = client.get_current_conditions(&Location::new("NYC", 40.7128, -74.006));
        assert_requests(&case["exchanges"], &http, &name);
        match result {
            Ok(current) => assert_matches(&case["output"], &to_value(current).unwrap(), &name, &[]),
            Err(e) => assert_eq!(
                case["error"],
                json!({"message": e.message, "status_code": e.status_code}),
                "{name}"
            ),
        }
    }
}
