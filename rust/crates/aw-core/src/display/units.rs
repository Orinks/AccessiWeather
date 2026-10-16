//! Unit resolution and measurement formatting.
//!
//! Ports `accessiweather/units.py`, `utils/temperature_utils.py` and
//! `utils/unit_utils.py`.

use crate::display::pyfmt::{fixed, round_int};
use crate::location::Location;

/// `TemperatureUnit`: the effective display preference.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TemperatureUnit {
    Fahrenheit,
    Celsius,
    Both,
}

/// `DisplayUnitSystem`: a single-unit display system chosen per location.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DisplayUnitSystem {
    Us,
    Uk,
    Ca,
    Si,
}

impl DisplayUnitSystem {
    pub fn as_str(self) -> &'static str {
        match self {
            DisplayUnitSystem::Us => "us",
            DisplayUnitSystem::Uk => "uk",
            DisplayUnitSystem::Ca => "ca",
            DisplayUnitSystem::Si => "si",
        }
    }
}

/// `resolve_auto_unit_system`.
pub fn resolve_auto_unit_system(location: Option<&Location>) -> DisplayUnitSystem {
    let code = location
        .and_then(|l| l.country_code.as_deref())
        .unwrap_or("")
        .to_uppercase();
    match code.as_str() {
        "US" => DisplayUnitSystem::Us,
        "GB" => DisplayUnitSystem::Uk,
        "CA" => DisplayUnitSystem::Ca,
        _ => DisplayUnitSystem::Si,
    }
}

/// `(preference or default).strip().lower()`
fn normalized(preference: &str, default: &str) -> String {
    let p = if preference.is_empty() {
        default
    } else {
        preference
    };
    p.trim().to_lowercase()
}

/// `resolve_temperature_unit_preference`.
pub fn resolve_temperature_unit_preference(
    preference: &str,
    location: Option<&Location>,
) -> TemperatureUnit {
    match normalized(preference, "both").as_str() {
        "fahrenheit" | "f" => TemperatureUnit::Fahrenheit,
        "celsius" | "c" => TemperatureUnit::Celsius,
        "auto" => {
            if resolve_auto_unit_system(location) == DisplayUnitSystem::Us {
                TemperatureUnit::Fahrenheit
            } else {
                TemperatureUnit::Celsius
            }
        }
        _ => TemperatureUnit::Both,
    }
}

/// `resolve_display_unit_system`.
pub fn resolve_display_unit_system(
    preference: &str,
    location: Option<&Location>,
) -> Option<DisplayUnitSystem> {
    (normalized(preference, "both") == "auto").then(|| resolve_auto_unit_system(location))
}

