//! Stream URL resolution: WeatherIndex, then wxradio.org, then the bundled
//! table, then (optionally) a Broadcastify fallback.
//!
//! Ports `noaa_radio/stream_url.py`.

use std::collections::HashMap;
use std::sync::Arc;

use crate::data::STREAM_URLS;
use crate::weatherindex::WeatherIndexClient;
use crate::wxradio::WxRadioClient;

const DEFAULT_PATTERN: &str = "https://broadcastify.cdnstream1.com/noaa/{call_sign}";

/// Something that can list stream URLs for a call sign. Implemented by
/// [`StreamUrlProvider`] and by closures (handy for tests).
pub trait StreamUrls: Send + Sync {
    fn get_stream_urls(&self, call_sign: &str) -> Vec<String>;
}

impl<F: Fn(&str) -> Vec<String> + Send + Sync> StreamUrls for F {
    fn get_stream_urls(&self, call_sign: &str) -> Vec<String> {
        self(call_sign)
    }
}

pub struct StreamUrlProvider {
    urls: HashMap<String, Vec<String>>,
    use_fallback: bool,
    wxradio: Option<Arc<WxRadioClient>>,
    weatherindex: Option<Arc<WeatherIndexClient>>,
}

impl Default for StreamUrlProvider {
    /// Python's `StreamURLProvider()`: bundled table plus the fallback pattern.
    fn default() -> Self {
        Self::new(HashMap::new(), true, None, None)
    }
}

impl StreamUrlProvider {
    /// `custom_urls` override or extend the bundled table (keys are
    /// upper-cased). The optional clients are consulted first, WeatherIndex
    /// before wxradio.org.
    pub fn new(
        custom_urls: HashMap<String, Vec<String>>,
        use_fallback: bool,
        wxradio: Option<Arc<WxRadioClient>>,
        weatherindex: Option<Arc<WeatherIndexClient>>,
    ) -> Self {
        let mut urls: HashMap<String, Vec<String>> = STREAM_URLS
            .iter()
            .map(|(cs, list)| (cs.to_string(), list.iter().map(|u| u.to_string()).collect()))
            .collect();
        for (call_sign, list) in custom_urls {
            urls.insert(call_sign.to_uppercase(), list);
        }
        Self {
            urls,
            use_fallback,
            wxradio,
            weatherindex,
        }
    }

    /// Primary stream URL, if any.
    pub fn get_stream_url(&self, call_sign: &str) -> Option<String> {
        self.get_stream_urls(call_sign).into_iter().next()
    }

    /// Whether the bundled (or custom) table knows this station.
    pub fn has_known_url(&self, call_sign: &str) -> bool {
        self.urls.contains_key(&call_sign.trim().to_uppercase())
    }

    /// Warm the wxradio.org cache (WeatherIndex is per call sign; see
    /// [`Self::prewarm_stations`]).
    pub fn prewarm_cache(&self) {
        if let Some(wxradio) = &self.wxradio {
            wxradio.get_streams();
        }
    }

    /// Resolve each station once so a later lookup hits warm caches.
    pub fn prewarm_stations<S: AsRef<str>>(&self, call_signs: &[S]) {
        for call_sign in call_signs {
            self.get_stream_urls(call_sign.as_ref());
        }
    }
}

impl StreamUrls for StreamUrlProvider {
    /// All stream URLs, primary first, without duplicates.
    fn get_stream_urls(&self, call_sign: &str) -> Vec<String> {
        let normalized = call_sign.trim().to_uppercase();
        if normalized.is_empty() {
            return Vec::new();
        }
        let weatherindex = self
            .weatherindex
            .as_ref()
            .map(|c| c.get_stream_urls(&normalized))
            .unwrap_or_default();
        let wxradio = self
            .wxradio
            .as_ref()
            .and_then(|c| c.get_streams().remove(&normalized))
            .unwrap_or_default();
        self.merge(&normalized, weatherindex, wxradio)
    }
}

