//! Weather-client orchestration: which sources to ask, fusing their answers,
//! enrichment, alert lifecycle tracking and the offline cache. Port of
//! `accessiweather/weather_client_base.py` and the mixins it combines
//! (`weather_client_auto.py`, `_fetch.py`, `_parallel.py`, `_enrichment.py`,
//! `_notification.py`, `_sources.py`).
//!
//! The per-source HTTP clients plug in through the traits in [`sources`].
//! Everything here is blocking; call it from a worker thread.

use std::collections::HashMap;
use std::sync::{Arc, Condvar, Mutex, PoisonError};

use aw_core::location::is_us_location;
use aw_core::model::{Location, WeatherAlerts, WeatherData};
use aw_core::settings::AppSettings;
use aw_core::source_selection::{self, normalize_data_source};
use aw_store::weather_cache::WeatherDataCache;
use chrono::{DateTime, Duration, Utc};

mod auto;
mod enrichment;
mod fetch;
pub mod history;
mod notification;
pub mod parallel;
pub mod sources;

pub use sources::{
    AviationOptions, AviationSource, EnvironmentalSource, MarineSource, NwsAllData, NwsSource,
    OpenMeteoSource, PirateWeatherSource, SourceError, SourceResult,
};

/// Minutely precipitation polling cadence (`weather_client_base.py`).
pub const MINUTELY_FAST_POLL_INTERVAL_MINUTES: i64 = 5;
pub const MINUTELY_RECOMMENDED_MIN_POLL_INTERVAL_MINUTES: i64 = 15;
pub const MINUTELY_ADAPTIVE_PRECIP_PROBABILITY_THRESHOLD: f64 = 30.0;
pub const MINUTELY_ADAPTIVE_LOOKAHEAD_HOURS: i64 = 6;

/// The data sources a [`WeatherClient`] talks to.
#[derive(Clone)]
pub struct ClientSources {
    pub nws: Arc<dyn NwsSource>,
    pub openmeteo: Arc<dyn OpenMeteoSource>,
    /// Present only when a Pirate Weather API key is configured.
    pub pirate_weather: Option<Arc<dyn PirateWeatherSource>>,
    /// Present when air quality or pollen is enabled.
    pub environmental: Option<Arc<dyn EnvironmentalSource>>,
    pub aviation: Arc<dyn AviationSource>,
    pub marine: Arc<dyn MarineSource>,
}

#[derive(Default)]
struct ClientState {
    /// Last alerts per location key, for lifecycle diffs.
    previous_alerts: HashMap<String, WeatherAlerts>,
    latest_weather: HashMap<String, WeatherData>,
    last_minutely_poll: HashMap<String, DateTime<Utc>>,
    cache_purged: bool,
}

/// A fetch other callers for the same location can wait on. `result` is
/// `Some` once finished: `Some(None)` if the fetch panicked.
#[derive(Default)]
struct InFlight {
    result: Mutex<Option<Option<WeatherData>>>,
    done: Condvar,
}

/// Clock used for every "now" decision, replaceable in tests.
pub type Clock = Arc<dyn Fn() -> DateTime<Utc> + Send + Sync>;

/// Multi-source weather client (Python's `WeatherClient`).
pub struct WeatherClient {
    sources: ClientSources,
    settings: AppSettings,
    /// "auto", "nws", "openmeteo" or "pirateweather".
    data_source: String,
    offline_cache: Option<WeatherDataCache>,
    state: Mutex<ClientState>,
    in_flight: Mutex<HashMap<String, Arc<InFlight>>>,
    clock: Clock,
}

/// Result of a scoped worker thread; a panic counts as a failed call.
fn joined<T>(handle: std::thread::ScopedJoinHandle<'_, SourceResult<T>>) -> SourceResult<T> {
    handle
        .join()
        .unwrap_or_else(|_| Err(SourceError::new("fetch thread panicked")))
}

/// `_location_key`: `"{lat:.4f},{lon:.4f}"`.
pub fn location_key(location: &Location) -> String {
    format!("{:.4},{:.4}", location.latitude, location.longitude)
}

