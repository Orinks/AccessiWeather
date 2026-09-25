//! Shared helpers from `weather_client_nws_common.py`, plus the handful of
//! Python behaviours the NWS code leans on (`repr(float)`, `str()`,
//! banker's `round`, truthiness, `float(str)`, `datetime.fromisoformat`).

use aw_core::model::{CurrentConditions, Timestamp};
use chrono::{DateTime, Local, NaiveDate, NaiveDateTime, TimeZone, Utc};
use serde_json::Value;

use super::normalize::convert_wind_speed_to_mph_and_kph;

pub const MAX_STATION_OBSERVATION_ATTEMPTS: usize = 10;
pub const MAX_OBSERVATION_AGE_HOURS: i64 = 2;

// ---------------------------------------------------------------------------
// Python value semantics
// ---------------------------------------------------------------------------

/// `repr(float)`: shortest round-trip digits, exponent form outside
/// `1e-4 <= |x| < 1e16`.
pub fn py_float_repr(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.into();
    }
    if x == 0.0 {
        return if x.is_sign_negative() { "-0.0" } else { "0.0" }.into();
    }
    let sci = format!("{x:e}");
    let (mantissa, exp) = sci.split_once('e').expect("LowerExp has an exponent");
    let exp: i32 = exp.parse().expect("LowerExp exponent is an integer");
    let (sign, mantissa) = match mantissa.strip_prefix('-') {
        Some(m) => ("-", m),
        None => ("", mantissa),
    };
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    if !(-5 < exp && exp < 16) {
        let mut m = digits[..1].to_string();
        if digits.len() > 1 {
            m.push('.');
            m.push_str(&digits[1..]);
        }
        let esign = if exp < 0 { '-' } else { '+' };
        return format!("{sign}{m}e{esign}{:02}", exp.abs());
    }
    let point = exp + 1; // digits before the decimal point
    let body = if point <= 0 {
        format!("0.{}{digits}", "0".repeat((-point) as usize))
    } else if point as usize >= digits.len() {
        format!("{digits}{}.0", "0".repeat(point as usize - digits.len()))
    } else {
        let (int, frac) = digits.split_at(point as usize);
        format!("{int}.{frac}")
    };
    format!("{sign}{body}")
}

/// `str(value)` for a JSON value (dicts/lists fall back to JSON text).
pub fn py_str(v: &Value) -> String {
    match v {
        Value::Null => "None".into(),
        Value::Bool(b) => if *b { "True" } else { "False" }.into(),
        Value::Number(n) => py_num_str(n),
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

pub fn py_num_str(n: &serde_json::Number) -> String {
    if n.is_f64() {
        py_float_repr(n.as_f64().unwrap_or(f64::NAN))
    } else {
        n.to_string()
    }
}

/// Python's `round()` to an integer: ties go to the even neighbour.
pub fn py_round(x: f64) -> i64 {
    x.round_ties_even() as i64
}

/// Python truthiness of a JSON value.
pub fn truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// `value.get(key)` returning `None` for missing *or* falsy values, i.e.
/// the `a.get(k) or b` idiom.
pub fn get_truthy<'a>(v: &'a Value, key: &str) -> Option<&'a Value> {
    v.get(key).filter(|x| truthy(x))
}

/// `float(text)`: surrounding whitespace, `inf`/`nan` and digit-separating
/// underscores are accepted.
pub fn py_parse_float(text: &str) -> Option<f64> {
    let t = text.trim();
    if t.contains('_') {
        let chars: Vec<char> = t.chars().collect();
        let valid = chars.iter().enumerate().all(|(i, c)| {
            *c != '_'
                || (i > 0
                    && chars[i - 1].is_ascii_digit()
                    && chars.get(i + 1).is_some_and(|n| n.is_ascii_digit()))
        });
        if !valid {
            return None;
        }
        return t.replace('_', "").parse().ok();
    }
    t.parse().ok()
}

/// Python `float(x)` of a JSON scalar (`None` where Python would raise).
pub fn py_float(v: &Value) -> Option<f64> {
    match v {
        Value::Number(n) => n.as_f64(),
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        Value::String(s) => py_parse_float(s),
        _ => None,
    }
}

