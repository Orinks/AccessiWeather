//! The Settings dialog as plain data: the value of every control, loaded from
//! `AppSettings` and collected back into the settings dict exactly as the
//! Python tabs do (`ui/dialogs/settings_tabs/*.py` `load`/`save`, plus the
//! validation and save guards in `settings_dialog_core.py` and
//! `settings_dialog_handlers.py`). No wx here, so the mapping is unit tested
//! against Python goldens; `settings_dialog.rs` copies it to and from the
//! widgets.

use aw_core::settings::AppSettings;
use aw_core::shortcut_preferences::{
    normalize_hotkey, normalize_shortcut_text, py_repr, reserved_shortcut_use,
    WINDOW_TRAY_SHORTCUTS,
};
use aw_core::sound_events::{
    is_user_mutable_sound_event, normalize_known_muted_sound_events, user_mutable_sound_events,
};
use serde::Serialize;
use serde_json::{json, Map, Value};

// --- Display tab (`settings_tabs/display.py`) ---

pub(crate) const TEMP_UNIT_CHOICES: [&str; 4] = [
    "Auto (based on location)",
    "Imperial (°F)",
    "Metric (°C)",
    "Both (°F and °C)",
];
const TEMP_VALUES: [&str; 4] = ["auto", "f", "c", "both"];
pub(crate) const WIND_SPEED_UNIT_CHOICES: [&str; 4] = [
    "Match temperature setting/location",
    "Miles per hour (mph)",
    "Kilometers per hour (km/h)",
    "Meters per second (m/s)",
];
const WIND_SPEED_UNIT_VALUES: [&str; 4] = ["auto", "mph", "km/h", "m/s"];
pub(crate) const LOCATION_SORT_CHOICES: [&str; 3] = [
    "Alphabetical (default)",
    "Manual (custom)",
    "Nearest to current location",
];
const LOCATION_SORT_VALUES: [&str; 3] = ["alphabetical", "manual", "nearest_current"];
pub(crate) const FORECAST_DURATION_CHOICES: [&str; 6] = [
    "3 days",
    "5 days",
    "7 days (default)",
    "10 days",
    "14 days",
    "15 days",
];
const FORECAST_DURATION_VALUES: [i64; 6] = [3, 5, 7, 10, 14, 15];
pub(crate) const FORECAST_TIME_REF_CHOICES: [&str; 2] =
    ["Location timezone (default)", "My local timezone"];
const FORECAST_TIME_REF_VALUES: [&str; 2] = ["location", "user_local"];
pub(crate) const TIME_MODE_CHOICES: [&str; 3] =
    ["Local time only", "UTC time only", "Both local and UTC"];
const TIME_MODE_VALUES: [&str; 3] = ["local", "utc", "both"];
pub(crate) const DATE_FORMAT_CHOICES: [&str; 4] = [
    "ISO (2026-04-18)",
    "US short (04/18/2026)",
    "US long (April 18, 2026)",
    "EU (18/04/2026)",
];
const DATE_FORMAT_VALUES: [&str; 4] = ["iso", "us_short", "us_long", "eu"];
pub(crate) const VERBOSITY_CHOICES: [&str; 3] = [
    "Minimal (essentials only)",
    "Standard (recommended)",
    "Detailed (all available info)",
];
const VERBOSITY_VALUES: [&str; 3] = ["minimal", "standard", "detailed"];
pub(crate) const ALERT_DISPLAY_CHOICES: [&str; 2] =
    ["Separate fields (default)", "Single combined view"];
const ALERT_DISPLAY_VALUES: [&str; 2] = ["separate", "combined"];

// --- Alerts tab (`settings_tabs/notifications.py`) ---

pub(crate) const RADIUS_TYPE_CHOICES: [&str; 4] = [
    "County (recommended)",
    "Point (exact coordinate, may miss alerts)",
    "Zone (slightly broader than county)",
    "State (broadest and noisiest)",
];
const RADIUS_TYPE_VALUES: [&str; 4] = ["county", "point", "zone", "state"];
pub(crate) const SENSITIVITY_CHOICES: [&str; 3] = [
    "Light rain and above (default, \u{2265}0.01\u{a0}mm/hr)",
    "Moderate rain and above (\u{2265}0.1\u{a0}mm/hr)",
    "Heavy rain only (\u{2265}1.0\u{a0}mm/hr)",
];
const SENSITIVITY_VALUES: [&str; 3] = ["light", "moderate", "heavy"];
pub(crate) const LIKELIHOOD_THRESHOLD_CHOICES: [&str; 4] = ["50%", "60%", "70%", "80%"];
const LIKELIHOOD_THRESHOLD_VALUES: [f64; 4] = [0.5, 0.6, 0.7, 0.8];

// --- Data Sources tab (`settings_tabs/data_sources.py`) ---

