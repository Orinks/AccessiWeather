//! The data sources over the real HTTP clients: what the Python
//! `WeatherClient` calls through `weather_client_sources.py`,
//! `_fetch_nws_data` / `_fetch_openmeteo_data` (`weather_client_base.py`),
//! `enrich_with_marine_data`, the Pirate Weather and environmental clients
//! and `WeatherHistoryService`'s archive request, wired as
//! `app_initialization.py` / `refresh_runtime_settings` wire them.

use std::collections::HashSet;
use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;

use aw_core::model::{
    AviationData, CurrentConditions, EnvironmentalConditions, Forecast, HourlyForecast, Location,
    MinutelyPrecipitationForecast, Timestamp, WeatherAlerts,
};
use aw_core::py;
use aw_core::settings::AppSettings;
use chrono::{Local, Utc};
use serde_json::Value;

use super::history::{ArchiveRequest, ArchiveSource};
use super::sources::{
    AviationOptions, AviationSource, EnvironmentalSource, MarineSource, NwsAllData, NwsSource,
    OpenMeteoSource, PirateWeatherSource, SourceError, SourceResult,
};
use super::{ClientSources, Clock};
use crate::environmental::{EnvironmentalDataClient, FetchOptions};
use crate::http::{retry_with_backoff, HttpClient, HttpError};
use crate::nws::{self, parsers::parse_alerts, NwsClient, ZoneDriftSink};
use crate::openmeteo::{self, OpenMeteoApiClient};
use crate::pirateweather::{self, PirateWeatherClient};

/// The `user_agent` `app_initialization.py` gives the weather client.
pub const USER_AGENT: &str = nws::USER_AGENT;

fn source_error(e: impl std::fmt::Display) -> SourceError {
    SourceError::new(e.to_string())
}

/// `retry_with_backoff(max_retries=1, initial_delay=1.0)` from
/// `utils/retry.py`: a timeout or connection failure gets one more try;
/// `Ok(None)` once both failed (the `APITimeoutError` callers turn into
/// "no data"). Anything else fails straight away.
fn retry_timeouts<T>(
    delay: Duration,
    mut attempt: impl FnMut() -> Result<T, HttpError>,
) -> Result<Option<T>, HttpError> {
    for n in 1..=2 {
        match attempt() {
            Ok(value) => return Ok(Some(value)),
            Err(e @ HttpError::Transport { .. }) => {
                if n == 1 {
                    tracing::warn!(
                        "Attempt 1/2 failed: {e}. Retrying in {:.1}s...",
                        delay.as_secs_f64()
                    );
                    std::thread::sleep(delay);
                } else {
                    tracing::error!("All 2 attempts failed. Last error: {e}");
                }
            }
            Err(e) => return Err(e),
        }
    }
    Ok(None)
}

/// Builds the orchestrator's [`ClientSources`] from settings and API keys.
#[derive(Clone)]
pub struct Live {
    pub http: Arc<dyn HttpClient>,
    /// Receives NWS zone metadata drift (`set_zone_drift_sink`).
    pub zone_drift_sink: Option<ZoneDriftSink>,
    /// "now" for the parsers; tests freeze it.
    pub clock: Clock,
    /// First delay of every retry wrapper (Python: 1 s).
    pub retry_delay: Duration,
}

impl Live {
    pub fn new(http: Arc<dyn HttpClient>) -> Self {
        Self {
            http,
            zone_drift_sink: None,
            clock: Arc::new(Utc::now),
            retry_delay: Duration::from_secs(1),
        }
    }

    /// Python's local, naive `datetime.now()`.
    fn local_now(&self) -> Timestamp {
        (self.clock)().with_timezone(&Local).fixed_offset()
    }

    /// Every source for `settings`: Pirate Weather only with an API key,
    /// the environmental client only with air quality or pollen enabled.
    pub fn sources(&self, settings: &AppSettings) -> ClientSources {
        let shared = Arc::new(Shared {
            live: self.clone(),
            avwx_api_key: settings.avwx_api_key.clone(),
        });
        let pirate_weather = (!settings.pirate_weather_api_key.is_empty()).then(|| {
            Arc::new(Pirate {
                live: self.clone(),
                api_key: settings.pirate_weather_api_key.clone(),
                client: Mutex::new(None),
            }) as Arc<dyn PirateWeatherSource>
        });
        let environmental = (settings.air_quality_enabled || settings.pollen_enabled).then(|| {
            Arc::new(Environmental {
                client: EnvironmentalDataClient::new(
                    self.http.clone(),
                    USER_AGENT,
                    &settings.airnow_api_key,
                ),
                live: self.clone(),
            }) as Arc<dyn EnvironmentalSource>
        });
        ClientSources {
            nws: shared.clone(),
            openmeteo: shared.clone(),
            pirate_weather,
            environmental,
            aviation: shared.clone(),
            marine: shared,
        }
    }

