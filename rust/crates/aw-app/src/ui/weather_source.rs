//! Adapter between the main window and today's data path
//! (`WeatherClient::fetch` + the legacy `aw_core::presenter`).
//!
//! The window only sees Python-shaped values: `aw_core::model::WeatherData`
//! and the `WeatherPresentation` fields below (named as in
//! `display/presentation/models.py`). Swapping in
//! `aw_core::display::WeatherPresenter` and a client that returns model data
//! only touches this file; the location search helpers at the bottom stand in
//! for the `location_manager.py` / `current_location.py` port the same way.

use std::cell::RefCell;
use std::collections::HashMap;

use aw_core::model::{self, WeatherData};
use aw_core::presenter::WeatherPresenter;
use aw_core::settings::AppSettings;
use aw_core::weather as legacy;
use aw_core::Location;
use aw_providers::geocoding::Geocoder;
use aw_providers::{HttpClient, WeatherClient};
use serde::Deserialize;

use crate::app::State;

/// The parts of Python's `WeatherPresentation` the main window reads.
#[derive(Debug, Default, Deserialize)]
pub(crate) struct WeatherPresentation {
    pub current_conditions: Option<CurrentConditionsPresentation>,
    pub forecast: Option<ForecastPresentation>,
    #[serde(default)]
    pub status_messages: Vec<String>,
    pub source_attribution: Option<SourceAttributionPresentation>,
}

#[derive(Debug, Default, Deserialize)]
pub(crate) struct CurrentConditionsPresentation {
    pub fallback_text: String,
}

