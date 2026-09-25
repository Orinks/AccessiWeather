//! Location search via the Open-Meteo geocoding API, with a Nominatim
//! fallback for street addresses / postcodes it does not know.

use aw_core::Location;
use serde_json::Value;

use crate::http::{HttpClient, HttpError};

pub const OPEN_METEO_GEOCODING: &str = "https://geocoding-api.open-meteo.com/v1";
pub const NOMINATIM: &str = "https://nominatim.openstreetmap.org";

#[derive(Debug, Clone, PartialEq)]
pub struct GeocodeResult {
    pub display_name: String,
    pub location: Location,
}

pub struct Geocoder<'a> {
    http: &'a dyn HttpClient,
    pub open_meteo_base: String,
    pub nominatim_base: String,
}

fn encode(s: &str) -> String {
    url::form_urlencoded::byte_serialize(s.as_bytes()).collect()
}

impl<'a> Geocoder<'a> {
    pub fn new(http: &'a dyn HttpClient) -> Self {
        Self {
            http,
            open_meteo_base: OPEN_METEO_GEOCODING.into(),
            nominatim_base: NOMINATIM.into(),
        }
    }

    pub fn search(&self, query: &str, limit: usize) -> Result<Vec<GeocodeResult>, HttpError> {
        let q = query.trim();
        if q.is_empty() {
            return Ok(Vec::new());
        }
        if let Some((lat, lon)) = parse_coordinates(q) {
            return Ok(vec![GeocodeResult {
                display_name: format!("{lat:.4}, {lon:.4}"),
                location: Location::new(format!("{lat:.4}, {lon:.4}"), lat, lon),
            }]);
        }
        let results = self.search_open_meteo(q, limit)?;
        if !results.is_empty() {
            return Ok(results);
        }
        // Open-Meteo only knows place names; fall back to Nominatim for
        // addresses and postcodes.
        self.search_nominatim(q, limit)
    }

    fn search_open_meteo(&self, q: &str, limit: usize) -> Result<Vec<GeocodeResult>, HttpError> {
        let url = format!(
            "{}/search?name={}&count={}&language=en&format=json",
            self.open_meteo_base,
            encode(q),
            limit.max(1)
        );
        let v = self.http.get_json(&url)?;
        let Some(items) = v.get("results").and_then(Value::as_array) else {
            return Ok(Vec::new());
        };
        Ok(items
            .iter()
            .filter_map(|r| {
                let name = r.get("name")?.as_str()?;
                let lat = r.get("latitude")?.as_f64()?;
                let lon = r.get("longitude")?.as_f64()?;
                let mut parts = vec![name.to_string()];
                for key in ["admin1", "country"] {
                    if let Some(s) = r.get(key).and_then(Value::as_str) {
                        if !s.is_empty() && !parts.contains(&s.to_string()) {
                            parts.push(s.to_string());
                        }
                    }
                }
                let display = parts.join(", ");
                let mut loc = Location::new(display.clone(), lat, lon);
                loc.country_code = r
                    .get("country_code")
                    .and_then(Value::as_str)
                    .map(|c| c.to_uppercase());
                loc.timezone = r.get("timezone").and_then(Value::as_str).map(String::from);
                Some(GeocodeResult {
                    display_name: display,
                    location: loc,
                })
            })
            .collect())
    }

    fn search_nominatim(&self, q: &str, limit: usize) -> Result<Vec<GeocodeResult>, HttpError> {
        let url = format!(
            "{}/search?q={}&format=jsonv2&addressdetails=1&limit={}",
            self.nominatim_base,
            encode(q),
            limit.max(1)
        );
        let v = self.http.get_json(&url)?;
        let Some(items) = v.as_array() else {
            return Ok(Vec::new());
        };
        Ok(items
            .iter()
            .filter_map(|r| {
                let display = r.get("display_name")?.as_str()?.to_string();
                let lat = r.get("lat")?.as_str()?.parse().ok()?;
                let lon = r.get("lon")?.as_str()?.parse().ok()?;
                let mut loc = Location::new(display.clone(), lat, lon);
                loc.country_code = r
                    .get("address")
                    .and_then(|a| a.get("country_code"))
                    .and_then(Value::as_str)
                    .map(|c| c.to_uppercase());
                Some(GeocodeResult {
                    display_name: display,
                    location: loc,
                })
            })
            .collect())
    }
}

/// Accept "40.1, -75.2" style input directly.
pub fn parse_coordinates(text: &str) -> Option<(f64, f64)> {
    let mut parts = text.split([',', ' ']).filter(|s| !s.is_empty());
    let lat: f64 = parts.next()?.parse().ok()?;
    let lon: f64 = parts.next()?.parse().ok()?;
    if parts.next().is_some() || !(-90.0..=90.0).contains(&lat) || !(-180.0..=180.0).contains(&lon)
    {
        return None;
    }
    Some((lat, lon))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    #[test]
    fn coordinates_bypass_network() {
        let http = FixtureClient::new();
        let g = Geocoder::new(&http);
        let r = g.search("40.1, -75.2", 5).unwrap();
        assert_eq!(r.len(), 1);
        assert!(http.request_log().is_empty());
    }

    #[test]
    fn open_meteo_results_build_display_names() {
        let http = FixtureClient::new().with(
            OPEN_METEO_GEOCODING,
            json!({"results": [{"name": "Philadelphia", "latitude": 39.95, "longitude": -75.16,
                "admin1": "Pennsylvania", "country": "United States", "country_code": "us",
                "timezone": "America/New_York"}]}),
        );
        let r = Geocoder::new(&http).search("Philadelphia", 5).unwrap();
        assert_eq!(
            r[0].display_name,
            "Philadelphia, Pennsylvania, United States"
        );
        assert_eq!(r[0].location.country_code.as_deref(), Some("US"));
        assert!(aw_core::location::is_us_location(&r[0].location));
    }

    #[test]
    fn falls_back_to_nominatim() {
        let http = FixtureClient::new()
            .with(OPEN_METEO_GEOCODING, json!({}))
            .with(
                NOMINATIM,
                json!([{"display_name": "10 Downing St, London", "lat": "51.5034", "lon": "-0.1276",
                    "address": {"country_code": "gb"}}]),
            );
        let r = Geocoder::new(&http).search("10 Downing Street", 5).unwrap();
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].location.country_code.as_deref(), Some("GB"));
        assert_eq!(http.request_log().len(), 2);
    }
}
