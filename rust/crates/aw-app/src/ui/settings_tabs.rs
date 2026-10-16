//! The eight Settings pages, built control by control in the order, with the
//! labels and names, of `ui/dialogs/settings_tabs/*.py` and the layout
//! helpers of `settings_dialog_core.py`. Screen readers name each control
//! from the StaticText created just before it, so creation order matters.

use wxdragon::prelude::*;

use super::settings_form::*;

/// `_wrap_static_text`.
const WRAP_WIDTH: i32 = 620;

fn text<P: WxWidget>(parent: &P, label: &str) -> StaticText {
    StaticText::builder(parent).with_label(label).build()
}

fn wrapped<P: WxWidget>(parent: &P, label: &str) -> StaticText {
    let t = text(parent, label);
    t.wrap(WRAP_WIDTH);
    t
}

/// `add_help_text`.
fn add_help_text<P: WxWidget>(
    parent: &P,
    sizer: &BoxSizer,
    label: &str,
    border: i32,
) -> StaticText {
    let t = wrapped(parent, label);
    sizer.add(
        &t,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom | SizerFlag::Expand,
        border,
    );
    t
}

/// `create_section`: a heading, then the sizer its controls go into. No
/// StaticBox, so the heading is not read as part of the first control.
fn create_section<P: WxWidget>(parent: &P, parent_sizer: &BoxSizer, title: &str) -> BoxSizer {
    let heading = wrapped(parent, title);
    parent_sizer.add(
        &heading,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top | SizerFlag::Expand,
        5,
    );
    let section = BoxSizer::builder(Orientation::Vertical).build();
    parent_sizer.add_sizer(
        &section,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        5,
    );
    section
}

/// `add_labeled_control_row`: the label is created before the control.
fn labeled<P: WxWidget, W: WxWidget>(
    parent: &P,
    sizer: &BoxSizer,
    label: &str,
    expand: bool,
    bottom: i32,
    make: impl FnOnce(&P) -> W,
) -> (StaticText, W) {
    let row = BoxSizer::builder(Orientation::Horizontal).build();
    let label = text(parent, label);
    row.add(
        &label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        10,
    );
    let control = make(parent);
    if expand {
        row.add(&control, 1, SizerFlag::Expand, 0);
    } else {
        row.add(&control, 0, SizerFlag::empty(), 0);
    }
    sizer.add_sizer(
        &row,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom | SizerFlag::Expand,
        bottom,
    );
    (label, control)
}

