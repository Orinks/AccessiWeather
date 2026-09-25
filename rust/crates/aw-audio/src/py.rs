//! Small helpers that reproduce Python behaviour the sound code relies on
//! (`str()`, `float()`, `str.title()`, `json.dump(indent=N)`).

use std::fmt::Write as _;
use std::path::Path;

use serde::Serialize;
use serde_json::Value;

/// Python `str(value)` for a JSON-decoded value.
pub(crate) fn py_str(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        _ => py_repr(v),
    }
}

/// Python `repr(value)` for a JSON-decoded value.
pub(crate) fn py_repr(v: &Value) -> String {
    match v {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Number(n) => n.to_string(),
        Value::String(s) => py_repr_str(s),
        Value::Array(items) => {
            let inner: Vec<String> = items.iter().map(py_repr).collect();
            format!("[{}]", inner.join(", "))
        }
        Value::Object(map) => {
            let inner: Vec<String> = map
                .iter()
                .map(|(k, v)| format!("{}: {}", py_repr_str(k), py_repr(v)))
                .collect();
            format!("{{{}}}", inner.join(", "))
        }
    }
}

/// Python `repr(str)`: single quotes unless the text holds a single quote
/// and no double quote.
pub(crate) fn py_repr_str(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(s.len() + 2);
    out.push(quote);
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
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// Python type name used in `'list' object has no attribute 'items'`.
pub(crate) fn py_type_name(v: &Value) -> &'static str {
    match v {
        Value::Null => "NoneType",
        Value::Bool(_) => "bool",
        Value::Number(n) if n.is_f64() => "float",
        Value::Number(_) => "int",
        Value::String(_) => "str",
        Value::Array(_) => "list",
        Value::Object(_) => "dict",
    }
}

/// Python `float(value)`; `None` where Python raises.
pub(crate) fn py_float(v: &Value) -> Option<f64> {
    match v {
        Value::Number(n) => n.as_f64(),
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        Value::String(s) => s.trim().replace('_', "").parse().ok(),
        _ => None,
    }
}

/// Python truthiness of a JSON value.
pub(crate) fn py_truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64() != Some(0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// `max(0.0, min(1.0, v))` with Python's argument-order semantics (NaN -> 1.0).
pub(crate) fn clamp_volume(v: f64) -> f64 {
    let low = if v < 1.0 { v } else { 1.0 };
    if low > 0.0 {
        low
    } else {
        0.0
    }
}

/// `dict.get(key, default)` then `str()`, treating a missing key as `default`.
pub(crate) fn get_str(obj: &serde_json::Map<String, Value>, key: &str, default: &str) -> String {
    obj.get(key).map(py_str).unwrap_or_else(|| default.into())
}

/// `dict.get(key) or default` then `str()`.
pub(crate) fn get_str_or(obj: &serde_json::Map<String, Value>, key: &str, default: &str) -> String {
    obj.get(key)
        .filter(|v| py_truthy(v))
        .map(py_str)
        .unwrap_or_else(|| default.into())
}

/// Python `str.title()`.
pub(crate) fn py_title(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut prev_cased = false;
    for c in s.chars() {
        let cased = c.is_lowercase() || c.is_uppercase();
        if prev_cased {
            out.extend(c.to_lowercase());
        } else {
            out.extend(c.to_uppercase());
        }
        prev_cased = cased;
    }
    out
}

/// `json.dumps(value, indent=indent)` byte for byte: Python escapes every
/// non-ASCII character (`ensure_ascii`) and writes no trailing newline.
pub(crate) fn python_json(v: &Value, indent: usize) -> String {
    let spaces = " ".repeat(indent);
    let mut buf = Vec::new();
    let mut ser = serde_json::Serializer::with_formatter(
        &mut buf,
        serde_json::ser::PrettyFormatter::with_indent(spaces.as_bytes()),
    );
    v.serialize(&mut ser).expect("JSON values always serialise");
    let text = String::from_utf8(buf).expect("serde_json writes UTF-8");
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        if c.is_ascii() && c != '\x7f' {
            out.push(c);
        } else {
            for unit in c.encode_utf16(&mut [0; 2]) {
                let _ = write!(out, "\\u{unit:04x}");
            }
        }
    }
    out
}

/// Write `json.dump(data, f, indent=indent)` output to `path`.
pub(crate) fn write_python_json(path: &Path, v: &Value, indent: usize) -> std::io::Result<()> {
    std::fs::write(path, python_json(v, indent))
}

/// Python `int(x)` for a float (truncation toward zero).
pub(crate) fn py_int(v: f64) -> i64 {
    v.trunc() as i64
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn python_json_matches_json_dump() {
        let v = json!({"name": "Caf\u{e9} \u{1F600}", "sounds": {}, "v": 0.55, "n": [1, 2.0]});
        assert_eq!(
            python_json(&v, 2),
            "{\n  \"name\": \"Caf\\u00e9 \\ud83d\\ude00\",\n  \"sounds\": {},\n  \"v\": 0.55,\n  \"n\": [\n    1,\n    2.0\n  ]\n}"
        );
    }

    #[test]
    fn title_and_clamp_follow_python() {
        assert_eq!(py_title("tornado warning"), "Tornado Warning");
        assert_eq!(py_title("wind2x gust"), "Wind2X Gust");
        assert_eq!(clamp_volume(f64::NAN), 1.0);
        assert_eq!(clamp_volume(-3.0), 0.0);
        assert_eq!(py_int(0.29 * 100.0), 28);
        assert_eq!(py_repr_str("../x"), "'../x'");
        assert_eq!(py_repr(&json!([{"msg": "bad"}])), "[{'msg': 'bad'}]");
    }
}
