use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use crate::location::Location;

pub const DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT: &str = "Ctrl+Alt+Shift+W";
pub const DEFAULT_HIDE_MAIN_WINDOW_SHORTCUT: &str = "Ctrl+Alt+Shift+M";
pub const DEFAULT_READ_TRAY_INFO_SHORTCUT: &str = "Ctrl+Alt+Shift+I";
pub const DEFAULT_NOAA_RADIO_HOTKEY: &str = "Ctrl+Alt+Shift+R";

const LEGACY_NATIONWIDE_LOCATION_NAME: &str = "Nationwide";

fn s(v: &str) -> String {
    v.to_string()
}

macro_rules! default_fn {
    ($name:ident, $ty:ty, $val:expr) => {
        fn $name() -> $ty {
            $val
        }
    };
}

default_fn!(d_both, String, s("both"));
default_fn!(d_auto, String, s("auto"));
default_fn!(d_10, i64, 10);
default_fn!(d_true, bool, true);
default_fn!(
    d_show_shortcut,
    String,
    s(DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT)
);
default_fn!(
    d_hide_shortcut,
    String,
    s(DEFAULT_HIDE_MAIN_WINDOW_SHORTCUT)
);
default_fn!(d_tray_shortcut, String, s(DEFAULT_READ_TRAY_INFO_SHORTCUT));
default_fn!(d_radio_hotkey, String, s(DEFAULT_NOAA_RADIO_HOTKEY));
default_fn!(d_stable, String, s("stable"));
default_fn!(d_24, i64, 24);
default_fn!(d_default, String, s("default"));
default_fn!(d_5, i64, 5);
default_fn!(d_60, i64, 60);
default_fn!(d_15, i64, 15);
default_fn!(d_180, i64, 180);
default_fn!(d_7, i64, 7);
default_fn!(d_6, i64, 6);
default_fn!(d_county, String, s("county"));
default_fn!(d_light, String, s("light"));
default_fn!(d_half, f64, 0.5);
default_fn!(d_location, String, s("location"));
default_fn!(d_local, String, s("local"));
default_fn!(d_separate, String, s("separate"));
default_fn!(d_alphabetical, String, s("alphabetical"));
default_fn!(d_iso, String, s("iso"));
default_fn!(d_taskbar_fmt, String, s("{temp} {condition}"));
default_fn!(d_best_match, String, s("best_match"));
default_fn!(d_hybrid, String, s("hybrid_default"));
default_fn!(d_openrouter, String, s("openrouter"));
default_fn!(d_venice_model, String, s("venice-uncensored-1-2"));
default_fn!(d_ai_model, String, s("openrouter/free"));
default_fn!(d_standard, String, s("standard"));
default_fn!(d_300, i64, 300);
default_fn!(d_parallel_timeout, f64, 10.0);
default_fn!(d_max_coverage, String, s("max_coverage"));
default_fn!(
    d_us_sources,
    Vec<String>,
    vec![s("nws"), s("openmeteo"), s("pirateweather")]
);
default_fn!(
    d_intl_sources,
    Vec<String>,
    vec![s("openmeteo"), s("pirateweather")]
);
default_fn!(
    d_category_order,
    Vec<String>,
    vec![
        s("temperature"),
        s("precipitation"),
        s("wind"),
        s("humidity_pressure"),
        s("visibility_clouds"),
        s("uv_index"),
    ]
);

