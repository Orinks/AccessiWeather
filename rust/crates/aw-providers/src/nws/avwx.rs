//! AVWX REST client for international TAFs (`api/avwx_client.py`).

use aw_core::model::AviationData;
use chrono::{Datelike, Utc};
use serde_json::Value;

use super::common::{fromisoformat, get_truthy, py_str, PyDateTime};
use crate::http::{HttpClient, HttpRequest};

pub const AVWX_BASE_URL: &str = "https://avwx.rest/api";

/// ICAO prefixes covered by NWS/AWC: contiguous US, Alaska, Hawaii, Guam and
/// the US-affiliated Pacific.
const US_ICAO_PREFIXES: [&str; 7] = ["K", "PA", "PH", "PG", "PF", "PK", "PP"];

/// `is_us_station`.
pub fn is_us_station(icao: &str) -> bool {
    let code = icao.trim().to_uppercase();
    !code.is_empty() && US_ICAO_PREFIXES.iter().any(|p| code.starts_with(p))
}

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum AvwxError {
    #[error("station must be a non-empty ICAO identifier")]
    EmptyStation,
    /// `AvwxApiError`, with Python's messages.
    #[error("{0}")]
    Api(String),
    /// Transport failure or an unparsable body. The request URL carries the
    /// API token, so it is deliberately left out.
    #[error("AVWX request failed")]
    Request,
}

/// `fetch_avwx_taf`: raw TAF plus AVWX's speech/translation summary.
pub fn fetch_avwx_taf(
    http: &dyn HttpClient,
    station: &str,
    api_key: &str,
) -> Result<AviationData, AvwxError> {
    let station = station.trim().to_uppercase();
    if station.is_empty() {
        return Err(AvwxError::EmptyStation);
    }
    let req = HttpRequest::new(format!("{AVWX_BASE_URL}/taf/{station}"))
        .param("token", api_key)
        .param("options", "info,translate,speech,summary")
        .header("Accept", "application/json");
    let resp = http.send(&req).map_err(|_| AvwxError::Request)?;
    match resp.status {
        200 => {}
        401 => {
            return Err(AvwxError::Api(
                "AVWX API key is invalid or expired. Please update your key in Settings → Data Sources."
                    .into(),
            ))
        }
        404 => {
            return Err(AvwxError::Api(format!(
                "Station {station} was not found in AVWX. Verify the ICAO code and try again."
            )))
        }
        status => {
            return Err(AvwxError::Api(format!(
                "AVWX API returned HTTP {status} for station {station}."
            )))
        }
    }
    let data = resp.json().map_err(|_| AvwxError::Request)?;
    Ok(build_aviation_data(&station, &data))
}

/// `_build_aviation_data`.
fn build_aviation_data(station: &str, data: &Value) -> AviationData {
    let info = get_truthy(data, "info").cloned().unwrap_or(Value::Null);
    let name = get_truthy(&info, "name").or_else(|| get_truthy(&info, "city"));
    let raw = get_truthy(data, "raw")
        .map(|r| py_str(r).trim().to_string())
        .filter(|r| !r.is_empty());
    let decoded = build_decoded_taf(station, data, &info);
    AviationData {
        station_id: Some(station.to_string()),
        airport_name: Some(name.map(py_str).unwrap_or_else(|| station.to_string())),
        raw_taf: raw,
        decoded_taf: (!decoded.is_empty()).then_some(decoded),
        ..Default::default()
    }
}

fn text_or_empty(v: &Value, key: &str) -> String {
    get_truthy(v, key).map(py_str).unwrap_or_default()
}

