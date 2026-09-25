//! The weather data an explanation sends.
//!
//! Ports `ui/dialogs/explanation_generation.py`: the explainer payload built
//! from the app's current weather and the location's time context.

use aw_core::model::{CurrentConditions, Location, WeatherData};
use aw_core::units::{
    format_pressure, format_temperature, format_visibility, format_wind_speed,
    resolve_display_unit_system, resolve_temperature_unit_preference,
    resolve_wind_display_unit_system, DisplayUnitSystem, TemperatureUnit,
};
use chrono::{DateTime, Timelike, Utc};
use serde_json::{json, Map, Value};

fn formatted_or_none(value: String) -> Value {
    if value == "N/A" {
        Value::Null
    } else {
        Value::String(value)
    }
}

fn num(value: Option<f64>) -> Value {
    value.map_or(Value::Null, Value::from)
}

fn opt_str(value: &Option<String>) -> Value {
    value.clone().map_or(Value::Null, Value::String)
}

/// `build_current_weather_payload`: the dict `AiExplainer::explain_weather`
/// receives. `temperature_unit_preference` and `wind_speed_unit_preference`
/// are the `temperature_unit` and `wind_speed_unit` settings.
pub fn build_current_weather_payload(
    weather: &WeatherData,
    temperature_unit_preference: &str,
    wind_speed_unit_preference: &str,
    location: Option<&Location>,
) -> Map<String, Value> {
    let default_current = CurrentConditions::default();
    let current = weather.current.as_ref().unwrap_or(&default_current);
    let unit = resolve_temperature_unit_preference(temperature_unit_preference, location);
    let system = resolve_display_unit_system(temperature_unit_preference, location);
    let wind_system = resolve_wind_display_unit_system(
        wind_speed_unit_preference,
        temperature_unit_preference,
        location,
    );
    let (temperature, temperature_unit) = temperature_for_prompt(current, unit);

    let mut payload = Map::new();
    let mut put = |key: &str, value: Value| {
        payload.insert(key.to_string(), value);
    };
    put("temperature", num(temperature));
    put("temperature_unit", json!(temperature_unit));
    put(
        "temperature_text",
        formatted_or_none(format_temperature(
            current.temperature_f,
            current.temperature_c,
            unit,
            1,
        )),
    );
    put("conditions", opt_str(&current.condition));
    put(
        "humidity",
        current.humidity.map_or(Value::Null, Value::from),
    );
    put(
        "wind_speed",
        num(wind_speed_for_prompt(current, unit, wind_system)),
    );
    put("wind_speed_unit", json!(wind_unit_label(unit, wind_system)));
    put(
        "wind_text",
        formatted_or_none(format_wind_speed(
            current.wind_speed_mph,
            current.wind_speed_kph,
            unit,
            1,
            wind_system,
        )),
    );
    put("wind_direction", opt_str(&current.wind_direction));
    put(
        "visibility",
        num(visibility_for_prompt(current, unit, system)),
    );
    put(
        "visibility_unit",
        json!(visibility_unit_label(unit, system)),
    );
    put(
        "visibility_text",
        formatted_or_none(format_visibility(
            current.visibility_miles,
            current.visibility_km,
            unit,
            1,
            system,
        )),
    );
    put("pressure", num(pressure_for_prompt(current, unit, system)));
    put("pressure_unit", json!(pressure_unit_label(unit, system)));
    put(
        "pressure_text",
        formatted_or_none(format_pressure(
            current.pressure_in,
            current.pressure_mb,
            unit,
            2,
            system,
        )),
    );

    let alerts: Vec<Value> = weather
        .alerts
        .iter()
        .flat_map(|a| &a.alerts)
        .map(|alert| json!({"title": alert.title, "severity": alert.severity}))
        .collect();
    put("alerts", Value::Array(alerts));

    let periods: Vec<Value> = weather
        .forecast
        .iter()
        .flat_map(|f| f.periods.iter().take(6))
        .map(|period| {
            let unit_is = |u: &str| {
                (period.temperature_unit == u)
                    .then_some(())
                    .and(period.temperature)
            };
            let wind_speed = match period.wind_speed_mph {
                Some(mph) => {
                    Value::String(format_wind_speed(Some(mph), None, unit, 1, wind_system))
                }
                None => opt_str(&period.wind_speed),
            };
            json!({
                "name": period.name,
                "temperature": num(period.temperature),
                "temperature_unit": period.temperature_unit,
                "temperature_text": format_temperature(unit_is("F"), unit_is("C"), unit, 1),
                "short_forecast": opt_str(&period.short_forecast),
                "wind_speed": wind_speed,
                "wind_direction": opt_str(&period.wind_direction),
            })
        })
        .collect();
    put("forecast_periods", Value::Array(periods));
    payload
}

fn temperature_for_prompt(
    current: &CurrentConditions,
    unit: TemperatureUnit,
) -> (Option<f64>, &'static str) {
    let fahrenheit = match (current.temperature_f, current.temperature_c) {
        (None, Some(c)) => Some((c * 9.0 / 5.0) + 32.0),
        (f, _) => f,
    };
    let celsius = match (current.temperature_c, current.temperature_f) {
        (None, Some(f)) => Some((f - 32.0) * 5.0 / 9.0),
        (c, _) => c,
    };
    match unit {
        TemperatureUnit::Celsius => (celsius, "C"),
        _ => (fahrenheit, "F"),
    }
}

