//! Location search and reverse geocoding for the location dialogs, ported
//! from `accessiweather.location_manager.LocationManager`.
//!
//! Street addresses go to the US Census geocoder first, everything else to
//! Open-Meteo (with the accent/country fallbacks of
//! [`super::OpenMeteoGeocodingClient`]). Reverse geocoding asks the NWS
//! `/points` endpoint, then OpenStreetMap Nominatim.

use std::sync::LazyLock;

use aw_core::model::Location;
use aw_core::py::{self, casefold};
use regex::Regex;
use serde_json::Value;

use super::OpenMeteoGeocodingClient;
use crate::http::{build_url, HttpClient, HttpError};

pub const GEOCODING_BASE_URL: &str = "https://geocoding-api.open-meteo.com/v1";
pub const CENSUS_GEOCODING_BASE_URL: &str = "https://geocoding.geo.census.gov/geocoder";
pub const NOMINATIM_BASE_URL: &str = "https://nominatim.openstreetmap.org";
pub const NWS_POINTS_BASE_URL: &str = "https://api.weather.gov/points";
const REVERSE_USER_AGENT: &str = "AccessiWeather/1.0 (AccessiWeather)";

static STREET_ADDRESS_PATTERN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(?i)\b\d+\b.*\b(aly|alley|ave|avenue|blvd|boulevard|cir|circle|ct|court|dr|drive|hwy|highway|ln|lane|pkwy|parkway|pl|place|rd|road|sq|square|st|street|ter|terrace|trail|trl|way)\b",
    )
    .expect("valid street address regex")
});
static STARTS_WITH_NUMBER_PATTERN: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\s*\d+\b").expect("valid number regex"));

pub struct LocationManager<'a> {
    http: &'a dyn HttpClient,
    pub geocoding_base_url: String,
    pub census_geocoding_base_url: String,
    pub nominatim_base_url: String,
    pub nws_points_base_url: String,
}

/// Python's search wraps every failure: retryable ones propagate (after its
/// retry decorator), everything else becomes an empty result.
fn swallow(e: HttpError) -> Result<Vec<Location>, HttpError> {
    tracing::error!("Failed to search locations: {e}");
    if e.is_retryable() {
        Err(e)
    } else {
        Ok(Vec::new())
    }
}

/// `str(value or "").strip()`.
fn text_or_empty(value: Option<&Value>) -> String {
    match value {
        Some(v) if py::truthy(Some(v)) => py::value_str(v).trim().to_string(),
        _ => String::new(),
    }
}

impl<'a> LocationManager<'a> {
    pub fn new(http: &'a dyn HttpClient) -> Self {
        Self {
            http,
            geocoding_base_url: GEOCODING_BASE_URL.into(),
            census_geocoding_base_url: CENSUS_GEOCODING_BASE_URL.into(),
            nominatim_base_url: NOMINATIM_BASE_URL.into(),
            nws_points_base_url: NWS_POINTS_BASE_URL.into(),
        }
    }

    /// Search by name, ZIP or US street address (queries under two
    /// characters return nothing).
    pub fn search_locations(&self, query: &str, limit: usize) -> Result<Vec<Location>, HttpError> {
        let query = query.trim();
        if query.chars().count() < 2 {
            tracing::info!("Query too short for geocoding");
            return Ok(Vec::new());
        }
        if Self::looks_like_street_address(query) {
            match self.search_us_street_address(query, limit) {
                Ok(found) if !found.is_empty() => return Ok(found),
                Ok(_) => {}
                Err(e) => return swallow(e),
            }
        }

        let url = build_url(
            &format!("{}/search", self.geocoding_base_url),
            &[
                ("name", query.to_string()),
                ("count", limit.min(100).to_string()),
                ("language", "en".into()),
                ("format", "json".into()),
            ],
        );
        let data = match self.http.get_json(&url) {
            Ok(d) => d,
            Err(e) => return swallow(e),
        };
        let mut results: Vec<Value> = data
            .get("results")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        if results.is_empty() {
            return self.unicode_fallback(query, limit);
        }

        let population = |item: &Value| {
            let p = item.get("population");
            if py::truthy(p) {
                py::as_float(p).unwrap_or(0.0)
            } else {
                0.0
            }
        };
        results.sort_by(|a, b| population(b).total_cmp(&population(a)));

        let mut unique: Vec<Location> = Vec::new();
        for item in &results {
            let location = parse_geocoding_result(item);
            let key = location.name.to_lowercase();
            if !unique.iter().any(|l| l.name.to_lowercase() == key) {
                unique.push(location);
            }
            if unique.len() >= limit {
                break;
            }
        }
        Ok(unique)
    }