/// The value of a string field, or `None` when absent or not a string.
pub fn str_field<'a>(v: &'a Value, key: &str) -> Option<&'a str> {
    v.get(key).and_then(Value::as_str)
}

/// `props.get(key, default)` for a `str` model field: a JSON `null` maps
/// to `""`, which is how Python consumers treat the resulting `None`.
pub fn str_or(v: &Value, key: &str, default: &str) -> String {
    match v.get(key) {
        None => default.to_string(),
        Some(Value::Null) => String::new(),
        Some(x) => py_str(x),
    }
}

/// `props.get(key)` for an optional `str` model field.
pub fn opt_str(v: &Value, key: &str) -> Option<String> {
    match v.get(key) {
        None | Some(Value::Null) => None,
        Some(x) => Some(py_str(x)),
    }
}

// ---------------------------------------------------------------------------
// datetime.fromisoformat
// ---------------------------------------------------------------------------

/// Result of `datetime.fromisoformat`: aware, or naive (no offset given).
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum PyDateTime {
    Aware(Timestamp),
    Naive(NaiveDateTime),
}

impl PyDateTime {
    /// Naive values taken as UTC (`_parse_iso_datetime`).
    pub fn assume_utc(self) -> Timestamp {
        match self {
            PyDateTime::Aware(t) => t,
            PyDateTime::Naive(n) => Utc.from_utc_datetime(&n).fixed_offset(),
        }
    }

    /// Naive values taken as local wall time (what Python's `astimezone()`
    /// does with them).
    pub fn assume_local(self) -> Timestamp {
        match self {
            PyDateTime::Aware(t) => t,
            PyDateTime::Naive(n) => Local
                .from_local_datetime(&n)
                .earliest()
                .map(|t| t.fixed_offset())
                .unwrap_or_else(|| Utc.from_utc_datetime(&n).fixed_offset()),
        }
    }
}

const AWARE_FORMATS: &[&str] = &[
    "%Y-%m-%dT%H:%M:%S%.f%:z",
    "%Y-%m-%dT%H:%M:%S%.f%z",
    "%Y-%m-%dT%H:%M%:z",
    "%Y-%m-%d %H:%M:%S%.f%:z",
    "%Y-%m-%d %H:%M%:z",
];
const NAIVE_FORMATS: &[&str] = &[
    "%Y-%m-%dT%H:%M:%S%.f",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S%.f",
    "%Y-%m-%d %H:%M",
];

/// `datetime.fromisoformat(text)` for the ISO-8601 shapes NWS, AVWX and
/// Python itself produce.
pub fn fromisoformat(text: &str) -> Option<PyDateTime> {
    if let Ok(t) = DateTime::parse_from_rfc3339(text) {
        return Some(PyDateTime::Aware(t));
    }
    for fmt in AWARE_FORMATS {
        if let Ok(t) = DateTime::parse_from_str(text, fmt) {
            return Some(PyDateTime::Aware(t));
        }
    }
    for fmt in NAIVE_FORMATS {
        if let Ok(n) = NaiveDateTime::parse_from_str(text, fmt) {
            return Some(PyDateTime::Naive(n));
        }
    }
    NaiveDate::parse_from_str(text, "%Y-%m-%d")
        .ok()
        .and_then(|d| d.and_hms_opt(0, 0, 0))
        .map(PyDateTime::Naive)
}

/// `datetime.fromisoformat(text.replace("Z", "+00:00"))`, naive -> local.
pub fn parse_z_datetime(text: &str) -> Option<Timestamp> {
    fromisoformat(&text.replace('Z', "+00:00")).map(PyDateTime::assume_local)
}

/// `_parse_iso_datetime`: timezone-aware parse, naive values assumed UTC.
pub fn parse_iso_datetime(value: &Value) -> Option<Timestamp> {
    let text = value.as_str()?.trim();
    if text.is_empty() {
        return None;
    }
    let text = match text.strip_suffix('Z') {
        Some(rest) => format!("{rest}+00:00"),
        None => text.to_string(),
    };
    fromisoformat(&text).map(PyDateTime::assume_utc)
}