pub(crate) const DATA_SOURCE_CHOICES: [&str; 4] = [
    "Automatic (combine all available sources)",
    "National Weather Service (US only, forecast and alerts)",
    "Open-Meteo (global forecast, no alerts, no API key)",
    "Pirate Weather (global forecast and alerts, API key)",
];
const SOURCE_VALUES: [&str; 4] = ["auto", "nws", "openmeteo", "pirateweather"];
const AUTO_MODE_BUDGET_VALUES: [&str; 3] = ["economy", "balanced", "max_coverage"];
const AUTO_MODE_BUDGET_LABELS: [&str; 3] = ["Economy", "Balanced", "Max coverage"];
const DEFAULT_BUDGET_INDEX: i32 = 2;
const DEFAULT_AUTO_SOURCES_US: [&str; 3] = ["nws", "openmeteo", "pirateweather"];
const DEFAULT_AUTO_SOURCES_INTERNATIONAL: [&str; 2] = ["openmeteo", "pirateweather"];
const STATION_STRATEGY_VALUES: [&str; 4] = [
    "hybrid_default",
    "nearest",
    "major_airport_preferred",
    "freshest_observation",
];
const STATION_STRATEGY_LABELS: [&str; 4] = [
    "Hybrid default",
    "Nearest station",
    "Major airport preferred",
    "Freshest observation",
];

fn source_label(source: &str) -> Option<&'static str> {
    match source {
        "nws" => Some("NWS"),
        "openmeteo" => Some("Open-Meteo"),
        "pirateweather" => Some("Pirate Weather"),
        _ => None,
    }
}

// --- AI tab (`settings_tabs/ai.py`) ---

pub(crate) const AI_PROVIDER_CHOICES: [&str; 2] = ["OpenRouter", "Venice AI"];
pub(crate) const AI_MODEL_CHOICES: [&str; 2] =
    ["Free router (automatic, free)", "Auto router (paid)"];
pub(crate) const AI_STYLE_CHOICES: [&str; 3] = [
    "Brief (1-2 sentences)",
    "Standard (3-4 sentences)",
    "Detailed (full paragraph)",
];
const STYLE_VALUES: [&str; 3] = ["brief", "standard", "detailed"];
pub(crate) const DEFAULT_VENICE_MODEL: &str = "venice-uncensored-1-2";

// --- Updates tab (`settings_tabs/updates.py`) ---

pub(crate) const UPDATE_CHANNEL_CHOICES: [&str; 2] = [
    "Stable (production releases only)",
    "Development (latest features, may be unstable)",
];

/// The API key fields guarded against accidental blanking on save, in
/// `_save_settings` order: (setting, control).
pub(crate) const GUARDED_API_KEYS: [(&str, &str); 4] = [
    ("pirate_weather_api_key", "pw_key"),
    ("airnow_api_key", "airnow_key"),
    ("openrouter_api_key", "openrouter_key"),
    ("venice_api_key", "venice_key"),
];

fn position<T: PartialEq>(values: &[T], value: &T) -> Option<usize> {
    values.iter().position(|v| v == value)
}

/// `wx.SpinCtrl.SetValue` keeps the value inside the control's range.
fn spin(value: i64, min: i32, max: i32) -> i32 {
    value.clamp(i64::from(min), i64::from(max)) as i32
}

/// A sound pack offered on the Audio tab (`get_available_sound_packs`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct SoundPack {
    pub id: String,
    pub name: String,
    /// `sound_pack_uses_specific_alert_sounds`.
    pub specific_alert_sounds: bool,
}

/// `_source_settings_states`: what "Configure Source Settings" edits.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct SourceSettings {
    pub auto_mode_api_budget: i32,
    pub auto_sources_us: Vec<String>,
    pub auto_sources_international: Vec<String>,
    pub station_selection_strategy: i32,
}

impl Default for SourceSettings {
    /// `_build_default_source_settings_states`.
    fn default() -> Self {
        Self {
            auto_mode_api_budget: DEFAULT_BUDGET_INDEX,
            auto_sources_us: DEFAULT_AUTO_SOURCES_US.map(String::from).to_vec(),
            auto_sources_international: DEFAULT_AUTO_SOURCES_INTERNATIONAL
                .map(String::from)
                .to_vec(),
            station_selection_strategy: 0,
        }
    }
}

impl SourceSettings {
    /// `_get_state_sources`: known sources in their saved order, or the
    /// region's defaults.
    fn sources(&self, us: bool) -> Vec<String> {
        let (saved, defaults): (&[String], &[&str]) = if us {
            (&self.auto_sources_us, &DEFAULT_AUTO_SOURCES_US)
        } else {
            (
                &self.auto_sources_international,
                &DEFAULT_AUTO_SOURCES_INTERNATIONAL,
            )
        };
        let known: Vec<String> = saved
            .iter()
            .filter(|s| source_label(s).is_some())
            .cloned()
            .collect();
        if known.is_empty() {
            defaults.iter().map(|s| s.to_string()).collect()
        } else {
            known
        }
    }

    /// `build_source_settings_summary_text`.
    pub fn summary_text(&self) -> String {
        let budget = usize::try_from(self.auto_mode_api_budget)
            .ok()
            .and_then(|i| AUTO_MODE_BUDGET_LABELS.get(i))
            .unwrap_or(&AUTO_MODE_BUDGET_LABELS[DEFAULT_BUDGET_INDEX as usize]);
        let strategy = usize::try_from(self.station_selection_strategy)
            .ok()
            .and_then(|i| STATION_STRATEGY_LABELS.get(i))
            .unwrap_or(&STATION_STRATEGY_LABELS[0]);
        let labels = |us| {
            self.sources(us)
                .iter()
                .filter_map(|s| source_label(s))
                .collect::<Vec<_>>()
                .join(", ")
        };
        format!(
            "Automatic mode budget: {budget}. US automatic sources: {}. \
             International automatic sources: {}. NWS station strategy: {strategy}.",
            labels(true),
            labels(false)
        )
    }

