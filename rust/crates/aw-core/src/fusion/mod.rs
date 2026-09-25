//! Data fusion engine for merging weather data from multiple sources.
//! Port of `accessiweather/weather_client_fusion.py` (plus
//! `config/source_priority.py`).
//!
//! Current conditions are merged field by field on a JSON map, exactly like
//! Python's `merged_values` dict, then rebuilt into `CurrentConditions`.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use crate::location::is_us_location;
use crate::model::{
    CurrentConditions, Forecast, HourlyForecast, Location, SourceAttribution, SourceData,
};

pub mod forecasts;
pub mod values;

use values::{GroupValues, KM_PER_MILE};

const MISSING_CONDITION_TEXT: &[&str] = &[
    "",
    "n/a",
    "na",
    "none",
    "not available",
    "null",
    "unavailable",
    "unknown",
    "--",
];

fn us_default() -> Vec<String> {
    vec!["nws".into(), "openmeteo".into(), "pirateweather".into()]
}

fn international_default() -> Vec<String> {
    vec!["openmeteo".into(), "pirateweather".into()]
}

/// `SourcePriorityConfig`: which source wins each field.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct SourcePriorityConfig {
    pub us_default: Vec<String>,
    pub international_default: Vec<String>,
    /// Per-field overrides (field name -> priority list).
    pub field_priorities: BTreeMap<String, Vec<String>>,
    /// Conflict threshold for temperature (°F).
    pub temperature_conflict_threshold: f64,
}

impl Default for SourcePriorityConfig {
    fn default() -> Self {
        Self {
            us_default: us_default(),
            international_default: international_default(),
            field_priorities: BTreeMap::new(),
            temperature_conflict_threshold: 5.0,
        }
    }
}

impl SourcePriorityConfig {
    pub fn get_priority(&self, field_name: &str, is_us: bool) -> &[String] {
        if let Some(list) = self.field_priorities.get(field_name) {
            return list;
        }
        if is_us {
            &self.us_default
        } else {
            &self.international_default
        }
    }
}

pub(crate) fn source_priority_index(source: &str, priority: &[String]) -> usize {
    priority
        .iter()
        .position(|p| p == source)
        .unwrap_or(priority.len())
}

fn field_value_is_present(field: &str, value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::String(s) => {
            let normalized = s.trim();
            !normalized.is_empty()
                && !(field == "condition"
                    && MISSING_CONDITION_TEXT.contains(&normalized.to_lowercase().as_str()))
        }
        _ => true,
    }
}

fn to_map(current: &CurrentConditions) -> Map<String, Value> {
    match serde_json::to_value(current) {
        Ok(Value::Object(map)) => map,
        _ => Map::new(),
    }
}

/// A valid source together with its current conditions as a field map.
struct Candidate<'a> {
    source: &'a SourceData,
    current: &'a CurrentConditions,
    fields: Map<String, Value>,
}

impl Candidate<'_> {
    fn has_any(&self, names: &[&str]) -> bool {
        names
            .iter()
            .any(|n| field_value_is_present(n, self.fields.get(*n).unwrap_or(&Value::Null)))
    }
}

/// Merges weather data from multiple sources using configurable priorities.
#[derive(Debug, Clone, Default)]
pub struct DataFusionEngine {
    pub config: SourcePriorityConfig,
}

impl DataFusionEngine {
    pub fn new(config: SourcePriorityConfig) -> Self {
        Self { config }
    }

    /// Merge current conditions field by field, keeping each semantic
    /// reading (temperature, wind, pressure, ...) from a single source.
    pub fn merge_current_conditions(
        &self,
        sources: &[SourceData],
        location: &Location,
    ) -> (Option<CurrentConditions>, SourceAttribution) {
        let mut attribution = SourceAttribution::default();
        let is_us = is_us_location(location);

        let mut valid: Vec<Candidate> = sources
            .iter()
            .filter(|s| s.success)
            .filter_map(|s| {
                s.current.as_ref().map(|c| Candidate {
                    source: s,
                    current: c,
                    fields: to_map(c),
                })
            })
            .collect();
        if valid.is_empty() {
            return (None, attribution);
        }
        let priority = self
            .config
            .get_priority("current_conditions", is_us)
            .to_vec();
        valid.sort_by_key(|c| source_priority_index(&c.source.source, &priority));

        for c in &valid {
            attribution
                .contributing_sources
                .insert(c.source.source.clone());
        }
        for s in sources.iter().filter(|s| !s.success) {
            attribution.failed_sources.insert(s.source.clone());
        }

        let mut merged = Map::new();
        for field in to_map(&CurrentConditions::default()).keys() {
            let field_priority = self.config.get_priority(field, is_us);
            let mut order: Vec<&Candidate> = valid.iter().collect();
            order.sort_by_key(|c| source_priority_index(&c.source.source, field_priority));
            for c in order {
                let value = c.fields.get(field).unwrap_or(&Value::Null);
                if field_value_is_present(field, value) {
                    merged.insert(field.clone(), value.clone());
                    attribution
                        .field_sources
                        .insert(field.clone(), c.source.source.clone());
                    break;
                }
            }
        }

        self.apply_semantic_group_selections(&valid, &mut merged, &mut attribution, is_us);

        let sorted_sources: Vec<&SourceData> = valid.iter().map(|c| c.source).collect();
        values::check_temperature_conflicts(
            &sorted_sources,
            &mut merged,
            &mut attribution,
            self.config.temperature_conflict_threshold,
            |field| self.config.get_priority(field, is_us).to_vec(),
        );

        // For US locations only NWS station observations are trusted for
        // snow depth; model snowpack (ERA5/GFS) can be badly wrong.
        if is_us {
            let snow_source = attribution.field_sources.get("snow_depth_in").cloned();
            if snow_source.is_some_and(|s| s != "nws") {
                for field in ["snow_depth_in", "snow_depth_cm"] {
                    merged.shift_remove(field);
                    attribution.field_sources.remove(field);
                }
            }
        }

        let mut current: CurrentConditions =
            serde_json::from_value(Value::Object(merged)).unwrap_or_default();
        current.backfill();
        (Some(current), attribution)
    }

