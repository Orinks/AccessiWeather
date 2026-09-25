//! Current U.S. AQI observations from EPA AirNow, ported from
//! `accessiweather.services.airnow_client`.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use aw_core::model::{Location, Timestamp};
use aw_core::py;
use chrono::{FixedOffset, Local, NaiveDate, TimeZone};
use chrono_tz::Tz;
use serde_json::Value;

use crate::http::{build_url, HttpClient, HttpError};

pub const ENDPOINT: &str = "https://www.airnowapi.org/aq/observation/current/ziplatlong/";
pub const DEFAULT_CACHE_TTL: Duration = Duration::from_secs(60 * 60);
/// Washington, DC: reliably inside AirNow coverage for key validation.
pub const VALIDATION_COORDINATES: (f64, f64) = (38.8977, -77.0365);

/// Highest current pollutant AQI returned for a location.
#[derive(Debug, Clone, PartialEq)]
pub struct AirNowObservation {
    pub aqi: i64,
    pub category: String,
    pub pollutant: String,
    pub observed_at: Option<Timestamp>,
    pub reporting_area: Option<String>,
}

pub struct AirNowClient {
    http: Arc<dyn HttpClient>,
    api_key: String,
    pub user_agent: String,
    pub distance: i64,
    ttl: Duration,
    /// `None` caches "a successful response without a usable observation".
    cache: Mutex<HashMap<String, (Instant, Option<AirNowObservation>)>>,
}

fn timezone_offset_hours(name: &str) -> Option<i32> {
    Some(match name {
        "UTC" | "GMT" => 0,
        "AST" => -4,
        "ADT" => -3,
        "EST" => -5,
        "EDT" => -4,
        "CST" => -6,
        "CDT" => -5,
        "MST" => -7,
        "MDT" => -6,
        "PST" => -8,
        "PDT" => -7,
        "AKST" => -9,
        "AKDT" => -8,
        "HST" | "HAST" => -10,
        "HADT" => -9,
        "SST" => -11,
        "CHST" => 10,
        _ => return None,
    })
}

/// AQI category by EPA breakpoints.
pub fn air_quality_category(value: f64) -> &'static str {
    if value <= 50.0 {
        "Good"
    } else if value <= 100.0 {
        "Moderate"
    } else if value <= 150.0 {
        "Unhealthy for Sensitive Groups"
    } else if value <= 200.0 {
        "Unhealthy"
    } else if value <= 300.0 {
        "Very Unhealthy"
    } else {
        "Hazardous"
    }
}

/// First present field among the documented (PascalCase) and live
/// (camelCase) spellings.
fn field<'a>(item: &'a serde_json::Map<String, Value>, names: &[&str]) -> Option<&'a Value> {
    names.iter().find_map(|n| item.get(*n))
}

fn coerce_aqi(value: Option<&Value>) -> Option<i64> {
    let value = value?;
    if value.is_boolean() {
        return None;
    }
    let numeric = py::as_float(Some(value))?;
    (numeric.is_finite() && numeric >= 0.0).then(|| py::round(numeric) as i64)
}

fn coerce_hour(value: Option<&Value>) -> Option<u32> {
    let hour: i64 = match value? {
        Value::Number(n) => n.as_i64().or_else(|| n.as_f64().map(|f| f.trunc() as i64))?,
        Value::String(s) => s.trim().split(':').next()?.trim().parse().ok()?,
        _ => return None,
    };
    (0..=23).contains(&hour).then_some(hour as u32)
}

fn category_name(value: Option<&Value>) -> Option<String> {
    let value = match value? {
        Value::Object(o) => o.get("Name")?,
        v => v,
    };
    value
        .as_str()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

fn parse_date(text: &str) -> Option<NaiveDate> {
    let text = text.trim();
    NaiveDate::parse_from_str(text, "%Y-%m-%d")
        .or_else(|_| NaiveDate::parse_from_str(text, "%m/%d/%Y"))
        .ok()
}

fn parse_observed_at(item: &serde_json::Map<String, Value>) -> Option<Timestamp> {
    let date = parse_date(field(item, &["DateObserved", "dateObserved"])?.as_str()?)?;
    let hour = coerce_hour(field(item, &["HourObserved", "hourObserved"]))?;
    let naive = date.and_hms_opt(hour, 0, 0)?;
    let zone = field(item, &["LocalTimeZone", "localTimeZone"])
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty());
    match zone {
        Some(name) => {
            if let Some(hours) = timezone_offset_hours(&name.to_uppercase()) {
                return FixedOffset::east_opt(hours * 3600)?.from_local_datetime(&naive).single();
            }
            match name.parse::<Tz>() {
                Ok(tz) => tz.from_local_datetime(&naive).earliest().map(|t| t.fixed_offset()),
                // Python keeps a naive local time here.
                Err(_) => Local.from_local_datetime(&naive).earliest().map(|t| t.fixed_offset()),
            }
        }
        None => Local.from_local_datetime(&naive).earliest().map(|t| t.fixed_offset()),
    }
}

