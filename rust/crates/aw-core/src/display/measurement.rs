//! Measurement formatting for presentation output.
//!
//! Port of `display/presentation/measurement_formatters.py`.

use crate::display::thermal::{sanitize_thermal_comfort_readings, ThermalInputs};
use crate::display::units::{
    calculate_dewpoint, format_pressure, format_temperature, format_visibility, format_wind_speed,
    DisplayUnitSystem, TemperatureUnit,
};
use crate::model::{CurrentConditions, ForecastPeriod, HourlyForecastPeriod};

/// `format_temperature_pair`.
pub fn format_temperature_pair(
    temp_f: Option<f64>,
    temp_c: Option<f64>,
    unit_pref: TemperatureUnit,
    precision: usize,
) -> Option<String> {
    if temp_f.is_none() && temp_c.is_none() {
        return None;
    }
    Some(format_temperature(temp_f, unit_pref, temp_c, precision))
}

/// `format_wind`: direction and speed, "Calm" when negligible.
pub fn format_wind(
    current: &CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: usize,
    unit_system: Option<DisplayUnitSystem>,
) -> Option<String> {
    if current.wind_speed_mph.is_none()
        && current.wind_speed_kph.is_none()
        && current.wind_direction.is_none()
    {
        return None;
    }
    let speed_mph = current
        .wind_speed_mph
        .or(current.wind_speed_kph.map(|k| k * 0.621371));
    if speed_mph.is_some_and(|s| s.abs() < 0.5) {
        return Some("Calm".into());
    }
    let direction = current.wind_direction.clone().filter(|d| !d.is_empty());
    // format_wind_speed never returns an empty string, so a direction always
    // gets "at <speed>" - even "at N/A" when only the direction is known.
    let speed = format_wind_speed(
        current.wind_speed_mph,
        unit_pref,
        current.wind_speed_kph,
        precision,
        unit_system,
    );
    Some(match direction {
        Some(d) => format!("{d} at {speed}"),
        None => speed,
    })
}

/// `format_dewpoint`: reuse or calculate the dewpoint.
pub fn format_dewpoint(
    current: &CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: usize,
) -> Option<String> {
    let (mut dewpoint_f, mut dewpoint_c) = (current.dewpoint_f, current.dewpoint_c);
    if dewpoint_f.is_none() && dewpoint_c.is_none() {
        let (Some(t), Some(h)) = (current.temperature_f, current.humidity) else {
            return None;
        };
        let dp = calculate_dewpoint(t, h as f64, false)?;
        dewpoint_f = Some(dp);
        dewpoint_c = Some((dp - 32.0) * 5.0 / 9.0);
    }
    Some(format_temperature(dewpoint_f, unit_pref, dewpoint_c, precision))
}

/// `format_pressure_value`.
pub fn format_pressure_value(
    current: &CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: usize,
    unit_system: Option<DisplayUnitSystem>,
) -> Option<String> {
    if current.pressure_in.is_none() && current.pressure_mb.is_none() {
        return None;
    }
    let pressure_in = current
        .pressure_in
        .or(current.pressure_mb.map(|mb| mb / 33.8639));
    Some(format_pressure(
        pressure_in,
        unit_pref,
        current.pressure_mb,
        precision,
        unit_system,
    ))
}

/// `format_visibility_value`.
pub fn format_visibility_value(
    current: &CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: usize,
    unit_system: Option<DisplayUnitSystem>,
) -> Option<String> {
    if current.visibility_miles.is_none() && current.visibility_km.is_none() {
        return None;
    }
    Some(format_visibility(
        current.visibility_miles,
        unit_pref,
        current.visibility_km,
        precision,
        unit_system,
    ))
}

/// `select_feels_like_temperature`: wind chill when cold and windy, heat
/// index when hot and humid, else the reported feels-like or the actual
/// temperature. Returns `(feels_f, feels_c, reason)`.
pub fn select_feels_like_temperature(
    current: &CurrentConditions,
) -> (Option<f64>, Option<f64>, Option<&'static str>) {
    let temp_f = current
        .temperature_f
        .or(current.temperature_c.map(|c| (c * 9.0 / 5.0) + 32.0));
    let wind_mph = current
        .wind_speed_mph
        .or(current.wind_speed_kph.map(|k| k * 0.621371));
    let humidity = current.humidity.map(|h| h as f64);
    let comfort = sanitize_thermal_comfort_readings(ThermalInputs {
        temperature_f: temp_f,
        temperature_c: current.temperature_c,
        humidity,
        feels_like_f: current.feels_like_f,
        feels_like_c: current.feels_like_c,
        wind_chill_f: current.wind_chill_f,
        wind_chill_c: current.wind_chill_c,
        heat_index_f: current.heat_index_f,
        heat_index_c: current.heat_index_c,
    });

    if let (Some(t), Some(w), Some(_)) = (temp_f, wind_mph, comfort.wind_chill_f) {
        if t < 50.0 && w > 3.0 {
            return (comfort.wind_chill_f, comfort.wind_chill_c, Some("wind chill"));
        }
    }
    if let (Some(t), Some(h), Some(_)) = (temp_f, humidity, comfort.heat_index_f) {
        if t > 80.0 && h > 40.0 {
            return (comfort.heat_index_f, comfort.heat_index_c, Some("heat index"));
        }
    }
    if comfort.feels_like_f.is_some() || comfort.feels_like_c.is_some() {
        return (comfort.feels_like_f, comfort.feels_like_c, None);
    }
    (current.temperature_f, current.temperature_c, None)
}

fn f_and_c(temp: f64, unit: &str) -> (f64, f64) {
    if unit == "F" {
        (temp, (temp - 32.0) * 5.0 / 9.0)
    } else {
        ((temp * 9.0 / 5.0) + 32.0, temp)
    }
}