/// Application settings. Field names and defaults mirror the Python
/// `AppSettings` dataclass so an existing `accessiweather.json` loads
/// unchanged and stays readable by the Python app.
///
/// Unknown keys are preserved in `extra` so the Rust build never drops
/// settings it does not understand yet.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AppSettings {
    #[serde(default = "d_both")]
    pub temperature_unit: String,
    #[serde(default = "d_auto")]
    pub wind_speed_unit: String,
    #[serde(default = "d_10")]
    pub update_interval_minutes: i64,
    #[serde(default = "d_true")]
    pub enable_alerts: bool,
    #[serde(default)]
    pub minimize_to_tray: bool,
    #[serde(default)]
    pub minimize_on_startup: bool,
    #[serde(default = "d_show_shortcut")]
    pub shortcut_show_main_window: String,
    #[serde(default = "d_hide_shortcut")]
    pub shortcut_hide_main_window: String,
    #[serde(default = "d_tray_shortcut")]
    pub shortcut_read_tray_info: String,
    #[serde(default)]
    pub startup_enabled: bool,
    #[serde(default = "d_auto")]
    pub data_source: String,
    /// API keys live in the keyring or the portable bundle (see
    /// `aw_store::secrets`) and are never written to the JSON file.
    #[serde(default, skip_serializing)]
    pub pirate_weather_api_key: String,
    #[serde(default, skip_serializing)]
    pub airnow_api_key: String,
    #[serde(default = "d_true")]
    pub auto_update_enabled: bool,
    #[serde(default = "d_stable")]
    pub update_channel: String,
    #[serde(default = "d_24")]
    pub update_check_interval_hours: i64,
    #[serde(default = "d_true")]
    pub sound_enabled: bool,
    #[serde(default = "d_default")]
    pub sound_pack: String,
    #[serde(default)]
    pub muted_sound_events: Vec<String>,
    #[serde(default)]
    pub specific_alert_sound_packs: Vec<String>,
    #[serde(default)]
    pub auto_tune_weather_radio_alerts: bool,
    #[serde(default = "d_5")]
    pub auto_tune_weather_radio_duration_minutes: i64,
    #[serde(default = "d_radio_hotkey")]
    pub noaa_radio_hotkey: String,
    #[serde(default = "d_true")]
    pub notify_discussion_update: bool,
    #[serde(default)]
    pub notify_daily_climate_report_update: bool,
    #[serde(default = "d_true")]
    pub notify_hwo_update: bool,
    #[serde(default = "d_true")]
    pub notify_sps_issued: bool,
    #[serde(default)]
    pub notify_severe_risk_change: bool,
    #[serde(default = "d_true")]
    pub notify_minutely_precipitation_start: bool,
    #[serde(default = "d_true")]
    pub notify_minutely_precipitation_stop: bool,
    #[serde(default)]
    pub minutely_precipitation_fast_polling: bool,
    #[serde(default = "d_light")]
    pub precipitation_sensitivity: String,
    #[serde(default)]
    pub notify_precipitation_likelihood: bool,
    #[serde(default = "d_half")]
    pub precipitation_likelihood_threshold: f64,
    #[serde(default = "d_county")]
    pub alert_radius_type: String,
    #[serde(default = "d_true")]
    pub alert_notifications_enabled: bool,
    #[serde(default = "d_true")]
    pub alert_notify_extreme: bool,
    #[serde(default = "d_true")]
    pub alert_notify_severe: bool,
    #[serde(default = "d_true")]
    pub alert_notify_moderate: bool,
    #[serde(default)]
    pub alert_notify_minor: bool,
    #[serde(default)]
    pub alert_notify_unknown: bool,
    #[serde(default)]
    pub immediate_alert_details_popups: bool,
    #[serde(default = "d_5")]
    pub alert_global_cooldown_minutes: i64,
    #[serde(default = "d_60")]
    pub alert_per_alert_cooldown_minutes: i64,
    #[serde(default = "d_15")]
    pub alert_escalation_cooldown_minutes: i64,
    #[serde(default = "d_15")]
    pub alert_freshness_window_minutes: i64,
    #[serde(default = "d_10")]
    pub alert_max_notifications_per_hour: i64,
    #[serde(default)]
    pub alert_ignored_categories: Vec<String>,
    #[serde(default = "d_true")]
    pub trend_insights_enabled: bool,
    #[serde(default = "d_24")]
    pub trend_hours: i64,
    #[serde(default = "d_true")]
    pub show_dewpoint: bool,
    #[serde(default = "d_true")]
    pub show_pressure_trend: bool,
    #[serde(default = "d_true")]
    pub show_visibility: bool,
    #[serde(default = "d_true")]
    pub show_uv_index: bool,
    #[serde(default = "d_true")]
    pub show_seasonal_data: bool,
    #[serde(default = "d_true")]
    pub air_quality_enabled: bool,
    #[serde(default = "d_true")]
    pub pollen_enabled: bool,
    #[serde(default = "d_true")]
    pub offline_cache_enabled: bool,
    #[serde(default = "d_180")]
    pub offline_cache_max_age_minutes: i64,
    #[serde(default = "d_true")]
    pub weather_history_enabled: bool,
    #[serde(default = "d_7")]
    pub forecast_duration_days: i64,
    #[serde(default = "d_6")]
    pub hourly_forecast_hours: i64,
    #[serde(default = "d_location")]
    pub forecast_time_reference: String,
    #[serde(default = "d_local")]
    pub time_display_mode: String,
    #[serde(default = "d_true")]
    pub time_format_12hour: bool,
    #[serde(default)]
    pub show_timezone_suffix: bool,
    #[serde(default = "d_separate")]
    pub alert_display_style: String,
    #[serde(default)]
    pub location_buttons_on_top: bool,
    #[serde(default = "d_alphabetical")]
    pub location_sort_order: String,
    #[serde(default = "d_iso")]
    pub date_format: String,
    #[serde(default)]
    pub taskbar_icon_text_enabled: bool,
    #[serde(default = "d_true")]
    pub taskbar_icon_dynamic_enabled: bool,
    #[serde(default = "d_taskbar_fmt")]
    pub taskbar_icon_text_format: String,
    #[serde(default = "d_us_sources")]
    pub source_priority_us: Vec<String>,
    #[serde(default = "d_intl_sources")]
    pub source_priority_international: Vec<String>,
    #[serde(default = "d_best_match")]
    pub openmeteo_weather_model: String,
    #[serde(default = "d_hybrid")]
    pub station_selection_strategy: String,
    #[serde(default, skip_serializing)]
    pub avwx_api_key: String,
    #[serde(default, skip_serializing)]
    pub openrouter_api_key: String,
    #[serde(default = "d_openrouter")]
    pub ai_provider: String,
    #[serde(default, skip_serializing)]
    pub venice_api_key: String,
    #[serde(default = "d_venice_model")]
    pub venice_model: String,
    #[serde(default = "d_ai_model")]
    pub ai_model_preference: String,
    #[serde(default = "d_standard")]
    pub ai_explanation_style: String,
    #[serde(default = "d_300")]
    pub ai_cache_ttl: i64,
    #[serde(default)]
    pub custom_system_prompt: Option<String>,
    #[serde(default)]
    pub custom_instructions: Option<String>,
    #[serde(default = "d_standard")]
    pub verbosity_level: String,
    #[serde(default = "d_category_order")]
    pub category_order: Vec<String>,
    #[serde(default)]
    pub severe_weather_override: bool,
    #[serde(default)]
    pub onboarding_wizard_shown: bool,
    #[serde(default)]
    pub portable_missing_api_keys_hint_shown: bool,
    #[serde(default)]
    pub round_values: bool,
    #[serde(default)]
    pub show_impact_summaries: bool,
    #[serde(default = "d_parallel_timeout")]
    pub parallel_fetch_timeout: f64,
    #[serde(default = "d_max_coverage")]
    pub auto_mode_api_budget: String,
    #[serde(default = "d_us_sources")]
    pub auto_sources_us: Vec<String>,
    #[serde(default = "d_intl_sources")]
    pub auto_sources_international: Vec<String>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

