//! Text formatters for Weather Assistant tool results.
//!
//! Ports `ai_tool_formatters.py` and `ai_weather_time.py`. The inputs are the
//! raw provider JSON the Python tools format: NWS observation, forecast and
//! alert GeoJSON (`properties`, `features`) or Open-Meteo responses
//! (`current`, `hourly`, `daily` with their `*_units`), so measurements keep
//! their original units and valid times.

use chrono::{DateTime, Duration, NaiveDate, NaiveDateTime, TimeZone, Utc};
use serde_json::{Map, Value};

use crate::pyfmt::{self, truthy};

static EMPTY: std::sync::LazyLock<Map<String, Value>> = std::sync::LazyLock::new(Map::new);

/// `mapping`: accept mappings from provider JSON without trusting container types.
fn mapping(value: Option<&Value>) -> &Map<String, Value> {
    value.and_then(Value::as_object).unwrap_or(&EMPTY)
}

/// `scalar`: finite numbers or nonempty strings.
fn scalar(value: &Value) -> bool {
    match value {
        Value::String(s) => !s.is_empty(),
        Value::Number(n) => n.as_f64().is_some_and(f64::is_finite),
        _ => false,
    }
}

fn unit_symbol(unit: &str) -> &str {
    match unit {
        "wmoUnit:degC" => "°C",
        "wmoUnit:degF" => "°F",
        "wmoUnit:percent" => "%",
        "wmoUnit:km_h-1" => "km/h",
        "wmoUnit:m_s-1" => "m/s",
        "wmoUnit:Pa" => "Pa",
        "wmoUnit:degree_(angle)" => "°",
        "wmoUnit:m" => "m",
        other => other,
    }
}

/// `measurement`: raw NWS quantities and Open-Meteo scalar measurements.
fn measurement(value: Option<&Value>, unit: Option<&Value>) -> Option<String> {
    let (value, unit) = match value {
        Some(Value::Object(quantity)) => (quantity.get("value"), quantity.get("unitCode")),
        other => (other, unit),
    };
    let value = value.filter(|v| scalar(v))?;
    let unit = unit.and_then(Value::as_str).unwrap_or("");
    Some(format!("{}{}", pyfmt::str(value), unit_symbol(unit)))
}

/// A provider time zone: an IANA zone, or a fixed UTC offset.
#[derive(Debug, Clone, Copy, PartialEq)]
enum Zone {
    Named(chrono_tz::Tz),
    Fixed(i32),
}

impl Zone {
    /// `str(tzinfo)` as Python prints it.
    fn name(self) -> String {
        match self {
            Zone::Named(tz) => tz.name().to_string(),
            Zone::Fixed(0) => "UTC".into(),
            Zone::Fixed(secs) => {
                let sign = if secs < 0 { '-' } else { '+' };
                let abs = secs.abs();
                let mut text = format!("UTC{sign}{:02}:{:02}", abs / 3600, abs % 3600 / 60);
                if abs % 60 != 0 {
                    text.push_str(&format!(":{:02}", abs % 60));
                }
                text
            }
        }
    }
}

/// `local_zone`: the provider time zone, using its UTC offset when needed.
fn local_zone(data: &Map<String, Value>) -> Option<Zone> {
    if let Some(Ok(tz)) = data
        .get("timezone")
        .and_then(Value::as_str)
        .map(str::parse::<chrono_tz::Tz>)
    {
        return Some(Zone::Named(tz));
    }
    let offset = data.get("utc_offset_seconds")?.as_f64()?;
    (offset.is_finite() && offset.abs() < 86400.0).then_some(Zone::Fixed(offset as i32))
}

/// A parsed provider time: wall-clock time plus its zone (`None` = naive).
#[derive(Debug, Clone, Copy)]
struct Stamp {
    local: NaiveDateTime,
    zone: Option<Zone>,
}

impl Stamp {
    fn utc(self) -> Option<DateTime<Utc>> {
        let offset_secs = match self.zone? {
            Zone::Fixed(secs) => secs,
            Zone::Named(tz) => {
                // Ambiguous times take the first occurrence (fold=0); times in a
                // spring-forward gap use the offset in force just before it.
                let offset = tz
                    .offset_from_local_datetime(&self.local)
                    .earliest()
                    .or_else(|| {
                        tz.offset_from_local_datetime(&(self.local - Duration::hours(1)))
                            .earliest()
                    })?;
                chrono::Offset::fix(&offset).local_minus_utc()
            }
        };
        Some(Utc.from_utc_datetime(&(self.local - Duration::seconds(offset_secs as i64))))
    }
}

