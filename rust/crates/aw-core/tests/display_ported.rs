//! Ports of the Python unit tests for the presentation layer (the golden
//! files cover the full pipeline; these pin individual rules). Each section
//! names the Python test module it comes from.

use std::collections::HashMap;

use aw_core::display::alerts::build_alerts;
use aw_core::display::current::{
    compute_pressure_trend_from_hourly, describe_trend, direction_descriptor,
    format_temperature_value, format_trend_lines, severe_risk_description,
    split_direction_descriptor,
};
use aw_core::display::environmental::{build_air_quality_panel, format_pollen_details};
use aw_core::display::forecast::{build_hourly_section_text, render_hourly_fallback};
use aw_core::display::impact::{build_forecast_impact_summary, build_impact_summary};
use aw_core::display::measurement::{
    format_hourly_wind, format_period_wind, format_temperature_with_feels_like,
};
use aw_core::display::mobility::build_mobility_briefing;
use aw_core::display::time::{
    format_date, format_datetime, format_display_time, resolve_forecast_display_time, PyDateTime,
};
use aw_core::display::tray::{self, TaskbarIconUpdater, DEFAULT_TOOLTIP_TEXT};
use aw_core::display::units::TemperatureUnit;
use aw_core::display::{Clock, WeatherPresenter};
use aw_core::location::Location;
use aw_core::model::*;
use aw_core::settings::AppSettings;
use chrono::{DateTime, Duration, FixedOffset, NaiveDate, TimeZone, Utc};

fn utc(y: i32, mo: u32, d: u32, h: u32, mi: u32) -> Timestamp {
    Utc.with_ymd_and_hms(y, mo, d, h, mi, 0)
        .unwrap()
        .fixed_offset()
}

fn settings(json: serde_json::Value) -> AppSettings {
    serde_json::from_value(json).unwrap()
}

fn presenter(json: serde_json::Value, now: Timestamp) -> WeatherPresenter {
    WeatherPresenter::with_clock(
        &settings(json),
        Clock::fixed(now.with_timezone(&Utc), chrono_tz::America::New_York),
    )
}

fn testville() -> Location {
    Location::new("Testville", 40.0, -75.0)
}

fn hourly_period(start: Timestamp) -> HourlyForecastPeriod {
    HourlyForecastPeriod::new(start)
}

fn labels(p: &aw_core::display::CurrentConditionsPresentation) -> Vec<&str> {
    p.metrics.iter().map(|m| m.label.as_str()).collect()
}

fn metric<'a>(
    p: &'a aw_core::display::CurrentConditionsPresentation,
    label: &str,
) -> Option<&'a str> {
    p.metrics
        .iter()
        .find(|m| m.label == label)
        .map(|m| m.value.as_str())
}

// ---------------------------------------------------------------------------
// test_current_conditions.py
// ---------------------------------------------------------------------------

#[test]
fn current_format_temperature_value() {
    use TemperatureUnit::*;
    assert_eq!(
        format_temperature_value(Some(72.0), None, Fahrenheit, 0).unwrap(),
        "72°F"
    );
    assert_eq!(
        format_temperature_value(Some(72.0), Some(22.2), Celsius, 1).unwrap(),
        "22.2°C"
    );
    assert_eq!(
        format_temperature_value(Some(32.0), None, Celsius, 0).unwrap(),
        "0°C"
    );
    assert_eq!(
        format_temperature_value(Some(72.0), Some(22.0), Both, 0).unwrap(),
        "72°F (22°C)"
    );
    assert_eq!(
        format_temperature_value(Some(212.0), None, Both, 0).unwrap(),
        "212°F (100°C)"
    );
    assert_eq!(format_temperature_value(None, None, Both, 0), None);
    assert_eq!(
        format_temperature_value(None, Some(20.0), Fahrenheit, 0),
        None
    );
    assert_eq!(format_temperature_value(None, None, Celsius, 0), None);
    assert_eq!(format_temperature_value(None, Some(20.0), Both, 0), None);
}

#[test]
fn current_severe_risk_and_direction_descriptors() {
    assert_eq!(severe_risk_description(85), "Extreme");
    assert_eq!(severe_risk_description(60), "High");
    assert_eq!(severe_risk_description(40), "Moderate");
    assert_eq!(severe_risk_description(20), "Low");
    assert_eq!(severe_risk_description(5), "Minimal");
    assert_eq!(direction_descriptor(0.06, 0.02, 0.05), "rising ⬆⬆");
    assert_eq!(direction_descriptor(0.03, 0.02, 0.05), "rising ⬆");
    assert_eq!(direction_descriptor(-0.06, 0.02, 0.05), "falling ⬇⬇");
    assert_eq!(direction_descriptor(-0.03, 0.02, 0.05), "falling ⬇");
    assert_eq!(direction_descriptor(0.0, 0.02, 0.05), "steady →");
    assert_eq!(split_direction_descriptor("rising ⬆"), ("rising", "⬆"));
    assert_eq!(split_direction_descriptor("steady"), ("steady", ""));
    assert_eq!(split_direction_descriptor(""), ("steady", ""));
    assert_eq!(split_direction_descriptor("falling ⬇⬇"), ("falling", "⬇⬇"));
}

#[test]
fn current_describe_trend() {
    let mut t = TrendInsight {
        metric: "temperature".into(),
        direction: "rising".into(),
        change: Some(5.2),
        unit: Some("°F".into()),
        timeframe_hours: 24,
        summary: None,
        sparkline: None,
    };
    assert_eq!(describe_trend(&t), "Rising +5.2°F over 24h");
    t.change = None;
    assert_eq!(describe_trend(&t), "Rising over 24h");
    t.timeframe_hours = 12;
    assert_eq!(describe_trend(&t), "Rising over 12h");
    t.change = Some(1.0);
    t.unit = None;
    assert_eq!(describe_trend(&t), "Rising +1.0 over 12h");
    t.direction = String::new();
    assert_eq!(describe_trend(&t), "Steady +1.0 over 12h");
}

fn full_current() -> CurrentConditions {
    CurrentConditions {
        temperature_f: Some(72.0),
        temperature_c: Some(22.2),
        humidity: Some(55),
        wind_speed_mph: Some(10.0),
        wind_direction: Some("NW".into()),
        dewpoint_f: Some(50.0),
        dewpoint_c: Some(10.0),
        pressure_in: Some(30.01),
        visibility_miles: Some(10.0),
        uv_index: Some(5.0),
        condition: Some("Sunny".into()),
        ..Default::default()
    }
}

#[test]
fn current_basic_metrics_and_toggles() {
    let now = utc(2026, 2, 7, 12, 0);
    let loc = testville();
    let p = presenter(serde_json::json!({"temperature_unit": "f"}), now)
        .present_current(Some(&full_current()), &loc, None, &[], None, None)
        .unwrap();
    for l in [
        "Temperature",
        "Humidity",
        "Wind",
        "Dewpoint",
        "Pressure",
        "Visibility",
        "UV Index",
    ] {
        assert!(labels(&p).contains(&l), "{l}");
    }
    assert_eq!(metric(&p, "UV Index"), Some("5.0 (Moderate)"));

    let minimal = CurrentConditions {
        temperature_f: Some(72.0),
        temperature_c: Some(22.2),
        condition: Some("Sunny".into()),
        ..Default::default()
    };
    let p = presenter(
        serde_json::json!({"temperature_unit": "f", "round_values": true}),
        now,
    )
    .present_current(Some(&minimal), &loc, None, &[], None, None)
    .unwrap();
    assert_eq!(metric(&p, "Temperature"), Some("72°F"));
    assert!(p
        .metrics
        .iter()
        .all(|m| !m.label.to_lowercase().contains("feel")));
    assert!(p.metrics.iter().all(|m| m.value.to_lowercase() != "n/a"));

    let hidden = presenter(
        serde_json::json!({"show_dewpoint": false, "show_visibility": false, "show_uv_index": false}),
        now,
    )
    .present_current(Some(&full_current()), &loc, None, &[], None, None)
    .unwrap();
    for l in ["Dewpoint", "Visibility", "UV Index"] {
        assert!(!labels(&hidden).contains(&l), "{l}");
    }
}

