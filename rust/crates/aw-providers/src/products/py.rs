//! Python-compatibility helpers so text products read exactly as they do in
//! the Python app: `datetime.isoformat` / `fromisoformat` (CPython 3.12 C
//! implementation), `str()` of JSON values, httpx / `urlencode` query escaping,
//! `str.splitlines` and truthiness.

use aw_core::model::Timestamp;
use chrono::{FixedOffset, Local, NaiveDate, NaiveDateTime, NaiveTime, TimeZone, Timelike, Utc};
use serde_json::Value;

/// `datetime.isoformat()` for an aware datetime.
pub fn isoformat(ts: &Timestamp) -> String {
    let mut out = ts.naive_local().format("%Y-%m-%dT%H:%M:%S").to_string();
    let micros = ts.nanosecond() / 1000;
    if micros != 0 {
        out.push_str(&format!(".{micros:06}"));
    }
    let offset = ts.offset().local_minus_utc();
    let sign = if offset < 0 { '-' } else { '+' };
    let abs = offset.unsigned_abs();
    out.push_str(&format!("{sign}{:02}:{:02}", abs / 3600, abs % 3600 / 60));
    if !abs.is_multiple_of(60) {
        out.push_str(&format!(":{:02}", abs % 60));
    }
    out
}

/// `value.astimezone(UTC).isoformat().replace("+00:00", "Z")`.
pub fn utc_z(ts: &Timestamp) -> String {
    isoformat(&ts.with_timezone(&Utc).fixed_offset()).replace("+00:00", "Z")
}

/// `datetime.fromisoformat` → wall time plus offset (`None` for naive input).
/// Week dates are not supported (nothing the app parses uses them).
pub fn fromisoformat(text: &str) -> Option<(NaiveDateTime, Option<FixedOffset>)> {
    let chars: Vec<char> = text.chars().collect();
    if chars.len() < 8 {
        return None;
    }
    let (date_len, extended) = match (chars[4], chars[5]) {
        ('W', _) | ('-', 'W') => return None,
        ('-', _) => (10, true),
        _ => (8, false),
    };
    if chars.len() < date_len {
        return None;
    }
    let year = digits(&chars, 0, 4)?;
    let (month, day) = if extended {
        if chars[7] != '-' {
            return None;
        }
        (digits(&chars, 5, 2)?, digits(&chars, 8, 2)?)
    } else {
        (digits(&chars, 4, 2)?, digits(&chars, 6, 2)?)
    };
    let date = NaiveDate::from_ymd_opt(year as i32, month, day)?;
    if chars.len() == date_len {
        return Some((date.and_time(NaiveTime::MIN), None));
    }
    let (h, m, s, us, offset) = parse_time(&chars[date_len + 1..])?;
    let time = NaiveTime::from_hms_micro_opt(h, m, s, us)?;
    Some((date.and_time(time), offset))
}

/// `fromisoformat`, with naive values treated as UTC (the IEM and NWS parsers).
pub fn parse_iso_utc(text: &str) -> Option<Timestamp> {
    let (naive, offset) = fromisoformat(text)?;
    Some(attach(naive, offset.unwrap_or_else(utc)))
}

/// Naive values are interpreted in the machine's local zone, matching what
/// Python's `.astimezone()` does with them at display time.
pub fn local_or_offset(naive: NaiveDateTime, offset: Option<FixedOffset>) -> Timestamp {
    match offset {
        Some(offset) => attach(naive, offset),
        None => Local
            .from_local_datetime(&naive)
            .earliest()
            .map(|t| t.fixed_offset())
            .unwrap_or_else(|| attach(naive, utc())),
    }
}

fn attach(naive: NaiveDateTime, offset: FixedOffset) -> Timestamp {
    offset
        .from_local_datetime(&naive)
        .single()
        .expect("fixed offsets are unambiguous")
}

pub fn utc() -> FixedOffset {
    FixedOffset::east_opt(0).expect("zero offset")
}

fn digits(chars: &[char], at: usize, n: usize) -> Option<u32> {
    let mut value = 0;
    for i in at..at + n {
        value = value * 10 + chars.get(i)?.to_digit(10)?;
    }
    Some(value)
}

type TimeParts = (u32, u32, u32, u32, Option<FixedOffset>);

/// CPython's `parse_isoformat_time`.
fn parse_time(t: &[char]) -> Option<TimeParts> {
    if t.is_empty() {
        return None;
    }
    let tz_pos = t
        .iter()
        .position(|c| matches!(c, 'Z' | '+' | '-'))
        .unwrap_or(t.len());
    let (h, m, s, us, trailing) = parse_hh_mm_ss_ff(t, tz_pos)?;
    if tz_pos == t.len() {
        return (!trailing).then_some((h, m, s, us, None));
    }
    if t[tz_pos] == 'Z' {
        return (tz_pos + 1 == t.len()).then_some((h, m, s, us, Some(utc())));
    }
    let sign = if t[tz_pos] == '-' { -1 } else { 1 };
    let tz = &t[tz_pos + 1..];
    let (th, tm, ts, _, tz_trailing) = parse_hh_mm_ss_ff(tz, tz.len())?;
    if tz_trailing {
        return None;
    }
    let seconds = sign * (th * 3600 + tm * 60 + ts) as i32;
    Some((h, m, s, us, Some(FixedOffset::east_opt(seconds)?)))
}

