//! Location search: the Open-Meteo geocoding client with its accent and
//! country fallbacks (`accessiweather.openmeteo_geocoding_client`), the
//! address/ZIP geocoding service (`accessiweather.geocoding`) and the
//! location manager used by the location dialogs
//! (`accessiweather.location_manager`).

pub mod legacy;
pub mod location_manager;

use std::cmp::Ordering;
use std::sync::LazyLock;

use aw_core::py::casefold;
use regex::Regex;
use serde_json::Value;

use crate::http::{build_url, HttpClient, HttpError};

// The legacy location dialog still uses these.
pub use legacy::{GeocodeResult, Geocoder, NOMINATIM, OPEN_METEO_GEOCODING};
pub use location_manager::LocationManager;

pub const BASE_URL: &str = "https://geocoding-api.open-meteo.com/v1";

#[derive(Debug, thiserror::Error)]
pub enum GeocodingError {
    #[error("{0}")]
    Api(String),
    #[error("{0}")]
    Network(String),
}

impl GeocodingError {
    fn from_http(e: HttpError) -> Self {
        match e {
            HttpError::Status { status: 400, .. } => {
                GeocodingError::Api("API error: Bad request".into())
            }
            HttpError::Status { status: 429, .. } => {
                GeocodingError::Api("Rate limit exceeded".into())
            }
            HttpError::Status { status, .. } if status >= 500 => {
                GeocodingError::Api(format!("Server error: {status}"))
            }
            HttpError::Transport { .. } if e.is_timeout() => {
                GeocodingError::Network(format!("Request timeout after 3 retries: {e}"))
            }
            HttpError::Transport { .. } => {
                GeocodingError::Network(format!("Network error after 3 retries: {e}"))
            }
            other => GeocodingError::Api(format!("Unexpected error: {other}")),
        }
    }
}

/// One Open-Meteo geocoding result.
#[derive(Debug, Clone, PartialEq)]
pub struct GeocodingResult {
    pub name: String,
    pub latitude: f64,
    pub longitude: f64,
    pub country: String,
    pub country_code: String,
    pub timezone: String,
    pub admin1: Option<String>,
    pub admin2: Option<String>,
    pub admin3: Option<String>,
    pub elevation: Option<f64>,
    pub population: Option<i64>,
}

impl GeocodingResult {
    /// "Name, Admin1, Country".
    pub fn display_name(&self) -> String {
        let mut parts = vec![self.name.as_str()];
        if let Some(admin1) = self.admin1.as_deref().filter(|a| !a.is_empty()) {
            parts.push(admin1);
        }
        parts.push(&self.country);
        parts.join(", ")
    }
}

const UNICODE_SUBSTITUTIONS: [(char, &[char]); 9] = [
    ('a', &['á', 'à', 'â', 'ã', 'ä', 'å']),
    ('c', &['ç']),
    ('e', &['é', 'è', 'ê', 'ë']),
    ('i', &['í', 'ì', 'î', 'ï']),
    ('n', &['ñ']),
    ('o', &['ó', 'ò', 'ô', 'õ', 'ö', 'ø']),
    ('s', &['ß']),
    ('u', &['ú', 'ù', 'û', 'ü']),
    ('y', &['ý', 'ÿ']),
];

fn country_hints(normalized_name: &str) -> &'static [&'static str] {
    match normalized_name {
        "alesund" | "tromso" => &["Norway"],
        "goteborg" | "malmo" => &["Sweden"],
        "munchen" => &["Germany"],
        "reykjavik" => &["Iceland"],
        "zurich" => &["Switzerland"],
        _ => &[],
    }
}

fn substitutions(c: char) -> &'static [char] {
    let folded = casefold(&c.to_string());
    UNICODE_SUBSTITUTIONS
        .iter()
        .find(|(base, _)| folded.chars().eq(std::iter::once(*base)))
        .map_or(&[], |(_, subs)| subs)
}