    /// What `_run_source_settings_dialog` returns on OK. A region with every
    /// box cleared falls back to Open-Meteo.
    pub fn from_dialog(
        budget: i32,
        strategy: i32,
        us: [bool; 3],
        international: [bool; 2],
    ) -> Self {
        let pick = |names: &[&str], on: &[bool]| {
            let chosen: Vec<String> = names
                .iter()
                .zip(on)
                .filter(|(_, on)| **on)
                .map(|(n, _)| n.to_string())
                .collect();
            if chosen.is_empty() {
                vec!["openmeteo".to_string()]
            } else {
                chosen
            }
        };
        Self {
            auto_mode_api_budget: budget,
            auto_sources_us: pick(&["nws", "openmeteo", "pirateweather"], &us),
            auto_sources_international: pick(&["openmeteo", "pirateweather"], &international),
            station_selection_strategy: strategy,
        }
    }
}

/// `AudioTab.build_event_sound_summary_text`.
pub(crate) fn event_sound_summary_text(states: &[(&str, bool)]) -> String {
    let total = user_mutable_sound_events().count();
    let enabled = states.iter().filter(|(_, on)| *on).count();
    if enabled == total {
        format!("Sounds will play for all {total} selectable event types.")
    } else if enabled == 0 {
        "Sounds are turned off for every selectable event type.".to_string()
    } else {
        format!("Sounds will play for {enabled} of {total} selectable event types.")
    }
}

/// `_build_default_event_sound_states`.
pub(crate) fn default_event_sound_states() -> Vec<(&'static str, bool)> {
    user_mutable_sound_events()
        .map(|(k, _)| (k, true))
        .collect()
}

/// Everything the dialog keeps besides control values.
#[derive(Debug, Clone, Default)]
pub(crate) struct DialogState {
    pub sound_packs: Vec<SoundPack>,
    /// `_specific_alert_sound_packs`.
    pub specific_alert_sound_packs: Vec<String>,
    /// `_event_sound_states`, in `USER_MUTABLE_SOUND_EVENTS` order.
    pub event_sound_states: Vec<(&'static str, bool)>,
    /// `_hidden_muted_sound_events`: known legacy keys kept muted.
    pub hidden_muted_sound_events: Vec<String>,
    pub source_settings: SourceSettings,
    /// `_selected_specific_model`: survives reloads, as in Python.
    pub selected_specific_model: Option<String>,
    /// The model preference choice's items (loads append "Selected: ...").
    pub ai_model_items: Vec<String>,
    /// `GeneralTab._saved_hotkey`.
    pub saved_hotkey: String,
    /// `_original_*_key`, in `GUARDED_API_KEYS` order.
    pub original_keys: [String; 4],
    /// `_loaded_startup_enabled`.
    pub loaded_startup_enabled: bool,
}

/// The value of every Settings control, named after the Python `_controls`
/// keys.
#[derive(Debug, Clone, Default, Serialize)]
pub(crate) struct SettingsForm {
    // General
    pub update_interval: i32,
    pub taskbar_icon_text_enabled: bool,
    pub taskbar_icon_dynamic_enabled: bool,
    pub taskbar_icon_text_format: String,
    pub noaa_radio_hotkey: String,
    // Display
    pub temp_unit: usize,
    pub wind_speed_unit: usize,
    pub round_values: bool,
    pub location_sort_order: usize,
    pub forecast_duration_days: usize,
    pub hourly_forecast_hours: i32,
    pub trend_hours: i32,
    pub show_dewpoint: bool,
    pub show_visibility: bool,
    pub show_uv_index: bool,
    pub show_pressure_trend: bool,
    pub show_impact_summaries: bool,
    pub forecast_time_reference: usize,
    pub time_display_mode: usize,
    pub time_format_12hour: bool,
    pub show_timezone_suffix: bool,
    pub date_format: usize,
    pub verbosity_level: usize,
    pub severe_weather_override: bool,
    pub alert_display_style: usize,
    pub location_buttons_on_top: bool,
    // Alerts
    pub enable_alerts: bool,
    pub alert_notif: bool,
    pub immediate_alert_details_popups: bool,
    pub auto_tune_weather_radio_alerts: bool,
    pub auto_tune_weather_radio_duration_minutes: i32,
    pub alert_radius_type: usize,
    pub notify_extreme: bool,
    pub notify_severe: bool,
    pub notify_moderate: bool,
    pub notify_minor: bool,
    pub notify_unknown: bool,
    pub notify_discussion_update: bool,
    pub notify_daily_climate_report_update: bool,
    pub notify_hwo_update: bool,
    pub notify_sps_issued: bool,
    pub notify_severe_risk_change: bool,
    pub notify_minutely_precipitation_start: bool,
    pub notify_minutely_precipitation_stop: bool,
    pub minutely_precipitation_fast_polling: bool,
    pub precipitation_sensitivity: usize,
    pub notify_precipitation_likelihood: bool,
    pub precipitation_likelihood_threshold: usize,
    /// The hidden timing spins behind "Advanced timing...".
    pub global_cooldown: i32,
    pub per_alert_cooldown: i32,
    pub freshness_window: i32,
    pub max_notifications: i32,
    // Audio
    pub sound_enabled: bool,
    pub specific_alert_sounds_for_pack: bool,
    pub sound_pack: Option<usize>,
    // Data Sources
    pub data_source: usize,
    pub pw_key: String,
    pub airnow_key: String,
    // AI
    pub ai_provider: usize,
    pub openrouter_key: String,
    pub ai_model: usize,
    pub venice_key: String,
    pub venice_model: String,
    pub ai_style: usize,
    pub custom_prompt: String,
    pub custom_instructions: String,
    // Updates
    pub auto_update: bool,
    pub update_channel: usize,
    pub update_check_interval: i32,
    // Advanced
    pub minimize_tray: bool,
    pub minimize_on_startup: bool,
    pub startup: bool,
    pub weather_history: bool,
    pub shortcut_show_main_window: String,
    pub shortcut_hide_main_window: String,
    pub shortcut_read_tray_info: String,

