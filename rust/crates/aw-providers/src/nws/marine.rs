//! Marine zone forecast and alerts for locations in marine mode (the marine
//! parts of `weather_client_enrichment.py`).

use std::collections::HashSet;

use aw_core::is_us_location;
use aw_core::model::{
    Location, MarineForecast, MarineForecastPeriod, Timestamp, WeatherAlert, WeatherAlerts,
    WeatherData,
};
use serde_json::Value;

use super::common::{get_truthy, parse_z_datetime, py_float_repr, py_str};
use super::parsers::parse_alerts;
use super::NwsClient;
use crate::http::HttpError;

const HIGHLIGHT_WORDS: [&str; 9] = [
    "wind", "winds", "gust", "gusts", "wave", "waves", "seas", "swell", "swells",
];

fn is_word_char(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// `_MARINE_HIGHLIGHT_PATTERN.findall`: every `.`/`;`-delimited clause that
/// contains one of the wind/wave words as a whole word (case-insensitive).
fn highlight_clauses(text: &str) -> impl Iterator<Item = &str> {
    text.split(['.', ';']).filter(|clause| {
        clause
            .split(|c: char| !is_word_char(c))
            .any(|word| HIGHLIGHT_WORDS.contains(&word.to_lowercase().as_str()))
    })
}

/// `_build_marine_highlights`: up to four distinct wind/wave clauses.
pub fn build_marine_highlights(periods: &[Value]) -> Vec<String> {
    let mut highlights = Vec::new();
    let mut seen = HashSet::new();
    for period in periods {
        for field in ["shortForecast", "detailedForecast"] {
            let text = get_truthy(period, field).map(py_str).unwrap_or_default();
            let text = text.trim();
            if text.is_empty() {
                continue;
            }
            for clause in highlight_clauses(text) {
                let candidate = clause.split_whitespace().collect::<Vec<_>>().join(" ");
                let candidate = candidate.trim_matches([' ', '.']);
                if candidate.is_empty() || !seen.insert(candidate.to_lowercase()) {
                    continue;
                }
                highlights.push(candidate.to_string());
                if highlights.len() >= 4 {
                    return highlights;
                }
            }
        }
    }
    highlights
}

/// `period.get("detailedForecast") or period.get("shortForecast")`.
fn text_of(period: &Value) -> Option<&Value> {
    get_truthy(period, "detailedForecast").or_else(|| get_truthy(period, "shortForecast"))
}

/// `_parse_marine_issued_at`.
fn parse_issued_at(value: &Value) -> Option<Timestamp> {
    value
        .as_str()
        .filter(|s| !s.is_empty())
        .and_then(parse_z_datetime)
}

impl NwsClient<'_> {
    /// `enrich_with_marine_data`: the marine zone forecast and its alerts
    /// (tagged "NWS Marine") for US locations in marine mode. Failures leave
    /// `weather_data` as it was.
    pub fn enrich_with_marine_data(&self, weather_data: &mut WeatherData, location: &Location) {
        if !location.marine_mode || !is_us_location(location) {
            return;
        }
        if let Err(e) = self.marine_once(weather_data, location) {
            tracing::debug!(
                "Failed to fetch marine essentials for {}: {e}",
                location.name
            );
        }
    }

    fn marine_once(
        &self,
        weather_data: &mut WeatherData,
        location: &Location,
    ) -> Result<(), HttpError> {
        let point = format!(
            "{},{}",
            py_float_repr(location.latitude),
            py_float_repr(location.longitude)
        );
        let req = self
            .request(format!("{}/zones", self.base_url))
            .param("type", "marine")
            .param("point", point);
        let zones = self.fetch_json(&req)?;
        let Some(feature) = get_truthy(&zones, "features")
            .and_then(Value::as_array)
            .and_then(|f| f.first())
        else {
            return Ok(());
        };
        let zone_props = &feature["properties"];
        let Some(zone_id) = get_truthy(zone_props, "id").or_else(|| get_truthy(feature, "id"))
        else {
            return Ok(());
        };
        let zone_id = py_str(zone_id);

        let Some(data) = self
            .marine_forecast("marine", &zone_id)?
            .filter(super::common::truthy)
        else {
            return Ok(());
        };
        let props = &data["properties"];
        let empty = Vec::new();
        let raw_periods = get_truthy(props, "periods")
            .and_then(Value::as_array)
            .unwrap_or(&empty);

        let periods = raw_periods
            .iter()
            .take(3)
            .filter(|p| text_of(p).is_some())
            .map(|p| MarineForecastPeriod {
                name: get_truthy(p, "name")
                    .map(py_str)
                    .unwrap_or_else(|| "Marine period".into()),
                summary: text_of(p)
                    .map(py_str)
                    .unwrap_or_default()
                    .trim()
                    .to_string(),
            })
            .collect();
        let marine = MarineForecast {
            zone_id: Some(zone_id.clone()),
            zone_name: get_truthy(props, "name")
                .or_else(|| zone_props.get("name").filter(|v| !v.is_null()))
                .map(py_str),
            // `str(detailed or short)`: a missing text becomes the literal "None".
            forecast_summary: raw_periods.first().map(|p| {
                get_truthy(p, "detailedForecast")
                    .map(py_str)
                    .unwrap_or_else(|| py_str(p.get("shortForecast").unwrap_or(&Value::Null)))
            }),
            issued_at: parse_issued_at(&props["updateTime"]),
            periods,
            highlights: build_marine_highlights(&raw_periods[..raw_periods.len().min(4)]),
        };
        if marine.has_data() {
            weather_data.marine = Some(marine);
        }

        let req = self
            .request(format!("{}/alerts/active", self.base_url))
            .param("zone", zone_id)
            .param("status", "actual");
        let marine_alerts = parse_alerts(&self.fetch_json(&req)?)?;
        if marine_alerts.alerts.is_empty() {
            return Ok(());
        }
        // {unique_id: alert}: later duplicates replace earlier ones in place.
        let mut merged: Vec<(String, WeatherAlert)> = Vec::new();
        let existing = weather_data
            .alerts
            .take()
            .map(|a| a.alerts)
            .unwrap_or_default();
        for alert in existing {
            let id = alert.unique_id();
            match merged.iter_mut().find(|(k, _)| *k == id) {
                Some(slot) => slot.1 = alert,
                None => merged.push((id, alert)),
            }
        }
        for mut alert in marine_alerts.alerts {
            alert.source = Some("NWS Marine".into());
            let id = alert.unique_id();
            if !merged.iter().any(|(k, _)| *k == id) {
                merged.push((id, alert));
            }
        }
        weather_data.alerts = Some(WeatherAlerts {
            alerts: merged.into_iter().map(|(_, a)| a).collect(),
        });
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    // tests/test_marine_enrichment.py
    #[test]
    fn highlights_dedupe_and_cap_at_four() {
        let periods = vec![
            json!({"shortForecast": "Winds 10 kt", "detailedForecast": "Winds 10 kt. Seas 2 ft; waves 1 ft. Sunny."}),
            json!({"detailedForecast": "SW winds 15 kt. Seas 3 ft. Swell 5 ft. Gusts to 25 kt."}),
        ];
        assert_eq!(
            build_marine_highlights(&periods),
            ["Winds 10 kt", "Seas 2 ft", "waves 1 ft", "SW winds 15 kt"]
        );
        assert!(
            build_marine_highlights(&[json!({"detailedForecast": "Windy and sunny"})]).is_empty()
        );
    }

    #[test]
    fn issued_at_parses_or_ignores() {
        assert!(parse_issued_at(&json!("2026-01-20T10:00:00Z")).is_some());
        assert!(parse_issued_at(&json!("not-a-date")).is_none());
        assert!(parse_issued_at(&json!("")).is_none());
        assert!(parse_issued_at(&json!(null)).is_none());
    }
}
