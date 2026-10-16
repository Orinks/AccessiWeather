//! Golden parity tests for `aw_core::display` against the Python presenter.
//!
//! The files come from `rust/tools/golden/display.py`; see that script for
//! how the inputs are built and normalised.

use std::collections::BTreeMap;
use std::path::PathBuf;

use aw_core::display::time::{format_date, format_datetime, PyDateTime};
use aw_core::display::tray::{self, TaskbarIconUpdater};
use aw_core::display::{taf, Clock, WeatherPresenter};
use aw_core::model::WeatherData;
use aw_core::settings::AppSettings;
use chrono::{DateTime, NaiveDateTime, Utc};
use serde_json::Value;

fn golden_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../testdata/golden/display")
}

fn load(name: &str) -> Value {
    let path = golden_dir().join(name);
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).expect("golden JSON")
}

/// The first path where two JSON values differ.
fn first_diff(path: &str, expected: &Value, actual: &Value) -> Option<String> {
    match (expected, actual) {
        (Value::Object(e), Value::Object(a)) => {
            for (k, ev) in e {
                let av = a.get(k).unwrap_or(&Value::Null);
                if let Some(d) = first_diff(&format!("{path}.{k}"), ev, av) {
                    return Some(d);
                }
            }
            a.keys()
                .find(|k| !e.contains_key(*k))
                .map(|k| format!("{path}.{k}: unexpected key"))
        }
        (Value::Array(e), Value::Array(a)) => {
            for (i, (ev, av)) in e.iter().zip(a).enumerate() {
                if let Some(d) = first_diff(&format!("{path}[{i}]"), ev, av) {
                    return Some(d);
                }
            }
            (e.len() != a.len()).then(|| format!("{path}: length {} != {}", e.len(), a.len()))
        }
        _ if expected == actual => None,
        _ => Some(format!("{path}:\n  python: {expected}\n  rust:   {actual}")),
    }
}

fn check(failures: &mut Vec<String>, label: String, expected: &Value, actual: Value) {
    if let Some(d) = first_diff("", expected, &actual) {
        failures.push(format!("{label}{d}"));
    }
}