/// `_build_decoded_taf`: AVWX's top-level speech string when present,
/// otherwise a per-period summary.
fn build_decoded_taf(station: &str, data: &Value, info: &Value) -> String {
    let speech = text_or_empty(data, "speech");
    if !speech.trim().is_empty() {
        return speech.trim().to_string();
    }
    let label = get_truthy(info, "name")
        .or_else(|| get_truthy(info, "city"))
        .map(py_str)
        .unwrap_or_else(|| station.to_string());
    let mut lines = vec![format!("Terminal Aerodrome Forecast for {label}.")];
    match (
        format_avwx_time(&data["start_time"]),
        format_avwx_time(&data["end_time"]),
    ) {
        (Some(s), Some(e)) => lines.push(format!("Valid from {s} to {e}.")),
        (Some(s), None) => lines.push(format!("Valid from {s}.")),
        _ => {}
    }
    let empty = Vec::new();
    let forecast = get_truthy(data, "forecast")
        .and_then(Value::as_array)
        .unwrap_or(&empty);
    let translations = get_truthy(data, "translate")
        .and_then(|t| get_truthy(t, "forecast"))
        .and_then(Value::as_array)
        .unwrap_or(&empty);
    for (i, period) in forecast.iter().enumerate() {
        lines.extend(format_period(period, translations.get(i)));
    }
    lines.join("\n")
}

/// `_format_period`.
fn format_period(period: &Value, translation: Option<&Value>) -> Vec<String> {
    let period_type = get_truthy(period, "type")
        .map(py_str)
        .unwrap_or_else(|| "FM".into())
        .to_uppercase();
    let mut type_label = match period_type.as_str() {
        "FM" | "FROM" => "From".to_string(),
        "TEMPO" => "Temporary".into(),
        "BECMG" => "Becoming".into(),
        "PROB" => "Probability".into(),
        other => other.to_string(),
    };
    let prob = &period["probability"];
    if !prob.is_null() && matches!(period_type.as_str(), "PROB" | "PROBABILITY") {
        let value = if prob.is_object() {
            &prob["value"]
        } else {
            prob
        };
        if !value.is_null() {
            type_label = format!("Probability {}%", py_str(value));
        }
    }
    let header = match (
        format_avwx_time(&period["start_time"]),
        format_avwx_time(&period["end_time"]),
    ) {
        (Some(s), Some(e)) => format!("{type_label} from {s} to {e}:"),
        (Some(s), None) => format!("{type_label} from {s}:"),
        _ => format!("{type_label}:"),
    };
    let mut lines = vec![header];

    let speech = text_or_empty(period, "speech");
    if !speech.trim().is_empty() {
        lines.push(format!("  {}", speech.trim()));
        return lines;
    }
    match translation.filter(|t| super::common::truthy(t)) {
        Some(trans) => {
            let mut parts = Vec::new();
            if let Some(wind) = get_truthy(trans, "wind") {
                parts.push(py_str(wind));
            }
            for (key, label) in [
                ("visibility", "Visibility"),
                ("clouds", "Clouds"),
                ("wx_codes", "Weather"),
            ] {
                if let Some(v) = get_truthy(trans, key) {
                    parts.push(format!("{label}: {}", py_str(v)));
                }
            }
            if let Some(rules) =
                get_truthy(period, "flight_rules").or_else(|| get_truthy(trans, "flight_rules"))
            {
                lines.push(format!("  Flight rules: {}.", py_str(rules)));
            }
            if !parts.is_empty() {
                lines.push(format!("  {}.", parts.join("; ")));
            }
        }
        None => {
            let raw = text_or_empty(period, "raw");
            if !raw.trim().is_empty() {
                lines.push(format!("  {}", raw.trim()));
            }
        }
    }
    lines
}

