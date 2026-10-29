//! WeatherIndex station directory, feeds and coverage metadata.
//!
//! Ports `noaa_radio/weatherindex_client.py`.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use aw_providers::HttpClient;
use serde_json::{Map, Value};

use crate::stations::{Station, StationDirectory};

pub const WEATHERINDEX_API_URL: &str = "https://api.wxindex.org/v1/stations/{call_sign}";
pub const WEATHERINDEX_DIRECTORY_URL: &str = "https://api.wxindex.org/v1/stations/all";
pub const DEFAULT_CACHE_TTL: Duration = Duration::from_secs(1800);
/// `<config>/noaa_radio_stations.json`: the last directory download, used
/// when WeatherIndex can't be reached.
pub const DIRECTORY_FILE_NAME: &str = "noaa_radio_stations.json";
/// How long to wait before retrying the directory download after a failure.
const DIRECTORY_RETRY_DELAY: Duration = Duration::from_secs(300);

/// A station with live feeds, from the WeatherIndex station directory.
#[derive(Debug, Clone, PartialEq)]
pub struct WeatherIndexDirectoryStation {
    pub call_sign: String,
    pub city: String,
    pub state: String,
    pub frequency: Option<f64>,
    pub latitude: Option<f64>,
    pub longitude: Option<f64>,
    pub status: String,
    pub stream_urls: Vec<String>,
}

impl WeatherIndexDirectoryStation {
    /// The finder's `Station`, or `None` without coordinates.
    pub fn to_station(&self) -> Option<Station> {
        let (lat, lon) = (self.latitude?, self.longitude?);
        let mut name = self.city.clone();
        if !self.state.is_empty() && !name.to_uppercase().ends_with(&format!(", {}", self.state)) {
            name = if name.is_empty() {
                self.state.clone()
            } else {
                format!("{name}, {}", self.state)
            };
        }
        let mut station = Station::new(
            &self.call_sign,
            self.frequency.unwrap_or(0.0),
            &name,
            lat,
            lon,
            &self.state,
        );
        station.status = self.status.clone();
        Some(station)
    }
}

