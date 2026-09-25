//! The main window: widgets, labels and names (`ui/main_window_ui.py`), the
//! instance state of `ui/main_window.py`, the status bar, Recent Events,
//! alerts list and section focus (`ui/main_window_display.py`) and the
//! window lifecycle from `app.py` / `app_lifecycle.py`.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::sync::atomic::Ordering;

use aw_core::location_sorting::sort_locations_for_display;
use aw_core::model::{WeatherAlert, WeatherAlerts, WeatherData};
use aw_core::Location;
use chrono::{Local, Utc};
use wxdragon::prelude::*;

use super::display::{self, ALL_LOCATIONS_SENTINEL};
use super::menus::{self, ID_CHECK_UPDATES, ID_PRECIPITATION_TIMELINE};
use super::shortcuts::{match_shortcut, Shortcut};
use super::{commands, locations, refresh};
use crate::app::{with_state, Shared, SMOKE_COMPLETED, SMOKE_DURATION_MS};

/// `QUICK_ACTION_LABELS`.
const LABEL_ADD: &str = "&Add Location";
const LABEL_EDIT: &str = "&Edit Location";
const LABEL_REMOVE: &str = "&Remove Location";
const LABEL_REFRESH: &str = "Re&fresh Weather";
const LABEL_EXPLAIN: &str = "Explain &Conditions";
const LABEL_DISCUSSION: &str = "Forecaster &Notes";
const LABEL_SETTINGS: &str = "&Settings";

const EVENT_CENTER_TOOLTIP: &str = "Reviewable log of recent weather notifications, AFD updates, \
                                    forecast briefings, and other in-app events.";

/// wxSTB_DEFAULT_STYLE (size grip, tooltips, end ellipsis, full repaint).
const STB_DEFAULT_STYLE: i64 = 0x0001_0130;
/// Roughly what `wx.lib.sized_controls` uses around each child on Windows.
const BORDER: i32 = 3;

/// Handles to the main window's controls. wx handles are `Copy` and become
/// harmless no-ops once the window is destroyed.
#[derive(Clone, Copy)]
pub(crate) struct MainWindow {
    pub frame: Frame,
    pane: Panel,
    pub location_dropdown: Choice,
    pub add_button: Button,
    pub edit_button: Button,
    pub remove_button: Button,
    pub refresh_button: Button,
    pub explain_button: Button,
    pub discussion_button: Button,
    pub settings_button: Button,
    pub current_conditions: TextCtrl,
    hourly_forecast_label: StaticText,
    pub hourly_forecast_display: TextCtrl,
    daily_forecast_label: StaticText,
    pub daily_forecast_display: TextCtrl,
    pub alerts_list: ListBox,
    pub view_alert_button: Button,
    event_center_label: StaticText,
    pub event_center_display: TextCtrl,
    status_bar: StatusBar,
}

/// Instance attributes of the Python `MainWindow`.
pub(crate) struct WindowState {
    /// Bumped per fetch so a superseded fetch never updates the display.
    pub fetch_generation: u64,
    /// alert id -> "New" / "Updated"; cleared when the location changes.
    pub alert_lifecycle_labels: HashMap<String, String>,
    /// "All Locations" is the active view.
    pub all_locations_active: bool,
    pub last_single_location_name: Option<String>,
    /// (location name, alert) pairs behind the alerts list in All Locations.
    pub all_locations_alerts_data: Vec<(String, WeatherAlert)>,
    pub event_center_visible: bool,
    /// Last section reached with F6.
    pub section_focus_index: Option<usize>,
}

impl Default for WindowState {
    fn default() -> Self {
        Self {
            fetch_generation: 0,
            alert_lifecycle_labels: HashMap::new(),
            all_locations_active: false,
            last_single_location_name: None,
            all_locations_alerts_data: Vec::new(),
            event_center_visible: true,
            section_focus_index: None,
        }
    }
}

thread_local! {
    static WINDOW: Cell<Option<MainWindow>> = const { Cell::new(None) };
    static WINDOW_STATE: RefCell<WindowState> = RefCell::new(WindowState::default());
    /// Timers must outlive their closures, and must go before wx tears down;
    /// left in thread-locals past that they crash on exit.
    static TIMERS: RefCell<Vec<Timer<Frame>>> = const { RefCell::new(Vec::new()) };
    static UPDATE_TIMER: RefCell<Option<Timer<Frame>>> = const { RefCell::new(None) };
    static DEBOUNCE_TIMER: RefCell<Option<Timer<Frame>>> = const { RefCell::new(None) };
}

