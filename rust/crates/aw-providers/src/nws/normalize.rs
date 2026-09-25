//! Unit conversion and sanity helpers the NWS parsers use: the NWS parts of
//! `weather_client_parsers.py`, the pair normalisers from
//! `provider_normalization.py` and `thermal_comfort.py`.
//!
//! These are provider-neutral in Python; they live here until the shared
//! normalisation layer is ported so the NWS port stays self-contained.

use serde_json::Value;

use super::common::py_float;

// ---------------------------------------------------------------------------
// weather_client_parsers
// ---------------------------------------------------------------------------

fn ends_with_any(s: &str, suffixes: &[&str]) -> bool {
    suffixes.iter().any(|x| s.ends_with(x))
}

/// `convert_wind_speed_to_mph`.
pub fn convert_wind_speed_to_mph(value: Option<f64>, unit_code: Option<&str>) -> Option<f64> {
    let value = value?;
    let Some(unit) = unit_code.filter(|u| !u.is_empty()) else {
        return Some(value);
    };
    let unit = unit.to_lowercase();
    Some(if ends_with_any(&unit, &["m_s-1", "mps"]) {
        value * 2.237
    } else if ends_with_any(&unit, &["km_h-1", "kmh", "km/h"]) {
        value * 0.621371
    } else if ends_with_any(&unit, &["mi_h-1", "mph", "mp/h"]) {
        value
    } else if ends_with_any(&unit, &["kn", "kt"]) {
        value * 1.15078
    } else {
        value
    })
}

/// `convert_wind_speed_to_kph`.
pub fn convert_wind_speed_to_kph(value: Option<f64>, unit_code: Option<&str>) -> Option<f64> {
    let value = value?;
    let Some(unit) = unit_code.filter(|u| !u.is_empty()) else {
        return Some(value);
    };
    let unit = unit.to_lowercase();
    Some(if ends_with_any(&unit, &["m_s-1", "mps"]) {
        value * 3.6
    } else if ends_with_any(&unit, &["km_h-1", "kmh", "km/h"]) {
        value
    } else if ends_with_any(&unit, &["mi_h-1", "mph", "mp/h"]) {
        value * 1.60934
    } else if ends_with_any(&unit, &["kn", "kt"]) {
        value * 1.852
    } else {
        value
    })
}

/// `convert_wind_speed_to_mph_and_kph`.
pub fn convert_wind_speed_to_mph_and_kph(
    value: Option<f64>,
    unit_code: Option<&str>,
) -> (Option<f64>, Option<f64>) {
    (
        convert_wind_speed_to_mph(value, unit_code),
        convert_wind_speed_to_kph(value, unit_code),
    )
}

/// `convert_pa_to_inches`.
pub fn convert_pa_to_inches(pa: f64) -> f64 {
    pa * 0.0002953
}

/// `convert_pa_to_mb`.
pub fn convert_pa_to_mb(pa: f64) -> f64 {
    pa / 100.0
}

/// `convert_f_to_c`.
pub fn convert_f_to_c(fahrenheit: f64) -> f64 {
    (fahrenheit - 32.0) * 5.0 / 9.0
}

/// `normalize_temperature`: (°F, °C) from a value in `unit`.
pub fn normalize_temperature(value: f64, unit: Option<&str>) -> (f64, f64) {
    let unit = unit.unwrap_or("").to_lowercase();
    if unit.contains('f') {
        (value, convert_f_to_c(value))
    } else if unit.contains('c') {
        ((value * 9.0 / 5.0) + 32.0, value)
    } else {
        (value, convert_f_to_c(value))
    }
}

/// `normalize_pressure`: (inHg, mb) from a value in `unit`.
pub fn normalize_pressure(value: f64, unit: Option<&str>) -> (Option<f64>, Option<f64>) {
    let unit = unit.unwrap_or("").to_lowercase();
    if unit.contains("hpa") || unit.contains("mb") {
        (Some(value * 0.0295299830714), Some(value))
    } else if unit.contains("pa") {
        (Some(convert_pa_to_inches(value)), Some(value / 100.0))
    } else if unit.contains("inch") || unit.ends_with("in") {
        (Some(value), Some(value * 33.8639))
    } else {
        (None, Some(value))
    }
}

// ---------------------------------------------------------------------------
// provider_normalization
// ---------------------------------------------------------------------------

/// `as_float`: missing, empty or unparsable values are absent.
pub fn as_float(value: &Value) -> Option<f64> {
    match value {
        Value::Null => None,
        Value::String(s) if s.is_empty() => None,
        other => py_float(other),
    }
}

/// `normalize_humidity_percent`.
pub fn normalize_humidity_percent(value: &Value) -> Option<i64> {
    as_float(value).map(super::common::py_round)
}

/// `normalize_temperature_pair`: (°F, °C).
pub fn normalize_temperature_pair(value: &Value, unit: Option<&str>) -> (Option<f64>, Option<f64>) {
    match as_float(value) {
        Some(v) => {
            let (f, c) = normalize_temperature(v, unit);
            (Some(f), Some(c))
        }
        None => (None, None),
    }
}

