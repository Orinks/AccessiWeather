//! WeatherIndex station feeds and coverage metadata.
//!
//! Ports `noaa_radio/weatherindex_client.py`.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use aw_providers::HttpClient;
use serde_json::{Map, Value};

pub const WEATHERINDEX_API_URL: &str = "https://api.wxindex.org/v1/stations/{call_sign}";
pub const DEFAULT_CACHE_TTL: Duration = Duration::from_secs(1800);

/// County coverage advertised for a station.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WeatherIndexServedCounty {
    pub county: String,
    pub same_code: String,
    pub state: String,
    pub area: Option<String>,
}

/// Coverage metadata from the WeatherIndex station detail endpoint.
#[derive(Debug, Clone, PartialEq)]
pub struct WeatherIndexStationMetadata {
    pub call_sign: String,
    pub wfo: Option<String>,
    pub latitude: Option<f64>,
    pub longitude: Option<f64>,
    pub served_counties: Vec<WeatherIndexServedCounty>,
}

type Cached<T> = Mutex<HashMap<String, (T, Instant)>>;

/// Resolves live stream URLs and SAME coverage for a known call sign.
pub struct WeatherIndexClient {
    http: Arc<dyn HttpClient>,
    api_url_template: String,
    cache_ttl: Duration,
    cache: Cached<Vec<String>>,
    metadata_cache: Cached<Option<WeatherIndexStationMetadata>>,
}

impl WeatherIndexClient {
    pub fn new(http: Arc<dyn HttpClient>) -> Self {
        Self::with_options(http, WEATHERINDEX_API_URL, DEFAULT_CACHE_TTL)
    }

    pub fn with_options(
        http: Arc<dyn HttpClient>,
        api_url_template: &str,
        cache_ttl: Duration,
    ) -> Self {
        Self {
            http,
            api_url_template: api_url_template.to_string(),
            cache_ttl,
            cache: Mutex::default(),
            metadata_cache: Mutex::default(),
        }
    }

    /// Live stream URLs for a call sign; empty on any failure (not cached).
    pub fn get_stream_urls(&self, call_sign: &str) -> Vec<String> {
        let normalized = call_sign.trim().to_uppercase();
        if normalized.is_empty() {
            return Vec::new();
        }
        if let Some(urls) = cached(&self.cache, &normalized, self.cache_ttl) {
            return urls;
        }
        match self.fetch(&normalized) {
            Ok(payload) => {
                let urls = parse_stream_urls(&payload);
                store(&self.cache, normalized, urls.clone());
                urls
            }
            Err(e) => {
                tracing::warn!("Failed to fetch WeatherIndex feeds for {normalized}: {e}");
                Vec::new()
            }
        }
    }

    /// Station coverage metadata, or `None` when unavailable.
    pub fn get_station_metadata(&self, call_sign: &str) -> Option<WeatherIndexStationMetadata> {
        let normalized = call_sign.trim().to_uppercase();
        if normalized.is_empty() {
            return None;
        }
        if let Some(metadata) = cached(&self.metadata_cache, &normalized, self.cache_ttl) {
            return metadata;
        }
        match self.fetch(&normalized) {
            Ok(payload) => {
                let metadata = parse_metadata(&payload, &normalized);
                store(&self.metadata_cache, normalized, metadata.clone());
                metadata
            }
            Err(e) => {
                tracing::warn!("Failed to fetch WeatherIndex metadata for {normalized}: {e}");
                None
            }
        }
    }

    fn fetch(&self, call_sign: &str) -> Result<Value, aw_providers::HttpError> {
        self.http
            .get_json(&self.api_url_template.replace("{call_sign}", call_sign))
    }
}

fn cached<T: Clone>(cache: &Cached<T>, key: &str, ttl: Duration) -> Option<T> {
    let cache = cache.lock().unwrap();
    let (value, at) = cache.get(key)?;
    (at.elapsed() < ttl).then(|| value.clone())
}

