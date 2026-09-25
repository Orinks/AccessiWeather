//! What the orchestrator asks of each data source.
//!
//! One trait per source, mirroring the calls `weather_client_*.py` makes on
//! the NWS / Open-Meteo / Pirate Weather / environmental / aviation / marine
//! helpers. Implementations are blocking (they run on worker threads) and
//! own their HTTP details, retries and parsing.
//!
//! Error contract: return `Err` where the Python helper *raises*, and
//! `Ok(None)` / `Ok(Default)` where it returns `None` / an all-`None` tuple.
//! The distinction matters: in automatic mode an `Err` marks the source as
//! failed, while `Ok` with no data still counts as a successful (empty)
//! answer.

use std::collections::HashSet;

use aw_core::model::{
    AviationData, CurrentConditions, EnvironmentalConditions, Forecast, HourlyForecast, Location,
    MinutelyPrecipitationForecast, Timestamp, WeatherAlerts,
};
use serde_json::Value;

/// A data source call that failed (the Python helper raised).
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error("{0}")]
pub struct SourceError(pub String);

impl SourceError {
    pub fn new(message: impl Into<String>) -> Self {
        Self(message.into())
    }
}

pub type SourceResult<T> = Result<T, SourceError>;

/// Everything `get_nws_all_data_parallel` returns.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct NwsAllData {
    pub current: Option<CurrentConditions>,
    pub forecast: Option<Forecast>,
    pub discussion: Option<String>,
    pub discussion_issuance_time: Option<Timestamp>,
    pub alerts: Option<WeatherAlerts>,
    pub hourly_forecast: Option<HourlyForecast>,
    /// `/points`' `timeZone`, which the Python helper copies onto the
    /// location it was given.
    pub timezone: Option<String>,
}

/// National Weather Service (`weather_client_nws.py`).
pub trait NwsSource: Send + Sync {
    /// `get_nws_all_data_parallel` wrapped in `retry_with_backoff`
    /// (`max_retries=1`, `initial_delay=1.0`): /points once, then current
    /// conditions, forecast + AFD, alerts (`alert_radius_type`: "county",
    /// "zone", ...) and hourly in parallel. `Ok(NwsAllData::default())` for
    /// non-retryable failures and exhausted timeouts (Python's all-`None`
    /// tuple); `Err` for retryable errors that still fail after the helper's
    /// own retries.
    fn get_all_data(
        &self,
        location: &Location,
        alert_radius_type: &str,
    ) -> SourceResult<NwsAllData>;

    /// `get_nws_forecast_and_discussion`: (forecast, AFD text, AFD issuance).
    fn get_forecast_and_discussion(
        &self,
        location: &Location,
    ) -> SourceResult<(Option<Forecast>, Option<String>, Option<Timestamp>)>;

    /// `get_nws_discussion_only`: (AFD text, AFD issuance) without the
    /// forecast request, so a forecast outage cannot hide AFD updates.
    fn get_discussion_only(
        &self,
        location: &Location,
    ) -> SourceResult<(Option<String>, Option<Timestamp>)>;

    /// `get_nws_alerts` for the location and alert radius type.
    fn get_alerts(
        &self,
        location: &Location,
        alert_radius_type: &str,
    ) -> SourceResult<Option<WeatherAlerts>>;

    /// `fetch_nws_cancel_references(lookback_minutes)`: ids referenced by NWS
    /// Cancel messages issued in the lookback window. Never fails: an empty
    /// set on any error.
    fn fetch_cancel_references(&self, lookback_minutes: i64) -> HashSet<String>;
}

/// Open-Meteo forecast API (`weather_client_openmeteo.py`).
pub trait OpenMeteoSource: Send + Sync {
    /// `get_openmeteo_all_data_parallel(location, ..., forecast_days,
    /// "best_match", hourly_hours)` wrapped in `retry_with_backoff`:
    /// (current, daily forecast, hourly forecast). `Ok((None, None, None))`
    /// when retries time out.
    #[allow(clippy::type_complexity)]
    fn get_all_data(
        &self,
        location: &Location,
        forecast_days: i64,
        hourly_hours: i64,
    ) -> SourceResult<(
        Option<CurrentConditions>,
        Option<Forecast>,
        Option<HourlyForecast>,
    )>;

    /// `get_openmeteo_current_conditions` (used for fresh sunrise/sunset).
    fn get_current_conditions(
        &self,
        location: &Location,
    ) -> SourceResult<Option<CurrentConditions>>;
}

/// Pirate Weather (`pirate_weather_client.py`). Only constructed when an API
/// key is configured. `units` is the unit bundle ("us", "ca", "uk", "si")
/// from `resolve_pirate_weather_units`.
pub trait PirateWeatherSource: Send + Sync {
    fn get_current_conditions(
        &self,
        location: &Location,
        units: &str,
    ) -> SourceResult<Option<CurrentConditions>>;
    fn get_forecast(
        &self,
        location: &Location,
        days: i64,
        units: &str,
    ) -> SourceResult<Option<Forecast>>;
    fn get_hourly_forecast(
        &self,
        location: &Location,
        units: &str,
    ) -> SourceResult<Option<HourlyForecast>>;
    fn get_alerts(&self, location: &Location, units: &str) -> SourceResult<Option<WeatherAlerts>>;
    /// `_get_pirate_weather_minutely`: the minutely block parsed with
    /// `parse_pirate_weather_minutely_block(block, units)`; `None` on any
    /// failure.
    fn get_minutely(
        &self,
        location: &Location,
        units: &str,
    ) -> Option<MinutelyPrecipitationForecast>;
}

/// Air quality and pollen (`services.EnvironmentalDataClient.fetch`).
pub trait EnvironmentalSource: Send + Sync {
    fn fetch(
        &self,
        location: &Location,
        include_air_quality: bool,
        include_pollen: bool,
        include_hourly_air_quality: bool,
        prefer_airnow: bool,
    ) -> SourceResult<Option<EnvironmentalConditions>>;
}

pub use crate::nws::AviationOptions;

/// Aviation products (`weather_client_aviation.py`, NWS / AVWX backed).
pub trait AviationSource: Send + Sync {
    /// `get_nws_primary_station_info`: (station id, station name).
    fn primary_station_info(
        &self,
        location: &Location,
    ) -> SourceResult<(Option<String>, Option<String>)>;
    /// `get_aviation_weather(station_id, ...)`: TAF (decoded), optional
    /// SIGMETs/CWAs; AVWX for international stations when keyed.
    fn aviation_weather(
        &self,
        station_id: &str,
        options: &AviationOptions,
    ) -> SourceResult<AviationData>;
}

/// NWS marine products used by `enrich_with_marine_data`.
pub trait MarineSource: Send + Sync {
    /// Body of `GET {nws}/zones?type=marine&point={lat},{lon}`.
    fn marine_zones(&self, location: &Location) -> SourceResult<Value>;
    /// `get_nws_marine_forecast("marine", zone_id)`: the zone forecast JSON.
    fn marine_forecast(&self, zone_id: &str) -> SourceResult<Option<Value>>;
    /// `GET {nws}/alerts/active?zone={zone_id}&status=actual` parsed with
    /// `parse_nws_alerts`.
    fn marine_alerts(&self, zone_id: &str) -> SourceResult<WeatherAlerts>;
}
