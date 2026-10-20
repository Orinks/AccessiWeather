//! Observed pollutant concentrations from the nearest OpenAQ station
//! (API v3, <https://docs.openaq.org>). Rust-only: the Python app has no
//! OpenAQ support.
//!
//! Two requests per lookup: the stations within [`SEARCH_RADIUS_M`] of the
//! location, then the latest values of the nearest one with recent data.
//! The key travels in the `X-API-Key` header and is never logged.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use aw_core::model::{Location, Timestamp};
use aw_core::py;
use chrono::DateTime;
use serde_json::Value;

use super::airnow::error_kind;
use crate::http::{build_url, HttpClient, HttpError};

pub const LOCATIONS_ENDPOINT: &str = "https://api.openaq.org/v3/locations";
/// The API's maximum search radius, in metres.
pub const SEARCH_RADIUS_M: u32 = 25_000;
/// Stations and values older than this are ignored.
pub const MAX_AGE: Duration = Duration::from_secs(3 * 60 * 60);
/// Answers (including "nothing nearby") are reused for this long.
pub const DEFAULT_CACHE_TTL: Duration = Duration::from_secs(30 * 60);
/// At most this many stations are asked for their latest values.
const MAX_LATEST_REQUESTS: usize = 3;
const SEARCH_LIMIT: u32 = 20;

/// One pollutant value from a station.
#[derive(Debug, Clone, PartialEq)]
pub struct OpenAqReading {
    /// `pm2_5`, `pm10`, `o3`, `no2`, `so2` or `co`.
    pub code: &'static str,
    pub value: f64,
    /// As OpenAQ reports it: "µg/m³", "ppm" or "ppb".
    pub unit: Option<String>,
    pub time: Timestamp,
}

/// The nearest station with recent readings.
#[derive(Debug, Clone, PartialEq)]
pub struct OpenAqStation {
    pub id: i64,
    pub name: String,
    pub locality: Option<String>,
    pub distance_km: Option<f64>,
    /// A reference-grade monitor rather than a low-cost sensor.
    pub is_monitor: bool,
    /// The network that runs the station ("AirNow", "EEA", ...).
    pub provider_name: Option<String>,
    /// One reading per pollutant, in display order.
    pub readings: Vec<OpenAqReading>,
}

impl OpenAqStation {
    /// "Del Norte, Albuquerque", or the name alone.
    pub fn display_name(&self) -> String {
        match self.locality.as_deref() {
            Some(locality) if !self.name.contains(locality) => {
                format!("{}, {locality}", self.name)
            }
            _ => self.name.clone(),
        }
    }
}

/// Reading code for an OpenAQ parameter name; other parameters (pm1, bc,
/// temperature, ...) are not shown.
pub fn pollutant_code(parameter: &str) -> Option<&'static str> {
    Some(match parameter.trim().to_lowercase().as_str() {
        "pm25" | "pm2.5" | "pm2_5" => "pm2_5",
        "pm10" => "pm10",
        "o3" => "o3",
        "no2" => "no2",
        "so2" => "so2",
        "co" => "co",
        _ => return None,
    })
}

const DISPLAY_ORDER: [&str; 6] = ["pm2_5", "pm10", "o3", "no2", "so2", "co"];

