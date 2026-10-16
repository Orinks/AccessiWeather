//! Weather data model, ported field-for-field from the Python app's
//! `accessiweather.models` (weather_core, weather_conditions,
//! weather_forecast, weather_data, alerts, text_product) plus the small
//! result types they reference (`alert_lifecycle`, `forecast_confidence`,
//! `weather_anomaly`).
//!
//! Field names match the Python dataclasses exactly, so JSON produced by
//! `dataclasses.asdict` on the Python side deserialises straight into these
//! types. That is what the golden parity tests rely on.

use std::collections::{BTreeMap, BTreeSet};

use chrono::{DateTime, FixedOffset, NaiveDateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub use crate::location::Location;

/// A point in time with the offset it was reported in (NWS and Open-Meteo
/// report local offsets, which the presentation layer relies on).
pub type Timestamp = DateTime<FixedOffset>;

/// A Python `datetime` that may be naive. The NWS and Open-Meteo parsers
/// stamp `generated_at` with a naive `datetime.now()` (local wall time),
/// Pirate Weather with an aware UTC now. The presenter shows a naive value
/// as it is; the mobility briefing and the offline cache read its wall time
/// as UTC (`replace(tzinfo=UTC)`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum PyTimestamp {
    Aware(Timestamp),
    Naive(NaiveDateTime),
}

impl PyTimestamp {
    /// Python's `dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)`.
    pub fn coerce_utc(&self) -> DateTime<Utc> {
        match self {
            PyTimestamp::Aware(t) => t.with_timezone(&Utc),
            PyTimestamp::Naive(wall) => wall.and_utc(),
        }
    }
}

// ---------------------------------------------------------------------------
// weather_core
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Season {
    Winter,
    Spring,
    Summer,
    Fall,
}

/// `get_hemisphere`: "northern" for latitude >= 0, else "southern".
pub fn hemisphere(latitude: f64) -> &'static str {
    if latitude >= 0.0 {
        "northern"
    } else {
        "southern"
    }
}

