//! Hourly forecast with gridpoint pressure (`weather_client_nws_hourly.py`).

use aw_core::model::{HourlyForecast, Location};
use serde_json::Value;

use super::common::{get_truthy, py_str};
use super::parsers::{
    apply_gridpoint_pressure, parse_gridpoint_pressure, parse_hourly_forecast, PressureByTime,
};
use super::{or_fallback, NwsClient, FEATURE_FLAGS};
use crate::http::HttpError;

impl NwsClient<'_> {
    /// `get_nws_hourly_forecast`, with pressure filled in from the gridpoint
    /// layer. `grid_data` is a `/points` document already in hand.
    pub fn hourly_forecast(
        &self,
        location: &Location,
        grid_data: Option<&Value>,
    ) -> Result<Option<HourlyForecast>, HttpError> {
        self.retry(|| {
            let attempt = self.hourly_once(location, grid_data);
            or_fallback(attempt, None, "Failed to get NWS hourly forecast")
        })
    }

    fn hourly_once(
        &self,
        location: &Location,
        grid_data: Option<&Value>,
    ) -> Result<Option<HourlyForecast>, HttpError> {
        let fetched;
        let grid = match grid_data {
            Some(g) => g,
            None => {
                fetched = self.fetch_json(&self.request(self.points_url(location)))?;
                &fetched
            }
        };
        let Some(url) = get_truthy(&grid["properties"], "forecastHourly") else {
            tracing::warn!("No hourly forecast URL found in grid data");
            return Ok(None);
        };
        let req = self
            .request(py_str(url))
            .header("Feature-Flags", FEATURE_FLAGS);
        let hourly = parse_hourly_forecast(&self.fetch_json(&req)?, Some(location), self.now())?;
        let pressure = self.gridpoint_pressure(grid)?;
        Ok(Some(apply_gridpoint_pressure(hourly, &pressure)))
    }

    /// `_fetch_nws_gridpoint_pressure`: only retryable failures propagate.
    fn gridpoint_pressure(&self, point_data: &Value) -> Result<PressureByTime, HttpError> {
        let Some(url) = get_truthy(&point_data["properties"], "forecastGridData") else {
            return Ok(Vec::new());
        };
        match self.fetch_json(&self.request(py_str(url))) {
            Ok(data) => Ok(parse_gridpoint_pressure(&data)),
            Err(e) if e.is_retryable() => Err(e),
            Err(e) => {
                tracing::debug!("NWS gridpoint pressure fetch failed: {e}");
                Ok(Vec::new())
            }
        }
    }
}