/// Accent-insensitive comparison text: transliterated, casefolded, only
/// `[a-z0-9]` words separated by single spaces.
pub fn normalize_text(text: &str) -> String {
    let ascii = casefold(&deunicode::deunicode(text));
    let words: Vec<String> = ascii
        .split(|c: char| !(c.is_ascii_lowercase() || c.is_ascii_digit()))
        .filter(|w| !w.is_empty())
        .map(str::to_string)
        .collect();
    words.join(" ")
}

pub struct OpenMeteoGeocodingClient<'a> {
    http: &'a dyn HttpClient,
    pub user_agent: String,
    pub base_url: String,
}

impl<'a> OpenMeteoGeocodingClient<'a> {
    pub fn new(http: &'a dyn HttpClient) -> Self {
        Self {
            http,
            user_agent: "AccessiWeather".into(),
            base_url: BASE_URL.into(),
        }
    }

    /// Search by name, retrying with simplified, accented and country-hinted
    /// queries when the literal query has no results.
    pub fn search(
        &self,
        name: &str,
        count: usize,
        language: &str,
    ) -> Result<Vec<GeocodingResult>, GeocodingError> {
        let search_name = name.trim();
        let params = [
            ("count", count.min(100).to_string()),
            ("language", language.to_string()),
            ("format", "json".to_string()),
        ];
        let direct = self.search_once(search_name, &params)?;
        if !direct.is_empty() {
            return Ok(direct);
        }
        for fallback_query in build_fallback_queries(search_name) {
            let results = self.search_once(&fallback_query, &params)?;
            let matched = filter_matching_results(search_name, results, Some(&fallback_query));
            if !matched.is_empty() {
                tracing::info!("Geocoding fallback matched '{search_name}' using retry query '{fallback_query}'");
                return Ok(matched);
            }
        }
        Ok(Vec::new())
    }

