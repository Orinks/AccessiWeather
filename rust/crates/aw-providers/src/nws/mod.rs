//! National Weather Service client, ported from the Python
//! `weather_client_nws*.py` modules (plus the aviation, marine, TAF and zone
//! helpers they rely on).
//!
//! Every Python function decorated with
//! `async_retry_with_backoff(max_attempts=3, base_delay=1.0)` keeps that
//! contract here: retryable failures (transport errors, 5xx/408/409/425/429)
//! are retried with a 1 s, 2 s backoff and surface as `Err` once exhausted;
//! everything else degrades to the same fallback value Python returns.

mod alerts;
mod aviation;
mod avwx;
pub mod common;
mod current;
mod forecast;
mod hourly;
pub mod normalize;
pub mod parsers;
pub mod taf;
mod zones;

use std::sync::Arc;
use std::time::Duration;

use aw_core::model::{
    CurrentConditions, Forecast, HourlyForecast, Location, Timestamp, WeatherAlerts,
};
use chrono::Local;
use serde_json::Value;

use crate::http::{retry_with_backoff, HttpClient, HttpError, HttpRequest, HttpResponse};

pub use aviation::{filter_advisories, taf_indicates_no_data, AviationError, AviationOptions};
pub use avwx::{fetch_avwx_taf, is_us_station, AvwxError, AVWX_BASE_URL};
pub use common::py_float_repr;
pub use forecast::{ForecastAndDiscussion, TextProductError, TextProducts};
pub use parsers::Malformed;
pub use taf::decode_taf_text;
pub use zones::{diff_zone_fields, extract_zone_fields, last_path_segment, ZoneFields};

pub const BASE_URL: &str = "https://api.weather.gov";
/// The `user_agent` the app hands `WeatherClient` (`app_initialization.py`).
pub const USER_AGENT: &str = "AccessiWeather/2.0";
/// Default `user_agent` of the standalone text-product helpers, which the
/// forecast-products and climate dialogs call without overriding it.
pub const PRODUCT_USER_AGENT: &str = "AccessiWeather (github.com/orinks/accessiweather)";
/// Requests quantitative temperature and wind values in forecasts.
pub const FEATURE_FLAGS: &str = "forecast_temperature_qv, forecast_wind_speed_qv";

const MAX_ATTEMPTS: u32 = 3;

impl From<Malformed> for HttpError {
    fn from(m: Malformed) -> Self {
        HttpError::Json {
            url: String::new(),
            message: m.0,
        }
    }
}

/// Receives `(location name, changed zone fields)` after a `/points` fetch
/// shows the stored NWS metadata has drifted; the app persists them on the
/// UI thread (`set_zone_drift_sink` + `wx.CallAfter` in Python).
pub type ZoneDriftSink = Arc<dyn Fn(&str, &ZoneFields) + Send + Sync>;

/// Everything `get_nws_all_data_parallel` returns.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct NwsData {
    pub current: Option<CurrentConditions>,
    pub forecast: Option<Forecast>,
    pub discussion: Option<String>,
    pub discussion_issuance_time: Option<Timestamp>,
    pub alerts: Option<WeatherAlerts>,
    pub hourly_forecast: Option<HourlyForecast>,
}

pub struct NwsClient<'a> {
    http: &'a dyn HttpClient,
    pub base_url: String,
    pub user_agent: String,
    /// First retry delay; doubles per attempt (Python `base_delay=1.0`).
    pub retry_delay: Duration,
    /// Frozen clock for tests; `None` reads the local clock.
    pub now: Option<Timestamp>,
    pub zone_drift_sink: Option<ZoneDriftSink>,
}

impl<'a> NwsClient<'a> {
    pub fn new(http: &'a dyn HttpClient) -> Self {
        Self {
            http,
            base_url: BASE_URL.to_string(),
            user_agent: USER_AGENT.to_string(),
            retry_delay: Duration::from_secs(1),
            now: None,
            zone_drift_sink: None,
        }
    }

    /// `datetime.now()`.
    pub(crate) fn now(&self) -> Timestamp {
        self.now.unwrap_or_else(|| Local::now().fixed_offset())
    }

    /// A GET carrying the client's `User-Agent`, as every NWS call does.
    pub(crate) fn request(&self, url: impl Into<String>) -> HttpRequest {
        HttpRequest::new(url).header("User-Agent", self.user_agent.clone())
    }

