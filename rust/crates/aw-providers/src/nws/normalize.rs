//! The provider-neutral helpers the NWS parsers use (`weather_client_parsers.py`,
//! `provider_normalization.py` and `thermal_comfort.py`, ported in
//! `aw_core`), taking the JSON values the parsers hold.

use aw_core::provider_normalization as pn;
use serde_json::Value;

use super::common::py_float;

pub use aw_core::thermal_comfort::{
    calculate_heat_index_f, calculate_wind_chill_f, sanitize_thermal_comfort_readings,
    ThermalComfortInput as ThermalInputs,
};
pub use aw_core::weather_client_parsers::{
    convert_pa_to_inches, convert_pa_to_mb, convert_wind_speed_to_mph_and_kph, normalize_pressure,
};

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
    pn::normalize_humidity_percent(as_float(value), false)
}

/// `normalize_temperature_pair`: (°F, °C).
pub fn normalize_temperature_pair(value: &Value, unit: Option<&str>) -> (Option<f64>, Option<f64>) {
    let pair = pn::normalize_temperature_pair(as_float(value), unit);
    (pair.fahrenheit, pair.celsius)
}

/// `normalize_pressure_pair`: (inHg, mb).
pub fn normalize_pressure_pair(value: &Value, unit: Option<&str>) -> (Option<f64>, Option<f64>) {
    let pair = pn::normalize_pressure_pair(as_float(value), unit);
    (pair.inches, pair.millibars)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn json_values_become_python_floats() {
        assert_eq!(normalize_humidity_percent(&json!(72.5)), Some(72));
        assert_eq!(normalize_humidity_percent(&json!("")), None);
        assert_eq!(
            normalize_temperature_pair(&json!("0"), Some("wmoUnit:degC")),
            (Some(32.0), Some(0.0))
        );
        assert_eq!(
            normalize_pressure_pair(&json!(null), Some("wmoUnit:Pa")),
            (None, None)
        );
    }
}
