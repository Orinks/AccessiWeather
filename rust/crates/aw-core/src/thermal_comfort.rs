//! Sanity checks for apparent temperature, wind chill and heat index
//! readings. Port of `accessiweather/thermal_comfort.py`.

use crate::units::{c_to_f, f_to_c};

const WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F: f64 = 3.0;
const HEAT_INDEX_COHERENCE_TOLERANCE_F: f64 = 2.5;
const APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_BASE_F: f64 = 4.0;
const APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_MAX_F: f64 = 5.5;
const APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_PER_DEGREE_F: f64 = 0.15;
const HEAT_INDEX_MIN_TEMP_F: f64 = 80.0;
const HEAT_INDEX_MIN_HUMIDITY: f64 = 40.0;
const WIND_CHILL_MAX_TEMP_F: f64 = 50.0;
const WIND_CHILL_MIN_WIND_MPH: f64 = 3.0;

/// Normalised and sanity-checked apparent-temperature readings.
#[derive(Debug, Clone, Copy, Default, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct ThermalComfortReadings {
    pub feels_like_f: Option<f64>,
    pub feels_like_c: Option<f64>,
    pub wind_chill_f: Option<f64>,
    pub wind_chill_c: Option<f64>,
    pub heat_index_f: Option<f64>,
    pub heat_index_c: Option<f64>,
}

