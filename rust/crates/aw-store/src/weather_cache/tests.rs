use aw_core::golden::{self, assert_json_eq, field};
use aw_core::model::{CurrentConditions, Forecast, ForecastPeriod, WeatherAlerts};

use super::*;

fn cache_in(dir: &tempfile::TempDir, max_age_minutes: i64) -> WeatherDataCache {
    WeatherDataCache::new(dir.path(), max_age_minutes).unwrap()
}

#[test]
fn golden_store_writes_python_bytes() {
    for case in golden::load("cache/store.json").as_array().unwrap() {
        let dir = tempfile::tempdir().unwrap();
        let cache = cache_in(&dir, DEFAULT_MAX_AGE_MINUTES);
        let location: Location = field(case, "location");
        let weather: WeatherData = field(case, "weather");
        cache.store(&location, &weather, field(case, "now"));
        let path = cache.path_for_location(&location);
        assert_eq!(
            path.file_name().unwrap().to_str().unwrap(),
            case["file_name"].as_str().unwrap()
        );
        let written = fs::read_to_string(&path).unwrap();
        // Generated on Windows, where Python's text mode writes CRLF.
        let expected = case["file_text"].as_str().unwrap();
        let expected = if cfg!(windows) {
            expected.to_string()
        } else {
            expected.replace("\r\n", "\n")
        };
        assert_eq!(written, expected, "{}", case["name"]);
    }
}

#[test]
fn golden_load_matches_python() {
    let location = Location::new("Test City", 40.0, -74.0);
    for case in golden::load("cache/load.json").as_array().unwrap() {
        let dir = tempfile::tempdir().unwrap();
        let cache = cache_in(&dir, DEFAULT_MAX_AGE_MINUTES);
        let path = cache.path_for_location(&location);
        fs::write(&path, case["file_text"].as_str().unwrap()).unwrap();
        let loaded = cache.load(&location, field(case, "allow_stale"), field(case, "now"));
        let name = case["name"].as_str().unwrap();
        let mut expected = case["result"].clone();
        if let Some(stored) = expected.get_mut("location") {
            // Round-trip through `Location` so its skip-if-default rules apply.
            let typed: Location = serde_json::from_value(stored.clone()).unwrap();
            *stored = serde_json::to_value(typed).unwrap();
        }
        assert_json_eq(&loaded, &expected, name);
        assert_eq!(
            path.exists(),
            case["file_kept"].as_bool().unwrap(),
            "{name}"
        );
    }
}

#[test]
fn golden_purge_matches_python() {
    let case = golden::load("cache/purge.json");
    let dir = tempfile::tempdir().unwrap();
    for (name, text) in case["files"].as_object().unwrap() {
        fs::write(dir.path().join(name), text.as_str().unwrap()).unwrap();
    }
    cache_in(&dir, DEFAULT_MAX_AGE_MINUTES).purge_expired(field(&case, "now"));
    let mut remaining: Vec<String> = fs::read_dir(dir.path())
        .unwrap()
        .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
        .collect();
    remaining.sort();
    let expected: Vec<String> = field(&case, "remaining");
    assert_eq!(remaining, expected);
}

#[test]
fn golden_location_keys() {
    for case in golden::load("cache/keys.json").as_array().unwrap() {
        let location: Location = field(case, "location");
        assert_eq!(safe_location_key(&location), case["key"].as_str().unwrap());
    }
}

#[test]
fn python_float_repr() {
    for (value, repr) in [
        (72.0, "72.0"),
        (-0.0, "-0.0"),
        (0.1 + 0.2, "0.30000000000000004"),
        (1e16, "1e+16"),
        (1e15, "1000000000000000.0"),
        (0.0001, "0.0001"),
        (0.00001, "1e-05"),
        (1.5e-7, "1.5e-07"),
        (-123.456, "-123.456"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
    ] {
        assert_eq!(py_float_repr(value), repr);
    }
}

fn test_location() -> Location {
    Location::new("Test City", 40.0, -74.0)
}

fn test_weather() -> WeatherData {
    let mut current = CurrentConditions {
        temperature_f: Some(72.0),
        temperature_c: Some(22.2),
        condition: Some("Sunny".into()),
        ..Default::default()
    };
    current.backfill();
    WeatherData {
        current: Some(current),
        forecast: Some(Forecast {
            periods: vec![ForecastPeriod {
                name: "Today".into(),
                temperature: Some(75.0),
                short_forecast: Some("Sunny".into()),
                ..Default::default()
            }],
            generated_at: Some(PyTimestamp::Aware(Utc::now().fixed_offset())),
            summary: None,
        }),
        alerts: Some(WeatherAlerts::default()),
        ..WeatherData::new(test_location())
    }
}

#[test]
fn store_and_load_round_trip() {
    let dir = tempfile::tempdir().unwrap();
    let cache = cache_in(&dir, 60);
    let now = Utc::now();
    cache.store(&test_location(), &test_weather(), now);
    let loaded = cache.load(&test_location(), true, now).unwrap();
    let current = loaded.current.unwrap();
    assert_eq!(current.temperature_f, Some(72.0));
    assert_eq!(current.condition.as_deref(), Some("Sunny"));
    assert!(!loaded.stale);
    assert_eq!(loaded.stale_reason.as_deref(), Some("Cached data"));
}

#[test]
fn missing_and_invalidated_entries_load_nothing() {
    let dir = tempfile::tempdir().unwrap();
    let cache = cache_in(&dir, 60);
    let now = Utc::now();
    assert!(cache.load(&test_location(), true, now).is_none());
    cache.store(&test_location(), &test_weather(), now);
    cache.invalidate(&test_location());
    assert!(cache.load(&test_location(), true, now).is_none());
}

#[test]
fn old_entries_are_stale_rejected_when_strict_and_purged() {
    let dir = tempfile::tempdir().unwrap();
    let cache = cache_in(&dir, 0);
    let saved = Utc::now();
    cache.store(&test_location(), &test_weather(), saved);
    let later = saved + Duration::milliseconds(100);
    assert!(cache.load(&test_location(), true, later).unwrap().stale);
    assert!(cache.load(&test_location(), false, later).is_none());
    cache.purge_expired(later);
    assert!(cache.load(&test_location(), true, later).is_none());
}
