//! Unit normalization for Open-Meteo payloads, ported from
//! `accessiweather.weather_client_openmeteo_units`.

use aw_core::provider_normalization::normalize_visibility_pair;

pub const CM_PER_INCH: f64 = 2.54;
pub const FEET_PER_METER: f64 = 3.28084;
pub const INCHES_PER_FOOT: f64 = 12.0;
pub const VISIBILITY_CAP_MILES: f64 = 10.0;

fn unit_text(unit: Option<&str>) -> String {
    unit.unwrap_or("").trim().to_lowercase().replace(' ', "_")
}

fn has_any(text: &str, needles: &[&str]) -> bool {
    needles.iter().any(|n| text.contains(n))
}

/// Snow depth as (inches, centimeters); unitless values are meters.
pub fn normalize_snow_depth_to_inches_and_cm(
    value: Option<f64>,
    unit: Option<&str>,
) -> (Option<f64>, Option<f64>) {
    let Some(numeric) = value else {
        return (None, None);
    };
    let unit = unit_text(unit);
    let inches = if has_any(&unit, &["ft", "feet"]) {
        numeric * INCHES_PER_FOOT
    } else if has_any(&unit, &["mm", "millimeter", "millimetre"]) {
        numeric / 25.4
    } else if has_any(&unit, &["cm", "centimeter", "centimetre"]) {
        numeric / CM_PER_INCH
    } else if matches!(unit.as_str(), "in" | "inch" | "inches") {
        numeric
    } else {
        numeric * FEET_PER_METER * INCHES_PER_FOOT
    };
    (Some(inches), Some(inches * CM_PER_INCH))
}

/// Precipitation as (inches, millimeters); unitless values are inches.
pub fn normalize_precipitation_to_inches_and_mm(
    value: Option<f64>,
    unit: Option<&str>,
) -> (Option<f64>, Option<f64>) {
    let Some(numeric) = value else {
        return (None, None);
    };
    let unit = unit_text(unit);
    let inches = if has_any(&unit, &["mm", "millimeter", "millimetre"]) {
        numeric / 25.4
    } else if has_any(&unit, &["cm", "centimeter", "centimetre"]) {
        numeric / CM_PER_INCH
    } else {
        numeric
    };
    (Some(inches), Some(inches * 25.4))
}

/// Height in feet; unitless values are meters.
pub fn normalize_height_to_feet(value: Option<f64>, unit: Option<&str>) -> Option<f64> {
    let numeric = value?;
    let unit = unit_text(unit);
    Some(if has_any(&unit, &["ft", "feet"]) {
        numeric
    } else if has_any(&unit, &["km", "kilometer", "kilometre"]) {
        numeric * 1000.0 * FEET_PER_METER
    } else {
        numeric * FEET_PER_METER
    })
}

/// Visibility as (miles, kilometers), capped at 10 miles.
pub fn normalize_visibility_to_miles_and_km(
    value: Option<f64>,
    unit: Option<&str>,
) -> (Option<f64>, Option<f64>) {
    let v = normalize_visibility_pair(value, unit, Some(VISIBILITY_CAP_MILES));
    (v.miles, v.kilometers)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn snow_depth_units() {
        assert_eq!(normalize_snow_depth_to_inches_and_cm(Some(2.0), Some("inch")).0, Some(2.0));
        assert_eq!(normalize_snow_depth_to_inches_and_cm(Some(1.0), Some("ft")).0, Some(12.0));
        let (inches, _) = normalize_snow_depth_to_inches_and_cm(Some(0.1), Some("m"));
        assert!((inches.unwrap() - 3.937).abs() < 0.001);
        assert_eq!(normalize_snow_depth_to_inches_and_cm(None, None), (None, None));
    }

    #[test]
    fn precipitation_and_height() {
        assert_eq!(normalize_precipitation_to_inches_and_mm(Some(25.4), Some("mm")).0, Some(1.0));
        assert_eq!(normalize_precipitation_to_inches_and_mm(Some(0.5), Some("inch")).1, Some(12.7));
        assert_eq!(normalize_height_to_feet(Some(100.0), Some("ft")), Some(100.0));
        assert!((normalize_height_to_feet(Some(1000.0), Some("m")).unwrap() - 3280.84).abs() < 1e-9);
    }

    #[test]
    fn visibility_is_capped() {
        let (miles, km) = normalize_visibility_to_miles_and_km(Some(80000.0), Some("ft"));
        assert_eq!(miles, Some(10.0));
        assert!((km.unwrap() - 16.09344).abs() < 1e-9);
    }
}
