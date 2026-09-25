use std::collections::BTreeMap;

use super::*;
use crate::golden::{self, field};
use crate::model::{Forecast, ForecastPeriod, HourlyForecast, SourceAttribution};

#[test]
fn golden_merge_current_conditions() {
    let cases = golden::load("fusion/merge_current.json");
    for case in cases.as_array().unwrap() {
        let engine = DataFusionEngine::new(field(case, "config"));
        let sources: Vec<SourceData> = field(case, "sources");
        let location: Location = field(case, "location");
        let (current, attribution) = engine.merge_current_conditions(&sources, &location);
        let expected: Option<CurrentConditions> = field(case, "current");
        let expected_attr: SourceAttribution = field(case, "attribution");
        assert_eq!(current, expected, "{}", case["name"]);
        assert_eq!(attribution, expected_attr, "{}", case["name"]);
    }
}

#[test]
fn golden_merge_forecasts() {
    let cases = golden::load("fusion/merge_forecasts.json");
    for case in cases.as_array().unwrap() {
        let sources: Vec<SourceData> = field(case, "sources");
        let location: Location = field(case, "location");
        let days: i64 = field(case, "requested_days");
        let (forecast, sources_map) =
            DataFusionEngine::default().merge_forecasts(&sources, &location, days);
        let expected: Option<Forecast> = field(case, "forecast");
        let expected_map: BTreeMap<String, String> = field(case, "field_sources");
        assert_eq!(forecast, expected, "{}", case["name"]);
        assert_eq!(sources_map, expected_map, "{}", case["name"]);
    }
}

#[test]
fn golden_merge_hourly_forecasts() {
    let cases = golden::load("fusion/merge_hourly.json");
    for case in cases.as_array().unwrap() {
        let sources: Vec<SourceData> = field(case, "sources");
        let location: Location = field(case, "location");
        let (hourly, sources_map) =
            DataFusionEngine::default().merge_hourly_forecasts(&sources, &location);
        let expected: Option<HourlyForecast> = field(case, "hourly");
        let expected_map: BTreeMap<String, String> = field(case, "field_sources");
        assert_eq!(hourly, expected, "{}", case["name"]);
        assert_eq!(sources_map, expected_map, "{}", case["name"]);
    }
}

fn us() -> Location {
    Location::new("New York", 40.7, -74.0).with_country("US")
}

fn intl() -> Location {
    Location::new("London", 51.5, -0.1).with_country("GB")
}

fn source(name: &str, current: CurrentConditions) -> SourceData {
    SourceData {
        current: Some(current),
        ..SourceData::new(name)
    }
}

fn cc() -> CurrentConditions {
    CurrentConditions::default()
}

#[test]
fn no_valid_sources_returns_none() {
    let engine = DataFusionEngine::default();
    assert!(engine.merge_current_conditions(&[], &us()).0.is_none());
    let failed = SourceData {
        success: false,
        ..SourceData::new("nws")
    };
    assert!(engine
        .merge_current_conditions(&[failed], &us())
        .0
        .is_none());
}

#[test]
fn per_field_priority_override_wins() {
    let mut config = SourcePriorityConfig::default();
    config
        .field_priorities
        .insert("humidity".into(), vec!["openmeteo".into(), "nws".into()]);
    let engine = DataFusionEngine::new(config);
    let sources = [
        source(
            "nws",
            CurrentConditions {
                humidity: Some(40),
                ..cc()
            },
        ),
        source(
            "openmeteo",
            CurrentConditions {
                humidity: Some(55),
                ..cc()
            },
        ),
    ];
    let (current, attr) = engine.merge_current_conditions(&sources, &us());
    assert_eq!(current.unwrap().humidity, Some(55));
    assert_eq!(attr.field_sources["humidity"], "openmeteo");
}

#[test]
fn temperature_conflict_selects_priority_source() {
    let sources = [
        source(
            "nws",
            CurrentConditions {
                temperature_f: Some(70.0),
                ..cc()
            },
        ),
        source(
            "openmeteo",
            CurrentConditions {
                temperature_f: Some(80.0),
                ..cc()
            },
        ),
    ];
    let (_, attr) = DataFusionEngine::default().merge_current_conditions(&sources, &us());
    let conflict = &attr.conflicts[0];
    assert_eq!(conflict.selected_source, "nws");
    assert_eq!(conflict.selected_value, serde_json::json!(70.0));
}

#[test]
fn gust_below_fused_speed_is_dropped() {
    let sources = [
        source(
            "pirateweather",
            CurrentConditions {
                wind_speed_mph: Some(14.0),
                wind_speed_kph: Some(22.5),
                ..cc()
            },
        ),
        source(
            "openmeteo",
            CurrentConditions {
                wind_gust_mph: Some(11.0),
                wind_gust_kph: Some(17.7),
                ..cc()
            },
        ),
    ];
    let (current, attr) = DataFusionEngine::default().merge_current_conditions(&sources, &intl());
    let current = current.unwrap();
    assert_eq!(current.wind_gust_mph, None);
    assert!(!attr.field_sources.contains_key("wind_gust_mph"));
}

#[test]
fn us_forecast_extended_prefers_openmeteo() {
    let fc = |name: &str| Forecast {
        periods: vec![ForecastPeriod {
            name: name.into(),
            ..Default::default()
        }],
        ..Default::default()
    };
    let sources = [
        SourceData {
            forecast: Some(fc("NWS")),
            ..SourceData::new("nws")
        },
        SourceData {
            forecast: Some(fc("OM")),
            ..SourceData::new("openmeteo")
        },
    ];
    let engine = DataFusionEngine::default();
    let (_, seven) = engine.merge_forecasts(&sources, &us(), 7);
    let (_, fifteen) = engine.merge_forecasts(&sources, &us(), 15);
    assert_eq!(seven["forecast_source"], "nws");
    assert_eq!(fifteen["forecast_source"], "openmeteo");
}