/// `datetime.fromisoformat` for the formats providers send.
fn parse_iso(text: &str) -> Option<(NaiveDateTime, Option<i32>)> {
    let text = text.trim_end();
    let date = NaiveDate::parse_from_str(text.get(..10)?, "%Y-%m-%d").ok()?;
    let rest = &text[10..];
    if rest.is_empty() {
        return Some((date.and_hms_opt(0, 0, 0)?, None));
    }
    let rest = rest.strip_prefix(['T', ' '])?;
    let split = rest.find(['+', '-']).unwrap_or(rest.len());
    let (time_text, offset_text) = rest.split_at(split);
    let mut hms = time_text.splitn(3, ':');
    let hour: u32 = hms.next()?.parse().ok()?;
    let minute: u32 = hms.next().map_or(Some(0), |m| m.parse().ok())?;
    let (second, micros) = match hms.next() {
        None => (0, 0),
        Some(s) => {
            let (whole, fraction) = s.split_once(['.', ',']).unwrap_or((s, ""));
            let digits: String = fraction.chars().chain("000000".chars()).take(6).collect();
            (
                whole.parse().ok()?,
                if fraction.is_empty() {
                    0
                } else {
                    digits.parse().ok()?
                },
            )
        }
    };
    let time = date.and_hms_micro_opt(hour, minute, second, micros)?;
    if offset_text.is_empty() {
        return Some((time, None));
    }
    let sign = if offset_text.starts_with('-') { -1 } else { 1 };
    let digits: String = offset_text[1..].chars().filter(|c| *c != ':').collect();
    let part = |range: std::ops::Range<usize>| -> Option<i32> {
        digits.get(range).map_or(Some(0), |d| d.parse().ok())
    };
    if digits.len() < 2 {
        return None;
    }
    let seconds = part(0..2)? * 3600 + part(2..4)? * 60 + part(4..6)?;
    Some((time, Some(sign * seconds)))
}

/// `timestamp`: parse an ISO provider time without guessing a missing zone.
fn timestamp(value: Option<&Value>, data: &Map<String, Value>) -> Option<Stamp> {
    let text = value?.as_str()?.replace('Z', "+00:00");
    let (local, offset) = parse_iso(&text)?;
    let zone = match offset {
        Some(secs) => Some(Zone::Fixed(secs)),
        None => local_zone(data),
    };
    Some(Stamp { local, zone })
}

/// `current_or_future`: exclude elapsed hours; keep unresolvable times.
fn current_or_future(
    value: Option<&Value>,
    data: &Map<String, Value>,
    now: DateTime<Utc>,
    end: Option<&Value>,
) -> bool {
    let Some(start) = timestamp(value, data).filter(|s| s.zone.is_some()) else {
        return true;
    };
    let finish = end
        .filter(|e| truthy(e))
        .and_then(|e| timestamp(Some(e), data))
        .filter(|f| f.zone.is_some())
        .unwrap_or(Stamp {
            local: start.local + Duration::hours(1),
            zone: start.zone,
        });
    finish.utc().is_some_and(|f| f > now)
}

/// `provenance`: keep provider origin and time interpretation explicit.
fn provenance(data: &Map<String, Value>, source: &str) -> [String; 2] {
    let zone = match data.get("timezone").and_then(Value::as_str) {
        Some(zone) if !zone.is_empty() => zone.to_string(),
        _ => local_zone(data).map_or_else(
            || "not supplied; use timestamps' explicit offsets".to_string(),
            Zone::name,
        ),
    };
    [format!("Source: {source}"), format!("Timezone: {zone}")]
}

/// `series_lines`: aligned Open-Meteo arrays, units kept, metadata skipped.
fn series_lines(
    data: &Map<String, Value>,
    section: &str,
    limit: usize,
    now: Option<DateTime<Utc>>,
) -> Vec<String> {
    let values = mapping(data.get(section));
    let units = mapping(data.get(&format!("{section}_units")));
    let Some(times) = values.get("time").and_then(Value::as_array) else {
        return Vec::new();
    };
    let mut result = Vec::new();
    for (index, time) in times.iter().enumerate() {
        let Some(time_text) = time.as_str().filter(|t| !t.is_empty()) else {
            continue;
        };
        if section == "hourly"
            && !current_or_future(Some(time), data, now.unwrap_or_else(Utc::now), None)
        {
            continue;
        }
        let mut parts = vec![time_text.to_string()];
        for (key, column) in values {
            if key == "time" {
                continue;
            }
            if let Some(cell) = column.as_array().and_then(|c| c.get(index)) {
                if let Some(text) = measurement(Some(cell), units.get(key)) {
                    parts.push(format!("{key}: {text}"));
                }
            }
        }
        if parts.len() > 1 {
            result.push(parts.join(" | "));
        }
        if result.len() >= limit {
            break;
        }
    }
    result
}

