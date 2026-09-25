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