    fn search_once(
        &self,
        name: &str,
        base: &[(&'static str, String); 3],
    ) -> Result<Vec<GeocodingResult>, GeocodingError> {
        let mut params = base.to_vec();
        params.push(("name", name.to_string()));
        let url = build_url(&format!("{}/search", self.base_url), &params);
        let data = self
            .http
            .get_json_with_headers(&url, &[("User-Agent", &self.user_agent)])
            .map_err(GeocodingError::from_http)?;
        Ok(parse_results(&data))
    }
}

/// `_parse_results`: items missing name or coordinates are skipped.
pub fn parse_results(data: &Value) -> Vec<GeocodingResult> {
    let Some(items) = data.get("results").and_then(Value::as_array) else {
        return Vec::new();
    };
    let text = |item: &Value, key: &str| {
        item.get(key)
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string()
    };
    let opt = |item: &Value, key: &str| item.get(key).and_then(Value::as_str).map(str::to_string);
    items
        .iter()
        .filter_map(|item| {
            Some(GeocodingResult {
                name: item.get("name")?.as_str()?.to_string(),
                latitude: item.get("latitude")?.as_f64()?,
                longitude: item.get("longitude")?.as_f64()?,
                country: text(item, "country"),
                country_code: text(item, "country_code"),
                timezone: text(item, "timezone"),
                admin1: opt(item, "admin1"),
                admin2: opt(item, "admin2"),
                admin3: opt(item, "admin3"),
                elevation: item.get("elevation").and_then(Value::as_f64),
                population: item.get("population").and_then(Value::as_i64),
            })
        })
        .collect()
}

fn append_unique_query(queries: &mut Vec<String>, seen: &mut Vec<String>, query: String) {
    let normalized = casefold(&query);
    if !seen.contains(&normalized) {
        seen.push(normalized);
        queries.push(query);
    }
}

/// Retry queries for a search that found nothing.
pub fn build_fallback_queries(name: &str) -> Vec<String> {
    let mut queries = Vec::new();
    let mut seen = vec![casefold(name)];
    for simplified in build_simplified_location_queries(name) {
        append_unique_query(&mut queries, &mut seen, simplified);
    }
    for variant in generate_unicode_variants(name, 32) {
        append_unique_query(&mut queries, &mut seen, variant);
    }
    if name.split_whitespace().count() == 1 {
        for country in country_hints(&normalize_text(name)) {
            append_unique_query(&mut queries, &mut seen, format!("{name}, {country}"));
            for variant in generate_unicode_variants(name, 32) {
                append_unique_query(&mut queries, &mut seen, format!("{variant}, {country}"));
            }
        }
    }
    queries
}

fn build_simplified_location_queries(name: &str) -> Vec<String> {
    let parts: Vec<&str> = name
        .split(',')
        .map(str::trim)
        .filter(|p| !p.is_empty())
        .collect();
    if parts.len() < 2 || casefold(parts[0]) == casefold(name) {
        return Vec::new();
    }
    vec![parts[0].to_string()]
}

/// Likely accented spellings of an ASCII query (two substitution rounds).
pub fn generate_unicode_variants(name: &str, max_variants: usize) -> Vec<String> {
    let mut variants = Vec::new();
    let mut seen = vec![casefold(name)];
    let mut frontier = vec![name.to_string()];
    for _ in 0..2 {
        let mut next = Vec::new();
        for candidate in &frontier {
            let chars: Vec<char> = candidate.chars().collect();
            for (index, c) in chars.iter().enumerate() {
                for replacement in substitutions(*c) {
                    let mut variant_chars = chars.clone();
                    variant_chars[index] = *replacement;
                    let variant: String = variant_chars.into_iter().collect();
                    let normalized = casefold(&variant);
                    if seen.contains(&normalized) {
                        continue;
                    }
                    seen.push(normalized);
                    variants.push(variant.clone());
                    next.push(variant);
                    if variants.len() >= max_variants {
                        return variants;
                    }
                }
            }
        }
        if next.is_empty() {
            break;
        }
        frontier = next;
    }
    variants
}

fn result_matches_query(query: &str, result: &GeocodingResult) -> bool {
    let name = normalize_text(&result.name);
    let display = normalize_text(&result.display_name());
    name == query
        || display == query
        || name.starts_with(&format!("{query} "))
        || display.starts_with(&format!("{query} "))
        || format!(" {display} ").contains(&format!(" {query} "))
}

fn score_result_match(query: &str, result: &GeocodingResult) -> u8 {
    let name = normalize_text(&result.name);
    let display = normalize_text(&result.display_name());
    if name == query {
        0
    } else if display == query {
        1
    } else if name.starts_with(&format!("{query} ")) {
        2
    } else if display.starts_with(&format!("{query} ")) {
        3
    } else {
        4
    }
}

/// Keep fallback results that still match the user's original query, best
/// match first, then by population and display name.
pub fn filter_matching_results(
    original_query: &str,
    results: Vec<GeocodingResult>,
    fallback_query: Option<&str>,
) -> Vec<GeocodingResult> {
    let mut queries = vec![normalize_text(original_query)];
    if let Some(fallback) = fallback_query.map(normalize_text) {
        if !queries.contains(&fallback) {
            queries.push(fallback);
        }
    }
    let mut scored: Vec<(u8, GeocodingResult)> = results
        .into_iter()
        .filter_map(|r| {
            let best = queries
                .iter()
                .filter(|q| result_matches_query(q, &r))
                .map(|q| score_result_match(q, &r))
                .min()?;
            Some((best, r))
        })
        .collect();
    scored.sort_by(|(sa, a), (sb, b)| {
        sa.cmp(sb)
            .then_with(|| b.population.unwrap_or(0).cmp(&a.population.unwrap_or(0)))
            .then_with(|| casefold(&a.display_name()).cmp(&casefold(&b.display_name())))
            .then(Ordering::Equal)
    });
    scored.into_iter().map(|(_, r)| r).collect()
}

/// Address and ZIP geocoding (`GeocodingService`).
pub struct GeocodingService<'a> {
    pub client: OpenMeteoGeocodingClient<'a>,
    /// "nws" limits results to the United States.
    pub data_source: String,
}

const ALLOWED_COUNTRY_CODES: [&str; 1] = ["US"];

impl<'a> GeocodingService<'a> {
    pub fn new(http: &'a dyn HttpClient, user_agent: &str, data_source: &str) -> Self {
        let mut client = OpenMeteoGeocodingClient::new(http);
        client.user_agent = user_agent.to_string();
        Self {
            client,
            data_source: data_source.to_string(),
        }
    }

