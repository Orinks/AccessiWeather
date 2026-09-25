//! Automatic ("smart auto") source mode. Port of
//! `accessiweather/weather_client_auto.py`.

use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::sync::Arc;

use aw_core::alert_aggregator::AlertAggregator;
use aw_core::alert_lifecycle::diff_alerts;
use aw_core::forecast_confidence::calculate_forecast_confidence;
use aw_core::fusion::{DataFusionEngine, SourcePriorityConfig};
use aw_core::model::{
    CurrentConditions, Forecast, HourlyForecast, Location, SourceAttribution, SourceData,
    WeatherAlerts, WeatherData,
};
use aw_core::source_selection::{
    self as selection, AutoBudget, AutoPrimaryOutcome, NWS, OPENMETEO, PIRATEWEATHER,
};

use super::parallel::{ParallelFetchCoordinator, SourceFetch};
use super::{location_key, WeatherClient};

pub const AUTO_NWS_DISCUSSION_PLACEHOLDER: &str =
    "Forecast discussion available from NWS for US locations.";
pub const AUTO_NO_NWS_DISCUSSION_TEXT: &str =
    "Forecast discussion is unavailable because Automatic mode did not use NWS.";
pub const AUTO_NON_NWS_DISCUSSION_TEXT: &str = "Forecast discussion not available from Open-Meteo.";

/// Stale reasons shown with cached data after a failed refresh.
pub const ALL_SOURCES_FAILED_REASON: &str = "All weather sources failed";
pub const ALL_SOURCES_FAILED_NO_CACHE_REASON: &str =
    "All weather sources failed and no cached data available";

/// Whether the data already carries a fetched AFD (not a placeholder).
pub(super) fn has_real_discussion(weather: &WeatherData) -> bool {
    match weather.discussion.as_deref() {
        None | Some("") => false,
        Some(text) => {
            ![
                AUTO_NWS_DISCUSSION_PLACEHOLDER,
                AUTO_NO_NWS_DISCUSSION_TEXT,
                AUTO_NON_NWS_DISCUSSION_TEXT,
            ]
            .contains(&text)
                && !text.starts_with("Forecast discussion not available")
        }
    }
}

/// Whether automatic mode should make a follow-up NWS discussion request.
pub(super) fn should_enrich_nws_discussion(weather: &WeatherData) -> bool {
    !has_real_discussion(weather)
        && weather.discussion.as_deref() != Some(AUTO_NO_NWS_DISCUSSION_TEXT)
}

fn has_core_data(source: Option<&SourceData>) -> bool {
    source.is_some_and(|s| {
        s.current.as_ref().is_some_and(CurrentConditions::has_data)
            && s.forecast.as_ref().is_some_and(Forecast::has_data)
            && s.hourly_forecast
                .as_ref()
                .is_some_and(HourlyForecast::has_data)
    })
}

impl WeatherClient {
    /// One fetch closure per requested source, in Python's fixed
    /// NWS / Open-Meteo / Pirate Weather order.
    fn auto_fetches(
        &self,
        location: &Location,
        requested: &[String],
        fetchable: &[&str],
    ) -> Vec<(String, SourceFetch)> {
        let wanted = |s: &str| fetchable.contains(&s) && requested.iter().any(|r| r == s);
        let mut fetches: Vec<(String, SourceFetch)> = Vec::new();
        let settings = &self.settings;
        if wanted(NWS) {
            let nws = Arc::clone(&self.sources.nws);
            let loc = location.clone();
            let radius = settings.alert_radius_type.clone();
            fetches.push((
                NWS.into(),
                Box::new(move || {
                    let data = nws.get_all_data(&loc, &radius)?;
                    Ok(SourceData {
                        current: data.current,
                        forecast: data.forecast,
                        hourly_forecast: data.hourly_forecast,
                        alerts: data.alerts,
                        discussion: data.discussion,
                        discussion_issuance_time: data.discussion_issuance_time,
                        ..SourceData::new(NWS)
                    })
                }),
            ));
        }
        if wanted(OPENMETEO) {
            let openmeteo = Arc::clone(&self.sources.openmeteo);
            let loc = location.clone();
            let days =
                selection::forecast_days_for_source(settings.forecast_duration_days, OPENMETEO);
            let hours = selection::hourly_hours_for_pressure_outlook(
                settings.hourly_forecast_hours,
                settings.trend_hours,
            );
            fetches.push((
                OPENMETEO.into(),
                Box::new(move || {
                    let (current, forecast, hourly_forecast) =
                        openmeteo.get_all_data(&loc, days, hours)?;
                    Ok(SourceData {
                        current,
                        forecast,
                        hourly_forecast,
                        ..SourceData::new(OPENMETEO)
                    })
                }),
            ));
        }
        if let Some(pirate) = self
            .sources
            .pirate_weather
            .as_ref()
            .filter(|_| wanted(PIRATEWEATHER))
        {
            let pirate = Arc::clone(pirate);
            let loc = location.clone();
            let units = self.pirate_units(location);
            let days =
                selection::forecast_days_for_source(settings.forecast_duration_days, PIRATEWEATHER);
            fetches.push((
                PIRATEWEATHER.into(),
                Box::new(move || {
                    Ok(SourceData {
                        current: pirate.get_current_conditions(&loc, units)?,
                        forecast: pirate.get_forecast(&loc, days, units)?,
                        hourly_forecast: pirate.get_hourly_forecast(&loc, units)?,
                        alerts: pirate.get_alerts(&loc, units)?,
                        ..SourceData::new(PIRATEWEATHER)
                    })
                }),
            ));
        }
        fetches
    }