    /// The Open-Meteo archive for `WeatherHistoryService`.
    pub fn archive(&self) -> Arc<dyn ArchiveSource> {
        Arc::new(Shared {
            live: self.clone(),
            avwx_api_key: String::new(),
        })
    }
}

/// NWS, Open-Meteo, aviation, marine and archive: no state beyond the AVWX key.
struct Shared {
    live: Live,
    avwx_api_key: String,
}

impl Shared {
    fn nws(&self) -> NwsClient<'_> {
        let mut client = NwsClient::new(self.live.http.as_ref());
        client.zone_drift_sink = self.live.zone_drift_sink.clone();
        client.retry_delay = self.live.retry_delay;
        client.now = Some(self.live.local_now());
        client
    }
}

impl NwsSource for Shared {
    fn get_all_data(
        &self,
        location: &Location,
        alert_radius_type: &str,
    ) -> SourceResult<NwsAllData> {
        let mut updated = location.clone();
        let result = retry_timeouts(self.live.retry_delay, || {
            self.nws()
                .all_data_parallel(&mut updated, alert_radius_type)
        })
        .map_err(source_error)?;
        let Some(data) = result else {
            tracing::error!("NWS API timeout after retries");
            return Ok(NwsAllData::default());
        };
        Ok(NwsAllData {
            current: data.current,
            forecast: data.forecast,
            discussion: data.discussion,
            discussion_issuance_time: data.discussion_issuance_time,
            alerts: data.alerts,
            hourly_forecast: data.hourly_forecast,
            timezone: updated
                .timezone
                .filter(|tz| location.timezone.as_ref() != Some(tz)),
        })
    }

    fn get_forecast_and_discussion(
        &self,
        location: &Location,
    ) -> SourceResult<(Option<Forecast>, Option<String>, Option<Timestamp>)> {
        let result = self
            .nws()
            .forecast_and_discussion(location, None)
            .map_err(source_error)?;
        Ok((
            result.forecast,
            result.discussion,
            result.discussion_issuance_time,
        ))
    }

    fn get_discussion_only(
        &self,
        location: &Location,
    ) -> SourceResult<(Option<String>, Option<Timestamp>)> {
        self.nws().discussion_only(location).map_err(source_error)
    }

    fn get_alerts(
        &self,
        location: &Location,
        alert_radius_type: &str,
    ) -> SourceResult<Option<WeatherAlerts>> {
        self.nws()
            .alerts(location, alert_radius_type)
            .map(Some)
            .map_err(source_error)
    }

    fn fetch_cancel_references(&self, lookback_minutes: i64) -> HashSet<String> {
        self.nws()
            .cancel_references(lookback_minutes)
            .into_iter()
            .collect()
    }
}

impl OpenMeteoSource for Shared {
    fn get_all_data(
        &self,
        location: &Location,
        forecast_days: i64,
        hourly_hours: i64,
    ) -> SourceResult<(
        Option<CurrentConditions>,
        Option<Forecast>,
        Option<HourlyForecast>,
    )> {
        let http = self.live.http.as_ref();
        let delay = self.live.retry_delay;
        let now = self.live.local_now();
        let result = retry_timeouts(delay, || {
            retry_with_backoff(3, delay, || {
                openmeteo::get_openmeteo_all_data_parallel(
                    http,
                    location,
                    openmeteo::BASE_URL,
                    forecast_days,
                    "best_match",
                    hourly_hours,
                    now,
                )
            })
        })
        .map_err(source_error)?;
        Ok(result.unwrap_or_else(|| {
            tracing::error!("Open-Meteo API timeout after retries");
            (None, None, None)
        }))
    }

    fn get_current_conditions(
        &self,
        location: &Location,
    ) -> SourceResult<Option<CurrentConditions>> {
        openmeteo::get_openmeteo_current_conditions(
            self.live.http.as_ref(),
            location,
            openmeteo::BASE_URL,
            "best_match",
        )
        .map_err(source_error)
    }
}

impl AviationSource for Shared {
    fn primary_station_info(
        &self,
        location: &Location,
    ) -> SourceResult<(Option<String>, Option<String>)> {
        Ok(self.nws().primary_station_info(location))
    }

    fn aviation_weather(
        &self,
        station_id: &str,
        options: &AviationOptions,
    ) -> SourceResult<AviationData> {
        self.nws()
            .aviation_weather(station_id, options, &self.avwx_api_key)
            .map_err(source_error)
    }
}