fn header(label: &str, display_name: &str) -> String {
    if display_name.is_empty() {
        format!("{label}:")
    } else {
        format!("{label} for {display_name}:")
    }
}

fn source_name(data: &Map<String, Value>) -> &'static str {
    if data.contains_key("properties") {
        "NWS"
    } else {
        "weather service"
    }
}

/// `data.get("periods", data["properties"].get("periods", []))`.
fn periods(data: &Map<String, Value>) -> Option<&Vec<Value>> {
    match data.get("periods") {
        Some(periods) => periods.as_array(),
        None => mapping(data.get("properties")).get("periods")?.as_array(),
    }
}

fn truthy_str(map: &Map<String, Value>, key: &str) -> Option<String> {
    map.get(key).filter(|v| truthy(v)).map(pyfmt::str)
}

/// "72°F", or the bare value when the unit is missing.
fn temperature_part(period: &Map<String, Value>) -> Option<String> {
    let temp = period.get("temperature").filter(|t| !t.is_null())?;
    Some(match truthy_str(period, "temperatureUnit") {
        Some(unit) => format!("{}°{unit}", pyfmt::str(temp)),
        None => pyfmt::str(temp),
    })
}

/// `format_current_weather`.
pub fn format_current_weather(data: &Value, display_name: &str) -> String {
    let data = mapping(Some(data));
    let mut lines = vec![header("Current weather", display_name)];
    let count;
    if let Some(current) = data.get("current").and_then(Value::as_object) {
        let units = mapping(data.get("current_units"));
        lines.extend(provenance(data, "Open-Meteo"));
        let time = current
            .get("time")
            .filter(|t| truthy(t))
            .map_or("not supplied".into(), pyfmt::str);
        lines.push(format!("Observation time: {time}"));
        count = lines.len();
        for (key, value) in current {
            if key != "time" && key != "interval" {
                if let Some(text) = measurement(Some(value), units.get(key)) {
                    lines.push(format!("{key}: {text}"));
                }
            }
        }
    } else {
        let current = if data.contains_key("properties") {
            mapping(data.get("properties"))
        } else {
            data
        };
        lines.extend(provenance(data, source_name(data)));
        let time = truthy_str(current, "timestamp")
            .or_else(|| truthy_str(current, "time"))
            .unwrap_or_else(|| "not supplied".into());
        lines.push(format!("Observation time: {time}"));
        count = lines.len();
        const FIELDS: [(&str, &[&str]); 8] = [
            ("Temperature", &["temperature"]),
            (
                "Feels Like",
                &["feels_like", "feelsLike", "heatIndex", "windChill"],
            ),
            (
                "Conditions",
                &["description", "textDescription", "conditions"],
            ),
            ("Humidity", &["humidity", "relativeHumidity"]),
            ("Wind", &["wind", "windSpeed"]),
            ("Wind direction", &["windDirection"]),
            ("Pressure", &["pressure", "barometricPressure"]),
            ("Visibility", &["visibility"]),
        ];
        for (label, keys) in FIELDS {
            if let Some(text) = keys.iter().find_map(|k| measurement(current.get(*k), None)) {
                lines.push(format!("{label}: {text}"));
            }
        }
    }
    if lines.len() == count {
        lines.push("No current weather data available.".into());
    }
    lines.join("\n")
}