pub(crate) fn window() -> Option<MainWindow> {
    WINDOW.with(Cell::get)
}

pub(crate) fn main_frame() -> Option<Frame> {
    window().map(|w| w.frame)
}

/// Run `f` on the window state. Never call back into wx from inside `f`.
pub(crate) fn window_state<R>(f: impl FnOnce(&mut WindowState) -> R) -> R {
    WINDOW_STATE.with(|w| f(&mut w.borrow_mut()))
}

fn app_state() -> Shared {
    with_state().expect("app state is set before the window exists")
}

fn label<W: WxWidget>(parent: &W, text: &str) -> StaticText {
    StaticText::builder(parent).with_label(text).build()
}

fn button<W: WxWidget>(parent: &W, text: &str) -> Button {
    Button::builder(parent).with_label(text).build()
}

/// A `SizedPanel` child with `expand=True`.
fn add<W: WxWidget>(sizer: &BoxSizer, widget: &W, proportion: i32) {
    sizer.add(
        widget,
        proportion,
        SizerFlag::Expand | SizerFlag::All,
        BORDER,
    );
}

fn text_panel(parent: &Panel, name: &str) -> TextCtrl {
    let ctrl = TextCtrl::builder(parent)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::Rich2)
        .build();
    ctrl.set_name(name);
    ctrl
}

