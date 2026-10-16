//! Python formatting semantics the prompts and tool output depend on:
//! `str()`/`repr()` of JSON values, `format(x, "g")`, `str.title()`,
//! `str.casefold()` and `datetime.isoformat()`.

use chrono::{DateTime, FixedOffset, Timelike};
use serde_json::{Number, Value};

/// `repr(float)`: shortest round-trip digits, exponent past 1e16 / below 1e-4.
pub fn float(v: f64) -> String {
    if v.is_nan() {
        return "nan".into();
    }
    if v.is_infinite() {
        return if v > 0.0 { "inf" } else { "-inf" }.into();
    }
    // Rust's Debug output uses the same digits and thresholds; only the
    // exponent spelling differs ("1e16" vs "1e+16").
    let text = format!("{v:?}");
    match text.split_once('e') {
        Some((mantissa, exp)) => {
            let exp: i32 = exp.parse().unwrap_or(0);
            let sign = if exp < 0 { '-' } else { '+' };
            format!("{mantissa}e{sign}{:02}", exp.abs())
        }
        None => text,
    }
}

/// A value the data model keeps as `f64` that Python usually held as an int
/// (NWS temperatures, UV index): whole numbers print without ".0".
pub fn whole_or_float(v: f64) -> String {
    if v.is_finite() && v.fract() == 0.0 && v.abs() < 1e16 {
        format!("{}", v as i64)
    } else {
        float(v)
    }
}

pub fn number(n: &Number) -> String {
    if let Some(i) = n.as_i64() {
        i.to_string()
    } else if let Some(u) = n.as_u64() {
        u.to_string()
    } else {
        float(n.as_f64().unwrap_or(f64::NAN))
    }
}

/// `str(value)` for a JSON-decoded Python value.
pub fn str(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        other => repr(other),
    }
}

/// `repr(value)` for a JSON-decoded Python value.
pub fn repr(v: &Value) -> String {
    match v {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Number(n) => number(n),
        Value::String(s) => repr_str(s),
        Value::Array(items) => {
            let inner: Vec<String> = items.iter().map(repr).collect();
            format!("[{}]", inner.join(", "))
        }
        Value::Object(map) => {
            let inner: Vec<String> = map
                .iter()
                .map(|(k, v)| format!("{}: {}", repr_str(k), repr(v)))
                .collect();
            format!("{{{}}}", inner.join(", "))
        }
    }
}

fn repr_str(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(s.len() + 2);
    out.push(quote);
    for ch in s.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if (c as u32) < 0x20 || c as u32 == 0x7f => {
                out.push_str(&format!("\\x{:02x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// Python truthiness of a JSON-decoded value.
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

/// `format(v, "g")`: six significant digits, trailing zeros removed.
pub fn format_g(v: f64) -> String {
    if !v.is_finite() {
        return float(v);
    }
    if v == 0.0 {
        return if v.is_sign_negative() { "-0" } else { "0" }.into();
    }
    let sci = format!("{v:.5e}");
    let (mantissa, exp) = sci.split_once('e').unwrap_or((&sci, "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    if (-4..6).contains(&exp) {
        let decimals = (5 - exp) as usize;
        strip_fraction_zeros(format!("{v:.decimals$}"))
    } else {
        let sign = if exp < 0 { '-' } else { '+' };
        format!(
            "{}e{sign}{:02}",
            strip_fraction_zeros(mantissa.to_string()),
            exp.abs()
        )
    }
}

fn strip_fraction_zeros(s: String) -> String {
    if s.contains('.') {
        s.trim_end_matches('0').trim_end_matches('.').to_string()
    } else {
        s
    }
}

/// `str.title()`: uppercase a cased character that follows an uncased one.
pub fn title(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut previous_cased = false;
    for ch in s.chars() {
        let cased = ch.is_lowercase() || ch.is_uppercase();
        if cased && !previous_cased {
            out.extend(ch.to_uppercase());
        } else if cased {
            out.extend(ch.to_lowercase());
        } else {
            out.push(ch);
        }
        previous_cased = cased;
    }
    out
}

/// `str.casefold()` for the text AccessiWeather compares (ß is the common
/// character where it differs from lowercasing).
pub fn casefold(s: &str) -> String {
    s.to_lowercase().replace('ß', "ss")
}

/// `datetime.isoformat()` of an aware datetime.
pub fn isoformat(dt: &DateTime<FixedOffset>) -> String {
    let mut out = dt.format("%Y-%m-%dT%H:%M:%S").to_string();
    let micros = dt.nanosecond() % 1_000_000_000 / 1000;
    if micros != 0 {
        out.push_str(&format!(".{micros:06}"));
    }
    let offset = dt.offset().local_minus_utc();
    let sign = if offset < 0 { '-' } else { '+' };
    let abs = offset.abs();
    out.push_str(&format!("{sign}{:02}:{:02}", abs / 3600, abs % 3600 / 60));
    if abs % 60 != 0 {
        out.push_str(&format!(":{:02}", abs % 60));
    }
    out
}

/// First `n` characters (Python slices by code point).
pub fn head(s: &str, n: usize) -> &str {
    match s.char_indices().nth(n) {
        Some((i, _)) => &s[..i],
        None => s,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn float_repr_matches_python() {
        assert_eq!(float(22.0), "22.0");
        assert_eq!(float(0.1), "0.1");
        assert_eq!(float(1e16), "1e+16");
        assert_eq!(float(1.5e-5), "1.5e-05");
        assert_eq!(float(-40.7128), "-40.7128");
        assert_eq!(whole_or_float(72.0), "72");
        assert_eq!(whole_or_float(72.5), "72.5");
    }

    #[test]
    fn format_g_matches_python() {
        assert_eq!(format_g(0.0), "0");
        assert_eq!(format_g(2.5), "2.5");
        assert_eq!(format_g(12.0), "12");
        assert_eq!(format_g(0.000123456789), "0.000123457");
        assert_eq!(format_g(1234567.0), "1.23457e+06");
        assert_eq!(format_g(0.00001), "1e-05");
        assert_eq!(format_g(100000.0), "100000");
    }

    #[test]
    fn repr_and_title() {
        assert_eq!(
            repr(&json!({"a": [1, 2.5, null, true, "it's"]})),
            "{'a': [1, 2.5, None, True, \"it's\"]}"
        );
        assert_eq!(title("eva unit 01"), "Eva Unit 01");
        assert_eq!(title("x2y ai21"), "X2Y Ai21");
        assert_eq!(head("héllo", 2), "hé");
    }
}
