//! Python-semantics helpers the provider ports rely on for exact parity:
//! `round()`, `repr(float)`, `str()` of JSON values, `str.casefold`,
//! `str.title`, `float()` coercion and `datetime.fromisoformat`/`isoformat`.

use chrono::{FixedOffset, NaiveDate, NaiveDateTime, NaiveTime, Offset};
use serde_json::Value;

/// `round(x)` — ties to even.
pub fn round(x: f64) -> f64 {
    x.round_ties_even()
}

/// `round(x, ndigits)` — correctly rounded, ties to even on exact values
/// (Rust's fixed-precision formatting uses the same algorithm as Python's).
pub fn round_to(x: f64, ndigits: usize) -> f64 {
    format!("{x:.ndigits$}").parse().unwrap_or(x)
}

/// `repr(float)` / `str(float)`.
pub fn float_repr(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.into();
    }
    let abs = x.abs();
    if abs != 0.0 && !(1e-4..1e16).contains(&abs) {
        // Rust: "1e-5" / "1.2345e17"; Python: "1e-05" / "1.2345e+17".
        let s = format!("{x:e}");
        let (mantissa, exp) = s.split_once('e').unwrap_or((&s, "0"));
        let (sign, digits) = match exp.strip_prefix('-') {
            Some(d) => ('-', d),
            None => ('+', exp),
        };
        return format!("{mantissa}e{sign}{digits:0>2}");
    }
    let s = format!("{x}");
    if s.contains('.') {
        s
    } else {
        format!("{s}.0")
    }
}