/// `_parse_observations`: the highest valid AQI in a list response.
pub fn parse_observations(payload: &Value) -> Option<AirNowObservation> {
    let mut selected = None;
    let mut selected_aqi = -1;
    for item in payload.as_array()?.iter().filter_map(Value::as_object) {
        let Some(aqi) = coerce_aqi(field(item, &["AQI", "nowcastAQI"])) else {
            continue;
        };
        if aqi <= selected_aqi {
            continue;
        }
        selected = Some(item);
        selected_aqi = aqi;
    }
    let item = selected?;
    let text = |names: &[&str]| {
        field(item, names)
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string)
    };
    Some(AirNowObservation {
        aqi: selected_aqi,
        category: category_name(field(item, &["Category", "aqiCategoryName"]))
            .unwrap_or_else(|| air_quality_category(selected_aqi as f64).to_string()),
        pollutant: text(&["ParameterName", "parameterName"]).unwrap_or_else(|| "Unknown".into()),
        observed_at: parse_observed_at(item),
        reporting_area: text(&["ReportingArea", "reportingAreaName"]),
    })
}

/// Coordinate validation error (Python raises `ValueError`).
#[derive(Debug, Clone, PartialEq, thiserror::Error)]
#[error("{0}")]
pub struct InvalidCoordinates(pub String);

impl AirNowClient {
    pub fn new(http: Arc<dyn HttpClient>, api_key: &str, user_agent: &str) -> Self {
        Self {
            http,
            api_key: api_key.to_string(),
            user_agent: user_agent.to_string(),
            distance: 25,
            ttl: DEFAULT_CACHE_TTL,
            cache: Mutex::new(HashMap::new()),
        }
    }

    pub fn api_key(&self) -> &str {
        self.api_key.trim()
    }

    fn url(&self, latitude: f64, longitude: f64) -> String {
        build_url(
            ENDPOINT,
            &[
                ("format", "application/json".into()),
                ("latitude", py::float_repr(latitude)),
                ("longitude", py::float_repr(longitude)),
                ("distance", self.distance.to_string()),
                ("API_KEY", self.api_key().to_string()),
            ],
        )
    }

    fn validated_coordinates(location: &Location) -> Result<(f64, f64), InvalidCoordinates> {
        let (lat, lon) = (location.latitude, location.longitude);
        if !lat.is_finite() {
            return Err(InvalidCoordinates("latitude must be finite".into()));
        }
        if !lon.is_finite() {
            return Err(InvalidCoordinates("longitude must be finite".into()));
        }
        if !(-90.0..=90.0).contains(&lat) {
            return Err(InvalidCoordinates("latitude must be between -90 and 90".into()));
        }
        if !(-180.0..=180.0).contains(&lon) {
            return Err(InvalidCoordinates("longitude must be between -180 and 180".into()));
        }
        Ok((lat, lon))
    }

    fn cache_key(&self, latitude: f64, longitude: f64) -> String {
        format!("{latitude:.4},{longitude:.4},{}", self.distance)
    }

    /// Highest valid current pollutant AQI near `location`, cached per
    /// location for an hour (including "no observation" answers).
    pub fn fetch_current_air_quality(
        &self,
        location: &Location,
    ) -> Result<Option<AirNowObservation>, InvalidCoordinates> {
        let (lat, lon) = Self::validated_coordinates(location)?;
        let key = self.cache_key(lat, lon);
        if let Some((stored, cached)) = self.cache.lock().unwrap().get(&key) {
            if stored.elapsed() <= self.ttl {
                return Ok(cached.clone());
            }
        }
        if self.api_key().is_empty() {
            return Ok(None);
        }
        let payload = match self
            .http
            .get_json_with_headers(&self.url(lat, lon), &[("User-Agent", &self.user_agent)])
        {
            Ok(p) => p,
            Err(e) => {
                // Never log the error text: the URL carries the API key.
                tracing::warn!("AirNow current AQI request failed ({})", error_kind(&e));
                return Ok(None);
            }
        };
        let observation = parse_observations(&payload);
        if observation.is_some() || payload.is_array() {
            self.cache
                .lock()
                .unwrap()
                .insert(key, (Instant::now(), observation.clone()));
        }
        Ok(observation)
    }

    /// Check the key against the live API: `(true, None)` or `(false, reason)`.
    pub fn validate_api_key(&self) -> (bool, Option<String>) {
        if self.api_key().is_empty() {
            return (false, Some("No API key provided".into()));
        }
        let (lat, lon) = VALIDATION_COORDINATES;
        match self
            .http
            .get_json_with_headers(&self.url(lat, lon), &[("User-Agent", &self.user_agent)])
        {
            Ok(Value::Array(_)) => (true, None),
            Ok(Value::Object(o)) if o.contains_key("WebServiceError") => {
                (false, Some("Invalid API key".into()))
            }
            Ok(_) | Err(HttpError::Json { .. }) => {
                (false, Some("Unexpected response from AirNow".into()))
            }
            Err(e) => match e.status() {
                Some(401 | 403) => (false, Some("Invalid API key".into())),
                Some(429) => (false, Some("Rate limit exceeded — but key appears valid".into())),
                Some(status) => (false, Some(format!("AirNow returned HTTP {status}"))),
                None => (false, Some(format!("Could not reach AirNow ({})", error_kind(&e)))),
            },
        }
    }