pub(crate) fn build_main_window(state: &Shared, smoke: bool) {
    let (buttons_on_top, channel, debug_mode) = {
        let st = state.borrow();
        (
            st.config.settings.location_buttons_on_top,
            st.config.settings.update_channel.clone(),
            st.debug,
        )
    };

    let frame = Frame::builder().with_title("AccessiWeather").build();
    let pane = Panel::builder(&frame).build();
    let pane_sizer = BoxSizer::builder(Orientation::Vertical).build();
    // Location section.
    let location_panel = Panel::builder(&pane).build();
    let location_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let location_label = label(&location_panel, "Location:");
    location_sizer.add(
        &location_label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::All,
        BORDER,
    );
    let location_dropdown = Choice::builder(&location_panel).build();
    location_dropdown.set_name("Location selection");
    add(&location_sizer, &location_dropdown, 1);
    // Optionally Add/Edit/Remove sit on the location row (restart required).
    let top_buttons = buttons_on_top.then(|| {
        let b = [
            button(&location_panel, LABEL_ADD),
            button(&location_panel, LABEL_EDIT),
            button(&location_panel, LABEL_REMOVE),
        ];
        for b in &b {
            location_sizer.add(b, 0, SizerFlag::All, BORDER);
        }
        b
    });
    location_panel.set_sizer(location_sizer, true);
    add(&pane_sizer, &location_panel, 0);

    // Current conditions and forecasts.
    add(&pane_sizer, &label(&pane, "Current Conditions:"), 0);
    let current_conditions = text_panel(&pane, "Current weather conditions");
    add(&pane_sizer, &current_conditions, 1);
    let hourly_forecast_label = label(&pane, "Hourly Forecast:");
    add(&pane_sizer, &hourly_forecast_label, 0);
    let hourly_forecast_display = text_panel(&pane, "Hourly weather forecast");
    add(&pane_sizer, &hourly_forecast_display, 1);
    let daily_forecast_label = label(&pane, "Daily Forecast:");
    add(&pane_sizer, &daily_forecast_label, 0);
    let daily_forecast_display = text_panel(&pane, "Daily weather forecast");
    add(&pane_sizer, &daily_forecast_display, 1);

    // Weather alerts.
    let alerts_panel = Panel::builder(&pane).build();
    let alerts_sizer = BoxSizer::builder(Orientation::Vertical).build();
    add(&alerts_sizer, &label(&alerts_panel, "Weather Alerts:"), 0);
    let alerts_list = ListBox::builder(&alerts_panel).build();
    alerts_list.set_name("Weather alerts list");
    add(&alerts_sizer, &alerts_list, 1);
    let view_alert_button = button(&alerts_panel, "View Alert Details");
    view_alert_button.enable(false);
    alerts_sizer.add(&view_alert_button, 0, SizerFlag::All, BORDER);
    alerts_panel.set_sizer(alerts_sizer, true);
    add(&pane_sizer, &alerts_panel, 0);

    // Event Center, shown as "Recent Events".
    let event_center_label = label(&pane, "Recent Events:");
    event_center_label.set_tooltip(EVENT_CENTER_TOOLTIP);
    add(&pane_sizer, &event_center_label, 0);
    let event_center_display = text_panel(&pane, "Recent events");
    event_center_display.set_tooltip(EVENT_CENTER_TOOLTIP);
    add(&pane_sizer, &event_center_display, 1);

    // Control buttons.
    let button_panel = Panel::builder(&pane).build();
    let button_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let [add_button, edit_button, remove_button] = top_buttons.unwrap_or_else(|| {
        [
            button(&button_panel, LABEL_ADD),
            button(&button_panel, LABEL_EDIT),
            button(&button_panel, LABEL_REMOVE),
        ]
    });
    let refresh_button = button(&button_panel, LABEL_REFRESH);
    let explain_button = button(&button_panel, LABEL_EXPLAIN);
    let discussion_button = button(&button_panel, LABEL_DISCUSSION);
    let settings_button = button(&button_panel, LABEL_SETTINGS);
    let mut row = vec![
        refresh_button,
        explain_button,
        discussion_button,
        settings_button,
    ];
    if !buttons_on_top {
        row.splice(0..0, [add_button, edit_button, remove_button]);
    }
    for b in &row {
        button_sizer.add(b, 0, SizerFlag::All, BORDER);
    }
    button_panel.set_sizer(button_sizer, true);
    add(&pane_sizer, &button_panel, 0);
    pane.set_sizer(pane_sizer, true);

    // Status bar: [0] main status, [1] stale/cached warning.
    let status_bar = frame.create_status_bar(2, STB_DEFAULT_STYLE, 0, "statusBar");
    status_bar.set_status_widths(&[-2, -1]);

    frame.set_menu_bar(menus::build_menu_bar(&channel, debug_mode));
    let frame_sizer = BoxSizer::builder(Orientation::Vertical).build();
    frame_sizer.add(&pane, 1, SizerFlag::Expand, 0);
    frame.set_sizer(frame_sizer, true);
    frame.set_size(Size::new(900, 820));
    frame.set_min_size(Size::new(800, 700));

    let win = MainWindow {
        frame,
        pane,
        location_dropdown,
        add_button,
        edit_button,
        remove_button,
        refresh_button,
        explain_button,
        discussion_button,
        settings_button,
        current_conditions,
        hourly_forecast_label,
        hourly_forecast_display,
        daily_forecast_label,
        daily_forecast_display,
        alerts_list,
        view_alert_button,
        event_center_label,
        event_center_display,
        status_bar,
    };
    WINDOW.with(|w| w.set(Some(win)));
    bind_events(&win);
    populate_locations();

    // `load_initial_data`.
    let (has_locations, has_current) = {
        let st = state.borrow();
        (
            !st.config.locations.is_empty(),
            st.config.current_location.is_some(),
        )
    };
    if !has_locations {
        set_status("Add a location to get started.");
    } else if has_current {
        refresh::refresh_weather_async(false);
    }
    start_background_updates();

    if smoke {
        let smoke_state = state.clone();
        keep_timer(SMOKE_DURATION_MS, move || {
            if smoke_state.borrow().current_weather_data.is_some() {
                SMOKE_COMPLETED.store(true, Ordering::SeqCst);
            }
            tracing::info!("smoke run complete");
            frame.close(true);
        });
    }

    frame.show(true);
    // Python sets focus from EVT_SHOW (which wxDragon lacks) 100 ms after the
    // window appears, so screen readers announce the dropdown.
    keep_timer(100, move || {
        location_dropdown.set_focus();
        tracing::debug!("Initial focus set to location dropdown");
    });
}

/// Start a one-shot timer that lives until the window closes.
fn keep_timer(ms: i32, f: impl Fn() + 'static) {
    let Some(frame) = main_frame() else { return };
    let timer = Timer::new(&frame);
    timer.on_tick(move |_| f());
    timer.start(ms, true);
    TIMERS.with(|t| t.borrow_mut().push(timer));
}