fn store<T>(cache: &Cached<T>, key: String, value: T) {
    cache.lock().unwrap().insert(key, (value, Instant::now()));
}

/// `payload["station"]` when it is an object, else the payload itself.
fn station_payload(payload: &Value) -> Option<&Map<String, Value>> {
    let object = payload.as_object()?;
    match object.get("station") {
        Some(Value::Object(station)) => Some(station),
        _ => Some(object),
    }
    .filter(|m| !m.is_empty())
}

pub(crate) fn parse_stream_urls(payload: &Value) -> Vec<String> {
    let Some(station) = station_payload(payload) else {
        return Vec::new();
    };
    let Some(Value::Array(feeds)) = station.get("feeds") else {
        return Vec::new();
    };
    let mut urls: Vec<String> = Vec::new();
    for feed in feeds {
        if let Some(url) = feed.get("stream_url").and_then(Value::as_str) {
            let url = url.trim();
            if !url.is_empty() && !urls.iter().any(|u| u == url) {
                urls.push(url.to_string());
            }
        }
    }
    urls
}

fn stripped(value: Option<&Value>) -> Option<String> {
    value
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

/// Python `float(value)`: numbers, numeric strings and booleans.
fn as_float(value: Option<&Value>) -> Option<f64> {
    match value? {
        Value::Number(n) => n.as_f64(),
        Value::String(s) => s.trim().parse().ok(),
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        _ => None,
    }
}

/// Python `str(value)` for the scalar JSON values a call sign can hold.
fn py_str(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        other => other.to_string(),
    }
}

