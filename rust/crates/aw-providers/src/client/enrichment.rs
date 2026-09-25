//! Post-fetch enrichment: sunrise/sunset, NWS discussion, environmental,
//! aviation and marine data, then trend insights. Port of
//! `accessiweather/weather_client_enrichment.py` and
//! `_launch_enrichment_tasks` / `_await_enrichments` in
//! `weather_client_auto.py`.
//!
//! The enrichments fetch concurrently and their results are applied once all
//! have finished; a failed enrichment is logged and skipped.

use std::collections::BTreeSet;
use std::thread::ScopedJoinHandle;

use aw_core::model::{
    AviationData, CurrentConditions, EnvironmentalConditions, Location, MarineForecast,
    MarineForecastPeriod, Timestamp, WeatherAlert, WeatherAlerts, WeatherData,
};
use aw_core::trends::apply_trend_insights;
use serde_json::Value;

use super::auto::should_enrich_nws_discussion;
use super::sources::{AviationOptions, SourceResult};
use super::WeatherClient;

/// `_get_uv_category` (EPA/WHO bands).
pub fn uv_category(uv_index: f64) -> &'static str {
    if uv_index <= 2.0 {
        "Low"
    } else if uv_index <= 5.0 {
        "Moderate"
    } else if uv_index <= 7.0 {
        "High"
    } else if uv_index <= 10.0 {
        "Very High"
    } else {
        "Extreme"
    }
}

const MARINE_KEYWORDS: [&str; 9] = [
    "wind", "winds", "gust", "gusts", "wave", "waves", "seas", "swell", "swells",
];

/// `_MARINE_HIGHLIGHT_PATTERN.findall`: every `.`/`;`-delimited clause that
/// contains one of the wind/wave keywords as a whole word.
fn highlight_clauses(text: &str) -> Vec<&str> {
    text.split(['.', ';'])
        .filter(|clause| {
            clause
                .split(|c: char| !(c.is_alphanumeric() || c == '_'))
                .any(|word| {
                    !word.is_empty() && MARINE_KEYWORDS.contains(&word.to_lowercase().as_str())
                })
        })
        .collect()
}

/// `_build_marine_highlights`: up to four distinct wind/wave clauses.
pub fn build_marine_highlights(periods: &[Value]) -> Vec<String> {
    let mut highlights = Vec::new();
    let mut seen = BTreeSet::new();
    for period in periods {
        for field in ["shortForecast", "detailedForecast"] {
            let text = json_text(period.get(field));
            let text = text.trim();
            if text.is_empty() {
                continue;
            }
            for clause in highlight_clauses(text) {
                let candidate = clause.split_whitespace().collect::<Vec<_>>().join(" ");
                let candidate = candidate.trim_matches(|c| c == ' ' || c == '.');
                if candidate.is_empty() || !seen.insert(candidate.to_lowercase()) {
                    continue;
                }
                highlights.push(candidate.to_string());
                if highlights.len() >= 4 {
                    return highlights;
                }
            }
        }
    }
    highlights
}

/// `str(value or "")` for JSON values.
fn json_text(value: Option<&Value>) -> String {
    match value {
        None => String::new(),
        Some(v) if is_falsy(v) => String::new(),
        Some(Value::String(s)) => s.clone(),
        Some(Value::Bool(true)) => "True".into(),
        Some(v) => v.to_string(),
    }
}

fn is_falsy(value: &Value) -> bool {
    match value {
        Value::Null => true,
        Value::Bool(b) => !b,
        Value::Number(n) => n.as_f64() == Some(0.0),
        Value::String(s) => s.is_empty(),
        Value::Array(a) => a.is_empty(),
        Value::Object(o) => o.is_empty(),
    }
}

/// `period.get("detailedForecast") or period.get("shortForecast")`.
fn period_text(period: &Value) -> Option<&Value> {
    ["detailedForecast", "shortForecast"]
        .iter()
        .filter_map(|k| period.get(*k))
        .find(|v| !is_falsy(v))
}

/// `_parse_marine_issued_at`.
fn parse_issued_at(value: Option<&Value>) -> Option<Timestamp> {
    let text = value?.as_str().filter(|s| !s.is_empty())?;
    let text = text.replace('Z', "+00:00");
    chrono::DateTime::parse_from_rfc3339(&text)
        .ok()
        .or_else(|| {
            chrono::NaiveDateTime::parse_from_str(&text, "%Y-%m-%dT%H:%M:%S%.f")
                .ok()
                .and_then(|n| n.and_local_timezone(chrono::Local).earliest())
                .map(|d| d.fixed_offset())
        })
}

