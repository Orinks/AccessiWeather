//! Shared helpers for the golden parity tests: load the JSON written by
//! `rust/tools/golden/*.py` and compare it with Rust output.

#![allow(dead_code)]

use std::path::PathBuf;

use aw_core::model::Timestamp;
use aw_providers::http::FixtureClient;
use chrono::DateTime;
use serde_json::Value;

pub fn golden_dir(area: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/golden")
        .join(area)
}

/// `(file stem, parsed JSON)` for golden files starting with `prefix`.
pub fn cases(area: &str, prefix: &str) -> Vec<(String, Value)> {
    let mut out = Vec::new();
    for entry in std::fs::read_dir(golden_dir(area)).expect("golden directory exists") {
        let path = entry.unwrap().path();
        let stem = path.file_stem().unwrap().to_string_lossy().to_string();
        if !stem.starts_with(prefix) || path.extension().is_none_or(|e| e != "json") {
            continue;
        }
        let text = std::fs::read_to_string(&path).unwrap();
        out.push((stem, serde_json::from_str(&text).unwrap()));
    }
    out.sort_by(|a, b| a.0.cmp(&b.0));
    assert!(!out.is_empty(), "no golden cases for {area}/{prefix}*");
    out
}

pub fn timestamp(value: &Value) -> Timestamp {
    DateTime::parse_from_rfc3339(value.as_str().expect("timestamp string")).expect("RFC 3339")
}

/// Compare Python golden JSON with Rust output. Missing keys equal `null`;
/// numbers compare with a 1e-9 relative tolerance; missing `false` is `false`; ISO datetimes compare by
/// instant and offset. Keys in `ignore` are skipped at any depth.
pub fn assert_matches(expected: &Value, actual: &Value, context: &str, ignore: &[&str]) {
    if let Err(message) = compare(expected, actual, "$", ignore) {
        panic!("{context}: {message}\nexpected: {expected}\nactual:   {actual}");
    }
}

fn compare(expected: &Value, actual: &Value, path: &str, ignore: &[&str]) -> Result<(), String> {
    match (expected, actual) {
        (Value::Number(e), Value::Number(a)) => {
            let (e, a) = (e.as_f64().unwrap(), a.as_f64().unwrap());
            if (e - a).abs() <= 1e-9 * e.abs().max(a.abs()).max(1.0) {
                Ok(())
            } else {
                Err(format!("{path}: {e} != {a}"))
            }
        }
        (Value::String(e), Value::String(a)) => {
            if e == a {
                return Ok(());
            }
            match (
                DateTime::parse_from_rfc3339(e),
                DateTime::parse_from_rfc3339(a),
            ) {
                (Ok(de), Ok(da)) if de == da && de.offset() == da.offset() => Ok(()),
                _ => Err(format!("{path}: {e:?} != {a:?}")),
            }
        }
        (Value::Array(e), Value::Array(a)) => {
            if e.len() != a.len() {
                return Err(format!("{path}: length {} != {}", e.len(), a.len()));
            }
            for (i, (ev, av)) in e.iter().zip(a).enumerate() {
                compare(ev, av, &format!("{path}[{i}]"), ignore)?;
            }
            Ok(())
        }
        (Value::Object(e), Value::Object(a)) => {
            for key in e.keys().chain(a.keys()) {
                if ignore.contains(&key.as_str()) {
                    continue;
                }
                // `Location` omits null/false fields when serialized.
                let (ev, av) = match (e.get(key), a.get(key)) {
                    (Some(Value::Bool(false)), None) | (None, Some(Value::Bool(false))) => continue,
                    (ev, av) => (ev.unwrap_or(&Value::Null), av.unwrap_or(&Value::Null)),
                };
                compare(ev, av, &format!("{path}.{key}"), ignore)?;
            }
            Ok(())
        }
        (e, a) if e == a => Ok(()),
        (e, a) => Err(format!("{path}: {e} != {a}")),
    }
}

/// A fixture client answering each recorded exchange by its exact URL.
pub fn fixture_from_exchanges(exchanges: &Value) -> FixtureClient {
    let mut http = FixtureClient::new();
    for exchange in exchanges.as_array().expect("exchanges array") {
        let url = exchange["url"].as_str().unwrap();
        http = match exchange.get("error").and_then(Value::as_str) {
            Some("timeout") => http.with_transport_error(url, "operation timed out"),
            Some(_) => http.with_transport_error(url, "connection refused"),
            None => match exchange["status"].as_u64().unwrap() {
                200 => http.with(url, exchange["body"].clone()),
                status => http.with_status(url, status as u16),
            },
        };
    }
    http
}

/// The recorded URLs and explicit headers must equal what Rust sent
/// (consecutive duplicates collapsed on both sides).
pub fn assert_requests(exchanges: &Value, http: &FixtureClient, context: &str) {
    let expected: Vec<(String, Vec<(String, String)>)> = exchanges
        .as_array()
        .unwrap()
        .iter()
        .map(|e| {
            let mut headers: Vec<(String, String)> = e["headers"]
                .as_object()
                .unwrap()
                .iter()
                .map(|(k, v)| (k.to_lowercase(), v.as_str().unwrap().to_string()))
                .collect();
            headers.sort();
            (e["url"].as_str().unwrap().to_string(), headers)
        })
        .collect();
    let mut actual: Vec<(String, Vec<(String, String)>)> = Vec::new();
    for (url, headers) in http.request_log().into_iter().zip(http.header_log()) {
        if actual.last().is_some_and(|(u, _)| *u == url) {
            continue;
        }
        let mut headers: Vec<(String, String)> = headers
            .into_iter()
            .map(|(k, v)| (k.to_lowercase(), v))
            .collect();
        headers.sort();
        actual.push((url, headers));
    }
    assert_eq!(expected, actual, "{context}: requests differ");
}