/// A truthy JSON value in the Python sense.
fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64() != Some(0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

pub(crate) fn parse_metadata(
    payload: &Value,
    requested: &str,
) -> Option<WeatherIndexStationMetadata> {
    let station = station_payload(payload)?;
    let counties = match station.get("served_counties") {
        Some(Value::Array(items)) => items.as_slice(),
        _ => &[],
    };
    let served_counties = counties
        .iter()
        .filter_map(|county| {
            let same_code = normalize_same_code_value(county.get("same_code")?)?;
            let state = county.get("state")?.as_str()?;
            let name = county.get("county")?.as_str()?;
            Some(WeatherIndexServedCounty {
                county: name.trim().to_string(),
                same_code,
                state: state.trim().to_uppercase(),
                area: stripped(county.get("area")),
            })
        })
        .collect();

    let call_sign = [station.get("callsign"), station.get("call_sign")]
        .into_iter()
        .flatten()
        .find(|v| truthy(v))
        .map(py_str)
        .unwrap_or_else(|| requested.to_string());
    Some(WeatherIndexStationMetadata {
        call_sign: call_sign.trim().to_uppercase(),
        wfo: stripped(station.get("wfo")),
        latitude: as_float(station.get("latitude")),
        longitude: as_float(station.get("longitude")),
        served_counties,
    })
}

/// Normalize a SAME/FIPS county code string to six digits.
pub fn normalize_same_code(value: &str) -> Option<String> {
    let digits: String = value.trim().chars().filter(char::is_ascii_digit).collect();
    if digits.is_empty() {
        return None;
    }
    Some(format!("{digits:0>6}"))
}

/// [`normalize_same_code`] for a JSON value: integers are zero-padded too.
pub(crate) fn normalize_same_code_value(value: &Value) -> Option<String> {
    match value {
        Value::String(s) => normalize_same_code(s),
        Value::Number(n) => n.as_i64().map(|i| format!("{i:06}")),
        // Python's bool is an int.
        Value::Bool(b) => Some(format!("{:06}", u8::from(*b))),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use aw_providers::http::FixtureClient;
    use serde_json::json;

    fn client(fixture: FixtureClient) -> (Arc<FixtureClient>, WeatherIndexClient) {
        let http = Arc::new(fixture);
        (http.clone(), WeatherIndexClient::new(http))
    }

    const URL: &str = "https://api.wxindex.org/v1/stations/WXK27";

    #[test]
    fn fetches_v1_station_detail_endpoint_and_caches_by_call_sign() {
        let (http, client) = client(FixtureClient::new().with(
            URL,
            json!({"feeds": [{"stream_url": "https://example.com/live"}]}),
        ));
        assert_eq!(
            client.get_stream_urls("WXK27"),
            ["https://example.com/live"]
        );
        assert_eq!(
            client.get_stream_urls("wxk27"),
            ["https://example.com/live"]
        );
        assert_eq!(http.request_log(), [URL]);
    }

    #[test]
    fn parses_feeds_and_fails_soft() {
        let feeds = json!({"feeds": [
            {"stream_url": "https://example.com/1"},
            {"stream_url": " https://example.com/2 "},
            {"stream_url": "https://example.com/1"},
            {"stream_url": 5},
            "junk"
        ]});
        assert_eq!(
            parse_stream_urls(&feeds),
            ["https://example.com/1", "https://example.com/2"]
        );
        assert!(parse_stream_urls(&json!({"call_sign": "WXK27"})).is_empty());
        assert!(parse_stream_urls(&json!({"feeds": []})).is_empty());
        assert!(parse_stream_urls(&json!({"station": {"feeds": "x"}})).is_empty());
        // Missing fixture stands in for a 404 / network error.
        let (_http, client) = client(FixtureClient::new());
        assert!(client.get_stream_urls("WXK27").is_empty());
        assert!(client.get_station_metadata("WXK27").is_none());
        assert!(client.get_stream_urls("  ").is_empty());
    }

    #[test]
    fn metadata_from_cassette_shape() {
        let payload = json!({
            "callsign": "WXK27", "wfo": "Austin/San Antonio TX",
            "latitude": 30.3219, "longitude": -97.8033,
            "served_counties": [
                {"county": "Travis", "same_code": "048453", "state": "tx", "area": "All"},
                {"county": "Hays", "same_code": 48209, "state": "TX", "area": " "},
                {"county": "Bad", "same_code": "x", "state": "TX"}
            ],
            "feeds": []
        });
        let meta = parse_metadata(&payload, "WXK27").unwrap();
        assert_eq!(meta.call_sign, "WXK27");
        assert_eq!(meta.wfo.as_deref(), Some("Austin/San Antonio TX"));
        assert_eq!(meta.latitude, Some(30.3219));
        let codes: Vec<_> = meta
            .served_counties
            .iter()
            .map(|c| c.same_code.as_str())
            .collect();
        assert_eq!(codes, ["048453", "048209"]);
        assert_eq!(meta.served_counties[0].state, "TX");
        assert_eq!(meta.served_counties[1].area, None);
        assert!(parse_metadata(&json!([]), "X").is_none());
        assert_eq!(
            parse_metadata(&json!({"wfo": ""}), "abc")
                .unwrap()
                .call_sign,
            "ABC"
        );
    }

    #[test]
    fn golden_payload_parsing() {
        let golden = crate::golden("clients.json");
        for case in golden["weatherindex"].as_array().unwrap() {
            let payload = &case["payload"];
            let urls: Vec<String> = serde_json::from_value(case["urls"].clone()).unwrap();
            assert_eq!(parse_stream_urls(payload), urls, "{payload}");
            let metadata = parse_metadata(payload, "REQ1").map(|m| {
                json!({
                    "call_sign": m.call_sign,
                    "wfo": m.wfo,
                    "latitude": m.latitude,
                    "longitude": m.longitude,
                    "served_counties": m.served_counties.iter().map(|c| json!({
                        "county": c.county, "same_code": c.same_code, "state": c.state, "area": c.area
                    })).collect::<Vec<_>>(),
                })
            });
            assert_eq!(
                metadata.unwrap_or(Value::Null),
                case["metadata"],
                "{payload}"
            );
        }
    }
}