/// `normalize_pressure_pair`: (inHg, mb).
pub fn normalize_pressure_pair(value: &Value, unit: Option<&str>) -> (Option<f64>, Option<f64>) {
    match as_float(value) {
        Some(v) => normalize_pressure(v, unit),
        None => (None, None),
    }
}

// ---------------------------------------------------------------------------
// thermal_comfort
// ---------------------------------------------------------------------------

const WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F: f64 = 3.0;
const HEAT_INDEX_COHERENCE_TOLERANCE_F: f64 = 2.5;
const APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_BASE_F: f64 = 4.0;
const APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_MAX_F: f64 = 5.5;
const APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_PER_DEGREE_F: f64 = 0.15;
const HEAT_INDEX_MIN_TEMP_F: f64 = 80.0;
const HEAT_INDEX_MIN_HUMIDITY: f64 = 40.0;
const WIND_CHILL_MAX_TEMP_F: f64 = 50.0;
const WIND_CHILL_MIN_WIND_MPH: f64 = 3.0;

/// `ThermalComfortReadings`.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct ThermalComfort {
    pub feels_like_f: Option<f64>,
    pub feels_like_c: Option<f64>,
    pub wind_chill_f: Option<f64>,
    pub wind_chill_c: Option<f64>,
    pub heat_index_f: Option<f64>,
    pub heat_index_c: Option<f64>,
}

/// Inputs to [`sanitize_thermal_comfort_readings`] (Python keyword args).
#[derive(Debug, Clone, Copy, Default)]
pub struct ThermalInputs {
    pub temperature_f: Option<f64>,
    pub temperature_c: Option<f64>,
    pub humidity: Option<f64>,
    pub feels_like_f: Option<f64>,
    pub feels_like_c: Option<f64>,
    pub wind_chill_f: Option<f64>,
    pub wind_chill_c: Option<f64>,
    pub heat_index_f: Option<f64>,
    pub heat_index_c: Option<f64>,
}

fn to_fahrenheit(f: Option<f64>, c: Option<f64>) -> Option<f64> {
    f.or_else(|| c.map(|c| (c * 9.0 / 5.0) + 32.0))
}

fn to_celsius(f: Option<f64>) -> Option<f64> {
    f.map(|f| (f - 32.0) * 5.0 / 9.0)
}

/// `sanitize_thermal_comfort_readings`.
pub fn sanitize_thermal_comfort_readings(i: ThermalInputs) -> ThermalComfort {
    let temp_f = to_fahrenheit(i.temperature_f, i.temperature_c);
    let mut feels_f = to_fahrenheit(i.feels_like_f, i.feels_like_c);
    let mut chill_f = to_fahrenheit(i.wind_chill_f, i.wind_chill_c);
    let mut heat_f = to_fahrenheit(i.heat_index_f, i.heat_index_c);

    if !warm_apparent_temperature_is_coherent(temp_f, i.humidity, feels_f) {
        feels_f = None;
    }
    if !warm_heat_index_is_coherent(temp_f, i.humidity, heat_f) {
        heat_f = None;
    }

    if let Some(t) = temp_f {
        if heat_f.is_some_and(|h| h <= t) {
            heat_f = None;
        }
        if chill_f.is_some_and(|c| c >= t) {
            chill_f = None;
        }
    }

    if let (Some(feels), Some(t)) = (feels_f, temp_f) {
        if feels > t && heat_f.is_none() && warm_heat_index_is_coherent(temp_f, i.humidity, feels_f)
        {
            heat_f = feels_f;
        } else if feels < t && chill_f.is_none() {
            chill_f = feels_f;
        }
    }

    if let (None, Some(t)) = (feels_f, temp_f) {
        if chill_f.is_some_and(|c| c < t) {
            feels_f = chill_f;
        } else if heat_f.is_some_and(|h| h > t) {
            feels_f = heat_f;
        }
    }

    ThermalComfort {
        feels_like_f: feels_f,
        feels_like_c: to_celsius(feels_f),
        wind_chill_f: chill_f,
        wind_chill_c: to_celsius(chill_f),
        heat_index_f: heat_f,
        heat_index_c: to_celsius(heat_f),
    }
}

/// `calculate_heat_index_f` (Rothfusz), `None` outside its warm/humid range.
pub fn calculate_heat_index_f(t: f64, rh: f64) -> Option<f64> {
    if t < HEAT_INDEX_MIN_TEMP_F || rh < HEAT_INDEX_MIN_HUMIDITY {
        return None;
    }
    let mut hi = -42.379 + 2.04901523 * t + 10.14333127 * rh
        - 0.22475541 * t * rh
        - 0.00683783 * t * t
        - 0.05481717 * rh * rh
        + 0.00122874 * t * t * rh
        + 0.00085282 * t * rh * rh
        - 0.00000199 * t * t * rh * rh;
    if rh > 85.0 && (80.0..=87.0).contains(&t) {
        hi += ((rh - 85.0) / 10.0) * ((87.0 - t) / 5.0);
    }
    Some(hi)
}

