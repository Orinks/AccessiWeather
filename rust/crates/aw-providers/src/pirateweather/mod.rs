//! Pirate Weather client (api.pirateweather.net, Dark Sky compatible JSON),
//! ported from `accessiweather.pirate_weather_client`. One request returns
//! current, minutely, hourly, daily and alert data; a short-lived cache lets
//! the per-section getters share it.

pub mod legacy;
pub mod parsing;

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use aw_core::model::{
    CurrentConditions, Forecast, HourlyForecast, Location, MinutelyPrecipitationForecast,
    WeatherAlerts,
};
use aw_core::py;
use aw_core::units::{resolve_auto_unit_system, DisplayUnitSystem};
use chrono::Local;
use serde_json::Value;

use crate::http::{build_url, HttpClient, HttpError};

pub use parsing::{
    build_alert_id, data_point_condition, icon_to_condition, map_severity, parse_alerts,
    parse_current_conditions, parse_forecast, parse_hourly_forecast, parse_minutely_block,
};

pub const BASE_URL: &str = "https://api.pirateweather.net/forecast";
const API_VERSION: &str = "2";
const RECENT_PAYLOAD_TTL: Duration = Duration::from_secs(2);
const RATE_LIMIT_COOLDOWN: Duration = Duration::from_secs(300);

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
#[error("{message}")]
pub struct PirateWeatherApiError {
    pub message: String,
    pub status_code: Option<u16>,
}

impl PirateWeatherApiError {
    fn new(message: impl Into<String>, status_code: Option<u16>) -> Self {
        Self {
            message: message.into(),
            status_code,
        }
    }
}

#[derive(Default)]
struct State {
    recent: HashMap<String, (Instant, Value)>,
    rate_limited_until: Option<Instant>,
}

pub struct PirateWeatherClient {
    http: Arc<dyn HttpClient>,
    pub api_key: String,
    pub user_agent: String,
    /// "us", "si", "ca" or "uk2" ("uk" is stored as "uk2").
    pub units: String,
    pub base_url: String,
    state: Mutex<State>,
    /// Serialises network fetches so concurrent section getters share one
    /// request (Python shares an in-flight task per location).
    fetch_lock: Mutex<()>,
}

/// Unit bundle for a location from the temperature-unit setting
/// (`WeatherClient._resolve_pirate_weather_units`).
pub fn resolve_pirate_weather_units(temperature_unit: &str, location: &Location) -> &'static str {
    let preference = if temperature_unit.is_empty() { "both" } else { temperature_unit };
    match preference.trim().to_lowercase().as_str() {
        "auto" => match resolve_auto_unit_system(Some(location)) {
            DisplayUnitSystem::Us => "us",
            DisplayUnitSystem::Uk => "uk",
            DisplayUnitSystem::Ca => "ca",
            DisplayUnitSystem::Si => "si",
        },
        "c" | "celsius" => "ca",
        _ => "us",
    }
}

impl PirateWeatherClient {
    pub fn new(http: Arc<dyn HttpClient>, api_key: &str, user_agent: &str, units: &str) -> Self {
        Self {
            http,
            api_key: api_key.to_string(),
            user_agent: user_agent.to_string(),
            units: if units == "uk" { "uk2".into() } else { units.to_string() },
            base_url: BASE_URL.into(),
            state: Mutex::new(State::default()),
            fetch_lock: Mutex::new(()),
        }
    }

    pub fn build_url(&self, lat: f64, lon: f64) -> String {
        format!(
            "{}/{}/{},{}",
            self.base_url,
            self.api_key,
            py::float_repr(lat),
            py::float_repr(lon)
        )
    }

    fn cache_key(&self, location: &Location) -> String {
        format!("{:.6},{:.6}:{}", location.latitude, location.longitude, self.units)
    }

