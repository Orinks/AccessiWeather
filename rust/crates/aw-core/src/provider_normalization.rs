//! Provider-neutral normalization helpers, ported from
//! `accessiweather.provider_normalization` (plus `calculate_dewpoint` from
//! `accessiweather.utils.temperature_utils`).

use crate::py;
use crate::weather_client_parsers::{
    convert_f_to_c, convert_wind_speed_to_mph_and_kph, normalize_pressure, normalize_temperature,
};

pub const KM_PER_MILE: f64 = 1.609344;
pub const MB_PER_INHG: f64 = 33.8639;

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct TemperaturePair {
    pub fahrenheit: Option<f64>,
    pub celsius: Option<f64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct SpeedPair {
    pub mph: Option<f64>,
    pub kph: Option<f64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct PressurePair {
    pub inches: Option<f64>,
    pub millibars: Option<f64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct VisibilityPair {
    pub miles: Option<f64>,
    pub kilometers: Option<f64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct ApparentTemperatureClassification {
    pub wind_chill_f: Option<f64>,
    pub wind_chill_c: Option<f64>,
    pub heat_index_f: Option<f64>,
    pub heat_index_c: Option<f64>,
}

/// Magnus-approximation dewpoint in the unit family of `unit` ("c"/"°C"/
/// "celsius"/"degC"... mean Celsius; anything else Fahrenheit).
pub fn calculate_dewpoint(temperature: Option<f64>, humidity: Option<f64>, unit: &str) -> Option<f64> {
    let (temperature, humidity) = (temperature?, humidity?);
    if humidity <= 0.0 {
        return None;
    }
    let celsius = matches!(
        unit.trim().to_lowercase().as_str(),
        "c" | "celsius" | "°c" | "degc" | "wmounit:degc"
    );
    let ratio = humidity.clamp(0.1, 100.0) / 100.0;
    let temp_c = if celsius {
        temperature
    } else {
        (temperature - 32.0) * 5.0 / 9.0
    };
    let (a, b) = (17.27, 237.7);
    let alpha = (a * temp_c) / (b + temp_c) + ratio.ln();
    let dewpoint_c = (b * alpha) / (a - alpha);
    Some(if celsius {
        dewpoint_c
    } else {
        (dewpoint_c * 9.0 / 5.0) + 32.0
    })
}

/// Humidity rounded to a 0-100 percentage (`fraction` scales 0-1 values).
pub fn normalize_humidity_percent(value: Option<f64>, fraction: bool) -> Option<i64> {
    let numeric = value?;
    let numeric = if fraction { numeric * 100.0 } else { numeric };
    Some(py::round(numeric) as i64)
}

pub fn normalize_temperature_pair(value: Option<f64>, unit: Option<&str>) -> TemperaturePair {
    let (fahrenheit, celsius) = normalize_temperature(value, unit);
    TemperaturePair { fahrenheit, celsius }
}

/// Dewpoint pair, calculated from temperature and humidity when the provider has none.
pub fn normalize_dewpoint_pair(
    dewpoint_value: Option<f64>,
    dewpoint_unit: Option<&str>,
    fallback_temperature_f: Option<f64>,
    humidity_percent: Option<f64>,
) -> TemperaturePair {
    let dewpoint = normalize_temperature_pair(dewpoint_value, dewpoint_unit);
    if dewpoint.fahrenheit.is_some() || dewpoint.celsius.is_some() {
        return dewpoint;
    }
    let dewpoint_f = calculate_dewpoint(fallback_temperature_f, humidity_percent, "fahrenheit");
    TemperaturePair {
        fahrenheit: dewpoint_f,
        celsius: convert_f_to_c(dewpoint_f),
    }
}

pub fn normalize_pressure_pair(value: Option<f64>, unit: Option<&str>) -> PressurePair {
    let (inches, millibars) = normalize_pressure(value, unit);
    PressurePair { inches, millibars }
}

/// Pressure in Pascals for NWS-compatible mapped payloads.
pub fn normalize_pressure_to_pascals(value: Option<f64>, unit: Option<&str>) -> Option<f64> {
    let numeric = value?;
    let unit = unit.unwrap_or("").trim().to_lowercase();
    Some(if unit.contains("hpa") || unit.contains("mb") {
        numeric * 100.0
    } else if unit.contains("pa") {
        numeric
    } else if unit.contains("inch") || unit == "in" || unit == "inhg" {
        numeric * 3386.39
    } else {
        numeric * 100.0
    })
}

/// Values already in millibars/hectopascals.
pub fn normalize_millibars(value: Option<f64>) -> PressurePair {
    PressurePair {
        inches: value.map(|v| v / MB_PER_INHG),
        millibars: value,
    }
}

fn canonical_wind_unit(unit: Option<&str>) -> Option<&str> {
    let text = unit.unwrap_or("").trim().to_lowercase();
    match text.as_str() {
        "m/s" | "meter/s" | "meters/s" | "metre/s" | "metres/s" => Some("wmoUnit:m_s-1"),
        "km/h" | "kmh" | "kph" => Some("wmoUnit:km_h-1"),
        "mph" | "mi/h" => Some("wmoUnit:mi_h-1"),
        "kn" | "kt" | "knot" | "knots" => Some("wmoUnit:kn"),
        _ => unit,
    }
}

pub fn normalize_speed_pair(value: Option<f64>, unit: Option<&str>) -> SpeedPair {
    if value.is_none() {
        return SpeedPair::default();
    }
    let (mph, kph) = convert_wind_speed_to_mph_and_kph(value, canonical_wind_unit(unit));
    SpeedPair { mph, kph }
}

/// Provider-native speed for text forecast fields, e.g. "10 mph".
pub fn format_speed(value: Option<f64>, unit_label: &str) -> Option<String> {
    Some(format!("{} {unit_label}", py::round(value?) as i64))
}

pub fn normalize_visibility_pair(
    value: Option<f64>,
    unit: Option<&str>,
    cap_miles: Option<f64>,
) -> VisibilityPair {
    let Some(numeric) = value else {
        return VisibilityPair::default();
    };
    let unit = unit.unwrap_or("").trim().to_lowercase().replace(' ', "_");
    let (mut miles, mut kilometers) = if unit.contains("ft") || unit.contains("feet") {
        let miles = numeric / 5280.0;
        (miles, miles * KM_PER_MILE)
    } else if unit.contains("km") || unit.contains("kilometer") || unit.contains("kilometre") {
        (numeric / KM_PER_MILE, numeric)
    } else if matches!(unit.as_str(), "mi" | "mile" | "miles") {
        (numeric, numeric * KM_PER_MILE)
    } else {
        (numeric / 1609.344, numeric / 1000.0)
    };
    if let Some(cap) = cap_miles {
        miles = miles.min(cap);
        kilometers = miles * KM_PER_MILE;
    }
    VisibilityPair {
        miles: Some(miles),
        kilometers: Some(kilometers),
    }
}

/// Split a feels-like value into wind chill (colder) or heat index (warmer).
pub fn classify_apparent_temperature(
    temperature_f: Option<f64>,
    apparent_f: Option<f64>,
    apparent_c: Option<f64>,
) -> ApparentTemperatureClassification {
    let (Some(apparent), Some(temperature)) = (apparent_f, temperature_f) else {
        return ApparentTemperatureClassification::default();
    };
    if apparent < temperature {
        ApparentTemperatureClassification {
            wind_chill_f: apparent_f,
            wind_chill_c: apparent_c,
            ..Default::default()
        }
    } else if apparent > temperature {
        ApparentTemperatureClassification {
            heat_index_f: apparent_f,
            heat_index_c: apparent_c,
            ..Default::default()
        }
    } else {
        ApparentTemperatureClassification::default()
    }
}

pub fn pirate_temperature_unit(units: &str) -> &'static str {
    if units == "us" {
        "F"
    } else {
        "C"
    }
}

pub fn pirate_wind_unit(units: &str) -> &'static str {
    match units {
        "us" | "uk2" => "mph",
        "ca" => "km/h",
        _ => "m/s",
    }
}

pub fn pirate_visibility_unit(units: &str) -> &'static str {
    if matches!(units, "us" | "uk2") {
        "mi"
    } else {
        "km"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn close(a: Option<f64>, b: f64) -> bool {
        a.is_some_and(|a| (a - b).abs() < 0.01)
    }

    #[test]
    fn temperature_pair_preserves_both_units() {
        let p = normalize_temperature_pair(Some(20.0), Some("°C"));
        assert_eq!(p.fahrenheit, Some(68.0));
        assert_eq!(p.celsius, Some(20.0));
    }

    #[test]
    fn humidity_supports_fraction_and_percent() {
        assert_eq!(normalize_humidity_percent(Some(0.655), true), Some(66));
        assert_eq!(normalize_humidity_percent(Some(72.5), false), Some(72));
        assert_eq!(normalize_humidity_percent(None, false), None);
    }

    #[test]
    fn dewpoint_prefers_provider_value() {
        let p = normalize_dewpoint_pair(Some(10.0), Some("C"), Some(70.0), Some(50.0));
        assert_eq!(p.celsius, Some(10.0));
        let p = normalize_dewpoint_pair(None, Some("F"), Some(70.0), Some(50.0));
        assert!(close(p.fahrenheit, 50.5));
        let p = normalize_dewpoint_pair(None, Some("F"), Some(70.0), Some(0.0));
        assert_eq!(p, TemperaturePair::default());
    }

    #[test]
    fn pressure_pairs_and_pascals() {
        assert_eq!(normalize_pressure_to_pascals(Some(1013.0), Some("hPa")), Some(101300.0));
        assert_eq!(normalize_pressure_to_pascals(Some(101300.0), Some("Pa")), Some(101300.0));
        assert!(close(
            normalize_pressure_to_pascals(Some(29.92), Some("inHg")),
            101320.79
        ));
        assert!(close(normalize_millibars(Some(1013.0)).inches, 29.91));
    }

    #[test]
    fn speed_pair_accepts_provider_labels() {
        let p = normalize_speed_pair(Some(10.0), Some("km/h"));
        assert!(close(p.mph, 6.21));
        assert_eq!(p.kph, Some(10.0));
        let p = normalize_speed_pair(Some(10.0), Some("m/s"));
        assert!(close(p.mph, 22.37));
        assert_eq!(format_speed(Some(10.5), "mph").as_deref(), Some("10 mph"));
        assert_eq!(format_speed(Some(11.5), "mph").as_deref(), Some("12 mph"));
    }

    #[test]
    fn visibility_capped_and_uncapped() {
        let p = normalize_visibility_pair(Some(80000.0), Some("ft"), Some(10.0));
        assert_eq!(p.miles, Some(10.0));
        let p = normalize_visibility_pair(Some(16.09344), Some("km"), None);
        assert!(close(p.miles, 10.0));
        let p = normalize_visibility_pair(Some(24140.16), None, None);
        assert!(close(p.miles, 15.0));
    }

    #[test]
    fn apparent_temperature_classification() {
        let c = classify_apparent_temperature(Some(30.0), Some(20.0), Some(-6.7));
        assert_eq!(c.wind_chill_f, Some(20.0));
        let c = classify_apparent_temperature(Some(90.0), Some(100.0), None);
        assert_eq!(c.heat_index_f, Some(100.0));
        let c = classify_apparent_temperature(Some(50.0), Some(50.0), None);
        assert_eq!(c, ApparentTemperatureClassification::default());
    }

    #[test]
    fn pirate_unit_groups() {
        assert_eq!(pirate_temperature_unit("us"), "F");
        assert_eq!(pirate_temperature_unit("si"), "C");
        assert_eq!(pirate_wind_unit("uk2"), "mph");
        assert_eq!(pirate_wind_unit("ca"), "km/h");
        assert_eq!(pirate_wind_unit("si"), "m/s");
        assert_eq!(pirate_visibility_unit("us"), "mi");
        assert_eq!(pirate_visibility_unit("ca"), "km");
    }
}