#[test]
fn current_feels_like_rules() {
    // test_present_feels_like_still_displays_when_meaningfully_different
    let c = CurrentConditions {
        temperature_f: Some(81.0),
        temperature_c: Some(27.2),
        humidity: Some(36),
        feels_like_f: Some(85.0),
        feels_like_c: Some(29.4),
        ..Default::default()
    };
    let (t, _) = format_temperature_with_feels_like(&c, TemperatureUnit::Fahrenheit, 0);
    assert_eq!(t, "81°F (feels like 85°F)");
    // test_thermal_comfort_sanity: presentation cases
    let implausible = CurrentConditions {
        temperature_f: Some(81.0),
        humidity: Some(36),
        feels_like_f: Some(87.0),
        ..Default::default()
    };
    assert_eq!(
        format_temperature_with_feels_like(&implausible, TemperatureUnit::Fahrenheit, 1),
        ("81°F".to_string(), None)
    );
    let solar = CurrentConditions {
        feels_like_f: Some(85.0),
        ..implausible.clone()
    };
    assert_eq!(
        format_temperature_with_feels_like(&solar, TemperatureUnit::Fahrenheit, 1),
        ("81°F (feels like 85°F)".to_string(), None)
    );
    let humid = CurrentConditions {
        temperature_f: Some(90.0),
        temperature_c: Some(32.2),
        humidity: Some(70),
        feels_like_f: Some(106.0),
        feels_like_c: Some(41.1),
        heat_index_f: Some(106.0),
        heat_index_c: Some(41.1),
        ..Default::default()
    };
    assert_eq!(
        format_temperature_with_feels_like(&humid, TemperatureUnit::Fahrenheit, 1),
        (
            "90°F (feels like 106°F)".to_string(),
            Some("due to heat index".to_string())
        )
    );
}

#[test]
fn current_astronomical_environmental_and_seasonal() {
    let now = utc(2026, 2, 7, 12, 0);
    let loc = testville();
    let p = presenter(serde_json::json!({}), now);
    let c = CurrentConditions {
        temperature_f: Some(30.0),
        sunrise_time: Some(now),
        sunset_time: Some(now),
        moon_phase: Some("Full".into()),
        moonrise_time: Some(now),
        moonset_time: Some(now),
        ..Default::default()
    };
    let out = p
        .present_current(Some(&c), &loc, None, &[], None, None)
        .unwrap();
    for l in ["Sunrise", "Sunset", "Moon phase", "Moonrise", "Moonset"] {
        assert!(labels(&out).contains(&l), "{l}");
    }
    assert_eq!(metric(&out, "Sunrise"), Some("12:00 PM"));

    let env = EnvironmentalConditions {
        air_quality_index: Some(42.0),
        air_quality_category: Some("Good".into()),
        pollen_index: Some(3.0),
        pollen_category: Some("Low".into()),
        pollen_primary_allergen: Some("Oak".into()),
        ..Default::default()
    };
    let out = p
        .present_current(Some(&c), &loc, Some(&env), &[], None, None)
        .unwrap();
    assert_eq!(
        metric(&out, "Air Quality"),
        Some("AQI 42 (Good). Pollen: Low (Oak) | Advice: Air quality is satisfactory; enjoy normal outdoor activities.")
    );
    assert_eq!(metric(&out, "Pollen"), Some("3 (Low) – Oak"));
    let allergen_only = EnvironmentalConditions {
        pollen_primary_allergen: Some("Grass".into()),
        ..Default::default()
    };
    let out = p
        .present_current(Some(&c), &loc, Some(&allergen_only), &[], None, None)
        .unwrap();
    assert_eq!(metric(&out, "Pollen"), Some("Grass"));
    assert_eq!(metric(&out, "Air Quality"), None);

    let seasonal = CurrentConditions {
        temperature_f: Some(20.0),
        heat_index_f: Some(21.0),
        wind_chill_f: Some(18.0),
        snow_depth_in: Some(0.0),
        frost_risk: Some("None".into()),
        precipitation_type: Some(vec!["snow".into()]),
        condition: Some("Clear".into()),
        severe_weather_risk: Some(0),
        ..Default::default()
    };
    let out = p
        .present_current(Some(&seasonal), &loc, None, &[], None, None)
        .unwrap();
    for l in [
        "Snow on ground",
        "Wind chill",
        "Heat index",
        "Frost risk",
        "Precipitation type",
        "Severe weather risk",
    ] {
        assert!(!labels(&out).contains(&l), "{l}");
    }
}

#[test]
fn current_trends_and_pressure_outlook() {
    let now = utc(2026, 2, 7, 12, 0);
    let trends = vec![
        TrendInsight {
            metric: "temperature".into(),
            direction: "rising".into(),
            change: Some(5.0),
            unit: Some("°F".into()),
            timeframe_hours: 24,
            summary: None,
            sparkline: Some("▁▃▅".into()),
        },
        TrendInsight {
            metric: "pressure".into(),
            direction: "falling".into(),
            change: Some(-0.05),
            unit: Some("inHg".into()),
            timeframe_hours: 24,
            summary: Some("Pressure falling".into()),
            sparkline: None,
        },
        TrendInsight {
            metric: "daily_trend".into(),
            direction: "warmer".into(),
            change: None,
            unit: None,
            timeframe_hours: 24,
            summary: Some("Warmer than yesterday".into()),
            sparkline: None,
        },
    ];
    let c = full_current();
    let p = presenter(serde_json::json!({"temperature_unit": "c"}), now);
    let out = p
        .present_current(Some(&c), &testville(), None, &trends, None, None)
        .unwrap();
    assert_eq!(
        metric(&out, "Temperature trend"),
        Some("Temperature rising +2.8°C over 24h ▁▃▅")
    );
    assert_eq!(metric(&out, "Pressure outlook"), Some("Pressure falling"));
    assert!(!out.metrics.iter().any(|m| m.value.contains("yesterday")));
    let hidden = presenter(serde_json::json!({"show_pressure_trend": false}), now)
        .present_current(Some(&c), &testville(), None, &trends, None, None)
        .unwrap();
    assert!(!labels(&hidden).contains(&"Pressure outlook"));

    let lines = format_trend_lines(
        &trends,
        None,
        None,
        true,
        TemperatureUnit::Celsius,
        now.with_timezone(&Utc),
    );
    assert_eq!(
        lines,
        ["Temperature rising +2.8°C over 24h ▁▃▅", "Pressure falling"]
    );

    // compute_pressure_trend_from_hourly
    let base = CurrentConditions {
        pressure_in: Some(30.00),
        ..Default::default()
    };
    let hourly = HourlyForecast {
        periods: (0..6)
            .map(|i| HourlyForecastPeriod {
                pressure_in: Some(30.00 + 0.012 * f64::from(i)),
                ..hourly_period(now + Duration::hours(i64::from(i)))
            })
            .collect(),
        ..Default::default()
    };
    let (summary, value) =
        compute_pressure_trend_from_hourly(&base, Some(&hourly), now.with_timezone(&Utc)).unwrap();
    assert_eq!(summary, "Pressure rising ⬆⬆ +0.06 inHg over next 6h");
    assert_eq!(value, "Rising ⬆⬆ +0.06 inHg over next 6h");
    assert!(compute_pressure_trend_from_hourly(&base, None, now.with_timezone(&Utc)).is_none());
    let implausible = CurrentConditions {
        pressure_in: Some(29.0),
        ..Default::default()
    };
    assert!(compute_pressure_trend_from_hourly(
        &implausible,
        Some(&hourly),
        now.with_timezone(&Utc)
    )
    .is_none());
}