    /// Accent/country retries; their errors are not retryable in Python, so
    /// any failure is an empty result.
    fn unicode_fallback(&self, query: &str, limit: usize) -> Result<Vec<Location>, HttpError> {
        let client = OpenMeteoGeocodingClient::new(self.http);
        match client.search(query, limit, "en") {
            Ok(results) => Ok(results
                .into_iter()
                .take(limit)
                .map(|r| {
                    let name = if r.display_name().is_empty() {
                        r.name.clone()
                    } else {
                        r.display_name()
                    };
                    let mut location = Location::new(name, r.latitude, r.longitude);
                    // Python keeps "" rather than None for a missing code here.
                    location.country_code = Some(r.country_code.to_uppercase());
                    location
                })
                .collect()),
            Err(e) => {
                tracing::error!("Failed to search locations: {e}");
                Ok(Vec::new())
            }
        }
    }

    /// Whether a query has enough street-address shape for the Census geocoder.
    pub fn looks_like_street_address(query: &str) -> bool {
        STREET_ADDRESS_PATTERN.is_match(query)
            || (STARTS_WITH_NUMBER_PATTERN.is_match(query) && query.contains(','))
    }

    fn search_us_street_address(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<Location>, HttpError> {
        let url = build_url(
            &format!(
                "{}/locations/onelineaddress",
                self.census_geocoding_base_url
            ),
            &[
                ("address", query.to_string()),
                ("benchmark", "Public_AR_Current".into()),
                ("format", "json".into()),
            ],
        );
        let data = self.http.get_json(&url)?;
        let matches = data
            .get("result")
            .and_then(|r| r.get("addressMatches"))
            .and_then(Value::as_array)
            .map_or(&[][..], Vec::as_slice);
        let mut locations = Vec::new();
        let mut seen: Vec<String> = Vec::new();
        for m in matches {
            let Some(location) = parse_census_address_match(m) else {
                continue;
            };
            let key = format!(
                "{}:{:.6}:{:.6}",
                casefold(&location.name),
                location.latitude,
                location.longitude
            );
            if seen.contains(&key) {
                continue;
            }
            seen.push(key);
            locations.push(location);
            if locations.len() >= limit {
                break;
            }
        }
        Ok(locations)
    }

    /// A friendly label for coordinates (NWS first, then Nominatim); `None`
    /// when neither source can name the point.
    pub fn reverse_geocode_coordinates(&self, latitude: f64, longitude: f64) -> Option<Location> {
        self.reverse_geocode_with_nws(latitude, longitude)
            .or_else(|| self.reverse_geocode_with_nominatim(latitude, longitude))
    }

    fn reverse_geocode_with_nws(&self, latitude: f64, longitude: f64) -> Option<Location> {
        let url = format!(
            "{}/{},{}",
            self.nws_points_base_url,
            py::float_repr(latitude),
            py::float_repr(longitude)
        );
        let data = match self.http.get_json_with_headers(
            &url,
            &[
                ("User-Agent", REVERSE_USER_AGENT),
                ("Accept", "application/geo+json"),
            ],
        ) {
            Ok(d) => d,
            Err(e) => {
                tracing::debug!("Reverse geocoding failed for ({latitude}, {longitude}): {e}");
                return None;
            }
        };
        let properties = data.as_object()?.get("properties").unwrap_or(&Value::Null);
        let relative_properties = properties
            .get("relativeLocation")
            .filter(|r| r.is_object())
            .and_then(|r| r.get("properties"));
        let city = text_or_empty(relative_properties.and_then(|p| p.get("city")));
        let state = text_or_empty(relative_properties.and_then(|p| p.get("state")));
        if city.is_empty() {
            return None;
        }
        let name = if state.is_empty() {
            city
        } else {
            format!("{city}, {state}")
        };
        let mut location = Location::new(name, latitude, longitude);
        location.timezone = properties
            .get("timeZone")
            .filter(|v| py::truthy(Some(v)))
            .map(py::value_str);
        location.country_code = Some("US".into());
        Some(location)
    }

    fn reverse_geocode_with_nominatim(&self, latitude: f64, longitude: f64) -> Option<Location> {
        let url = build_url(
            &format!("{}/reverse", self.nominatim_base_url),
            &[
                ("format", "jsonv2".into()),
                ("lat", py::float_repr(latitude)),
                ("lon", py::float_repr(longitude)),
                ("zoom", "10".into()),
                ("addressdetails", "1".into()),
                ("accept-language", "en".into()),
            ],
        );
        let data = match self.http.get_json_with_headers(
            &url,
            &[
                ("User-Agent", REVERSE_USER_AGENT),
                ("Accept", "application/json"),
            ],
        ) {
            Ok(d) => d,
            Err(e) => {
                tracing::debug!(
                    "Nominatim reverse geocoding failed for ({latitude}, {longitude}): {e}"
                );
                return None;
            }
        };
        if !data.is_object() {
            return None;
        }
        let name = format_nominatim_location_name(&data)?;
        let mut location = Location::new(name, latitude, longitude);
        if let Some(address) = data.get("address").filter(|a| a.is_object()) {
            let code = text_or_empty(address.get("country_code")).to_uppercase();
            location.country_code = (!code.is_empty()).then_some(code);
        }
        Some(location)
    }

    pub fn validate_coordinates(latitude: f64, longitude: f64) -> bool {
        (-90.0..=90.0).contains(&latitude) && (-180.0..=180.0).contains(&longitude)
    }

    /// Haversine distance in miles (Earth radius 3959 mi).
    pub fn calculate_distance(loc1: &Location, loc2: &Location) -> f64 {
        let (lat1, lon1) = (loc1.latitude.to_radians(), loc1.longitude.to_radians());
        let (lat2, lon2) = (loc2.latitude.to_radians(), loc2.longitude.to_radians());
        let a = ((lat2 - lat1) / 2.0).sin().powi(2)
            + lat1.cos() * lat2.cos() * ((lon2 - lon1) / 2.0).sin().powi(2);
        3959.0 * 2.0 * a.sqrt().asin()
    }

    /// "40.7128°N, 74.0060°W".
    pub fn format_coordinates(latitude: f64, longitude: f64, precision: usize) -> String {
        let lat_dir = if latitude >= 0.0 { "N" } else { "S" };
        let lon_dir = if longitude >= 0.0 { "E" } else { "W" };
        format!(
            "{:.precision$}°{lat_dir}, {:.precision$}°{lon_dir}",
            latitude.abs(),
            longitude.abs()
        )
    }
}

/// Editable label from a Nominatim reverse response: locality, region and
/// country without case-insensitive repeats, else `display_name`.
pub fn format_nominatim_location_name(data: &Value) -> Option<String> {
    let display_name = || Some(text_or_empty(data.get("display_name"))).filter(|s| !s.is_empty());
    let Some(address) = data.get("address").filter(|a| a.is_object()) else {
        return display_name();
    };
    let first = |keys: &[&str]| {
        keys.iter()
            .map(|k| text_or_empty(address.get(*k)))
            .find(|v| !v.is_empty())
    };
    let locality = first(&[
        "city",
        "town",
        "village",
        "municipality",
        "hamlet",
        "suburb",
        "county",
    ]);
    let region = first(&["state", "province", "region", "state_district"]);
    let country = Some(text_or_empty(address.get("country"))).filter(|s| !s.is_empty());
    let mut parts: Vec<String> = Vec::new();
    for value in [locality, region, country].into_iter().flatten() {
        if !parts.iter().any(|p| casefold(p) == casefold(&value)) {
            parts.push(value);
        }
    }
    if parts.is_empty() {
        display_name()
    } else {
        Some(parts.join(", "))
    }
}

/// A Census geocoder address match as a US location.
pub fn parse_census_address_match(data: &Value) -> Option<Location> {
    let coordinates = data.get("coordinates")?;
    let latitude = py::as_float(coordinates.get("y"))?;
    let longitude = py::as_float(coordinates.get("x"))?;
    let matched = text_or_empty(data.get("matchedAddress"));
    if matched.is_empty() {
        return None;
    }
    let mut location = Location::new(matched, latitude, longitude);
    location.country_code = Some("US".into());
    Some(location)
}

/// An Open-Meteo geocoding item as a location; the country is omitted for
/// the United States.
pub fn parse_geocoding_result(data: &Value) -> Location {
    let text = |key: &str| {
        data.get(key)
            .filter(|v| py::truthy(Some(v)))
            .map(py::value_str)
            .unwrap_or_default()
    };
    let (name, admin1, country, country_code) = (
        text("name"),
        text("admin1"),
        text("country"),
        text("country_code"),
    );
    let mut parts = Vec::new();
    if !name.is_empty() {
        parts.push(name.clone());
    }
    if !admin1.is_empty() && admin1 != name {
        parts.push(admin1);
    }
    if !country.is_empty() && country != "United States" && country != "United States of America" {
        parts.push(country);
    }
    let display = if parts.is_empty() {
        "Unknown Location".to_string()
    } else {
        parts.join(", ")
    };
    let mut location = Location::new(
        display,
        py::as_float(data.get("latitude")).unwrap_or(0.0),
        py::as_float(data.get("longitude")).unwrap_or(0.0),
    );
    location.country_code = (!country_code.is_empty()).then(|| country_code.to_uppercase());
    location
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    #[test]
    fn street_address_detection() {
        assert!(LocationManager::looks_like_street_address(
            "1600 Pennsylvania Ave NW, Washington"
        ));
        assert!(LocationManager::looks_like_street_address("10 Main Street"));
        assert!(LocationManager::looks_like_street_address(
            "221 Baker, London"
        ));
        assert!(!LocationManager::looks_like_street_address("New York, NY"));
        assert!(!LocationManager::looks_like_street_address("10001"));
    }

    #[test]
    fn census_first_then_openmeteo() {
        let census = json!({"result": {"addressMatches": [
            {"matchedAddress": "1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500",
             "coordinates": {"x": -77.0365, "y": 38.8977}},
            {"matchedAddress": "1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500",
             "coordinates": {"x": -77.0365, "y": 38.8977}},
            {"matchedAddress": "", "coordinates": {"x": 1, "y": 2}}]}});
        let http = FixtureClient::new().with(CENSUS_GEOCODING_BASE_URL, census);
        let found = LocationManager::new(&http)
            .search_locations("1600 Pennsylvania Ave NW, Washington, DC", 5)
            .unwrap();
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].country_code.as_deref(), Some("US"));
        assert_eq!(
            http.request_log()[0],
            "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address=1600%20Pennsylvania%20Ave%20NW%2C%20Washington%2C%20DC&benchmark=Public_AR_Current&format=json"
        );
    }

    #[test]
    fn openmeteo_results_are_sorted_and_deduped() {
        let http = FixtureClient::new().with(
            GEOCODING_BASE_URL,
            json!({"results": [
                {"name": "Springfield", "admin1": "Ohio", "country": "United States",
                 "country_code": "us", "latitude": 39.9, "longitude": -83.8, "population": 58000},
                {"name": "Springfield", "admin1": "Illinois", "country": "United States",
                 "country_code": "us", "latitude": 39.8, "longitude": -89.6, "population": 114000},
                {"name": "Springfield", "admin1": "Illinois", "country": "United States",
                 "country_code": "us", "latitude": 39.7, "longitude": -89.6, "population": null}]}),
        );
        let found = LocationManager::new(&http)
            .search_locations("Springfield", 5)
            .unwrap();
        let names: Vec<&str> = found.iter().map(|l| l.name.as_str()).collect();
        assert_eq!(names, ["Springfield, Illinois", "Springfield, Ohio"]);
        assert!(LocationManager::new(&http)
            .search_locations("S", 5)
            .unwrap()
            .is_empty());
    }

    #[test]
    fn reverse_geocoding_prefers_nws_then_nominatim() {
        let http = FixtureClient::new().with(
            NWS_POINTS_BASE_URL,
            json!({"properties": {"timeZone": "America/New_York",
                "relativeLocation": {"properties": {"city": "Philadelphia", "state": "PA"}}}}),
        );
        let loc = LocationManager::new(&http)
            .reverse_geocode_coordinates(39.95, -75.16)
            .unwrap();
        assert_eq!(loc.name, "Philadelphia, PA");
        assert_eq!(loc.timezone.as_deref(), Some("America/New_York"));
        assert_eq!(
            http.request_log(),
            vec!["https://api.weather.gov/points/39.95,-75.16"]
        );

        let http = FixtureClient::new()
            .with_status(NWS_POINTS_BASE_URL, 404)
            .with(
                NOMINATIM_BASE_URL,
                json!({"address": {"city": "Paris", "state": "Île-de-France",
                "country": "France", "country_code": "fr"}}),
            );
        let loc = LocationManager::new(&http)
            .reverse_geocode_coordinates(48.85, 2.35)
            .unwrap();
        assert_eq!(loc.name, "Paris, Île-de-France, France");
        assert_eq!(loc.country_code.as_deref(), Some("FR"));
        assert_eq!(
            http.request_log()[1],
            "https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=48.85&lon=2.35&zoom=10&addressdetails=1&accept-language=en"
        );
    }

    #[test]
    fn nominatim_name_falls_back_to_display_name() {
        assert_eq!(
            format_nominatim_location_name(&json!({"display_name": " Somewhere ", "address": {}}))
                .as_deref(),
            Some("Somewhere")
        );
        assert_eq!(
            format_nominatim_location_name(
                &json!({"address": {"county": "Monaco", "country": "monaco"}})
            )
            .as_deref(),
            Some("Monaco")
        );
        assert_eq!(format_nominatim_location_name(&json!({})), None);
    }

    #[test]
    fn coordinates_formatting_and_distance() {
        assert_eq!(
            LocationManager::format_coordinates(40.7128, -74.006, 4),
            "40.7128°N, 74.0060°W"
        );
        let a = Location::new("a", 40.7128, -74.006);
        let b = Location::new("b", 34.0522, -118.2437);
        assert!((LocationManager::calculate_distance(&a, &b) - 2445.0).abs() < 5.0);
        assert!(!LocationManager::validate_coordinates(91.0, 0.0));
    }
}