    /// `_fetch_smart_auto_source`: fetch the configured sources (all at once
    /// for max coverage, staged for economy/balanced) and fuse them.
    pub(super) fn fetch_smart_auto_source(&self, location: &Location) -> WeatherData {
        tracing::info!("Using smart auto source for {}", location.name);
        let settings = &self.settings;
        let is_us = self.is_us(location);
        let auto_sources_us = selection::validated_auto_sources(&settings.auto_sources_us, true);
        let auto_sources_international =
            selection::validated_auto_sources(&settings.auto_sources_international, false);
        let engine = DataFusionEngine::new(SourcePriorityConfig {
            us_default: auto_sources_us.clone(),
            international_default: auto_sources_international.clone(),
            ..Default::default()
        });
        let budget = AutoBudget::parse(&settings.auto_mode_api_budget);
        let coordinator = ParallelFetchCoordinator::new(settings.parallel_fetch_timeout);
        let active = if is_us {
            auto_sources_us
        } else {
            auto_sources_international
        };
        let fetchable = selection::auto_fetchable_sources(
            &active,
            is_us,
            self.sources.pirate_weather.is_some(),
        );

        let initial = selection::auto_initial_sources(budget, &active, &fetchable);
        let mut results = coordinator.fetch_all(
            self.auto_fetches(location, &initial, &fetchable),
            self.now(),
        );
        if budget != AutoBudget::MaxCoverage {
            let fetched: Vec<String> = results.iter().map(|s| s.source.clone()).collect();
            let outcome = AutoPrimaryOutcome {
                is_us,
                active: &active,
                fetchable: &fetchable,
                fetched: &fetched,
                primary_source: initial.first().map(String::as_str),
                core_complete: has_core_data(results.first()),
                wants_extended_forecast: selection::should_use_openmeteo_for_extended_forecast(
                    "auto",
                    is_us,
                    settings.forecast_duration_days,
                ),
            };
            let secondary = selection::auto_secondary_sources(&outcome);
            if !secondary.is_empty() {
                let more = coordinator.fetch_all(
                    self.auto_fetches(location, &secondary, &fetchable),
                    self.now(),
                );
                results.extend(more);
            }
        }

        let successful = results.iter().filter(|s| s.success).count();
        if successful == 0 {
            tracing::warn!("All sources failed for {}, checking cache", location.name);
            return self.handle_all_sources_failed(location, &results);
        }

        let (merged_current, current_attribution) =
            engine.merge_current_conditions(&results, location);
        let (merged_forecast, forecast_attribution) =
            engine.merge_forecasts(&results, location, settings.forecast_duration_days);
        let (merged_hourly, hourly_attribution) = engine.merge_hourly_forecasts(&results, location);

        let wants_minutely = settings.notify_minutely_precipitation_start
            || settings.notify_minutely_precipitation_stop
            || settings.notify_precipitation_likelihood;
        let pirate_fetched = results.iter().any(|s| s.source == PIRATEWEATHER);
        let minutely = match &self.sources.pirate_weather {
            Some(pirate) if pirate_fetched || wants_minutely => {
                pirate.get_minutely(location, self.pirate_units(location))
            }
            _ => None,
        };

        let has_data = merged_current
            .as_ref()
            .is_some_and(CurrentConditions::has_data)
            || merged_forecast.as_ref().is_some_and(Forecast::has_data)
            || merged_hourly.as_ref().is_some_and(HourlyForecast::has_data);
        if !has_data {
            tracing::warn!("All sources returned empty data for {}", location.name);
            return self.handle_all_sources_failed(location, &results);
        }

        let mut nws_alerts: Option<&WeatherAlerts> = None;
        let mut pirate_alerts: Option<&WeatherAlerts> = None;
        for source in &results {
            match (source.source.as_str(), &source.alerts) {
                (NWS, Some(alerts)) => nws_alerts = Some(alerts),
                (PIRATEWEATHER, Some(alerts)) => pirate_alerts = Some(alerts),
                _ => {}
            }
        }
        let aggregator = AlertAggregator::default();
        let merged_alerts = if is_us && nws_alerts.is_some() {
            aggregator.aggregate_alerts(nws_alerts, None)
        } else {
            aggregator.aggregate_alerts(nws_alerts, pirate_alerts)
        };

        let key = location_key(location);
        let cancel_ids: HashSet<String> = if nws_alerts.is_some() {
            self.sources.nws.fetch_cancel_references(15)
        } else {
            HashSet::new()
        };
        let previous = self.state().previous_alerts.get(&key).cloned();
        let lifecycle = diff_alerts(
            previous.as_ref(),
            Some(&merged_alerts),
            Some(&cancel_ids),
            self.now(),
        );
        self.state()
            .previous_alerts
            .insert(key, merged_alerts.clone());

        let mut contributing: BTreeSet<String> = current_attribution.contributing_sources.clone();
        contributing.extend(forecast_attribution.values().cloned());
        contributing.extend(hourly_attribution.values().cloned());
        contributing.extend(
            results
                .iter()
                .filter(|s| s.alerts.is_some())
                .map(|s| s.source.clone()),
        );
        let mut failed = current_attribution.failed_sources.clone();
        failed.extend(
            results
                .iter()
                .filter(|s| !s.success)
                .map(|s| s.source.clone()),
        );
        let mut field_sources: BTreeMap<String, String> = current_attribution.field_sources.clone();
        field_sources.extend(forecast_attribution);
        field_sources.extend(hourly_attribution);
        let attribution = SourceAttribution {
            field_sources,
            conflicts: current_attribution.conflicts,
            contributing_sources: contributing,
            failed_sources: failed,
        };

        let mut incomplete = BTreeSet::new();
        if merged_current.is_none() {
            incomplete.insert("current".to_string());
        }
        if merged_forecast.is_none() {
            incomplete.insert("forecast".to_string());
        }
        if merged_hourly.is_none() {
            incomplete.insert("hourly_forecast".to_string());
        }

        let nws_discussion = results.iter().find(|s| {
            s.source == NWS && s.success && s.discussion.as_deref().is_some_and(|d| !d.is_empty())
        });
        let (discussion, discussion_issuance_time) = match nws_discussion {
            Some(source) if is_us => (source.discussion.clone(), source.discussion_issuance_time),
            _ if is_us && results.iter().any(|s| s.source == NWS) => {
                (Some(AUTO_NWS_DISCUSSION_PLACEHOLDER.to_string()), None)
            }
            _ if is_us => (Some(AUTO_NO_NWS_DISCUSSION_TEXT.to_string()), None),
            _ => (Some(AUTO_NON_NWS_DISCUSSION_TEXT.to_string()), None),
        };

        let mut weather = WeatherData {
            current: merged_current,
            forecast: merged_forecast,
            hourly_forecast: merged_hourly,
            discussion,
            discussion_issuance_time,
            minutely_precipitation: minutely,
            alerts: Some(merged_alerts),
            source_attribution: Some(attribution),
            incomplete_sections: incomplete,
            forecast_confidence: Some(calculate_forecast_confidence(&results)),
            alert_lifecycle_diff: Some(lifecycle),
            ..WeatherData::new(location.clone())
        };
        if weather.has_any_data() {
            self.run_enrichments(&mut weather, location);
        }
        tracing::info!(
            "Smart auto source completed for {}: {successful} sources succeeded",
            location.name
        );
        weather
    }