/// A label + control row added by hand (Python builds these inline).
fn row<P: WxWidget, W: WxWidget>(
    parent: &P,
    sizer: &BoxSizer,
    label: &str,
    flags: SizerFlag,
    border: i32,
    make: impl FnOnce(&P) -> W,
) -> W {
    let row = BoxSizer::builder(Orientation::Horizontal).build();
    let label = text(parent, label);
    row.add(
        &label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        10,
    );
    let control = make(parent);
    row.add(&control, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(&row, 0, flags, border);
    control
}

fn choice<P: WxWidget>(parent: &P, choices: &[&str]) -> Choice {
    Choice::builder(parent)
        .with_choices(choices.iter().map(|c| c.to_string()).collect())
        .build()
}

fn spin<P: WxWidget>(parent: &P, min: i32, max: i32, initial: i32) -> SpinCtrl {
    SpinCtrl::builder(parent)
        .with_range(min, max)
        .with_initial_value(initial)
        .build()
}

fn check<P: WxWidget>(parent: &P, label: &str) -> CheckBox {
    CheckBox::builder(parent).with_label(label).build()
}

fn button<P: WxWidget>(parent: &P, label: &str) -> Button {
    Button::builder(parent).with_label(label).build()
}

fn text_ctrl<P: WxWidget>(parent: &P, width: i32, style: TextCtrlStyle) -> TextCtrl {
    TextCtrl::builder(parent)
        .with_size(Size::new(width, -1))
        .with_style(style)
        .build()
}

const LRB: SizerFlag = SizerFlag::Left
    .union(SizerFlag::Right)
    .union(SizerFlag::Bottom);
const LRBE: SizerFlag = LRB.union(SizerFlag::Expand);

fn page(notebook: &Notebook) -> (ScrolledWindow, BoxSizer) {
    let panel = ScrolledWindow::builder(notebook)
        .with_style(ScrolledWindowStyle::HScroll | ScrolledWindowStyle::VScroll)
        .build();
    panel.set_scroll_rate(0, 20);
    (panel, BoxSizer::builder(Orientation::Vertical).build())
}

fn finish_page(notebook: &Notebook, panel: ScrolledWindow, sizer: BoxSizer, label: &str) {
    panel.set_sizer(sizer, true);
    notebook.add_page(&panel, label, false, None);
}

/// The Pirate Weather part of Provider API keys, shown only for the
/// Automatic and Pirate Weather sources.
#[derive(Clone, Copy)]
pub(crate) struct PirateWeatherSection {
    heading: StaticText,
    label: StaticText,
    pub key: TextCtrl,
    pub get_key: Button,
    pub validate_key: Button,
    help: StaticText,
}

impl PirateWeatherSection {
    pub fn show(&self, shown: bool) {
        self.heading.show(shown);
        self.label.show(shown);
        self.key.show(shown);
        self.get_key.show(shown);
        self.validate_key.show(shown);
        self.help.show(shown);
    }
}

/// Every Settings control, named after Python's `_controls` keys.
#[derive(Clone, Copy)]
pub(crate) struct Controls {
    pub pages: [ScrolledWindow; 8],
    // General
    pub update_interval: SpinCtrl,
    pub taskbar_icon_text_enabled: CheckBox,
    pub taskbar_icon_dynamic_enabled: CheckBox,
    pub taskbar_icon_text_format: TextCtrl,
    pub taskbar_icon_text_format_dialog: Button,
    pub noaa_radio_hotkey: TextCtrl,
    // Display
    pub temp_unit: Choice,
    pub wind_speed_unit: Choice,
    pub round_values: CheckBox,
    pub location_sort_order: Choice,
    pub forecast_duration_days: Choice,
    pub hourly_forecast_hours: SpinCtrl,
    pub trend_hours: SpinCtrl,
    pub show_dewpoint: CheckBox,
    pub show_visibility: CheckBox,
    pub show_uv_index: CheckBox,
    pub show_pressure_trend: CheckBox,
    pub show_impact_summaries: CheckBox,
    pub forecast_time_reference: Choice,
    pub time_display_mode: Choice,
    pub time_format_12hour: CheckBox,
    pub show_timezone_suffix: CheckBox,
    pub date_format: Choice,
    pub verbosity_level: Choice,
    pub severe_weather_override: CheckBox,
    pub alert_display_style: Choice,
    pub location_buttons_on_top: CheckBox,
    // Alerts
    pub enable_alerts: CheckBox,
    pub alert_notif: CheckBox,
    pub immediate_alert_details_popups: CheckBox,
    pub auto_tune_weather_radio_alerts: CheckBox,
    pub auto_tune_weather_radio_duration_minutes: SpinCtrl,
    pub alert_radius_type: Choice,
    pub notify_extreme: CheckBox,
    pub notify_severe: CheckBox,
    pub notify_moderate: CheckBox,
    pub notify_minor: CheckBox,
    pub notify_unknown: CheckBox,
    pub notify_discussion_update: CheckBox,
    pub notify_daily_climate_report_update: CheckBox,
    pub notify_hwo_update: CheckBox,
    pub notify_sps_issued: CheckBox,
    pub notify_severe_risk_change: CheckBox,
    pub notify_minutely_precipitation_start: CheckBox,
    pub notify_minutely_precipitation_stop: CheckBox,
    pub minutely_precipitation_fast_polling: CheckBox,
    pub precipitation_sensitivity: Choice,
    pub notify_precipitation_likelihood: CheckBox,
    pub precipitation_likelihood_threshold: Choice,
    pub max_notifications: SpinCtrl,
    pub advanced_timing: Button,
    // Audio
    pub sound_enabled: CheckBox,
    pub specific_alert_sounds_for_pack: CheckBox,
    pub sound_pack: Choice,
    pub play_sample: Button,
    pub manage_sound_packs: Button,
    pub event_sounds_summary: StaticText,
    pub configure_event_sounds: Button,
    // Data Sources
    pub data_source: Choice,
    pub source_settings_summary: TextCtrl,
    pub configure_source_settings: Button,
    pub pirate_weather: PirateWeatherSection,
    pub airnow_key: TextCtrl,
    pub get_airnow_key: Button,
    pub validate_airnow_key: Button,
    // AI
    pub ai_provider: Choice,
    pub openrouter_panel: Panel,
    pub openrouter_key: TextCtrl,
    pub validate_openrouter_key: Button,
    pub ai_model: Choice,
    pub browse_models: Button,
    pub venice_panel: Panel,
    pub venice_key: TextCtrl,
    pub validate_venice_key: Button,
    pub get_venice_key: Button,
    pub venice_model: TextCtrl,
    pub browse_venice_models: Button,
    pub ai_style: Choice,
    pub custom_prompt: TextCtrl,
    pub reset_prompt: Button,
    pub custom_instructions: TextCtrl,
    // Updates
    pub auto_update: CheckBox,
    pub update_channel: Choice,
    pub update_check_interval: SpinCtrl,
    pub check_updates: Button,
    pub update_status: StaticText,
    // Advanced
    pub minimize_tray: CheckBox,
    pub minimize_on_startup: CheckBox,
    pub startup: CheckBox,
    pub weather_history: CheckBox,
    pub shortcut_show_main_window: TextCtrl,
    pub shortcut_hide_main_window: TextCtrl,
    pub shortcut_read_tray_info: TextCtrl,
    pub export_settings: Button,
    pub import_settings: Button,
    pub export_api_keys: Button,
    pub import_api_keys: Button,
    pub open_config_dir: Button,
    pub open_installed_config_dir: Button,
    pub copy_installed_config: Option<Button>,
    pub open_soundpacks_dir: Button,
    pub reset_defaults: Button,
    pub full_reset: Button,
}

/// Page labels in notebook order (`_TAB_DEFINITIONS`).
pub(crate) const TAB_LABELS: [&str; 8] = [
    "General",
    "Display",
    "Alerts",
    "Audio",
    "Data Sources",
    "AI",
    "Updates",
    "Advanced",
];
pub(crate) const ADVANCED_PAGE: usize = 7;

/// Build every page into `notebook`. The copy-to-portable button exists
/// only in portable mode.
pub(crate) fn build(notebook: &Notebook, sound_pack_names: &[String], portable: bool) -> Controls {
    // --- General (`settings_tabs/general.py`) ---
    let (general, sizer) = page(notebook);
    add_help_text(
        &general,
        &sizer,
        "Choose how often AccessiWeather refreshes and what appears on the tray icon.",
        5,
    );
    let refresh_section = create_section(&general, &sizer, "Weather refresh");
    let (_, update_interval) = labeled(
        &general,
        &refresh_section,
        "Refresh weather every (minutes):",
        false,
        8,
        |p| spin(p, 1, 120, 10),
    );
    let tray_section = create_section(&general, &sizer, "Tray icon text");
    let taskbar_icon_text_enabled = check(&general, "Show weather text on the tray icon");
    tray_section.add(&taskbar_icon_text_enabled, 0, LRBE, 10);
    let taskbar_icon_dynamic_enabled = check(&general, "Update tray text as conditions change");
    tray_section.add(&taskbar_icon_dynamic_enabled, 0, LRBE, 10);
    let (_, taskbar_icon_text_format) = labeled(
        &general,
        &tray_section,
        "Current tray text format:",
        true,
        8,
        |p| text_ctrl(p, 320, TextCtrlStyle::ReadOnly),
    );
    let taskbar_icon_text_format_dialog = button(&general, "Edit tray text format...");
    tray_section.add(&taskbar_icon_text_format_dialog, 0, LRB, 10);
    let hotkey_section = create_section(&general, &sizer, "System-wide hotkey");
    let (_, noaa_radio_hotkey) = labeled(
        &general,
        &hotkey_section,
        "NOAA Weather Radio play/stop hotkey (for example Ctrl+Alt+Shift+R, leave blank to turn off):",
        true,
        8,
        |p| text_ctrl(p, 320, TextCtrlStyle::Default),
    );
    finish_page(notebook, general, sizer, TAB_LABELS[0]);

    // --- Display (`settings_tabs/display.py`) ---
    let (display, sizer) = page(notebook);
    add_help_text(
        &display,
        &sizer,
        "Choose what weather details appear and how forecast times and units are shown.",
        5,
    );
    let temperature_section = create_section(&display, &sizer, "Temperature units");
    let (_, temp_unit) = labeled(
        &display,
        &temperature_section,
        "Temperature units:",
        false,
        8,
        |p| choice(p, &TEMP_UNIT_CHOICES),
    );
    let (_, wind_speed_unit) = labeled(
        &display,
        &temperature_section,
        "Wind speed units:",
        false,
        8,
        |p| choice(p, &WIND_SPEED_UNIT_CHOICES),
    );
    let round_values = check(&display, "Show values as whole numbers when possible");
    temperature_section.add(&round_values, 0, LRBE, 10);
    let saved_locations_section = create_section(&display, &sizer, "Saved locations");
    let (_, location_sort_order) = labeled(
        &display,
        &saved_locations_section,
        "Saved location order:",
        false,
        8,
        |p| choice(p, &LOCATION_SORT_CHOICES),
    );
    let forecast_section = create_section(&display, &sizer, "Forecast range");
    let forecast_duration_days = row(
        &display,
        &forecast_section,
        "Daily forecast range:",
        LRBE,
        8,
        |p| choice(p, &FORECAST_DURATION_CHOICES),
    );
    let hourly_forecast_hours = row(
        &display,
        &forecast_section,
        "Hourly forecast range (hours):",
        LRBE,
        8,
        |p| spin(p, 1, 168, 6),
    );
    let trend_hours = row(
        &display,
        &forecast_section,
        "Pressure outlook range (hours):",
        LRBE,
        8,
        |p| spin(p, 1, 168, 24),
    );
    let details_section = create_section(&display, &sizer, "Extra weather details");
    let show_dewpoint = check(&display, "Show dew point");
    details_section.add(&show_dewpoint, 0, LRB, 10);
    let show_visibility = check(&display, "Show visibility");
    details_section.add(&show_visibility, 0, LRB, 10);
    let show_uv_index = check(&display, "Show UV index");
    details_section.add(&show_uv_index, 0, LRB, 10);
    let show_pressure_trend = check(&display, "Show pressure trend");
    details_section.add(&show_pressure_trend, 0, LRB, 10);
    let show_impact_summaries = check(
        &display,
        "Show impact summaries for outdoor, driving, and allergy conditions",
    );
    details_section.add(&show_impact_summaries, 0, LRBE, 10);
    let time_section = create_section(&display, &sizer, "Time display");
    let (_, forecast_time_reference) = labeled(
        &display,
        &time_section,
        "Forecast times are based on:",
        false,
        8,
        |p| choice(p, &FORECAST_TIME_REF_CHOICES),
    );
    let (_, time_display_mode) =
        labeled(&display, &time_section, "Show times as:", false, 8, |p| {
            choice(p, &TIME_MODE_CHOICES)
        });
    let time_format_12hour = check(&display, "Use 12-hour time format (for example, 3:00 PM)");
    time_section.add(&time_format_12hour, 0, LRBE, 10);
    let show_timezone_suffix = check(
        &display,
        "Show timezone abbreviations (for example, EST or UTC)",
    );
    time_section.add(&show_timezone_suffix, 0, LRBE, 10);
    let (_, date_format) = labeled(&display, &time_section, "Date format:", false, 8, |p| {
        choice(p, &DATE_FORMAT_CHOICES)
    });
    let priority_section = create_section(&display, &sizer, "Reading priority");
    let (_, verbosity_level) = labeled(
        &display,
        &priority_section,
        "Verbosity level:",
        false,
        8,
        |p| choice(p, &VERBOSITY_CHOICES),
    );
    let severe_weather_override =
        check(&display, "Automatically prioritize severe weather details");
    priority_section.add(&severe_weather_override, 0, LRBE, 10);
    let alert_display_section = create_section(&display, &sizer, "Alert display");
    let (_, alert_display_style) = labeled(
        &display,
        &alert_display_section,
        "Alert display style:",
        false,
        8,
        |p| choice(p, &ALERT_DISPLAY_CHOICES),
    );
    let layout_section = create_section(&display, &sizer, "Location buttons");
    let location_buttons_on_top = check(
        &display,
        "Show Add, Edit, and Remove Location buttons next to the location dropdown (restart required)",
    );
    layout_section.add(&location_buttons_on_top, 0, LRBE, 10);
    finish_page(notebook, display, sizer, TAB_LABELS[1]);

    // --- Alerts (`settings_tabs/notifications.py`) ---
    let (alerts, sizer) = page(notebook);
    add_help_text(
        &alerts,
        &sizer,
        "Control which alerts notify you, how broad the alert area is, and how aggressively notifications repeat.",
        5,
    );
    let delivery_section = create_section(&alerts, &sizer, "Alert delivery");
    let enable_alerts = check(&alerts, "Monitor weather alerts");
    delivery_section.add(&enable_alerts, 0, LRB, 10);
    let alert_notif = check(&alerts, "Send alert notifications");
    delivery_section.add(&alert_notif, 0, LRB, 10);
    let immediate_alert_details_popups = check(
        &alerts,
        "Open alert details immediately while AccessiWeather is running",
    );
    delivery_section.add(&immediate_alert_details_popups, 0, LRBE, 10);
    let auto_tune_weather_radio_alerts = check(
        &alerts,
        "Automatically tune NOAA Weather Radio for qualifying Specific Area Message Encoding (SAME) alerts",
    );
    delivery_section.add(&auto_tune_weather_radio_alerts, 0, LRBE, 10);
    let (_, auto_tune_weather_radio_duration_minutes) = labeled(
        &alerts,
        &delivery_section,
        "Play weather radio for (minutes):",
        false,
        8,
        |p| spin(p, 1, 60, 5),
    );
    let coverage_section = create_section(&alerts, &sizer, "Coverage and severity");
    let (_, alert_radius_type) =
        labeled(&alerts, &coverage_section, "Alert area:", false, 8, |p| {
            choice(p, &RADIUS_TYPE_CHOICES)
        });
    let notify_extreme = check(&alerts, "Extreme severity alerts");
    coverage_section.add(&notify_extreme, 0, LRB, 10);
    let notify_severe = check(&alerts, "Severe severity alerts");
    coverage_section.add(&notify_severe, 0, LRB, 10);
    let notify_moderate = check(&alerts, "Moderate severity alerts");
    coverage_section.add(&notify_moderate, 0, LRB, 10);
    let notify_minor = check(&alerts, "Minor severity alerts");
    coverage_section.add(&notify_minor, 0, LRB, 10);
    let notify_unknown = check(&alerts, "Uncategorized alerts");
    coverage_section.add(&notify_unknown, 0, LRB, 10);
    let event_section = create_section(&alerts, &sizer, "Extra weather event notifications");
    let event_intro = text(
        &alerts,
        "Updates beyond standard alerts. Hazardous Weather Outlook and informational Special Weather Statement updates are on by default because they deliver information not in the alerts feed. Others are off unless you turn them on.",
    );
    event_section.add(&event_intro, 0, LRBE, 10);
    let event_check = |label: &str| {
        let cb = check(&alerts, label);
        event_section.add(&cb, 0, LRBE, 10);
        cb
    };
    let notify_discussion_update =
        event_check("Notify when the Area Forecast Discussion changes (NWS US only)");
    let notify_daily_climate_report_update =
        event_check("Notify when a Daily Climate Report changes (NWS US only)");
    let notify_hwo_update = event_check("Notify on Hazardous Weather Outlook updates");
    let notify_sps_issued = event_check("Notify on Special Weather Statement (informational)");
    let notify_severe_risk_change = event_check("Notify when severe weather risk changes");
    let notify_minutely_precipitation_start =
        event_check("Notify when precipitation is expected to start soon (Pirate Weather)");
    let notify_minutely_precipitation_stop =
        event_check("Notify when precipitation is expected to stop soon (Pirate Weather)");
    let minutely_precipitation_fast_polling =
        event_check("Check Pirate Weather precipitation more often when rain is likely");
    let precipitation_sensitivity = row(&alerts, &event_section, "Notify for:", LRB, 10, |p| {
        choice(p, &SENSITIVITY_CHOICES)
    });
    let notify_precipitation_likelihood =
        event_check("Notify when precipitation is likely (probability-based)");
    let precipitation_likelihood_threshold = row(
        &alerts,
        &event_section,
        "Precipitation likelihood threshold:",
        LRB,
        10,
        |p| choice(p, &LIKELIHOOD_THRESHOLD_CHOICES),
    );
    // Python also creates three hidden timing spin controls here; their
    // values live in the form and are edited in "Advanced timing...".
    let rate_section = create_section(&alerts, &sizer, "Rate limiting");
    let (_, max_notifications) = labeled(
        &alerts,
        &rate_section,
        "Maximum notifications per hour:",
        false,
        8,
        |p| spin(p, 1, 100, 10),
    );
    let advanced_timing = button(&alerts, "Advanced timing...");
    advanced_timing.set_name("Advanced alert timing settings");
    advanced_timing.set_tooltip("Configure cooldown periods and the alert freshness window");
    rate_section.add(&advanced_timing, 0, LRB, 10);
    finish_page(notebook, alerts, sizer, TAB_LABELS[2]);

    // --- Audio (`settings_tabs/audio.py`) ---
    let (audio, sizer) = page(notebook);
    add_help_text(
        &audio,
        &sizer,
        "Choose whether AccessiWeather plays sounds, which sound pack it uses, and which events are allowed to make noise.",
        5,
    );
    let playback_section = create_section(&audio, &sizer, "Playback");
    let sound_enabled = check(&audio, "Play notification sounds");
    playback_section.add(&sound_enabled, 0, LRBE, 10);
    let specific_alert_sounds_for_pack =
        check(&audio, "Use specific alert sounds for this sound pack");
    specific_alert_sounds_for_pack.set_tooltip(
        "Try sound pack keys like tornado_warning before severity sounds. This is automatic for packs that already contain those mappings.",
    );
    playback_section.add(&specific_alert_sounds_for_pack, 0, LRBE, 10);
    let (_, sound_pack) = labeled(&audio, &playback_section, "Sound pack:", false, 8, |p| {
        Choice::builder(p)
            .with_choices(sound_pack_names.to_vec())
            .build()
    });
    let action_row = BoxSizer::builder(Orientation::Horizontal).build();
    let play_sample = button(&audio, "Play sample sound");
    action_row.add(&play_sample, 0, SizerFlag::Right, 10);
    let manage_sound_packs = button(&audio, "Manage sound packs...");
    action_row.add(&manage_sound_packs, 0, SizerFlag::empty(), 0);
    playback_section.add_sizer(&action_row, 0, LRB, 10);
    let event_sounds_section = create_section(&audio, &sizer, "When sounds play");
    let event_sounds_summary = text(&audio, "");
    event_sounds_section.add(&event_sounds_summary, 0, LRBE, 10);
    let configure_event_sounds = button(&audio, "Choose event sounds...");
    event_sounds_section.add(&configure_event_sounds, 0, LRB, 10);
    finish_page(notebook, audio, sizer, TAB_LABELS[3]);

    // --- Data Sources (`settings_tabs/data_sources.py`) ---
    let (sources, sizer) = page(notebook);
    add_help_text(
        &sources,
        &sizer,
        "Choose where weather data comes from and manage provider-specific API keys.",
        5,
    );
    let source_section = create_section(&sources, &sizer, "Choose a weather source");
    let (_, data_source) = labeled(
        &sources,
        &source_section,
        "Weather source:",
        false,
        8,
        |p| choice(p, &DATA_SOURCE_CHOICES),
    );
    let auto_section = create_section(&sources, &sizer, "Automatic mode");
    let source_settings_summary = TextCtrl::builder(&sources)
        .with_value(&SourceSettings::default().summary_text())
        .with_size(Size::new(-1, 52))
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::NoVScroll | TextCtrlStyle::ReadOnly)
        .build();
    auto_section.add(&source_settings_summary, 0, LRBE, 10);
    let configure_source_settings =
        button(&sources, "Configure automatic mode budget and sources...");
    auto_section.add(&configure_source_settings, 0, LRB, 10);
    let keys_section = create_section(&sources, &sizer, "Provider API keys");

    let pw_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let pw_heading = text(&sources, "Pirate Weather");
    pw_sizer.add(&pw_heading, 0, LRBE, 10);
    let (pw_label, pw_key) = labeled(
        &sources,
        &pw_sizer,
        "Pirate Weather API key:",
        true,
        8,
        |p| text_ctrl(p, 280, TextCtrlStyle::Password),
    );
    let pw_buttons = BoxSizer::builder(Orientation::Horizontal).build();
    let get_pw_key = button(&sources, "Get Pirate Weather key");
    pw_buttons.add(&get_pw_key, 0, SizerFlag::Right, 10);
    let validate_pw_key = button(&sources, "Validate Pirate Weather key");
    pw_buttons.add(&validate_pw_key, 0, SizerFlag::empty(), 0);
    pw_sizer.add_sizer(&pw_buttons, 0, LRB, 10);
    let pw_help = add_help_text(
        &sources,
        &pw_sizer,
        "Use this provider for global forecasts and broader alert coverage.",
        10,
    );
    keys_section.add_sizer(&pw_sizer, 0, SizerFlag::Expand, 0);

    let airnow_sizer = BoxSizer::builder(Orientation::Vertical).build();
    airnow_sizer.add(&text(&sources, "AirNow"), 0, LRBE, 10);
    let (_, airnow_key) = labeled(&sources, &airnow_sizer, "AirNow API key:", true, 8, |p| {
        text_ctrl(p, 280, TextCtrlStyle::Password)
    });
    let airnow_buttons = BoxSizer::builder(Orientation::Horizontal).build();
    let get_airnow_key = button(&sources, "Get AirNow key");
    airnow_buttons.add(&get_airnow_key, 0, SizerFlag::Right, 10);
    let validate_airnow_key = button(&sources, "Validate AirNow key");
    airnow_buttons.add(&validate_airnow_key, 0, SizerFlag::empty(), 0);
    airnow_sizer.add_sizer(&airnow_buttons, 0, LRB, 10);
    add_help_text(
        &sources,
        &airnow_sizer,
        "Optional: supplies current U.S. AQI without changing your weather provider. Your API key is stored securely.",
        10,
    );
    keys_section.add_sizer(&airnow_sizer, 0, SizerFlag::Expand, 0);
    finish_page(notebook, sources, sizer, TAB_LABELS[4]);

    // --- AI (`settings_tabs/ai.py`) ---
    let (ai, sizer) = page(notebook);
    add_help_text(
        &ai,
        &sizer,
        "Choose the provider used for AI weather explanations and the weather assistant. Each provider keeps its own key and model.",
        5,
    );
    let (_, ai_provider) = labeled(&ai, &sizer, "AI provider:", false, 8, |p| {
        choice(p, &AI_PROVIDER_CHOICES)
    });
    ai_provider.set_selection(0);

    let openrouter_panel = Panel::builder(&ai).build();
    let openrouter_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let key_section = create_section(&openrouter_panel, &openrouter_sizer, "OpenRouter access");
    let (_, openrouter_key) = labeled(
        &openrouter_panel,
        &key_section,
        "OpenRouter API key:",
        true,
        8,
        |p| text_ctrl(p, 320, TextCtrlStyle::Password),
    );
    let validate_openrouter_key = button(&openrouter_panel, "Validate OpenRouter key");
    key_section.add(&validate_openrouter_key, 0, LRB, 10);
    let model_section = create_section(&openrouter_panel, &openrouter_sizer, "OpenRouter model");
    let (_, ai_model) = labeled(
        &openrouter_panel,
        &model_section,
        "OpenRouter model preference:",
        false,
        8,
        |p| choice(p, &AI_MODEL_CHOICES),
    );
    let browse_models = button(&openrouter_panel, "Browse OpenRouter models...");
    model_section.add(&browse_models, 0, LRB, 10);
    openrouter_panel.set_sizer(openrouter_sizer, true);
    sizer.add(&openrouter_panel, 0, SizerFlag::Expand, 0);

    let venice_panel = Panel::builder(&ai).build();
    let venice_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let venice_section = create_section(&venice_panel, &venice_sizer, "Venice AI access");
    let (_, venice_key) = labeled(
        &venice_panel,
        &venice_section,
        "Venice API key:",
        true,
        8,
        |p| text_ctrl(p, 320, TextCtrlStyle::Password),
    );
    let validate_venice_key = button(&venice_panel, "Validate Venice key");
    venice_section.add(&validate_venice_key, 0, LRB, 10);
    let get_venice_key = button(&venice_panel, "Get Venice API key...");
    venice_section.add(&get_venice_key, 0, LRB, 10);
    let (_, venice_model) = labeled(
        &venice_panel,
        &venice_section,
        "Venice model ID:",
        true,
        8,
        |p| text_ctrl(p, 320, TextCtrlStyle::Default),
    );
    let browse_venice_models = button(&venice_panel, "Browse Venice models...");
    venice_section.add(&browse_venice_models, 0, LRB, 10);
    add_help_text(
        &venice_panel,
        &venice_section,
        "Default: venice-uncensored-1-2. Choose a text model with function calling for the weather assistant. Manage keys and API credits at venice.ai/settings/api.",
        10,
    );
    venice_panel.set_sizer(venice_sizer, true);
    sizer.add(&venice_panel, 0, SizerFlag::Expand, 0);
    // `_apply_provider_visibility` for the initial OpenRouter selection.
    venice_panel.show(false);

    let (_, ai_style) = labeled(&ai, &sizer, "Explanation style:", false, 8, |p| {
        choice(p, &AI_STYLE_CHOICES)
    });
    let prompt_section = create_section(&ai, &sizer, "Custom prompts");
    prompt_section.add(&text(&ai, "Custom system prompt (optional):"), 0, LRB, 10);
    let custom_prompt = TextCtrl::builder(&ai)
        .with_style(TextCtrlStyle::MultiLine)
        .with_size(Size::new(420, 70))
        .build();
    prompt_section.add(&custom_prompt, 0, LRBE, 10);
    let reset_prompt = button(&ai, "Reset prompt to default");
    prompt_section.add(&reset_prompt, 0, LRB, 10);
    prompt_section.add(&text(&ai, "Custom instructions (optional):"), 0, LRB, 10);
    let custom_instructions = TextCtrl::builder(&ai)
        .with_style(TextCtrlStyle::MultiLine)
        .with_size(Size::new(420, 50))
        .build();
    prompt_section.add(&custom_instructions, 0, LRBE, 10);
    let cost_section = create_section(&ai, &sizer, "Cost notes");
    add_help_text(
        &ai,
        &cost_section,
        "OpenRouter offers free models that may be rate limited. Paid models charge according to usage and model pricing. Venice can use prepaid USD, DIEM, or bundled API credits; having credits does not make a paid model free.",
        10,
    );
    finish_page(notebook, ai, sizer, TAB_LABELS[5]);

    // --- Updates (`settings_tabs/updates.py`) ---
    let (updates, sizer) = page(notebook);
    add_help_text(
        &updates,
        &sizer,
        "Choose how AccessiWeather checks for new releases and when you want to check manually.",
        5,
    );
    let auto_section = create_section(&updates, &sizer, "Automatic update checks");
    let auto_update = check(&updates, "Check for updates automatically");
    auto_section.add(&auto_update, 0, LRBE, 10);
    let (_, update_channel) = labeled(&updates, &auto_section, "Release channel:", false, 8, |p| {
        choice(p, &UPDATE_CHANNEL_CHOICES)
    });
    let (_, update_check_interval) = labeled(
        &updates,
        &auto_section,
        "Check every (hours):",
        false,
        8,
        |p| spin(p, 1, 168, 24),
    );
    let manual_section = create_section(&updates, &sizer, "Check now");
    let check_updates = button(&updates, "Check for updates now");
    manual_section.add(&check_updates, 0, LRB, 10);
    let update_status = text(&updates, "Ready to check for updates.");
    manual_section.add(&update_status, 0, LRBE, 10);
    finish_page(notebook, updates, sizer, TAB_LABELS[6]);

    // --- Advanced (`settings_tabs/advanced.py`) ---
    let (advanced, sizer) = page(notebook);
    add_help_text(
        &advanced,
        &sizer,
        "Advanced settings include startup behavior, backup tools, and maintenance actions that you may not need every day.",
        5,
    );
    let startup_section = create_section(&advanced, &sizer, "Startup and window behavior");
    let minimize_tray = check(&advanced, "Minimize to the notification area when closing");
    startup_section.add(&minimize_tray, 0, LRB, 10);
    let minimize_on_startup = check(&advanced, "Start minimized to the notification area");
    startup_section.add(&minimize_on_startup, 0, LRB, 10);
    let startup = check(&advanced, "Launch automatically at startup");
    startup_section.add(&startup, 0, LRB, 10);
    let weather_history = check(&advanced, "Enable weather history comparisons");
    startup_section.add(&weather_history, 0, LRB, 10);
    let shortcut_section = create_section(&advanced, &sizer, "Window and tray shortcuts");
    add_help_text(
        &advanced,
        &shortcut_section,
        "Combine Ctrl, Alt and Shift with a letter, digit, function key, Tab, Space or Escape. On Windows these also work while AccessiWeather is hidden in the tray.",
        10,
    );
    let shortcut = |label: &str| {
        labeled(&advanced, &shortcut_section, label, true, 8, |p| {
            TextCtrl::builder(p).build()
        })
        .1
    };
    let shortcut_show_main_window =
        shortcut("Show the hidden window (for example Ctrl+Alt+Shift+W, leave blank to turn off):");
    let shortcut_hide_main_window = shortcut(
        "Hide the window to the tray (for example Ctrl+Alt+Shift+M, leave blank to turn off):",
    );
    let shortcut_read_tray_info = shortcut(
        "Read the current tray information (for example Ctrl+Alt+Shift+I, leave blank to turn off):",
    );
    let backup_section = create_section(&advanced, &sizer, "Backup and transfer");
    let section_button = |section: &BoxSizer, label: &str| {
        let b = button(&advanced, label);
        section.add(&b, 0, LRB, 10);
        b
    };
    let export_settings = section_button(&backup_section, "Export settings...");
    let import_settings = section_button(&backup_section, "Import settings...");
    let export_api_keys = section_button(&backup_section, "Export API keys (encrypted)");
    let import_api_keys = section_button(&backup_section, "Import API keys (encrypted)");
    let folders_section = create_section(&advanced, &sizer, "Folders and files");
    let open_config_dir = section_button(&folders_section, "Open current config folder");
    let open_installed_config_dir =
        section_button(&folders_section, "Open installed config folder (source)");
    let copy_installed_config =
        portable.then(|| section_button(&folders_section, "Copy installed config to portable"));
    let open_soundpacks_dir = section_button(&folders_section, "Open sound packs folder");
    let reset_section = create_section(&advanced, &sizer, "Reset and maintenance");
    let reset_defaults = section_button(&reset_section, "Reset settings to defaults");
    let full_reset = section_button(
        &reset_section,
        "Reset all app data (settings, locations, caches)",
    );
    finish_page(notebook, advanced, sizer, TAB_LABELS[7]);

    let controls = Controls {
        pages: [
            general, display, alerts, audio, sources, ai, updates, advanced,
        ],
        update_interval,
        taskbar_icon_text_enabled,
        taskbar_icon_dynamic_enabled,
        taskbar_icon_text_format,
        taskbar_icon_text_format_dialog,
        noaa_radio_hotkey,
        temp_unit,
        wind_speed_unit,
        round_values,
        location_sort_order,
        forecast_duration_days,
        hourly_forecast_hours,
        trend_hours,
        show_dewpoint,
        show_visibility,
        show_uv_index,
        show_pressure_trend,
        show_impact_summaries,
        forecast_time_reference,
        time_display_mode,
        time_format_12hour,
        show_timezone_suffix,
        date_format,
        verbosity_level,
        severe_weather_override,
        alert_display_style,
        location_buttons_on_top,
        enable_alerts,
        alert_notif,
        immediate_alert_details_popups,
        auto_tune_weather_radio_alerts,
        auto_tune_weather_radio_duration_minutes,
        alert_radius_type,
        notify_extreme,
        notify_severe,
        notify_moderate,
        notify_minor,
        notify_unknown,
        notify_discussion_update,
        notify_daily_climate_report_update,
        notify_hwo_update,
        notify_sps_issued,
        notify_severe_risk_change,
        notify_minutely_precipitation_start,
        notify_minutely_precipitation_stop,
        minutely_precipitation_fast_polling,
        precipitation_sensitivity,
        notify_precipitation_likelihood,
        precipitation_likelihood_threshold,
        max_notifications,
        advanced_timing,
        sound_enabled,
        specific_alert_sounds_for_pack,
        sound_pack,
        play_sample,
        manage_sound_packs,
        event_sounds_summary,
        configure_event_sounds,
        data_source,
        source_settings_summary,
        configure_source_settings,
        pirate_weather: PirateWeatherSection {
            heading: pw_heading,
            label: pw_label,
            key: pw_key,
            get_key: get_pw_key,
            validate_key: validate_pw_key,
            help: pw_help,
        },
        airnow_key,
        get_airnow_key,
        validate_airnow_key,
        ai_provider,
        openrouter_panel,
        openrouter_key,
        validate_openrouter_key,
        ai_model,
        browse_models,
        venice_panel,
        venice_key,
        validate_venice_key,
        get_venice_key,
        venice_model,
        browse_venice_models,
        ai_style,
        custom_prompt,
        reset_prompt,
        custom_instructions,
        auto_update,
        update_channel,
        update_check_interval,
        check_updates,
        update_status,
        minimize_tray,
        minimize_on_startup,
        startup,
        weather_history,
        shortcut_show_main_window,
        shortcut_hide_main_window,
        shortcut_read_tray_info,
        export_settings,
        import_settings,
        export_api_keys,
        import_api_keys,
        open_config_dir,
        open_installed_config_dir,
        copy_installed_config,
        open_soundpacks_dir,
        reset_defaults,
        full_reset,
    };
    controls.set_names();
    controls
}