#[test]
fn current_fog_alert_moves_visibility_first() {
    let now = utc(2026, 2, 7, 12, 0);
    let mut fog = WeatherAlert::new("Dense Fog Advisory", "");
    fog.event = Some("Dense Fog Advisory".into());
    let alerts = WeatherAlerts { alerts: vec![fog] };
    let p = presenter(serde_json::json!({"severe_weather_override": true}), now)
        .present_current(
            Some(&full_current()),
            &testville(),
            None,
            &[],
            None,
            Some(&alerts),
        )
        .unwrap();
    assert_eq!(p.metrics[0].label, "Visibility");
    assert!(p
        .fallback_text
        .lines()
        .nth(1)
        .unwrap()
        .starts_with("Visibility: "));
}

#[test]
fn current_minutely_outlook_goes_first() {
    let now = utc(2026, 2, 7, 12, 0);
    let data = WeatherData {
        location: testville(),
        current: Some(full_current()),
        minutely_precipitation: Some(MinutelyPrecipitationForecast {
            summary: Some("Rain starting in 12 min.".into()),
            ..Default::default()
        }),
        ..Default::default()
    };
    let p = presenter(serde_json::json!({}), now).present(&data);
    let cc = p.current_conditions.unwrap();
    assert_eq!(cc.metrics[0].label, "Precipitation outlook");
    assert_eq!(cc.metrics[0].value, "Rain starting in 12 min.");
}

// ---------------------------------------------------------------------------
// test_hourly_forecast_presentation.py / test_forecast_time_reference.py
// ---------------------------------------------------------------------------

fn today_forecast() -> Forecast {
    Forecast {
        periods: vec![ForecastPeriod {
            name: "Today".into(),
            temperature: Some(70.0),
            temperature_low: Some(54.0),
            short_forecast: Some("Sunny".into()),
            ..Default::default()
        }],
        ..Default::default()
    }
}

#[test]
fn hourly_summary_shows_humidity_and_dewpoint() {
    let start = utc(2026, 3, 19, 12, 0);
    let hourly = HourlyForecast {
        periods: vec![HourlyForecastPeriod {
            temperature: Some(72.0),
            short_forecast: Some("Partly Cloudy".into()),
            humidity: Some(55),
            dewpoint_f: Some(54.0),
            wind_speed: Some("8 mph".into()),
            wind_direction: Some("S".into()),
            ..hourly_period(start)
        }],
        ..Default::default()
    };
    let out = presenter(
        serde_json::json!({"temperature_unit": "f", "hourly_forecast_hours": 1}),
        start,
    )
    .present_forecast(
        Some(&today_forecast()),
        &testville(),
        Some(&hourly),
        None,
        None,
        None,
    )
    .unwrap();
    assert_eq!(out.hourly_periods[0].humidity.as_deref(), Some("55%"));
    assert_eq!(out.hourly_periods[0].dewpoint.as_deref(), Some("54°F"));
    let text = render_hourly_fallback(&out.hourly_periods, 1);
    assert!(
        text.contains("Humidity 55%") && text.contains("Dewpoint 54°F"),
        "{text}"
    );
    assert_eq!(build_hourly_section_text(&[], 6, None), "");
}

#[test]
fn forecast_sections_and_generated_time() {
    let start = utc(2026, 3, 19, 12, 0);
    let mut forecast = today_forecast();
    forecast.summary = Some("Dry and pleasant through tomorrow.".into());
    let hourly = HourlyForecast {
        periods: vec![HourlyForecastPeriod {
            temperature: Some(72.0),
            short_forecast: Some("Sunny".into()),
            ..hourly_period(start)
        }],
        summary: Some("Clear through mid afternoon.".into()),
        ..Default::default()
    };
    let out = presenter(serde_json::json!({"hourly_forecast_hours": 1}), start)
        .present_forecast(
            Some(&forecast),
            &testville(),
            Some(&hourly),
            None,
            None,
            None,
        )
        .unwrap();
    assert!(out
        .daily_section_text
        .starts_with("Daily forecast for Testville:"));
    assert!(out
        .daily_section_text
        .contains("Overall: Dry and pleasant through tomorrow."));
    assert!(out.hourly_section_text.starts_with("Hourly forecast:"));
    assert!(out
        .hourly_section_text
        .contains("Hourly outlook: Clear through mid afternoon."));
    assert!(out.hourly_section_text.contains("Next 1 Hours:"));
    assert_eq!(
        out.fallback_text,
        format!("{}\n\n{}", out.daily_section_text, out.hourly_section_text)
    );

    let mut london = Location::new("London", 51.5074, -0.1278);
    london.timezone = Some("Europe/London".into());
    let mut f = today_forecast();
    f.generated_at = Some(aw_core::model::PyTimestamp::Aware(utc(2026, 7, 1, 12, 0)));
    let out = presenter(serde_json::json!({"show_timezone_suffix": true}), start)
        .present_forecast(Some(&f), &london, None, None, None, None)
        .unwrap();
    assert_eq!(out.generated_at.as_deref(), Some("1:00 PM BST"));
    assert!(out
        .daily_section_text
        .contains("Forecast generated: 1:00 PM BST"));

    // Hourly fixed offsets are shown in the location's zone.
    let plus_one = FixedOffset::east_opt(3600).unwrap();
    let hourly = HourlyForecast {
        periods: vec![HourlyForecastPeriod {
            temperature: Some(72.0),
            ..hourly_period(plus_one.with_ymd_and_hms(2026, 7, 1, 13, 0, 0).unwrap())
        }],
        ..Default::default()
    };
    let out = presenter(
        serde_json::json!({"show_timezone_suffix": true, "hourly_forecast_hours": 1}),
        utc(2026, 7, 1, 12, 0),
    )
    .present_forecast(
        Some(&today_forecast()),
        &london,
        Some(&hourly),
        None,
        None,
        None,
    )
    .unwrap();
    assert_eq!(out.hourly_periods[0].time, "1:00 PM BST");
}

#[test]
fn forecast_marine_and_mobility_sections() {
    let start = utc(2026, 3, 19, 12, 0);
    let marine = MarineForecast {
        zone_id: Some("ANZ530".into()),
        zone_name: Some("Chesapeake Bay from Pooles Island to Sandy Point".into()),
        forecast_summary: Some("South winds 10 to 15 knots with waves 1 to 2 feet.".into()),
        highlights: vec![
            "South winds 10 to 15 knots".into(),
            "Waves 1 to 2 feet".into(),
        ],
        periods: vec![MarineForecastPeriod {
            name: "Tonight".into(),
            summary: "South winds 10 to 15 knots with waves 1 to 2 feet.".into(),
        }],
        ..Default::default()
    };
    let annapolis = Location::new("Annapolis", 38.9784, -76.4922);
    let out = presenter(serde_json::json!({}), start)
        .present_forecast(
            Some(&today_forecast()),
            &annapolis,
            None,
            Some(&marine),
            None,
            None,
        )
        .unwrap();
    assert_eq!(out.marine_summary, marine.forecast_summary);
    assert_eq!(out.marine_highlights, marine.highlights);
    assert!(out
        .marine_section_text
        .contains("Marine conditions for Annapolis:"));
    assert!(out
        .marine_section_text
        .contains("Marine zone: Chesapeake Bay from Pooles Island to Sandy Point (ANZ530)"));
    assert!(out
        .marine_section_text
        .contains("Wind and wave highlights:"));
    assert_eq!(
        out.fallback_text,
        format!("{}\n\n{}", out.daily_section_text, out.marine_section_text)
    );

    let hourly = HourlyForecast {
        periods: vec![HourlyForecastPeriod {
            temperature: Some(72.0),
            short_forecast: Some("Sunny".into()),
            ..hourly_period(start)
        }],
        ..Default::default()
    };
    let out = presenter(serde_json::json!({"hourly_forecast_hours": 1}), start)
        .present_forecast(
            Some(&today_forecast()),
            &testville(),
            Some(&hourly),
            None,
            None,
            Some("Dry for 30 minutes, then rain likely."),
        )
        .unwrap();
    assert_eq!(
        out.mobility_briefing.as_deref(),
        Some("Dry for 30 minutes, then rain likely.")
    );
    assert!(out
        .hourly_section_text
        .starts_with("Hourly forecast:\nMobility briefing: Dry for 30 minutes, then rain likely."));
}

