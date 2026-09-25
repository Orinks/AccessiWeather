//! Multi-source weather fetch coordinator: runs the planned providers (in
//! parallel for `max_coverage`, primary-then-fallback otherwise) and merges
//! their results into one `WeatherData`.

use std::sync::Arc;
use std::time::Duration;

use aw_core::settings::AppSettings;
use aw_core::sources::{plan_sources, DataSource, SourcePlan};
use aw_core::weather::WeatherData;
use aw_core::Location;
use chrono::Utc;

use crate::http::HttpClient;
use crate::nws_legacy::NwsClient;
use crate::openmeteo::{Bundle, OpenMeteoClient};
use crate::pirateweather::legacy::PirateWeatherClient;

/// Result of one provider run.
#[derive(Debug, Default)]
pub struct FetchOutcome {
    pub source: String,
    pub bundle: Bundle,
    pub alerts: Option<aw_core::alerts::WeatherAlerts>,
    pub discussion: Option<String>,
    pub location_metadata: Option<crate::nws_legacy::PointInfo>,
    pub error: Option<String>,
}

#[derive(Clone)]
pub struct WeatherClient {
    http: Arc<dyn HttpClient>,
    pub nws_base: Option<String>,
    pub openmeteo_base: Option<String>,
    pub pirate_base: Option<String>,
}

impl WeatherClient {
    pub fn new(http: Arc<dyn HttpClient>) -> Self {
        Self {
            http,
            nws_base: None,
            openmeteo_base: None,
            pirate_base: None,
        }
    }

    pub fn http(&self) -> &dyn HttpClient {
        self.http.as_ref()
    }

    pub fn plan(&self, settings: &AppSettings, location: &Location) -> SourcePlan {
        plan_sources(
            settings,
            location,
            !settings.pirate_weather_api_key.trim().is_empty(),
        )
    }

    /// Fetch weather for `location` following the source plan. Never panics;
    /// provider failures are recorded in `WeatherData::failed_sources`.
    pub fn fetch(&self, settings: &AppSettings, location: &Location) -> WeatherData {
        let plan = self.plan(settings, location);
        let mut data = WeatherData::new(location.clone());
        let eager = plan.eager_sources();
        let mut outcomes = self.run_parallel(&eager, settings, location);

        // Fallbacks for lower budgets: walk the remaining sources until we
        // have current conditions and a forecast.
        for source in plan.sources.iter().skip(eager.len()) {
            if merged_is_complete(&outcomes) {
                break;
            }
            outcomes.push(self.run_one(*source, settings, location));
        }

        // If an eager source failed entirely and there are no fallbacks
        // planned, still try Open-Meteo so the user sees something.
        if !merged_is_complete(&outcomes) && !plan.sources.contains(&DataSource::OpenMeteo) {
            outcomes.push(self.run_one(DataSource::OpenMeteo, settings, location));
        }

        for outcome in outcomes {
            if let Some(err) = outcome.error {
                data.failed_sources.push((outcome.source.clone(), err));
                continue;
            }
            data.sources.push(outcome.source.clone());
            let Bundle {
                current,
                forecast,
                hourly,
            } = outcome.bundle;
            if data.current.as_ref().is_none_or(|c| !c.has_data()) {
                if let Some(c) = current.filter(|c| c.has_data()) {
                    data.current = Some(c);
                }
            }
            if data.forecast.as_ref().is_none_or(|f| !f.has_data()) {
                if let Some(f) = forecast.filter(|f| f.has_data()) {
                    data.forecast = Some(f);
                }
            }
            if data.hourly_forecast.as_ref().is_none_or(|h| !h.has_data()) {
                if let Some(h) = hourly.filter(|h| h.has_data()) {
                    data.hourly_forecast = Some(h);
                }
            }
            if data.alerts.is_none() {
                data.alerts = outcome.alerts;
            }
            if data.discussion.is_none() {
                data.discussion = outcome.discussion;
            }
            if let Some(meta) = outcome.location_metadata {
                let loc = &mut data.location;
                loc.forecast_zone_id = meta.forecast_zone_id.or(loc.forecast_zone_id.take());
                loc.county_zone_id = meta.county_zone_id.or(loc.county_zone_id.take());
                loc.fire_zone_id = meta.fire_zone_id.or(loc.fire_zone_id.take());
                loc.cwa_office = meta.cwa_office.or(loc.cwa_office.take());
                loc.radar_station = meta.radar_station.or(loc.radar_station.take());
                if loc.timezone.is_none() {
                    loc.timezone = meta.timezone;
                }
            }
        }
        if let Some(cur) = &mut data.current {
            cur.fill_unit_pairs();
        }
        data.last_updated = Some(Utc::now());
        data
    }