fn set_choice_items(choice: &Choice, items: &[String]) {
    choice.clear();
    for item in items {
        choice.append(item);
    }
}

fn selection(choice: &Choice) -> usize {
    choice.get_selection().map_or(0, |i| i as usize)
}

impl Controls {
    /// Every tab's `setup_accessibility`: the names Python gives controls.
    fn set_names(&self) {
        let names: &[(&dyn WxWidget, &str)] = &[
            (&self.update_interval, "Update interval in minutes"),
            (&self.taskbar_icon_text_enabled, "Show weather text on the tray icon"),
            (&self.taskbar_icon_dynamic_enabled, "Update tray text as conditions change"),
            (&self.taskbar_icon_text_format, "Tray text format"),
            (&self.noaa_radio_hotkey, "NOAA Weather Radio play and stop hotkey"),
            (&self.temp_unit, "Temperature units"),
            (&self.wind_speed_unit, "Wind speed units"),
            (&self.show_dewpoint, "Show dew point"),
            (&self.show_visibility, "Show visibility"),
            (&self.show_uv_index, "Show UV index"),
            (&self.show_pressure_trend, "Show pressure trend"),
            (&self.show_impact_summaries, "Show impact summaries for outdoor driving and allergy conditions"),
            (&self.round_values, "Show values as whole numbers when possible"),
            (&self.forecast_duration_days, "Daily forecast range"),
            (&self.hourly_forecast_hours, "Hourly forecast range in hours"),
            (&self.trend_hours, "Pressure outlook range in hours"),
            (&self.forecast_time_reference, "Forecast time reference"),
            (&self.time_display_mode, "Time display mode"),
            (&self.time_format_12hour, "Use 12-hour time format"),
            (&self.show_timezone_suffix, "Show timezone abbreviations"),
            (&self.date_format, "Date format"),
            (&self.verbosity_level, "Verbosity level"),
            (&self.severe_weather_override, "Automatically prioritize severe weather details"),
            (&self.alert_display_style, "Alert display style"),
            (&self.location_sort_order, "Saved location order"),
            (&self.location_buttons_on_top, "Show Add, Edit, and Remove Location buttons next to the location dropdown (restart required)"),
            (&self.enable_alerts, "Monitor weather alerts"),
            (&self.alert_notif, "Send alert notifications"),
            (&self.alert_radius_type, "Alert area"),
            (&self.notify_extreme, "Extreme severity alerts"),
            (&self.notify_severe, "Severe severity alerts"),
            (&self.notify_moderate, "Moderate severity alerts"),
            (&self.notify_minor, "Minor severity alerts"),
            (&self.notify_unknown, "Uncategorized alerts"),
            (&self.immediate_alert_details_popups, "Open alert details immediately while AccessiWeather is running"),
            (&self.auto_tune_weather_radio_alerts, "Automatically tune NOAA Weather Radio for qualifying Specific Area Message Encoding (SAME) alerts"),
            (&self.auto_tune_weather_radio_duration_minutes, "Play weather radio for this many minutes"),
            (&self.notify_discussion_update, "Notify when the Area Forecast Discussion changes"),
            (&self.notify_daily_climate_report_update, "Notify when a Daily Climate Report changes"),
            (&self.notify_hwo_update, "Notify on Hazardous Weather Outlook updates"),
            (&self.notify_sps_issued, "Notify on Special Weather Statement (informational)"),
            (&self.notify_severe_risk_change, "Notify when severe weather risk changes"),
            (&self.notify_minutely_precipitation_start, "Notify when precipitation is expected to start soon"),
            (&self.notify_minutely_precipitation_stop, "Notify when precipitation is expected to stop soon"),
            (&self.minutely_precipitation_fast_polling, "Check Pirate Weather precipitation more often when rain is likely"),
            (&self.precipitation_sensitivity, "Notify for: precipitation sensitivity level"),
            (&self.notify_precipitation_likelihood, "Notify when precipitation is likely (probability-based)"),
            (&self.precipitation_likelihood_threshold, "Precipitation likelihood threshold"),
            (&self.max_notifications, "Maximum notifications per hour"),
            (&self.sound_enabled, "Play notification sounds"),
            (&self.specific_alert_sounds_for_pack, "Use specific alert sounds for this sound pack"),
            (&self.sound_pack, "Sound pack"),
            (&self.event_sounds_summary, "Event sound summary"),
            (&self.configure_event_sounds, "Choose event sounds"),
            (&self.data_source, "Weather source"),
            (&self.pirate_weather.key, "Pirate Weather API key"),
            (&self.airnow_key, "AirNow API key"),
            (&self.get_airnow_key, "Get AirNow key"),
            (&self.validate_airnow_key, "Validate AirNow key"),
            (&self.source_settings_summary, "Automatic mode source summary"),
            (&self.configure_source_settings, "Configure automatic mode budget and sources"),
            (&self.ai_provider, "AI provider"),
            (&self.venice_key, "Venice API key"),
            (&self.venice_model, "Venice model ID"),
            (&self.validate_venice_key, "Validate Venice key"),
            (&self.get_venice_key, "Get Venice API key (opens browser)"),
            (&self.openrouter_key, "OpenRouter API key"),
            (&self.ai_model, "AI model preference"),
            (&self.ai_style, "AI explanation style"),
            (&self.custom_prompt, "Custom system prompt"),
            (&self.custom_instructions, "Custom instructions"),
            (&self.auto_update, "Check for updates automatically"),
            (&self.update_channel, "Release channel"),
            (&self.update_check_interval, "Update check interval in hours"),
            (&self.minimize_tray, "Minimize to the notification area when closing"),
            (&self.minimize_on_startup, "Start minimized to the notification area"),
            (&self.shortcut_show_main_window, "Shortcut for showing the hidden window"),
            (&self.shortcut_hide_main_window, "Shortcut for hiding the window to the tray"),
            (&self.shortcut_read_tray_info, "Shortcut for reading the current tray information"),
            (&self.startup, "Launch automatically at startup"),
            (&self.weather_history, "Enable weather history comparisons"),
        ];
        for (control, name) in names {
            control.set_name(name);
        }
    }

