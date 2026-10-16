//! Derived surf/beach conditions used when no official NWS Surf Zone Forecast
//! exists. Port of `surf_conditions.py`.

use aw_core::model::{Location, TextProduct, Timestamp};
use serde_json::{Map, Value};

use super::py::{self, py_float, py_str, with_params};
use crate::http::HttpClient;

pub const OPENMETEO_MARINE_BASE_URL: &str = "https://marine-api.open-meteo.com/v1";

const OPENMETEO_CURRENT_VARIABLES: [&str; 7] = [
    "wave_height",
    "wave_direction",
    "wave_period",
    "swell_wave_height",
    "swell_wave_direction",
    "swell_wave_period",
    "sea_surface_temperature",
];

/// Python raised while formatting (e.g. a NaN bearing); the whole summary is dropped.
struct Raised;

fn first_present<'a>(data: &'a Map<String, Value>, key: &str) -> Option<&'a Value> {
    match data.get(key)? {
        Value::Array(items) => items.first(),
        value => Some(value),
    }
    .filter(|v| !v.is_null())
}

fn as_number(value: &Value) -> Option<f64> {
    match value {
        Value::Number(n) => n.as_f64(),
        Value::Bool(b) => Some(f64::from(u8::from(*b))),
        _ => None,
    }
}

/// `_format_value`: numbers to one decimal with trailing zeros trimmed.
fn format_value(value: Option<&Value>, unit: Option<&Value>) -> Option<String> {
    let value = value?;
    let text = match as_number(value) {
        Some(n) => {
            let fixed = format!("{n:.1}");
            fixed
                .trim_end_matches('0')
                .trim_end_matches('.')
                .to_string()
        }
        None => py_str(value).trim().to_string(),
    };
    if text.is_empty() {
        return None;
    }
    Some(match unit.filter(|u| py::truthy(u)) {
        Some(unit) => format!("{text} {}", py_str(unit)).trim().to_string(),
        None => text,
    })
}

/// `_format_direction`: "W (270 degrees)"; non-numeric text passes through.
fn format_direction(value: Option<&Value>) -> Result<Option<String>, Raised> {
    let Some(value) = value else {
        return Ok(None);
    };
    let degrees = match value {
        Value::String(s) => s.trim().parse::<f64>().ok(),
        other => as_number(other),
    };
    let Some(degrees) = degrees else {
        let text = py_str(value).trim().to_string();
        return Ok((!text.is_empty()).then_some(text));
    };
    let cardinal = degrees_to_cardinal(degrees).ok_or(Raised)?;
    Ok(Some(format!("{cardinal} ({degrees:.0} degrees)")))
}

/// `degrees_to_cardinal` with Python's round-half-to-even.
fn degrees_to_cardinal(degrees: f64) -> Option<&'static str> {
    const DIRECTIONS: [&str; 16] = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW",
        "NW", "NNW",
    ];
    let scaled = degrees / 22.5;
    if !scaled.is_finite() {
        return None;
    }
    let index = (scaled.round_ties_even() as i64).rem_euclid(16);
    Some(DIRECTIONS[index as usize])
}

/// `format_openmeteo_marine_report(...).to_text_product()`.
pub fn format_openmeteo_marine_report(
    data: &Value,
    location: &Location,
    now: Timestamp,
) -> Option<TextProduct> {
    let current = data.get("current")?.as_object().filter(|c| !c.is_empty())?;
    let empty = Map::new();
    let units = data
        .get("current_units")
        .and_then(Value::as_object)
        .unwrap_or(&empty);
    let value = |key: &str| format_value(first_present(current, key), units.get(key));
    let direction = |key: &str| format_direction(first_present(current, key));

    let mut lines =
        vec![
        format!("Surf conditions from Open-Meteo Marine for {}.", location.name),
        "Marine/surf conditions from Open-Meteo Marine; not an official NWS Surf Zone Forecast."
            .to_string(),
    ];
    let fields = [
        ("Wave height", value("wave_height")),
        ("Wave direction", direction("wave_direction").ok()?),
        ("Wave period", value("wave_period")),
        ("Swell height", value("swell_wave_height")),
        ("Swell direction", direction("swell_wave_direction").ok()?),
        ("Swell period", value("swell_wave_period")),
        ("Sea surface temperature", value("sea_surface_temperature")),
    ];
    for (label, value) in fields {
        if let Some(value) = value.filter(|v| !v.is_empty()) {
            lines.push(format!("{label}: {value}."));
        }
    }
    if lines.len() == 2 {
        return None;
    }

    let issued_at = current
        .get("time")
        .and_then(Value::as_str)
        .filter(|t| !t.is_empty())
        .and_then(|t| py::fromisoformat(&t.replace('Z', "+00:00")))
        .map(|(naive, offset)| py::local_or_offset(naive, offset))
        .unwrap_or(now);
    Some(TextProduct {
        product_type: "SURF_CONDITIONS".into(),
        product_id: "openmeteo-marine-surf-conditions".into(),
        cwa_office: "Open-Meteo Marine".into(),
        issuance_time: Some(issued_at),
        product_text: lines.join("\n"),
        headline: Some("Surf conditions from Open-Meteo Marine".into()),
    })
}