// ---------------------------------------------------------------------------
// weather_client_nws_common helpers
// ---------------------------------------------------------------------------

/// `_station_sort_key`: ICAO `Kxxx` stations first, then other 4-letter
/// identifiers, then everything else; nearest first within a group.
pub fn station_sort_key(feature: &Value) -> (u8, f64, String) {
    let props = &feature["properties"];
    let station_id = get_truthy(props, "stationIdentifier")
        .map(py_str)
        .unwrap_or_default()
        .to_uppercase();
    let distance = py_float(&props["distance"]["value"]).unwrap_or(f64::INFINITY);
    let four = station_id.chars().count() == 4;
    let priority = if four && station_id.starts_with('K') {
        0
    } else if four {
        1
    } else {
        2
    };
    (priority, distance, station_id)
}

/// `_scrub_measurements`: blank out values whose QC code is not V, C or absent.
pub fn scrub_measurements(properties: &mut Value) {
    const KEYS: [&str; 11] = [
        "temperature",
        "dewpoint",
        "windSpeed",
        "windGust",
        "barometricPressure",
        "seaLevelPressure",
        "visibility",
        "relativeHumidity",
        "windDirection",
        "windChill",
        "heatIndex",
    ];
    for key in KEYS {
        let Some(Value::Object(measurement)) = properties.get_mut(key) else {
            continue;
        };
        let valid = match measurement.get("qualityControl") {
            None | Some(Value::Null) => true,
            Some(Value::String(qc)) => qc == "V" || qc == "C",
            Some(_) => false,
        };
        if !valid {
            measurement.insert("value".into(), Value::Null);
        }
    }
}

/// `_current_data_score`: how many useful fields an observation carries.
pub fn current_data_score(current: &CurrentConditions) -> usize {
    let blank_condition = current
        .condition
        .as_deref()
        .is_none_or(|c| c.trim().is_empty());
    [
        current.temperature_f.is_some(),
        current.temperature_c.is_some(),
        !blank_condition,
        current.humidity.is_some(),
        current.dewpoint_f.is_some(),
        current.wind_speed_mph.is_some(),
        current.pressure_in.is_some(),
        current.visibility_miles.is_some(),
        current.uv_index.is_some(),
    ]
    .into_iter()
    .filter(|present| *present)
    .count()
}

/// `_extract_scalar`: dig the first scalar out of nested NWS value objects.
pub fn extract_scalar(value: &Value) -> Option<&Value> {
    match value {
        Value::Object(map) => {
            if let Some(inner) = map.get("value") {
                return extract_scalar(inner);
            }
            match map.get("values") {
                Some(Value::Array(items)) => items.iter().find_map(extract_scalar),
                _ => None,
            }
        }
        Value::Array(items) => items.iter().find_map(extract_scalar),
        Value::Null => None,
        scalar => Some(scalar),
    }
}

/// `_extract_float`.
pub fn extract_float(value: &Value) -> Option<f64> {
    extract_scalar(value).and_then(py_float)
}

/// `_format_wind_speed`: "12 mph (19 km/h)" from a quantitative value, or
/// the text as NWS sent it.
pub fn format_wind_speed(value: &Value) -> Option<String> {
    match value {
        Value::Null => None,
        Value::Object(map) => {
            let unit_code = map.get("unitCode").and_then(Value::as_str);
            let field = |k: &str| map.get(k).and_then(extract_float);
            let numeric = field("value")
                .or_else(|| field("maxValue"))
                .or_else(|| field("minValue"))?;
            // The mph/kph conversions pass unknown units through, so both
            // are always present here; Python's other branches are unreachable.
            let (mph, kph) = convert_wind_speed_to_mph_and_kph(Some(numeric), unit_code);
            let (mph, kph) = (mph.unwrap_or(numeric), kph.unwrap_or(numeric));
            Some(format!("{} mph ({} km/h)", py_round(mph), py_round(kph)))
        }
        other => extract_scalar(other).map(py_str),
    }
}