#[test]
fn forecast_time_reference() {
    let clock = Clock::fixed(Utc::now(), chrono_tz::UTC);
    let minus_eight = FixedOffset::west_opt(8 * 3600).unwrap();
    let start = PyDateTime::aware(
        minus_eight.with_ymd_and_hms(2026, 2, 10, 9, 0, 0).unwrap(),
        None,
    );
    assert_eq!(
        resolve_forecast_display_time(&start, "location", None, &clock),
        start
    );
    let local = resolve_forecast_display_time(&start, "user_local", None, &clock);
    assert_eq!(
        local.dt,
        Utc.with_ymd_and_hms(2026, 2, 10, 17, 0, 0).unwrap()
    );
    assert_eq!(local.dt.offset().local_minus_utc(), 0);
    let naive = PyDateTime::naive(
        NaiveDate::from_ymd_opt(2026, 2, 10)
            .unwrap()
            .and_hms_opt(9, 0, 0)
            .unwrap(),
    );
    assert_eq!(
        resolve_forecast_display_time(&naive, "user_local", None, &clock),
        naive
    );
}

// ---------------------------------------------------------------------------
// test_forecast_confidence_presentation.py
// ---------------------------------------------------------------------------

fn confidence(level: ForecastConfidenceLevel, rationale: &str) -> ForecastConfidence {
    ForecastConfidence {
        level,
        rationale: rationale.into(),
        sources_compared: 2,
        source_names: vec![],
    }
}

#[test]
fn forecast_confidence_labels() {
    let now = utc(2026, 3, 19, 12, 0);
    let p = presenter(serde_json::json!({}), now);
    let loc = testville();
    let none = p
        .present_forecast(Some(&today_forecast()), &loc, None, None, None, None)
        .unwrap();
    assert_eq!(none.confidence_label, None);
    assert!(!none.fallback_text.contains("Forecast confidence"));
    for (level, label, rationale) in [
        (
            ForecastConfidenceLevel::High,
            "High",
            "Sources agree on temperature and precipitation",
        ),
        (
            ForecastConfidenceLevel::Medium,
            "Moderate",
            "Only a single forecast source is available.",
        ),
        (
            ForecastConfidenceLevel::Low,
            "Low",
            "Significant disagreement between sources.",
        ),
    ] {
        let c = confidence(level, rationale);
        let out = p
            .present_forecast(Some(&today_forecast()), &loc, None, None, Some(&c), None)
            .unwrap();
        assert_eq!(out.confidence_label, Some(format!("Confidence: {label}")));
        let line = format!(
            "Forecast confidence: {label}. {}.",
            rationale.trim_end_matches('.')
        );
        assert!(out.fallback_text.contains(&line), "{}", out.fallback_text);
    }
    let data = WeatherData {
        location: loc.clone(),
        forecast: Some(today_forecast()),
        forecast_confidence: Some(confidence(ForecastConfidenceLevel::High, "Agree")),
        ..Default::default()
    };
    assert_eq!(
        p.present(&data)
            .forecast
            .unwrap()
            .confidence_label
            .as_deref(),
        Some("Confidence: High")
    );
}

#[test]
fn forecast_duration_windows() {
    let now = utc(2026, 2, 27, 0, 0);
    let daily = Forecast {
        periods: (1..20)
            .map(|i| ForecastPeriod {
                name: format!("Day {i}"),
                temperature: Some(70.0 + f64::from(i)),
                short_forecast: Some("Clear".into()),
                ..Default::default()
            })
            .collect(),
        ..Default::default()
    };
    let london = Location::new("London", 51.5074, -0.1278).with_country("GB");
    let count = |days: i64, f: &Forecast| {
        presenter(serde_json::json!({"forecast_duration_days": days}), now)
            .present_forecast(Some(f), &london, None, None, None, None)
            .unwrap()
            .periods
            .len()
    };
    assert_eq!(count(10, &daily), 10);
    assert_eq!(count(15, &daily), 15);

    let half_days = Forecast {
        periods: (0..14)
            .map(|i| ForecastPeriod {
                name: if i % 2 == 1 {
                    format!("Night {}", i / 2 + 1)
                } else {
                    format!("Period {}", i + 1)
                },
                temperature: Some(60.0 + f64::from(i)),
                ..Default::default()
            })
            .collect(),
        ..Default::default()
    };
    assert_eq!(count(7, &half_days), 14);

    let start = utc(2026, 2, 27, 0, 0);
    let mut periods: Vec<ForecastPeriod> = (0..14)
        .map(|i| ForecastPeriod {
            name: format!("NWS {}", i + 1),
            start_time: Some(start + Duration::hours(12 * i)),
            temperature: Some(50.0),
            ..Default::default()
        })
        .collect();
    periods.extend((7..16).map(|i| ForecastPeriod {
        name: format!("OM Day {}", i + 1),
        start_time: Some(start + Duration::days(i) + Duration::hours(12)),
        temperature: Some(60.0),
        ..Default::default()
    }));
    assert_eq!(
        count(
            15,
            &Forecast {
                periods,
                ..Default::default()
            }
        ),
        22
    );
}

// ---------------------------------------------------------------------------
// test_presentation_formatters.py
// ---------------------------------------------------------------------------

#[test]
fn formatter_display_time_and_winds() {
    let t = PyDateTime::aware(utc(2026, 1, 20, 18, 0), None);
    assert_eq!(format_display_time(Some(&t), "local", false, true), "18:00");
    let naive = PyDateTime::naive(
        NaiveDate::from_ymd_opt(2026, 1, 20)
            .unwrap()
            .and_hms_opt(9, 30, 0)
            .unwrap(),
    );
    assert_eq!(
        format_display_time(Some(&naive), "local", false, true),
        "09:30"
    );

    let hourly = |dir: Option<&str>, speed: Option<&str>, mph: Option<f64>| HourlyForecastPeriod {
        wind_direction: dir.map(str::to_string),
        wind_speed: speed.map(str::to_string),
        wind_speed_mph: mph,
        ..hourly_period(utc(2026, 3, 27, 12, 0))
    };
    let c = format_hourly_wind(
        &hourly(Some("SW"), None, Some(10.0)),
        TemperatureUnit::Celsius,
        None,
    )
    .unwrap();
    assert!(c.contains("km/h") && !c.contains("mph"), "{c}");
    assert!(format_hourly_wind(
        &hourly(Some("SW"), None, Some(14.0)),
        TemperatureUnit::Fahrenheit,
        None
    )
    .unwrap()
    .contains("mph"));
    assert_eq!(
        format_hourly_wind(
            &hourly(Some("SW"), Some("12 mph"), None),
            TemperatureUnit::Celsius,
            None
        )
        .unwrap(),
        "SW at 12 mph"
    );
    assert_eq!(
        format_hourly_wind(
            &hourly(Some("SW"), None, None),
            TemperatureUnit::Fahrenheit,
            None
        ),
        None
    );
    assert_eq!(
        format_hourly_wind(
            &hourly(None, None, Some(10.0)),
            TemperatureUnit::Fahrenheit,
            None
        ),
        None
    );

    let period = |dir: Option<&str>, speed: Option<&str>, mph: Option<f64>| ForecastPeriod {
        name: "Tonight".into(),
        wind_direction: dir.map(str::to_string),
        wind_speed: speed.map(str::to_string),
        wind_speed_mph: mph,
        ..Default::default()
    };
    let f = format_period_wind(
        &period(Some("SE"), Some("15 mph (24 km/h)"), Some(15.0)),
        TemperatureUnit::Fahrenheit,
        None,
    )
    .unwrap();
    assert!(f.contains("mph") && !f.contains("km/h"), "{f}");
    let c = format_period_wind(
        &period(Some("SE"), Some("15 mph (24 km/h)"), Some(15.0)),
        TemperatureUnit::Celsius,
        None,
    )
    .unwrap();
    assert!(c.contains("km/h") && !c.contains("mph"), "{c}");
    assert_eq!(
        format_period_wind(
            &period(Some("SE"), Some("15 mph"), None),
            TemperatureUnit::Celsius,
            None
        )
        .unwrap(),
        "SE 15 mph"
    );
    assert!(format_period_wind(
        &period(Some("SE"), None, Some(20.0)),
        TemperatureUnit::Fahrenheit,
        None
    )
    .unwrap()
    .starts_with("SE"));
    assert_eq!(
        format_period_wind(&period(None, None, None), TemperatureUnit::Fahrenheit, None),
        None
    );
}