/// Raw inputs to [`sanitize_thermal_comfort_readings`]; any unit may be absent.
#[derive(Debug, Clone, Copy, Default, PartialEq, serde::Deserialize)]
#[serde(default)]
pub struct ThermalComfortInput {
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

/// Normalise and discard internally inconsistent thermal-comfort readings.
pub fn sanitize_thermal_comfort_readings(input: ThermalComfortInput) -> ThermalComfortReadings {
    let temp_f = to_fahrenheit(input.temperature_f, input.temperature_c);
    let mut feels_f = to_fahrenheit(input.feels_like_f, input.feels_like_c);
    let mut chill_f = to_fahrenheit(input.wind_chill_f, input.wind_chill_c);
    let mut heat_f = to_fahrenheit(input.heat_index_f, input.heat_index_c);
    let humidity = input.humidity;

    if !warm_apparent_temperature_is_coherent(temp_f, humidity, feels_f) {
        feels_f = None;
    }
    if !warm_heat_index_is_coherent(temp_f, humidity, heat_f) {
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

    if let (Some(f), Some(t)) = (feels_f, temp_f) {
        if f > t && heat_f.is_none() && warm_heat_index_is_coherent(temp_f, humidity, feels_f) {
            heat_f = feels_f;
        } else if f < t && chill_f.is_none() {
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

    ThermalComfortReadings {
        feels_like_f: feels_f,
        feels_like_c: feels_f.map(f_to_c),
        wind_chill_f: chill_f,
        wind_chill_c: chill_f.map(f_to_c),
        heat_index_f: heat_f,
        heat_index_c: heat_f.map(f_to_c),
    }
}

/// NOAA/NWS Rothfusz heat index (°F), or `None` outside the warm/humid range.
pub fn calculate_heat_index_f(temperature_f: f64, humidity: f64) -> Option<f64> {
    if temperature_f < HEAT_INDEX_MIN_TEMP_F || humidity < HEAT_INDEX_MIN_HUMIDITY {
        return None;
    }
    let t = temperature_f;
    let h = humidity;
    let mut heat_index = -42.379 + 2.04901523 * t + 10.14333127 * h
        - 0.22475541 * t * h
        - 0.00683783 * t * t
        - 0.05481717 * h * h
        + 0.00122874 * t * t * h
        + 0.00085282 * t * h * h
        - 0.00000199 * t * t * h * h;
    if h > 85.0 && (80.0..=87.0).contains(&t) {
        heat_index += ((h - 85.0) / 10.0) * ((87.0 - t) / 5.0);
    }
    Some(heat_index)
}

/// Standard NWS wind chill (°F), or `None` when it does not apply.
pub fn calculate_wind_chill_f(temperature_f: f64, wind_speed_mph: f64) -> Option<f64> {
    if temperature_f > WIND_CHILL_MAX_TEMP_F || wind_speed_mph <= WIND_CHILL_MIN_WIND_MPH {
        return None;
    }
    let wind_factor = wind_speed_mph.powf(0.16);
    Some(
        35.74 + (0.6215 * temperature_f) - (35.75 * wind_factor)
            + (0.4275 * temperature_f * wind_factor),
    )
}

/// Whether a warm provider apparent temperature is plausible.
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
    let Some(h) = humidity else {
        return true;
    };
    let mut max_coherent = t + solar_apparent_temperature_allowance_f(t);
    if let Some(heat_index) = calculate_heat_index_f(t, h) {
        max_coherent = max_coherent.max(t.max(heat_index) + HEAT_INDEX_COHERENCE_TOLERANCE_F);
    }
    a <= max_coherent
}

/// Whether a literal or inferred heat-index reading is plausible.
pub fn warm_heat_index_is_coherent(
    temperature_f: Option<f64>,
    humidity: Option<f64>,
    heat_index_f: Option<f64>,
) -> bool {
    let (Some(t), Some(hi)) = (temperature_f, heat_index_f) else {
        return true;
    };
    if hi <= t || hi - t < WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F {
        return true;
    }
    let Some(h) = humidity else {
        return true;
    };
    match calculate_heat_index_f(t, h) {
        Some(heat_index) => hi <= t.max(heat_index) + HEAT_INDEX_COHERENCE_TOLERANCE_F,
        None => false,
    }
}

fn solar_apparent_temperature_allowance_f(temperature_f: f64) -> f64 {
    let mut allowance = APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_BASE_F;
    if temperature_f > HEAT_INDEX_MIN_TEMP_F {
        allowance += (temperature_f - HEAT_INDEX_MIN_TEMP_F)
            * APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_PER_DEGREE_F;
    }
    allowance.min(APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_MAX_F)
}

fn to_fahrenheit(value_f: Option<f64>, value_c: Option<f64>) -> Option<f64> {
    value_f.or(value_c.map(c_to_f))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::golden;

    #[test]
    fn golden_sanitize_heat_index_and_wind_chill() {
        let cases = golden::load("thermal/cases.json");
        for case in cases["sanitize"].as_array().unwrap() {
            let input: ThermalComfortInput = serde_json::from_value(case["input"].clone()).unwrap();
            let expected: ThermalComfortReadings =
                serde_json::from_value(case["output"].clone()).unwrap();
            assert_eq!(
                sanitize_thermal_comfort_readings(input),
                expected,
                "{input:?}"
            );
        }
        for case in cases["heat_index"].as_array().unwrap() {
            let t = case["temperature_f"].as_f64().unwrap();
            let h = case["humidity"].as_f64().unwrap();
            assert_eq!(
                calculate_heat_index_f(t, h),
                case["output"].as_f64(),
                "{t} {h}"
            );
        }
        for case in cases["wind_chill"].as_array().unwrap() {
            let t = case["temperature_f"].as_f64().unwrap();
            let w = case["wind_speed_mph"].as_f64().unwrap();
            assert_eq!(
                calculate_wind_chill_f(t, w),
                case["output"].as_f64(),
                "{t} {w}"
            );
        }
    }

    #[test]
    fn cold_feels_like_becomes_wind_chill() {
        let out = sanitize_thermal_comfort_readings(ThermalComfortInput {
            temperature_f: Some(30.0),
            feels_like_f: Some(20.0),
            ..Default::default()
        });
        assert_eq!(out.wind_chill_f, Some(20.0));
        assert_eq!(out.feels_like_f, Some(20.0));
        assert_eq!(out.heat_index_f, None);
    }

    #[test]
    fn implausible_dry_heat_feels_like_is_dropped() {
        let out = sanitize_thermal_comfort_readings(ThermalComfortInput {
            temperature_f: Some(85.0),
            humidity: Some(20.0),
            feels_like_f: Some(99.0),
            ..Default::default()
        });
        assert_eq!(out, ThermalComfortReadings::default());
    }
}