/// A station from the search, before its latest values are read.
struct Candidate {
    id: i64,
    name: String,
    locality: Option<String>,
    distance_km: Option<f64>,
    is_monitor: bool,
    provider_name: Option<String>,
    /// Sensor id to (reading code, unit).
    sensors: HashMap<i64, (&'static str, Option<String>)>,
}

fn text(value: Option<&Value>) -> Option<String> {
    value
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

fn as_id(value: Option<&Value>) -> Option<i64> {
    value?.as_i64()
}

/// An OpenAQ `{"utc": ..., "local": ...}` time, keeping the local offset.
fn parse_time(value: Option<&Value>) -> Option<Timestamp> {
    let value = value?;
    ["local", "utc"].iter().find_map(|key| {
        value
            .get(key)
            .and_then(Value::as_str)
            .and_then(|s| DateTime::parse_from_rfc3339(s.trim()).ok())
    })
}

fn is_recent(time: Timestamp, now: Timestamp) -> bool {
    let age = now.signed_duration_since(time);
    age <= chrono::Duration::from_std(MAX_AGE).unwrap_or_default()
        // Allow for clock skew, not for times far in the future.
        && age >= -chrono::Duration::hours(1)
}

/// Great-circle distance in km.
fn haversine_km(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let (phi1, phi2) = (lat1.to_radians(), lat2.to_radians());
    let d_phi = (lat2 - lat1).to_radians();
    let d_lambda = (lon2 - lon1).to_radians();
    let a = (d_phi / 2.0).sin().powi(2) + phi1.cos() * phi2.cos() * (d_lambda / 2.0).sin().powi(2);
    6371.0088 * 2.0 * a.sqrt().atan2((1.0 - a).sqrt())
}

/// Stations from a `/locations` search worth asking for values: fixed,
/// reporting within [`MAX_AGE`], with a sensor for a shown pollutant.
/// Nearest first.
fn candidates(payload: &Value, location: &Location, now: Timestamp) -> Vec<Candidate> {
    let Some(results) = payload.get("results").and_then(Value::as_array) else {
        return Vec::new();
    };
    let mut found: Vec<Candidate> = Vec::new();
    for item in results.iter().filter(|r| r.is_object()) {
        let Some(id) = as_id(item.get("id")) else {
            continue;
        };
        if item.get("isMobile").and_then(Value::as_bool) == Some(true) {
            continue;
        }
        if !parse_time(item.get("datetimeLast")).is_some_and(|t| is_recent(t, now)) {
            continue;
        }
        let sensors: HashMap<i64, (&'static str, Option<String>)> = item
            .get("sensors")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(|sensor| {
                let parameter = sensor.get("parameter")?;
                let code = pollutant_code(parameter.get("name")?.as_str()?)?;
                Some((
                    as_id(sensor.get("id"))?,
                    (code, text(parameter.get("units"))),
                ))
            })
            .collect();
        if sensors.is_empty() {
            continue;
        }
        let distance_km = py::number(item.get("distance"))
            .filter(|d| d.is_finite() && *d >= 0.0)
            .map(|metres| metres / 1000.0)
            .or_else(|| {
                let coordinates = item.get("coordinates")?;
                let lat = py::number(coordinates.get("latitude"))?;
                let lon = py::number(coordinates.get("longitude"))?;
                Some(haversine_km(
                    location.latitude,
                    location.longitude,
                    lat,
                    lon,
                ))
            });
        if distance_km.is_some_and(|d| d > f64::from(SEARCH_RADIUS_M) / 1000.0 + 0.5) {
            continue;
        }
        found.push(Candidate {
            id,
            name: text(item.get("name")).unwrap_or_else(|| format!("Station {id}")),
            locality: text(item.get("locality")),
            distance_km,
            is_monitor: item.get("isMonitor").and_then(Value::as_bool) == Some(true),
            provider_name: item.get("provider").and_then(|p| text(p.get("name"))),
            sensors,
        });
    }
    found.sort_by(|a, b| {
        a.distance_km
            .unwrap_or(f64::INFINITY)
            .total_cmp(&b.distance_km.unwrap_or(f64::INFINITY))
    });
    found
}

/// The candidate's recent, valid values, one per pollutant (the newest
/// when two sensors measure the same one).
fn readings(candidate: &Candidate, payload: &Value, now: Timestamp) -> Vec<OpenAqReading> {
    let mut by_code: HashMap<&'static str, OpenAqReading> = HashMap::new();
    let results = payload.get("results").and_then(Value::as_array);
    for item in results.into_iter().flatten() {
        let Some((code, unit)) =
            as_id(item.get("sensorsId")).and_then(|id| candidate.sensors.get(&id))
        else {
            continue;
        };
        let Some(value) = item
            .get("value")
            .filter(|v| v.is_number())
            .and_then(Value::as_f64)
            .filter(|v| v.is_finite() && *v >= 0.0)
        else {
            continue;
        };
        let Some(time) = parse_time(item.get("datetime")).filter(|t| is_recent(*t, now)) else {
            continue;
        };
        let reading = OpenAqReading {
            code,
            value,
            unit: unit.clone(),
            time,
        };
        match by_code.get(code) {
            Some(existing) if existing.time >= time => {}
            _ => {
                by_code.insert(code, reading);
            }
        }
    }
    DISPLAY_ORDER
        .iter()
        .filter_map(|code| by_code.remove(code))
        .collect()
}

pub struct OpenAqClient {
    http: Arc<dyn HttpClient>,
    api_key: String,
    pub user_agent: String,
    ttl: Duration,
    cache: Mutex<HashMap<String, (Instant, Option<OpenAqStation>)>>,
}

impl OpenAqClient {
    pub fn new(http: Arc<dyn HttpClient>, api_key: &str, user_agent: &str) -> Self {
        Self {
            http,
            api_key: api_key.to_string(),
            user_agent: user_agent.to_string(),
            ttl: DEFAULT_CACHE_TTL,
            cache: Mutex::new(HashMap::new()),
        }
    }

    pub fn api_key(&self) -> &str {
        self.api_key.trim()
    }

    fn get(&self, url: &str) -> Result<Value, HttpError> {
        self.http.get_json_with_headers(
            url,
            &[
                ("User-Agent", &self.user_agent),
                ("X-API-Key", self.api_key()),
            ],
        )
    }

    fn search_url(latitude: f64, longitude: f64) -> String {
        build_url(
            LOCATIONS_ENDPOINT,
            &[
                ("coordinates", format!("{latitude:.4},{longitude:.4}")),
                ("radius", SEARCH_RADIUS_M.to_string()),
                ("limit", SEARCH_LIMIT.to_string()),
            ],
        )
    }

    /// The nearest station within 25 km with readings from the last three
    /// hours. `Ok(None)` when there is none (or no key, or the coordinates
    /// are invalid); `Err` when OpenAQ could not be asked.
    pub fn fetch_nearest(
        &self,
        location: &Location,
        now: Timestamp,
    ) -> Result<Option<OpenAqStation>, HttpError> {
        let (lat, lon) = (location.latitude, location.longitude);
        if !lat.is_finite()
            || !lon.is_finite()
            || !(-90.0..=90.0).contains(&lat)
            || !(-180.0..=180.0).contains(&lon)
            || self.api_key().is_empty()
        {
            return Ok(None);
        }
        let key = format!("{lat:.4},{lon:.4}");
        if let Some((stored, cached)) = self.cache.lock().unwrap().get(&key) {
            if stored.elapsed() <= self.ttl {
                return Ok(cached.clone());
            }
        }
        let payload = self.get(&Self::search_url(lat, lon))?;
        let mut last_error = None;
        let mut station = None;
        for candidate in candidates(&payload, location, now)
            .into_iter()
            .take(MAX_LATEST_REQUESTS)
        {
            let url = format!("{LOCATIONS_ENDPOINT}/{}/latest", candidate.id);
            let latest = match self.get(&url) {
                Ok(latest) => latest,
                Err(e) => {
                    tracing::debug!("OpenAQ latest values failed ({})", error_kind(&e));
                    last_error = Some(e);
                    continue;
                }
            };
            let values = readings(&candidate, &latest, now);
            if values.is_empty() {
                continue;
            }
            station = Some(OpenAqStation {
                id: candidate.id,
                name: candidate.name,
                locality: candidate.locality,
                distance_km: candidate.distance_km,
                is_monitor: candidate.is_monitor,
                provider_name: candidate.provider_name,
                readings: values,
            });
            break;
        }
        if station.is_none() {
            if let Some(e) = last_error {
                return Err(e);
            }
        }
        self.cache
            .lock()
            .unwrap()
            .insert(key, (Instant::now(), station.clone()));
        Ok(station)
    }

    /// Check the key against the live API: `(true, None)` or `(false, reason)`.
    pub fn validate_api_key(&self) -> (bool, Option<String>) {
        if self.api_key().is_empty() {
            return (false, Some("No API key provided".into()));
        }
        let url = build_url(LOCATIONS_ENDPOINT, &[("limit", "1".into())]);
        match self.get(&url) {
            Ok(Value::Object(o)) if o.contains_key("results") => (true, None),
            Ok(_) | Err(HttpError::Json { .. }) => {
                (false, Some("Unexpected response from OpenAQ".into()))
            }
            Err(e) => match e.status() {
                Some(401 | 403) => (false, Some("Invalid API key".into())),
                Some(429) => (
                    false,
                    Some("Rate limit exceeded, but key appears valid".into()),
                ),
                Some(status) => (false, Some(format!("OpenAQ returned HTTP {status}"))),
                None => (
                    false,
                    Some(format!("Could not reach OpenAQ ({})", error_kind(&e))),
                ),
            },
        }
    }

    pub fn clear_cache(&self) {
        self.cache.lock().unwrap().clear();
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    pub(crate) fn now() -> Timestamp {
        DateTime::parse_from_rfc3339("2025-06-01T14:20:00+00:00").unwrap()
    }

    /// A `/locations` result shaped like the v3 API's.
    pub(crate) fn station(
        id: i64,
        name: &str,
        distance: f64,
        last_utc: &str,
        sensors: &[(i64, &str, &str)],
    ) -> Value {
        json!({
            "id": id, "name": name, "locality": "Albuquerque", "timezone": "America/Denver",
            "country": {"id": 155, "code": "US", "name": "United States"},
            "owner": {"id": 4, "name": "Unknown Governmental Organization"},
            "provider": {"id": 119, "name": "AirNow"},
            "isMobile": false, "isMonitor": true,
            "instruments": [{"id": 2, "name": "Government Monitor"}],
            "sensors": sensors.iter().map(|(sid, param, units)| json!({
                "id": sid, "name": format!("{param} {units}"),
                "parameter": {"id": 2, "name": param, "units": units, "displayName": param}
            })).collect::<Vec<_>>(),
            "coordinates": {"latitude": 35.1353, "longitude": -106.5847},
            "licenses": null,
            "bounds": [-106.5847, 35.1353, -106.5847, 35.1353],
            "distance": distance,
            "datetimeFirst": {"utc": "2016-03-06T19:00:00Z", "local": "2016-03-06T12:00:00-07:00"},
            "datetimeLast": {"utc": last_utc, "local": last_utc},
        })
    }

    pub(crate) fn search(results: Vec<Value>) -> Value {
        json!({"meta": {"name": "openaq-api", "website": "/", "page": 1, "limit": 20,
            "found": results.len()}, "results": results})
    }

    /// A `/latest` result.
    pub(crate) fn latest(location_id: i64, values: &[(i64, f64, &str)]) -> Value {
        json!({"meta": {"name": "openaq-api", "website": "/", "page": 1, "limit": 100,
            "found": values.len()},
            "results": values.iter().map(|(sensor, value, utc)| json!({
                "datetime": {"utc": utc, "local": utc},
                "value": value,
                "coordinates": {"latitude": 35.1353, "longitude": -106.5847},
                "sensorsId": sensor, "locationsId": location_id,
            })).collect::<Vec<_>>()})
    }

    fn albuquerque() -> Location {
        Location::new("Albuquerque", 35.1, -106.6).with_country("US")
    }

    fn del_norte() -> Value {
        station(
            2178,
            "Del Norte",
            1834.2,
            "2025-06-01T13:00:00Z",
            &[
                (3917, "o3", "ppm"),
                (3920, "pm25", "µg/m³"),
                (3921, "temperature", "c"),
                (3922, "pm1", "µg/m³"),
            ],
        )
    }

    fn client(http: FixtureClient) -> (Arc<FixtureClient>, OpenAqClient) {
        let http = Arc::new(http);
        (
            http.clone(),
            OpenAqClient::new(http, " secret ", "AccessiWeather/2.0"),
        )
    }

    #[test]
    fn picks_the_nearest_recent_station_and_joins_sensors() {
        let far = station(
            9,
            "Far",
            9000.0,
            "2025-06-01T13:00:00Z",
            &[(1, "pm25", "µg/m³")],
        );
        let (http, c) = client(
            FixtureClient::new()
                .with(LOCATIONS_ENDPOINT, search(vec![far, del_norte()]))
                .with(
                    &format!("{LOCATIONS_ENDPOINT}/2178/latest"),
                    latest(
                        2178,
                        &[
                            (3917, 0.031, "2025-06-01T13:00:00Z"),
                            (3920, 8.4, "2025-06-01T13:00:00Z"),
                            (3921, 25.0, "2025-06-01T13:00:00Z"),
                            (3922, 3.0, "2025-06-01T13:00:00Z"),
                        ],
                    ),
                ),
        );
        let found = c.fetch_nearest(&albuquerque(), now()).unwrap().unwrap();
        assert_eq!(found.id, 2178);
        assert_eq!(found.display_name(), "Del Norte, Albuquerque");
        assert_eq!(found.distance_km, Some(1.8342));
        assert!(found.is_monitor);
        assert_eq!(found.provider_name.as_deref(), Some("AirNow"));
        let values: Vec<(&str, f64, Option<&str>)> = found
            .readings
            .iter()
            .map(|r| (r.code, r.value, r.unit.as_deref()))
            .collect();
        assert_eq!(
            values,
            [("pm2_5", 8.4, Some("µg/m³")), ("o3", 0.031, Some("ppm"))]
        );
        assert_eq!(
            http.request_log(),
            [
                format!(
                    "{LOCATIONS_ENDPOINT}?coordinates=35.1000%2C-106.6000&radius=25000&limit=20"
                ),
                format!("{LOCATIONS_ENDPOINT}/2178/latest"),
            ]
        );
        for headers in http.header_log() {
            assert!(headers.contains(&("X-API-Key".into(), "secret".into())));
            assert!(headers.contains(&("User-Agent".into(), "AccessiWeather/2.0".into())));
        }
        // Cached: no second search.
        c.fetch_nearest(&albuquerque(), now()).unwrap();
        assert_eq!(http.request_log().len(), 2);
    }

    #[test]
    fn skips_stale_mobile_and_empty_stations() {
        let stale = station(
            1,
            "Stale",
            100.0,
            "2025-05-30T13:00:00Z",
            &[(11, "pm25", "µg/m³")],
        );
        let mut mobile = station(
            2,
            "Mobile",
            200.0,
            "2025-06-01T14:00:00Z",
            &[(21, "pm25", "µg/m³")],
        );
        mobile["isMobile"] = json!(true);
        let weather_only = station(
            3,
            "Weather",
            300.0,
            "2025-06-01T14:00:00Z",
            &[(31, "temperature", "c")],
        );
        let (http, c) = client(
            FixtureClient::new()
                .with(
                    LOCATIONS_ENDPOINT,
                    search(vec![stale, mobile, weather_only, del_norte()]),
                )
                .with(
                    &format!("{LOCATIONS_ENDPOINT}/2178/latest"),
                    latest(2178, &[(3920, 8.4, "2025-06-01T13:00:00Z")]),
                ),
        );
        let found = c.fetch_nearest(&albuquerque(), now()).unwrap().unwrap();
        assert_eq!(found.id, 2178);
        assert_eq!(http.request_log().len(), 2);
    }

    #[test]
    fn falls_back_to_the_next_station_when_values_are_stale() {
        let near = station(
            1,
            "Near",
            500.0,
            "2025-06-01T13:00:00Z",
            &[(11, "no2", "µg/m³")],
        );
        let (http, c) = client(
            FixtureClient::new()
                .with(LOCATIONS_ENDPOINT, search(vec![near, del_norte()]))
                .with(
                    &format!("{LOCATIONS_ENDPOINT}/1/latest"),
                    // Stale, negative and unknown-sensor values are dropped.
                    latest(
                        1,
                        &[
                            (11, 20.0, "2025-06-01T09:00:00Z"),
                            (11, -1.0, "2025-06-01T14:00:00Z"),
                            (99, 5.0, "2025-06-01T14:00:00Z"),
                        ],
                    ),
                )
                .with(
                    &format!("{LOCATIONS_ENDPOINT}/2178/latest"),
                    latest(2178, &[(3917, 0.04, "2025-06-01T14:00:00Z")]),
                ),
        );
        let found = c.fetch_nearest(&albuquerque(), now()).unwrap().unwrap();
        assert_eq!(found.name, "Del Norte");
        assert_eq!(found.readings[0].code, "o3");
        assert_eq!(http.request_log().len(), 3);
    }

    #[test]
    fn latest_requests_are_capped() {
        let stations = (1..=5)
            .map(|id| {
                station(
                    id,
                    "S",
                    id as f64 * 100.0,
                    "2025-06-01T14:00:00Z",
                    &[(id * 10, "pm25", "µg/m³")],
                )
            })
            .collect();
        let (http, c) = client(
            FixtureClient::new()
                .with(LOCATIONS_ENDPOINT, search(stations))
                .with(&format!("{LOCATIONS_ENDPOINT}/"), latest(0, &[])),
        );
        assert!(matches!(c.fetch_nearest(&albuquerque(), now()), Ok(None)));
        assert_eq!(http.request_log().len(), 1 + MAX_LATEST_REQUESTS);
    }

    #[test]
    fn distance_falls_back_to_coordinates() {
        let mut no_distance = del_norte();
        no_distance.as_object_mut().unwrap().remove("distance");
        let found = candidates(&search(vec![no_distance]), &albuquerque(), now());
        let km = found[0].distance_km.unwrap();
        assert!((km - 4.2).abs() < 0.3, "{km}");
    }

    #[test]
    fn errors_empty_results_and_missing_key() {
        let (_, c) = client(FixtureClient::new().with_status(LOCATIONS_ENDPOINT, 401));
        assert!(c.fetch_nearest(&albuquerque(), now()).is_err());

        let (http, c) = client(FixtureClient::new().with(LOCATIONS_ENDPOINT, search(vec![])));
        assert!(matches!(c.fetch_nearest(&albuquerque(), now()), Ok(None)));
        // "Nothing nearby" is cached too.
        assert!(matches!(c.fetch_nearest(&albuquerque(), now()), Ok(None)));
        assert_eq!(http.request_log().len(), 1);

        let http = Arc::new(FixtureClient::new());
        let c = OpenAqClient::new(http.clone(), "  ", "UA");
        assert!(matches!(c.fetch_nearest(&albuquerque(), now()), Ok(None)));
        let c = OpenAqClient::new(http.clone(), "k", "UA");
        assert!(matches!(
            c.fetch_nearest(&Location::new("x", 95.0, 0.0), now()),
            Ok(None)
        ));
        assert!(http.request_log().is_empty());
    }

    #[test]
    fn failed_latest_requests_are_errors_and_not_cached() {
        let (http, c) = client(
            FixtureClient::new()
                .with(LOCATIONS_ENDPOINT, search(vec![del_norte()]))
                .with_status(&format!("{LOCATIONS_ENDPOINT}/2178/latest"), 500),
        );
        assert!(c.fetch_nearest(&albuquerque(), now()).is_err());
        assert!(c.fetch_nearest(&albuquerque(), now()).is_err());
        assert_eq!(http.request_log().len(), 4);
    }

    #[test]
    fn validation_messages() {
        let check = |http: FixtureClient| client(http).1.validate_api_key();
        assert_eq!(
            check(FixtureClient::new().with(LOCATIONS_ENDPOINT, search(vec![]))),
            (true, None)
        );
        for (status, message) in [
            (401, "Invalid API key"),
            (403, "Invalid API key"),
            (429, "Rate limit exceeded, but key appears valid"),
            (500, "OpenAQ returned HTTP 500"),
        ] {
            assert_eq!(
                check(FixtureClient::new().with_status(LOCATIONS_ENDPOINT, status))
                    .1
                    .as_deref(),
                Some(message)
            );
        }
        assert_eq!(
            check(FixtureClient::new().with_transport_error(LOCATIONS_ENDPOINT, "dns"))
                .1
                .as_deref(),
            Some("Could not reach OpenAQ (ConnectError)")
        );
        assert_eq!(
            check(FixtureClient::new().with(LOCATIONS_ENDPOINT, json!([])))
                .1
                .as_deref(),
            Some("Unexpected response from OpenAQ")
        );
        let (http, c) = client(FixtureClient::new().with(LOCATIONS_ENDPOINT, search(vec![])));
        c.validate_api_key();
        assert_eq!(
            http.request_log(),
            [format!("{LOCATIONS_ENDPOINT}?limit=1")]
        );
        assert_eq!(
            OpenAqClient::new(Arc::new(FixtureClient::new()), "", "UA").validate_api_key(),
            (false, Some("No API key provided".into()))
        );
    }

    #[test]
    fn parameter_codes() {
        assert_eq!(pollutant_code("pm25"), Some("pm2_5"));
        assert_eq!(pollutant_code("O3"), Some("o3"));
        assert_eq!(pollutant_code("pm1"), None);
        assert_eq!(pollutant_code("relativehumidity"), None);
    }
}
