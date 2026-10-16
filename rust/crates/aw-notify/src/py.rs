//! Small reproductions of the Python stdlib behaviour the notification code
//! depends on: `datetime.isoformat` / `fromisoformat`, `str.splitlines`,
//! `urllib.parse.quote_plus` / `parse_qs`, `strftime("%I:%M %p")` and
//! `json.dumps` with default separators. Keeping these exact is what lets
//! the state file and the notification text match the Python app byte for
//! byte.

use chrono::{DateTime, FixedOffset, NaiveDate, NaiveDateTime, NaiveTime, Offset, Timelike, Utc};
use serde_json::Value;

/// `datetime.isoformat()` for an aware datetime.
pub fn isoformat(dt: &DateTime<FixedOffset>) -> String {
    let mut s = isoformat_naive(&dt.naive_local());
    s.push_str(&format_offset(dt.offset().local_minus_utc()));
    s
}

/// `datetime.now(UTC).isoformat()` style (offset `+00:00`).
pub fn isoformat_utc(dt: &DateTime<Utc>) -> String {
    isoformat(&dt.fixed_offset())
}

/// `datetime.isoformat()` for a naive datetime (microseconds only when non-zero).
pub fn isoformat_naive(n: &NaiveDateTime) -> String {
    let base = n.format("%Y-%m-%dT%H:%M:%S").to_string();
    let micros = n.nanosecond() / 1000;
    if micros != 0 {
        format!("{base}.{micros:06}")
    } else {
        base
    }
}

fn format_offset(secs: i32) -> String {
    let sign = if secs < 0 { '-' } else { '+' };
    let a = secs.abs();
    let (h, m, s) = (a / 3600, a % 3600 / 60, a % 60);
    if s != 0 {
        format!("{sign}{h:02}:{m:02}:{s:02}")
    } else {
        format!("{sign}{h:02}:{m:02}")
    }
}

/// Result of `datetime.fromisoformat`: Python keeps naive and aware values apart.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PyDateTime {
    Naive(NaiveDateTime),
    Aware(DateTime<FixedOffset>),
}

impl PyDateTime {
    /// The aware value; naive values are taken as UTC (Python's own parsers
    /// only ever store aware times in these fields).
    pub fn aware(self) -> DateTime<FixedOffset> {
        match self {
            PyDateTime::Aware(dt) => dt,
            PyDateTime::Naive(n) => n.and_utc().fixed_offset(),
        }
    }

    pub fn isoformat(&self) -> String {
        match self {
            PyDateTime::Aware(dt) => isoformat(dt),
            PyDateTime::Naive(n) => isoformat_naive(n),
        }
    }
}

/// `datetime.fromisoformat` for the shapes the app writes and reads:
/// `YYYY-MM-DD[(T| )HH[:MM[:SS[.f+]]]][Z|±HH[:MM[:SS]]|±HHMM]`.
pub fn fromisoformat(s: &str) -> Option<PyDateTime> {
    if s.len() < 10 || !s.is_char_boundary(10) {
        return None;
    }
    let date = NaiveDate::parse_from_str(&s[..10], "%Y-%m-%d").ok()?;
    let rest = &s[10..];
    if rest.is_empty() {
        return Some(PyDateTime::Naive(date.and_time(NaiveTime::MIN)));
    }
    let sep = rest.chars().next()?;
    let rest = &rest[sep.len_utf8()..];
    let (time_str, offset) = if let Some(t) = rest.strip_suffix('Z') {
        (t, Some(0))
    } else if let Some(i) = rest.rfind(['+', '-']) {
        (&rest[..i], Some(parse_offset(&rest[i..])?))
    } else {
        (rest, None)
    };
    let time = ["%H:%M:%S%.f", "%H:%M:%S", "%H:%M", "%H"]
        .iter()
        .find_map(|f| NaiveTime::parse_from_str(time_str, f).ok())
        .or_else(|| {
            time_str
                .parse::<u32>()
                .ok()
                .and_then(|h| NaiveTime::from_hms_opt(h, 0, 0))
        })?;
    let naive = date.and_time(time);
    Some(match offset {
        None => PyDateTime::Naive(naive),
        Some(secs) => {
            let off = FixedOffset::east_opt(secs)?;
            PyDateTime::Aware(naive.and_local_timezone(off).single()?)
        }
    })
}

