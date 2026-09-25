//! Aviation (TAF and advisory) presentation.
//!
//! Port of `display/presentation/aviation.py`.

use chrono::{DateTime, NaiveDate, NaiveDateTime};
use serde_json::{Map, Value};

use crate::display::models::AviationPresentation;
use crate::display::pyfmt::{py_str, truthy};
use crate::display::taf::decode_taf_text;
use crate::display::time::PyDateTime;
use crate::model::AviationData;

fn filled(s: &Option<String>) -> Option<&str> {
    s.as_deref().filter(|s| !s.trim().is_empty())
}

/// `build_aviation`. `format_timestamp` is the presenter's datetime formatter.
pub fn build_aviation(
    aviation: Option<&AviationData>,
    location_name: &str,
    format_timestamp: &dyn Fn(&PyDateTime) -> String,
) -> Option<AviationPresentation> {
    let aviation = aviation?;
    let has_advisories = !aviation.active_sigmets.is_empty() || !aviation.active_cwas.is_empty();
    let taf_available = filled(&aviation.raw_taf).is_some() || filled(&aviation.decoded_taf).is_some();
    if !(taf_available || has_advisories) {
        return None;
    }

    let station_label = aviation
        .airport_name
        .as_deref()
        .filter(|s| !s.is_empty())
        .or(aviation.station_id.as_deref().filter(|s| !s.is_empty()));
    let header_location = match station_label {
        Some(label) if label.to_lowercase() != location_name.to_lowercase() => {
            format!("{label} near {location_name}")
        }
        Some(label) => label.to_string(),
        None => location_name.to_string(),
    };
    let header = format!("Aviation weather for {header_location}.");

    let mut taf_summary = aviation.decoded_taf.clone();
    if taf_summary.as_deref().is_none_or(str::is_empty) {
        if let Some(raw) = aviation.raw_taf.as_deref().filter(|r| !r.is_empty()) {
            taf_summary = Some(decode_taf_text(raw));
        }
    }

    let summarize = |entries: &[Value], f: fn(&Map<String, Value>, &dyn Fn(&PyDateTime) -> String) -> String| {
        entries
            .iter()
            .take(5)
            .filter_map(|e| e.as_object())
            .map(|o| f(o, format_timestamp))
            .filter(|s| !s.is_empty())
            .collect::<Vec<_>>()
    };
    let sigmets = summarize(&aviation.active_sigmets, summarize_sigmet);
    let cwas = summarize(&aviation.active_cwas, summarize_cwa);

    let mut lines = vec![header];
    let raw = filled(&aviation.raw_taf).map(str::trim);
    match (taf_summary.as_deref().filter(|t| !t.is_empty()), raw) {
        (Some(summary), raw) => {
            lines.push("Terminal Aerodrome Forecast:".into());
            lines.push(summary.to_string());
            if let Some(r) = raw {
                lines.push("Raw TAF message:".into());
                lines.push(r.to_string());
            }
        }
        (None, Some(r)) => {
            lines.push("Raw Terminal Aerodrome Forecast:".into());
            lines.push(r.to_string());
        }
        (None, None) => lines.push("No Terminal Aerodrome Forecast available.".into()),
    }
    if !sigmets.is_empty() {
        lines.push("SIGMET and AIRMET advisories:".into());
        lines.extend(sigmets.iter().map(|l| format!("• {l}")));
    }
    if !cwas.is_empty() {
        lines.push("Center Weather Advisories:".into());
        lines.extend(cwas.iter().map(|l| format!("• {l}")));
    }

    Some(AviationPresentation {
        title: "Aviation Weather".into(),
        airport_name: aviation.airport_name.clone(),
        station_id: aviation.station_id.clone(),
        taf_summary,
        raw_taf: aviation.raw_taf.clone(),
        sigmets,
        cwas,
        fallback_text: lines.join("\n"),
    })
}

/// `data.get(a) or data.get(b) or ...`: the first truthy value.
fn first_truthy<'a>(data: &'a Map<String, Value>, keys: &[&str]) -> Option<&'a Value> {
    keys.iter().filter_map(|k| data.get(*k)).find(|v| truthy(v))
}