/// `format_forecast`: daily rows, or NWS day/night periods for `forecast_days`.
pub fn format_forecast(data: &Value, display_name: &str, forecast_days: i64) -> String {
    let data = mapping(Some(data));
    let mut lines = vec![header("Forecast", display_name)];
    let days = forecast_days.clamp(1, 16);
    if data.contains_key("daily") {
        lines.extend(provenance(data, "Open-Meteo"));
        let rows = series_lines(data, "daily", days as usize, None);
        if rows.is_empty() {
            lines.push("No forecast data available.".into());
        }
        lines.extend(rows);
        return lines.join("\n");
    }
    lines.extend(provenance(data, source_name(data)));
    let count = lines.len();
    if let Some(periods) = periods(data) {
        let first = periods
            .iter()
            .filter_map(Value::as_object)
            .find_map(|p| timestamp(p.get("startTime"), data));
        let boundary = first.map(|f| Stamp {
            local: f.local + Duration::days(days),
            zone: f.zone,
        });
        for period in periods
            .iter()
            .take(2 * days as usize)
            .filter_map(Value::as_object)
        {
            let start = timestamp(period.get("startTime"), data);
            if let (Some(boundary), Some(start)) = (boundary, start) {
                // Python compares only when both times share a tzinfo.
                if start.zone == boundary.zone && start.local >= boundary.local {
                    continue;
                }
            }
            let mut parts = vec![truthy_str(period, "name").unwrap_or_else(|| "Unknown".into())];
            parts.extend(temperature_part(period));
            if let Some(short) = truthy_str(period, "shortForecast")
                .or_else(|| truthy_str(period, "detailedForecast"))
            {
                parts.push(short);
            }
            if let Some(start) = truthy_str(period, "startTime") {
                parts.push(format!("Valid from {start}"));
            }
            lines.push(parts.join(" - "));
        }
    }
    if lines.len() == count {
        lines.push("No forecast data available.".into());
    }
    lines.join("\n")
}

/// `format_alerts`: event, severity, validity, sender, headline, description.
pub fn format_alerts(data: &Value, display_name: &str) -> String {
    let data = mapping(Some(data));
    let mut lines = vec![header("Weather alerts", display_name)];
    let alerts = data
        .get("alerts")
        .or_else(|| data.get("features"))
        .and_then(Value::as_array)
        .filter(|a| !a.is_empty());
    lines.push(
        if data.contains_key("features") {
            "Source: NWS"
        } else {
            "Source: weather service"
        }
        .into(),
    );
    let Some(alerts) = alerts else {
        lines.push("No active alerts.".into());
        return lines.join("\n");
    };
    for alert in alerts.iter().filter_map(Value::as_object) {
        let props = match alert.get("properties") {
            Some(props) => mapping(Some(props)),
            None => alert,
        };
        let mut line = format!(
            "- {}",
            truthy_str(props, "event").unwrap_or_else(|| "Unknown Alert".into())
        );
        if let Some(severity) = truthy_str(props, "severity") {
            line.push_str(&format!(" (Severity: {severity})"));
        }
        lines.push(line);
        for (label, key) in [
            ("Sender", "senderName"),
            ("Effective", "effective"),
            ("Onset", "onset"),
            ("Expires", "expires"),
            ("Ends", "ends"),
        ] {
            let mut value = props.get(key);
            if key == "senderName" && !value.is_some_and(truthy) {
                value = props.get("sender");
            }
            let text = value
                .and_then(Value::as_str)
                .filter(|s| !s.is_empty())
                .unwrap_or("unknown");
            lines.push(format!("  {label}: {text}"));
        }
        if let Some(headline) = truthy_str(props, "headline") {
            lines.push(format!("  {headline}"));
        }
        if let Some(description) = props.get("description").filter(|d| truthy(d)) {
            let text = match description {
                Value::String(s) => pyfmt::head(s, 300).to_string(),
                other => pyfmt::str(other),
            };
            lines.push(format!("  {text}"));
        }
    }
    lines.join("\n")
}

/// `format_hourly_forecast`: up to 12 current or future hours.
pub fn format_hourly_forecast(data: &Value, display_name: &str, now: DateTime<Utc>) -> String {
    let data = mapping(Some(data));
    let mut lines = vec![header("Hourly forecast", display_name)];
    if data.contains_key("hourly") {
        lines.extend(provenance(data, "Open-Meteo"));
        let rows = series_lines(data, "hourly", 12, Some(now));
        if rows.is_empty() {
            lines.push("No hourly forecast data available.".into());
        }
        lines.extend(rows);
        return lines.join("\n");
    }
    lines.extend(provenance(data, source_name(data)));
    let count = lines.len();
    if let Some(periods) = periods(data) {
        let upcoming = periods
            .iter()
            .filter_map(Value::as_object)
            .filter(|p| current_or_future(p.get("startTime"), data, now, p.get("endTime")))
            .take(12);
        for period in upcoming {
            let name = truthy_str(period, "name")
                .unwrap_or_else(|| period.get("startTime").map_or(String::new(), pyfmt::str));
            let mut parts = vec![name];
            parts.extend(temperature_part(period));
            parts.extend(truthy_str(period, "shortForecast"));
            if let Some(wind) = truthy_str(period, "windSpeed") {
                parts.push(format!("Wind: {wind}"));
            }
            if let Some(start) = truthy_str(period, "startTime") {
                parts.push(format!("Valid from {start}"));
            }
            lines.push(parts.join(" - "));
        }
    }
    if lines.len() == count {
        lines.push("No hourly forecast data available.".into());
    }
    lines.join("\n")
}