fn parse_offset(s: &str) -> Option<i32> {
    let sign = match s.as_bytes().first()? {
        b'+' => 1,
        b'-' => -1,
        _ => return None,
    };
    let digits: String = s[1..].chars().filter(|c| *c != ':').collect();
    let digits = digits.split('.').next()?;
    let part = |i: usize| -> Option<i32> {
        digits
            .get(i..i + 2)
            .map_or(Some(0), |p| p.parse::<i32>().ok())
    };
    if !matches!(digits.len(), 2 | 4 | 6) {
        return None;
    }
    Some(sign * (part(0)? * 3600 + part(2)? * 60 + part(4)?))
}

/// Parse an aware timestamp (naive values are treated as UTC).
pub fn parse_aware(s: &str) -> Option<DateTime<FixedOffset>> {
    fromisoformat(s).map(PyDateTime::aware)
}

/// `str.splitlines()` (no keepends).
pub fn splitlines(s: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut start = 0;
    let mut iter = s.char_indices().peekable();
    while let Some((i, c)) = iter.next() {
        match c {
            '\r' => {
                out.push(&s[start..i]);
                if let Some(&(_, '\n')) = iter.peek() {
                    iter.next();
                    start = i + 2;
                } else {
                    start = i + 1;
                }
            }
            '\n' | '\x0b' | '\x0c' | '\x1c' | '\x1d' | '\x1e' | '\u{85}' | '\u{2028}'
            | '\u{2029}' => {
                out.push(&s[start..i]);
                start = i + c.len_utf8();
            }
            _ => {}
        }
    }
    if start < s.len() {
        out.push(&s[start..]);
    }
    out
}

/// `" ".join(text.split())`.
pub fn collapse_whitespace(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// `text[:n]` by code points.
pub fn truncate_chars(text: &str, n: usize) -> &str {
    match text.char_indices().nth(n) {
        Some((i, _)) => &text[..i],
        None => text,
    }
}

/// `strftime("%I:%M %p")` with the leading zero removed (`"3:05 PM"`).
pub fn clock_12h(t: &impl Timelike) -> String {
    let (pm, hour) = t.hour12();
    format!("{hour}:{:02} {}", t.minute(), if pm { "PM" } else { "AM" })
}

/// `tzname()` of a datetime carrying a fixed `datetime.timezone` offset:
/// `"UTC"` for zero, `"UTC-04:00"` otherwise.
pub fn fixed_tzname(offset: &FixedOffset) -> String {
    let secs = offset.fix().local_minus_utc();
    if secs == 0 {
        "UTC".into()
    } else {
        format!("UTC{}", format_offset(secs))
    }
}

/// `urllib.parse.quote_plus(s, safe="")`.
pub fn quote_plus(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'_' | b'.' | b'-' | b'~' => {
                out.push(b as char)
            }
            b' ' => out.push('+'),
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

/// `urllib.parse.unquote_plus` (invalid escapes kept literally, bad UTF-8 replaced).
pub fn unquote_plus(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'+' => out.push(b' '),
            b'%' if i + 2 < bytes.len() => {
                let hex = std::str::from_utf8(&bytes[i + 1..i + 3]).ok();
                match hex.and_then(|h| u8::from_str_radix(h, 16).ok()) {
                    Some(v) => {
                        out.push(v);
                        i += 3;
                        continue;
                    }
                    None => out.push(b'%'),
                }
            }
            b => out.push(b),
        }
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// `urllib.parse.parse_qsl(qs, keep_blank_values=False)`.
pub fn parse_qsl(qs: &str) -> Vec<(String, String)> {
    qs.split('&')
        .filter(|p| !p.is_empty())
        .filter_map(|p| p.split_once('='))
        .filter(|(_, v)| !v.is_empty())
        .map(|(k, v)| (unquote_plus(k), unquote_plus(v)))
        .collect()
}

/// `json.dumps(value)` with Python's default `", "` / `": "` separators and
/// `ensure_ascii=True`, for the small single-line files Python writes that way.
pub fn json_dumps(value: &Value) -> String {
    let mut out = String::new();
    write_json(value, &mut out);
    out
}

fn write_json(value: &Value, out: &mut String) {
    match value {
        Value::Array(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                write_json(item, out);
            }
            out.push(']');
        }
        Value::Object(map) => {
            out.push('{');
            for (i, (k, v)) in map.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                write_ascii_string(k, out);
                out.push_str(": ");
                write_json(v, out);
            }
            out.push('}');
        }
        Value::String(s) => write_ascii_string(s, out),
        other => out.push_str(&other.to_string()),
    }
}