/// `_format_avwx_time`: "14:00Z on the 18th" from an AVWX time object.
fn format_avwx_time(time: &Value) -> Option<String> {
    if !super::common::truthy(time) {
        return None;
    }
    match time {
        Value::String(s) => Some(s.clone()),
        Value::Object(_) => {
            if let Some(dt) = get_truthy(time, "dt").and_then(Value::as_str) {
                if let Some(parsed) = fromisoformat(&dt.replace('Z', "+00:00")) {
                    let utc = PyDateTime::assume_local(parsed).with_timezone(&Utc);
                    let day = utc.day();
                    let suffix = if (10..=20).contains(&(day % 100)) {
                        "th"
                    } else {
                        match day % 10 {
                            1 => "st",
                            2 => "nd",
                            3 => "rd",
                            _ => "th",
                        }
                    };
                    return Some(format!("{} on the {day}{suffix}", utc.format("%H:%MZ")));
                }
            }
            get_truthy(time, "repr").map(py_str)
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    // tests/test_avwx_client.py
    #[test]
    fn us_prefixes() {
        for code in ["KJFK", "kjfk", "PANC", "PHNL", "PGUM"] {
            assert!(is_us_station(code), "{code}");
        }
        for code in ["EGLL", "RJTT", "YSSY", "LFPG", ""] {
            assert!(!is_us_station(code), "{code}");
        }
    }

    #[test]
    fn time_formatting() {
        assert_eq!(format_avwx_time(&json!(null)), None);
        assert_eq!(
            format_avwx_time(&json!("1812/1912")).as_deref(),
            Some("1812/1912")
        );
        assert_eq!(
            format_avwx_time(&json!({"dt": "2024-01-18T12:00:00Z"})).as_deref(),
            Some("12:00Z on the 18th")
        );
        assert_eq!(
            format_avwx_time(&json!({"dt": "2024-01-21T06:30:00+02:00"})).as_deref(),
            Some("04:30Z on the 21st")
        );
        assert_eq!(
            format_avwx_time(&json!({"repr": "1812/1912"})).as_deref(),
            Some("1812/1912")
        );
        assert_eq!(format_avwx_time(&json!({})), None);
        assert_eq!(
            format_avwx_time(&json!({"dt": "not a date", "repr": "1812"})).as_deref(),
            Some("1812")
        );
    }

    #[test]
    fn periods_prefer_speech_then_translation_then_raw() {
        let p = json!({"type": "FROM", "start_time": {"repr": "1812"}, "speech": "Winds calm"});
        assert_eq!(format_period(&p, None), ["From from 1812:", "  Winds calm"]);
        let p = json!({"type": "PROB", "probability": {"value": 30}, "flight_rules": "IFR"});
        let t = json!({"wind": "N-5kt", "visibility": "3sm", "clouds": "Broken layer"});
        assert_eq!(
            format_period(&p, Some(&t)),
            [
                "Probability 30%:",
                "  Flight rules: IFR.",
                "  N-5kt; Visibility: 3sm; Clouds: Broken layer."
            ]
        );
        let p = json!({"type": "BECMG", "raw": " BECMG 1812/1814 VRB03KT "});
        assert_eq!(
            format_period(&p, None),
            ["Becoming:", "  BECMG 1812/1814 VRB03KT"]
        );
    }

    #[test]
    fn fetch_maps_statuses_and_builds_summary() {
        let url = "https://avwx.rest/api/taf/EGLL";
        let http = FixtureClient::new().with(
            url,
            json!({"raw": "TAF EGLL 1812/1912 ", "info": {"city": "London"},
                   "forecast": [{"type": "TEMPO", "raw": "TEMPO RA"}]}),
        );
        let a = fetch_avwx_taf(&http, " egll ", "key").unwrap();
        assert_eq!(a.station_id.as_deref(), Some("EGLL"));
        assert_eq!(a.airport_name.as_deref(), Some("London"));
        assert_eq!(a.raw_taf.as_deref(), Some("TAF EGLL 1812/1912"));
        assert_eq!(
            a.decoded_taf.as_deref(),
            Some("Terminal Aerodrome Forecast for London.\nTemporary:\n  TEMPO RA")
        );
        let sent = &http.sent_requests()[0];
        assert_eq!(sent.params[0], ("token".into(), "key".into()));
        assert_eq!(
            sent.headers,
            [("Accept".to_string(), "application/json".to_string())]
        );

        for (status, msg) in [
            (401, "AVWX API key is invalid or expired. Please update your key in Settings → Data Sources."),
            (404, "Station EGLL was not found in AVWX. Verify the ICAO code and try again."),
            (500, "AVWX API returned HTTP 500 for station EGLL."),
        ] {
            let http = FixtureClient::new().with_response(url, status, "{}");
            assert_eq!(fetch_avwx_taf(&http, "EGLL", "k"), Err(AvwxError::Api(msg.into())));
        }
        assert_eq!(
            fetch_avwx_taf(&FixtureClient::new(), " ", "k"),
            Err(AvwxError::EmptyStation)
        );
    }
}
