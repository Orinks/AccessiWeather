//! Shared unit conversions and labels, ported from
//! `accessiweather.weather_client_parsers` (`merge_current_conditions`
//! belongs to the fusion layer and is not here).

use chrono::Datelike;
use serde_json::Value;

use crate::py;

/// Convert meters per second to miles per hour.
pub fn convert_mps_to_mph(mps: Option<f64>) -> Option<f64> {
    mps.map(|v| v * 2.237)
}

fn unit_factor(unit_code: Option<&str>, factors: [f64; 4]) -> f64 {
    let Some(unit) = unit_code.filter(|u| !u.is_empty()) else {
        return 1.0;
    };
    let unit = unit.to_lowercase();
    let ends = |suffixes: &[&str]| suffixes.iter().any(|s| unit.ends_with(s));
    if ends(&["m_s-1", "mps"]) {
        factors[0]
    } else if ends(&["km_h-1", "kmh", "km/h"]) {
        factors[1]
    } else if ends(&["mi_h-1", "mph", "mp/h"]) {
        factors[2]
    } else if ends(&["kn", "kt"]) {
        factors[3]
    } else {
        1.0
    }
}

/// Normalize WMO wind speed units to miles per hour.
pub fn convert_wind_speed_to_mph(value: Option<f64>, unit_code: Option<&str>) -> Option<f64> {
    let value = value?;
    Some(value * unit_factor(unit_code, [2.237, 0.621371, 1.0, 1.15078]))
}

/// Normalize WMO wind speed units to kilometers per hour.
pub fn convert_wind_speed_to_kph(value: Option<f64>, unit_code: Option<&str>) -> Option<f64> {
    let value = value?;
    Some(value * unit_factor(unit_code, [3.6, 1.0, 1.60934, 1.852]))
}

pub fn convert_wind_speed_to_mph_and_kph(
    value: Option<f64>,
    unit_code: Option<&str>,
) -> (Option<f64>, Option<f64>) {
    (
        convert_wind_speed_to_mph(value, unit_code),
        convert_wind_speed_to_kph(value, unit_code),
    )
}

pub fn convert_pa_to_inches(pa: Option<f64>) -> Option<f64> {
    pa.map(|p| p * 0.0002953)
}

pub fn convert_pa_to_mb(pa: Option<f64>) -> Option<f64> {
    pa.map(|p| p / 100.0)
}

pub fn convert_f_to_c(fahrenheit: Option<f64>) -> Option<f64> {
    fahrenheit.map(|f| (f - 32.0) * 5.0 / 9.0)
}

/// Temperature as (fahrenheit, celsius); units without "f" or "c" are Fahrenheit.
pub fn normalize_temperature(value: Option<f64>, unit: Option<&str>) -> (Option<f64>, Option<f64>) {
    let Some(value) = value else {
        return (None, None);
    };
    let unit = unit.unwrap_or("").to_lowercase();
    if !unit.contains('f') && unit.contains('c') {
        (Some((value * 9.0 / 5.0) + 32.0), Some(value))
    } else {
        (Some(value), convert_f_to_c(Some(value)))
    }
}

/// Pressure as (inches of mercury, millibars).
pub fn normalize_pressure(value: Option<f64>, unit: Option<&str>) -> (Option<f64>, Option<f64>) {
    let Some(value) = value else {
        return (None, None);
    };
    let unit = unit.unwrap_or("").to_lowercase();
    if unit.contains("hpa") || unit.contains("mb") {
        (Some(value * 0.0295299830714), Some(value))
    } else if unit.contains("pa") {
        (convert_pa_to_inches(Some(value)), Some(value / 100.0))
    } else if unit.contains("inch") || unit.ends_with("in") {
        (Some(value), Some(value * 33.8639))
    } else {
        (None, Some(value))
    }
}

const DIRECTIONS: [&str; 16] = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW",
    "NNW",
];

/// Wind direction in degrees to a 16-point cardinal (`round(deg / 22.5) % 16`).
pub fn degrees_to_cardinal(degrees: Option<f64>) -> Option<String> {
    let index = py::round(degrees? / 22.5).rem_euclid(16.0) as usize;
    Some(DIRECTIONS[index].to_string())
}