// ---------------------------------------------------------------------------
// test_formatters_date.py
// ---------------------------------------------------------------------------

#[test]
fn date_and_datetime_styles() {
    let at = |h, m| {
        PyDateTime::naive(
            NaiveDate::from_ymd_opt(2026, 4, 18)
                .unwrap()
                .and_hms_opt(h, m, 0)
                .unwrap(),
        )
    };
    let fixed = at(14, 5);
    for (style, expected) in [
        ("iso", "2026-04-18"),
        ("us_short", "04/18/2026"),
        ("us_long", "April 18, 2026"),
        ("eu", "18/04/2026"),
        ("not-a-real-style", "2026-04-18"),
    ] {
        assert_eq!(format_date(Some(&fixed), style), expected);
    }
    assert_eq!(format_date(None, "iso"), "");
    assert_eq!(
        format_datetime(Some(&fixed), "us_long", true),
        "April 18, 2026 2:05 PM"
    );
    assert_eq!(
        format_datetime(Some(&fixed), "iso", false),
        "2026-04-18 14:05"
    );
    assert_eq!(
        format_datetime(Some(&fixed), "us_short", false),
        "04/18/2026 14:05"
    );
    assert_eq!(
        format_datetime(Some(&at(9, 7)), "iso", true),
        "2026-04-18 9:07 AM"
    );
    assert_eq!(
        format_datetime(Some(&at(9, 7)), "iso", false),
        "2026-04-18 09:07"
    );
    assert_eq!(
        format_datetime(Some(&at(0, 0)), "iso", false),
        "2026-04-18 00:00"
    );
    assert_eq!(
        format_datetime(Some(&at(0, 0)), "iso", true),
        "2026-04-18 12:00 AM"
    );
    assert_eq!(
        format_datetime(Some(&at(12, 0)), "iso", true),
        "2026-04-18 12:00 PM"
    );
    assert_eq!(
        format_datetime(Some(&at(10, 5)), "iso", true),
        "2026-04-18 10:05 AM"
    );
    assert_eq!(format_datetime(None, "iso", true), "");
    let aware = PyDateTime::aware(utc(2026, 4, 18, 14, 5), None);
    assert_eq!(
        format_datetime(Some(&aware), "iso", false),
        "2026-04-18 14:05"
    );
}

// ---------------------------------------------------------------------------
// test_format_string_parser.py / test_alert_placeholder.py
// ---------------------------------------------------------------------------

#[test]
fn format_string_parser() {
    assert!(tray::get_placeholders("plain text").is_empty());
    assert_eq!(
        tray::get_placeholders("{temp} and {humidity}"),
        ["temp", "humidity"]
    );
    assert!(tray::validate_format_string("").is_ok());
    assert!(tray::validate_format_string("{temp} - {condition}").is_ok());
    assert!(tray::validate_format_string("{bogus}")
        .unwrap_err()
        .contains("bogus"));
    assert!(tray::validate_format_string("{temp")
        .unwrap_err()
        .contains("Unbalanced"));
    assert!(tray::validate_format_string("{alert}").is_ok());
    let data = |pairs: &[(&str, &str)]| {
        pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect()
    };
    assert_eq!(
        tray::format_string(
            "{temp}, {condition}",
            &data(&[("temp", "72°F"), ("condition", "Sunny")])
        ),
        "72°F, Sunny"
    );
    assert_eq!(tray::format_string("{temp}", &data(&[])), "{temp}");
    assert_eq!(tray::format_string("", &data(&[("temp", "72")])), "");
    assert!(tray::format_string("{temp", &data(&[("temp", "72")])).contains("Error"));
    assert_eq!(
        tray::format_string("{humidity}%", &data(&[("humidity", "65")])),
        "65%"
    );
    let help = tray::supported_placeholders_help();
    assert!(help.contains("Supported Placeholders") && help.contains("{alert}"));
}

// ---------------------------------------------------------------------------
// test_system_tray.py, test_alert_placeholder.py, test_round_values_setting.py
// ---------------------------------------------------------------------------

fn tray_data(current: CurrentConditions) -> WeatherData {
    WeatherData {
        location: Location::new("Test City", 40.0, -74.0),
        current: Some(current),
        ..Default::default()
    }
}

fn updater(fmt: &str, unit: &str) -> TaskbarIconUpdater {
    TaskbarIconUpdater {
        text_enabled: true,
        format_string: fmt.into(),
        temperature_unit: unit.into(),
        ..Default::default()
    }
}

fn sunny() -> CurrentConditions {
    CurrentConditions {
        temperature_f: Some(72.0),
        temperature_c: Some(22.2),
        condition: Some("Sunny".into()),
        ..Default::default()
    }
}

#[test]
fn tray_basic_tooltips() {
    let now = Utc::now();
    let data = tray_data(sunny());
    assert_eq!(
        updater("{location}: {temp}", "f").format_tooltip(Some(&data), Some("Test City"), now),
        "Test City: 72F"
    );
    assert_eq!(
        updater("{temp}", "f").format_tooltip(None, None, now),
        DEFAULT_TOOLTIP_TEXT
    );
    let mut off = updater("{temp}", "f");
    off.text_enabled = false;
    assert_eq!(
        off.format_tooltip(Some(&data), None, now),
        DEFAULT_TOOLTIP_TEXT
    );
    assert_eq!(
        updater("{location}: {temp}", "both").build_preview(
            "{location}: {temp} | {condition}",
            None,
            None,
            now
        ),
        "Sample Location: 72F/22C | Partly Cloudy"
    );
    assert_eq!(
        updater("{temp} {nope}", "f").format_tooltip(Some(&data), None, now),
        "72F {nope}"
    );
    let long = updater(&"{condition} ".repeat(40), "f").format_tooltip(Some(&data), None, now);
    assert_eq!(long.chars().count(), 127);
    assert!(long.ends_with("..."));
}