/// Current Open-Meteo Marine conditions as a labelled summary; any failure → `None`.
pub fn fetch_openmeteo_marine_surf_conditions(
    http: &dyn HttpClient,
    marine_base_url: &str,
    location: &Location,
    now: Timestamp,
) -> Option<TextProduct> {
    let url = with_params(
        &format!("{marine_base_url}/marine"),
        &[
            ("latitude", py_float(location.latitude)),
            ("longitude", py_float(location.longitude)),
            ("current", OPENMETEO_CURRENT_VARIABLES.join(",")),
            ("timezone", "auto".to_string()),
        ],
    );
    match http.get_json(&url) {
        Ok(data) => format_openmeteo_marine_report(&data, location, now),
        Err(err) => {
            tracing::debug!("Open-Meteo Marine surf conditions unavailable: {err}");
            None
        }
    }
}

/// Beach-weather context from a raw Pirate Weather forecast payload
/// (`fetch_pirate_weather_beach_conditions` after `get_forecast_data`).
pub fn format_pirate_weather_beach_conditions(
    payload: &Value,
    location: &Location,
    now: Timestamp,
) -> Option<TextProduct> {
    let current = payload.get("currently")?.as_object()?;
    let mut lines = vec![
        format!("Surf conditions from Pirate Weather for {}.", location.name),
        "Beach-weather context from Pirate Weather; not an official NWS Surf Zone Forecast and \
         wave data is not available from this source in AccessiWeather."
            .to_string(),
    ];
    for (label, key, unit) in [
        ("Conditions", "summary", ""),
        ("Temperature", "temperature", "degrees"),
        ("Feels like", "apparentTemperature", "degrees"),
        ("Wind speed", "windSpeed", "mph"),
        ("Wind gust", "windGust", "mph"),
        ("Wind direction", "windBearing", ""),
        ("UV index", "uvIndex", ""),
        ("Visibility", "visibility", "miles"),
    ] {
        let value = current.get(key).filter(|v| !v.is_null());
        let formatted = if key == "windBearing" {
            format_direction(value).ok()?
        } else {
            let unit = Value::String(unit.to_string());
            format_value(value, Some(&unit))
        };
        if let Some(formatted) = formatted.filter(|f| !f.is_empty()) {
            lines.push(format!("{label}: {formatted}."));
        }
    }
    if let Some(probability) = current.get("precipProbability").and_then(as_number) {
        lines.push(format!(
            "Precipitation chance: {:.0} percent.",
            probability * 100.0
        ));
    }
    if lines.len() == 2 {
        return None;
    }
    Some(TextProduct {
        product_type: "SURF_CONDITIONS".into(),
        product_id: "pirate-weather-beach-conditions".into(),
        cwa_office: "Pirate Weather".into(),
        issuance_time: Some(now),
        product_text: lines.join("\n"),
        headline: Some("Surf conditions from Pirate Weather".into()),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn format_helpers_ignore_empty_values() {
        let data = json!({"wave_height": []});
        assert!(first_present(data.as_object().unwrap(), "wave_height").is_none());
        assert_eq!(format_value(Some(&json!("   ")), Some(&json!("m"))), None);
        assert_eq!(
            format_direction(Some(&json!("offshore"))).ok().flatten(),
            Some("offshore".into())
        );
    }

    #[test]
    fn cardinal_uses_round_half_even() {
        assert_eq!(degrees_to_cardinal(11.25), Some("N"));
        assert_eq!(degrees_to_cardinal(33.75), Some("NE"));
        assert_eq!(degrees_to_cardinal(-22.5), Some("NNW"));
        assert_eq!(degrees_to_cardinal(f64::NAN), None);
    }
}