#[derive(Debug, Default, Deserialize)]
pub(crate) struct ForecastPresentation {
    pub daily_section_text: String,
    pub hourly_section_text: String,
    pub marine_section_text: String,
    pub mobility_briefing: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
pub(crate) struct SourceAttributionPresentation {
    pub summary_text: String,
}

/// One fetch result, produced on a worker thread.
pub(crate) struct Fetched(legacy::WeatherData);

/// `weather_client.get_weather_data` (blocking; call off the UI thread).
pub(crate) fn fetch(
    client: &WeatherClient,
    settings: &AppSettings,
    location: &Location,
) -> Fetched {
    Fetched(client.fetch(settings, location))
}

thread_local! {
    /// Stand-in for the weather client's offline cache, by location name.
    static CACHE: RefCell<HashMap<String, legacy::WeatherData>> = RefCell::new(HashMap::new());
}

/// Cache a fetch (UI thread), persist NWS zone metadata the fetch learned,
/// and return the data the window works with.
pub(crate) fn remember(st: &mut State, fetched: Fetched) -> WeatherData {
    let legacy = fetched.0;
    if let Some(saved) = st
        .config
        .locations
        .iter_mut()
        .find(|l| l.name == legacy.location.name)
    {
        if saved.forecast_zone_id.is_none() && legacy.location.forecast_zone_id.is_some() {
            *saved = legacy.location.clone();
            let saved = saved.clone();
            if let Some(current) = st.config.current_location.as_mut() {
                if current.name == saved.name {
                    *current = saved;
                }
            }
            let _ = crate::app::save(st);
        }
    }
    let data = to_model(&legacy);
    CACHE.with(|c| c.borrow_mut().insert(legacy.location.name.clone(), legacy));
    data
}

/// `weather_client.get_cached_weather`.
pub(crate) fn get_cached_weather(location: &Location) -> Option<WeatherData> {
    CACHE.with(|c| c.borrow().get(&location.name).map(to_model))
}

/// `app.presenter.present(weather_data)`.
pub(crate) fn present(settings: &AppSettings, data: &WeatherData) -> WeatherPresentation {
    let Some(p) = CACHE.with(|c| {
        c.borrow()
            .get(&data.location.name)
            .map(|legacy| WeatherPresenter::new(settings).present(legacy))
    }) else {
        return WeatherPresentation::default();
    };
    let has_forecast = data.forecast.is_some() || data.hourly_forecast.is_some();
    WeatherPresentation {
        current_conditions: data.current.as_ref().filter(|c| c.has_data()).map(|_| {
            CurrentConditionsPresentation {
                fallback_text: p.current_text,
            }
        }),
        forecast: has_forecast.then(|| ForecastPresentation {
            daily_section_text: p.daily_text,
            hourly_section_text: p.hourly_text,
            ..Default::default()
        }),
        status_messages: p.status_messages,
        source_attribution: None,
    }
}

/// Only the fields the main window reads are carried over.
fn to_model(legacy: &legacy::WeatherData) -> WeatherData {
    let mut data = WeatherData::new(legacy.location.clone());
    data.current = legacy.current.as_ref().map(|c| model::CurrentConditions {
        temperature_f: c.temperature_f,
        temperature_c: c.temperature_c,
        condition: c.condition.clone(),
        ..Default::default()
    });
    data.forecast = legacy.forecast.as_ref().map(|f| model::Forecast {
        periods: f
            .periods
            .iter()
            .map(|p| model::ForecastPeriod {
                name: p.name.clone(),
                temperature: p.temperature,
                short_forecast: p.short_forecast.clone(),
                ..Default::default()
            })
            .collect(),
        ..Default::default()
    });
    data.hourly_forecast = legacy
        .hourly_forecast
        .as_ref()
        .map(|h| model::HourlyForecast {
            periods: h
                .periods
                .iter()
                .map(|p| {
                    let mut period = model::HourlyForecastPeriod::new(p.start_time.fixed_offset());
                    period.temperature = p.temperature;
                    period.short_forecast = p.short_forecast.clone();
                    period
                })
                .collect(),
            ..Default::default()
        });
    data.alerts = legacy.alerts.as_ref().map(|a| model::WeatherAlerts {
        alerts: a.alerts.iter().map(to_model_alert).collect(),
    });
    data.discussion = legacy.discussion.clone();
    data.stale = legacy.stale;
    data.stale_reason = legacy.stale_reason.clone();
    data
}

fn to_model_alert(a: &aw_core::alerts::WeatherAlert) -> model::WeatherAlert {
    model::WeatherAlert {
        title: a.title.clone(),
        description: a.description.clone(),
        severity: a.severity.clone(),
        urgency: a.urgency.clone(),
        certainty: a.certainty.clone(),
        event: a.event.clone(),
        headline: a.headline.clone(),
        instruction: a.instruction.clone(),
        onset: a.onset.map(|t| t.fixed_offset()),
        expires: a.expires.map(|t| t.fixed_offset()),
        sent: a.sent.map(|t| t.fixed_offset()),
        effective: a.effective.map(|t| t.fixed_offset()),
        areas: a.areas.clone(),
        references: a.references.clone(),
        id: a.id.clone(),
        source: a.source.clone(),
        message_type: a.message_type.clone(),
        affected_zones: a.affected_zones.clone(),
        same_codes: a.same_codes.clone(),
        same_event_codes: a.same_event_codes.clone(),
    }
}

// ---------------------------------------------------------------------------
// Location search (`location_manager.py`, `current_location.py`)
// ---------------------------------------------------------------------------

/// `LocationManager.search_locations` (blocking).
pub(crate) fn search_locations(
    http: &dyn HttpClient,
    query: &str,
    limit: usize,
) -> Result<Vec<Location>, String> {
    Geocoder::new(http)
        .search(query, limit)
        .map(|found| found.into_iter().map(|r| r.location).collect())
        .map_err(|e| e.to_string())
}

/// `CurrentLocationService.detect_once` followed by reverse geocoding
/// (blocking). The native platform location call is not ported yet, so this
/// is Python's generic "unavailable" outcome.
pub(crate) fn detect_current_location(_http: &dyn HttpClient) -> Result<Location, String> {
    Err("Current location is unavailable. You can still search manually.".to_string())
}

/// `LocationManager.format_coordinates` (4 decimals).
pub(crate) fn format_coordinates(latitude: f64, longitude: f64) -> String {
    let lat_dir = if latitude >= 0.0 { "N" } else { "S" };
    let lon_dir = if longitude >= 0.0 { "E" } else { "W" };
    format!(
        "{:.4}°{lat_dir}, {:.4}°{lon_dir}",
        latitude.abs(),
        longitude.abs()
    )
}

/// `LocationManager.calculate_distance` in miles (haversine, R = 3959).
pub(crate) fn calculate_distance(a: &Location, b: &Location) -> f64 {
    let (lat1, lon1) = (a.latitude.to_radians(), a.longitude.to_radians());
    let (lat2, lon2) = (b.latitude.to_radians(), b.longitude.to_radians());
    let h = ((lat2 - lat1) / 2.0).sin().powi(2)
        + lat1.cos() * lat2.cos() * ((lon2 - lon1) / 2.0).sin().powi(2);
    3959.0 * 2.0 * h.sqrt().asin()
}

/// `LocationManager.validate_coordinates`.
pub(crate) fn validate_coordinates(latitude: f64, longitude: f64) -> bool {
    (-90.0..=90.0).contains(&latitude) && (-180.0..=180.0).contains(&longitude)
}