    #[serde(skip)]
    pub state: DialogState,
}

impl SettingsForm {
    /// A freshly built dialog: the constructor defaults of every control
    /// before the first load.
    pub fn new(sound_packs: Vec<SoundPack>) -> Self {
        Self {
            update_interval: 10,
            hourly_forecast_hours: 6,
            trend_hours: 24,
            auto_tune_weather_radio_duration_minutes: 5,
            global_cooldown: 5,
            per_alert_cooldown: 60,
            freshness_window: 15,
            max_notifications: 10,
            update_check_interval: 24,
            state: DialogState {
                sound_packs,
                event_sound_states: default_event_sound_states(),
                ai_model_items: AI_MODEL_CHOICES.map(String::from).to_vec(),
                ..DialogState::default()
            },
            ..Self::default()
        }
    }

    /// `_load_settings`: every tab's `load`, with the startup checkbox showing
    /// the OS registration (`startup_actual`) rather than the saved flag.
    pub fn load(&mut self, s: &AppSettings, startup_actual: bool) {
        self.state.loaded_startup_enabled = startup_actual;
        self.load_general(s);
        self.load_display(s);
        self.load_alerts(s);
        self.load_audio(s);
        self.load_data_sources(s);
        self.load_ai(s);
        self.load_updates(s);
        self.load_advanced(s, startup_actual);
    }

    fn load_general(&mut self, s: &AppSettings) {
        self.update_interval = spin(s.update_interval_minutes, 1, 120);
        self.taskbar_icon_text_enabled = s.taskbar_icon_text_enabled;
        self.taskbar_icon_dynamic_enabled = s.taskbar_icon_dynamic_enabled;
        self.taskbar_icon_text_format = s.taskbar_icon_text_format.clone();
        self.noaa_radio_hotkey = s.noaa_radio_hotkey.clone();
        self.state.saved_hotkey = s.noaa_radio_hotkey.clone();
    }

    fn load_display(&mut self, s: &AppSettings) {
        self.temp_unit = match s.temperature_unit.as_str() {
            "auto" => 0,
            "f" | "fahrenheit" => 1,
            "c" | "celsius" => 2,
            _ => 3,
        };
        self.wind_speed_unit = match s.wind_speed_unit.as_str() {
            "mph" | "mi/h" => 1,
            "km/h" | "kmh" | "kph" => 2,
            "m/s" | "mps" | "ms" => 3,
            _ => 0,
        };
        self.show_dewpoint = s.show_dewpoint;
        self.show_visibility = s.show_visibility;
        self.show_uv_index = s.show_uv_index;
        self.show_pressure_trend = s.show_pressure_trend;
        self.show_impact_summaries = s.show_impact_summaries;
        self.round_values = s.round_values;
        self.forecast_duration_days =
            position(&FORECAST_DURATION_VALUES, &s.forecast_duration_days).unwrap_or(2);
        self.hourly_forecast_hours = spin(s.hourly_forecast_hours, 1, 168);
        self.trend_hours = spin(s.trend_hours, 1, 168);
        self.forecast_time_reference =
            index_of(&FORECAST_TIME_REF_VALUES, &s.forecast_time_reference, 0);
        self.time_display_mode = index_of(&TIME_MODE_VALUES, &s.time_display_mode, 0);
        self.time_format_12hour = s.time_format_12hour;
        self.show_timezone_suffix = s.show_timezone_suffix;
        self.date_format = index_of(&DATE_FORMAT_VALUES, &s.date_format, 0);
        self.verbosity_level = index_of(&VERBOSITY_VALUES, &s.verbosity_level, 1);
        self.severe_weather_override = s.severe_weather_override;
        self.alert_display_style = index_of(&ALERT_DISPLAY_VALUES, &s.alert_display_style, 0);
        self.location_sort_order = index_of(&LOCATION_SORT_VALUES, &s.location_sort_order, 0);
        self.location_buttons_on_top = s.location_buttons_on_top;
    }