fn bind_events(win: &MainWindow) {
    let w = *win;
    w.frame
        .bind_internal(EventType::CLOSE_WINDOW, |e: Event| on_close(&e));
    w.frame.on_menu(|e| menus::on_menu(e.get_id()));
    w.location_dropdown
        .on_selection_changed(|_| locations::on_location_changed());

    w.add_button.on_click(|_| locations::on_add_location());
    w.edit_button.on_click(|_| locations::on_edit_location());
    w.remove_button
        .on_click(|_| locations::on_remove_location());
    w.refresh_button.on_click(|_| locations::on_refresh());
    w.explain_button
        .on_click(|_| commands::on_explain_weather());
    w.discussion_button.on_click(|_| commands::on_discussion());
    w.settings_button.on_click(|_| locations::on_settings());
    w.view_alert_button.on_click(|_| commands::on_view_alert());

    // Enter/Space on the alerts list open the details; EVT_CHAR_HOOK sees
    // them before a screen reader in forms mode can.
    w.alerts_list
        .on_item_double_clicked(|_| commands::on_view_alert());
    w.alerts_list
        .bind_internal(EventType::CHAR_HOOK, |e: Event| match e.get_key_code() {
            Some(WXK_RETURN | WXK_NUMPAD_ENTER | WXK_SPACE) => {
                e.skip(false);
                commands::on_view_alert();
            }
            _ => e.skip(true),
        });

    w.frame.bind_internal(EventType::CHAR_HOOK, |e: Event| {
        let key = e.get_key_code().unwrap_or(0);
        let Some(shortcut) = match_shortcut(key, e.cmd_down(), e.alt_down(), e.shift_down()) else {
            e.skip(true);
            return;
        };
        e.skip(false);
        match shortcut {
            Shortcut::Refresh => locations::on_refresh(),
            Shortcut::FocusSection(n) => focus_section_by_number(n),
            Shortcut::CycleSections => cycle_section_focus(),
            // `_on_escape_pressed` minimizes to the tray when that is on;
            // see `should_minimize_to_tray`.
            Shortcut::Escape => {}
        }
    });
}

/// `_should_minimize_to_tray`. Python reads only the setting; until the tray
/// icon is ported, hiding the window would leave no way back, so this
/// reports false. The tray work should return
/// `settings.minimize_to_tray` here and hide the window on Escape, close
/// and minimize (Python's EVT_ICONIZE, which wxDragon lacks).
fn should_minimize_to_tray() -> bool {
    false
}

/// `_on_close`.
fn on_close(e: &Event) {
    if e.can_veto() && should_minimize_to_tray() {
        e.veto();
        return;
    }
    // Stop timers and drop handles before wx tears the window down.
    for slot in [&UPDATE_TIMER, &DEBOUNCE_TIMER] {
        slot.with(|t| {
            if let Some(timer) = t.borrow_mut().take() {
                timer.stop();
            }
        });
    }
    TIMERS.with(|t| t.borrow_mut().clear());
    WINDOW.with(|w| w.set(None));
    e.skip(true);
}

/// `app_timer_manager.start_background_updates`: a full refresh every
/// `update_interval_minutes`, skipped while one is already running.
pub(crate) fn start_background_updates() {
    let Some(frame) = main_frame() else { return };
    let minutes = app_state()
        .borrow()
        .config
        .settings
        .update_interval_minutes();
    let timer = Timer::new(&frame);
    timer.on_tick(|_| {
        if window().is_some() && !app_state().borrow().is_updating {
            refresh::refresh_weather_async(false);
        }
    });
    timer.start((minutes * 60_000).min(i32::MAX as u64) as i32, false);
    tracing::info!("Background updates started (weather every {minutes} minutes)");
    if let Some(old) = UPDATE_TIMER.with(|t| t.borrow_mut().replace(timer)) {
        old.stop();
    }
}

/// Restart the 500 ms location-change debounce, then force a fetch.
pub(crate) fn restart_location_debounce() {
    let Some(frame) = main_frame() else { return };
    DEBOUNCE_TIMER.with(|slot| {
        let mut slot = slot.borrow_mut();
        let timer = slot.get_or_insert_with(|| {
            let timer = Timer::new(&frame);
            timer.on_tick(|_| refresh::refresh_weather_async(true));
            timer
        });
        if timer.is_running() {
            timer.stop();
        }
        timer.start(500, true);
    });
}