    fn apply_semantic_group_selections(
        &self,
        valid: &[Candidate],
        merged: &mut Map<String, Value>,
        attribution: &mut SourceAttribution,
        is_us: bool,
    ) {
        type Builder = fn(&CurrentConditions) -> GroupValues;
        let group = |priority_field: &str,
                     names: &[&str],
                     builder: Builder,
                     merged: &mut Map<String, Value>,
                     attribution: &mut SourceAttribution| {
            let field_priority = self.config.get_priority(priority_field, is_us);
            let mut order: Vec<&Candidate> = valid.iter().collect();
            order.sort_by_key(|c| source_priority_index(&c.source.source, field_priority));
            if let Some(c) = order.into_iter().find(|c| c.has_any(names)) {
                set_group_values(builder(c.current), merged, attribution, &c.source.source);
            }
        };

        group(
            "temperature",
            &["temperature", "temperature_f", "temperature_c"],
            values::temperature_values,
            merged,
            attribution,
        );
        group(
            "dewpoint_f",
            &["dewpoint_f", "dewpoint_c"],
            values::dewpoint_values,
            merged,
            attribution,
        );
        group(
            "wind_speed",
            &["wind_speed", "wind_speed_mph", "wind_speed_kph"],
            values::speed_values,
            merged,
            attribution,
        );
        group(
            "pressure",
            &["pressure", "pressure_in", "pressure_mb"],
            values::pressure_values,
            merged,
            attribution,
        );
        group(
            "feels_like_f",
            &["feels_like_f", "feels_like_c"],
            values::feels_like_values,
            merged,
            attribution,
        );
        apply_visibility_selection(valid, merged, attribution);
        group(
            "wind_gust_mph",
            &["wind_gust_mph", "wind_gust_kph"],
            values::wind_gust_values,
            merged,
            attribution,
        );
        values::discard_gust_if_below_wind_speed(merged, attribution);
        group(
            "precipitation_in",
            &["precipitation_in", "precipitation_mm"],
            values::precipitation_values,
            merged,
            attribution,
        );
        group(
            "snow_depth_in",
            &["snow_depth_in", "snow_depth_cm"],
            values::snow_depth_values,
            merged,
            attribution,
        );
        group(
            "wind_chill_f",
            &["wind_chill_f", "wind_chill_c"],
            values::wind_chill_values,
            merged,
            attribution,
        );
        group(
            "freezing_level_ft",
            &["freezing_level_ft", "freezing_level_m"],
            values::freezing_level_values,
            merged,
            attribution,
        );
        group(
            "heat_index_f",
            &["heat_index_f", "heat_index_c"],
            values::heat_index_values,
            merged,
            attribution,
        );
        values::sanitize_thermal_comfort_values(merged, attribution);
    }

    /// Select the daily forecast from a single source based on location.
    pub fn merge_forecasts(
        &self,
        sources: &[SourceData],
        location: &Location,
        requested_days: i64,
    ) -> (Option<Forecast>, BTreeMap<String, String>) {
        forecasts::merge_forecasts(sources, location, requested_days)
    }

    /// Select the hourly forecast from a single source based on location.
    pub fn merge_hourly_forecasts(
        &self,
        sources: &[SourceData],
        location: &Location,
    ) -> (Option<HourlyForecast>, BTreeMap<String, String>) {
        forecasts::merge_hourly_forecasts(sources, location)
    }
}

fn set_group_values(
    values: GroupValues,
    merged: &mut Map<String, Value>,
    attribution: &mut SourceAttribution,
    source: &str,
) {
    for (field, value) in values {
        match value {
            Some(v) => {
                merged.insert(field.to_string(), Value::from(v));
                attribution
                    .field_sources
                    .insert(field.to_string(), source.to_string());
            }
            None => {
                merged.shift_remove(field);
                attribution.field_sources.remove(field);
            }
        }
    }
}

/// Visibility comes whole from the highest-priority source that reports it.
fn apply_visibility_selection(
    valid: &[Candidate],
    merged: &mut Map<String, Value>,
    attribution: &mut SourceAttribution,
) {
    let Some(best) = valid
        .iter()
        .find(|c| c.current.visibility_miles.is_some() || c.current.visibility_km.is_some())
    else {
        return;
    };
    let mut miles = best.current.visibility_miles;
    let mut km = best.current.visibility_km;
    if miles.is_none() {
        miles = km.map(|k| k / KM_PER_MILE);
    }
    if km.is_none() {
        km = miles.map(|m| m * KM_PER_MILE);
    }
    set_group_values(
        vec![("visibility_miles", miles), ("visibility_km", km)],
        merged,
        attribution,
        &best.source.source,
    );
}

#[cfg(test)]
mod tests;