/// `_extract_wind_speed_mph`: numeric mph from a quantitative value or from
/// text such as "5 to 15 mph" (the last number wins).
pub fn extract_wind_speed_mph(value: &Value) -> Option<f64> {
    match value {
        Value::Null => None,
        Value::Object(map) => {
            let unit_code = map.get("unitCode").and_then(Value::as_str);
            let field = |k: &str| map.get(k).and_then(extract_float);
            let numeric = field("value")
                .or_else(|| field("maxValue"))
                .or_else(|| field("minValue"))?;
            convert_wind_speed_to_mph_and_kph(Some(numeric), unit_code).0
        }
        other => {
            let text = extract_scalar(other)?.as_str()?;
            if let Some(mph) = last_number_before(text, "mph") {
                return Some(mph);
            }
            let kph = last_number_before(text, "km/h")?;
            convert_wind_speed_to_mph_and_kph(Some(kph), Some("wmoUnit:km_h-1")).0
        }
    }
}

/// The last match of `(\d+(?:\.\d+)?)\s*<unit>` (case-insensitive) in `text`.
fn last_number_before(text: &str, unit: &str) -> Option<f64> {
    let lower = text.to_ascii_lowercase();
    let bytes = lower.as_bytes();
    let mut found = None;
    let mut search = 0;
    while let Some(pos) = lower[search..].find(unit) {
        let at = search + pos;
        search = at + unit.len();
        let mut end = at;
        while end > 0 && bytes[end - 1].is_ascii_whitespace() {
            end -= 1;
        }
        let digits_start = |mut i: usize| {
            while i > 0 && bytes[i - 1].is_ascii_digit() {
                i -= 1;
            }
            i
        };
        let frac_start = digits_start(end);
        if frac_start == end {
            continue;
        }
        let mut start = frac_start;
        if frac_start >= 2
            && bytes[frac_start - 1] == b'.'
            && bytes[frac_start - 2].is_ascii_digit()
        {
            start = digits_start(frac_start - 1);
        }
        found = lower[start..end].parse().ok().or(found);
    }
    found
}

/// `_normalize_temperature_unit`: "F", "C" or `None`.
pub fn normalize_temperature_unit(unit: &Value) -> Option<&'static str> {
    let raw = extract_scalar(unit)?.as_str()?;
    let mut n = raw.trim().to_lowercase();
    if let Some((_, rest)) = n.split_once(':') {
        n = rest.to_string();
    }
    for (from, to) in [
        ("degree", ""),
        ("deg", ""),
        ("fahrenheit", "f"),
        ("celsius", "c"),
        ("wmounit", ""),
        ("°", ""),
        ("_", ""),
    ] {
        n = n.replace(from, to);
    }
    if n.ends_with('f') {
        Some("F")
    } else if n.ends_with('c') {
        Some("C")
    } else {
        None
    }
}