/// The loaded directory and when it should be fetched again.
struct Directory {
    stations: Vec<WeatherIndexDirectoryStation>,
    refresh_at: Instant,
}

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
    directory_url: String,
    directory_cache_path: Option<PathBuf>,
    directory: Mutex<Option<Directory>>,
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
            directory_url: WEATHERINDEX_DIRECTORY_URL.to_string(),
            directory_cache_path: None,
            directory: Mutex::default(),
        }
    }

    /// Keep a copy of the directory at `path` for when the API is down.
    pub fn with_directory_cache_path(mut self, path: impl AsRef<Path>) -> Self {
        self.directory_cache_path = Some(path.as_ref().to_path_buf());
        self
    }

    pub fn with_directory_url(mut self, url: &str) -> Self {
        self.directory_url = url.to_string();
        self
    }

    /// Every station WeatherIndex lists with a live feed.
    ///
    /// One request, cached for the TTL. When it fails: the previous
    /// in-memory copy, then the on-disk copy from an earlier run, then an
    /// empty list, and the download is retried after five minutes.
    pub fn get_all_stations(&self) -> Vec<WeatherIndexDirectoryStation> {
        if let Some(directory) = self.directory.lock().unwrap().as_ref() {
            if Instant::now() < directory.refresh_at {
                return directory.stations.clone();
            }
        }
        let fetched = self
            .http
            .get_json(&self.directory_url)
            .map_err(|e| e.to_string())
            .and_then(|payload| {
                let stations = parse_directory(&payload);
                if stations.is_empty() {
                    Err("the station directory is empty".to_string())
                } else {
                    Ok((payload, stations))
                }
            });
        match fetched {
            Ok((payload, stations)) => {
                self.save_directory_to_disk(&payload);
                *self.directory.lock().unwrap() = Some(Directory {
                    stations: stations.clone(),
                    refresh_at: Instant::now() + self.cache_ttl,
                });
                stations
            }
            Err(e) => {
                tracing::warn!("Failed to fetch WeatherIndex station directory: {e}");
                let mut directory = self.directory.lock().unwrap();
                let fallback = directory
                    .as_ref()
                    .map(|d| d.stations.clone())
                    .filter(|s| !s.is_empty())
                    .or_else(|| self.load_directory_from_disk())
                    .unwrap_or_default();
                *directory = Some(Directory {
                    stations: fallback.clone(),
                    refresh_at: Instant::now() + DIRECTORY_RETRY_DELAY.min(self.cache_ttl),
                });
                fallback
            }
        }
    }

    /// True once a directory (live or from disk) has been loaded.
    pub fn has_station_directory(&self) -> bool {
        self.directory
            .lock()
            .unwrap()
            .as_ref()
            .is_some_and(|d| !d.stations.is_empty())
    }

    /// Feeds from the loaded directory; `None` when it doesn't list the
    /// station (or nothing is loaded yet). Never touches the network.
    fn directory_stream_urls(&self, call_sign: &str) -> Option<Vec<String>> {
        let directory = self.directory.lock().unwrap();
        directory
            .as_ref()?
            .stations
            .iter()
            .find(|s| s.call_sign == call_sign)
            .map(|s| s.stream_urls.clone())
    }

    fn load_directory_from_disk(&self) -> Option<Vec<WeatherIndexDirectoryStation>> {
        let path = self.directory_cache_path.as_ref()?;
        let text = std::fs::read_to_string(path).ok()?;
        match serde_json::from_str::<Value>(&text) {
            Ok(payload) => Some(parse_directory(&payload)).filter(|s| !s.is_empty()),
            Err(e) => {
                tracing::warn!("Failed to load cached WeatherIndex station directory: {e}");
                None
            }
        }
    }

    fn save_directory_to_disk(&self, payload: &Value) {
        let Some(path) = &self.directory_cache_path else {
            return;
        };
        let result = path
            .parent()
            .map_or(Ok(()), std::fs::create_dir_all)
            .and_then(|()| std::fs::write(path, payload.to_string()));
        if let Err(e) = result {
            tracing::warn!("Failed to save WeatherIndex station directory cache: {e}");
        }
    }

    /// Live stream URLs for a call sign; empty on any failure (not cached).
    pub fn get_stream_urls(&self, call_sign: &str) -> Vec<String> {
        let normalized = call_sign.trim().to_uppercase();
        if normalized.is_empty() {
            return Vec::new();
        }
        if let Some(urls) = self.directory_stream_urls(&normalized) {
            return urls;
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

impl StationDirectory for WeatherIndexClient {
    fn stations(&self) -> Vec<Station> {
        self.get_all_stations()
            .iter()
            .filter_map(WeatherIndexDirectoryStation::to_station)
            .collect()
    }

    fn cached_stations(&self) -> Vec<Station> {
        let directory = self.directory.lock().unwrap();
        directory.as_ref().map_or_else(Vec::new, |d| {
            d.stations
                .iter()
                .filter_map(WeatherIndexDirectoryStation::to_station)
                .collect()
        })
    }
}

/// Stations with at least one feed from a `/v1/stations/all` payload (a
/// list, or an object with a `stations` list), first entry per call sign.
pub(crate) fn parse_directory(payload: &Value) -> Vec<WeatherIndexDirectoryStation> {
    let entries = match payload {
        Value::Array(entries) => entries,
        Value::Object(object) => match object.get("stations") {
            Some(Value::Array(entries)) => entries,
            _ => return Vec::new(),
        },
        _ => return Vec::new(),
    };
    let mut stations: Vec<WeatherIndexDirectoryStation> = Vec::new();
    for entry in entries {
        let Some(object) = entry.as_object() else {
            continue;
        };
        let Some(call_sign) = [object.get("callsign"), object.get("call_sign")]
            .into_iter()
            .flatten()
            .find(|v| truthy(v))
            .and_then(Value::as_str)
            .map(|s| s.trim().to_uppercase())
            .filter(|s| !s.is_empty())
        else {
            continue;
        };
        if stations.iter().any(|s| s.call_sign == call_sign) {
            continue;
        }
        let stream_urls = parse_stream_urls(entry);
        if stream_urls.is_empty() {
            continue;
        }
        let text = |key: &str| {
            object
                .get(key)
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string()
        };
        let state = [object.get("state_slug"), object.get("state")]
            .into_iter()
            .flatten()
            .find(|v| truthy(v))
            .and_then(Value::as_str)
            .map_or_else(String::new, |s| s.trim().to_uppercase());
        stations.push(WeatherIndexDirectoryStation {
            call_sign,
            city: text("city"),
            state,
            frequency: as_float(object.get("frequency")),
            latitude: as_float(object.get("latitude")),
            longitude: as_float(object.get("longitude")),
            status: text("status").to_uppercase(),
            stream_urls,
        });
    }
    stations
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

    const ALL_URL: &str = "https://api.wxindex.org/v1/stations/all";

    fn directory_payload() -> Value {
        json!({"stations": [
            {"callsign": "wxk27", "city": "Austin", "state_slug": "tx", "frequency": "162.400",
             "latitude": 30.3219, "longitude": -97.8033, "status": "normal",
             "feeds": [{"stream_url": "https://example.com/wxk27"}]},
            {"callsign": "WXK27", "city": "Duplicate", "feeds": [{"stream_url": "https://dup"}]},
            {"callsign": "KZZ99", "city": "No Feeds", "feeds": []},
            {"call_sign": "WXL45", "city": "Keytesville, MO", "state": "MO",
             "latitude": 39.43, "longitude": -92.94, "status": "OUT OF SERVICE",
             "feeds": [{"stream_url": "https://example.com/wxl45"}]},
            {"callsign": "NOLOC", "city": "Nowhere", "state_slug": "KS",
             "feeds": [{"stream_url": "https://example.com/noloc"}]},
            "junk"
        ]})
    }

    #[test]
    fn parses_directory_entries_with_feeds() {
        let stations = parse_directory(&directory_payload());
        let call_signs: Vec<_> = stations.iter().map(|s| s.call_sign.as_str()).collect();
        assert_eq!(call_signs, ["WXK27", "WXL45", "NOLOC"]);
        assert_eq!(stations[0].state, "TX");
        assert_eq!(stations[0].frequency, Some(162.4));
        assert_eq!(stations[0].status, "NORMAL");
        assert_eq!(stations[0].stream_urls, ["https://example.com/wxk27"]);
        // A bare list works too.
        assert_eq!(parse_directory(&directory_payload()["stations"]).len(), 3);
        assert!(parse_directory(&json!({"stations": "x"})).is_empty());

        let austin = stations[0].to_station().unwrap();
        assert_eq!(austin.name, "Austin, TX");
        assert!(!austin.is_out_of_service());
        let keytesville = stations[1].to_station().unwrap();
        assert_eq!(keytesville.name, "Keytesville, MO");
        assert!(keytesville.is_out_of_service());
        assert!(stations[2].to_station().is_none(), "no coordinates");
    }

    #[test]
    fn directory_is_cached_and_answers_stream_lookups() {
        let dir = tempfile::tempdir().unwrap();
        let cache_path = dir.path().join(DIRECTORY_FILE_NAME);
        let http = Arc::new(FixtureClient::new().with(ALL_URL, directory_payload()));
        let client = WeatherIndexClient::new(http.clone()).with_directory_cache_path(&cache_path);
        assert!(!client.has_station_directory());
        assert!(client.cached_stations().is_empty());

        assert_eq!(client.get_all_stations().len(), 3);
        assert_eq!(client.get_all_stations().len(), 3);
        assert!(client.has_station_directory());
        assert_eq!(
            client.get_stream_urls("wxk27"),
            ["https://example.com/wxk27"]
        );
        // One request: the directory answers the feed lookup.
        assert_eq!(http.request_log(), [ALL_URL]);
        let call_signs: Vec<_> = client
            .cached_stations()
            .into_iter()
            .map(|s| s.call_sign)
            .collect();
        assert_eq!(call_signs, ["WXK27", "WXL45"]);
        assert!(cache_path.exists());
    }

    #[test]
    fn failed_download_falls_back_to_the_copy_on_disk() {
        let dir = tempfile::tempdir().unwrap();
        let cache_path = dir.path().join(DIRECTORY_FILE_NAME);
        std::fs::write(&cache_path, directory_payload().to_string()).unwrap();
        let http = Arc::new(FixtureClient::new().with_status(ALL_URL, 503));
        let cached = WeatherIndexClient::new(http.clone()).with_directory_cache_path(&cache_path);
        assert_eq!(cached.get_all_stations().len(), 3);
        // The fallback is reused until the retry delay passes.
        assert_eq!(cached.get_all_stations().len(), 3);
        assert_eq!(http.request_log().len(), 1);

        let (_http, offline) = client(FixtureClient::new());
        assert!(offline.get_all_stations().is_empty());
        assert!(!offline.has_station_directory());
    }

    #[test]
    fn empty_directory_counts_as_a_failure() {
        let http = Arc::new(FixtureClient::new().with(ALL_URL, json!({"stations": []})));
        let client = WeatherIndexClient::new(http);
        assert!(client.get_all_stations().is_empty());
        assert!(StationDirectory::stations(&client).is_empty());
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