/// The first marine zone's id and properties from the `/zones` lookup.
fn marine_zone(zones: &Value) -> Option<(String, Option<&Value>)> {
    let feature = zones.get("features")?.as_array()?.first()?;
    let properties = feature.get("properties");
    let id = properties
        .and_then(|p| p.get("id"))
        .filter(|v| !is_falsy(v))
        .or_else(|| feature.get("id").filter(|v| !is_falsy(v)))?;
    Some((json_text(Some(id)), properties))
}

/// Build the marine summary for `zone_id` from its forecast JSON.
pub fn build_marine_forecast(
    zone_id: &str,
    zone_properties: Option<&Value>,
    forecast: &Value,
) -> MarineForecast {
    let properties = forecast.get("properties");
    let periods: Vec<Value> = properties
        .and_then(|p| p.get("periods"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    MarineForecast {
        zone_id: Some(zone_id.to_string()),
        zone_name: properties
            .and_then(|p| p.get("name"))
            .filter(|v| !is_falsy(v))
            .or_else(|| zone_properties.and_then(|p| p.get("name")))
            .and_then(Value::as_str)
            .map(str::to_string),
        // Python's str() of a missing text is "None".
        forecast_summary: periods.first().map(|p| match period_text(p) {
            Some(text) => json_text(Some(text)),
            None => "None".to_string(),
        }),
        issued_at: parse_issued_at(properties.and_then(|p| p.get("updateTime"))),
        periods: periods
            .iter()
            .take(3)
            .filter_map(|p| {
                let text = period_text(p)?;
                let name = json_text(p.get("name").filter(|v| !is_falsy(v)));
                Some(MarineForecastPeriod {
                    name: if name.is_empty() {
                        "Marine period".into()
                    } else {
                        name
                    },
                    summary: json_text(Some(text)).trim().to_string(),
                })
            })
            .collect(),
        highlights: build_marine_highlights(&periods[..periods.len().min(4)]),
    }
}

/// Results of one enrichment round, applied after all fetches finish.
#[derive(Default)]
struct Enrichments {
    sun: Option<CurrentConditions>,
    discussion: Option<(String, Option<Timestamp>)>,
    environmental: Option<EnvironmentalConditions>,
    aviation: Option<AviationData>,
    marine: Option<(Option<MarineForecast>, WeatherAlerts)>,
}

/// Wait for an enrichment; failures are logged and skipped.
fn joined<T>(name: &str, handle: Option<ScopedJoinHandle<'_, SourceResult<T>>>) -> Option<T> {
    match handle?.join() {
        Ok(Ok(value)) => Some(value),
        Ok(Err(e)) => {
            tracing::debug!("Enrichment '{name}' failed: {e}");
            None
        }
        Err(_) => {
            tracing::debug!("Enrichment '{name}' panicked");
            None
        }
    }
}

impl WeatherClient {
    /// `_launch_enrichment_tasks` + `_await_enrichments`: enrich, apply trend
    /// insights, then remember and cache the result.
    pub(super) fn run_enrichments(&self, weather: &mut WeatherData, location: &Location) {
        let auto = self.data_source == "auto";
        let is_us = self.is_us(location);
        let want_sun = auto && weather.current.is_some();
        let want_discussion = auto && is_us && should_enrich_nws_discussion(weather);
        let air_quality = self.settings.air_quality_enabled;
        let pollen = self.settings.pollen_enabled;

        let results = std::thread::scope(|scope| {
            let sun = want_sun
                .then(|| scope.spawn(|| self.sources.openmeteo.get_current_conditions(location)));
            let discussion = want_discussion
                .then(|| scope.spawn(|| self.sources.nws.get_forecast_and_discussion(location)));
            let environmental = self
                .sources
                .environmental
                .as_ref()
                .filter(|_| air_quality || pollen)
                .map(|env| {
                    scope.spawn(move || {
                        env.fetch(
                            location,
                            air_quality,
                            pollen,
                            air_quality,
                            air_quality && is_us,
                        )
                    })
                });
            let aviation = is_us.then(|| scope.spawn(|| self.fetch_aviation(location)));
            let marine = (location.marine_mode && is_us)
                .then(|| scope.spawn(|| self.fetch_marine(location)));

            Enrichments {
                sun: joined("sunrise_sunset", sun).flatten(),
                discussion: joined("nws_discussion", discussion)
                    .and_then(|(_, text, time)| text.filter(|t| !t.is_empty()).map(|t| (t, time))),
                environmental: joined("environmental", environmental).flatten(),
                aviation: joined("aviation", aviation).flatten(),
                marine: joined("marine", marine).flatten(),
            }
        });
        self.apply_enrichments(weather, results);

        apply_trend_insights(
            weather,
            self.settings.trend_insights_enabled,
            self.trend_hours(),
            self.settings.show_pressure_trend,
            self.now(),
        );
        self.persist_weather_data(&weather.location.clone(), weather);
    }

    fn apply_enrichments(&self, weather: &mut WeatherData, results: Enrichments) {
        if let (Some(sun), Some(current)) = (results.sun, weather.current.as_mut()) {
            if sun.sunrise_time.is_some() {
                current.sunrise_time = sun.sunrise_time;
            }
            if sun.sunset_time.is_some() {
                current.sunset_time = sun.sunset_time;
            }
        }
        if let Some((text, time)) = results.discussion {
            weather.discussion = Some(text);
            weather.discussion_issuance_time = time;
        }
        if let Some(mut environmental) = results.environmental {
            if let Some(uv) = weather.current.as_ref().and_then(|c| c.uv_index) {
                environmental.uv_index = Some(uv);
                environmental.uv_category = Some(uv_category(uv).into());
            }
            weather.environmental = Some(environmental);
        }
        if let Some(aviation) = results.aviation {
            weather.aviation = Some(aviation);
        }
        if let Some((marine, marine_alerts)) = results.marine {
            if let Some(marine) = marine {
                weather.marine = Some(marine);
            }
            if !marine_alerts.alerts.is_empty() {
                weather.alerts = Some(merge_marine_alerts(weather.alerts.take(), marine_alerts));
            }
        }
    }

    /// `enrich_with_aviation_data`: TAF for the location's primary station.
    fn fetch_aviation(&self, location: &Location) -> SourceResult<Option<AviationData>> {
        let (station_id, station_name) = self.sources.aviation.primary_station_info(location)?;
        let Some(station_id) = station_id.filter(|s| !s.is_empty()) else {
            return Ok(None);
        };
        let mut aviation = self.get_aviation_weather(&station_id, &AviationOptions::default())?;
        if let Some(name) = station_name.filter(|n| !n.is_empty()) {
            aviation.airport_name = Some(name);
        }
        Ok(Some(aviation))
    }

    /// `enrich_with_marine_data`: zone forecast summary and marine alerts.
    fn fetch_marine(
        &self,
        location: &Location,
    ) -> SourceResult<Option<(Option<MarineForecast>, WeatherAlerts)>> {
        let zones = self.sources.marine.marine_zones(location)?;
        let Some((zone_id, zone_properties)) = marine_zone(&zones) else {
            return Ok(None);
        };
        let Some(forecast) = self
            .sources
            .marine
            .marine_forecast(&zone_id)?
            .filter(|f| !is_falsy(f))
        else {
            return Ok(None);
        };
        let marine = Some(build_marine_forecast(&zone_id, zone_properties, &forecast))
            .filter(MarineForecast::has_data);
        // Python sets the forecast before requesting alerts, so an alerts
        // failure keeps the forecast.
        let alerts = match self.sources.marine.marine_alerts(&zone_id) {
            Ok(alerts) => alerts,
            Err(e) => {
                tracing::debug!(
                    "Failed to fetch marine essentials for {}: {e}",
                    location.name
                );
                WeatherAlerts::default()
            }
        };
        Ok(Some((marine, alerts)))
    }
}

/// Add marine alerts (tagged "NWS Marine") to the existing alerts, keeping
/// existing ones when the unique id collides.
fn merge_marine_alerts(existing: Option<WeatherAlerts>, marine: WeatherAlerts) -> WeatherAlerts {
    let mut merged: Vec<(String, WeatherAlert)> = Vec::new();
    for alert in existing.map(|a| a.alerts).unwrap_or_default() {
        let id = alert.unique_id();
        match merged.iter_mut().find(|(k, _)| *k == id) {
            Some(slot) => slot.1 = alert,
            None => merged.push((id, alert)),
        }
    }
    for mut alert in marine.alerts {
        alert.source = Some("NWS Marine".into());
        let id = alert.unique_id();
        if !merged.iter().any(|(k, _)| *k == id) {
            merged.push((id, alert));
        }
    }
    WeatherAlerts {
        alerts: merged.into_iter().map(|(_, a)| a).collect(),
    }
}