impl Default for AppSettings {
    fn default() -> Self {
        // An empty object deserialises into all defaults thanks to `#[serde(default)]`.
        serde_json::from_value(Value::Object(Map::new()))
            .expect("AppSettings defaults must deserialize from an empty object")
    }
}

impl AppSettings {
    pub fn forecast_days(&self) -> u32 {
        self.forecast_duration_days.clamp(3, 16) as u32
    }

    pub fn hourly_hours(&self) -> usize {
        self.hourly_forecast_hours.clamp(1, 384) as usize
    }

    pub fn update_interval_minutes(&self) -> u64 {
        self.update_interval_minutes.clamp(1, 24 * 60) as u64
    }
}

/// Top level configuration file (`accessiweather.json`).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct AppConfig {
    #[serde(default)]
    pub settings: AppSettings,
    #[serde(default)]
    pub locations: Vec<Location>,
    #[serde(default)]
    pub current_location: Option<Location>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

impl AppConfig {
    /// Parse the JSON document, applying the same clean-ups as Python's
    /// `AppConfig.from_dict` (drop the legacy "Nationwide" entry, uppercase
    /// country codes).
    pub fn from_json(text: &str) -> Result<Self, serde_json::Error> {
        let mut config: AppConfig = serde_json::from_str(text)?;
        config.normalize();
        Ok(config)
    }