/// CPython's `parse_hh_mm_ss_ff`: `[HH[:?MM[:?SS]]][.,ffffff]`, reading
/// `t[end]` (a time-zone marker or the end of string) as a terminator.
/// The final flag is true when something other than end-of-string follows.
fn parse_hh_mm_ss_ff(t: &[char], end: usize) -> Option<(u32, u32, u32, u32, bool)> {
    let at = |i: usize| t.get(i).copied().unwrap_or('\0');
    let mut vals = [0u32; 3];
    let mut p = 0;
    let mut has_sep = true;
    for i in 0..3 {
        vals[i] = digits(t, p, 2)?;
        p += 2;
        let c = at(p);
        p += 1;
        if i == 0 {
            has_sep = c == ':';
        }
        if p >= end {
            return Some((vals[0], vals[1], vals[2], 0, c != '\0'));
        } else if has_sep && c == ':' {
            continue;
        } else if c == '.' || c == ',' {
            break;
        } else if !has_sep {
            p -= 1;
        } else {
            return None;
        }
    }
    let to_parse = (end - p).min(6);
    let mut micro = digits(t, p, to_parse)?;
    if to_parse < 6 {
        micro *= 10u32.pow(6 - to_parse as u32);
    }
    p += to_parse;
    while at(p).is_ascii_digit() {
        p += 1;
    }
    Some((vals[0], vals[1], vals[2], micro, at(p) != '\0'))
}

/// Python `repr(float)`.
pub fn py_float(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.into();
    }
    if x == 0.0 {
        return if x.is_sign_negative() { "-0.0" } else { "0.0" }.into();
    }
    let sci = format!("{:e}", x.abs());
    let (mantissa, exp) = sci.split_once('e').expect("LowerExp has an exponent");
    let exp: i32 = exp.parse().expect("numeric exponent");
    let digits: String = mantissa.chars().filter(char::is_ascii_digit).collect();
    let sign = if x < 0.0 { "-" } else { "" };
    let body = if (-4..16).contains(&exp) {
        if exp >= 0 {
            let int_len = exp as usize + 1;
            if digits.len() <= int_len {
                format!("{digits}{}.0", "0".repeat(int_len - digits.len()))
            } else {
                format!("{}.{}", &digits[..int_len], &digits[int_len..])
            }
        } else {
            format!("0.{}{digits}", "0".repeat((-exp - 1) as usize))
        }
    } else {
        let m = if digits.len() > 1 {
            format!("{}.{}", &digits[..1], &digits[1..])
        } else {
            digits
        };
        format!("{m}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs())
    };
    format!("{sign}{body}")
}

/// Python `str()` of a JSON-decoded value.
pub fn py_str(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        other => py_repr(other),
    }
}

fn py_repr(value: &Value) -> String {
    match value {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Number(n) if n.is_f64() => py_float(n.as_f64().unwrap_or_default()),
        Value::Number(n) => n.to_string(),
        Value::String(s) => repr_str(s),
        Value::Array(items) => {
            let inner: Vec<String> = items.iter().map(py_repr).collect();
            format!("[{}]", inner.join(", "))
        }
        Value::Object(map) => {
            let inner: Vec<String> = map
                .iter()
                .map(|(k, v)| format!("{}: {}", repr_str(k), py_repr(v)))
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
    let mut out = String::from(quote);
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if (c as u32) < 0x20 || c as u32 == 0x7f => {
                out.push_str(&format!("\\x{:02x}", c as u32))
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// Python truthiness of a JSON value.
pub fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// Percent-encode like `urllib.parse.quote(safe="")` (httpx params) or
/// `quote_plus` (`urlencode`, spaces become `+`).
pub fn quote(s: &str, space_plus: bool) -> String {
    let mut out = String::new();
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'.' | b'_' | b'~' => {
                out.push(b as char)
            }
            b' ' if space_plus => out.push('+'),
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

/// Build `url?k=v&...` the way httpx encodes a params dict.
pub fn with_params(url: &str, params: &[(&str, String)]) -> String {
    let query: Vec<String> = params
        .iter()
        .map(|(k, v)| format!("{}={}", quote(k, false), quote(v, false)))
        .collect();
    format!("{url}?{}", query.join("&"))
}

/// Python `str.splitlines()`.
pub fn splitlines(s: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut iter = s.char_indices().peekable();
    while let Some((i, c)) = iter.next() {
        let is_break = matches!(
            c,
            '\n' | '\r'
                | '\u{0b}'
                | '\u{0c}'
                | '\u{1c}'
                | '\u{1d}'
                | '\u{1e}'
                | '\u{85}'
                | '\u{2028}'
                | '\u{2029}'
        );
        if is_break {
            lines.push(&s[start..i]);
            let mut next = i + c.len_utf8();
            if c == '\r' {
                if let Some(&(j, '\n')) = iter.peek() {
                    iter.next();
                    next = j + 1;
                }
            }
            start = next;
        }
    }
    if start < s.len() {
        lines.push(&s[start..]);
    }
    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn float_repr_matches_python() {
        assert_eq!(py_float(-77.0), "-77.0");
        assert_eq!(py_float(35.7796), "35.7796");
        assert_eq!(py_float(1e20), "1e+20");
        assert_eq!(py_float(1e16), "1e+16");
        assert_eq!(py_float(1234567890123456.0), "1234567890123456.0");
        assert_eq!(py_float(0.0001), "0.0001");
        assert_eq!(py_float(0.00001), "1e-05");
        assert_eq!(py_float(0.1 + 0.2), "0.30000000000000004");
    }

    #[test]
    fn splitlines_matches_python() {
        assert_eq!(splitlines("a\r\nb\rc\n\nd\n"), vec!["a", "b", "c", "", "d"]);
        assert!(splitlines("").is_empty());
    }
}