/// `format_open_meteo_response`: raw current and forecast sections with valid times.
pub fn format_open_meteo_response(data: &Value, display_name: &str, now: DateTime<Utc>) -> String {
    let map = mapping(Some(data));
    let mut lines = vec![header("Open-Meteo data", display_name)];
    lines.extend(provenance(map, "Open-Meteo"));
    let has_current = map.get("current").is_some_and(Value::is_object);
    if has_current {
        lines.extend(
            format_current_weather(data, "")
                .lines()
                .filter(|l| !l.starts_with("Source:") && !l.starts_with("Timezone:"))
                .map(String::from),
        );
    }
    let mut found = has_current;
    for (section, limit, label) in [("hourly", 24, "periods"), ("daily", 16, "days")] {
        let rows = series_lines(map, section, limit, Some(now));
        if !rows.is_empty() {
            found = true;
            lines.push(format!(
                "\n{} ({} {label}):",
                pyfmt::title(section),
                rows.len()
            ));
            lines.extend(rows);
        }
    }
    if !found {
        lines.push("No data returned.".into());
    }
    lines.join("\n")
}

/// `format_location_search`.
pub fn format_location_search(suggestions: &[String], query: &str) -> String {
    if suggestions.is_empty() {
        return format!("No locations found matching '{query}'.");
    }
    let mut lines = vec![format!("Locations matching '{query}':")];
    lines.extend(
        suggestions
            .iter()
            .enumerate()
            .map(|(i, s)| format!("{}. {s}", i + 1)),
    );
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn at(h: u32, m: u32) -> DateTime<Utc> {
        Utc.with_ymd_and_hms(2026, 9, 12, h, m, 0).unwrap()
    }

    #[test]
    fn iso_parsing_matches_fromisoformat() {
        let (t, off) = parse_iso("2026-09-12T14:15").unwrap();
        assert_eq!(t.to_string(), "2026-09-12 14:15:00");
        assert_eq!(off, None);
        assert_eq!(
            parse_iso("2026-09-12T02:20:00-04:00").unwrap().1,
            Some(-4 * 3600)
        );
        assert_eq!(parse_iso("2026-09-12T18:00:00+00:00").unwrap().1, Some(0));
        assert_eq!(
            parse_iso("2026-09-12").unwrap().0.to_string(),
            "2026-09-12 00:00:00"
        );
        assert!(parse_iso("tomorrow").is_none());
    }

    #[test]
    fn hourly_selects_current_hour_in_location_timezone() {
        let data = json!({
            "timezone": "America/New_York",
            "hourly": {"time": ["2026-09-12T00:00", "2026-09-12T14:00", "2026-09-12T15:00"],
                       "temperature_2m": [-99, 20, 21]},
            "hourly_units": {"temperature_2m": "°C"},
        });
        for text in [
            format_hourly_forecast(&data, "", at(18, 30)),
            format_open_meteo_response(&data, "", at(18, 30)),
        ] {
            assert!(
                !text.contains("-99") && text.contains("20°C") && text.contains("21°C"),
                "{text}"
            );
            assert!(text.contains("14:00") && text.contains("America/New_York"));
        }
    }

    #[test]
    fn forecast_stops_at_requested_day_boundary() {
        let data = json!({"properties": {"periods": [
            {"name": "First", "startTime": "2026-09-12T06:00:00-04:00", "temperature": 20},
            {"name": "Outside", "startTime": "2026-09-13T06:00:00-04:00", "temperature": 21},
        ]}});
        let text = format_forecast(&data, "", 1);
        assert!(text.contains("First") && !text.contains("Outside"));
    }

    #[test]
    fn malformed_arrays_are_safe() {
        for value in [json!(null), json!(5), json!("text"), json!([null, 3, "x"])] {
            let data = json!({"daily": {"time": value, "temperature_2m_max": value},
                              "daily_units": null, "hourly": {"time": value, "temperature_2m": value},
                              "hourly_units": []});
            format_forecast(&data, "", 7);
            format_hourly_forecast(&data, "", at(0, 0));
            format_open_meteo_response(&data, "", at(0, 0));
        }
    }
}
