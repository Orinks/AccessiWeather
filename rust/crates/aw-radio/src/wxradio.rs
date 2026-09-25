//! Dynamic stream discovery from the wxradio.org Icecast status JSON.
//!
//! Ports `noaa_radio/wxradio_client.py`.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use aw_providers::HttpClient;
use serde_json::Value;

pub const WXRADIO_API_URL: &str = "https://wxradio.org/status-json.xsl";
pub const DEFAULT_CACHE_TTL: Duration = Duration::from_secs(1800);

pub type StreamMap = HashMap<String, Vec<String>>;

/// Extract a call sign from a mount such as `/FL-Tallahassee-KIH24` or
/// `/MI-MountPleasant-KZZ33-alt2` (state and city segments are skipped).
pub fn extract_call_sign(mount: &str) -> Option<String> {
    let name = mount.trim_start_matches('/');
    let parts: Vec<&str> = name.split('-').collect();
    if name.is_empty() || parts.len() < 3 {
        return None;
    }
    // `^[A-Z]{2,4}\d{2,4}$`, case-insensitive.
    let is_call_sign = |part: &&&str| {
        let letters = part.bytes().take_while(u8::is_ascii_alphabetic).count();
        let digits = part.len() - letters;
        (2..=4).contains(&letters)
            && (2..=4).contains(&digits)
            && part.bytes().skip(letters).all(|b| b.is_ascii_digit())
    };
    parts[2..]
        .iter()
        .find(is_call_sign)
        .map(|p| p.to_uppercase())
}

/// Fetches and caches live wxradio.org streams by call sign.
pub struct WxRadioClient {
    http: Arc<dyn HttpClient>,
    api_url: String,
    cache_ttl: Duration,
    cache: Mutex<Option<(StreamMap, Instant)>>,
}

impl WxRadioClient {
    pub fn new(http: Arc<dyn HttpClient>) -> Self {
        Self::with_options(http, WXRADIO_API_URL, DEFAULT_CACHE_TTL)
    }

    pub fn with_options(http: Arc<dyn HttpClient>, api_url: &str, cache_ttl: Duration) -> Self {
        Self {
            http,
            api_url: api_url.to_string(),
            cache_ttl,
            cache: Mutex::new(None),
        }
    }

    pub fn cache_ttl(&self) -> Duration {
        self.cache_ttl
    }

    /// Call sign → HTTPS stream URLs. Fresh cache first; on a fetch error the
    /// stale cache (or nothing) is returned.
    pub fn get_streams(&self) -> StreamMap {
        if let Some((streams, at)) = self.cache.lock().unwrap().as_ref() {
            if at.elapsed() < self.cache_ttl {
                return streams.clone();
            }
        }
        match self.http.get_json(&self.api_url) {
            Ok(data) => {
                let streams = parse_streams(&data);
                *self.cache.lock().unwrap() = Some((streams.clone(), Instant::now()));
                streams
            }
            Err(e) => {
                tracing::warn!("Failed to fetch wxradio.org streams, using cached/empty data: {e}");
                self.cache
                    .lock()
                    .unwrap()
                    .as_ref()
                    .map(|(streams, _)| streams.clone())
                    .unwrap_or_default()
            }
        }
    }

    pub fn invalidate_cache(&self) {
        *self.cache.lock().unwrap() = None;
    }
}

pub(crate) fn parse_streams(data: &Value) -> StreamMap {
    let mut streams = StreamMap::new();
    let Some(icestats) = data.as_object().map(|d| d.get("icestats")) else {
        tracing::warn!("Malformed wxradio.org response: missing icestats/source");
        return streams;
    };
    let sources = match icestats {
        None => return streams,
        Some(Value::Object(stats)) => stats.get("source"),
        Some(_) => {
            tracing::warn!("Malformed wxradio.org response: missing icestats/source");
            return streams;
        }
    };
    // Icecast returns a bare object when there is only one source.
    let sources = match sources {
        Some(Value::Array(list)) => list.iter().collect::<Vec<_>>(),
        Some(single @ Value::Object(_)) => vec![single],
        _ => return streams,
    };

    for source in sources.into_iter().filter_map(Value::as_object) {
        let mut mount = String::new();
        if let Some(listenurl) = source.get("listenurl").and_then(Value::as_str) {
            if let Some((_, last)) = listenurl.rsplit_once('/') {
                mount = format!("/{last}");
            }
        }
        if mount.is_empty() {
            match source.get("server_name") {
                None => mount = "/".into(),
                Some(Value::String(name)) => mount = format!("/{name}"),
                Some(_) => continue,
            }
        }
        let Some(call_sign) = extract_call_sign(&mount) else {
            continue;
        };
        let url = format!("https://wxradio.org/{}", mount.trim_start_matches('/'));
        let urls = streams.entry(call_sign).or_default();
        if !urls.contains(&url) {
            urls.push(url);
        }
    }
    streams
}