    pub fn normalize(&mut self) {
        self.locations
            .retain(|loc| loc.name != LEGACY_NATIONWIDE_LOCATION_NAME);
        for loc in &mut self.locations {
            loc.normalize();
        }
        if let Some(current) = self.current_location.as_mut() {
            if current.name == LEGACY_NATIONWIDE_LOCATION_NAME {
                self.current_location = None;
            } else {
                current.normalize();
            }
        }
    }

    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }

    pub fn location_names(&self) -> Vec<String> {
        self.locations.iter().map(|l| l.name.clone()).collect()
    }

    pub fn find_location(&self, name: &str) -> Option<&Location> {
        self.locations.iter().find(|l| l.name == name)
    }

    /// `LocationOperations.add_location`: append a new location, making it
    /// current when none is set. False for bad coordinates or a duplicate name.
    pub fn add_location(&mut self, mut location: Location) -> bool {
        location.normalize();
        if !location.valid_coordinates() || self.find_location(&location.name).is_some() {
            return false;
        }
        if self.current_location.is_none() {
            self.current_location = Some(location.clone());
        }
        self.locations.push(location);
        true
    }

    /// `LocationOperations.update_location_details`. Moving the coordinates
    /// clears the NWS metadata so the next refresh resolves the new point.
    pub fn update_location_details(
        &mut self,
        name: &str,
        latitude: f64,
        longitude: f64,
        country_code: Option<String>,
        marine_mode: bool,
        display_name: Option<&str>,
    ) -> bool {
        let new_name = display_name.unwrap_or(name).trim().to_string();
        if new_name.is_empty() || (new_name != name && self.find_location(&new_name).is_some()) {
            return false;
        }
        let current_matches = self
            .current_location
            .as_ref()
            .is_some_and(|c| c.name == name);
        let Some(location) = self.locations.iter_mut().find(|l| l.name == name) else {
            return false;
        };
        let moved = (location.latitude - latitude).abs() > 1e-6
            || (location.longitude - longitude).abs() > 1e-6;
        location.name = new_name;
        location.latitude = latitude;
        location.longitude = longitude;
        location.country_code = country_code.map(|c| c.to_uppercase());
        location.marine_mode = marine_mode;
        if moved {
            location.timezone = None;
            location.forecast_zone_id = None;
            location.cwa_office = None;
            location.county_zone_id = None;
            location.fire_zone_id = None;
            location.radar_station = None;
        }
        if current_matches {
            self.current_location = Some(location.clone());
        }
        true
    }

    /// `LocationOperations.remove_location`: the first remaining location
    /// becomes current when the current one is removed.
    pub fn remove_location(&mut self, name: &str) -> bool {
        let Some(index) = self.locations.iter().position(|l| l.name == name) else {
            return false;
        };
        self.locations.remove(index);
        if self
            .current_location
            .as_ref()
            .is_some_and(|c| c.name == name)
        {
            self.current_location = self.locations.first().cloned();
        }
        true
    }

    /// `LocationOperations.reorder_locations`: the names must be exactly the
    /// saved ones, in a new order.
    pub fn reorder_locations(&mut self, ordered_names: &[String]) -> bool {
        let current_names = self.location_names();
        if ordered_names == current_names.as_slice() {
            return true;
        }
        let mut sorted_new = ordered_names.to_vec();
        let mut sorted_old = current_names;
        sorted_new.sort();
        sorted_new.dedup();
        sorted_old.sort();
        if ordered_names.len() != self.locations.len() || sorted_new != sorted_old {
            return false;
        }
        let mut old = std::mem::take(&mut self.locations);
        for name in ordered_names {
            let i = old
                .iter()
                .position(|l| &l.name == name)
                .expect("names checked");
            self.locations.push(old.remove(i));
        }
        true
    }

    pub fn set_current_location(&mut self, name: &str) -> bool {
        match self.find_location(name).cloned() {
            Some(loc) => {
                self.current_location = Some(loc);
                true
            }
            None => false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_match_python() {
        let s = AppSettings::default();
        assert_eq!(s.temperature_unit, "both");
        assert_eq!(s.update_interval_minutes, 10);
        assert!(s.enable_alerts);
        assert_eq!(s.forecast_duration_days, 7);
        assert_eq!(
            s.source_priority_us,
            vec!["nws", "openmeteo", "pirateweather"]
        );
        assert_eq!(s.parallel_fetch_timeout, 10.0);
        assert!(s.custom_system_prompt.is_none());
    }

    #[test]
    fn unknown_keys_survive_round_trip() {
        let text = r#"{"settings":{"temperature_unit":"f","future_flag":true},
            "locations":[{"name":"Nationwide","latitude":0,"longitude":0},
                         {"name":"Philadelphia, PA","latitude":39.95,"longitude":-75.16,"country_code":"us"}],
            "current_location":null,"schema_version":1}"#;
        let cfg = AppConfig::from_json(text).unwrap();
        assert_eq!(cfg.locations.len(), 1);
        assert_eq!(cfg.locations[0].country_code.as_deref(), Some("US"));
        assert!(cfg.current_location.is_none());
        let out: Value = serde_json::from_str(&cfg.to_json().unwrap()).unwrap();
        assert_eq!(out["settings"]["future_flag"], Value::Bool(true));
        assert_eq!(out["settings"]["temperature_unit"], "f");
        assert_eq!(out["schema_version"], 1);
        assert!(out["settings"].get("pirate_weather_api_key").is_none());
    }
}
