//! Parity with `rust/tools/golden/openmeteo.py`.

mod common;

use aw_core::model::Location;
use aw_providers::openmeteo::{self, mapper, OpenMeteoApiClient};
use common::{assert_matches, assert_requests, cases, fixture_from_exchanges, timestamp};
use serde_json::{to_value, Value};

#[test]
fn parsers_and_mapper_match_python() {
    for (name, case) in cases("openmeteo", "parse_") {
        let input = &case["input"];
        let now = timestamp(&case["now"]);
        let checks: [(&str, Value); 7] = [
            (
                "current",
                to_value(openmeteo::parse_openmeteo_current_conditions(input)).unwrap(),
            ),
            (
                "forecast",
                to_value(openmeteo::parse_openmeteo_forecast(input, now)).unwrap(),
            ),
            (
                "hourly",
                to_value(openmeteo::parse_openmeteo_hourly_forecast(input, now)).unwrap(),
            ),
            ("mapped_current", mapper::map_current_conditions(input, now)),
            ("mapped_forecast", mapper::map_forecast(input, now)),
            ("mapped_hourly", mapper::map_hourly_forecast(input, now)),
            (
                "hourly_uv",
                to_value(mapper::map_hourly_uv_index(input)).unwrap(),
            ),
        ];
        for (key, mut actual) in checks {
            // The golden file records Python's naive `datetime.now()` with
            // the local offset; the model keeps it naive.
            if let Some(g) = actual.get_mut("generated_at").filter(|g| !g.is_null()) {
                assert_eq!(*g, to_value(now.naive_local()).unwrap(), "{name}.{key}");
                *g = to_value(now).unwrap();
            }
            assert_matches(&case[key], &actual, &format!("{name}.{key}"), &[]);
        }
    }
}

fn nyc() -> Location {
    Location::new("New York", 40.7128, -74.006)
}

fn now() -> aw_core::model::Timestamp {
    chrono::Local::now().fixed_offset()
}

fn london() -> Location {
    Location::new("London", 51.5074, -0.1278)
}

#[test]
fn fetchers_request_the_same_urls() {
    let base = openmeteo::BASE_URL;
    for (name, case) in cases("openmeteo", "fetch_") {
        let http = fixture_from_exchanges(&case["exchanges"]);
        let output = match name.as_str() {
            "fetch_current_best_match" => to_value(
                openmeteo::get_openmeteo_current_conditions(&http, &nyc(), base, "best_match")
                    .unwrap(),
            ),
            "fetch_forecast_model_clamped" => to_value(
                openmeteo::get_openmeteo_forecast(
                    &http,
                    &london(),
                    base,
                    30,
                    "icon_seamless",
                    now(),
                )
                .unwrap(),
            ),
            "fetch_hourly_min_clamped" => to_value(
                openmeteo::get_openmeteo_hourly_forecast(
                    &http,
                    &nyc(),
                    base,
                    0,
                    "best_match",
                    now(),
                )
                .unwrap(),
            ),
            "fetch_dict_client_urls" => {
                let client = OpenMeteoApiClient::new(&http);
                client
                    .get_current_weather(
                        40.7128,
                        -74.006,
                        "fahrenheit",
                        "mph",
                        "inch",
                        "best_match",
                    )
                    .unwrap();
                client
                    .get_forecast(40.0, -74.0, 20, "celsius", "mph", "inch", "gfs_seamless")
                    .unwrap();
                client
                    .get_hourly_forecast(51.5, -0.12, 500, "fahrenheit", "kmh", "mm", "best_match")
                    .unwrap();
                assert_requests(&case["exchanges"], &http, &name);
                continue;
            }
            other => panic!("unhandled golden case {other}"),
        }
        .unwrap();
        assert_requests(&case["exchanges"], &http, &name);
        // generated_at is the wall clock in the fetch helpers; the parse
        // cases cover it with a frozen clock.
        assert_matches(&case["output"], &output, &name, &["generated_at"]);
    }
}