pub fn weather_code_label(code: i64) -> Option<&'static str> {
    Some(match code {
        0 => "Clear sky",
        1 => "Mainly clear",
        2 => "Partly cloudy",
        3 => "Overcast",
        45 => "Fog",
        48 => "Depositing rime fog",
        51 => "Light drizzle",
        53 => "Moderate drizzle",
        55 => "Dense drizzle",
        56 => "Light freezing drizzle",
        57 => "Dense freezing drizzle",
        61 => "Slight rain",
        63 => "Moderate rain",
        65 => "Heavy rain",
        66 => "Light freezing rain",
        67 => "Heavy freezing rain",
        71 => "Slight snow fall",
        73 => "Moderate snow fall",
        75 => "Heavy snow fall",
        77 => "Snow grains",
        80 => "Slight rain showers",
        81 => "Moderate rain showers",
        82 => "Violent rain showers",
        85 => "Slight snow showers",
        86 => "Heavy snow showers",
        95 => "Thunderstorm",
        96 => "Thunderstorm with slight hail",
        99 => "Thunderstorm with heavy hail",
        _ => return None,
    })
}

/// `int(code)` for a JSON value, as Python would coerce it.
pub fn py_int(value: &Value) -> Option<i64> {
    match value {
        Value::Number(n) => n.as_i64().or_else(|| n.as_f64().map(|f| f.trunc() as i64)),
        Value::Bool(b) => Some(i64::from(*b)),
        Value::String(s) => s.trim().parse().ok(),
        _ => None,
    }
}

/// Open-Meteo weather code to a description; `None` for a missing code.
pub fn weather_code_to_description(code: Option<&Value>) -> Option<String> {
    let code = code.filter(|c| !c.is_null())?;
    match py_int(code) {
        Some(n) => Some(
            weather_code_label(n)
                .map(str::to_string)
                .unwrap_or_else(|| format!("Weather code {n}")),
        ),
        None => Some(format!("Weather code {}", py::value_str(code))),
    }
}

/// "Today", "Tomorrow", the weekday name, or "Day N" when the date is unreadable.
pub fn format_date_name(date_str: &str, index: usize) -> String {
    match index {
        0 => "Today".into(),
        1 => "Tomorrow".into(),
        _ => match py::fromisoformat(date_str) {
            Some((dt, _)) => weekday_name(dt.weekday()).into(),
            None => format!("Day {}", index + 1),
        },
    }
}

pub fn weekday_name(day: chrono::Weekday) -> &'static str {
    match day {
        chrono::Weekday::Mon => "Monday",
        chrono::Weekday::Tue => "Tuesday",
        chrono::Weekday::Wed => "Wednesday",
        chrono::Weekday::Thu => "Thursday",
        chrono::Weekday::Fri => "Friday",
        chrono::Weekday::Sat => "Saturday",
        chrono::Weekday::Sun => "Sunday",
    }
}