/// `_extract_temperature`: (value in °F, unit). The unit stays "C" only when
/// there is no value to convert.
pub fn extract_temperature(measurement: &Value, unit_hint: &Value) -> (Option<f64>, &'static str) {
    let mut unit = normalize_temperature_unit(unit_hint).unwrap_or("F");
    let numeric = match measurement {
        Value::Object(map) => {
            let field = |k: &str| map.get(k).and_then(extract_float);
            if let Some(u) = map.get("unitCode").and_then(normalize_temperature_unit) {
                unit = u;
            }
            field("value")
                .or_else(|| field("maxValue"))
                .or_else(|| field("minValue"))
        }
        other => extract_float(other),
    };
    match numeric {
        None => (None, unit),
        Some(n) if unit == "C" => (Some((n * 9.0 / 5.0) + 32.0), "F"),
        Some(n) => (Some(n), unit),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn float_repr_matches_python() {
        for (x, s) in [
            (40.0, "40.0"),
            (40.7128, "40.7128"),
            (-74.006, "-74.006"),
            (0.1, "0.1"),
            (1e-5, "1e-05"),
            (0.0001, "0.0001"),
            (1e16, "1e+16"),
            (1234567890123456.0, "1234567890123456.0"),
            (1.5e-7, "1.5e-07"),
            (-0.0, "-0.0"),
            (12.0, "12.0"),
        ] {
            assert_eq!(py_float_repr(x), s, "{x}");
        }
    }

    #[test]
    fn round_is_bankers() {
        assert_eq!(py_round(2.5), 2);
        assert_eq!(py_round(3.5), 4);
        assert_eq!(py_round(-2.5), -2);
        assert_eq!(py_round(2.6), 3);
    }

    #[test]
    fn wind_speed_text_takes_last_number() {
        assert_eq!(extract_wind_speed_mph(&json!("5 to 15 mph")), Some(15.0));
        assert_eq!(extract_wind_speed_mph(&json!("10 MPH")), Some(10.0));
        assert_eq!(extract_wind_speed_mph(&json!("12.5mph")), Some(12.5));
        let kph = extract_wind_speed_mph(&json!("20 km/h")).unwrap();
        assert!((kph - 20.0 * 0.621371).abs() < 1e-12);
        assert_eq!(extract_wind_speed_mph(&json!("calm")), None);
        assert_eq!(extract_wind_speed_mph(&json!(12)), None);
    }

    #[test]
    fn wind_speed_formats_quantitative_values() {
        let v = json!({"unitCode": "wmoUnit:km_h-1", "minValue": 10, "maxValue": 20});
        assert_eq!(format_wind_speed(&v).as_deref(), Some("12 mph (20 km/h)"));
        assert_eq!(format_wind_speed(&json!("5 mph")).as_deref(), Some("5 mph"));
        assert_eq!(format_wind_speed(&json!(7.0)).as_deref(), Some("7.0"));
        assert_eq!(format_wind_speed(&json!({"unitCode": "x"})), None);
    }

    #[test]
    fn temperature_units_normalise() {
        assert_eq!(
            normalize_temperature_unit(&json!("wmoUnit:degF")),
            Some("F")
        );
        assert_eq!(
            normalize_temperature_unit(&json!("wmoUnit:degC")),
            Some("C")
        );
        assert_eq!(normalize_temperature_unit(&json!("Celsius")), Some("C"));
        assert_eq!(normalize_temperature_unit(&json!("K")), None);
        let (t, u) = extract_temperature(
            &json!({"unitCode": "wmoUnit:degC", "value": 10}),
            &json!("F"),
        );
        assert_eq!((t, u), (Some(50.0), "F"));
        assert_eq!(extract_temperature(&json!(null), &json!("C")), (None, "C"));
    }

    #[test]
    fn scrub_blanks_failed_qc() {
        let mut props = json!({
            "temperature": {"value": 1.0, "qualityControl": "Z"},
            "dewpoint": {"value": 2.0, "qualityControl": "V"},
            "windSpeed": {"value": 3.0},
        });
        scrub_measurements(&mut props);
        assert_eq!(props["temperature"]["value"], Value::Null);
        assert_eq!(props["dewpoint"]["value"], json!(2.0));
        assert_eq!(props["windSpeed"]["value"], json!(3.0));
    }

    #[test]
    fn iso_parsing_handles_naive_and_z() {
        let t = parse_iso_datetime(&json!("2026-01-20T19:01:00Z")).unwrap();
        assert_eq!(t.to_rfc3339(), "2026-01-20T19:01:00+00:00");
        let t = parse_iso_datetime(&json!("2026-01-20T19:01:00")).unwrap();
        assert_eq!(t.to_rfc3339(), "2026-01-20T19:01:00+00:00");
        assert!(parse_iso_datetime(&json!("nope")).is_none());
        assert!(parse_iso_datetime(&json!(5)).is_none());
    }

    #[test]
    fn station_sort_prefers_icao_then_distance() {
        let f = |id: &str, d: f64| json!({"properties": {"stationIdentifier": id, "distance": {"value": d}}});
        let mut v = [
            f("AB12", 1.0),
            f("KXYZ", 9.0),
            f("PAMR", 2.0),
            f("KABC", 3.0),
        ];
        v.sort_by(|a, b| {
            let (a, b) = (station_sort_key(a), station_sort_key(b));
            a.partial_cmp(&b).unwrap()
        });
        let ids: Vec<_> = v
            .iter()
            .map(|x| x["properties"]["stationIdentifier"].clone())
            .collect();
        assert_eq!(
            ids,
            [json!("KABC"), json!("KXYZ"), json!("AB12"), json!("PAMR")]
        );
    }
}