/// `get_season`: meteorological season by month, flipped south of the equator.
pub fn season(month: u32, latitude: f64) -> Season {
    let base = match month {
        12 | 1 | 2 => Season::Winter,
        3..=5 => Season::Spring,
        6..=8 => Season::Summer,
        _ => Season::Fall,
    };
    if hemisphere(latitude) == "southern" {
        match base {
            Season::Winter => Season::Summer,
            Season::Spring => Season::Fall,
            Season::Summer => Season::Winter,
            Season::Fall => Season::Spring,
        }
    } else {
        base
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DataConflict {
    pub field_name: String,
    /// source -> value
    pub values: BTreeMap<String, Value>,
    pub selected_source: String,
    pub selected_value: Value,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct SourceAttribution {
    /// Field name -> source name.
    pub field_sources: BTreeMap<String, String>,
    pub conflicts: Vec<DataConflict>,
    pub contributing_sources: BTreeSet<String>,
    pub failed_sources: BTreeSet<String>,
}

// ---------------------------------------------------------------------------
// weather_conditions
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct CurrentConditions {
    pub temperature: Option<f64>,
    pub temperature_f: Option<f64>,
    pub temperature_c: Option<f64>,
    pub condition: Option<String>,
    pub humidity: Option<i64>,
    pub wind_speed: Option<f64>,
    pub dewpoint_f: Option<f64>,
    pub dewpoint_c: Option<f64>,
    pub wind_speed_mph: Option<f64>,
    pub wind_speed_kph: Option<f64>,
    pub wind_direction: Option<WindDirection>,
    pub pressure: Option<f64>,
    pub pressure_in: Option<f64>,
    pub pressure_mb: Option<f64>,
    pub feels_like_f: Option<f64>,
    pub feels_like_c: Option<f64>,
    pub visibility_miles: Option<f64>,
    pub visibility_km: Option<f64>,
    pub uv_index: Option<f64>,
    /// Cloud cover percentage (0-100).
    pub cloud_cover: Option<f64>,
    pub wind_gust_mph: Option<f64>,
    pub wind_gust_kph: Option<f64>,
    pub precipitation_in: Option<f64>,
    pub precipitation_mm: Option<f64>,
    pub sunrise_time: Option<Timestamp>,
    pub sunset_time: Option<Timestamp>,
    pub moon_phase: Option<String>,
    pub moonrise_time: Option<Timestamp>,
    pub moonset_time: Option<Timestamp>,

    // Seasonal - winter
    pub snow_depth_in: Option<f64>,
    pub snow_depth_cm: Option<f64>,
    pub snowfall_rate_in: Option<f64>,
    pub wind_chill_f: Option<f64>,
    pub wind_chill_c: Option<f64>,
    pub freezing_level_ft: Option<f64>,
    pub freezing_level_m: Option<f64>,

    // Seasonal - summer
    pub heat_index_f: Option<f64>,
    pub heat_index_c: Option<f64>,

    // Seasonal - spring/fall: "None", "Low", "Moderate", "High"
    pub frost_risk: Option<String>,

    // Seasonal - year-round
    pub precipitation_type: Option<Vec<String>>,
    /// 0-100 scale.
    pub severe_weather_risk: Option<i64>,
}

/// `CurrentConditions.wind_direction` is typed `str` in Python but NWS
/// observations store the raw degrees (a number) there, and the display
/// layer branches on the type (`isinstance(..., int | float)` -> cardinal).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum WindDirection {
    Degrees(f64),
    Text(String),
}

impl WindDirection {
    /// What Python shows: degrees become a compass point, text is used as-is.
    pub fn display_text(&self) -> String {
        match self {
            WindDirection::Degrees(d) => {
                crate::display::units::convert_wind_direction_to_cardinal(*d).to_string()
            }
            WindDirection::Text(s) => s.clone(),
        }
    }
}

impl From<&str> for WindDirection {
    fn from(s: &str) -> Self {
        WindDirection::Text(s.to_string())
    }
}

impl From<String> for WindDirection {
    fn from(s: String) -> Self {
        WindDirection::Text(s)
    }
}

impl CurrentConditions {
    pub fn has_data(&self) -> bool {
        self.temperature.is_some()
            || self.temperature_f.is_some()
            || self.temperature_c.is_some()
            || self.condition.is_some()
    }

    /// `__post_init__`: backfill the unit-agnostic fields from unit-specific ones.
    pub fn backfill(&mut self) {
        if self.temperature.is_none() {
            self.temperature = self.temperature_f.or(self.temperature_c);
        }
        if self.wind_speed.is_none() {
            self.wind_speed = self.wind_speed_mph.or(self.wind_speed_kph);
        }
        if self.pressure.is_none() {
            self.pressure = self.pressure_in.or(self.pressure_mb);
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct EnvironmentalConditions {
    pub air_quality_index: Option<f64>,
    pub air_quality_category: Option<String>,
    pub air_quality_pollutant: Option<String>,
    pub air_quality_updated_at: Option<Timestamp>,
    pub air_quality_reporting_area: Option<String>,
    pub air_quality_source: Option<String>,
    pub hourly_air_quality: Vec<HourlyAirQuality>,
    pub uv_index: Option<f64>,
    pub uv_category: Option<String>,
    pub hourly_uv_index: Vec<HourlyUVIndex>,
    pub pollen_index: Option<f64>,
    pub pollen_category: Option<String>,
    pub pollen_tree_index: Option<f64>,
    pub pollen_grass_index: Option<f64>,
    pub pollen_weed_index: Option<f64>,
    pub pollen_primary_allergen: Option<String>,
    pub updated_at: Option<Timestamp>,
    pub sources: Vec<String>,
}

impl EnvironmentalConditions {
    pub fn has_data(&self) -> bool {
        self.air_quality_index.is_some()
            || self.pollen_index.is_some()
            || self.pollen_tree_index.is_some()
            || self.pollen_grass_index.is_some()
            || self.pollen_weed_index.is_some()
            || !self.hourly_air_quality.is_empty()
            || self.uv_index.is_some()
            || !self.hourly_uv_index.is_empty()
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct AviationData {
    pub raw_taf: Option<String>,
    pub decoded_taf: Option<String>,
    pub station_id: Option<String>,
    pub airport_name: Option<String>,
    /// Raw advisory dicts, as in Python.
    pub active_sigmets: Vec<Value>,
    pub active_cwas: Vec<Value>,
}

impl AviationData {
    pub fn has_taf(&self) -> bool {
        let filled = |s: &Option<String>| s.as_deref().is_some_and(|t| !t.trim().is_empty());
        filled(&self.raw_taf) || filled(&self.decoded_taf)
    }
}

// ---------------------------------------------------------------------------
// weather_forecast
// ---------------------------------------------------------------------------

fn d_unit_f() -> String {
    "F".into()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct ForecastPeriod {
    pub name: String,
    /// High temperature (or single temperature for the period).
    pub temperature: Option<f64>,
    pub temperature_low: Option<f64>,
    pub temperature_unit: String,
    pub short_forecast: Option<String>,
    pub detailed_forecast: Option<String>,
    pub wind_speed: Option<String>,
    pub wind_speed_mph: Option<f64>,
    pub wind_direction: Option<String>,
    pub icon: Option<String>,
    pub start_time: Option<Timestamp>,
    pub end_time: Option<Timestamp>,
    pub precipitation_probability: Option<f64>,
    pub snowfall: Option<f64>,
    pub uv_index: Option<f64>,
    pub cloud_cover: Option<f64>,
    /// e.g. "25 mph"
    pub wind_gust: Option<String>,
    /// Inches.
    pub precipitation_amount: Option<f64>,

    // Seasonal - winter
    pub snow_depth: Option<f64>,
    pub wind_chill_min_f: Option<f64>,
    pub wind_chill_max_f: Option<f64>,
    pub freezing_level_ft: Option<f64>,
    pub ice_risk: Option<String>,

    // Seasonal - summer
    pub heat_index_max_f: Option<f64>,
    pub heat_index_min_f: Option<f64>,
    pub uv_index_max: Option<f64>,
    pub air_quality_forecast: Option<i64>,

    // Seasonal - spring/fall
    pub frost_risk: Option<String>,
    pub pollen_forecast: Option<String>,

    // Seasonal - year-round
    pub precipitation_type: Option<Vec<String>>,
    pub severe_weather_risk: Option<i64>,
    pub feels_like_high: Option<f64>,
    pub feels_like_low: Option<f64>,
}

impl Default for ForecastPeriod {
    fn default() -> Self {
        Self {
            name: String::new(),
            temperature: None,
            temperature_low: None,
            temperature_unit: d_unit_f(),
            short_forecast: None,
            detailed_forecast: None,
            wind_speed: None,
            wind_speed_mph: None,
            wind_direction: None,
            icon: None,
            start_time: None,
            end_time: None,
            precipitation_probability: None,
            snowfall: None,
            uv_index: None,
            cloud_cover: None,
            wind_gust: None,
            precipitation_amount: None,
            snow_depth: None,
            wind_chill_min_f: None,
            wind_chill_max_f: None,
            freezing_level_ft: None,
            ice_risk: None,
            heat_index_max_f: None,
            heat_index_min_f: None,
            uv_index_max: None,
            air_quality_forecast: None,
            frost_risk: None,
            pollen_forecast: None,
            precipitation_type: None,
            severe_weather_risk: None,
            feels_like_high: None,
            feels_like_low: None,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Forecast {
    pub periods: Vec<ForecastPeriod>,
    pub generated_at: Option<PyTimestamp>,
    pub summary: Option<String>,
}

impl Forecast {
    pub fn has_data(&self) -> bool {
        !self.periods.is_empty()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HourlyForecastPeriod {
    pub start_time: Timestamp,
    #[serde(default)]
    pub temperature: Option<f64>,
    #[serde(default = "d_unit_f")]
    pub temperature_unit: String,
    #[serde(default)]
    pub short_forecast: Option<String>,
    #[serde(default)]
    pub wind_speed: Option<String>,
    #[serde(default)]
    pub wind_direction: Option<String>,
    #[serde(default)]
    pub icon: Option<String>,
    #[serde(default)]
    pub end_time: Option<Timestamp>,
    #[serde(default)]
    pub humidity: Option<i64>,
    #[serde(default)]
    pub dewpoint_f: Option<f64>,
    #[serde(default)]
    pub dewpoint_c: Option<f64>,
    #[serde(default)]
    pub pressure_mb: Option<f64>,
    #[serde(default)]
    pub pressure_in: Option<f64>,
    #[serde(default)]
    pub precipitation_probability: Option<f64>,
    #[serde(default)]
    pub snowfall: Option<f64>,
    #[serde(default)]
    pub uv_index: Option<f64>,
    #[serde(default)]
    pub cloud_cover: Option<f64>,
    #[serde(default)]
    pub wind_speed_mph: Option<f64>,
    #[serde(default)]
    pub wind_gust_mph: Option<f64>,
    /// Inches.
    #[serde(default)]
    pub precipitation_amount: Option<f64>,

    // Seasonal - winter
    #[serde(default)]
    pub snow_depth: Option<f64>,
    #[serde(default)]
    pub freezing_level_ft: Option<f64>,
    #[serde(default)]
    pub wind_chill_f: Option<f64>,
    #[serde(default)]
    pub wind_chill_c: Option<f64>,

    // Seasonal - summer
    #[serde(default)]
    pub heat_index_f: Option<f64>,
    #[serde(default)]
    pub heat_index_c: Option<f64>,
    #[serde(default)]
    pub air_quality_index: Option<i64>,

    // Seasonal - spring/fall
    #[serde(default)]
    pub frost_risk: Option<bool>,
    #[serde(default)]
    pub pollen_level: Option<String>,

    // Seasonal - year-round
    #[serde(default)]
    pub precipitation_type: Option<Vec<String>>,
    #[serde(default)]
    pub feels_like: Option<f64>,
    #[serde(default)]
    pub visibility_miles: Option<f64>,
    #[serde(default)]
    pub visibility_km: Option<f64>,
}

impl HourlyForecastPeriod {
    pub fn new(start_time: Timestamp) -> Self {
        Self {
            start_time,
            temperature: None,
            temperature_unit: d_unit_f(),
            short_forecast: None,
            wind_speed: None,
            wind_direction: None,
            icon: None,
            end_time: None,
            humidity: None,
            dewpoint_f: None,
            dewpoint_c: None,
            pressure_mb: None,
            pressure_in: None,
            precipitation_probability: None,
            snowfall: None,
            uv_index: None,
            cloud_cover: None,
            wind_speed_mph: None,
            wind_gust_mph: None,
            precipitation_amount: None,
            snow_depth: None,
            freezing_level_ft: None,
            wind_chill_f: None,
            wind_chill_c: None,
            heat_index_f: None,
            heat_index_c: None,
            air_quality_index: None,
            frost_risk: None,
            pollen_level: None,
            precipitation_type: None,
            feels_like: None,
            visibility_miles: None,
            visibility_km: None,
        }
    }

    pub fn has_data(&self) -> bool {
        self.temperature.is_some()
            || self.short_forecast.is_some()
            || self.wind_speed.is_some()
            || self.humidity.is_some()
            || self.dewpoint_f.is_some()
            || self.dewpoint_c.is_some()
            || self.pressure_mb.is_some()
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct HourlyForecast {
    pub periods: Vec<HourlyForecastPeriod>,
    pub generated_at: Option<PyTimestamp>,
    pub summary: Option<String>,
}

impl HourlyForecast {
    pub fn has_data(&self) -> bool {
        !self.periods.is_empty()
    }

    /// `get_next_hours`: the next `count` periods starting no earlier than an
    /// hour before `now`, sorted by start; the first `count` if all are past.
    pub fn next_hours(&self, count: usize, now: DateTime<Utc>) -> Vec<&HourlyForecastPeriod> {
        let mut sorted: Vec<&HourlyForecastPeriod> = self.periods.iter().collect();
        sorted.sort_by_key(|p| p.start_time);
        let cutoff = now - chrono::Duration::hours(1);
        let upcoming: Vec<&HourlyForecastPeriod> = sorted
            .iter()
            .copied()
            .filter(|p| p.start_time >= cutoff)
            .take(count)
            .collect();
        if upcoming.is_empty() {
            sorted.into_iter().take(count).collect()
        } else {
            upcoming
        }
    }
}

fn d_mm_hr() -> String {
    "mm/hr".into()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MinutelyPrecipitationPoint {
    pub time: Timestamp,
    #[serde(default)]
    pub precipitation_intensity: Option<f64>,
    #[serde(default)]
    pub precipitation_probability: Option<f64>,
    #[serde(default)]
    pub precipitation_type: Option<String>,
    #[serde(default = "d_mm_hr")]
    pub precipitation_intensity_unit: String,
    #[serde(default)]
    pub precipitation_intensity_error: Option<f64>,
    #[serde(default = "d_mm_hr")]
    pub precipitation_intensity_error_unit: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct MinutelyPrecipitationForecast {
    pub summary: Option<String>,
    pub icon: Option<String>,
    pub points: Vec<MinutelyPrecipitationPoint>,
}

impl MinutelyPrecipitationForecast {
    pub fn has_data(&self) -> bool {
        !self.points.is_empty()
    }
}

fn d_24() -> i64 {
    24
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TrendInsight {
    pub metric: String,
    pub direction: String,
    #[serde(default)]
    pub change: Option<f64>,
    #[serde(default)]
    pub unit: Option<String>,
    #[serde(default = "d_24")]
    pub timeframe_hours: i64,
    #[serde(default)]
    pub summary: Option<String>,
    #[serde(default)]
    pub sparkline: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HourlyAirQuality {
    pub timestamp: Timestamp,
    pub aqi: i64,
    pub category: String,
    #[serde(default)]
    pub pm2_5: Option<f64>,
    #[serde(default)]
    pub pm10: Option<f64>,
    #[serde(default)]
    pub ozone: Option<f64>,
    #[serde(default)]
    pub nitrogen_dioxide: Option<f64>,
    #[serde(default)]
    pub sulphur_dioxide: Option<f64>,
    #[serde(default)]
    pub carbon_monoxide: Option<f64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HourlyUVIndex {
    pub timestamp: Timestamp,
    pub uv_index: f64,
    pub category: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MarineForecastPeriod {
    pub name: String,
    pub summary: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct MarineForecast {
    pub zone_id: Option<String>,
    pub zone_name: Option<String>,
    pub forecast_summary: Option<String>,
    pub issued_at: Option<Timestamp>,
    pub periods: Vec<MarineForecastPeriod>,
    pub highlights: Vec<String>,
}

impl MarineForecast {
    pub fn has_data(&self) -> bool {
        self.forecast_summary
            .as_deref()
            .is_some_and(|s| !s.is_empty())
            || self.zone_name.as_deref().is_some_and(|s| !s.is_empty())
            || !self.periods.is_empty()
            || !self.highlights.is_empty()
    }
}

// ---------------------------------------------------------------------------
// alerts
// ---------------------------------------------------------------------------

fn d_unknown() -> String {
    "Unknown".into()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WeatherAlert {
    pub title: String,
    pub description: String,
    #[serde(default = "d_unknown")]
    pub severity: String,
    #[serde(default = "d_unknown")]
    pub urgency: String,
    #[serde(default = "d_unknown")]
    pub certainty: String,
    #[serde(default)]
    pub event: Option<String>,
    #[serde(default)]
    pub headline: Option<String>,
    #[serde(default)]
    pub instruction: Option<String>,
    #[serde(default)]
    pub onset: Option<Timestamp>,
    #[serde(default)]
    pub expires: Option<Timestamp>,
    #[serde(default)]
    pub sent: Option<Timestamp>,
    #[serde(default)]
    pub effective: Option<Timestamp>,
    #[serde(default)]
    pub areas: Vec<String>,
    #[serde(default)]
    pub references: Vec<String>,
    #[serde(default)]
    pub id: Option<String>,
    #[serde(default)]
    pub source: Option<String>,
    /// e.g. "Alert", "Update", "Cancel".
    #[serde(default)]
    pub message_type: Option<String>,
    /// NWS zone identifiers (e.g. "PHZ007") from `affectedZones`.
    #[serde(default)]
    pub affected_zones: Vec<String>,
    /// SAME/FIPS county codes (geography only).
    #[serde(default)]
    pub same_codes: Vec<String>,
    /// SAME/EAS event codes from `eventCode.SAME`, e.g. ["TOR"].
    #[serde(default)]
    pub same_event_codes: Vec<String>,
}

impl WeatherAlert {
    pub fn new(title: impl Into<String>, description: impl Into<String>) -> Self {
        Self {
            title: title.into(),
            description: description.into(),
            severity: d_unknown(),
            urgency: d_unknown(),
            certainty: d_unknown(),
            event: None,
            headline: None,
            instruction: None,
            onset: None,
            expires: None,
            sent: None,
            effective: None,
            areas: Vec::new(),
            references: Vec::new(),
            id: None,
            source: None,
            message_type: None,
            affected_zones: Vec::new(),
            same_codes: Vec::new(),
            same_event_codes: Vec::new(),
        }
    }

    /// `get_unique_id`.
    pub fn unique_id(&self) -> String {
        if let Some(id) = self.id.as_deref().filter(|s| !s.is_empty()) {
            return id.to_string();
        }
        let or_unknown =
            |s: Option<&str>| s.filter(|s| !s.is_empty()).unwrap_or("unknown").to_string();
        let mut parts = vec![
            or_unknown(self.event.as_deref()),
            or_unknown(Some(&self.severity)),
            or_unknown(
                self.headline
                    .as_deref()
                    .filter(|s| !s.is_empty())
                    .or(Some(&self.title)),
            ),
        ];
        if let Some(src) = self.source.as_deref().filter(|s| !s.is_empty()) {
            parts.push(src.to_string());
        }
        if !self.areas.is_empty() {
            let mut areas = self.areas.clone();
            areas.sort();
            parts.push(areas.join(","));
        }
        parts
            .iter()
            .map(|p| p.to_lowercase().replace(' ', "_"))
            .collect::<Vec<_>>()
            .join("-")
    }

    /// `get_content_hash`: md5 of the key content fields.
    pub fn content_hash(&self) -> String {
        let parts = [
            self.title.as_str(),
            self.description.as_str(),
            self.severity.as_str(),
            self.urgency.as_str(),
            self.headline.as_deref().unwrap_or(""),
            self.instruction.as_deref().unwrap_or(""),
        ];
        format!("{:x}", md5::compute(parts.join("|")))
    }

    pub fn is_expired(&self, now: DateTime<Utc>) -> bool {
        self.expires.is_some_and(|e| now > e)
    }

    /// `get_severity_priority` (`SEVERITY_PRIORITY_MAP`): higher = more severe.
    pub fn severity_priority(&self) -> u8 {
        severity_priority(&self.severity)
    }
}

/// `constants.SEVERITY_PRIORITY_MAP`.
pub fn severity_priority(severity: &str) -> u8 {
    match severity.to_lowercase().as_str() {
        "minor" => 2,
        "moderate" => 3,
        "severe" => 4,
        "extreme" => 5,
        _ => 1,
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct WeatherAlerts {
    pub alerts: Vec<WeatherAlert>,
}

impl WeatherAlerts {
    pub fn has_alerts(&self) -> bool {
        !self.alerts.is_empty()
    }

    /// `get_active_alerts`: alerts without an expiry or expiring after `now`
    /// (an alert expiring exactly at `now` is neither active nor expired,
    /// as in Python).
    pub fn active(&self, now: DateTime<Utc>) -> Vec<&WeatherAlert> {
        self.alerts
            .iter()
            .filter(|a| a.expires.is_none_or(|e| e > now))
            .collect()
    }
}

// ---------------------------------------------------------------------------
// alert_lifecycle / forecast_confidence / weather_anomaly result types
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AlertChangeKind {
    New,
    Updated,
    Escalated,
    Extended,
    Cancelled,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AlertChange {
    pub kind: AlertChangeKind,
    #[serde(default)]
    pub alert: Option<WeatherAlert>,
    #[serde(default)]
    pub alert_id: String,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub old_severity: Option<String>,
    #[serde(default)]
    pub new_severity: Option<String>,
}

fn d_no_changes() -> String {
    "No changes".into()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AlertLifecycleDiff {
    #[serde(default)]
    pub new_alerts: Vec<AlertChange>,
    #[serde(default)]
    pub updated_alerts: Vec<AlertChange>,
    #[serde(default)]
    pub escalated_alerts: Vec<AlertChange>,
    #[serde(default)]
    pub extended_alerts: Vec<AlertChange>,
    #[serde(default)]
    pub cancelled_alerts: Vec<AlertChange>,
    #[serde(default = "d_no_changes")]
    pub summary: String,
}

impl Default for AlertLifecycleDiff {
    fn default() -> Self {
        Self {
            new_alerts: Vec::new(),
            updated_alerts: Vec::new(),
            escalated_alerts: Vec::new(),
            extended_alerts: Vec::new(),
            cancelled_alerts: Vec::new(),
            summary: d_no_changes(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ForecastConfidenceLevel {
    High,
    Medium,
    Low,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ForecastConfidence {
    pub level: ForecastConfidenceLevel,
    pub rationale: String,
    pub sources_compared: i64,
    #[serde(default)]
    pub source_names: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AnomalyCallout {
    /// Positive = warmer, negative = cooler (°F).
    pub temp_anomaly: f64,
    pub temp_anomaly_description: String,
    #[serde(default)]
    pub precip_anomaly_description: Option<String>,
    /// "normal", "notable" or "significant".
    pub severity: String,
}

// ---------------------------------------------------------------------------
// weather_data / text_product
// ---------------------------------------------------------------------------

/// Data from a single source before fusion.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SourceData {
    /// "nws", "openmeteo", "pirateweather"
    pub source: String,
    #[serde(default)]
    pub current: Option<CurrentConditions>,
    #[serde(default)]
    pub forecast: Option<Forecast>,
    #[serde(default)]
    pub hourly_forecast: Option<HourlyForecast>,
    #[serde(default)]
    pub alerts: Option<WeatherAlerts>,
    #[serde(default)]
    pub discussion: Option<String>,
    #[serde(default)]
    pub discussion_issuance_time: Option<Timestamp>,
    pub fetch_time: Timestamp,
    #[serde(default = "d_true")]
    pub success: bool,
    #[serde(default)]
    pub error: Option<String>,
}

fn d_true() -> bool {
    true
}

impl SourceData {
    pub fn new(source: impl Into<String>) -> Self {
        Self {
            source: source.into(),
            current: None,
            forecast: None,
            hourly_forecast: None,
            alerts: None,
            discussion: None,
            discussion_issuance_time: None,
            fetch_time: Utc::now().fixed_offset(),
            success: true,
            error: None,
        }
    }
}

/// Everything known about a location after a refresh.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct WeatherData {
    pub location: Location,
    pub current: Option<CurrentConditions>,
    pub forecast: Option<Forecast>,
    pub hourly_forecast: Option<HourlyForecast>,
    pub daily_history: Vec<ForecastPeriod>,
    pub discussion: Option<String>,
    /// NWS AFD issuance time, for update detection.
    pub discussion_issuance_time: Option<Timestamp>,
    pub minutely_precipitation: Option<MinutelyPrecipitationForecast>,
    pub alerts: Option<WeatherAlerts>,
    pub environmental: Option<EnvironmentalConditions>,
    pub aviation: Option<AviationData>,
    pub marine: Option<MarineForecast>,
    pub trend_insights: Vec<TrendInsight>,
    pub stale: bool,
    pub stale_since: Option<Timestamp>,
    pub stale_reason: Option<String>,
    pub source_attribution: Option<SourceAttribution>,
    pub incomplete_sections: BTreeSet<String>,
    pub alert_lifecycle_diff: Option<AlertLifecycleDiff>,
    pub forecast_confidence: Option<ForecastConfidence>,
    pub anomaly_callout: Option<AnomalyCallout>,
}

impl WeatherData {
    pub fn new(location: Location) -> Self {
        Self {
            location,
            ..Default::default()
        }
    }

    pub fn has_any_data(&self) -> bool {
        self.current
            .as_ref()
            .is_some_and(CurrentConditions::has_data)
            || self.forecast.as_ref().is_some_and(Forecast::has_data)
            || self
                .hourly_forecast
                .as_ref()
                .is_some_and(HourlyForecast::has_data)
            || self
                .minutely_precipitation
                .as_ref()
                .is_some_and(MinutelyPrecipitationForecast::has_data)
            || self.alerts.as_ref().is_some_and(WeatherAlerts::has_alerts)
            || self
                .environmental
                .as_ref()
                .is_some_and(EnvironmentalConditions::has_data)
            || self.aviation.as_ref().is_some_and(AviationData::has_taf)
            || self.marine.as_ref().is_some_and(MarineForecast::has_data)
    }
}

/// A single NWS text product (AFD, HWO, SPS, SRF, CLI, ...).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TextProduct {
    pub product_type: String,
    pub product_id: String,
    pub cwa_office: String,
    pub issuance_time: Option<Timestamp>,
    pub product_text: String,
    pub headline: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn season_flips_south_of_equator() {
        assert_eq!(season(1, 40.0), Season::Winter);
        assert_eq!(season(1, -33.9), Season::Summer);
        assert_eq!(season(10, 0.0), Season::Fall);
    }

    #[test]
    fn unique_id_matches_python_derivation() {
        let mut a = WeatherAlert::new("Title", "desc");
        a.event = Some("Wind Advisory".into());
        a.severity = "Moderate".into();
        a.headline = Some("Wind Advisory issued".into());
        a.source = Some("NWS".into());
        a.areas = vec!["B".into(), "A".into()];
        assert_eq!(
            a.unique_id(),
            "wind_advisory-moderate-wind_advisory_issued-nws-a,b"
        );
        a.id = Some("urn:1".into());
        assert_eq!(a.unique_id(), "urn:1");
    }

    #[test]
    fn content_hash_matches_python_md5() {
        // hashlib.md5("T|D|Minor|Unknown||".encode()).hexdigest()
        let mut a = WeatherAlert::new("T", "D");
        a.severity = "Minor".into();
        assert_eq!(a.content_hash(), "7aa0b99aab9eb86ccb215fa9a89a3e5c");
    }

    #[test]
    fn python_asdict_json_deserialises() {
        let json = r#"{
            "location": {"name": "Home", "latitude": 40.0, "longitude": -75.0,
                         "timezone": null, "country_code": "US", "marine_mode": false,
                         "forecast_zone_id": null, "cwa_office": null, "county_zone_id": null,
                         "fire_zone_id": null, "radar_station": null},
            "current": {"temperature": 72.0, "humidity": 55, "condition": "Clear",
                        "sunrise_time": "2026-09-25T06:58:00-04:00"},
            "hourly_forecast": {"periods": [{"start_time": "2026-09-25T15:00:00-04:00",
                                             "temperature": 71.0}],
                                "generated_at": null, "summary": null},
            "incomplete_sections": ["hourly"],
            "pending_enrichments": null
        }"#;
        let data: WeatherData = serde_json::from_str(json).unwrap();
        assert_eq!(data.current.as_ref().unwrap().humidity, Some(55));
        let hourly = data.hourly_forecast.unwrap();
        assert_eq!(hourly.periods[0].temperature_unit, "F");
        let offset = FixedOffset::west_opt(4 * 3600).unwrap();
        assert_eq!(
            hourly.periods[0].start_time,
            offset.with_ymd_and_hms(2026, 9, 25, 15, 0, 0).unwrap()
        );
    }
}