    fn load_alerts(&mut self, s: &AppSettings) {
        self.enable_alerts = s.enable_alerts;
        self.alert_notif = s.alert_notifications_enabled;
        self.alert_radius_type = index_of(&RADIUS_TYPE_VALUES, &s.alert_radius_type, 0);
        self.notify_extreme = s.alert_notify_extreme;
        self.notify_severe = s.alert_notify_severe;
        self.notify_moderate = s.alert_notify_moderate;
        self.notify_minor = s.alert_notify_minor;
        self.notify_unknown = s.alert_notify_unknown;
        self.immediate_alert_details_popups = s.immediate_alert_details_popups;
        self.auto_tune_weather_radio_alerts = s.auto_tune_weather_radio_alerts;
        self.auto_tune_weather_radio_duration_minutes =
            spin(s.auto_tune_weather_radio_duration_minutes, 1, 60);
        self.global_cooldown = spin(s.alert_global_cooldown_minutes, 0, 60);
        self.per_alert_cooldown = spin(s.alert_per_alert_cooldown_minutes, 0, 1440);
        self.freshness_window = spin(s.alert_freshness_window_minutes, 0, 120);
        self.max_notifications = spin(s.alert_max_notifications_per_hour, 1, 100);
        self.notify_discussion_update = s.notify_discussion_update;
        self.notify_daily_climate_report_update = s.notify_daily_climate_report_update;
        self.notify_hwo_update = s.notify_hwo_update;
        self.notify_sps_issued = s.notify_sps_issued;
        self.notify_severe_risk_change = s.notify_severe_risk_change;
        self.notify_minutely_precipitation_start = s.notify_minutely_precipitation_start;
        self.notify_minutely_precipitation_stop = s.notify_minutely_precipitation_stop;
        self.minutely_precipitation_fast_polling = s.minutely_precipitation_fast_polling;
        self.precipitation_sensitivity =
            index_of(&SENSITIVITY_VALUES, &s.precipitation_sensitivity, 0);
        self.notify_precipitation_likelihood = s.notify_precipitation_likelihood;
        self.precipitation_likelihood_threshold = position(
            &LIKELIHOOD_THRESHOLD_VALUES,
            &s.precipitation_likelihood_threshold,
        )
        .unwrap_or(0);
    }

    fn load_audio(&mut self, s: &AppSettings) {
        self.sound_enabled = s.sound_enabled;
        self.state.specific_alert_sound_packs = s.specific_alert_sound_packs.clone();
        let packs = &self.state.sound_packs;
        self.sound_pack = packs
            .iter()
            .position(|p| p.id == s.sound_pack)
            .or((!packs.is_empty()).then_some(0));
        self.refresh_specific_alert_sounds_control();
        self.set_event_sound_states(&s.muted_sound_events);
    }

    fn load_data_sources(&mut self, s: &AppSettings) {
        self.data_source = index_of(&SOURCE_VALUES, &s.data_source, 0);
        self.pw_key = s.pirate_weather_api_key.clone();
        self.airnow_key = s.airnow_api_key.clone();
        self.state.original_keys[0] = s.pirate_weather_api_key.clone();
        self.state.original_keys[1] = s.airnow_api_key.clone();
        let strategy = index_of(&STATION_STRATEGY_VALUES, &s.station_selection_strategy, 0);
        let budget = position(&AUTO_MODE_BUDGET_VALUES, &s.auto_mode_api_budget.as_str())
            .map_or(DEFAULT_BUDGET_INDEX, |i| i as i32);
        let or_default = |saved: &[String], default: &[&str]| {
            if saved.is_empty() {
                default.iter().map(|s| s.to_string()).collect()
            } else {
                saved.to_vec()
            }
        };
        self.state.source_settings = SourceSettings {
            auto_mode_api_budget: budget,
            auto_sources_us: or_default(&s.auto_sources_us, &DEFAULT_AUTO_SOURCES_US),
            auto_sources_international: or_default(
                &s.auto_sources_international,
                &DEFAULT_AUTO_SOURCES_INTERNATIONAL,
            ),
            station_selection_strategy: strategy as i32,
        };
    }

    fn load_ai(&mut self, s: &AppSettings) {
        self.ai_provider = usize::from(s.ai_provider == "venice");
        self.venice_key = s.venice_api_key.clone();
        self.state.original_keys[3] = s.venice_api_key.clone();
        self.venice_model = if s.venice_model.is_empty() {
            DEFAULT_VENICE_MODEL.to_string()
        } else {
            s.venice_model.clone()
        };
        self.openrouter_key = s.openrouter_api_key.clone();
        self.state.original_keys[2] = s.openrouter_api_key.clone();
        let model = s.ai_model_preference.as_str();
        self.ai_model = match model {
            "openrouter/free" => 0,
            "auto" | "openrouter/auto" => 1,
            _ => {
                let short = model.rsplit('/').next().unwrap_or(model);
                self.state.ai_model_items.push(format!("Selected: {short}"));
                self.state.selected_specific_model = Some(model.to_string());
                2
            }
        };
        self.ai_style = index_of(&STYLE_VALUES, &s.ai_explanation_style, 1);
        self.custom_prompt = s.custom_system_prompt.clone().unwrap_or_default();
        self.custom_instructions = s.custom_instructions.clone().unwrap_or_default();
    }

    fn load_updates(&mut self, s: &AppSettings) {
        self.auto_update = s.auto_update_enabled;
        self.update_channel = usize::from(s.update_channel != "stable");
        self.update_check_interval = spin(s.update_check_interval_hours, 1, 168);
    }

    fn load_advanced(&mut self, s: &AppSettings, startup_actual: bool) {
        self.minimize_tray = s.minimize_to_tray;
        self.minimize_on_startup = s.minimize_on_startup;
        self.shortcut_show_main_window = s.shortcut_show_main_window.clone();
        self.shortcut_hide_main_window = s.shortcut_hide_main_window.clone();
        self.shortcut_read_tray_info = s.shortcut_read_tray_info.clone();
        self.update_minimize_on_startup_state();
        self.startup = startup_actual;
        self.weather_history = s.weather_history_enabled;
    }

    /// `_update_minimize_on_startup_state`: starting minimized needs the tray.
    pub fn update_minimize_on_startup_state(&mut self) {
        if !self.minimize_tray {
            self.minimize_on_startup = false;
        }
    }