fn unit_code(unit: &str) -> String {
    if unit.is_empty() {
        "F".into()
    } else {
        unit.to_uppercase()
    }
}

/// `format_forecast_temperature`: "High / Low" when a low is present.
pub fn format_forecast_temperature(
    period: &ForecastPeriod,
    unit_pref: TemperatureUnit,
    precision: usize,
) -> Option<String> {
    let temp = period.temperature?;
    let unit = unit_code(&period.temperature_unit);
    let (f, c) = f_and_c(temp, &unit);
    let high = format_temperature(Some(f), unit_pref, Some(c), precision);
    match period.temperature_low {
        Some(low) => {
            let (lf, lc) = f_and_c(low, &unit);
            let low = format_temperature(Some(lf), unit_pref, Some(lc), precision);
            Some(format!("{high} / {low}"))
        }
        None => Some(high),
    }
}

fn filled(s: &Option<String>) -> Option<&str> {
    s.as_deref().filter(|s| !s.is_empty())
}

/// `format_period_wind`.
pub fn format_period_wind(
    period: &ForecastPeriod,
    unit_pref: TemperatureUnit,
    unit_system: Option<DisplayUnitSystem>,
) -> Option<String> {
    if filled(&period.wind_speed).is_none() && filled(&period.wind_direction).is_none() {
        return None;
    }
    let mut parts: Vec<String> = Vec::new();
    if let Some(d) = filled(&period.wind_direction) {
        parts.push(d.to_string());
    }
    if let Some(mph) = period.wind_speed_mph {
        parts.push(format_wind_speed(Some(mph), unit_pref, None, 0, unit_system));
    } else if let Some(s) = filled(&period.wind_speed) {
        parts.push(s.to_string());
    }
    (!parts.is_empty()).then(|| parts.join(" "))
}

/// `format_period_temperature` (hourly).
pub fn format_period_temperature(
    period: &HourlyForecastPeriod,
    unit_pref: TemperatureUnit,
    precision: usize,
) -> Option<String> {
    let temp = period.temperature?;
    let (f, c) = f_and_c(temp, &unit_code(&period.temperature_unit));
    Some(format_temperature(Some(f), unit_pref, Some(c), precision))
}

/// `get_uv_description`.
pub fn get_uv_description(uv_index: f64) -> &'static str {
    if uv_index < 3.0 {
        "Low"
    } else if uv_index < 6.0 {
        "Moderate"
    } else if uv_index < 8.0 {
        "High"
    } else if uv_index < 11.0 {
        "Very High"
    } else {
        "Extreme"
    }
}

/// `get_temperature_precision`: one decimal everywhere; smart precision
/// drops ".0" for whole values.
pub fn get_temperature_precision(_unit_pref: TemperatureUnit) -> usize {
    1
}

/// `format_temperature_with_feels_like`: "75°F (feels like 82°F)" when the
/// apparent temperature differs by at least 3°F, plus the reason.
pub fn format_temperature_with_feels_like(
    current: &CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: usize,
) -> (String, Option<String>) {
    const DIFFERENCE_THRESHOLD: f64 = 3.0;
    let Some(temp_str) =
        format_temperature_pair(current.temperature_f, current.temperature_c, unit_pref, precision)
    else {
        return ("N/A".into(), None);
    };
    let (mut feels_f, feels_c, selection_reason) = select_feels_like_temperature(current);
    if feels_f.is_none() && feels_c.is_none() {
        return (temp_str, None);
    }
    let actual_f = current
        .temperature_f
        .or(current.temperature_c.map(|c| (c * 9.0 / 5.0) + 32.0));
    if feels_f.is_none() {
        feels_f = feels_c.map(|c| (c * 9.0 / 5.0) + 32.0);
    }
    let (Some(actual), Some(feels)) = (actual_f, feels_f) else {
        return (temp_str, None);
    };
    let diff = feels - actual;
    if diff.abs() < DIFFERENCE_THRESHOLD {
        return (temp_str, None);
    }
    let Some(feels_str) = format_temperature_pair(feels_f, feels_c, unit_pref, precision) else {
        return (temp_str, None);
    };
    let combined = format!("{temp_str} (feels like {feels_str})");
    let reason = match selection_reason {
        Some(r) => Some(format!("due to {r}")),
        None => feels_like_reason(current, diff).map(str::to_string),
    };
    (combined, reason)
}

/// `_get_feels_like_reason`.
fn feels_like_reason(current: &CurrentConditions, diff_f: f64) -> Option<&'static str> {
    let humidity = current.humidity;
    if diff_f > 0.0 {
        return match humidity {
            Some(h) if h >= 70 => Some("due to high humidity"),
            Some(h) if h >= 40 => Some("due to humidity"),
            _ => None,
        };
    }
    match current.wind_speed_mph {
        Some(w) if w >= 15.0 => return Some("due to strong wind"),
        Some(w) if w >= 3.0 => return Some("due to wind"),
        _ => {}
    }
    if current.temperature_f.is_some_and(|t| t < 50.0) && humidity.is_some_and(|h| h < 30) {
        return Some("due to dry air");
    }
    None
}

/// `format_hourly_wind`: "<direction> at <speed>" when both are known.
pub fn format_hourly_wind(
    period: &HourlyForecastPeriod,
    unit_pref: TemperatureUnit,
    unit_system: Option<DisplayUnitSystem>,
) -> Option<String> {
    let direction = filled(&period.wind_direction)?;
    let speed = if let Some(mph) = period.wind_speed_mph {
        format_wind_speed(Some(mph), unit_pref, None, 0, unit_system)
    } else {
        filled(&period.wind_speed)?.to_string()
    };
    Some(format!("{direction} at {speed}"))
}