fn write_ascii_string(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\x08' => out.push_str("\\b"),
            '\x0c' => out.push_str("\\f"),
            c if (c as u32) < 0x20 || (c as u32) > 0x7e => {
                let mut buf = [0u16; 2];
                for unit in c.encode_utf16(&mut buf) {
                    out.push_str(&format!("\\u{unit:04x}"));
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

/// `json.dumps(value, indent=2, ensure_ascii=False)`, the format of
/// `runtime_state.json`.
pub fn json_dumps_indent2(value: &Value) -> String {
    serde_json::to_string_pretty(value).expect("JSON values always serialise")
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn isoformat_matches_python() {
        let off = FixedOffset::west_opt(4 * 3600).unwrap();
        let dt = off.with_ymd_and_hms(2026, 9, 25, 8, 5, 0).unwrap();
        assert_eq!(isoformat(&dt), "2026-09-25T08:05:00-04:00");
        let dt = dt + chrono::Duration::microseconds(1500);
        assert_eq!(isoformat(&dt), "2026-09-25T08:05:00.001500-04:00");
        let utc = Utc.with_ymd_and_hms(2026, 1, 2, 3, 4, 5).unwrap();
        assert_eq!(isoformat_utc(&utc), "2026-01-02T03:04:05+00:00");
    }

    #[test]
    fn fromisoformat_round_trips_python_shapes() {
        for s in [
            "2026-09-25T08:05:00-04:00",
            "2026-09-25T08:05:00.123456+00:00",
            "2026-09-25T08:05:00",
            "2026-09-25T08:05:00+05:30",
        ] {
            assert_eq!(fromisoformat(s).unwrap().isoformat(), s);
        }
        assert_eq!(
            fromisoformat("2026-09-25T08:05:00Z").unwrap().isoformat(),
            "2026-09-25T08:05:00+00:00"
        );
        assert_eq!(
            fromisoformat("2026-09-25 08:05").unwrap().isoformat(),
            "2026-09-25T08:05:00"
        );
        assert!(fromisoformat("not a date").is_none());
    }

    #[test]
    fn splitlines_matches_python() {
        assert_eq!(splitlines(""), Vec::<&str>::new());
        assert_eq!(splitlines("\n"), vec![""]);
        assert_eq!(splitlines("a\r\nb\rc\n"), vec!["a", "b", "c"]);
        assert_eq!(splitlines("a\n\nb"), vec!["a", "", "b"]);
    }

    #[test]
    fn query_encoding_matches_urllib() {
        assert_eq!(quote_plus("urn:oid:2.49 x/y"), "urn%3Aoid%3A2.49+x%2Fy");
        assert_eq!(
            unquote_plus("urn%3Aoid%3A2.49+x%2Fy%zz"),
            "urn:oid:2.49 x/y%zz"
        );
        assert_eq!(
            parse_qsl("kind=alert_details&alert_id=a%26b&empty=&bare"),
            vec![
                ("kind".to_string(), "alert_details".to_string()),
                ("alert_id".to_string(), "a&b".to_string())
            ]
        );
    }

    #[test]
    fn json_dumps_uses_python_separators() {
        let v =
            serde_json::json!({"kind": "discussion", "alert_id": null, "n": [1, true], "s": "é"});
        assert_eq!(
            json_dumps(&v),
            r#"{"kind": "discussion", "alert_id": null, "n": [1, true], "s": "\u00e9"}"#
        );
    }

    #[test]
    fn clock_and_tzname() {
        let off = FixedOffset::west_opt(4 * 3600).unwrap();
        let dt = off.with_ymd_and_hms(2026, 9, 25, 0, 5, 0).unwrap();
        assert_eq!(clock_12h(&dt), "12:05 AM");
        assert_eq!(fixed_tzname(dt.offset()), "UTC-04:00");
        assert_eq!(fixed_tzname(&FixedOffset::east_opt(0).unwrap()), "UTC");
    }
}