impl MarineSource for Shared {
    fn marine_zones(&self, location: &Location) -> SourceResult<Value> {
        let nws = self.nws();
        let point = format!(
            "{},{}",
            nws::py_float_repr(location.latitude),
            nws::py_float_repr(location.longitude)
        );
        let request = nws
            .request(format!("{}/zones", nws.base_url))
            .param("type", "marine")
            .param("point", point);
        nws.fetch_json(&request).map_err(source_error)
    }

    fn marine_forecast(&self, zone_id: &str) -> SourceResult<Option<Value>> {
        self.nws()
            .marine_forecast("marine", zone_id)
            .map_err(source_error)
    }

    fn marine_alerts(&self, zone_id: &str) -> SourceResult<WeatherAlerts> {
        let nws = self.nws();
        let request = nws
            .request(format!("{}/alerts/active", nws.base_url))
            .param("zone", zone_id)
            .param("status", "actual");
        let data = nws.fetch_json(&request).map_err(source_error)?;
        parse_alerts(&data).map_err(|e| source_error(e.0))
    }
}

impl ArchiveSource for Shared {
    fn archive(&self, request: &ArchiveRequest) -> SourceResult<Value> {
        let mut params = vec![
            ("latitude", py::float_repr(request.latitude)),
            ("longitude", py::float_repr(request.longitude)),
            ("start_date", request.start_date.to_string()),
            ("end_date", request.end_date.to_string()),
        ];
        params.extend(request.daily.iter().map(|d| ("daily", d.to_string())));
        params.push(("temperature_unit", request.temperature_unit.clone()));
        params.push(("timezone", "auto".into()));
        OpenMeteoApiClient::new(self.live.http.as_ref())
            .make_request("archive", &params, true)
            .map_err(source_error)
    }

    fn weather_description(&self, code: &Value) -> String {
        OpenMeteoApiClient::get_weather_description(code)
    }
}

/// Pirate Weather, keyed. Like `_pirate_weather_client_for_location`, the
/// client (with its short payload cache and 429 cooldown) is rebuilt when
/// the unit bundle changes.
struct Pirate {
    live: Live,
    api_key: String,
    client: Mutex<Option<Arc<PirateWeatherClient>>>,
}

impl Pirate {
    fn client(&self, units: &str) -> Arc<PirateWeatherClient> {
        let mut slot = self.client.lock().unwrap_or_else(PoisonError::into_inner);
        // Python compares the stored units ("uk2") with the requested bundle
        // ("uk"), so UK users get a fresh client on every call.
        if let Some(client) = slot.as_ref().filter(|c| c.units == units) {
            return client.clone();
        }
        let client = Arc::new(PirateWeatherClient::new(
            self.live.http.clone(),
            &self.api_key,
            USER_AGENT,
            units,
        ));
        *slot = Some(client.clone());
        client
    }

    fn payload(&self, location: &Location, units: &str) -> SourceResult<(Value, String)> {
        let client = self.client(units);
        let data = client.get_forecast_data(location).map_err(source_error)?;
        Ok((data, client.units.clone()))
    }
}

impl PirateWeatherSource for Pirate {
    fn get_current_conditions(
        &self,
        location: &Location,
        units: &str,
    ) -> SourceResult<Option<CurrentConditions>> {
        let (data, units) = self.payload(location, units)?;
        Ok(Some(pirateweather::parse_current_conditions(&units, &data)))
    }

    fn get_forecast(
        &self,
        location: &Location,
        _days: i64,
        units: &str,
    ) -> SourceResult<Option<Forecast>> {
        let (data, units) = self.payload(location, units)?;
        Ok(pirateweather::parse_forecast(
            &units,
            &data,
            self.live.local_now(),
        ))
    }

    fn get_hourly_forecast(
        &self,
        location: &Location,
        units: &str,
    ) -> SourceResult<Option<HourlyForecast>> {
        let (data, units) = self.payload(location, units)?;
        Ok(Some(pirateweather::parse_hourly_forecast(
            &units,
            &data,
            self.live.local_now(),
        )))
    }

    fn get_alerts(&self, location: &Location, units: &str) -> SourceResult<Option<WeatherAlerts>> {
        Ok(Some(self.client(units).get_alerts(location)))
    }

    fn get_minutely(
        &self,
        location: &Location,
        units: &str,
    ) -> Option<MinutelyPrecipitationForecast> {
        self.client(units).get_minutely_forecast(location)
    }
}