    pub fn clear_cache(&self) {
        self.cache.lock().unwrap().clear();
    }
}

/// An httpx-style exception name for log and validation messages.
fn error_kind(e: &HttpError) -> &'static str {
    match e {
        HttpError::Status { .. } => "HTTPStatusError",
        HttpError::Json { .. } => "JSONDecodeError",
        _ if e.is_timeout() => "ReadTimeout",
        _ => "ConnectError",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    fn client(http: FixtureClient) -> (Arc<FixtureClient>, AirNowClient) {
        let http = Arc::new(http);
        (http.clone(), AirNowClient::new(http, " key ", "AccessiWeather/2.0"))
    }

    #[test]
    fn selects_highest_aqi_and_builds_url() {
        let (http, c) = client(FixtureClient::new().with(
            ENDPOINT,
            json!([
                {"AQI": 42, "ParameterName": "O3", "Category": {"Name": "Good"},
                 "DateObserved": "2025-06-01 ", "HourObserved": 14, "LocalTimeZone": "EST",
                 "ReportingArea": "Metro"},
                {"AQI": 61, "ParameterName": "PM2.5", "Category": {"Name": "Moderate"},
                 "DateObserved": "2025-06-01", "HourObserved": 14, "LocalTimeZone": "EDT",
                 "ReportingArea": " Metro "}
            ]),
        ));
        let obs = c
            .fetch_current_air_quality(&Location::new("x", 40.0, -75.0))
            .unwrap()
            .unwrap();
        assert_eq!(obs.aqi, 61);
        assert_eq!(obs.pollutant, "PM2.5");
        assert_eq!(obs.reporting_area.as_deref(), Some("Metro"));
        assert_eq!(obs.observed_at.unwrap().to_rfc3339(), "2025-06-01T14:00:00-04:00");
        assert_eq!(
            http.request_log()[0],
            "https://www.airnowapi.org/aq/observation/current/ziplatlong/?format=application%2Fjson&latitude=40.0&longitude=-75.0&distance=25&API_KEY=key"
        );
        // Cached for an hour.
        c.fetch_current_air_quality(&Location::new("x", 40.0, -75.0)).unwrap();
        assert_eq!(http.request_log().len(), 1);
    }

    #[test]
    fn live_camelcase_schema_and_derived_category() {
        let payload = json!([{"nowcastAQI": "151.4", "parameterName": "OZONE",
            "dateObserved": "06/01/2025", "hourObserved": "09:00", "localTimeZone": "America/Denver",
            "reportingAreaName": "Denver"}]);
        let obs = parse_observations(&payload).unwrap();
        assert_eq!(obs.aqi, 151);
        assert_eq!(obs.category, "Unhealthy");
        assert_eq!(obs.observed_at.unwrap().to_rfc3339(), "2025-06-01T09:00:00-06:00");
        assert!(parse_observations(&json!([{"AQI": -1}, {"AQI": true}, "x"])).is_none());
        assert!(parse_observations(&json!({"a": 1})).is_none());
    }

    #[test]
    fn invalid_coordinates_and_missing_key() {
        let (http, c) = client(FixtureClient::new());
        assert!(c.fetch_current_air_quality(&Location::new("x", 91.0, 0.0)).is_err());
        let c2 = AirNowClient::new(http.clone(), "", "UA");
        assert_eq!(c2.fetch_current_air_quality(&Location::new("x", 1.0, 1.0)), Ok(None));
        assert!(http.request_log().is_empty());
    }

    #[test]
    fn validation_messages() {
        let check = |http: FixtureClient| client(http).1.validate_api_key();
        assert_eq!(check(FixtureClient::new().with(ENDPOINT, json!([]))), (true, None));
        assert_eq!(
            check(FixtureClient::new().with_status(ENDPOINT, 403)).1.as_deref(),
            Some("Invalid API key")
        );
        assert_eq!(
            check(FixtureClient::new().with_status(ENDPOINT, 429)).1.as_deref(),
            Some("Rate limit exceeded — but key appears valid")
        );
        assert_eq!(
            check(FixtureClient::new().with(ENDPOINT, json!({"WebServiceError": [1]}))).1.as_deref(),
            Some("Invalid API key")
        );
        assert_eq!(
            check(FixtureClient::new().with_transport_error(ENDPOINT, "dns")).1.as_deref(),
            Some("Could not reach AirNow (ConnectError)")
        );
        assert_eq!(
            AirNowClient::new(Arc::new(FixtureClient::new()), "", "UA").validate_api_key(),
            (false, Some("No API key provided".into()))
        );
    }

    #[test]
    fn category_boundaries() {
        for (aqi, cat) in [(50.0, "Good"), (51.0, "Moderate"), (101.0, "Unhealthy for Sensitive Groups"),
            (151.0, "Unhealthy"), (201.0, "Very Unhealthy"), (301.0, "Hazardous")] {
            assert_eq!(air_quality_category(aqi), cat);
        }
    }
}