#[test]
fn tray_unit_aware_placeholders() {
    let now = Utc::now();
    let current = CurrentConditions {
        temperature_f: Some(72.0),
        temperature_c: Some(22.2),
        condition: Some("Partly Cloudy".into()),
        wind_speed_mph: Some(10.0),
        wind_speed_kph: Some(16.1),
        wind_direction: Some("NW".into()),
        pressure_in: Some(30.05),
        pressure_mb: Some(1017.0),
        visibility_miles: Some(10.0),
        visibility_km: Some(16.1),
        precipitation_in: Some(1.0),
        precipitation_mm: Some(25.4),
        ..Default::default()
    };
    let forecast = Forecast {
        periods: vec![
            ForecastPeriod {
                name: "Today".into(),
                temperature: Some(75.0),
                ..Default::default()
            },
            ForecastPeriod {
                name: "Tonight".into(),
                temperature: Some(55.0),
                ..Default::default()
            },
        ],
        ..Default::default()
    };
    let fmt = "{wind_speed} | {pressure} | {visibility} | {precip} | {high} | {low}";
    for (unit, country, expected) in [
        ("f", "US", "10.0 mph | 30.05 inHg | 10.0 mi | 1.00 in | 75F | 55F"),
        ("c", "US", "16.1 km/h | 1017.00 hPa | 16.1 km | 25.40 mm | 24C | 13C"),
        ("both", "US", "10.0 mph (16.1 km/h) | 30.05 inHg (1017.00 hPa) | 10.0 mi (16.1 km) | 1.00 in (25.40 mm) | 75F/24C | 55F/13C"),
        ("auto", "GB", "10.0 mph | 1017.00 hPa | 10.0 mi | 25.40 mm | 24C | 13C"),
        ("auto", "CA", "16.1 km/h | 101.70 kPa | 16.1 km | 25.40 mm | 24C | 13C"),
        ("auto", "FR", "4.5 m/s | 1017.00 hPa | 16.1 km | 25.40 mm | 24C | 13C"),
    ] {
        let mut data = tray_data(current.clone());
        data.forecast = Some(forecast.clone());
        data.location = data.location.with_country(country);
        assert_eq!(updater(fmt, unit).format_tooltip(Some(&data), Some("Test City"), now), expected, "{unit} {country}");
    }
    let data = tray_data(current);
    assert_eq!(
        updater("{temp_f} / {temp_c}", "c").format_tooltip(Some(&data), None, now),
        "72F / 22C"
    );
    assert_eq!(
        updater("{high} / {low}", "f").format_tooltip(Some(&tray_data(sunny())), None, now),
        "N/A / N/A"
    );
}

#[test]
fn tray_feels_like_fragments() {
    let now = Utc::now();
    let with = |f: Option<f64>, c: Option<f64>| {
        tray_data(CurrentConditions {
            feels_like_f: f,
            feels_like_c: c,
            ..sunny()
        })
    };
    for (unit, data, expected) in [
        ("f", with(None, Some(20.0)), "68F"),
        ("c", with(Some(68.0), None), "20C"),
        ("both", with(None, Some(20.0)), "68F/20C"),
        ("both", with(Some(68.0), None), "68F/20C"),
    ] {
        assert_eq!(
            updater("{feels_like}", unit).format_tooltip(Some(&data), None, now),
            expected
        );
    }
    let none = with(None, None);
    assert_eq!(
        updater("{temp} (feels {feels_like}) • {condition}", "f").format_tooltip(
            Some(&none),
            None,
            now
        ),
        "72F • Sunny"
    );
    assert_eq!(
        updater("{temp} | Heat index: {feels_like} | {condition}", "f").format_tooltip(
            Some(&none),
            None,
            now
        ),
        "72F Sunny"
    );
    assert_eq!(
        updater("{temp} (feels {feels_like}) • {condition}", "f").format_tooltip(
            Some(&with(Some(68.0), None)),
            None,
            now
        ),
        "72F (feels 68F) • Sunny"
    );
}

#[test]
fn tray_precip_and_alert_placeholders() {
    let now = Utc.with_ymd_and_hms(2026, 5, 1, 12, 0, 0).unwrap();
    let with_hourly = |current: CurrentConditions| {
        let mut d = tray_data(current);
        d.hourly_forecast = Some(HourlyForecast {
            periods: vec![HourlyForecastPeriod {
                precipitation_probability: Some(40.0),
                precipitation_amount: Some(0.1),
                ..hourly_period(now.fixed_offset())
            }],
            ..Default::default()
        });
        d
    };
    let u = updater("", "f");
    let vars = u.extract_weather_variables(
        &with_hourly(CurrentConditions {
            temperature_f: Some(72.0),
            ..Default::default()
        }),
        Some("Test City"),
        now,
    );
    assert_eq!(vars["precip_chance"], "40");
    assert_ne!(vars["precip"], "N/A");
    let vars = u.extract_weather_variables(
        &with_hourly(CurrentConditions {
            temperature_f: Some(72.0),
            precipitation_in: Some(0.25),
            ..Default::default()
        }),
        None,
        now,
    );
    assert!(vars["precip"].contains("0.25"));
    let vars = u.extract_weather_variables(
        &tray_data(CurrentConditions {
            temperature_f: Some(72.0),
            ..Default::default()
        }),
        None,
        now,
    );
    assert_eq!(
        (vars["precip"].as_str(), vars["precip_chance"].as_str()),
        ("N/A", "N/A")
    );
    assert_eq!(vars["alert"], "");

    let alert = |title: &str, event: Option<&str>, severity: &str| {
        let mut a = WeatherAlert::new(title, "");
        a.event = event.map(str::to_string);
        a.severity = severity.into();
        a
    };
    let mut d = tray_data(sunny());
    d.alerts = Some(WeatherAlerts {
        alerts: vec![
            alert("Wind Advisory", Some("Wind Advisory"), "Moderate"),
            alert("Tornado Warning", Some("Tornado Warning"), "Extreme"),
            alert("Flood Watch", Some("Flood Watch"), "Extreme"),
            alert("Title only", None, "Unknown"),
        ],
    });
    assert_eq!(
        updater("{temp} {alert}", "f").format_tooltip(Some(&d), None, now),
        "72F Tornado Warning"
    );
    d.alerts = Some(WeatherAlerts {
        alerts: vec![alert("Title only", None, "Minor")],
    });
    assert_eq!(
        updater("{alert}", "f").format_tooltip(Some(&d), None, now),
        "Title only"
    );
}

#[test]
fn tray_round_values() {
    let now = Utc::now();
    let data = tray_data(CurrentConditions {
        wind_speed_mph: Some(10.4),
        pressure_in: Some(30.12),
        visibility_miles: Some(9.6),
        ..sunny()
    });
    let mut u = updater("{wind_speed} {pressure} {visibility}", "f");
    assert_eq!(
        u.format_tooltip(Some(&data), None, now),
        "10.4 mph 30.12 inHg 9.6 mi"
    );
    u.round_values = true;
    assert_eq!(
        u.format_tooltip(Some(&data), None, now),
        "10 mph 30 inHg 10 mi"
    );
    let mut canada = data.clone();
    canada.location = canada.location.with_country("CA");
    let u = updater("{pressure}", "auto");
    assert_eq!(u.format_tooltip(Some(&canada), None, now), "102.00 kPa");
}

// ---------------------------------------------------------------------------
// test_alert_lifecycle_presentation.py
// ---------------------------------------------------------------------------

fn tornado() -> WeatherAlert {
    let mut a = WeatherAlert::new("Tornado Warning", "Take shelter now.");
    a.event = Some("Tornado Warning".into());
    a.severity = "Extreme".into();
    a.id = Some("alert-1".into());
    a
}

fn change(kind: AlertChangeKind) -> AlertChange {
    AlertChange {
        kind,
        alert: None,
        alert_id: "x".into(),
        title: "x".into(),
        old_severity: None,
        new_severity: None,
    }
}