impl WeatherClient {
    pub fn new(
        sources: ClientSources,
        settings: AppSettings,
        data_source: &str,
        offline_cache: Option<WeatherDataCache>,
    ) -> Self {
        if normalize_data_source(data_source) != data_source {
            tracing::warn!("Invalid data source '{data_source}', defaulting to 'auto'");
        }
        Self {
            sources,
            settings,
            data_source: normalize_data_source(data_source).to_string(),
            offline_cache,
            state: Mutex::default(),
            in_flight: Mutex::default(),
            clock: Arc::new(Utc::now),
        }
    }

    /// Replace the clock (tests freeze time with this).
    pub fn with_clock(mut self, clock: Clock) -> Self {
        self.clock = clock;
        self
    }

    pub fn settings(&self) -> &AppSettings {
        &self.settings
    }

    pub fn data_source(&self) -> &str {
        &self.data_source
    }

    fn now(&self) -> DateTime<Utc> {
        (self.clock)()
    }

    fn state(&self) -> std::sync::MutexGuard<'_, ClientState> {
        self.state.lock().unwrap_or_else(PoisonError::into_inner)
    }

    fn is_us(&self, location: &Location) -> bool {
        let us = is_us_location(location);
        if !us && location.country_code.is_none() {
            tracing::debug!(
                "Location '{}' lacks country_code and is not safely classifiable as US; \
                 re-add it through geocoding to set country_code.",
                location.name
            );
        }
        us
    }

    fn pirate_units(&self, location: &Location) -> &'static str {
        source_selection::resolve_pirate_weather_units(&self.settings.temperature_unit, location)
    }

    fn trend_hours(&self) -> i64 {
        if self.settings.trend_hours == 0 {
            24
        } else {
            self.settings.trend_hours.max(1)
        }
    }

    /// Get complete weather data for a location. `force_refresh` drops the
    /// cached entry first and bypasses in-flight request sharing.
    pub fn get_weather_data(&self, location: &Location, force_refresh: bool) -> WeatherData {
        tracing::info!("Fetching weather data for {}", location.name);
        if let Some(cache) = &self.offline_cache {
            let purge = !std::mem::replace(&mut self.state().cache_purged, true);
            if purge {
                cache.purge_expired(self.now());
            }
            if force_refresh {
                cache.invalidate(location);
            }
        }
        if force_refresh {
            return self.do_fetch_weather_data(location);
        }
        self.fetch_with_dedup(location)
    }

    /// Concurrent requests for the same location share one fetch.
    fn fetch_with_dedup(&self, location: &Location) -> WeatherData {
        let key = location_key(location);
        let (slot, owner) = {
            let mut in_flight = self
                .in_flight
                .lock()
                .unwrap_or_else(PoisonError::into_inner);
            match in_flight.get(&key) {
                Some(slot) => (slot.clone(), false),
                None => {
                    let slot = Arc::new(InFlight::default());
                    in_flight.insert(key.clone(), slot.clone());
                    (slot, true)
                }
            }
        };
        if !owner {
            tracing::debug!(
                "Request for {} already in flight, waiting for result",
                location.name
            );
            let result = slot
                .done
                .wait_while(
                    slot.result.lock().unwrap_or_else(PoisonError::into_inner),
                    |r| r.is_none(),
                )
                .unwrap_or_else(PoisonError::into_inner);
            if let Some(Some(data)) = result.clone() {
                return data;
            }
            // The owning fetch panicked; fetch for ourselves.
            drop(result);
            return self.do_fetch_weather_data(location);
        }

        /// Unregisters the fetch and wakes waiters, even if the fetch panics.
        struct Release<'a>(&'a WeatherClient, String, Arc<InFlight>);
        impl Drop for Release<'_> {
            fn drop(&mut self) {
                self.0
                    .in_flight
                    .lock()
                    .unwrap_or_else(PoisonError::into_inner)
                    .remove(&self.1);
                self.2
                    .result
                    .lock()
                    .unwrap_or_else(PoisonError::into_inner)
                    .get_or_insert(None);
                self.2.done.notify_all();
            }
        }
        let _release = Release(self, key, slot.clone());
        let data = self.do_fetch_weather_data(location);
        *slot.result.lock().unwrap_or_else(PoisonError::into_inner) = Some(Some(data.clone()));
        data
    }

    fn do_fetch_weather_data(&self, location: &Location) -> WeatherData {
        if self.data_source == "auto" {
            self.fetch_smart_auto_source(location)
        } else {
            self.fetch_single_source(location)
        }
    }

    /// Cached weather for a location (stale allowed) without any network.
    pub fn get_cached_weather(&self, location: &Location) -> Option<WeatherData> {
        self.offline_cache
            .as_ref()?
            .load(location, true, self.now())
    }

    /// Fetch fresh data for a location to warm the cache.
    pub fn pre_warm_cache(&self, location: &Location) -> bool {
        tracing::info!("Pre-warming cache for {}", location.name);
        let warmed = self.get_weather_data(location, true).has_any_data();
        if !warmed {
            tracing::warn!(
                "Cache pre-warm failed: no data returned for {}",
                location.name
            );
        }
        warmed
    }

    /// Warm several locations; returns how many succeeded.
    pub fn pre_warm_batch(&self, locations: &[Location]) -> usize {
        locations.iter().filter(|l| self.pre_warm_cache(l)).count()
    }

    /// Aviation products for an ICAO station (`get_aviation_weather`).
    pub fn get_aviation_weather(
        &self,
        station_id: &str,
        options: &AviationOptions,
    ) -> SourceResult<aw_core::model::AviationData> {
        let station = station_id.trim().to_uppercase();
        if station.is_empty() {
            return Err(SourceError::new(
                "station_id must be a non-empty ICAO identifier.",
            ));
        }
        self.sources.aviation.aviation_weather(&station, options)
    }

    fn remember_weather_data(&self, weather: &WeatherData) {
        self.state()
            .latest_weather
            .insert(location_key(&weather.location), weather.clone());
    }

    /// `_persist_weather_data`: remember it, and cache it unless it is empty
    /// or stale.
    fn persist_weather_data(&self, location: &Location, weather: &WeatherData) {
        self.remember_weather_data(weather);
        if let Some(cache) = &self.offline_cache {
            if weather.has_any_data() && !weather.stale {
                cache.store(location, weather, self.now());
            }
        }
    }

    fn latest_weather_data(&self, location: &Location) -> Option<WeatherData> {
        let latest = self
            .state()
            .latest_weather
            .get(&location_key(location))
            .cloned();
        latest.or_else(|| self.get_cached_weather(location))
    }

    /// Likely precipitation in the next few forecast hours?
    fn should_use_fast_minutely_poll(&self, location: &Location) -> bool {
        let Some(hourly) = self
            .latest_weather_data(location)
            .and_then(|w| w.hourly_forecast)
            .filter(|h| h.has_data())
        else {
            return false;
        };
        let now = self.now();
        let deadline = now + Duration::hours(MINUTELY_ADAPTIVE_LOOKAHEAD_HOURS);
        hourly
            .next_hours(MINUTELY_ADAPTIVE_LOOKAHEAD_HOURS as usize, now)
            .into_iter()
            .any(|p| {
                p.precipitation_probability
                    .is_some_and(|prob| prob >= MINUTELY_ADAPTIVE_PRECIP_PROBABILITY_THRESHOLD)
                    && p.start_time <= deadline
            })
    }

    /// `_should_fetch_minutely_precipitation`: poll Pirate Weather minutely
    /// data no more often than every 15 minutes (or the update interval if
    /// longer); with fast polling on and rain likely soon, every 5 minutes
    /// (or the update interval if shorter).
    pub fn should_fetch_minutely_precipitation(&self, location: &Location) -> bool {
        let normal = Duration::minutes(self.settings.update_interval_minutes.max(1));
        let mut target = normal.max(Duration::minutes(
            MINUTELY_RECOMMENDED_MIN_POLL_INTERVAL_MINUTES,
        ));
        if self.settings.minutely_precipitation_fast_polling
            && self.should_use_fast_minutely_poll(location)
        {
            target = normal.min(Duration::minutes(MINUTELY_FAST_POLL_INTERVAL_MINUTES));
        }
        let last = self
            .state()
            .last_minutely_poll
            .get(&location_key(location))
            .copied();
        last.is_none_or(|last| self.now() - last >= target)
    }
}

#[cfg(test)]
mod tests;