#[cfg(test)]
mod tests {
    use super::*;
    use aw_providers::http::FixtureClient;
    use serde_json::json;

    #[test]
    fn call_sign_extraction() {
        let cases = [
            ("/FL-Tallahassee-KIH24", Some("KIH24")),
            ("/NY-New-York-City-KWO35", Some("KWO35")),
            ("/MI-MountPleasant-KZZ33-alt2", Some("KZZ33")),
            ("/NE-Omaha-KIH61-A", Some("KIH61")),
            ("/AB-Calgary-XLF339", Some("XLF339")),
            ("/IL-Marion-WXM49-ALT1", Some("WXM49")),
            ("FL-Tallahassee-KIH24", Some("KIH24")),
            ("/FL-Tallahassee", None),
            ("", None),
            ("/FL-Tallahassee-nothing", None),
            ("/fl-tallahassee-kih24", Some("KIH24")),
        ];
        for (mount, expected) in cases {
            assert_eq!(extract_call_sign(mount).as_deref(), expected, "{mount}");
        }
    }

    #[test]
    fn parses_list_single_and_malformed() {
        let data = json!({"icestats": {"source": [
            {"listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24"},
            {"listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24"},
            {"listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24-alt1"},
            {"server_name": "GA-Atlanta-KEC80"},
            {"listenurl": 5, "server_name": 7},
            "junk"
        ]}});
        let streams = parse_streams(&data);
        assert_eq!(
            streams["KIH24"],
            [
                "https://wxradio.org/FL-Tallahassee-KIH24",
                "https://wxradio.org/FL-Tallahassee-KIH24-alt1"
            ]
        );
        assert_eq!(streams["KEC80"], ["https://wxradio.org/GA-Atlanta-KEC80"]);
        assert_eq!(streams.len(), 2);

        let single = json!({"icestats": {"source": {"listenurl": "http://x/OK-Tulsa-KIH27"}}});
        assert_eq!(
            parse_streams(&single)["KIH27"],
            ["https://wxradio.org/OK-Tulsa-KIH27"]
        );
        assert!(parse_streams(&json!({"icestats": {}})).is_empty());
        assert!(parse_streams(&json!("nope")).is_empty());
    }

    #[test]
    fn cache_and_stale_fallback() {
        let http = Arc::new(FixtureClient::new().with(
            WXRADIO_API_URL,
            json!({"icestats": {"source": {"listenurl": "http://x/OK-Tulsa-KIH27"}}}),
        ));
        let client = WxRadioClient::new(http.clone());
        assert_eq!(client.get_streams().len(), 1);
        assert_eq!(client.get_streams().len(), 1);
        assert_eq!(http.request_log().len(), 1);
        client.invalidate_cache();
        client.get_streams();
        assert_eq!(http.request_log().len(), 2);

        // Expired cache + failing fetch → stale data.
        let failing = Arc::new(FixtureClient::new());
        let client = WxRadioClient::with_options(failing, WXRADIO_API_URL, Duration::ZERO);
        assert!(client.get_streams().is_empty());
        *client.cache.lock().unwrap() = Some((
            StreamMap::from([("KIH27".into(), vec!["u".into()])]),
            Instant::now(),
        ));
        assert_eq!(client.get_streams()["KIH27"], ["u"]);
    }

    #[test]
    fn golden_status_parsing_and_mounts() {
        let golden = crate::golden("clients.json");
        for case in golden["wxradio"].as_array().unwrap() {
            let expected: StreamMap = serde_json::from_value(case["streams"].clone()).unwrap();
            assert_eq!(
                parse_streams(&case["payload"]),
                expected,
                "{}",
                case["payload"]
            );
        }
        for (mount, expected) in golden["mounts"].as_object().unwrap() {
            assert_eq!(
                extract_call_sign(mount).as_deref(),
                expected.as_str(),
                "{mount}"
            );
        }
    }
}