    /// 5-digit or ZIP+4 US ZIP code.
    pub fn is_zip_code(text: &str) -> bool {
        static ZIP: LazyLock<Regex> =
            LazyLock::new(|| Regex::new(r"^\d{5}(?:-\d{4})?\n?$").expect("valid ZIP regex"));
        ZIP.is_match(text)
    }

    /// "12345, USA" (ZIP+4 reduced to the 5-digit base).
    pub fn format_zip_code(zip_code: &str) -> String {
        let base = zip_code.split('-').next().unwrap_or(zip_code);
        format!("{base}, USA")
    }

    fn filter_results_by_country(&self, results: Vec<GeocodingResult>) -> Vec<GeocodingResult> {
        if self.data_source == "nws" {
            results
                .into_iter()
                .filter(|r| ALLOWED_COUNTRY_CODES.contains(&r.country_code.as_str()))
                .collect()
        } else {
            results
        }
    }

    /// `(latitude, longitude, display_name)` for the first allowed match.
    pub fn geocode_address(&self, address: &str) -> Option<(f64, f64, String)> {
        let original = address.trim();
        let query = if Self::is_zip_code(original) {
            Self::format_zip_code(original)
        } else {
            original.to_string()
        };
        let results = match self.client.search(&query, 5, "en") {
            Ok(r) => r,
            Err(e) => {
                tracing::error!("Geocoding error for '{original}': {e}");
                return None;
            }
        };
        if results.is_empty() {
            tracing::warn!("No results found for address: {original}");
            return None;
        }
        let first = self.filter_results_by_country(results).into_iter().next()?;
        Some((first.latitude, first.longitude, first.display_name()))
    }

    /// Range check, plus a US bounding-box check for the NWS data source.
    pub fn validate_coordinates(&self, lat: f64, lon: f64, us_only: Option<bool>) -> bool {
        let us_only = us_only.unwrap_or(self.data_source == "nws");
        if !(-90.0..=90.0).contains(&lat) || !(-180.0..=180.0).contains(&lon) {
            return false;
        }
        if !us_only {
            return true;
        }
        const US_BOUNDS: [(f64, f64, f64, f64); 6] = [
            (24.0, 50.0, -125.0, -66.0),
            (51.0, 72.0, -180.0, -130.0),
            (51.0, 55.0, 172.0, 180.0),
            (18.0, 23.0, -161.0, -154.0),
            (17.0, 19.0, -68.0, -64.0),
            (13.0, 14.0, 144.0, 146.0),
        ];
        US_BOUNDS
            .iter()
            .any(|(min_lat, max_lat, min_lon, max_lon)| {
                (*min_lat..=*max_lat).contains(&lat) && (*min_lon..=*max_lon).contains(&lon)
            })
    }

