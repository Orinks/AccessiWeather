//! Forecast source selection for data fusion.
//! Port of `accessiweather/weather_client_fusion_forecasts.py`.

use std::collections::BTreeMap;

use chrono::Duration;

use crate::location::is_us_location;
use crate::model::{
    Forecast, HourlyForecast, HourlyForecastPeriod, Location, SourceData, Timestamp,
};

use super::source_priority_index;

/// Pick the first source (in `preferred` order, then input order) from `valid`.
fn select<'a>(valid: &[&'a SourceData], preferred: &[&str]) -> &'a SourceData {
    preferred
        .iter()
        .find_map(|name| valid.iter().find(|s| s.source == *name))
        .unwrap_or(&valid[0])
}

/// `merge_forecasts`: select the daily forecast from a single source.
///
/// US: NWS, then Open-Meteo, then Pirate Weather (Open-Meteo first when more
/// than 7 days were requested). Elsewhere: Open-Meteo, then Pirate Weather.
/// Pirate Weather's block summary is kept when another source wins.
pub fn merge_forecasts(
    sources: &[SourceData],
    location: &Location,
    requested_days: i64,
) -> (Option<Forecast>, BTreeMap<String, String>) {
    let mut field_sources = BTreeMap::new();
    let valid: Vec<&SourceData> = sources
        .iter()
        .filter(|s| s.success && s.forecast.is_some())
        .collect();
    if valid.is_empty() {
        return (None, field_sources);
    }
    let preferred: &[&str] = if is_us_location(location) {
        if requested_days > 7 {
            &["openmeteo", "nws", "pirateweather"]
        } else {
            &["nws", "openmeteo", "pirateweather"]
        }
    } else {
        &["openmeteo", "pirateweather"]
    };
    let selected = select(&valid, preferred);
    let mut forecast = selected.forecast.clone().expect("filtered on forecast");
    let pirate_summary = valid
        .iter()
        .find(|s| s.source == "pirateweather")
        .and_then(|s| s.forecast.as_ref())
        .and_then(|f| f.summary.clone())
        .filter(|s| !s.is_empty());
    if forecast.summary.is_none() && pirate_summary.is_some() {
        forecast.summary = pirate_summary.clone();
    }
    field_sources.insert("forecast_source".into(), selected.source.clone());
    if pirate_summary.is_some() && forecast.summary == pirate_summary {
        field_sources.insert("forecast_summary".into(), "pirateweather".into());
    }
    (Some(forecast), field_sources)
}

/// `merge_hourly_forecasts`: select the hourly forecast from a single source
/// (mixing sources breaks timezone display), then borrow pressure from another
/// source when the chosen one has none.
pub fn merge_hourly_forecasts(
    sources: &[SourceData],
    location: &Location,
) -> (Option<HourlyForecast>, BTreeMap<String, String>) {
    let mut field_sources = BTreeMap::new();
    let valid: Vec<&SourceData> = sources
        .iter()
        .filter(|s| s.success && s.hourly_forecast.is_some())
        .collect();
    if valid.is_empty() {
        return (None, field_sources);
    }
    let preferred: &[&str] = if is_us_location(location) {
        &["nws", "openmeteo", "pirateweather"]
    } else {
        &["openmeteo", "pirateweather"]
    };
    let selected = select(&valid, preferred);
    let mut hourly = selected
        .hourly_forecast
        .clone()
        .expect("filtered on hourly");
    let pirate_summary = valid
        .iter()
        .find(|s| s.source == "pirateweather")
        .and_then(|s| s.hourly_forecast.as_ref())
        .and_then(|h| h.summary.clone())
        .filter(|s| !s.is_empty());
    if hourly.summary.is_none() && pirate_summary.is_some() {
        hourly.summary = pirate_summary.clone();
    }

    if let Some(pressure_source) = select_hourly_pressure_source(&valid, selected) {
        if pressure_source.source != selected.source {
            let pressure_hourly = pressure_source.hourly_forecast.as_ref().expect("filtered");
            if let Some(overlaid) = overlay_hourly_pressure(&hourly, pressure_hourly) {
                hourly = overlaid;
                field_sources.insert(
                    "hourly_pressure_source".into(),
                    pressure_source.source.clone(),
                );
            }
        }
    }

    field_sources.insert("hourly_source".into(), selected.source.clone());
    if pirate_summary.is_some() && hourly.summary == pirate_summary {
        field_sources.insert("hourly_summary".into(), "pirateweather".into());
    }
    (Some(hourly), field_sources)
}

/// The selected source when it has hourly pressure, else the best other
/// source that does (Open-Meteo before Pirate Weather).
pub fn select_hourly_pressure_source<'a>(
    valid: &[&'a SourceData],
    selected: &'a SourceData,
) -> Option<&'a SourceData> {
    if hourly_has_pressure(selected.hourly_forecast.as_ref()) {
        return Some(selected);
    }
    let priority = ["openmeteo".to_string(), "pirateweather".to_string()];
    let mut with_pressure: Vec<&SourceData> = valid
        .iter()
        .copied()
        .filter(|s| hourly_has_pressure(s.hourly_forecast.as_ref()))
        .collect();
    with_pressure.sort_by_key(|s| source_priority_index(&s.source, &priority));
    with_pressure.first().copied()
}

pub fn hourly_has_pressure(hourly: Option<&HourlyForecast>) -> bool {
    hourly.is_some_and(|h| h.periods.iter().any(has_pressure))
}

fn has_pressure(p: &HourlyForecastPeriod) -> bool {
    p.pressure_in.is_some() || p.pressure_mb.is_some()
}

/// Copy pressure from the nearest pressure-bearing period (within 90 min)
/// into display periods that lack it. `None` when nothing changed.
pub fn overlay_hourly_pressure(
    display: &HourlyForecast,
    pressure: &HourlyForecast,
) -> Option<HourlyForecast> {
    let pressure_periods: Vec<&HourlyForecastPeriod> = pressure
        .periods
        .iter()
        .filter(|p| has_pressure(p))
        .collect();
    if pressure_periods.is_empty() {
        return None;
    }
    let mut changed = false;
    let periods = display
        .periods
        .iter()
        .map(|period| {
            if has_pressure(period) {
                return period.clone();
            }
            match nearest_hourly_pressure_period(period.start_time, &pressure_periods) {
                Some(source) => {
                    changed = true;
                    HourlyForecastPeriod {
                        pressure_in: source.pressure_in,
                        pressure_mb: source.pressure_mb,
                        ..period.clone()
                    }
                }
                None => period.clone(),
            }
        })
        .collect();
    changed.then(|| HourlyForecast {
        periods,
        ..display.clone()
    })
}

pub fn nearest_hourly_pressure_period<'a>(
    target: Timestamp,
    pressure_periods: &[&'a HourlyForecastPeriod],
) -> Option<&'a HourlyForecastPeriod> {
    let mut best: Option<(&HourlyForecastPeriod, Duration)> = None;
    for period in pressure_periods {
        let delta = (period.start_time - target).abs();
        if best.is_none_or(|(_, d)| delta < d) {
            best = Some((period, delta));
        }
    }
    best.filter(|(_, d)| *d <= Duration::minutes(90))
        .map(|(p, _)| p)
}