    /// Show every control's value from the form (`load` on each tab).
    pub fn push(&self, f: &SettingsForm) {
        self.update_interval.set_value(f.update_interval);
        self.taskbar_icon_text_enabled
            .set_value(f.taskbar_icon_text_enabled);
        self.taskbar_icon_dynamic_enabled
            .set_value(f.taskbar_icon_dynamic_enabled);
        self.taskbar_icon_text_format
            .change_value(&f.taskbar_icon_text_format);
        self.update_taskbar_text_controls_state(f.taskbar_icon_text_enabled);
        self.noaa_radio_hotkey.change_value(&f.noaa_radio_hotkey);

        self.temp_unit.set_selection(f.temp_unit as u32);
        self.wind_speed_unit.set_selection(f.wind_speed_unit as u32);
        self.show_dewpoint.set_value(f.show_dewpoint);
        self.show_visibility.set_value(f.show_visibility);
        self.show_uv_index.set_value(f.show_uv_index);
        self.show_pressure_trend.set_value(f.show_pressure_trend);
        self.show_impact_summaries
            .set_value(f.show_impact_summaries);
        self.round_values.set_value(f.round_values);
        self.forecast_duration_days
            .set_selection(f.forecast_duration_days as u32);
        self.hourly_forecast_hours
            .set_value(f.hourly_forecast_hours);
        self.trend_hours.set_value(f.trend_hours);
        self.forecast_time_reference
            .set_selection(f.forecast_time_reference as u32);
        self.time_display_mode
            .set_selection(f.time_display_mode as u32);
        self.time_format_12hour.set_value(f.time_format_12hour);
        self.show_timezone_suffix.set_value(f.show_timezone_suffix);
        self.date_format.set_selection(f.date_format as u32);
        self.verbosity_level.set_selection(f.verbosity_level as u32);
        self.severe_weather_override
            .set_value(f.severe_weather_override);
        self.alert_display_style
            .set_selection(f.alert_display_style as u32);
        self.location_sort_order
            .set_selection(f.location_sort_order as u32);
        self.location_buttons_on_top
            .set_value(f.location_buttons_on_top);

        self.enable_alerts.set_value(f.enable_alerts);
        self.alert_notif.set_value(f.alert_notif);
        self.alert_radius_type
            .set_selection(f.alert_radius_type as u32);
        self.notify_extreme.set_value(f.notify_extreme);
        self.notify_severe.set_value(f.notify_severe);
        self.notify_moderate.set_value(f.notify_moderate);
        self.notify_minor.set_value(f.notify_minor);
        self.notify_unknown.set_value(f.notify_unknown);
        self.immediate_alert_details_popups
            .set_value(f.immediate_alert_details_popups);
        self.auto_tune_weather_radio_alerts
            .set_value(f.auto_tune_weather_radio_alerts);
        self.auto_tune_weather_radio_duration_minutes
            .set_value(f.auto_tune_weather_radio_duration_minutes);
        self.max_notifications.set_value(f.max_notifications);
        self.notify_discussion_update
            .set_value(f.notify_discussion_update);
        self.notify_daily_climate_report_update
            .set_value(f.notify_daily_climate_report_update);
        self.notify_hwo_update.set_value(f.notify_hwo_update);
        self.notify_sps_issued.set_value(f.notify_sps_issued);
        self.notify_severe_risk_change
            .set_value(f.notify_severe_risk_change);
        self.notify_minutely_precipitation_start
            .set_value(f.notify_minutely_precipitation_start);
        self.notify_minutely_precipitation_stop
            .set_value(f.notify_minutely_precipitation_stop);
        self.minutely_precipitation_fast_polling
            .set_value(f.minutely_precipitation_fast_polling);
        self.precipitation_sensitivity
            .set_selection(f.precipitation_sensitivity as u32);
        self.notify_precipitation_likelihood
            .set_value(f.notify_precipitation_likelihood);
        self.precipitation_likelihood_threshold
            .set_selection(f.precipitation_likelihood_threshold as u32);

        self.sound_enabled.set_value(f.sound_enabled);
        if let Some(i) = f.sound_pack {
            self.sound_pack.set_selection(i as u32);
        }
        self.push_specific_alert_sounds(f);
        self.event_sounds_summary
            .set_label(&f.event_sound_summary());

        self.data_source.set_selection(f.data_source as u32);
        self.pirate_weather.key.change_value(&f.pw_key);
        self.airnow_key.change_value(&f.airnow_key);
        self.push_source_settings_summary(f);
        self.update_api_key_visibility(f);

        self.ai_provider.set_selection(f.ai_provider as u32);
        self.apply_provider_visibility(f.ai_provider);
        self.venice_key.change_value(&f.venice_key);
        self.venice_model.change_value(&f.venice_model);
        self.openrouter_key.change_value(&f.openrouter_key);
        self.push_ai_model(f);
        self.ai_style.set_selection(f.ai_style as u32);
        self.custom_prompt.change_value(&f.custom_prompt);
        self.custom_instructions
            .change_value(&f.custom_instructions);

        self.auto_update.set_value(f.auto_update);
        self.update_channel.set_selection(f.update_channel as u32);
        self.update_check_interval
            .set_value(f.update_check_interval);

        self.minimize_tray.set_value(f.minimize_tray);
        self.minimize_on_startup.set_value(f.minimize_on_startup);
        self.push_shortcuts(f);
        self.minimize_on_startup.enable(f.minimize_tray);
        self.startup.set_value(f.startup);
        self.weather_history.set_value(f.weather_history);
    }