    /// Display names for partial input (at least two characters).
    pub fn suggest_locations(&self, query: &str, limit: usize) -> Vec<String> {
        let query = query.trim();
        if query.chars().count() < 2 {
            return Vec::new();
        }
        let query = if Self::is_zip_code(query) {
            Self::format_zip_code(query)
        } else {
            query.to_string()
        };
        match self.client.search(&query, limit * 2, "en") {
            Ok(results) => self
                .filter_results_by_country(results)
                .into_iter()
                .take(limit)
                .map(|r| r.display_name())
                .collect(),
            Err(e) => {
                tracing::error!("Location suggestion error for '{query}': {e}");
                Vec::new()
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    fn result(name: &str, country: &str, code: &str, population: Option<i64>) -> Value {
        json!({"name": name, "latitude": 1.0, "longitude": 2.0, "country": country,
            "country_code": code, "timezone": "UTC", "population": population})
    }

    #[test]
    fn zip_codes() {
        assert!(GeocodingService::is_zip_code("12345"));
        assert!(GeocodingService::is_zip_code("12345-6789"));
        for bad in ["1234", "123456", "12345-678", "abcde", "12345-abcd"] {
            assert!(!GeocodingService::is_zip_code(bad));
        }
        assert_eq!(
            GeocodingService::format_zip_code("12345-6789"),
            "12345, USA"
        );
    }

    #[test]
    fn coordinate_validation() {
        let http = FixtureClient::new();
        let s = GeocodingService::new(&http, "AccessiWeather", "nws");
        assert!(s.validate_coordinates(40.0, -75.0, None));
        assert!(!s.validate_coordinates(51.5, -0.1, None));
        assert!(s.validate_coordinates(51.5, -0.1, Some(false)));
        assert!(s.validate_coordinates(61.2, -149.9, None));
        assert!(s.validate_coordinates(21.3, -157.8, None));
        assert!(!s.validate_coordinates(91.0, 0.0, Some(false)));
    }

    #[test]
    fn unicode_variants_and_fallback_queries() {
        let variants = generate_unicode_variants("Zurich", 32);
        assert!(variants.contains(&"Zürich".to_string()));
        assert!(variants.len() <= 32);
        let queries = build_fallback_queries("Tromso");
        assert!(queries.contains(&"Tromso, Norway".to_string()));
        assert!(queries.contains(&"Tromsø".to_string()));
        assert_eq!(build_fallback_queries("Paris, France")[0], "Paris");
        assert_eq!(normalize_text("  Zürich,  CH "), "zurich ch");
    }

    #[test]
    fn nws_source_filters_to_us_and_retries_accents() {
        let http = FixtureClient::new()
            .with(
                &format!("{BASE_URL}/search?count=5&language=en&format=json&name=London"),
                json!({"results": [result("London", "United Kingdom", "GB", Some(8_000_000))]}),
            )
            .with(
                &format!("{BASE_URL}/search?count=5&language=en&format=json&name=Zurich"),
                json!({}),
            )
            .with(
                &format!("{BASE_URL}/search?count=5&language=en&format=json&name=Z%C3%BArich"),
                json!({}),
            )
            .with(
                &format!("{BASE_URL}/search?count=5&language=en&format=json&name=Z%C3%B9rich"),
                json!({}),
            )
            .with(
                &format!("{BASE_URL}/search?count=5&language=en&format=json&name=Z%C3%BBrich"),
                json!({}),
            )
            .with(
                &format!("{BASE_URL}/search?count=5&language=en&format=json&name=Z%C3%BCrich"),
                json!({"results": [result("Zürich", "Switzerland", "CH", Some(400_000))]}),
            )
            .with(
                &format!("{BASE_URL}/search?count=5&language=en&format=json&name=Z"),
                json!({}),
            );
        let nws = GeocodingService::new(&http, "AccessiWeather", "nws");
        assert_eq!(nws.geocode_address("London"), None);
        let auto = GeocodingService::new(&http, "AccessiWeather", "auto");
        assert_eq!(
            auto.geocode_address("London"),
            Some((1.0, 2.0, "London, United Kingdom".into()))
        );
        assert_eq!(
            auto.geocode_address("Zurich").map(|r| r.2),
            Some("Zürich, Switzerland".into())
        );
    }
}