#[test]
fn presentations_match_python() {
    let mut files: Vec<PathBuf> = std::fs::read_dir(golden_dir())
        .expect("golden dir")
        .map(|e| e.expect("entry").path())
        .filter(|p| {
            p.extension().is_some_and(|e| e == "json")
                && !p
                    .file_name()
                    .is_some_and(|n| n.to_string_lossy().starts_with('_'))
        })
        .collect();
    files.sort();
    assert!(
        files.len() >= 15,
        "expected the golden cases, found {}",
        files.len()
    );

    let mut failures = Vec::new();
    let mut compared = 0;
    for file in &files {
        let doc = load(&file.file_name().unwrap().to_string_lossy());
        let case = doc["name"].as_str().unwrap().to_string();
        let data: WeatherData = serde_json::from_value(doc["weather_data"].clone())
            .unwrap_or_else(|e| panic!("{case}: weather_data: {e}"));
        let now: DateTime<Utc> = doc["now"].as_str().unwrap().parse().unwrap();
        let clock = Clock::fixed(now, doc["local_tz"].as_str().unwrap().parse().unwrap());

        for variant in doc["variants"].as_array().unwrap() {
            let settings: AppSettings =
                serde_json::from_value(variant["settings"].clone()).unwrap();
            let label = format!("[{case} {}] ", variant["settings"]);
            let presenter = WeatherPresenter::with_clock(&settings, clock);

            check(
                &mut failures,
                format!("{label}presentation"),
                &variant["presentation"],
                serde_json::to_value(presenter.present(&data)).unwrap(),
            );
            compared += 1;

            if let Some(expected) = variant.get("present_current") {
                let got = presenter.present_current(
                    data.current.as_ref(),
                    &data.location,
                    data.environmental.as_ref(),
                    &data.trend_insights,
                    data.hourly_forecast.as_ref(),
                    data.alerts.as_ref(),
                );
                check(
                    &mut failures,
                    format!("{label}present_current"),
                    expected,
                    serde_json::to_value(got).unwrap(),
                );
                let got = presenter.present_forecast(
                    data.forecast.as_ref(),
                    &data.location,
                    data.hourly_forecast.as_ref(),
                    data.marine.as_ref(),
                    data.forecast_confidence.as_ref(),
                    Some("Stay dry."),
                );
                check(
                    &mut failures,
                    format!("{label}present_forecast"),
                    &variant["present_forecast"],
                    serde_json::to_value(got).unwrap(),
                );
                let got = presenter.present_alerts(data.alerts.as_ref(), &data.location);
                check(
                    &mut failures,
                    format!("{label}present_alerts"),
                    &variant["present_alerts"],
                    serde_json::to_value(got).unwrap(),
                );
            }

            for (fmt, expected) in variant["tray"].as_object().unwrap() {
                let updater = TaskbarIconUpdater {
                    text_enabled: true,
                    format_string: fmt.clone(),
                    temperature_unit: settings.temperature_unit.clone(),
                    wind_speed_unit: settings.wind_speed_unit.clone(),
                    round_values: settings.round_values,
                    ..Default::default()
                };
                let name = Some(data.location.name.as_str());
                let got = serde_json::json!({
                    "tooltip": updater.format_tooltip(Some(&data), name, now),
                    "preview": updater.build_preview(fmt, Some(&data), name, now),
                    "sample_preview": updater.build_preview(fmt, None, None, now),
                });
                check(&mut failures, format!("{label}tray {fmt:?}"), expected, got);
            }
        }
    }
    assert!(
        failures.is_empty(),
        "{} of {compared} presentations differ from Python:\n{}",
        failures.len(),
        failures
            .iter()
            .take(25)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
}

#[test]
fn helpers_match_python() {
    let doc = load("_helpers.json");
    for case in doc["taf"].as_array().unwrap() {
        assert_eq!(
            taf::decode_taf_text(case["raw"].as_str().unwrap()),
            case["decoded"].as_str().unwrap(),
            "TAF {}",
            case["raw"]
        );
    }
    type Decoder = fn(&str) -> Option<String>;
    let decoders: [(&str, Decoder); 4] = [
        ("_decode_wind", taf::decode_wind),
        ("_decode_visibility", taf::decode_visibility),
        ("_decode_weather", taf::decode_weather),
        ("_decode_cloud", taf::decode_cloud),
    ];
    for (name, decode) in decoders {
        for case in doc["taf_elements"][name].as_array().unwrap() {
            let token = case["token"].as_str().unwrap();
            assert_eq!(
                decode(token).as_deref(),
                case["decoded"].as_str(),
                "{name}({token:?})"
            );
        }
    }
    for case in doc["dates"].as_array().unwrap() {
        let text = case["value"].as_str().unwrap();
        let value = match DateTime::parse_from_rfc3339(text) {
            Ok(dt) => PyDateTime::aware(dt, None),
            Err(_) => {
                PyDateTime::naive(NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M:%S").unwrap())
            }
        };
        let style = case["style"].as_str().unwrap();
        let twelve = case["time_12hour"].as_bool().unwrap();
        assert_eq!(
            format_date(Some(&value), style),
            case["date"].as_str().unwrap(),
            "{case}"
        );
        assert_eq!(
            format_datetime(Some(&value), style, twelve),
            case["datetime"].as_str().unwrap(),
            "{case}"
        );
    }
    let data: BTreeMap<String, String> = [("temp", "72F"), ("condition", "{temp}")]
        .map(|(k, v)| (k.into(), v.into()))
        .into();
    for case in doc["placeholders"].as_array().unwrap() {
        let fmt = case["format"].as_str().unwrap();
        let placeholders: Vec<String> =
            serde_json::from_value(case["placeholders"].clone()).unwrap();
        assert_eq!(tray::get_placeholders(fmt), placeholders, "{fmt}");
        let valid = &case["valid"];
        let got = match tray::validate_format_string(fmt) {
            Ok(()) => serde_json::json!([true, null]),
            Err(e) => serde_json::json!([false, e]),
        };
        assert_eq!(&got, valid, "{fmt}");
        assert_eq!(
            tray::format_string(fmt, &data),
            case["formatted"].as_str().unwrap(),
            "{fmt}"
        );
    }
    assert_eq!(
        tray::supported_placeholders_help(),
        doc["placeholder_help"].as_str().unwrap()
    );
}