/// `message_box`: `wx.MessageBox` returning the dialog result.
pub(crate) fn message_box(
    parent: &dyn WxWidget,
    message: &str,
    caption: &str,
    style: MessageDialogStyle,
) -> i32 {
    MessageDialog::builder(parent, message, caption)
        .with_style(style)
        .build()
        .show_modal()
}

// ---------------------------------------------------------------------------
// Display helpers (`main_window_display.py`)
// ---------------------------------------------------------------------------

/// `set_status`: status bar field 0, spoken by the screen reader.
pub(crate) fn set_status(message: &str) {
    if let Some(w) = window() {
        w.status_bar.set_status_text(message, 0);
    }
    tracing::info!("Status: {message}");
    if !message.is_empty() {
        crate::screen_reader::announce(message);
    }
}

/// `_set_last_updated_status`: field 0, silent.
pub(crate) fn set_last_updated_status() {
    if let Some(w) = window() {
        let text = display::last_updated_status(Local::now().time());
        w.status_bar.set_status_text(&text, 0);
    }
}

/// `stale_warning_label.SetLabel`: status bar field 1.
pub(crate) fn set_stale_warning(text: &str) {
    if let Some(w) = window() {
        w.status_bar.set_status_text(text, 1);
    }
}

/// `append_event_center_entry`.
pub(crate) fn append_event_center_entry(text: &str, category: Option<&str>) {
    let (Some(w), Some(entry)) = (
        window(),
        display::event_center_entry(text, category, Local::now().time()),
    ) else {
        return;
    };
    w.event_center_display.append_text(&entry);
}

/// `_set_forecast_sections`.
pub(crate) fn set_forecast_sections(daily_text: &str, hourly_text: &str) {
    if let Some(w) = window() {
        w.daily_forecast_display.set_value(daily_text);
        w.hourly_forecast_display.set_value(hourly_text);
    }
}

/// `_set_forecast_sections_visible`.
pub(crate) fn set_forecast_sections_visible(visible: bool) {
    let Some(w) = window() else { return };
    w.daily_forecast_label.show(visible);
    w.daily_forecast_display.show(visible);
    w.hourly_forecast_label.show(visible);
    w.hourly_forecast_display.show(visible);
    w.pane.layout();
}

/// `toggle_event_center` (View > Event Center).
pub(crate) fn toggle_event_center() {
    let Some(w) = window() else { return };
    let visible = window_state(|s| {
        s.event_center_visible = !s.event_center_visible;
        s.event_center_visible
    });
    w.event_center_label.show(visible);
    w.event_center_display.show(visible);
    w.pane.layout();
}

fn focus_section(w: &MainWindow, index: usize) {
    match index {
        0 => w.location_dropdown.set_focus(),
        1 => w.current_conditions.set_focus(),
        2 => w.hourly_forecast_display.set_focus(),
        3 => w.daily_forecast_display.set_focus(),
        4 => w.alerts_list.set_focus(),
        _ => w.event_center_display.set_focus(),
    }
}

/// `focus_section_by_number` (Ctrl+1..5).
pub(crate) fn focus_section_by_number(number: usize) {
    let Some(w) = window() else { return };
    let visible = window_state(|s| s.event_center_visible);
    if let Some(index) = display::section_for_number(number, visible) {
        focus_section(&w, index);
    }
}

/// `cycle_section_focus` (F6).
pub(crate) fn cycle_section_focus() {
    let Some(w) = window() else { return };
    let index = window_state(|s| {
        let next = display::next_section(s.section_focus_index, s.event_center_visible);
        s.section_focus_index = Some(next);
        next
    });
    focus_section(&w, index);
}

/// `_update_title_for_location`.
pub(crate) fn update_title_for_location(location_name: Option<&str>) {
    if let Some(w) = window() {
        w.frame.set_title(&display::window_title(location_name));
    }
}

fn set_alert_items(w: &MainWindow, items: &[String]) {
    w.alerts_list.clear();
    for item in items {
        w.alerts_list.append(item);
    }
    w.view_alert_button.enable(!items.is_empty());
}

/// `_update_alerts`: active alerts only, with lifecycle labels.
pub(crate) fn update_alerts(alerts: Option<&WeatherAlerts>, labels: &HashMap<String, String>) {
    let Some(w) = window() else { return };
    let active = alerts.map(|a| a.active(Utc::now())).unwrap_or_default();
    set_alert_items(&w, &display::alert_list_items(&active, labels));
}