/// `resolve_wind_display_unit_system`.
pub fn resolve_wind_display_unit_system(
    preference: &str,
    temperature_preference: &str,
    location: Option<&Location>,
) -> Option<DisplayUnitSystem> {
    match normalized(preference, "auto").as_str() {
        "mph" | "mi/h" => Some(DisplayUnitSystem::Us),
        "km/h" | "kmh" | "kph" => Some(DisplayUnitSystem::Ca),
        "m/s" | "mps" | "ms" | "meter/s" | "meters/s" | "metre/s" | "metres/s" => {
            Some(DisplayUnitSystem::Si)
        }
        "auto" => resolve_display_unit_system(temperature_preference, location),
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// temperature_utils
// ---------------------------------------------------------------------------

pub fn celsius_to_fahrenheit(celsius: f64) -> f64 {
    (celsius * 9.0 / 5.0) + 32.0
}

pub fn fahrenheit_to_celsius(fahrenheit: f64) -> f64 {
    (fahrenheit - 32.0) * 5.0 / 9.0
}

/// `calculate_dewpoint` (Magnus approximation). `celsius` selects the unit of
/// both the input temperature and the result.
pub fn calculate_dewpoint(temperature: f64, humidity: f64, celsius: bool) -> Option<f64> {
    if humidity <= 0.0 {
        return None;
    }
    let humidity_ratio = humidity.clamp(0.1, 100.0) / 100.0;
    let temp_c = if celsius {
        temperature
    } else {
        fahrenheit_to_celsius(temperature)
    };
    let (a, b) = (17.27, 237.7);
    let alpha = (a * temp_c) / (b + temp_c) + humidity_ratio.ln();
    let dewpoint_c = (b * alpha) / (a - alpha);
    Some(if celsius {
        dewpoint_c
    } else {
        celsius_to_fahrenheit(dewpoint_c)
    })
}

fn smart_precision(value: f64, precision: usize) -> usize {
    // `value == int(value)`: whole numbers drop their decimals.
    if value == value.trunc() {
        0
    } else {
        precision
    }
}

/// `format_temperature` with `smart_precision=True`.
pub fn format_temperature(
    temperature: Option<f64>,
    unit: TemperatureUnit,
    temperature_c: Option<f64>,
    precision: usize,
) -> String {
    let (f, c) = match (temperature, temperature_c) {
        (None, None) => return "N/A".into(),
        (None, Some(c)) => (celsius_to_fahrenheit(c), c),
        (Some(f), None) => (f, fahrenheit_to_celsius(f)),
        (Some(f), Some(c)) => (f, c),
    };
    let f_str = fixed(f, smart_precision(f, precision));
    let c_str = fixed(c, smart_precision(c, precision));
    match unit {
        TemperatureUnit::Fahrenheit => format!("{f_str}°F"),
        TemperatureUnit::Celsius => format!("{c_str}°C"),
        TemperatureUnit::Both => format!("{f_str}°F ({c_str}°C)"),
    }
}

// ---------------------------------------------------------------------------
// unit_utils
// ---------------------------------------------------------------------------

/// `format_wind_speed`.
pub fn format_wind_speed(
    mph: Option<f64>,
    unit: TemperatureUnit,
    kph: Option<f64>,
    precision: usize,
    unit_system: Option<DisplayUnitSystem>,
) -> String {
    let (mph, kph) = match (mph, kph) {
        (None, None) => return "N/A".into(),
        (None, Some(k)) => (k * 0.621371, k),
        (Some(m), None) => (m, m * 1.60934),
        (Some(m), Some(k)) => (m, k),
    };
    match unit_system {
        Some(DisplayUnitSystem::Us | DisplayUnitSystem::Uk) => {
            return format!("{} mph", fixed(mph, precision))
        }
        Some(DisplayUnitSystem::Ca) => return format!("{} km/h", fixed(kph, precision)),
        Some(DisplayUnitSystem::Si) => return format!("{} m/s", fixed(kph / 3.6, precision)),
        None => {}
    }
    match unit {
        TemperatureUnit::Fahrenheit => format!("{} mph", fixed(mph, precision)),
        TemperatureUnit::Celsius => format!("{} km/h", fixed(kph, precision)),
        TemperatureUnit::Both => format!(
            "{} mph ({} km/h)",
            fixed(mph, precision),
            fixed(kph, precision)
        ),
    }
}

/// `format_pressure`.
pub fn format_pressure(
    inhg: Option<f64>,
    unit: TemperatureUnit,
    mb: Option<f64>,
    precision: usize,
    unit_system: Option<DisplayUnitSystem>,
) -> String {
    let (inhg, mb) = match (inhg, mb) {
        (None, None) => return "N/A".into(),
        (None, Some(m)) => (m / 33.8639, m),
        (Some(i), None) => (i, i * 33.8639),
        (Some(i), Some(m)) => (i, m),
    };
    match unit_system {
        Some(DisplayUnitSystem::Us) => return format!("{} inHg", fixed(inhg, precision)),
        Some(DisplayUnitSystem::Ca) => return format!("{} kPa", fixed(mb / 10.0, precision)),
        Some(DisplayUnitSystem::Uk | DisplayUnitSystem::Si) => {
            return format!("{} hPa", fixed(mb, precision))
        }
        None => {}
    }
    match unit {
        TemperatureUnit::Fahrenheit => format!("{} inHg", fixed(inhg, precision)),
        TemperatureUnit::Celsius => format!("{} hPa", fixed(mb, precision)),
        TemperatureUnit::Both => format!(
            "{} inHg ({} hPa)",
            fixed(inhg, precision),
            fixed(mb, precision)
        ),
    }
}

/// `format_visibility`.
pub fn format_visibility(
    miles: Option<f64>,
    unit: TemperatureUnit,
    km: Option<f64>,
    precision: usize,
    unit_system: Option<DisplayUnitSystem>,
) -> String {
    let (miles, km) = match (miles, km) {
        (None, None) => return "N/A".into(),
        (None, Some(k)) => (k * 0.621371, k),
        (Some(m), None) => (m, m * 1.60934),
        (Some(m), Some(k)) => (m, k),
    };
    match unit_system {
        Some(DisplayUnitSystem::Us | DisplayUnitSystem::Uk) => {
            return format!("{} mi", fixed(miles, precision))
        }
        Some(DisplayUnitSystem::Ca | DisplayUnitSystem::Si) => {
            return format!("{} km", fixed(km, precision))
        }
        None => {}
    }
    match unit {
        TemperatureUnit::Fahrenheit => format!("{} mi", fixed(miles, precision)),
        TemperatureUnit::Celsius => format!("{} km", fixed(km, precision)),
        TemperatureUnit::Both => format!(
            "{} mi ({} km)",
            fixed(miles, precision),
            fixed(km, precision)
        ),
    }
}

/// `format_precipitation`.
pub fn format_precipitation(
    inches: Option<f64>,
    unit: TemperatureUnit,
    mm: Option<f64>,
    precision: usize,
    unit_system: Option<DisplayUnitSystem>,
) -> String {
    let (inches, mm) = match (inches, mm) {
        (None, None) => return "N/A".into(),
        (None, Some(m)) => (m / 25.4, m),
        (Some(i), None) => (i, i * 25.4),
        (Some(i), Some(m)) => (i, m),
    };
    match unit_system {
        Some(DisplayUnitSystem::Us) => return format!("{} in", fixed(inches, precision)),
        Some(_) => return format!("{} mm", fixed(mm, precision)),
        None => {}
    }
    match unit {
        TemperatureUnit::Fahrenheit => format!("{} in", fixed(inches, precision)),
        TemperatureUnit::Celsius => format!("{} mm", fixed(mm, precision)),
        TemperatureUnit::Both => format!(
            "{} in ({} mm)",
            fixed(inches, precision),
            fixed(mm, precision)
        ),
    }
}

const DIRECTIONS: [&str; 16] = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW",
    "NNW",
];

/// `convert_wind_direction_to_cardinal`.
pub fn convert_wind_direction_to_cardinal(degrees: f64) -> &'static str {
    DIRECTIONS[round_int(degrees / 22.5).rem_euclid(16) as usize]
}