    fn run_parallel(
        &self,
        sources: &[DataSource],
        settings: &AppSettings,
        location: &Location,
    ) -> Vec<FetchOutcome> {
        if sources.len() <= 1 {
            return sources
                .iter()
                .map(|s| self.run_one(*s, settings, location))
                .collect();
        }
        let (tx, rx) = std::sync::mpsc::channel();
        for &source in sources {
            let tx = tx.clone();
            let client = self.clone();
            let settings = settings.clone();
            let location = location.clone();
            std::thread::Builder::new()
                .name(format!("aw-fetch-{}", source.id()))
                .spawn(move || {
                    let _ = tx.send(client.run_one(source, &settings, &location));
                })
                .expect("spawn fetch thread");
        }
        drop(tx);
        let deadline = Duration::from_secs_f64(settings.parallel_fetch_timeout.clamp(1.0, 120.0));
        let start = std::time::Instant::now();
        let mut outcomes = Vec::with_capacity(sources.len());
        while outcomes.len() < sources.len() {
            let remaining = deadline.saturating_sub(start.elapsed());
            match rx.recv_timeout(remaining) {
                Ok(o) => outcomes.push(o),
                Err(_) => break,
            }
        }
        for source in sources {
            if !outcomes.iter().any(|o| o.source == source.id()) {
                outcomes.push(FetchOutcome {
                    source: source.id().into(),
                    error: Some("timed out".into()),
                    ..Default::default()
                });
            }
        }
        // Keep plan priority order for merging.
        outcomes.sort_by_key(|o| sources.iter().position(|s| s.id() == o.source));
        outcomes
    }

    pub fn run_one(
        &self,
        source: DataSource,
        settings: &AppSettings,
        location: &Location,
    ) -> FetchOutcome {
        let mut outcome = FetchOutcome {
            source: source.id().into(),
            ..Default::default()
        };
        let result = match source {
            DataSource::Nws => self.run_nws(settings, location, &mut outcome),
            DataSource::OpenMeteo => {
                let mut c = OpenMeteoClient::new(self.http.as_ref());
                if let Some(b) = &self.openmeteo_base {
                    c = c.with_base(b);
                }
                c.fetch(location, settings.forecast_days(), settings.hourly_hours())
                    .map(|b| outcome.bundle = b)
            }
            DataSource::PirateWeather => {
                let mut c =
                    PirateWeatherClient::new(self.http.as_ref(), &settings.pirate_weather_api_key);
                if let Some(b) = &self.pirate_base {
                    c = c.with_base(b);
                }
                c.fetch(location).map(|b| outcome.bundle = b)
            }
        };
        if let Err(e) = result {
            tracing::warn!("{} fetch failed: {e}", source.display_name());
            outcome.error = Some(e.to_string());
        }
        outcome
    }

    fn run_nws(
        &self,
        settings: &AppSettings,
        location: &Location,
        outcome: &mut FetchOutcome,
    ) -> Result<(), crate::http::HttpError> {
        let mut nws = NwsClient::new(self.http.as_ref());
        if let Some(b) = &self.nws_base {
            nws = nws.with_base(b);
        }
        let point = nws.points(location)?;
        outcome.bundle.current = nws.current_conditions(&point).unwrap_or_else(|e| {
            tracing::warn!("NWS observations failed: {e}");
            None
        });
        outcome.bundle.forecast = nws.forecast(&point)?;
        outcome.bundle.hourly = nws.hourly_forecast(&point).unwrap_or_else(|e| {
            tracing::warn!("NWS hourly failed: {e}");
            None
        });
        if settings.enable_alerts {
            outcome.alerts = nws.alerts(location).ok();
        }
        outcome.discussion = nws.discussion(&point).unwrap_or(None);
        outcome.location_metadata = Some(point);
        Ok(())
    }
}

fn merged_is_complete(outcomes: &[FetchOutcome]) -> bool {
    let has_current = outcomes
        .iter()
        .any(|o| o.bundle.current.as_ref().is_some_and(|c| c.has_data()));
    let has_forecast = outcomes
        .iter()
        .any(|o| o.bundle.forecast.as_ref().is_some_and(|f| f.has_data()));
    has_current && has_forecast
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    fn openmeteo_fixture() -> serde_json::Value {
        json!({
            "utc_offset_seconds": 0,
            "current": {"time": "2026-01-01T12:00", "temperature_2m": 50.0, "weather_code": 1},
            "daily": {"time": ["2026-01-01"], "weather_code": [1],
                "temperature_2m_max": [55.0], "temperature_2m_min": [35.0]},
            "hourly": {"time": ["2099-01-01T12:00"], "temperature_2m": [50.0]}
        })
    }

    #[test]
    fn international_location_uses_open_meteo_only() {
        let http =
            Arc::new(FixtureClient::new().with(crate::openmeteo::BASE_URL, openmeteo_fixture()));
        let client = WeatherClient::new(http.clone());
        let settings = AppSettings::default();
        let loc = Location::new("London", 51.5, -0.12).with_country("GB");
        let data = client.fetch(&settings, &loc);
        assert_eq!(data.sources, vec!["openmeteo"]);
        assert!(data.failed_sources.is_empty());
        assert_eq!(
            data.current.unwrap().condition.as_deref(),
            Some("Mainly clear")
        );
        assert!(http
            .request_log()
            .iter()
            .all(|u| u.starts_with(crate::openmeteo::BASE_URL)));
    }

    #[test]
    fn nws_failure_falls_back_to_open_meteo() {
        let http =
            Arc::new(FixtureClient::new().with(crate::openmeteo::BASE_URL, openmeteo_fixture()));
        let client = WeatherClient::new(http);
        let settings = AppSettings {
            data_source: "nws".into(),
            ..AppSettings::default()
        };
        let loc = Location::new("Philly", 39.95, -75.16).with_country("US");
        let data = client.fetch(&settings, &loc);
        assert!(data.sources.contains(&"openmeteo".to_string()));
        assert_eq!(data.failed_sources.len(), 1);
        assert_eq!(data.failed_sources[0].0, "nws");
        assert!(data.forecast.is_some());
    }
}