    fn cached(&self, key: &str) -> Option<Value> {
        let mut state = self.state.lock().unwrap();
        let (fetched_at, payload) = state.recent.get(key)?;
        if fetched_at.elapsed() > RECENT_PAYLOAD_TTL {
            state.recent.remove(key);
            return None;
        }
        Some(payload.clone())
    }

    fn enforce_rate_limit_cooldown(&self) -> Result<(), PirateWeatherApiError> {
        let state = self.state.lock().unwrap();
        if state.rate_limited_until.is_some_and(|until| Instant::now() < until) {
            return Err(PirateWeatherApiError::new("API rate limit exceeded", Some(429)));
        }
        Ok(())
    }

    fn request_forecast_data(&self, location: &Location) -> Result<Value, PirateWeatherApiError> {
        let url = build_url(
            &self.build_url(location.latitude, location.longitude),
            &[
                ("units", self.units.clone()),
                ("extend", "hourly".into()),
                ("version", API_VERSION.into()),
            ],
        );
        self.http
            .get_json_with_headers(&url, &[("User-Agent", &self.user_agent)])
            .map_err(|e| match e.status() {
                Some(400) => PirateWeatherApiError::new(
                    "Bad request – check API key and coordinates",
                    Some(400),
                ),
                Some(401) => PirateWeatherApiError::new("Invalid API key", Some(401)),
                Some(429) => {
                    self.state.lock().unwrap().rate_limited_until =
                        Some(Instant::now() + RATE_LIMIT_COOLDOWN);
                    PirateWeatherApiError::new("API rate limit exceeded", Some(429))
                }
                Some(status) => PirateWeatherApiError::new(
                    format!("API request failed: HTTP {status}"),
                    Some(status),
                ),
                None if e.is_timeout() => {
                    tracing::error!("Pirate Weather API request timed out");
                    PirateWeatherApiError::new("Request timed out", None)
                }
                None => match e {
                    HttpError::Transport { message, .. } => {
                        tracing::error!("Pirate Weather API request failed: {message}");
                        PirateWeatherApiError::new(format!("Request failed: {message}"), None)
                    }
                    other => {
                        tracing::error!("Unexpected Pirate Weather error: {other}");
                        PirateWeatherApiError::new(format!("Unexpected error: {other}"), None)
                    }
                },
            })
    }

    /// The full payload (`currently`, `minutely`, `hourly`, `daily`, `alerts`).
    pub fn get_forecast_data(&self, location: &Location) -> Result<Value, PirateWeatherApiError> {
        self.enforce_rate_limit_cooldown()?;
        let key = self.cache_key(location);
        if let Some(payload) = self.cached(&key) {
            return Ok(payload);
        }
        let _guard = self.fetch_lock.lock().unwrap();
        if let Some(payload) = self.cached(&key) {
            return Ok(payload);
        }
        let payload = self.request_forecast_data(location)?;
        self.state
            .lock()
            .unwrap()
            .recent
            .insert(key, (Instant::now(), payload.clone()));
        Ok(payload)
    }

    pub fn get_current_conditions(
        &self,
        location: &Location,
    ) -> Result<CurrentConditions, PirateWeatherApiError> {
        let data = self.get_forecast_data(location)?;
        Ok(parse_current_conditions(&self.units, &data))
    }

    /// All daily periods (the display layer applies the day window).
    pub fn get_forecast(&self, location: &Location) -> Result<Option<Forecast>, PirateWeatherApiError> {
        let data = self.get_forecast_data(location)?;
        Ok(parse_forecast(&self.units, &data, Local::now().fixed_offset()))
    }

    pub fn get_hourly_forecast(
        &self,
        location: &Location,
    ) -> Result<HourlyForecast, PirateWeatherApiError> {
        let data = self.get_forecast_data(location)?;
        Ok(parse_hourly_forecast(&self.units, &data, Local::now().fixed_offset()))
    }