fn wind_speed_for_prompt(
    current: &CurrentConditions,
    unit: TemperatureUnit,
    system: Option<DisplayUnitSystem>,
) -> Option<f64> {
    let (mut mph, mut kph) = (current.wind_speed_mph, current.wind_speed_kph);
    match (mph, kph) {
        (None, Some(k)) => mph = Some(k * 0.621371),
        (Some(m), None) => kph = Some(m * 1.60934),
        _ => {}
    }
    match system {
        Some(DisplayUnitSystem::Ca) => kph,
        Some(DisplayUnitSystem::Si) => kph.map(|k| k / 3.6),
        Some(DisplayUnitSystem::Us | DisplayUnitSystem::Uk) => mph,
        None if unit == TemperatureUnit::Celsius => kph,
        None => mph,
    }
}

fn wind_unit_label(unit: TemperatureUnit, system: Option<DisplayUnitSystem>) -> &'static str {
    match (system, unit) {
        (Some(DisplayUnitSystem::Us | DisplayUnitSystem::Uk), _) => "mph",
        (Some(DisplayUnitSystem::Ca), _) => "km/h",
        (Some(DisplayUnitSystem::Si), _) => "m/s",
        (None, TemperatureUnit::Celsius) => "km/h",
        (None, TemperatureUnit::Both) => "mph (km/h)",
        (None, TemperatureUnit::Fahrenheit) => "mph",
    }
}

fn visibility_for_prompt(
    current: &CurrentConditions,
    unit: TemperatureUnit,
    system: Option<DisplayUnitSystem>,
) -> Option<f64> {
    let (mut miles, mut km) = (current.visibility_miles, current.visibility_km);
    match (miles, km) {
        (None, Some(k)) => miles = Some(k * 0.621371),
        (Some(m), None) => km = Some(m * 1.60934),
        _ => {}
    }
    match system {
        Some(DisplayUnitSystem::Us | DisplayUnitSystem::Uk) => miles,
        Some(DisplayUnitSystem::Ca | DisplayUnitSystem::Si) => km,
        None if unit == TemperatureUnit::Celsius => km,
        None => miles,
    }
}

fn visibility_unit_label(unit: TemperatureUnit, system: Option<DisplayUnitSystem>) -> &'static str {
    match (system, unit) {
        (Some(DisplayUnitSystem::Us | DisplayUnitSystem::Uk), _) => "mi",
        (Some(DisplayUnitSystem::Ca | DisplayUnitSystem::Si), _) => "km",
        (None, TemperatureUnit::Celsius) => "km",
        (None, TemperatureUnit::Both) => "mi (km)",
        (None, TemperatureUnit::Fahrenheit) => "mi",
    }
}

fn pressure_for_prompt(
    current: &CurrentConditions,
    unit: TemperatureUnit,
    system: Option<DisplayUnitSystem>,
) -> Option<f64> {
    let (mut inches, mut mb) = (current.pressure_in, current.pressure_mb);
    match (inches, mb) {
        (None, Some(m)) => inches = Some(m / 33.8639),
        (Some(i), None) => mb = Some(i * 33.8639),
        _ => {}
    }
    match system {
        Some(DisplayUnitSystem::Ca) => mb.map(|m| m / 10.0),
        Some(DisplayUnitSystem::Uk | DisplayUnitSystem::Si) => mb,
        _ if unit == TemperatureUnit::Celsius => mb,
        _ => inches,
    }
}

fn pressure_unit_label(unit: TemperatureUnit, system: Option<DisplayUnitSystem>) -> &'static str {
    match (system, unit) {
        (Some(DisplayUnitSystem::Ca), _) => "kPa",
        (Some(DisplayUnitSystem::Uk | DisplayUnitSystem::Si), _) => "hPa",
        (_, TemperatureUnit::Celsius) => "hPa",
        (_, TemperatureUnit::Both) => "inHg (hPa)",
        (_, TemperatureUnit::Fahrenheit) => "inHg",
    }
}

/// `add_location_time_context`: UTC and local time for the location at `now`.
pub fn add_location_time_context(
    payload: &mut Map<String, Value>,
    location: &Location,
    now: DateTime<Utc>,
) {
    payload.insert(
        "utc_time".into(),
        json!(now.format("%Y-%m-%d %H:%M UTC").to_string()),
    );
    let Some(zone_name) = location.timezone.as_deref().filter(|z| !z.is_empty()) else {
        return;
    };
    let Ok(zone) = zone_name.parse::<chrono_tz::Tz>() else {
        return;
    };
    let local = now.with_timezone(&zone);
    payload.insert(
        "local_time".into(),
        json!(local.format("%Y-%m-%d %H:%M").to_string()),
    );
    payload.insert("timezone".into(), json!(zone_name));
    payload.insert("time_of_day".into(), json!(time_of_day(local.hour())));
}

fn time_of_day(hour: u32) -> &'static str {
    match hour {
        5..=11 => "morning",
        12..=16 => "afternoon",
        17..=20 => "evening",
        _ => "night",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn time_of_day_boundaries() {
        assert_eq!(
            [4, 5, 11, 12, 16, 17, 20, 21].map(time_of_day),
            [
                "night",
                "morning",
                "morning",
                "afternoon",
                "afternoon",
                "evening",
                "evening",
                "night"
            ]
        );
    }

    #[test]
    fn location_time_context_uses_the_location_zone() {
        let mut payload = Map::new();
        let mut location = Location::new("Home", 40.0, -75.0);
        location.timezone = Some("America/New_York".into());
        let now = Utc.with_ymd_and_hms(2026, 9, 25, 18, 5, 0).unwrap();
        add_location_time_context(&mut payload, &location, now);
        assert_eq!(payload["utc_time"], "2026-09-25 18:05 UTC");
        assert_eq!(payload["local_time"], "2026-09-25 14:05");
        assert_eq!(payload["time_of_day"], "afternoon");
        location.timezone = Some("Not/AZone".into());
        let mut bad = Map::new();
        add_location_time_context(&mut bad, &location, now);
        assert_eq!(bad.len(), 1);
    }
}