impl StreamUrlProvider {
    /// WeatherIndex, then wxradio.org, then the bundled table, deduplicated;
    /// the fallback pattern only when all are empty.
    fn merge(
        &self,
        normalized: &str,
        weatherindex: Vec<String>,
        wxradio: Vec<String>,
    ) -> Vec<String> {
        let bundled = self.urls.get(normalized).cloned().unwrap_or_default();
        let mut merged: Vec<String> = Vec::new();
        for url in weatherindex.into_iter().chain(wxradio).chain(bundled) {
            if !merged.contains(&url) {
                merged.push(url);
            }
        }
        if merged.is_empty() && self.use_fallback {
            merged.push(DEFAULT_PATTERN.replace("{call_sign}", normalized));
        }
        merged
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use aw_providers::http::FixtureClient;
    use serde_json::json;

    #[test]
    fn bundled_urls_fallback_and_custom() {
        let provider = StreamUrlProvider::default();
        assert_eq!(
            provider.get_stream_url("kih24").as_deref(),
            Some("https://wxradio.org/FL-Tallahassee-KIH24")
        );
        assert_eq!(provider.get_stream_urls("KIH24").len(), 2);
        assert_eq!(
            provider.get_stream_urls("ZZZ99"),
            ["https://broadcastify.cdnstream1.com/noaa/ZZZ99"]
        );
        assert!(provider.get_stream_urls("  ").is_empty());
        assert!(provider.has_known_url(" kih24 ") && !provider.has_known_url("ZZZ99"));

        let no_fallback = StreamUrlProvider::new(HashMap::new(), false, None, None);
        assert!(no_fallback.get_stream_urls("ZZZ99").is_empty());

        let custom = StreamUrlProvider::new(
            HashMap::from([("kih24".into(), vec!["https://custom".into()])]),
            false,
            None,
            None,
        );
        assert_eq!(custom.get_stream_urls("KIH24"), ["https://custom"]);
    }

    #[test]
    fn weatherindex_then_wxradio_then_bundled_deduplicated() {
        let http = Arc::new(
            FixtureClient::new()
                .with(
                    "https://api.wxindex.org/v1/stations/KIH24",
                    json!({"feeds": [{"stream_url": "https://wi/1"},
                                     {"stream_url": "https://wxradio.org/FL-Tallahassee-KIH24"}]}),
                )
                .with(
                    crate::wxradio::WXRADIO_API_URL,
                    json!({"icestats": {"source": [
                        {"listenurl": "http://x/FL-Tallahassee-KIH24"},
                        {"listenurl": "http://x/FL-Tallahassee-KIH24-alt"}
                    ]}}),
                ),
        );
        let provider = StreamUrlProvider::new(
            HashMap::new(),
            true,
            Some(Arc::new(WxRadioClient::new(http.clone()))),
            Some(Arc::new(WeatherIndexClient::new(http))),
        );
        assert_eq!(
            provider.get_stream_urls("KIH24"),
            [
                "https://wi/1",
                "https://wxradio.org/FL-Tallahassee-KIH24",
                "https://wxradio.org/FL-Tallahassee-KIH24-alt",
                "http://wxradio.dyndns.org:8000/FL-Tallahassee-KIH24",
            ]
        );
    }

    #[test]
    fn golden_bundled_table_and_merge_order() {
        let stations = crate::golden("stations.json");
        let table = stations["stream_urls"].as_object().unwrap();
        assert_eq!(table.len(), STREAM_URLS.len());
        for ((cs, urls), (ecs, eurls)) in STREAM_URLS.iter().zip(table) {
            assert_eq!(cs, ecs);
            let eurls: Vec<String> = serde_json::from_value(eurls.clone()).unwrap();
            assert_eq!(urls.to_vec(), eurls);
        }

        let clients = crate::golden("clients.json");
        for case in clients["merge"].as_array().unwrap() {
            let provider = StreamUrlProvider::new(
                HashMap::new(),
                case["use_fallback"].as_bool().unwrap(),
                None,
                None,
            );
            let normalized = case["call_sign"].as_str().unwrap().trim().to_uppercase();
            let weatherindex: Vec<String> =
                serde_json::from_value(case["weatherindex"].clone()).unwrap();
            let wxradio: Vec<String> = case["wxradio"]
                .get(&normalized)
                .map(|v| serde_json::from_value(v.clone()).unwrap())
                .unwrap_or_default();
            let urls = if normalized.is_empty() {
                Vec::new()
            } else {
                provider.merge(&normalized, weatherindex, wxradio)
            };
            let expected: Vec<String> = serde_json::from_value(case["urls"].clone()).unwrap();
            assert_eq!(urls, expected, "{case}");
        }
    }
}