    /// Minutely precipitation (the notification path parses the payload with
    /// this client's unit group); any failure yields `None`.
    pub fn get_minutely_forecast(&self, location: &Location) -> Option<MinutelyPrecipitationForecast> {
        match self.get_forecast_data(location) {
            Ok(data) => parse_minutely_block(&data, &self.units),
            Err(e) => {
                tracing::debug!("Pirate Weather minutely fetch failed: {e}");
                None
            }
        }
    }

    /// Alerts; failures yield an empty list.
    pub fn get_alerts(&self, location: &Location) -> WeatherAlerts {
        match self.get_forecast_data(location) {
            Ok(data) => parse_alerts(&data),
            Err(e) => {
                tracing::debug!("Pirate Weather alerts request failed: {e}");
                WeatherAlerts::default()
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    fn nyc() -> Location {
        Location::new("NYC", 40.7128, -74.006)
    }

    #[test]
    fn init_normalizes_uk_and_builds_url() {
        let http = Arc::new(FixtureClient::new());
        let client = PirateWeatherClient::new(http, "k", "AccessiWeather/1.0", "uk");
        assert_eq!(client.units, "uk2");
        assert_eq!(
            client.build_url(40.7128, -74.006),
            "https://api.pirateweather.net/forecast/k/40.7128,-74.006"
        );
    }

    #[test]
    fn request_uses_version_2_and_shares_the_payload() {
        let http = Arc::new(FixtureClient::new().with(BASE_URL, json!({"currently": {"temperature": 50}})));
        let client = PirateWeatherClient::new(http.clone(), "k", "AccessiWeather/2.0", "us");
        client.get_current_conditions(&nyc()).unwrap();
        client.get_hourly_forecast(&nyc()).unwrap();
        assert_eq!(
            http.request_log(),
            vec!["https://api.pirateweather.net/forecast/k/40.7128,-74.006?units=us&extend=hourly&version=2"]
        );
        assert_eq!(
            http.header_log()[0],
            vec![("User-Agent".to_string(), "AccessiWeather/2.0".to_string())]
        );
    }

    #[test]
    fn http_errors_map_to_python_messages() {
        for (status, message) in [
            (400, "Bad request – check API key and coordinates"),
            (401, "Invalid API key"),
            (500, "API request failed: HTTP 500"),
        ] {
            let http = Arc::new(FixtureClient::new().with_status(BASE_URL, status));
            let client = PirateWeatherClient::new(http, "k", "UA", "us");
            let err = client.get_current_conditions(&nyc()).unwrap_err();
            assert_eq!(err.message, message);
            assert_eq!(err.status_code, Some(status));
        }
        let http = Arc::new(FixtureClient::new().with_transport_error(BASE_URL, "operation timed out"));
        let client = PirateWeatherClient::new(http, "k", "UA", "us");
        assert_eq!(client.get_forecast(&nyc()).unwrap_err().message, "Request timed out");
        assert!(client.get_alerts(&nyc()).alerts.is_empty());
    }

    #[test]
    fn rate_limit_starts_a_cooldown() {
        let http = Arc::new(FixtureClient::new().with_status(BASE_URL, 429));
        let client = PirateWeatherClient::new(http.clone(), "k", "UA", "us");
        assert_eq!(client.get_forecast(&nyc()).unwrap_err().status_code, Some(429));
        assert_eq!(client.get_forecast(&nyc()).unwrap_err().message, "API rate limit exceeded");
        assert_eq!(http.request_log().len(), 1);
    }

    #[test]
    fn unit_bundle_resolution() {
        let gb = Location::new("London", 51.5, -0.1).with_country("GB");
        let ca = Location::new("Toronto", 43.7, -79.4).with_country("CA");
        assert_eq!(resolve_pirate_weather_units("auto", &gb), "uk");
        assert_eq!(resolve_pirate_weather_units("auto", &ca), "ca");
        assert_eq!(resolve_pirate_weather_units("celsius", &gb), "ca");
        assert_eq!(resolve_pirate_weather_units("both", &gb), "us");
        assert_eq!(resolve_pirate_weather_units("", &gb), "us");
    }
}