    /// Read every control back into the form.
    pub fn pull(&self, f: &mut SettingsForm) {
        f.update_interval = self.update_interval.value();
        f.taskbar_icon_text_enabled = self.taskbar_icon_text_enabled.is_checked();
        f.taskbar_icon_dynamic_enabled = self.taskbar_icon_dynamic_enabled.is_checked();
        f.taskbar_icon_text_format = self.taskbar_icon_text_format.get_value();
        f.noaa_radio_hotkey = self.noaa_radio_hotkey.get_value();

        f.temp_unit = selection(&self.temp_unit);
        f.wind_speed_unit = selection(&self.wind_speed_unit);
        f.round_values = self.round_values.is_checked();
        f.location_sort_order = selection(&self.location_sort_order);
        f.forecast_duration_days = selection(&self.forecast_duration_days);
        f.hourly_forecast_hours = self.hourly_forecast_hours.value();
        f.trend_hours = self.trend_hours.value();
        f.show_dewpoint = self.show_dewpoint.is_checked();
        f.show_visibility = self.show_visibility.is_checked();
        f.show_uv_index = self.show_uv_index.is_checked();
        f.show_pressure_trend = self.show_pressure_trend.is_checked();
        f.show_impact_summaries = self.show_impact_summaries.is_checked();
        f.forecast_time_reference = selection(&self.forecast_time_reference);
        f.time_display_mode = selection(&self.time_display_mode);
        f.time_format_12hour = self.time_format_12hour.is_checked();
        f.show_timezone_suffix = self.show_timezone_suffix.is_checked();
        f.date_format = selection(&self.date_format);
        f.verbosity_level = selection(&self.verbosity_level);
        f.severe_weather_override = self.severe_weather_override.is_checked();
        f.alert_display_style = selection(&self.alert_display_style);
        f.location_buttons_on_top = self.location_buttons_on_top.is_checked();

        f.enable_alerts = self.enable_alerts.is_checked();
        f.alert_notif = self.alert_notif.is_checked();
        f.immediate_alert_details_popups = self.immediate_alert_details_popups.is_checked();
        f.auto_tune_weather_radio_alerts = self.auto_tune_weather_radio_alerts.is_checked();
        f.auto_tune_weather_radio_duration_minutes =
            self.auto_tune_weather_radio_duration_minutes.value();
        f.alert_radius_type = selection(&self.alert_radius_type);
        f.notify_extreme = self.notify_extreme.is_checked();
        f.notify_severe = self.notify_severe.is_checked();
        f.notify_moderate = self.notify_moderate.is_checked();
        f.notify_minor = self.notify_minor.is_checked();
        f.notify_unknown = self.notify_unknown.is_checked();
        f.notify_discussion_update = self.notify_discussion_update.is_checked();
        f.notify_daily_climate_report_update = self.notify_daily_climate_report_update.is_checked();
        f.notify_hwo_update = self.notify_hwo_update.is_checked();
        f.notify_sps_issued = self.notify_sps_issued.is_checked();
        f.notify_severe_risk_change = self.notify_severe_risk_change.is_checked();
        f.notify_minutely_precipitation_start =
            self.notify_minutely_precipitation_start.is_checked();
        f.notify_minutely_precipitation_stop = self.notify_minutely_precipitation_stop.is_checked();
        f.minutely_precipitation_fast_polling =
            self.minutely_precipitation_fast_polling.is_checked();
        f.precipitation_sensitivity = selection(&self.precipitation_sensitivity);
        f.notify_precipitation_likelihood = self.notify_precipitation_likelihood.is_checked();
        f.precipitation_likelihood_threshold = selection(&self.precipitation_likelihood_threshold);
        f.max_notifications = self.max_notifications.value();

        f.sound_enabled = self.sound_enabled.is_checked();
        f.specific_alert_sounds_for_pack = self.specific_alert_sounds_for_pack.is_checked();
        f.sound_pack = self.sound_pack.get_selection().map(|i| i as usize);

        f.data_source = selection(&self.data_source);
        f.pw_key = self.pirate_weather.key.get_value();
        f.airnow_key = self.airnow_key.get_value();

        f.ai_provider = selection(&self.ai_provider);
        f.openrouter_key = self.openrouter_key.get_value();
        f.ai_model = selection(&self.ai_model);
        f.venice_key = self.venice_key.get_value();
        f.venice_model = self.venice_model.get_value();
        f.ai_style = selection(&self.ai_style);
        f.custom_prompt = self.custom_prompt.get_value();
        f.custom_instructions = self.custom_instructions.get_value();

        f.auto_update = self.auto_update.is_checked();
        f.update_channel = selection(&self.update_channel);
        f.update_check_interval = self.update_check_interval.value();

        f.minimize_tray = self.minimize_tray.is_checked();
        f.minimize_on_startup = self.minimize_on_startup.is_checked();
        f.startup = self.startup.is_checked();
        f.weather_history = self.weather_history.is_checked();
        f.shortcut_show_main_window = self.shortcut_show_main_window.get_value();
        f.shortcut_hide_main_window = self.shortcut_hide_main_window.get_value();
        f.shortcut_read_tray_info = self.shortcut_read_tray_info.get_value();
    }