/// Air quality, pollen and hourly UV (`EnvironmentalDataClient`).
struct Environmental {
    client: EnvironmentalDataClient,
    live: Live,
}

impl EnvironmentalSource for Environmental {
    fn fetch(
        &self,
        location: &Location,
        include_air_quality: bool,
        include_pollen: bool,
        include_hourly_air_quality: bool,
        prefer_airnow: bool,
    ) -> SourceResult<Option<EnvironmentalConditions>> {
        let options = FetchOptions {
            include_air_quality,
            include_pollen,
            include_hourly_air_quality,
            prefer_airnow,
            ..FetchOptions::default()
        };
        Ok(self.client.fetch(location, options, self.live.local_now()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    fn fixture_live(http: FixtureClient) -> (Arc<FixtureClient>, Live) {
        let http = Arc::new(http);
        let mut live = Live::new(http.clone());
        live.retry_delay = Duration::ZERO;
        (http, live)
    }

    fn nyc() -> Location {
        Location::new("New York, NY", 40.7128, -74.006).with_country("US")
    }

    #[test]
    fn sources_follow_settings_and_keys() {
        let (_, live) = fixture_live(FixtureClient::new());
        let mut settings = AppSettings {
            air_quality_enabled: false,
            pollen_enabled: false,
            ..AppSettings::default()
        };
        let sources = live.sources(&settings);
        assert!(sources.pirate_weather.is_none() && sources.environmental.is_none());
        settings.pirate_weather_api_key = "key".into();
        settings.pollen_enabled = true;
        let sources = live.sources(&settings);
        assert!(sources.pirate_weather.is_some() && sources.environmental.is_some());
    }

    #[test]
    fn nws_timeouts_become_empty_data_and_server_errors_fail() {
        let points = format!("{}/points/", nws::BASE_URL);
        let (http, live) =
            fixture_live(FixtureClient::new().with_transport_error(&points, "timed out"));
        let data = live.sources(&AppSettings::default()).nws;
        assert_eq!(
            data.get_all_data(&nyc(), "county").unwrap(),
            NwsAllData::default()
        );
        // Two outer attempts, each with the helper's own three.
        assert_eq!(http.request_log().len(), 6);

        let (http, live) = fixture_live(FixtureClient::new().with_status(&points, 503));
        let data = live.sources(&AppSettings::default()).nws;
        assert!(data.get_all_data(&nyc(), "county").is_err());
        assert_eq!(http.request_log().len(), 3);

        let (_, live) = fixture_live(FixtureClient::new().with_status(&points, 404));
        let data = live.sources(&AppSettings::default()).nws;
        assert_eq!(
            data.get_all_data(&nyc(), "county").unwrap(),
            NwsAllData::default()
        );
    }

    #[test]
    fn openmeteo_server_errors_fail_and_bad_requests_are_empty() {
        let (_, live) = fixture_live(FixtureClient::new().with_status(openmeteo::BASE_URL, 400));
        let source = live.sources(&AppSettings::default()).openmeteo;
        assert_eq!(
            source.get_all_data(&nyc(), 7, 24).unwrap(),
            (None, None, None)
        );
        let (_, live) = fixture_live(FixtureClient::new().with_status(openmeteo::BASE_URL, 503));
        let source = live.sources(&AppSettings::default()).openmeteo;
        assert!(source.get_all_data(&nyc(), 7, 24).is_err());
    }

    #[test]
    fn marine_requests_match_python() {
        let base = nws::BASE_URL;
        let (http, live) = fixture_live(
            FixtureClient::new()
                .with(&format!("{base}/zones"), json!({"features": []}))
                .with(&format!("{base}/alerts/active"), json!({"features": []})),
        );
        let marine = live.sources(&AppSettings::default()).marine;
        marine.marine_zones(&nyc()).unwrap();
        assert!(marine.marine_alerts("ANZ335").unwrap().alerts.is_empty());
        assert_eq!(
            http.request_log(),
            [
                format!("{base}/zones?type=marine&point=40.7128%2C-74.006"),
                format!("{base}/alerts/active?zone=ANZ335&status=actual"),
            ]
        );
    }

    #[test]
    fn pirate_client_is_rebuilt_per_unit_bundle() {
        let http = Arc::new(FixtureClient::new());
        let pirate = Pirate {
            live: Live::new(http),
            api_key: "k".into(),
            client: Mutex::new(None),
        };
        let us = pirate.client("us");
        assert!(Arc::ptr_eq(&us, &pirate.client("us")));
        let uk = pirate.client("uk");
        assert_eq!(uk.units, "uk2");
        assert!(!Arc::ptr_eq(&uk, &pirate.client("uk")));
    }
}