/// `str(value)` for a decoded JSON value (ints stay ints, floats use repr).
pub fn value_str(value: &Value) -> String {
    match value {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Number(n) => match n
            .as_i64()
            .map(|i| i.to_string())
            .or_else(|| n.as_u64().map(|u| u.to_string()))
        {
            Some(s) if !n.is_f64() => s,
            _ => float_repr(n.as_f64().unwrap_or(0.0)),
        },
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

/// `float(value)` treating missing, empty and unparseable values as absent.
pub fn as_float(value: Option<&Value>) -> Option<f64> {
    match value? {
        Value::Number(n) => n.as_f64(),
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        Value::String(s) => s.trim().parse().ok(),
        _ => None,
    }
}

/// `isinstance(value, int | float)` → float (bools count, as in Python).
pub fn number(value: Option<&Value>) -> Option<f64> {
    match value? {
        Value::Number(n) => n.as_f64(),
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        _ => None,
    }
}

/// Python truthiness of a JSON value.
pub fn truthy(value: Option<&Value>) -> bool {
    match value {
        None | Some(Value::Null) => false,
        Some(Value::Bool(b)) => *b,
        Some(Value::Number(n)) => n.as_f64().is_some_and(|f| f != 0.0),
        Some(Value::String(s)) => !s.is_empty(),
        Some(Value::Array(a)) => !a.is_empty(),
        Some(Value::Object(o)) => !o.is_empty(),
    }
}

/// `str.casefold()` (full Unicode lowercasing plus the common special folds).
pub fn casefold(s: &str) -> String {
    s.to_lowercase()
        .replace('ß', "ss")
        .replace('ς', "σ")
        .replace('ſ', "s")
}

/// `str.title()`: uppercase letters that follow a non-letter, lowercase the rest.
pub fn title(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut prev_alpha = false;
    for c in s.chars() {
        if prev_alpha {
            out.extend(c.to_lowercase());
        } else {
            out.extend(c.to_uppercase());
        }
        prev_alpha = c.is_alphabetic();
    }
    out
}

/// `datetime.fromisoformat` (Python 3.11+ extended forms): returns the
/// wall-clock time and the offset when one was given.
pub fn fromisoformat(text: &str) -> Option<(NaiveDateTime, Option<FixedOffset>)> {
    let date = NaiveDate::parse_from_str(text.get(..10)?, "%Y-%m-%d").ok()?;
    let rest = &text[10..];
    if rest.is_empty() {
        return Some((date.and_hms_opt(0, 0, 0)?, None));
    }
    let mut chars = rest.chars();
    let sep = chars.next()?;
    if sep != 'T' && sep != ' ' {
        return None;
    }
    let rest = chars.as_str();
    let split = rest.find(['Z', '+', '-']).unwrap_or(rest.len());
    let (time_text, offset_text) = rest.split_at(split);
    let time = parse_time(time_text)?;
    let offset = if offset_text.is_empty() {
        None
    } else if offset_text == "Z" {
        Some(FixedOffset::east_opt(0)?)
    } else {
        Some(parse_offset(offset_text)?)
    };
    Some((date.and_time(time), offset))
}

fn parse_time(text: &str) -> Option<NaiveTime> {
    let (hms, frac) = match text.split_once(['.', ',']) {
        Some((a, b)) => (a, Some(b)),
        None => (text, None),
    };
    let parts: Vec<&str> = hms.split(':').collect();
    let num = |s: &str| -> Option<u32> {
        (s.len() == 2 && s.bytes().all(|b| b.is_ascii_digit()))
            .then(|| s.parse().ok())
            .flatten()
    };
    let (h, m, s) = match parts.as_slice() {
        [h] => (num(h)?, 0, 0),
        [h, m] => (num(h)?, num(m)?, 0),
        [h, m, s] => (num(h)?, num(m)?, num(s)?),
        _ => return None,
    };
    let micros = match frac {
        None => 0,
        Some(f) if (1..=9).contains(&f.len()) && f.bytes().all(|b| b.is_ascii_digit()) => {
            format!("{:0<6}", &f[..f.len().min(6)]).parse().ok()?
        }
        Some(_) => return None,
    };
    NaiveTime::from_hms_micro_opt(h, m, s, micros)
}

fn parse_offset(text: &str) -> Option<FixedOffset> {
    let sign = match text.as_bytes().first()? {
        b'+' => 1,
        b'-' => -1,
        _ => return None,
    };
    let body = &text[1..];
    let digits: String = body.chars().filter(|c| *c != ':').collect();
    if !digits.bytes().all(|b| b.is_ascii_digit()) || ![2, 4, 6].contains(&digits.len()) {
        return None;
    }
    let field = |i: usize| {
        digits
            .get(i..i + 2)
            .map_or(Some(0), |s| s.parse::<i32>().ok())
    };
    let secs = field(0)? * 3600 + field(2)? * 60 + field(4)?;
    FixedOffset::east_opt(sign * secs)
}

/// `datetime.isoformat()` for a wall-clock time with an optional offset.
pub fn isoformat(naive: NaiveDateTime, offset: Option<FixedOffset>) -> String {
    let mut out = naive.format("%Y-%m-%dT%H:%M:%S").to_string();
    let micros = naive.and_utc().timestamp_subsec_micros();
    if micros != 0 {
        out.push_str(&format!(".{micros:06}"));
    }
    if let Some(offset) = offset {
        let total = offset.fix().local_minus_utc();
        let sign = if total < 0 { '-' } else { '+' };
        let total = total.abs();
        out.push_str(&format!(
            "{sign}{:02}:{:02}",
            total / 3600,
            total % 3600 / 60
        ));
        if total % 60 != 0 {
            out.push_str(&format!(":{:02}", total % 60));
        }
    }
    out
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
            (0.1 + 0.2, "0.30000000000000004"),
            (1e-5, "1e-05"),
            (0.0001, "0.0001"),
            (1e16, "1e+16"),
            (1e20, "1e+20"),
            (1234567890123456.0, "1234567890123456.0"),
            (1.5e-7, "1.5e-07"),
            (1.7976931348623157e308, "1.7976931348623157e+308"),
            (0.0, "0.0"),
            (-0.0, "-0.0"),
            (12.0, "12.0"),
        ] {
            assert_eq!(float_repr(x), s, "{x}");
        }
    }

    #[test]
    fn rounding_matches_python() {
        assert_eq!(round(2.5), 2.0);
        assert_eq!(round(3.5), 4.0);
        assert_eq!(round_to(2.675, 2), 2.67);
        assert_eq!(round_to(0.25, 1), 0.2);
    }

    #[test]
    fn value_str_keeps_int_float_distinction() {
        assert_eq!(value_str(&json!(12)), "12");
        assert_eq!(value_str(&json!(12.0)), "12.0");
        assert_eq!(value_str(&json!(null)), "None");
    }

    #[test]
    fn title_and_casefold() {
        assert_eq!(title("partly cloudy day"), "Partly Cloudy Day");
        assert_eq!(title("fOO bar"), "Foo Bar");
        assert_eq!(casefold("Straße"), "strasse");
    }

    #[test]
    fn fromisoformat_forms() {
        let (n, o) = fromisoformat("2025-01-15T12:00").unwrap();
        assert_eq!(n.to_string(), "2025-01-15 12:00:00");
        assert!(o.is_none());
        let (_, o) = fromisoformat("2025-01-15T12:00:00Z").unwrap();
        assert_eq!(o.unwrap().local_minus_utc(), 0);
        let (_, o) = fromisoformat("2025-01-15T12:00:00+05:30").unwrap();
        assert_eq!(o.unwrap().local_minus_utc(), 19800);
        let (n, _) = fromisoformat("2025-01-15").unwrap();
        assert_eq!(n.to_string(), "2025-01-15 00:00:00");
        assert!(fromisoformat("nope").is_none());
    }

    #[test]
    fn isoformat_forms() {
        let (n, _) = fromisoformat("2025-01-15T06:00").unwrap();
        assert_eq!(isoformat(n, None), "2025-01-15T06:00:00");
        assert_eq!(
            isoformat(n, FixedOffset::east_opt(-18000)),
            "2025-01-15T06:00:00-05:00"
        );
    }
}