    /// `_update_taskbar_text_controls_state`.
    pub fn update_taskbar_text_controls_state(&self, enabled: bool) {
        self.taskbar_icon_dynamic_enabled.enable(enabled);
        self.taskbar_icon_text_format_dialog.enable(enabled);
    }

    /// `_refresh_specific_alert_sounds_control`'s value and enabled state.
    pub fn push_specific_alert_sounds(&self, f: &SettingsForm) {
        self.specific_alert_sounds_for_pack
            .set_value(f.specific_alert_sounds_for_pack);
        self.specific_alert_sounds_for_pack
            .enable(f.specific_alert_sounds_editable());
    }

    pub fn push_sound_packs(&self, f: &SettingsForm) {
        let names: Vec<String> = f.state.sound_packs.iter().map(|p| p.name.clone()).collect();
        set_choice_items(&self.sound_pack, &names);
        if let Some(i) = f.sound_pack {
            self.sound_pack.set_selection(i as u32);
        }
    }

    pub fn push_source_settings_summary(&self, f: &SettingsForm) {
        self.source_settings_summary
            .change_value(&f.state.source_settings.summary_text());
    }

    /// `_update_api_key_visibility`.
    pub fn update_api_key_visibility(&self, f: &SettingsForm) {
        self.pirate_weather.show(f.pirate_weather_section_shown());
        self.pages[4].layout();
    }