    pub(crate) fn send(&self, req: &HttpRequest) -> Result<HttpResponse, HttpError> {
        self.http.send(req)
    }

    /// GET, `raise_for_status()`, `.json()`.
    pub(crate) fn fetch_json(&self, req: &HttpRequest) -> Result<Value, HttpError> {
        self.send(req)?.error_for_status()?.json()
    }

    /// `f"{nws_base_url}/points/{location.latitude},{location.longitude}"`.
    pub(crate) fn points_url(&self, location: &Location) -> String {
        format!(
            "{}/points/{},{}",
            self.base_url,
            py_float_repr(location.latitude),
            py_float_repr(location.longitude)
        )
    }

    /// `async_retry_with_backoff(max_attempts=3, base_delay=1.0)`.
    pub(crate) fn retry<T>(
        &self,
        attempt: impl FnMut() -> Result<T, HttpError>,
    ) -> Result<T, HttpError> {
        retry_with_backoff(MAX_ATTEMPTS, self.retry_delay, attempt)
    }

    /// `get_nws_all_data_parallel`: one `/points` fetch shared by the
    /// forecast and hourly requests, zone drift correction, then current
    /// conditions, forecast + discussion, alerts and hourly in parallel.
    pub fn all_data_parallel(
        &self,
        location: &mut Location,
        alert_radius_type: &str,
    ) -> Result<NwsData, HttpError> {
        self.retry(|| {
            let attempt = self.all_data_once(location, alert_radius_type);
            or_fallback(
                attempt,
                NwsData::default(),
                "Failed to get NWS data in parallel",
            )
        })
    }

    fn all_data_once(
        &self,
        location: &mut Location,
        alert_radius_type: &str,
    ) -> Result<NwsData, HttpError> {
        let grid = self.fetch_json(&self.request(self.points_url(location)))?;
        self.apply_zone_drift_correction(location, &grid);
        // The current-conditions fetch copies /points' timezone onto the
        // location; apply it up front so the hourly parse sees it too.
        if let Some(tz) = current::grid_timezone(&grid) {
            location.timezone = tz;
        }

        let loc = &*location;
        let grid = &grid;
        let (current, forecast, alerts, hourly) = std::thread::scope(|s| {
            let current = s.spawn(|| self.current_conditions_detached(loc, &mut None));
            let forecast = s.spawn(|| self.forecast_and_discussion(loc, Some(grid)));
            let alerts = s.spawn(|| self.alerts(loc, alert_radius_type));
            let hourly = s.spawn(|| self.hourly_forecast(loc, Some(grid)));
            (join(current), join(forecast), join(alerts), join(hourly))
        });
        let current = current?;
        let forecast = forecast?;
        let alerts = alerts?;
        let hourly_forecast = hourly?;
        Ok(NwsData {
            current,
            forecast: forecast.forecast,
            discussion: forecast.discussion,
            discussion_issuance_time: forecast.discussion_issuance_time,
            alerts: Some(alerts),
            hourly_forecast,
        })
    }

    /// `_apply_zone_drift_correction`: never fails the refresh.
    fn apply_zone_drift_correction(&self, location: &Location, point_data: &Value) {
        let Some(sink) = &self.zone_drift_sink else {
            return;
        };
        let properties = &point_data["properties"];
        if !properties.is_object() {
            return;
        }
        let changes = diff_zone_fields(location, &extract_zone_fields(properties));
        if changes.is_empty() {
            return;
        }
        tracing::debug!("Zone drift: scheduled update for {}", location.name);
        sink(&location.name, &changes);
    }
}

fn join<T>(handle: std::thread::ScopedJoinHandle<'_, T>) -> T {
    handle
        .join()
        .unwrap_or_else(|panic| std::panic::resume_unwind(panic))
}

/// The `except Exception` tail of the decorated Python functions: retryable
/// errors propagate so the retry loop sees them, anything else becomes the
/// function's fallback value.
pub(crate) fn or_fallback<T>(
    result: Result<T, HttpError>,
    fallback: T,
    what: &str,
) -> Result<T, HttpError> {
    match result {
        Ok(v) => Ok(v),
        Err(e) => {
            tracing::error!("{what}: {e}");
            if e.is_retryable() {
                Err(e)
            } else {
                Ok(fallback)
            }
        }
    }
}

#[cfg(test)]
mod tests;