    /// `_handle_all_sources_failed`: stale cached data when there is some,
    /// otherwise empty sections flagged as failed.
    fn handle_all_sources_failed(
        &self,
        location: &Location,
        results: &[SourceData],
    ) -> WeatherData {
        if let Some(mut cached) = self
            .offline_cache
            .as_ref()
            .and_then(|c| c.load(location, true, self.now()))
        {
            cached.stale = true;
            cached.stale_reason = Some(ALL_SOURCES_FAILED_REASON.into());
            tracing::info!("Returning stale cached data for {}", location.name);
            self.remember_weather_data(&cached);
            return cached;
        }
        WeatherData {
            current: Some(CurrentConditions::default()),
            forecast: Some(Forecast::default()),
            hourly_forecast: Some(HourlyForecast::default()),
            alerts: Some(WeatherAlerts::default()),
            source_attribution: Some(SourceAttribution {
                failed_sources: results.iter().map(|s| s.source.clone()).collect(),
                ..Default::default()
            }),
            incomplete_sections: ["current", "forecast", "hourly_forecast", "alerts"]
                .into_iter()
                .map(String::from)
                .collect(),
            stale: true,
            stale_reason: Some(ALL_SOURCES_FAILED_NO_CACHE_REASON.into()),
            ..WeatherData::new(location.clone())
        }
    }
}