    /// `_apply_provider_visibility`.
    pub fn apply_provider_visibility(&self, provider: usize) {
        self.openrouter_panel.show(provider != 1);
        self.venice_panel.show(provider == 1);
        self.pages[5].layout();
    }

    /// The model preference choice, whose third item names a chosen model.
    pub fn push_ai_model(&self, f: &SettingsForm) {
        if self.ai_model.get_count() as usize != f.state.ai_model_items.len()
            || (0..self.ai_model.get_count()).any(|i| {
                self.ai_model.get_string(i).as_ref() != f.state.ai_model_items.get(i as usize)
            })
        {
            set_choice_items(&self.ai_model, &f.state.ai_model_items);
        }
        self.ai_model.set_selection(f.ai_model as u32);
    }

    pub fn push_shortcuts(&self, f: &SettingsForm) {
        self.shortcut_show_main_window
            .change_value(&f.shortcut_show_main_window);
        self.shortcut_hide_main_window
            .change_value(&f.shortcut_hide_main_window);
        self.shortcut_read_tray_info
            .change_value(&f.shortcut_read_tray_info);
    }

    pub fn shortcut_control(&self, setting_name: &str) -> TextCtrl {
        match setting_name {
            "shortcut_show_main_window" => self.shortcut_show_main_window,
            "shortcut_hide_main_window" => self.shortcut_hide_main_window,
            _ => self.shortcut_read_tray_info,
        }
    }
}