/// `_update_all_locations_alerts`.
pub(crate) fn update_all_locations_alerts(location_alerts: &[(String, WeatherAlert)]) {
    if let Some(w) = window() {
        set_alert_items(&w, &display::all_locations_alert_items(location_alerts));
    }
}

/// `_update_precipitation_timeline_menu_state`: enabled only for a single
/// location whose data has minutely precipitation.
pub(crate) fn update_precipitation_timeline_menu_state(weather_data: Option<&WeatherData>) {
    let Some(bar) = main_frame().and_then(|f| f.get_menu_bar()) else {
        return;
    };
    let enabled = !window_state(|s| s.all_locations_active) && {
        let has = |d: &WeatherData| {
            d.minutely_precipitation
                .as_ref()
                .is_some_and(|m| m.has_data())
        };
        match weather_data {
            Some(d) => has(d),
            None => app_state()
                .borrow()
                .current_weather_data
                .as_ref()
                .is_some_and(has),
        }
    };
    bar.enable_item(ID_PRECIPITATION_TIMELINE, enabled);
}

/// `update_check_updates_menu_label`.
pub(crate) fn update_check_updates_menu_label() {
    let channel = app_state().borrow().config.settings.update_channel.clone();
    if let Some(item) = main_frame()
        .and_then(|f| f.get_menu_bar())
        .and_then(|bar| bar.find_item(ID_CHECK_UPDATES))
    {
        item.set_label(&display::check_updates_label(&channel));
    }
}

/// `_get_ordered_saved_locations`.
pub(crate) fn ordered_saved_locations() -> Vec<Location> {
    let state = app_state();
    let st = state.borrow();
    sort_locations_for_display(
        &st.config.locations,
        Some(&st.config.settings.location_sort_order),
        st.config.current_location.as_ref(),
    )
}

/// `_populate_locations`: "All Locations" first, then the saved locations in
/// display order, selecting the current one.
pub(crate) fn populate_locations() {
    let Some(w) = window() else { return };
    let mut names = vec![ALL_LOCATIONS_SENTINEL.to_string()];
    names.extend(ordered_saved_locations().into_iter().map(|l| l.name));
    w.location_dropdown.clear();
    for name in &names {
        w.location_dropdown.append(name);
    }
    let current = app_state()
        .borrow()
        .config
        .current_location
        .as_ref()
        .map(|c| c.name.clone());
    let index = current
        .as_ref()
        .and_then(|c| names.iter().position(|n| n == c))
        .filter(|_| !window_state(|s| s.all_locations_active));
    match index {
        Some(i) => {
            w.location_dropdown.set_selection(i as u32);
            update_title_for_location(current.as_deref());
        }
        None => {
            w.location_dropdown.set_selection(0);
            update_title_for_location(Some(ALL_LOCATIONS_SENTINEL));
        }
    }
}

/// `location_dropdown.FindString`.
pub(crate) fn find_location_index(name: &str) -> Option<u32> {
    let w = window()?;
    (0..w.location_dropdown.get_count())
        .find(|&i| w.location_dropdown.get_string(i).as_deref() == Some(name))
}

/// `_show_all_locations_summary`: cached data for every saved location, no
/// network. The forecast panels are hidden and the alerts list aggregates
/// every location's alerts.
pub(crate) fn show_all_locations_summary() {
    let Some(w) = window() else { return };
    let locations = ordered_saved_locations();
    if locations.is_empty() {
        w.current_conditions.set_value(display::NO_LOCATIONS_TEXT);
        set_forecast_sections("", "");
        w.alerts_list.clear();
        w.view_alert_button.enable(false);
        update_precipitation_timeline_menu_state(None);
        return;
    }
    let settings = app_state().borrow().config.settings.clone();
    let (text, location_alerts) = display::all_locations_summary(
        &locations,
        super::weather_source::get_cached_weather,
        &settings,
        Utc::now(),
    );
    w.current_conditions.set_value(&text);
    set_forecast_sections_visible(false);
    update_all_locations_alerts(&location_alerts);
    window_state(|s| s.all_locations_alerts_data = location_alerts);
    // Python also points the tray tooltip at the most severe location here.
    set_stale_warning("");
    update_precipitation_timeline_menu_state(None);
    app_state().borrow_mut().is_updating = false;
    w.refresh_button.enable(true);
}
