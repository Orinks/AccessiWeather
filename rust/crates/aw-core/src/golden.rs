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
    let differ = || Some(format!("{path}: {a} != {b}"));
    match (a, b) {
        (Value::Number(x), Value::Number(y)) if x.as_f64() == y.as_f64() => None,
        (Value::String(x), Value::String(y)) if x != y => {
            let parse = |s: &str| chrono::DateTime::parse_from_rfc3339(s).ok();
            match (parse(x), parse(y)) {
                (Some(p), Some(q)) if p == q && p.offset() == q.offset() => None,
                _ => differ(),
            }
        }
        (Value::Array(x), Value::Array(y)) if x.len() == y.len() => x
            .iter()
            .zip(y)
            .enumerate()
            .find_map(|(i, (p, q))| json_diff(p, q, &format!("{path}[{i}]"))),
        (Value::Object(x), Value::Object(y)) => x.keys().chain(y.keys()).find_map(|k| {
            json_diff(
                x.get(k).unwrap_or(&Value::Null),
                y.get(k).unwrap_or(&Value::Null),
                &format!("{path}.{k}"),
            )
        }),
        _ if a == b => None,
        _ => differ(),
    }
}

/// Assert `actual` serialises to JSON equal (per [`json_diff`]) to `expected`.
pub fn assert_json_eq<T: serde::Serialize>(actual: &T, expected: &Value, context: &str) {
    let actual = serde_json::to_value(actual).expect("serialisable");
    if let Some(diff) = json_diff(&actual, expected, "$") {
        panic!("{context}: {diff}");
    }
}
