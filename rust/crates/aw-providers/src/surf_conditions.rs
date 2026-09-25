//! Surf and beach-condition summaries, ported from
//! `accessiweather.surf_conditions` (Open-Meteo Marine plus Pirate Weather
//! beach-weather context, both shown as Forecaster Notes text products).

use aw_core::model::{Location, TextProduct, Timestamp};
use aw_core::py;
use aw_core::weather_client_parsers::degrees_to_cardinal;
use chrono::{Local, TimeZone, Utc};
use serde_json::Value;

use crate::http::{build_url, HttpClient};
use crate::pirateweather::PirateWeatherClient;

pub const OPENMETEO_MARINE_BASE_URL: &str = "https://marine-api.open-meteo.com/v1";
pub const DEFAULT_USER_AGENT: &str = "AccessiWeather (github.com/orinks/accessiweather)";
const CURRENT_VARIABLES: [&str; 7] = [
    "wave_height",
    "wave_direction",
    "wave_period",
    "swell_wave_height",
    "swell_wave_direction",
    "swell_wave_period",
    "sea_surface_temperature",
];

/// A source-labelled surf/beach conditions summary.
#[derive(Debug, Clone, PartialEq)]
pub struct SurfConditionReport {
    pub source_name: String,
    pub product_id: String,
    pub text: String,
    pub issued_at: Option<Timestamp>,
    pub official: bool,
}

impl SurfConditionReport {
    /// The Forecaster Notes text product shape.
    pub fn to_text_product(&self) -> TextProduct {
        TextProduct {
            product_type: "SURF_CONDITIONS".into(),
            product_id: self.product_id.clone(),
            cwa_office: self.source_name.clone(),
            issuance_time: self.issued_at,
            product_text: self.text.clone(),
            headline: Some(if self.official {
                format!("Official surf forecast from {}", self.source_name)
            } else {
                format!("Surf conditions from {}", self.source_name)
            }),
        }
    }
}

fn first_present<'a>(data: &'a Value, key: &str) -> Option<&'a Value> {
    match data.get(key)? {
        Value::Array(items) => items.first(),
        other => Some(other),
    }
    .filter(|v| !v.is_null())
}

fn format_value(value: Option<&Value>, unit: Option<&str>) -> Option<String> {
    let text = match value? {
        Value::Null => return None,
        v @ (Value::Number(_) | Value::Bool(_)) => {
            let formatted = format!("{:.1}", py::number(Some(v))?);
            formatted.trim_end_matches('0').trim_end_matches('.').to_string()
        }
        v => py::value_str(v).trim().to_string(),
    };
    if text.is_empty() {
        return None;
    }
    Some(match unit.filter(|u| !u.is_empty()) {
        Some(u) => format!("{text} {u}").trim().to_string(),
        None => text,
    })
}

fn format_direction(value: Option<&Value>) -> Option<String> {
    let value = value.filter(|v| !v.is_null())?;
    match py::as_float(Some(value)) {
        Some(degrees) => Some(format!(
            "{} ({degrees:.0} degrees)",
            degrees_to_cardinal(Some(degrees)).unwrap_or_default()
        )),
        None => Some(py::value_str(value).trim().to_string()).filter(|s| !s.is_empty()),
    }
}

/// Open-Meteo Marine current data as accessible plain text; `now` is the
/// fallback issue time. A naive `time` is read as local wall-clock time, as
/// Python does.
pub fn format_openmeteo_marine_report(
    data: &Value,
    location: &Location,
    now: Timestamp,
) -> Option<SurfConditionReport> {
    let current = data.get("current")?.as_object().filter(|c| !c.is_empty())?;
    let current = Value::Object(current.clone());
    let empty = serde_json::Map::new();
    let units = data.get("current_units").and_then(Value::as_object).unwrap_or(&empty);
    let unit = |key: &str| units.get(key).and_then(Value::as_str);

    let mut lines = vec![
        format!("Surf conditions from Open-Meteo Marine for {}.", location.name),
        "Marine/surf conditions from Open-Meteo Marine; not an official NWS Surf Zone Forecast."
            .to_string(),
    ];
    let fields = [
        ("Wave height", format_value(first_present(&current, "wave_height"), unit("wave_height"))),
        ("Wave direction", format_direction(first_present(&current, "wave_direction"))),
        ("Wave period", format_value(first_present(&current, "wave_period"), unit("wave_period"))),
        (
            "Swell height",
            format_value(first_present(&current, "swell_wave_height"), unit("swell_wave_height")),
        ),
        ("Swell direction", format_direction(first_present(&current, "swell_wave_direction"))),
        (
            "Swell period",
            format_value(first_present(&current, "swell_wave_period"), unit("swell_wave_period")),
        ),
        (
            "Sea surface temperature",
            format_value(
                first_present(&current, "sea_surface_temperature"),
                unit("sea_surface_temperature"),
            ),
        ),
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
        .filter(|s| !s.is_empty())
        .and_then(|s| py::fromisoformat(&s.replace('Z', "+00:00")))
        .and_then(|(naive, offset)| match offset {
            Some(off) => off.from_local_datetime(&naive).single(),
            None => Local.from_local_datetime(&naive).earliest().map(|t| t.fixed_offset()),
        });
    Some(SurfConditionReport {
        source_name: "Open-Meteo Marine".into(),
        product_id: "openmeteo-marine-surf-conditions".into(),
        issued_at: Some(issued_at.unwrap_or_else(|| now.to_utc().fixed_offset())),
        text: lines.join("\n"),
        official: false,
    })
}

/// Marine request URL.
pub fn marine_url(location: &Location, marine_base_url: &str) -> String {
    build_url(
        &format!("{marine_base_url}/marine"),
        &[
            ("latitude", py::float_repr(location.latitude)),
            ("longitude", py::float_repr(location.longitude)),
            ("current", CURRENT_VARIABLES.join(",")),
            ("timezone", "auto".into()),
        ],
    )
}

/// Fetch a small Open-Meteo Marine surf summary; any failure yields `None`.
pub fn fetch_openmeteo_marine_surf_conditions(
    http: &dyn HttpClient,
    location: &Location,
    marine_base_url: &str,
    user_agent: &str,
) -> Option<TextProduct> {
    let url = marine_url(location, marine_base_url);
    match http.get_json_with_headers(&url, &[("User-Agent", user_agent)]) {
        Ok(data) => {
            format_openmeteo_marine_report(&data, location, Utc::now().fixed_offset())
                .map(|r| r.to_text_product())
        }
        Err(e) => {
            tracing::debug!("Open-Meteo Marine surf conditions unavailable: {e}");
            None
        }
    }
}

/// Beach-weather context from a Pirate Weather payload (`now` = issue time).
pub fn pirate_weather_beach_conditions(
    payload: &Value,
    location: &Location,
    now: Timestamp,
) -> Option<TextProduct> {
    let current = payload.get("currently")?;
    if !current.is_object() {
        return None;
    }
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
        let value = current.get(key);
        let formatted = if key == "windBearing" {
            format_direction(value)
        } else {
            format_value(value, Some(unit))
        };
        if let Some(text) = formatted.filter(|t| !t.is_empty()) {
            lines.push(format!("{label}: {text}."));
        }
    }
    if let Some(p) = py::number(current.get("precipProbability")) {
        lines.push(format!("Precipitation chance: {:.0} percent.", p * 100.0));
    }
    if lines.len() == 2 {
        return None;
    }
    Some(TextProduct {
        product_type: "SURF_CONDITIONS".into(),
        product_id: "pirate-weather-beach-conditions".into(),
        cwa_office: "Pirate Weather".into(),
        issuance_time: Some(now.to_utc().fixed_offset()),
        product_text: lines.join("\n"),
        headline: Some("Surf conditions from Pirate Weather".into()),
    })
}

