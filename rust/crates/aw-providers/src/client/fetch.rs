//! Single-source fetch (a specific source chosen in settings). Port of
//! `_do_fetch_weather_data` in `accessiweather/weather_client_fetch.py`.
//!
//! Python's NWS branch also has an "Open-Meteo for the extended forecast"
//! path, but it only runs in automatic mode, which never reaches this code,
//! so it is not ported.

use std::collections::BTreeMap;

use aw_core::alert_lifecycle::diff_alerts;
use aw_core::model::{
    CurrentConditions, Forecast, HourlyForecast, Location, SourceAttribution, WeatherAlerts,
    WeatherData,
};
use aw_core::source_selection::{self as selection, NWS, OPENMETEO, PIRATEWEATHER};

use super::sources::{SourceError, SourceResult};
use super::{joined, location_key, WeatherClient};

pub const PIRATE_WEATHER_DISCUSSION_TEXT: &str =
    "Forecast discussion not available from Pirate Weather.";
pub const OPENMETEO_DISCUSSION_TEXT: &str = "Forecast discussion not available from Open-Meteo.";
pub const NO_DATA_DISCUSSION_TEXT: &str = "Weather data not available.";

fn attribution(sources: &[&str], field_sources: &[(&str, &str)]) -> SourceAttribution {
    SourceAttribution {
        field_sources: field_sources
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect::<BTreeMap<_, _>>(),
        contributing_sources: sources.iter().map(|s| s.to_string()).collect(),
        ..Default::default()
    }
}

/// `_set_empty_weather_data`: what the user sees when the source failed.
fn set_empty(weather: &mut WeatherData) {
    weather.current = Some(CurrentConditions::default());
    weather.forecast = Some(Forecast::default());
    weather.hourly_forecast = Some(HourlyForecast::default());
    weather.discussion = Some(NO_DATA_DISCUSSION_TEXT.into());
    weather.discussion_issuance_time = None;
    weather.alerts = Some(WeatherAlerts::default());
}

impl WeatherClient {
    pub(super) fn fetch_single_source(&self, location: &Location) -> WeatherData {
        let api = selection::determine_api_choice(
            &self.data_source,
            self.sources.pirate_weather.is_some(),
            self.is_us(location),
        );
        tracing::info!(
            "Using {} API for {} (data_source: {})",
            selection::api_display_name(api),
            location.name,
            self.data_source
        );
        let mut weather = WeatherData::new(location.clone());
        let result = match api {
            PIRATEWEATHER => self.fetch_pirate_weather(location, &mut weather),
            OPENMETEO => self.fetch_openmeteo_only(location, &mut weather),
            _ => self.fetch_nws_only(location, &mut weather),
        };
        if let Err(e) = result {
            tracing::error!(
                "{} API failed for {}: {e}",
                selection::api_display_name(api),
                location.name
            );
            set_empty(&mut weather);
        }

        if weather.has_any_data() {
            self.run_enrichments(&mut weather, location);
        } else if let Some(cached) = self
            .offline_cache
            .as_ref()
            .and_then(|c| c.load(location, true, self.now()))
        {
            tracing::info!("Using cached weather data for {}", location.name);
            self.remember_weather_data(&cached);
            return cached;
        }
        self.remember_weather_data(&weather);
        weather
    }

    fn fetch_pirate_weather(
        &self,
        location: &Location,
        weather: &mut WeatherData,
    ) -> SourceResult<()> {
        let pirate = self
            .sources
            .pirate_weather
            .clone()
            .ok_or_else(|| SourceError::new("Pirate Weather API key not configured"))?;
        let units = self.pirate_units(location);
        let days = selection::forecast_days_for_source(
            self.settings.forecast_duration_days,
            PIRATEWEATHER,
        );
        let (current, forecast, hourly, alerts) = std::thread::scope(|scope| {
            let current = scope.spawn(|| pirate.get_current_conditions(location, units));
            let forecast = scope.spawn(|| pirate.get_forecast(location, days, units));
            let hourly = scope.spawn(|| pirate.get_hourly_forecast(location, units));
            let alerts = scope.spawn(|| pirate.get_alerts(location, units));
            (
                joined(current),
                joined(forecast),
                joined(hourly),
                joined(alerts),
            )
        });
        weather.current = current?;
        weather.forecast = forecast?;
        weather.hourly_forecast = hourly?;
        let alerts = alerts?;
        weather.discussion = Some(PIRATE_WEATHER_DISCUSSION_TEXT.into());
        weather.discussion_issuance_time = None;

        let key = location_key(location);
        let previous = self.state().previous_alerts.get(&key).cloned();
        weather.alert_lifecycle_diff = Some(diff_alerts(
            previous.as_ref(),
            alerts.as_ref(),
            None,
            self.now(),
        ));
        if let Some(alerts) = &alerts {
            self.state().previous_alerts.insert(key, alerts.clone());
        }
        weather.alerts = alerts;
        weather.source_attribution = Some(attribution(&[PIRATEWEATHER], &[]));
        tracing::info!(
            "Successfully fetched Pirate Weather data for {}",
            location.name
        );
        Ok(())
    }

    fn fetch_openmeteo_only(
        &self,
        location: &Location,
        weather: &mut WeatherData,
    ) -> SourceResult<()> {
        let settings = &self.settings;
        let (current, forecast, hourly) = self.sources.openmeteo.get_all_data(
            location,
            selection::forecast_days_for_source(settings.forecast_duration_days, OPENMETEO),
            selection::hourly_hours_for_pressure_outlook(
                settings.hourly_forecast_hours,
                settings.trend_hours,
            ),
        )?;
        weather.current = current;
        weather.forecast = forecast;
        weather.hourly_forecast = hourly;
        weather.discussion = Some(OPENMETEO_DISCUSSION_TEXT.into());
        weather.discussion_issuance_time = None;
        // Open-Meteo has no alerts.
        weather.alerts = Some(WeatherAlerts::default());
        weather.source_attribution = Some(attribution(&[OPENMETEO], &[]));
        tracing::info!("Successfully fetched Open-Meteo data for {}", location.name);
        Ok(())
    }

    fn fetch_nws_only(&self, location: &Location, weather: &mut WeatherData) -> SourceResult<()> {
        let data = self
            .sources
            .nws
            .get_all_data(location, &self.settings.alert_radius_type)?;
        weather.current = data.current;
        weather.forecast = data.forecast;
        weather.hourly_forecast = data.hourly_forecast;
        weather.discussion = data.discussion;
        weather.discussion_issuance_time = data.discussion_issuance_time;
        let alerts = data.alerts;

        let key = location_key(location);
        let previous = self.state().previous_alerts.get(&key).cloned();
        let cancel_ids = self.sources.nws.fetch_cancel_references(15);
        weather.alert_lifecycle_diff = Some(diff_alerts(
            previous.as_ref(),
            alerts.as_ref(),
            Some(&cancel_ids),
            self.now(),
        ));
        if let Some(alerts) = &alerts {
            self.state().previous_alerts.insert(key, alerts.clone());
        }
        weather.alerts = alerts;
        weather.source_attribution = Some(attribution(
            &[NWS],
            &[("forecast_source", NWS), ("hourly_source", NWS)],
        ));
        if !weather
            .current
            .as_ref()
            .is_some_and(CurrentConditions::has_data)
            && weather.forecast.is_none()
        {
            tracing::warn!("NWS returned empty data for {}", location.name);
        } else {
            tracing::info!("Successfully fetched NWS data for {}", location.name);
        }
        Ok(())
    }
}