/// Numeric moon phase fraction to a descriptive label.
pub fn describe_moon_phase(value: Option<&Value>) -> Option<String> {
    let value = value.filter(|v| !v.is_null())?;
    let fraction = py::as_float(Some(value))?.rem_euclid(1.0);
    let phases = [
        (0.0625, "New Moon"),
        (0.1875, "Waxing Crescent"),
        (0.3125, "First Quarter"),
        (0.4375, "Waxing Gibbous"),
        (0.5625, "Full Moon"),
        (0.6875, "Waning Gibbous"),
        (0.8125, "Last Quarter"),
        (0.9375, "Waning Crescent"),
    ];
    let name = phases
        .iter()
        .find(|(threshold, _)| fraction < *threshold)
        .map_or("New Moon", |(_, name)| name);
    Some(name.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn close(a: Option<f64>, b: f64) -> bool {
        a.is_some_and(|a| (a - b).abs() < 0.01)
    }

    #[test]
    fn temperature_normalization() {
        assert_eq!(normalize_temperature(Some(32.0), Some("°F")), (Some(32.0), Some(0.0)));
        assert_eq!(normalize_temperature(Some(0.0), Some("°C")), (Some(32.0), Some(0.0)));
        assert_eq!(
            normalize_temperature(Some(100.0), Some("wmoUnit:degC")),
            (Some(212.0), Some(100.0))
        );
        assert_eq!(normalize_temperature(None, Some("°C")), (None, None));
    }

    #[test]
    fn wind_speed_conversions() {
        assert!(close(convert_mps_to_mph(Some(10.0)), 22.37));
        assert!(close(convert_wind_speed_to_mph(Some(100.0), Some("km/h")), 62.1371));
        assert!(close(convert_wind_speed_to_mph(Some(10.0), Some("wmoUnit:m_s-1")), 22.37));
        assert!(close(convert_wind_speed_to_mph(Some(10.0), Some("kn")), 11.5078));
        assert!(close(convert_wind_speed_to_kph(Some(10.0), Some("mph")), 16.0934));
        assert_eq!(convert_wind_speed_to_mph(Some(7.0), Some("mp/h")), Some(7.0));
        assert_eq!(convert_wind_speed_to_mph(Some(7.0), None), Some(7.0));
    }

    #[test]
    fn pressure_conversions() {
        assert!(close(convert_pa_to_inches(Some(101325.0)), 29.92));
        assert_eq!(convert_pa_to_mb(Some(101325.0)), Some(1013.25));
        let (inches, mb) = normalize_pressure(Some(101325.0), Some("wmoUnit:Pa"));
        assert!(close(inches, 29.92));
        assert_eq!(mb, Some(1013.25));
        let (inches, mb) = normalize_pressure(Some(1013.25), Some("hPa"));
        assert!(close(inches, 29.92));
        assert_eq!(mb, Some(1013.25));
        assert_eq!(normalize_pressure(Some(5.0), Some("?")), (None, Some(5.0)));
    }

    #[test]
    fn cardinal_directions() {
        let c = |d: f64| degrees_to_cardinal(Some(d)).unwrap();
        assert_eq!([c(0.0), c(90.0), c(180.0), c(270.0)], ["N", "E", "S", "W"]);
        assert_eq!([c(45.0), c(135.0), c(225.0), c(315.0)], ["NE", "SE", "SW", "NW"]);
        assert_eq!(c(22.5), "NNE");
        assert_eq!(c(360.0), "N");
        assert_eq!(c(-22.5), "NNW");
        assert_eq!(degrees_to_cardinal(None), None);
    }

    #[test]
    fn weather_codes() {
        let d = |v: Value| weather_code_to_description(Some(&v));
        assert_eq!(d(json!(0)).as_deref(), Some("Clear sky"));
        assert_eq!(d(json!(3)).as_deref(), Some("Overcast"));
        assert_eq!(d(json!("95")).as_deref(), Some("Thunderstorm"));
        assert_eq!(d(json!(999)).as_deref(), Some("Weather code 999"));
        assert_eq!(d(json!("abc")).as_deref(), Some("Weather code abc"));
        assert_eq!(weather_code_to_description(None), None);
        assert_eq!(d(json!(null)), None);
    }

    #[test]
    fn date_names() {
        assert_eq!(format_date_name("2025-01-15", 0), "Today");
        assert_eq!(format_date_name("2025-01-16", 1), "Tomorrow");
        assert_eq!(format_date_name("2025-01-17", 2), "Friday");
        assert_eq!(format_date_name("garbage", 4), "Day 5");
    }

    #[test]
    fn moon_phases() {
        let m = |v: Value| describe_moon_phase(Some(&v));
        assert_eq!(m(json!(0.0)).as_deref(), Some("New Moon"));
        assert_eq!(m(json!(0.5)).as_deref(), Some("Full Moon"));
        assert_eq!(m(json!(0.97)).as_deref(), Some("New Moon"));
        assert_eq!(m(json!(1.25)).as_deref(), Some("First Quarter"));
        assert_eq!(m(json!("x")), None);
    }
}