/// `fetch_pirate_weather_beach_conditions`: `None` without a configured client
/// or when the payload is unavailable.
pub fn fetch_pirate_weather_beach_conditions(
    location: &Location,
    pirate_client: Option<&PirateWeatherClient>,
) -> Option<TextProduct> {
    let payload = match pirate_client?.get_forecast_data(location) {
        Ok(p) => p,
        Err(e) => {
            tracing::debug!("Pirate Weather beach conditions unavailable: {e}");
            return None;
        }
    };
    pirate_weather_beach_conditions(&payload, location, Utc::now().fixed_offset())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn now() -> Timestamp {
        chrono::DateTime::parse_from_rfc3339("2025-06-01T12:00:00+00:00").unwrap()
    }

    #[test]
    fn marine_report_labels_derived_conditions() {
        let data = json!({
            "current": {"time": "2025-06-01T08:00Z", "wave_height": 1.25, "wave_direction": 270,
                "wave_period": 9.0, "swell_wave_height": [0.8], "sea_surface_temperature": 21.46},
            "current_units": {"wave_height": "m", "wave_period": "s", "swell_wave_height": "m",
                "sea_surface_temperature": "°C"}
        });
        let report = format_openmeteo_marine_report(&data, &Location::new("Beach", 1.0, 2.0), now()).unwrap();
        assert_eq!(
            report.text,
            "Surf conditions from Open-Meteo Marine for Beach.\n\
             Marine/surf conditions from Open-Meteo Marine; not an official NWS Surf Zone Forecast.\n\
             Wave height: 1.2 m.\nWave direction: W (270 degrees).\nWave period: 9 s.\n\
             Swell height: 0.8 m.\nSea surface temperature: 21.5 °C."
        );
        let product = report.to_text_product();
        assert_eq!(product.headline.as_deref(), Some("Surf conditions from Open-Meteo Marine"));
        assert_eq!(product.issuance_time.unwrap().to_rfc3339(), "2025-06-01T08:00:00+00:00");
    }

    #[test]
    fn marine_report_requires_values() {
        let loc = Location::new("Beach", 1.0, 2.0);
        assert!(format_openmeteo_marine_report(&json!({"current": {"wave_height": null}}), &loc, now()).is_none());
        assert!(format_openmeteo_marine_report(&json!({"current": {}}), &loc, now()).is_none());
        let r = format_openmeteo_marine_report(
            &json!({"current": {"time": "bad", "wave_height": 1}}),
            &loc,
            now(),
        )
        .unwrap();
        assert_eq!(r.issued_at, Some(now()));
    }

    #[test]
    fn pirate_beach_conditions_use_available_context() {
        let payload = json!({"currently": {"summary": "Clear", "temperature": 78.44,
            "windSpeed": 10, "windBearing": 180, "precipProbability": 0.25}});
        let p = pirate_weather_beach_conditions(&payload, &Location::new("Beach", 1.0, 2.0), now()).unwrap();
        assert_eq!(
            p.product_text,
            "Surf conditions from Pirate Weather for Beach.\n\
             Beach-weather context from Pirate Weather; not an official NWS Surf Zone Forecast and \
             wave data is not available from this source in AccessiWeather.\n\
             Conditions: Clear.\nTemperature: 78.4 degrees.\nWind speed: 10 mph.\n\
             Wind direction: S (180 degrees).\nPrecipitation chance: 25 percent."
        );
        assert!(pirate_weather_beach_conditions(&json!({"currently": {}}), &Location::new("B", 0.0, 0.0), now()).is_none());
        assert!(fetch_pirate_weather_beach_conditions(&Location::new("B", 0.0, 0.0), None).is_none());
    }
}
