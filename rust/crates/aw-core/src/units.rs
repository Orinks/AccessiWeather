//! Unit conversion and formatting, ported from `accessiweather.utils` and
//! `accessiweather.units`.

use crate::location::Location;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TemperatureUnit {
    Fahrenheit,
    Celsius,
    Both,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DisplayUnitSystem {
    Us,
    Uk,
    Ca,
    Si,
}

pub fn f_to_c(f: f64) -> f64 {
    (f - 32.0) * 5.0 / 9.0
}

pub fn c_to_f(c: f64) -> f64 {
    c * 9.0 / 5.0 + 32.0
}

pub fn resolve_auto_unit_system(location: Option<&Location>) -> DisplayUnitSystem {
    match location
        .and_then(|l| l.country_code.as_deref())
        .map(|c| c.to_uppercase())
        .as_deref()
    {
        Some("US") => DisplayUnitSystem::Us,
        Some("GB") => DisplayUnitSystem::Uk,
        Some("CA") => DisplayUnitSystem::Ca,
        _ => DisplayUnitSystem::Si,
    }
}

pub fn resolve_temperature_unit_preference(
    preference: &str,
    location: Option<&Location>,
) -> TemperatureUnit {
    match preference.trim().to_lowercase().as_str() {
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

pub fn resolve_display_unit_system(
    preference: &str,
    location: Option<&Location>,
) -> Option<DisplayUnitSystem> {
    if preference.trim().eq_ignore_ascii_case("auto") {
        Some(resolve_auto_unit_system(location))
    } else {
        None
    }
}

pub fn resolve_wind_display_unit_system(
    preference: &str,
    temperature_preference: &str,
    location: Option<&Location>,
) -> Option<DisplayUnitSystem> {
    match preference.trim().to_lowercase().as_str() {
        "mph" | "mi/h" => Some(DisplayUnitSystem::Us),
        "km/h" | "kmh" | "kph" => Some(DisplayUnitSystem::Ca),
        "m/s" | "mps" | "ms" | "meter/s" | "meters/s" | "metre/s" | "metres/s" => {
            Some(DisplayUnitSystem::Si)
        }
        "auto" => resolve_display_unit_system(temperature_preference, location),
        _ => None,
    }
}

fn fmt(value: f64, precision: usize) -> String {
    format!("{value:.precision$}")
}

/// Format a temperature honouring the preference. Whole numbers drop decimals
/// ("smart precision"), matching the Python behaviour.
pub fn format_temperature(
    temp_f: Option<f64>,
    temp_c: Option<f64>,
    unit: TemperatureUnit,
    precision: usize,
) -> String {
    let (f, c) = match (temp_f, temp_c) {
        (None, None) => return "N/A".into(),
        (Some(f), None) => (f, f_to_c(f)),
        (None, Some(c)) => (c_to_f(c), c),
        (Some(f), Some(c)) => (f, c),
    };
    let fp = if f == f.trunc() { 0 } else { precision };
    let cp = if c == c.trunc() { 0 } else { precision };
    match unit {
        TemperatureUnit::Fahrenheit => format!("{}°F", fmt(f, fp)),
        TemperatureUnit::Celsius => format!("{}°C", fmt(c, cp)),
        TemperatureUnit::Both => format!("{}°F ({}°C)", fmt(f, fp), fmt(c, cp)),
    }
}

pub fn format_wind_speed(
    mph: Option<f64>,
    kph: Option<f64>,
    unit: TemperatureUnit,
    precision: usize,
    system: Option<DisplayUnitSystem>,
) -> String {
    let (mph, kph) = match (mph, kph) {
        (None, None) => return "N/A".into(),
        (Some(m), None) => (m, m * 1.60934),
        (None, Some(k)) => (k * 0.621371, k),
        (Some(m), Some(k)) => (m, k),
    };
    match system {
        Some(DisplayUnitSystem::Us) | Some(DisplayUnitSystem::Uk) => {
            format!("{} mph", fmt(mph, precision))
        }
        Some(DisplayUnitSystem::Ca) => format!("{} km/h", fmt(kph, precision)),
        Some(DisplayUnitSystem::Si) => format!("{} m/s", fmt(kph / 3.6, precision)),
        None => match unit {
            TemperatureUnit::Fahrenheit => format!("{} mph", fmt(mph, precision)),
            TemperatureUnit::Celsius => format!("{} km/h", fmt(kph, precision)),
            TemperatureUnit::Both => {
                format!("{} mph ({} km/h)", fmt(mph, precision), fmt(kph, precision))
            }
        },
    }
}

pub fn format_pressure(
    inhg: Option<f64>,
    mb: Option<f64>,
    unit: TemperatureUnit,
    precision: usize,
    system: Option<DisplayUnitSystem>,
) -> String {
    let (inhg, mb) = match (inhg, mb) {
        (None, None) => return "N/A".into(),
        (Some(i), None) => (i, i * 33.8639),
        (None, Some(m)) => (m / 33.8639, m),
        (Some(i), Some(m)) => (i, m),
    };
    match system {
        Some(DisplayUnitSystem::Us) => format!("{} inHg", fmt(inhg, precision)),
        Some(DisplayUnitSystem::Ca) => format!("{} kPa", fmt(mb / 10.0, precision)),
        Some(DisplayUnitSystem::Uk) | Some(DisplayUnitSystem::Si) => {
            format!("{} hPa", fmt(mb, precision))
        }
        None => match unit {
            TemperatureUnit::Fahrenheit => format!("{} inHg", fmt(inhg, precision)),
            TemperatureUnit::Celsius => format!("{} hPa", fmt(mb, precision)),
            TemperatureUnit::Both => {
                format!("{} inHg ({} hPa)", fmt(inhg, precision), fmt(mb, precision))
            }
        },
    }
}

pub fn format_visibility(
    miles: Option<f64>,
    km: Option<f64>,
    unit: TemperatureUnit,
    precision: usize,
    system: Option<DisplayUnitSystem>,
) -> String {
    let (mi, km) = match (miles, km) {
        (None, None) => return "N/A".into(),
        (Some(m), None) => (m, m * 1.60934),
        (None, Some(k)) => (k * 0.621371, k),
        (Some(m), Some(k)) => (m, k),
    };
    match system {
        Some(DisplayUnitSystem::Us) | Some(DisplayUnitSystem::Uk) => {
            format!("{} mi", fmt(mi, precision))
        }
        Some(DisplayUnitSystem::Ca) | Some(DisplayUnitSystem::Si) => {
            format!("{} km", fmt(km, precision))
        }
        None => match unit {
            TemperatureUnit::Fahrenheit => format!("{} mi", fmt(mi, precision)),
            TemperatureUnit::Celsius => format!("{} km", fmt(km, precision)),
            TemperatureUnit::Both => {
                format!("{} mi ({} km)", fmt(mi, precision), fmt(km, precision))
            }
        },
    }
}

pub fn format_precipitation(
    inches: Option<f64>,
    mm: Option<f64>,
    unit: TemperatureUnit,
    precision: usize,
    system: Option<DisplayUnitSystem>,
) -> String {
    let (inches, mm) = match (inches, mm) {
        (None, None) => return "N/A".into(),
        (Some(i), None) => (i, i * 25.4),
        (None, Some(m)) => (m / 25.4, m),
        (Some(i), Some(m)) => (i, m),
    };
    match system {
        Some(DisplayUnitSystem::Us) => format!("{} in", fmt(inches, precision)),
        Some(_) => format!("{} mm", fmt(mm, precision)),
        None => match unit {
            TemperatureUnit::Fahrenheit => format!("{} in", fmt(inches, precision)),
            TemperatureUnit::Celsius => format!("{} mm", fmt(mm, precision)),
            TemperatureUnit::Both => {
                format!("{} in ({} mm)", fmt(inches, precision), fmt(mm, precision))
            }
        },
    }
}

const CARDINALS: [&str; 16] = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW",
    "NNW",
];

pub fn wind_direction_to_cardinal(degrees: Option<f64>) -> String {
    match degrees {
        None => "N/A".into(),
        Some(d) => {
            let normalized = d.rem_euclid(360.0);
            let index = ((normalized / 22.5).round() as usize) % 16;
            CARDINALS[index].to_string()
        }
    }
}

/// Magnus approximation, always computed in Celsius space. Returns Fahrenheit.
pub fn calculate_dewpoint_f(temp_f: f64, humidity: f64) -> Option<f64> {
    if humidity <= 0.0 {
        return None;
    }
    let ratio = humidity.clamp(0.1, 100.0) / 100.0;
    let temp_c = f_to_c(temp_f);
    let a = 17.27;
    let b = 237.7;
    let alpha = (a * temp_c) / (b + temp_c) + ratio.ln();
    let dew_c = (b * alpha) / (a - alpha);
    if dew_c.is_finite() {
        Some(c_to_f(dew_c))
    } else {
        None
    }
}

pub fn uv_description(uv: f64) -> &'static str {
    if uv < 3.0 {
        "Low"
    } else if uv < 6.0 {
        "Moderate"
    } else if uv < 8.0 {
        "High"
    } else if uv < 11.0 {
        "Very High"
    } else {
        "Extreme"
    }
}

/// Rothfusz heat index regression (NWS), in Fahrenheit.
pub fn heat_index_f(temp_f: f64, humidity: f64) -> Option<f64> {
    if temp_f < 80.0 || humidity < 40.0 {
        return None;
    }
    let t = temp_f;
    let r = humidity;
    let hi = -42.379 + 2.04901523 * t + 10.14333127 * r
        - 0.22475541 * t * r
        - 0.00683783 * t * t
        - 0.05481717 * r * r
        + 0.00122874 * t * t * r
        + 0.00085282 * t * r * r
        - 0.00000199 * t * t * r * r;
    Some(hi)
}

/// NWS wind chill formula, in Fahrenheit.
pub fn wind_chill_f(temp_f: f64, wind_mph: f64) -> Option<f64> {
    if temp_f > 50.0 || wind_mph <= 3.0 {
        return None;
    }
    let v = wind_mph.powf(0.16);
    Some(35.74 + 0.6215 * temp_f - 35.75 * v + 0.4275 * temp_f * v)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn temperature_uses_smart_precision() {
        assert_eq!(
            format_temperature(Some(72.0), None, TemperatureUnit::Both, 1),
            "72°F (22.2°C)"
        );
        assert_eq!(
            format_temperature(None, Some(20.0), TemperatureUnit::Fahrenheit, 1),
            "68°F"
        );
        assert_eq!(
            format_temperature(None, None, TemperatureUnit::Both, 1),
            "N/A"
        );
    }

    #[test]
    fn wind_speed_systems() {
        assert_eq!(
            format_wind_speed(Some(10.0), None, TemperatureUnit::Both, 0, None),
            "10 mph (16 km/h)"
        );
        assert_eq!(
            format_wind_speed(
                Some(36.0),
                None,
                TemperatureUnit::Both,
                1,
                Some(DisplayUnitSystem::Si)
            ),
            "16.1 m/s"
        );
    }

    #[test]
    fn cardinal_directions() {
        assert_eq!(wind_direction_to_cardinal(Some(0.0)), "N");
        assert_eq!(wind_direction_to_cardinal(Some(90.0)), "E");
        assert_eq!(wind_direction_to_cardinal(Some(359.0)), "N");
        assert_eq!(wind_direction_to_cardinal(Some(225.0)), "SW");
    }

    #[test]
    fn dewpoint_is_below_temperature() {
        let dew = calculate_dewpoint_f(80.0, 50.0).unwrap();
        assert!(dew > 55.0 && dew < 65.0, "{dew}");
        assert!(calculate_dewpoint_f(80.0, 0.0).is_none());
    }

    #[test]
    fn auto_unit_preference() {
        let us = Location::new("x", 0.0, 0.0).with_country("US");
        let de = Location::new("x", 0.0, 0.0).with_country("DE");
        assert_eq!(
            resolve_temperature_unit_preference("auto", Some(&us)),
            TemperatureUnit::Fahrenheit
        );
        assert_eq!(
            resolve_temperature_unit_preference("auto", Some(&de)),
            TemperatureUnit::Celsius
        );
        assert_eq!(
            resolve_temperature_unit_preference("both", None),
            TemperatureUnit::Both
        );
    }
}