/// `format_combined_wind` (e.g. "15 mph NW").
pub fn format_combined_wind(
    speed: Option<f64>,
    direction: Option<&str>,
    speed_unit: &str,
) -> String {
    let Some(speed) = speed else {
        return "N/A".into();
    };
    if speed == 0.0 {
        return "Calm".into();
    }
    let speed_str = format!("{} {speed_unit}", round_int(speed));
    match direction.filter(|d| !d.is_empty() && *d != "N/A") {
        Some(d) => format!("{speed_str} {d}"),
        None => speed_str,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn temperature_smart_precision() {
        let both = TemperatureUnit::Both;
        assert_eq!(
            format_temperature(Some(72.0), both, None, 1),
            "72°F (22.2°C)"
        );
        assert_eq!(
            format_temperature(Some(72.5), both, Some(22.5), 1),
            "72.5°F (22.5°C)"
        );
        assert_eq!(
            format_temperature(None, TemperatureUnit::Fahrenheit, Some(0.0), 1),
            "32°F"
        );
        assert_eq!(format_temperature(None, both, None, 1), "N/A");
    }

    #[test]
    fn unit_systems_override_preference() {
        let f = TemperatureUnit::Fahrenheit;
        assert_eq!(
            format_wind_speed(Some(10.0), f, None, 1, Some(DisplayUnitSystem::Si)),
            "4.5 m/s"
        );
        assert_eq!(
            format_pressure(Some(30.0), f, None, 2, Some(DisplayUnitSystem::Ca)),
            "101.59 kPa"
        );
        assert_eq!(
            format_visibility(Some(10.0), f, None, 1, Some(DisplayUnitSystem::Uk)),
            "10.0 mi"
        );
        assert_eq!(
            format_precipitation(Some(0.5), f, None, 2, Some(DisplayUnitSystem::Uk)),
            "12.70 mm"
        );
    }

    #[test]
    fn cardinal_rounding_is_bankers() {
        assert_eq!(convert_wind_direction_to_cardinal(0.0), "N");
        assert_eq!(convert_wind_direction_to_cardinal(11.25), "N");
        assert_eq!(convert_wind_direction_to_cardinal(33.75), "NE");
        assert_eq!(convert_wind_direction_to_cardinal(350.0), "N");
    }

    #[test]
    fn preferences_resolve_like_python() {
        let us = Location::new("x", 0.0, 0.0).with_country("US");
        let gb = Location::new("x", 0.0, 0.0).with_country("GB");
        assert_eq!(
            resolve_temperature_unit_preference("auto", Some(&us)),
            TemperatureUnit::Fahrenheit
        );
        assert_eq!(
            resolve_temperature_unit_preference("auto", Some(&gb)),
            TemperatureUnit::Celsius
        );
        assert_eq!(
            resolve_temperature_unit_preference("", None),
            TemperatureUnit::Both
        );
        assert_eq!(
            resolve_wind_display_unit_system("auto", "auto", Some(&gb)),
            Some(DisplayUnitSystem::Uk)
        );
        assert_eq!(
            resolve_wind_display_unit_system("KPH", "f", None),
            Some(DisplayUnitSystem::Ca)
        );
        assert_eq!(resolve_wind_display_unit_system("auto", "both", None), None);
    }

    #[test]
    fn dewpoint_magnus() {
        let dp = calculate_dewpoint(70.0, 50.0, false).unwrap();
        assert!((dp - 50.5).abs() < 0.3, "{dp}");
        assert!(calculate_dewpoint(70.0, 0.0, false).is_none());
    }
}