#[test]
fn alert_lifecycle_summaries_and_labels() {
    let now = Utc::now();
    let s = AppSettings::default();
    let alerts = WeatherAlerts {
        alerts: vec![tornado()],
    };
    let plain = build_alerts(&alerts, "Here", &s, None, None, None, now);
    assert_eq!(plain.change_summary, None);
    assert!(!plain.fallback_text.starts_with("Alert changes:"));

    let diff = AlertLifecycleDiff {
        updated_alerts: vec![change(AlertChangeKind::Updated)],
        summary: "1 updated".into(),
        ..Default::default()
    };
    let out = build_alerts(&alerts, "Here", &s, None, Some(&diff), None, now);
    assert_eq!(out.change_summary.as_deref(), Some("1 updated"));
    assert!(out.fallback_text.starts_with("Alert changes: 1 updated"));
    assert!(out.fallback_text.contains("Tornado Warning"));

    let unchanged = AlertLifecycleDiff::default();
    let out = build_alerts(&alerts, "Here", &s, None, Some(&unchanged), None, now);
    assert_eq!(out.change_summary, None);

    let empty = build_alerts(
        &WeatherAlerts::default(),
        "Here",
        &s,
        None,
        Some(&diff),
        None,
        now,
    );
    assert!(empty.fallback_text.contains("No active weather alerts"));
    assert_eq!(empty.change_summary, None);

    let mut pw = WeatherAlert::new("Wind warning", "Strong winds.");
    pw.source = Some("PirateWeather".into());
    pw.areas = vec!["New York".into(), "Hudson Valley".into()];
    let out = build_alerts(
        &WeatherAlerts { alerts: vec![pw] },
        "Here",
        &s,
        None,
        None,
        None,
        now,
    );
    assert!(out
        .fallback_text
        .contains("Regions: New York, Hudson Valley"));
    assert!(!out.fallback_text.contains("Areas:"));
    assert!(out
        .fallback_text
        .contains("may not match your exact county or zone"));

    let mut other = tornado();
    other.id = Some("alert-2".into());
    other.title = "Flood Watch".into();
    let two = WeatherAlerts {
        alerts: vec![tornado(), other],
    };
    let states: HashMap<String, String> = [("alert-1".to_string(), "Extended".to_string())].into();
    let out = build_alerts(&two, "Here", &s, None, None, Some(&states), now);
    assert_eq!(out.fallback_text.matches("(Extended)").count(), 1);
    assert!(out
        .fallback_text
        .contains("Alert 1: Tornado Warning (Extended)"));
    let unknown: HashMap<String, String> = [("nope".to_string(), "New".to_string())].into();
    let out = build_alerts(&two, "Here", &s, None, None, Some(&unknown), now);
    assert!(!out.fallback_text.contains("(New)"));
}

// ---------------------------------------------------------------------------
// test_presentation_environmental.py
// ---------------------------------------------------------------------------

#[test]
fn environmental_panel() {
    let s = AppSettings::default();
    assert!(
        build_air_quality_panel("Here", &EnvironmentalConditions::default(), &s, None).is_none()
    );
    let basic = EnvironmentalConditions {
        air_quality_index: Some(42.0),
        air_quality_category: Some("Good".into()),
        air_quality_pollutant: Some("PM2_5".into()),
        ..Default::default()
    };
    let p = build_air_quality_panel("Here", &basic, &s, None).unwrap();
    assert_eq!(p.title, "Air quality for Here");
    assert_eq!(p.summary, "AQI 42 (Good) – Dominant pollutant: PM2.5");
    let category_only = EnvironmentalConditions {
        air_quality_category: Some("Moderate".into()),
        ..Default::default()
    };
    assert_eq!(
        build_air_quality_panel("Here", &category_only, &s, None)
            .unwrap()
            .summary,
        "Moderate"
    );
    let with_time = EnvironmentalConditions {
        updated_at: Some(utc(2026, 1, 15, 14, 30)),
        ..basic.clone()
    };
    let p = build_air_quality_panel("Here", &with_time, &s, None).unwrap();
    assert_eq!(p.updated_at.as_deref(), Some("Updated Jan 15 2:30 PM"));
    let all = EnvironmentalConditions {
        pollen_tree_index: Some(5.0),
        pollen_grass_index: Some(3.0),
        pollen_weed_index: Some(1.0),
        ..Default::default()
    };
    assert_eq!(
        format_pollen_details(&all).as_deref(),
        Some("Pollen Levels: Tree: 5, Grass: 3, Weed: 1")
    );
    assert_eq!(
        format_pollen_details(&EnvironmentalConditions::default()),
        None
    );
}

// ---------------------------------------------------------------------------
// test_impact_summary.py / test_show_impact_summaries_setting.py
// ---------------------------------------------------------------------------

#[test]
fn impact_rules() {
    let current = |f: fn(&mut CurrentConditions)| {
        let mut c = CurrentConditions::default();
        f(&mut c);
        build_impact_summary(Some(&c), None)
    };
    for (temp, band) in [
        (-10.0, "Dangerous cold"),
        (0.0, "Extreme cold"),
        (20.0, "Very cold"),
        (32.0, "Cool"),
        (55.0, "Mild"),
        (70.0, "Comfortable"),
        (80.0, "Warm"),
        (90.0, "Hot"),
        (100.0, "Very hot"),
        (110.0, "Extreme heat"),
    ] {
        let c = CurrentConditions {
            temperature_f: Some(temp),
            ..Default::default()
        };
        let s = build_impact_summary(Some(&c), None);
        assert!(s.outdoor.as_deref().unwrap().starts_with(band), "{temp}");
    }
    assert_eq!(current(|c| c.uv_index = Some(8.0)).outdoor, None);
    let s = current(|c| {
        c.temperature_f = Some(70.0);
        c.uv_index = Some(6.0);
    });
    assert!(s.outdoor.unwrap().ends_with("; wear sunscreen"));
    assert_eq!(build_impact_summary(None, None), Default::default());
    let s = current(|c| {
        c.visibility_miles = Some(0.25);
        c.wind_gust_mph = Some(45.0);
        c.wind_speed_mph = Some(10.0);
    });
    assert_eq!(
        s.driving.unwrap(),
        "Caution: very low visibility - drive with extreme caution; dangerous winds - high-profile vehicles at serious risk"
    );
    let s = current(|c| {
        c.precipitation_type = Some(vec!["ice".into()]);
        c.condition = Some("Snow".into());
        c.temperature_f = Some(30.0);
    });
    assert_eq!(
        s.driving.unwrap(),
        "Caution: ice possible - slow down, allow extra stopping distance"
    );
    let env = EnvironmentalConditions {
        pollen_category: Some("Moderate".into()),
        air_quality_category: Some("Unhealthy for Sensitive Groups".into()),
        ..Default::default()
    };
    let c = CurrentConditions {
        wind_speed_mph: Some(15.0),
        ..Default::default()
    };
    assert_eq!(
        build_impact_summary(Some(&c), Some(&env)).allergy.unwrap(),
        "Moderate pollen - sensitive individuals may experience symptoms; wind increasing pollen dispersion; air quality unhealthy for sensitive groups"
    );
    let period = ForecastPeriod {
        name: "Tonight".into(),
        temperature: Some(28.0),
        short_forecast: Some("Heavy Snow".into()),
        wind_speed: Some("10 to 50 mph".into()),
        pollen_forecast: Some("High".into()),
        ..Default::default()
    };
    let s = build_forecast_impact_summary(&period);
    assert_eq!(
        s.outdoor.unwrap(),
        "Cold - wear a heavy coat; active precipitation - bring appropriate gear"
    );
    assert_eq!(
        s.driving.unwrap(),
        "Caution: snow on roads - reduce speed and increase following distance; near-freezing temperatures - watch for black ice; dangerous winds - high-profile vehicles at serious risk"
    );
    assert_eq!(s.allergy.unwrap(), "High pollen - sensitive individuals should limit exposure; wind increasing pollen dispersion");
}

#[test]
fn impact_setting_controls_metrics() {
    let now = utc(2026, 6, 1, 12, 0);
    let c = CurrentConditions {
        temperature_f: Some(72.0),
        condition: Some("Sunny".into()),
        ..Default::default()
    };
    let data = WeatherData {
        location: testville(),
        current: Some(c),
        forecast: Some(today_forecast()),
        ..Default::default()
    };
    let off = presenter(serde_json::json!({}), now).present(&data);
    let cc = off.current_conditions.unwrap();
    assert!(!cc.fallback_text.contains("Impact:"));
    assert_eq!(cc.impact_summary, Some(Default::default()));
    assert_eq!(off.forecast.unwrap().impact_summary, None);
    let on = presenter(serde_json::json!({"show_impact_summaries": true}), now).present(&data);
    let cc = on.current_conditions.unwrap();
    assert!(cc.fallback_text.contains("Impact: Outdoor: Comfortable"));
    assert!(cc
        .fallback_text
        .contains("Impact: Driving: Normal driving conditions"));
    assert!(on.forecast.unwrap().impact_summary.unwrap().has_content());
}

// ---------------------------------------------------------------------------
// test_mobility_briefing.py / test_weather_presenter_mobility_briefing.py
// ---------------------------------------------------------------------------

