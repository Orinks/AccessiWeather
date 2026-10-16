//! Current conditions and station lookups (`weather_client_nws_current.py`).

use std::cmp::Ordering;

use aw_core::model::{CurrentConditions, Location};
use chrono::Duration;
use serde_json::Value;

use super::common::{
    current_data_score, get_truthy, parse_iso_datetime, py_str, scrub_measurements,
    station_sort_key, MAX_OBSERVATION_AGE_HOURS, MAX_STATION_OBSERVATION_ATTEMPTS,
};
use super::parsers::parse_current_conditions;
use super::{or_fallback, NwsClient};
use crate::http::HttpError;

/// `/points` `properties.timeZone` when the key exists (its value may be null).
pub(crate) fn grid_timezone(grid: &Value) -> Option<Option<String>> {
    grid.get("properties")?
        .get("timeZone")
        .map(|tz| tz.as_str().map(str::to_string))
}

impl NwsClient<'_> {
    /// `get_nws_current_conditions`: the best observation among the nearby
    /// stations. Copies `/points`' timezone onto `location`, as Python does.
    pub fn current_conditions(
        &self,
        location: &mut Location,
    ) -> Result<Option<CurrentConditions>, HttpError> {
        let mut timezone = None;
        let result = self.current_conditions_detached(location, &mut timezone);
        if let Some(tz) = timezone {
            location.timezone = tz;
        }
        result
    }

    /// [`Self::current_conditions`] without touching the location; the
    /// timezone it would have set lands in `timezone`.
    pub(crate) fn current_conditions_detached(
        &self,
        location: &Location,
        timezone: &mut Option<Option<String>>,
    ) -> Result<Option<CurrentConditions>, HttpError> {
        self.retry(|| {
            let attempt = self.current_once(location, timezone);
            or_fallback(attempt, None, "Failed to get NWS current conditions")
        })
    }

    fn current_once(
        &self,
        location: &Location,
        timezone: &mut Option<Option<String>>,
    ) -> Result<Option<CurrentConditions>, HttpError> {
        let grid = self.fetch_json(&self.request(self.points_url(location)))?;
        if let Some(tz) = grid_timezone(&grid) {
            *timezone = Some(tz);
        }
        let stations_url = grid["properties"]["observationStations"]
            .as_str()
            .ok_or_else(|| missing("observationStations"))?;
        let stations = self.fetch_json(&self.request(stations_url))?;
        let features = stations
            .get("features")
            .ok_or_else(|| missing("features"))?;
        let features = match features.as_array() {
            Some(f) if !f.is_empty() => f,
            _ => {
                tracing::warn!("No observation stations found");
                return Ok(None);
            }
        };
        let current = self.select_best_observation(features);
        if current.is_none() {
            tracing::warn!(
                "No usable observations found for {} (lat={}, lon={})",
                location.name,
                location.latitude,
                location.longitude
            );
        }
        Ok(current)
    }

    /// `_select_best_observation`: the first fresh observation with a
    /// temperature or description wins; otherwise the best-scoring fallback,
    /// fresh before stale. At most ten stations are tried.
    fn select_best_observation(&self, features: &[Value]) -> Option<CurrentConditions> {
        let mut sorted: Vec<&Value> = features.iter().collect();
        sorted.sort_by(|a, b| {
            station_sort_key(a)
                .partial_cmp(&station_sort_key(b))
                .unwrap_or(Ordering::Equal)
        });

        let now = self.now();
        let mut fallback: Option<(CurrentConditions, (u8, i64, usize))> = None;
        let mut attempts = 0;
        for feature in sorted {
            if attempts >= MAX_STATION_OBSERVATION_ATTEMPTS {
                break;
            }
            let Some(station_id) = get_truthy(&feature["properties"], "stationIdentifier") else {
                continue;
            };
            let station_id = py_str(station_id);
            let obs_url = format!(
                "{}/stations/{station_id}/observations/latest",
                self.base_url
            );
            attempts += 1;

            let mut obs = match self.fetch_json(&self.request(obs_url)) {
                Ok(obs) => obs,
                Err(e) => {
                    tracing::debug!("Failed to fetch observation for {station_id}: {e}");
                    continue;
                }
            };
            let stale = match parse_iso_datetime(&obs["properties"]["timestamp"]) {
                Some(ts) => {
                    now.signed_duration_since(ts) > Duration::hours(MAX_OBSERVATION_AGE_HOURS)
                }
                None => true,
            };
            if let Some(props) = obs.get_mut("properties") {
                scrub_measurements(props);
            }
            let current = parse_current_conditions(&obs);

            let has_temperature =
                current.temperature_f.is_some() || current.temperature_c.is_some();
            let has_description = current
                .condition
                .as_deref()
                .is_some_and(|c| !c.trim().is_empty());
            let score = current_data_score(&current);

            if !stale && (has_temperature || has_description) {
                return Some(current);
            }
            if score == 0 {
                continue;
            }
            let rank = (u8::from(stale), -(score as i64), attempts);
            if fallback.as_ref().is_none_or(|(_, best)| rank < *best) {
                fallback = Some((current, rank));
            }
        }
        fallback.map(|(current, _)| current)
    }

    /// `get_nws_primary_station_info`: (identifier, name) of the first
    /// observation station for the location. Never fails.
    pub fn primary_station_info(&self, location: &Location) -> (Option<String>, Option<String>) {
        let lookup = || -> Result<(Option<String>, Option<String>), HttpError> {
            let grid = self.fetch_json(&self.request(self.points_url(location)))?;
            let Some(stations_url) = get_truthy(&grid["properties"], "observationStations") else {
                tracing::debug!("No observationStations URL in NWS grid data");
                return Ok((None, None));
            };
            let stations = self.fetch_json(&self.request(py_str(stations_url)))?;
            let Some(first) = stations["features"].as_array().and_then(|f| f.first()) else {
                tracing::debug!("No observation station features returned");
                return Ok((None, None));
            };
            let props = &first["properties"];
            let field = |k: &str| props.get(k).filter(|v| !v.is_null()).map(py_str);
            Ok((field("stationIdentifier"), field("name")))
        };
        lookup().unwrap_or_else(|e| {
            tracing::error!("Failed to look up primary station info: {e}");
            (None, None)
        })
    }

    /// `get_nws_station_metadata`: the raw `/stations/{id}` document.
    pub fn station_metadata(&self, station_id: &str) -> Option<Value> {
        if station_id.is_empty() {
            return None;
        }
        let url = format!("{}/stations/{station_id}", self.base_url);
        self.fetch_json(&self.request(url))
            .inspect_err(|e| {
                tracing::debug!("Failed to fetch station metadata for {station_id}: {e}")
            })
            .ok()
    }
}

fn missing(what: &str) -> HttpError {
    HttpError::Json {
        url: String::new(),
        message: format!("missing {what}"),
    }
}