/// `calculate_wind_chill_f` (NWS formula), `None` when not applicable.
pub fn calculate_wind_chill_f(t: f64, wind_mph: f64) -> Option<f64> {
    if t > WIND_CHILL_MAX_TEMP_F || wind_mph <= WIND_CHILL_MIN_WIND_MPH {
        return None;
    }
    let factor = wind_mph.powf(0.16);
    Some(35.74 + (0.6215 * t) - (35.75 * factor) + (0.4275 * t * factor))
}

fn solar_allowance_f(t: f64) -> f64 {
    let mut allowance = APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_BASE_F;
    if t > HEAT_INDEX_MIN_TEMP_F {
        allowance +=
            (t - HEAT_INDEX_MIN_TEMP_F) * APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_PER_DEGREE_F;
    }
    allowance.min(APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_MAX_F)
}

/// `warm_apparent_temperature_is_coherent`.
pub fn warm_apparent_temperature_is_coherent(
    temperature_f: Option<f64>,
    humidity: Option<f64>,
    apparent_f: Option<f64>,
) -> bool {
    let (Some(t), Some(a)) = (temperature_f, apparent_f) else {
        return true;
    };
    if a <= t || a - t < WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F {
        return true;
    }
    let Some(rh) = humidity else {
        return true;
    };
    let mut max_coherent = t + solar_allowance_f(t);
    if let Some(hi) = calculate_heat_index_f(t, rh) {
        max_coherent = max_coherent.max(t.max(hi) + HEAT_INDEX_COHERENCE_TOLERANCE_F);
    }
    a <= max_coherent
}

/// `warm_heat_index_is_coherent`.
pub fn warm_heat_index_is_coherent(
    temperature_f: Option<f64>,
    humidity: Option<f64>,
    heat_index_f: Option<f64>,
) -> bool {
    let (Some(t), Some(h)) = (temperature_f, heat_index_f) else {
        return true;
    };
    if h <= t || h - t < WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F {
        return true;
    }
    let Some(rh) = humidity else {
        return true;
    };
    match calculate_heat_index_f(t, rh) {
        Some(hi) => h <= t.max(hi) + HEAT_INDEX_COHERENCE_TOLERANCE_F,
        None => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn conversions_match_python_factors() {
        assert_eq!(
            convert_wind_speed_to_mph(Some(10.0), Some("wmoUnit:m_s-1")),
            Some(22.37)
        );
        assert_eq!(
            convert_wind_speed_to_kph(Some(10.0), Some("wmoUnit:km_h-1")),
            Some(10.0)
        );
        assert_eq!(convert_wind_speed_to_mph(Some(10.0), None), Some(10.0));
        assert_eq!(convert_wind_speed_to_mph(None, Some("kt")), None);
        assert_eq!(
            normalize_pressure(101325.0, Some("wmoUnit:Pa")),
            (Some(101325.0 * 0.0002953), Some(1013.25))
        );
        assert_eq!(normalize_pressure(1013.0, Some("hPa")).1, Some(1013.0));
        assert_eq!(
            normalize_pressure(30.0, Some("wmoUnit:in")),
            (Some(30.0), Some(30.0 * 33.8639))
        );
        // Python quirk kept: "inHg" matches neither "inch" nor a trailing "in".
        assert_eq!(normalize_pressure(30.0, Some("inHg")), (None, Some(30.0)));
        assert_eq!(normalize_pressure(5.0, Some("??")), (None, Some(5.0)));
        assert_eq!(
            normalize_temperature(0.0, Some("wmoUnit:degC")),
            (32.0, 0.0)
        );
        assert_eq!(normalize_humidity_percent(&json!(72.5)), Some(72));
        assert_eq!(normalize_humidity_percent(&json!("")), None);
    }

    #[test]
    fn thermal_comfort_drops_incoherent_heat_index() {
        // 85°F at 20% humidity: no heat index applies, so a literal 95°F is noise.
        let r = sanitize_thermal_comfort_readings(ThermalInputs {
            temperature_f: Some(85.0),
            humidity: Some(20.0),
            heat_index_f: Some(95.0),
            ..Default::default()
        });
        assert_eq!(r.heat_index_f, None);
        // Wind chill above the air temperature is discarded too.
        let r = sanitize_thermal_comfort_readings(ThermalInputs {
            temperature_f: Some(30.0),
            wind_chill_f: Some(31.0),
            ..Default::default()
        });
        assert_eq!(r.wind_chill_f, None);
        assert_eq!(r.feels_like_f, None);
    }

    #[test]
    fn wind_chill_and_heat_index_applicability() {
        assert!(calculate_wind_chill_f(60.0, 10.0).is_none());
        assert!(calculate_wind_chill_f(30.0, 3.0).is_none());
        assert!((calculate_wind_chill_f(32.0, 10.0).unwrap() - 23.727).abs() < 0.01);
        assert!(calculate_heat_index_f(79.0, 80.0).is_none());
        assert!((calculate_heat_index_f(90.0, 70.0).unwrap() - 105.9).abs() < 0.1);
    }
}