    /// `get_selected_temperature_unit`.
    pub fn selected_temperature_unit(&self) -> &'static str {
        TEMP_VALUES.get(self.temp_unit).unwrap_or(&"both")
    }

    /// `get_selected_wind_speed_unit`.
    pub fn selected_wind_speed_unit(&self) -> &'static str {
        WIND_SPEED_UNIT_VALUES
            .get(self.wind_speed_unit)
            .unwrap_or(&"auto")
    }

    /// `_get_selected_sound_pack`.
    pub fn selected_sound_pack(&self) -> &str {
        self.sound_pack
            .and_then(|i| self.state.sound_packs.get(i))
            .map_or("default", |p| p.id.as_str())
    }

    fn pack_uses_specific_alert_sounds(&self, id: &str) -> bool {
        self.state
            .sound_packs
            .iter()
            .any(|p| p.id == id && p.specific_alert_sounds)
    }

    /// Whether "Use specific alert sounds for this sound pack" can be changed:
    /// packs that already map specific alerts use them automatically.
    pub fn specific_alert_sounds_editable(&self) -> bool {
        !self.pack_uses_specific_alert_sounds(self.selected_sound_pack())
    }

    /// `_refresh_specific_alert_sounds_control`.
    pub fn refresh_specific_alert_sounds_control(&mut self) {
        let pack = self.selected_sound_pack().to_string();
        self.specific_alert_sounds_for_pack = self.pack_uses_specific_alert_sounds(&pack)
            || self.state.specific_alert_sound_packs.contains(&pack);
    }

    /// `set_event_sound_states`.
    pub fn set_event_sound_states(&mut self, muted: &[String]) {
        let muted = normalize_known_muted_sound_events(muted);
        self.state.hidden_muted_sound_events = muted
            .iter()
            .filter(|e| !is_user_mutable_sound_event(e))
            .cloned()
            .collect();
        self.state.event_sound_states = user_mutable_sound_events()
            .map(|(k, _)| (k, !muted.iter().any(|m| m == k)))
            .collect();
    }

    /// `_get_muted_sound_events`: hidden legacy keys first, then the
    /// unchecked events in display order.
    fn muted_sound_events(&self) -> Vec<String> {
        let mut muted = self.state.hidden_muted_sound_events.clone();
        for (key, on) in &self.state.event_sound_states {
            if !on && !muted.iter().any(|m| m == key) {
                muted.push(key.to_string());
            }
        }
        muted
    }

    pub fn event_sound_summary(&self) -> String {
        event_sound_summary_text(&self.state.event_sound_states)
    }

    /// Whether the Pirate Weather key section shows (Automatic or Pirate
    /// Weather selected).
    pub fn pirate_weather_section_shown(&self) -> bool {
        matches!(self.data_source, 0 | 3)
    }

    /// `_get_ai_model_preference`.
    fn ai_model_preference(&self) -> String {
        match (self.ai_model, &self.state.selected_specific_model) {
            (1, _) => "auto".to_string(),
            (2, Some(model)) if !model.is_empty() => model.clone(),
            _ => "openrouter/free".to_string(),
        }
    }

    /// Model Browser result for the OpenRouter preference (`_on_browse_models`).
    pub fn select_browsed_model(&mut self, model_id: &str) {
        match model_id {
            "openrouter/free" => self.ai_model = 0,
            "openrouter/auto" => self.ai_model = 1,
            _ => {
                let short = model_id.rsplit('/').next().unwrap_or(model_id);
                let display = format!("Selected: {short}");
                match self.state.ai_model_items.get_mut(2) {
                    Some(item) => *item = display,
                    None => self.state.ai_model_items.push(display),
                }
                self.ai_model = 2;
                self.state.selected_specific_model = Some(model_id.to_string());
            }
        }
    }

    /// `GeneralTab._collect_hotkey`: the canonical hotkey, or the previous
    /// one plus the warning Python shows when the typed combo is unusable.
    fn collect_hotkey(&self) -> (String, Option<String>) {
        let typed = self.noaa_radio_hotkey.trim();
        if typed.is_empty() {
            return (String::new(), None);
        }
        match normalize_hotkey(typed) {
            Ok(hotkey) => (hotkey, None),
            Err(_) => {
                tracing::warn!("Rejected invalid NOAA Weather Radio hotkey {typed:?}");
                (
                    self.state.saved_hotkey.clone(),
                    Some(format!(
                        "{} is not a usable hotkey. Use one or more of Ctrl, Alt, Shift and \
                         Win plus a letter, digit or function key, for example Ctrl+Alt+Shift+R. \
                         Keeping the previous hotkey.",
                        py_repr(typed)
                    )),
                )
            }
        }
    }

    /// `_collect_tab_values`: every tab's `save()` merged into one settings
    /// dict, plus the "Invalid hotkey" warning Python shows while collecting.
    pub fn collect(&self) -> (Map<String, Value>, Option<String>) {
        let (hotkey, hotkey_warning) = self.collect_hotkey();

        let pack = self.selected_sound_pack().to_string();
        let mut specific: Vec<String> = self.state.specific_alert_sound_packs.clone();
        specific.retain(|p| *p != pack);
        if !self.pack_uses_specific_alert_sounds(&pack) && self.specific_alert_sounds_for_pack {
            specific.push(pack.clone());
        }
        specific.sort();
        specific.dedup();

        let source = &self.state.source_settings;
        let us = source.sources(true);
        let international = source.sources(false);
        let strategy = STATION_STRATEGY_VALUES[source.station_selection_strategy.max(0) as usize];
        let budget = AUTO_MODE_BUDGET_VALUES
            [(source.auto_mode_api_budget.max(0) as usize).min(AUTO_MODE_BUDGET_VALUES.len() - 1)];
        let optional = |text: &str| {
            if text.is_empty() {
                Value::Null
            } else {
                Value::from(text)
            }
        };
        let venice_model = self.venice_model.trim();

        // Each tab's `save()`, merged in notebook order.
        let tabs = [
            // General
            json!({
                "update_interval_minutes": self.update_interval,
                "taskbar_icon_text_enabled": self.taskbar_icon_text_enabled,
                "taskbar_icon_dynamic_enabled": self.taskbar_icon_dynamic_enabled,
                "taskbar_icon_text_format": self.taskbar_icon_text_format,
                "noaa_radio_hotkey": hotkey,
            }),
            // Display
            json!({
                "temperature_unit": TEMP_VALUES[self.temp_unit],
                "wind_speed_unit": WIND_SPEED_UNIT_VALUES[self.wind_speed_unit],
                "show_dewpoint": self.show_dewpoint,
                "show_visibility": self.show_visibility,
                "show_uv_index": self.show_uv_index,
                "show_pressure_trend": self.show_pressure_trend,
                "show_impact_summaries": self.show_impact_summaries,
                "round_values": self.round_values,
                "forecast_duration_days": FORECAST_DURATION_VALUES[self.forecast_duration_days],
                "hourly_forecast_hours": self.hourly_forecast_hours,
                "trend_hours": self.trend_hours,
                "forecast_time_reference": FORECAST_TIME_REF_VALUES[self.forecast_time_reference],
                "time_display_mode": TIME_MODE_VALUES[self.time_display_mode],
                "time_format_12hour": self.time_format_12hour,
                "show_timezone_suffix": self.show_timezone_suffix,
                "date_format": DATE_FORMAT_VALUES[self.date_format],
                "verbosity_level": VERBOSITY_VALUES[self.verbosity_level],
                "severe_weather_override": self.severe_weather_override,
                "alert_display_style": ALERT_DISPLAY_VALUES[self.alert_display_style],
                "location_sort_order": LOCATION_SORT_VALUES[self.location_sort_order],
                "location_buttons_on_top": self.location_buttons_on_top,
            }),
            // Alerts
            json!({
                "enable_alerts": self.enable_alerts,
                "alert_notifications_enabled": self.alert_notif,
                "alert_radius_type": RADIUS_TYPE_VALUES[self.alert_radius_type],
                "alert_notify_extreme": self.notify_extreme,
                "alert_notify_severe": self.notify_severe,
                "alert_notify_moderate": self.notify_moderate,
                "alert_notify_minor": self.notify_minor,
                "alert_notify_unknown": self.notify_unknown,
                "immediate_alert_details_popups": self.immediate_alert_details_popups,
                "auto_tune_weather_radio_alerts": self.auto_tune_weather_radio_alerts,
                "auto_tune_weather_radio_duration_minutes": self.auto_tune_weather_radio_duration_minutes,
                "alert_global_cooldown_minutes": self.global_cooldown,
                "alert_per_alert_cooldown_minutes": self.per_alert_cooldown,
                "alert_freshness_window_minutes": self.freshness_window,
                "alert_max_notifications_per_hour": self.max_notifications,
                "notify_discussion_update": self.notify_discussion_update,
                "notify_daily_climate_report_update": self.notify_daily_climate_report_update,
                "notify_hwo_update": self.notify_hwo_update,
                "notify_sps_issued": self.notify_sps_issued,
                "notify_severe_risk_change": self.notify_severe_risk_change,
                "notify_minutely_precipitation_start": self.notify_minutely_precipitation_start,
                "notify_minutely_precipitation_stop": self.notify_minutely_precipitation_stop,
                "minutely_precipitation_fast_polling": self.minutely_precipitation_fast_polling,
                "precipitation_sensitivity": SENSITIVITY_VALUES[self.precipitation_sensitivity],
                "notify_precipitation_likelihood": self.notify_precipitation_likelihood,
                "precipitation_likelihood_threshold":
                    LIKELIHOOD_THRESHOLD_VALUES[self.precipitation_likelihood_threshold],
            }),
            // Audio
            json!({
                "sound_enabled": self.sound_enabled,
                "sound_pack": pack,
                "muted_sound_events": self.muted_sound_events(),
                "specific_alert_sound_packs": specific,
            }),
            // Data Sources
            json!({
                "data_source": SOURCE_VALUES[self.data_source],
                "pirate_weather_api_key": self.pw_key,
                "airnow_api_key": self.airnow_key,
                "source_priority_us": us,
                "source_priority_international": international,
                "auto_mode_api_budget": budget,
                "auto_sources_us": us,
                "auto_sources_international": international,
                "openmeteo_weather_model": "best_match",
                "station_selection_strategy": strategy,
            }),
            // AI
            json!({
                "ai_provider": if self.ai_provider == 1 { "venice" } else { "openrouter" },
                "venice_api_key": self.venice_key.trim(),
                "venice_model": if venice_model.is_empty() { DEFAULT_VENICE_MODEL } else { venice_model },
                "openrouter_api_key": self.openrouter_key,
                "ai_model_preference": self.ai_model_preference(),
                "ai_explanation_style": STYLE_VALUES[self.ai_style],
                "custom_system_prompt": optional(&self.custom_prompt),
                "custom_instructions": optional(&self.custom_instructions),
            }),
            // Updates
            json!({
                "auto_update_enabled": self.auto_update,
                "update_channel": if self.update_channel == 0 { "stable" } else { "nightly" },
                "update_check_interval_hours": self.update_check_interval,
            }),
            // Advanced
            json!({
                "minimize_to_tray": self.minimize_tray,
                "minimize_on_startup": self.minimize_on_startup,
                "shortcut_show_main_window": self.shortcut_show_main_window,
                "shortcut_hide_main_window": self.shortcut_hide_main_window,
                "shortcut_read_tray_info": self.shortcut_read_tray_info,
                "startup_enabled": self.startup,
                "weather_history_enabled": self.weather_history,
            }),
        ];
        let mut values = Map::new();
        for tab in tabs {
            let Value::Object(tab) = tab else {
                unreachable!("json! object literal")
            };
            values.extend(tab);
        }
        (values, hotkey_warning)
    }

    /// The API key guard in `_save_settings`: a key that loaded non-empty and
    /// is now blank is only dropped when the user edited that field
    /// (`cleared`); otherwise the stored key is kept.
    pub fn guard_api_keys(&self, values: &mut Map<String, Value>, cleared: [bool; 4]) {
        for (i, (setting, _)) in GUARDED_API_KEYS.iter().enumerate() {
            let blank = values
                .get(*setting)
                .and_then(Value::as_str)
                .is_none_or(str::is_empty);
            if blank && !self.state.original_keys[i].is_empty() {
                if cleared[i] {
                    tracing::info!("API key {setting} explicitly cleared by user.");
                } else {
                    tracing::warn!(
                        "Skipping empty {setting} save — original value was non-empty; \
                         keyring may have failed to load. Existing keyring value preserved."
                    );
                    values.remove(*setting);
                }
            }
        }
    }

    /// `_validate_window_tray_shortcuts`: rewrites each shortcut field in its
    /// canonical spelling and returns (setting, message) for the first
    /// problem. The radio hotkey counts as taken.
    pub fn validate_window_tray_shortcuts(&mut self) -> Option<(&'static str, String)> {
        let mut seen: Vec<(String, &str)> = Vec::new();
        if let Ok(radio) = normalize_hotkey(&self.noaa_radio_hotkey) {
            if !radio.is_empty() {
                seen.push((radio, "NOAA Weather Radio hotkey"));
            }
        }
        for preference in WINDOW_TRAY_SHORTCUTS {
            let field = self.shortcut_field(preference.setting_name);
            let normalized = match normalize_shortcut_text(field, true) {
                Ok(n) => n,
                Err(e) => {
                    return Some((
                        preference.setting_name,
                        format!("{}: {e}", preference.label),
                    ))
                }
            };
            *self.shortcut_field(preference.setting_name) = normalized.clone();
            if normalized.is_empty() {
                continue;
            }
            let parts: Vec<&str> = normalized.split('+').collect();
            let modifiers = &parts[..parts.len() - 1];
            if !modifiers.iter().any(|m| matches!(*m, "Ctrl" | "Alt")) {
                return Some((
                    preference.setting_name,
                    format!(
                        "{} must include Ctrl or Alt to avoid capturing typing keys.",
                        preference.label
                    ),
                ));
            }
            if let Some(used_for) = reserved_shortcut_use(&normalized) {
                return Some((
                    preference.setting_name,
                    format!(
                        "{} cannot use {normalized} because that shortcut already {used_for}.",
                        preference.label
                    ),
                ));
            }
            if let Some((_, existing)) = seen.iter().find(|(combo, _)| *combo == normalized) {
                return Some((
                    preference.setting_name,
                    format!(
                        "{} duplicates {existing} ({normalized}). Choose a different shortcut \
                         or leave one field blank.",
                        preference.label
                    ),
                ));
            }
            seen.push((normalized, preference.label));
        }
        None
    }

    fn shortcut_field(&mut self, setting_name: &str) -> &mut String {
        match setting_name {
            "shortcut_show_main_window" => &mut self.shortcut_show_main_window,
            "shortcut_hide_main_window" => &mut self.shortcut_hide_main_window,
            _ => &mut self.shortcut_read_tray_info,
        }
    }
}

fn index_of(values: &[&str], value: &str, default: usize) -> usize {
    position(values, &value).unwrap_or(default)
}

/// `update_settings` for the non-secret part: every collected value lands on
/// the settings (`setattr`); API key fields not in `values` keep their
/// current value. Unknown keys in `extra` survive.
pub(crate) fn apply_settings_dict(
    settings: &mut AppSettings,
    values: &Map<String, Value>,
) -> Result<(), serde_json::Error> {
    let mut merged = serde_json::to_value(&*settings)?;
    let object = merged
        .as_object_mut()
        .expect("settings serialize to an object");
    for (key, value) in values {
        object.insert(key.clone(), value.clone());
    }
    let mut updated: AppSettings = serde_json::from_value(merged)?;
    for name in aw_store::secrets::API_KEY_NAMES {
        let keep = !values.contains_key(name);
        let old = aw_store::secrets::api_key_mut(settings, name).expect("known key");
        let new = aw_store::secrets::api_key_mut(&mut updated, name).expect("known key");
        if keep {
            *new = std::mem::take(old);
        }
    }
    *settings = updated;
    Ok(())
}
