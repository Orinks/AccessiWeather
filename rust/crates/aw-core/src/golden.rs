//! Test helper: loads the Python-generated golden files from
//! `rust/testdata/golden` (see `rust/tools/golden/*.py`).

use serde_json::Value;

pub fn load(relative: &str) -> Value {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/golden")
        .join(relative);
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("reading {}: {e}", path.display()));
    serde_json::from_str(&text).unwrap_or_else(|e| panic!("parsing {}: {e}", path.display()))
}

/// Deserialise one field of a golden case.
pub fn field<T: serde::de::DeserializeOwned>(case: &Value, key: &str) -> T {
    serde_json::from_value(case[key].clone())
        .unwrap_or_else(|e| panic!("{}: field {key}: {e}", case["name"]))
}

/// The first difference between `a` and `b` as "path: a != b", comparing
/// numbers by value (Python writes `72` where Rust writes `72.0`), datetimes
/// by instant and offset (chrono writes `Z` where Python writes `+00:00`),
/// and treating a missing key as `null`.
pub fn json_diff(a: &Value, b: &Value, path: &str) -> Option<String> {
    diff(a, b, path, true)
}

fn diff(a: &Value, b: &Value, path: &str, offsets: bool) -> Option<String> {
    let differ = || Some(format!("{path}: {a} != {b}"));
    match (a, b) {
        (Value::Number(x), Value::Number(y)) if x.as_f64() == y.as_f64() => None,
        (Value::String(x), Value::String(y)) if x != y => {
            let parse = |s: &str| chrono::DateTime::parse_from_rfc3339(s).ok();
            match (parse(x), parse(y)) {
                (Some(p), Some(q)) if p == q && (!offsets || p.offset() == q.offset()) => None,
                _ => differ(),
            }
        }
        (Value::Array(x), Value::Array(y)) if x.len() == y.len() => x
            .iter()
            .zip(y)
            .enumerate()
            .find_map(|(i, (p, q))| diff(p, q, &format!("{path}[{i}]"), offsets)),
        (Value::Object(x), Value::Object(y)) => x.keys().chain(y.keys()).find_map(|k| {
            diff(
                x.get(k).unwrap_or(&Value::Null),
                y.get(k).unwrap_or(&Value::Null),
                &format!("{path}.{k}"),
                offsets,
            )
        }),
        _ if a == b => None,
        _ => differ(),
    }
}

/// Assert `actual` serialises to JSON equal (per [`json_diff`]) to `expected`.
pub fn assert_json_eq<T: serde::Serialize>(actual: &T, expected: &Value, context: &str) {
    let actual = serde_json::to_value(actual).expect("serialisable");
    if let Some(d) = json_diff(&actual, expected, "$") {
        panic!("{context}: {d}");
    }
}

/// Like [`assert_json_eq`], but datetimes only need the same instant: for
/// values that are machine-local by nature (naive times read back as local),
/// whose offset depends on the timezone of the machine running the test.
pub fn assert_json_eq_instants<T: serde::Serialize>(actual: &T, expected: &Value, context: &str) {
    let actual = serde_json::to_value(actual).expect("serialisable");
    if let Some(d) = diff(&actual, expected, "$", false) {
        panic!("{context}: {d}");
    }
}