fn mobility_data(now: Timestamp, dry_minutes: i64) -> WeatherData {
    let points = (0..91)
        .map(|i| MinutelyPrecipitationPoint {
            time: now + Duration::minutes(i),
            precipitation_intensity: Some(if i < dry_minutes { 0.0 } else { 0.08 }),
            precipitation_probability: None,
            precipitation_type: (i >= dry_minutes).then(|| "rain".into()),
            precipitation_intensity_unit: "mm/hr".into(),
            precipitation_intensity_error: None,
            precipitation_intensity_error_unit: "mm/hr".into(),
        })
        .collect();
    WeatherData {
        location: testville(),
        current: Some(CurrentConditions {
            visibility_miles: Some(10.0),
            ..Default::default()
        }),
        hourly_forecast: Some(HourlyForecast {
            periods: vec![
                HourlyForecastPeriod {
                    short_forecast: Some("Cloudy".into()),
                    wind_gust_mph: Some(15.0),
                    visibility_miles: Some(10.0),
                    ..hourly_period(now)
                },
                HourlyForecastPeriod {
                    short_forecast: Some("Light Rain".into()),
                    wind_gust_mph: Some(28.0),
                    visibility_miles: Some(8.0),
                    ..hourly_period(now + Duration::hours(1))
                },
            ],
            ..Default::default()
        }),
        minutely_precipitation: Some(MinutelyPrecipitationForecast {
            points,
            ..Default::default()
        }),
        ..Default::default()
    }
}

#[test]
fn mobility_briefings() {
    let now = utc(2026, 4, 12, 12, 0);
    let later: DateTime<Utc> = Utc.with_ymd_and_hms(2030, 1, 1, 0, 0, 0).unwrap();
    let text = build_mobility_briefing(
        &mobility_data(now, 30),
        Some(now.with_timezone(&Utc)),
        later,
    )
    .unwrap();
    assert!(
        text.contains("Dry for 30 minutes") && text.contains("gusts increase"),
        "{text}"
    );
    // No reference time: inferred from the data, not the clock.
    let text = build_mobility_briefing(&mobility_data(now, 20), None, later).unwrap();
    assert!(text.contains("Dry for 20 minutes"), "{text}");

    let hourly_only = |second: &str, prob: f64, vis: f64| WeatherData {
        location: testville(),
        current: Some(CurrentConditions {
            visibility_miles: Some(10.0),
            ..Default::default()
        }),
        hourly_forecast: Some(HourlyForecast {
            periods: vec![
                HourlyForecastPeriod {
                    short_forecast: Some("Mostly Cloudy".into()),
                    precipitation_probability: Some(10.0),
                    wind_gust_mph: Some(14.0),
                    visibility_miles: Some(10.0),
                    ..hourly_period(now)
                },
                HourlyForecastPeriod {
                    short_forecast: Some(second.into()),
                    precipitation_probability: Some(prob),
                    wind_gust_mph: Some(18.0),
                    visibility_miles: Some(vis),
                    ..hourly_period(now + Duration::hours(1))
                },
            ],
            ..Default::default()
        }),
        ..Default::default()
    };
    let text = build_mobility_briefing(
        &hourly_only("Rain Likely", 75.0, 4.0),
        Some(now.with_timezone(&Utc)),
        later,
    )
    .unwrap();
    assert_eq!(text, "Rain Likely; visibility may drop to around 4 miles.");
    assert_eq!(
        build_mobility_briefing(
            &hourly_only("Clear", 0.0, 10.0),
            Some(now.with_timezone(&Utc)),
            later
        ),
        None
    );

    let presented = presenter(serde_json::json!({}), now).present(&WeatherData {
        forecast: Some(today_forecast()),
        ..mobility_data(now, 30)
    });
    assert!(presented
        .forecast
        .unwrap()
        .hourly_section_text
        .contains("Mobility briefing: Dry for 30 minutes"));
}

#[test]
fn source_attribution_disagreement_note() {
    let now = utc(2026, 4, 12, 12, 0);
    let mut data = WeatherData {
        location: testville(),
        current: Some(CurrentConditions {
            temperature_f: Some(60.0),
            condition: Some("Sunny.".into()),
            ..Default::default()
        }),
        hourly_forecast: Some(HourlyForecast {
            periods: vec![HourlyForecastPeriod {
                short_forecast: Some("Light Rain".into()),
                ..hourly_period(now)
            }],
            ..Default::default()
        }),
        source_attribution: Some(SourceAttribution {
            field_sources: [("condition", "nws"), ("hourly_source", "openmeteo")]
                .map(|(k, v)| (k.to_string(), v.to_string()))
                .into(),
            contributing_sources: ["nws".to_string(), "openmeteo".to_string()].into(),
            ..Default::default()
        }),
        ..Default::default()
    };
    let p = presenter(serde_json::json!({}), now).present(&data);
    assert_eq!(
        p.source_attribution.unwrap().summary_text,
        "Data from: National Weather Service, Open-Meteo. Data note: current conditions from National Weather Service report Sunny; hourly forecast from Open-Meteo says Light Rain."
    );
    data.hourly_forecast.as_mut().unwrap().periods[0].short_forecast = Some("Mostly Sunny".into());
    let p = presenter(serde_json::json!({}), now).present(&data);
    assert_eq!(
        p.source_attribution.unwrap().summary_text,
        "Data from: National Weather Service, Open-Meteo"
    );
}

// ---------------------------------------------------------------------------
// test_unit_preference_bugs.py
// ---------------------------------------------------------------------------

#[test]
fn unit_preferences_reach_every_surface() {
    let now = utc(2026, 1, 20, 12, 0);
    let hourly = HourlyForecast {
        periods: vec![HourlyForecastPeriod {
            temperature: Some(40.0),
            short_forecast: Some("Rain".into()),
            wind_direction: Some("N".into()),
            wind_speed_mph: Some(10.0),
            wind_gust_mph: Some(20.0),
            precipitation_amount: Some(0.5),
            ..hourly_period(now)
        }],
        ..Default::default()
    };
    let hour = |unit: &str| {
        presenter(serde_json::json!({"temperature_unit": unit, "verbosity_level": "detailed", "hourly_forecast_hours": 1}), now)
            .present_forecast(Some(&today_forecast()), &testville(), Some(&hourly), None, None, None)
            .unwrap()
            .hourly_periods
            .remove(0)
    };
    let c = hour("c");
    assert_eq!(c.wind_gust.as_deref(), Some("32 km/h"));
    assert_eq!(c.precipitation_amount.as_deref(), Some("12.7 mm"));
    let f = hour("f");
    assert_eq!(f.wind_gust.as_deref(), Some("20 mph"));
    assert_eq!(f.precipitation_amount.as_deref(), Some("0.5 in"));
    let both = hour("both");
    assert_eq!(both.wind_gust.as_deref(), Some("20 mph (32 km/h)"));
    assert_eq!(
        both.precipitation_amount.as_deref(),
        Some("0.5 in (12.7 mm)")
    );

    let data = WeatherData {
        location: testville(),
        current: Some(CurrentConditions {
            temperature_f: Some(50.0),
            temperature_c: Some(10.0),
            condition: Some("Cloudy".into()),
            ..Default::default()
        }),
        trend_insights: vec![TrendInsight {
            metric: "temperature".into(),
            direction: "rising".into(),
            change: Some(9.0),
            unit: Some("°F".into()),
            timeframe_hours: 24,
            summary: Some("Temperature rising +9.0°F over 24h".into()),
            sparkline: None,
        }],
        ..Default::default()
    };
    let p = presenter(serde_json::json!({"temperature_unit": "c"}), now).present(&data);
    assert_eq!(
        p.summary_text,
        "Testville - 10°C - Cloudy - Temperature rising +5.0°C over 24h"
    );
    assert_eq!(p.trend_summary, ["Temperature rising +5.0°C over 24h"]);
}