/// `datetime.fromisoformat` for the common ISO shapes.
fn parse_iso(value: &str) -> Option<PyDateTime> {
    let v = match value.strip_suffix('Z') {
        Some(rest) => format!("{rest}+00:00"),
        None => value.to_string(),
    };
    if let Ok(dt) = DateTime::parse_from_rfc3339(&v) {
        return Some(PyDateTime::aware(dt, None));
    }
    for fmt in ["%Y-%m-%dT%H:%M:%S%.f%:z", "%Y-%m-%d %H:%M:%S%.f%:z", "%Y-%m-%dT%H:%M%:z", "%Y-%m-%d %H:%M%:z"] {
        if let Ok(dt) = DateTime::parse_from_str(&v, fmt) {
            return Some(PyDateTime::aware(dt, None));
        }
    }
    for fmt in ["%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%d %H:%M:%S%.f", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"] {
        if let Ok(dt) = NaiveDateTime::parse_from_str(&v, fmt) {
            return Some(PyDateTime::naive(dt));
        }
    }
    NaiveDate::parse_from_str(&v, "%Y-%m-%d")
        .ok()
        .and_then(|d| d.and_hms_opt(0, 0, 0))
        .map(PyDateTime::naive)
}

/// `_format_aviation_time`: formatted when parseable, else the raw text.
fn format_aviation_time(
    value: Option<&Value>,
    format_timestamp: &dyn Fn(&PyDateTime) -> String,
) -> Option<String> {
    let value = value?;
    let text = py_str(value);
    Some(match parse_iso(&text) {
        Some(dt) => format_timestamp(&dt),
        None => text,
    })
}

fn area_text(area: Option<&Value>) -> Option<String> {
    match area? {
        Value::Array(items) => Some(
            items
                .iter()
                .filter(|i| truthy(i))
                .map(py_str)
                .collect::<Vec<_>>()
                .join(", "),
        ),
        other => Some(py_str(other)),
    }
}

fn validity(start: Option<String>, end: Option<String>, start_word: &str) -> Option<String> {
    match (start, end) {
        (Some(s), Some(e)) => Some(format!("Valid {s} to {e}")),
        (None, Some(e)) => Some(format!("Valid until {e}")),
        (Some(s), None) => Some(format!("{start_word} {s}")),
        (None, None) => None,
    }
}

fn nonempty(s: Option<String>) -> Option<String> {
    s.filter(|s| !s.is_empty())
}

/// `_summarize_sigmet`.
fn summarize_sigmet(data: &Map<String, Value>, format_timestamp: &dyn Fn(&PyDateTime) -> String) -> String {
    let name = first_truthy(data, &["name", "event", "hazard", "phenomenon"])
        .map(py_str)
        .unwrap_or_else(|| "SIGMET".into());
    let severity = first_truthy(data, &["severity", "intensity"]);
    let area = nonempty(area_text(first_truthy(data, &["fir", "area", "regions", "airspace"])));
    let start = nonempty(format_aviation_time(
        first_truthy(data, &["startTime", "beginTime", "validTimeStart", "issueTime"]),
        format_timestamp,
    ));
    let end = nonempty(format_aviation_time(
        first_truthy(data, &["endTime", "expires", "validTimeEnd", "validUntil"]),
        format_timestamp,
    ));
    let description = first_truthy(data, &["description", "text", "summary"]);

    let mut summary = name;
    if let Some(s) = severity {
        summary = format!("{summary} severity {}", py_str(s));
    }
    let mut details = Vec::new();
    if let Some(a) = area {
        details.push(format!("Area: {a}"));
    }
    details.extend(validity(start, end, "Effective"));
    if let Some(d) = description {
        details.push(py_str(d));
    }
    if details.is_empty() {
        summary
    } else {
        format!("{summary}; {}", details.join("; "))
    }
}

/// `_summarize_cwa`.
fn summarize_cwa(data: &Map<String, Value>, format_timestamp: &dyn Fn(&PyDateTime) -> String) -> String {
    let name = first_truthy(data, &["event", "phenomenon", "hazard", "productType"])
        .map(py_str)
        .unwrap_or_else(|| "Center Weather Advisory".into());
    let cwsu = first_truthy(data, &["cwsu", "issuingOffice"]).map(py_str);
    let area = nonempty(area_text(
        first_truthy(data, &["area", "regions", "airspace"]).or(first_truthy(data, &["cwsu", "issuingOffice"])),
    ));
    let start = nonempty(format_aviation_time(
        first_truthy(data, &["startTime", "issueTime"]),
        format_timestamp,
    ));
    let end = nonempty(format_aviation_time(
        first_truthy(data, &["endTime", "expires"]),
        format_timestamp,
    ));
    let description = first_truthy(data, &["description", "text", "summary"]);

    let mut summary = name.clone();
    if let Some(c) = cwsu.filter(|c| *c != name) {
        summary = format!("{summary} ({c})");
    }
    let mut details = Vec::new();
    if let Some(a) = area.filter(|a| !summary.contains(a.as_str())) {
        details.push(format!("Area: {a}"));
    }
    details.extend(validity(start, end, "Issued"));
    if let Some(d) = description {
        details.push(py_str(d));
    }
    if details.is_empty() {
        summary
    } else {
        format!("{summary}; {}", details.join("; "))
    }
}
