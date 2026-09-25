//! wxDragon (wxWidgets) native user interface: main window and dialogs.

use std::cell::RefCell;
use std::rc::Rc;

use aw_core::presenter::{WeatherPresentation, WeatherPresenter};
use aw_core::Location;
use aw_providers::geocoding::Geocoder;
use wxdragon::prelude::*;

use crate::app::SMOKE_DURATION_MS;
use crate::app::{post_to_ui, remember_weather, save, status_for, with_state, Shared, State};

#[cfg(target_os = "macos")]
const MOD_KEY: &str = "Cmd";
#[cfg(not(target_os = "macos"))]
const MOD_KEY: &str = "Ctrl";

const ID_ADD_LOCATION: Id = ID_HIGHEST + 1;
const ID_REMOVE_LOCATION: Id = ID_HIGHEST + 2;
const ID_REFRESH: Id = ID_HIGHEST + 3;
const ID_SETTINGS: Id = ID_HIGHEST + 4;
const ID_DISCUSSION: Id = ID_HIGHEST + 5;
const ID_READ_ALOUD: Id = ID_HIGHEST + 6;
const ID_STOP_SPEECH: Id = ID_HIGHEST + 7;
const ID_ALERT_DETAILS: Id = ID_HIGHEST + 8;
const ID_SEARCH: Id = ID_HIGHEST + 9;

const NO_ALERTS: &str = "No active alerts";

/// Handles to the main window controls. All wx handles are `Copy` and become
/// safe no-ops once the window is destroyed.
#[derive(Clone, Copy)]
pub(crate) struct MainUi {
    frame: Frame,
    location_choice: Choice,
    remove_button: Button,
    refresh_button: Button,
    summary: StaticText,
    current: TextCtrl,
    hourly: TextCtrl,
    daily: TextCtrl,
    alerts: ListBox,
    details_button: Button,
    discussion_button: Button,
    status: StaticText,
}

thread_local! {
    static MAIN_UI: RefCell<Option<MainUi>> = const { RefCell::new(None) };
    /// The Add Location dialog currently shown (at most one) and its search results.
    static ADD_DIALOG: RefCell<Option<AddDialogUi>> = const { RefCell::new(None) };
    static SEARCH_RESULTS: RefCell<Vec<Location>> = const { RefCell::new(Vec::new()) };
    /// Timers must outlive the closures they drive; keep them for the life of the window.
    static TIMERS: RefCell<Vec<Timer<Frame>>> = const { RefCell::new(Vec::new()) };
}

fn main_ui() -> Option<MainUi> {
    MAIN_UI.with(|u| *u.borrow())
}

/// Give a control an accessible name (and optional description) on the
/// platforms where wxWidgets exposes it, plus a wx name usable by AT-SPI.
fn label_control<W: WxWidget>(w: &W, name: &str, description: Option<&str>) {
    w.set_name(name);
    w.set_accessibility_label(name);
    if let Some(d) = description {
        w.set_accessibility_description(d);
        w.set_tooltip(d);
    }
}

fn read_only_text<W: WxWidget>(parent: &W, name: &str, description: &str, height: i32) -> TextCtrl {
    let ctrl = TextCtrl::builder(parent)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::WordWrap)
        .with_size(Size::new(-1, height))
        .build();
    label_control(&ctrl, name, Some(description));
    ctrl
}

/// A labelled group box; returns the `StaticBox` to parent children on and its sizer.
fn group_box(
    parent: &Panel,
    label: &str,
    root: &BoxSizer,
    proportion: i32,
) -> (StaticBox, StaticBoxSizer) {
    let static_box = StaticBox::builder(parent).with_label(label).build();
    let sizer = StaticBoxSizerBuilder::new_with_box(&static_box, Orientation::Vertical).build();
    root.add_sizer(
        &sizer,
        proportion,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        8,
    );
    (static_box, sizer)
}

fn text_box(
    parent: &Panel,
    label: &str,
    description: &str,
    root: &BoxSizer,
    proportion: i32,
    height: i32,
) -> TextCtrl {
    let (static_box, sizer) = group_box(parent, label, root, proportion);
    let ctrl = read_only_text(&static_box, label, description, height);
    sizer.add(&ctrl, 1, SizerFlag::Expand | SizerFlag::All, 4);
    ctrl
}

// ---------------------------------------------------------------------------
// Main window
// ---------------------------------------------------------------------------

pub(crate) fn build_main_window(state: &Shared, smoke: bool) {
    let frame = Frame::builder()
        .with_title("AccessiWeather")
        .with_size(Size::new(820, 720))
        .build();
    frame.set_menu_bar(build_menu_bar());
    let panel = Panel::builder(&frame).build();
    let root = BoxSizer::builder(Orientation::Vertical).build();

    // Location row -----------------------------------------------------------
    let location_row = BoxSizer::builder(Orientation::Horizontal).build();
    let location_label = StaticText::builder(&panel).with_label("&Location:").build();
    let location_choice = Choice::builder(&panel).build();
    label_control(
        &location_choice,
        "Location",
        Some("Choose which saved location to show"),
    );
    let add_button = Button::builder(&panel)
        .with_id(ID_ADD_LOCATION)
        .with_label("&Add…")
        .build();
    label_control(
        &add_button,
        "Add location",
        Some("Search for a place and save it (Alt+A)"),
    );
    let remove_button = Button::builder(&panel)
        .with_id(ID_REMOVE_LOCATION)
        .with_label("Re&move")
        .build();
    label_control(
        &remove_button,
        "Remove location",
        Some("Remove the selected location"),
    );
    let refresh_button = Button::builder(&panel)
        .with_id(ID_REFRESH)
        .with_label("&Refresh")
        .build();
    label_control(
        &refresh_button,
        "Refresh weather",
        Some("Fetch the latest weather (F5)"),
    );
    location_row.add(
        &location_label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        6,
    );
    location_row.add(
        &location_choice,
        1,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        6,
    );
    location_row.add(&add_button, 0, SizerFlag::Right, 4);
    location_row.add(&remove_button, 0, SizerFlag::Right, 4);
    location_row.add(&refresh_button, 0, SizerFlag::Right, 0);
    root.add_sizer(&location_row, 0, SizerFlag::Expand | SizerFlag::All, 8);

    // Summary ----------------------------------------------------------------
    let summary = StaticText::builder(&panel).with_label("Loading…").build();
    label_control(&summary, "Weather summary", None);
    root.add(
        &summary,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        8,
    );

    // Forecast panels --------------------------------------------------------
    let current = text_box(
        &panel,
        "Current conditions",
        &format!("Current conditions ({MOD_KEY}+2)"),
        &root,
        2,
        110,
    );
    let hourly = text_box(
        &panel,
        "Hourly forecast",
        &format!("Hourly forecast ({MOD_KEY}+3)"),
        &root,
        2,
        110,
    );
    let daily = text_box(
        &panel,
        "Extended forecast",
        &format!("Extended forecast ({MOD_KEY}+4)"),
        &root,
        3,
        150,
    );

    // Alerts -----------------------------------------------------------------
    let (alerts_group, alerts_sizer) = group_box(&panel, "Alerts", &root, 2);
    let alerts = ListBox::builder(&alerts_group)
        .with_choices(vec![NO_ALERTS.to_string()])
        .with_size(Size::new(-1, 70))
        .build();
    label_control(
        &alerts,
        "Weather alerts",
        Some(&format!(
            "Active alerts; press Enter for details ({MOD_KEY}+5)"
        )),
    );
    alerts_sizer.add(&alerts, 1, SizerFlag::Expand | SizerFlag::All, 4);

    // Action row -------------------------------------------------------------
    let actions = BoxSizer::builder(Orientation::Horizontal).build();
    let details_button = Button::builder(&panel)
        .with_id(ID_ALERT_DETAILS)
        .with_label("Alert &details")
        .build();
    label_control(
        &details_button,
        "Alert details",
        Some("Show the full text of the selected alert"),
    );
    let discussion_button = Button::builder(&panel)
        .with_id(ID_DISCUSSION)
        .with_label("Forecast d&iscussion")
        .build();
    label_control(
        &discussion_button,
        "Forecast discussion",
        Some(&format!(
            "Read the NWS area forecast discussion ({MOD_KEY}+D)"
        )),
    );
    let read_button = Button::builder(&panel)
        .with_id(ID_READ_ALOUD)
        .with_label("Read a&loud")
        .build();
    label_control(
        &read_button,
        "Read aloud",
        Some(&format!(
            "Speak the summary and current conditions ({MOD_KEY}+Shift+S)"
        )),
    );
    let settings_button = Button::builder(&panel)
        .with_id(ID_SETTINGS)
        .with_label("&Settings…")
        .build();
    label_control(
        &settings_button,
        "Settings",
        Some(&format!("Open settings ({MOD_KEY}+,)")),
    );
    for b in [
        &details_button,
        &discussion_button,
        &read_button,
        &settings_button,
    ] {
        actions.add(b, 0, SizerFlag::Right, 6);
    }
    root.add_sizer(
        &actions,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        8,
    );

    // Status -----------------------------------------------------------------
    let status = StaticText::builder(&panel).with_label("Ready.").build();
    label_control(&status, "Status", None);
    root.add(&status, 0, SizerFlag::Expand | SizerFlag::All, 8);

    panel.set_sizer(root, true);
    let frame_sizer = BoxSizer::builder(Orientation::Vertical).build();
    frame_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    frame.set_sizer(frame_sizer, true);

    let ui = MainUi {
        frame,
        location_choice,
        remove_button,
        refresh_button,
        summary,
        current,
        hourly,
        daily,
        alerts,
        details_button,
        discussion_button,
        status,
    };
    MAIN_UI.with(|u| *u.borrow_mut() = Some(ui));

    wire_commands(&ui, state);
    wire_keys(&ui, state);
    sync_locations(&ui, &state.borrow());
    clear_weather(&ui);
    schedule_refresh_timer(state);

    if state.borrow().config.current_location.is_some() {
        start_refresh(&ui, state);
    } else {
        set_status(
            &ui,
            "No saved locations. Press Alt+A or use Add to search for one.",
        );
    }

    if smoke {
        let timer = Timer::new(&frame);
        timer.on_tick(move |_| {
            tracing::info!("smoke run complete");
            frame.close(true);
        });
        timer.start(SMOKE_DURATION_MS, true);
        TIMERS.with(|t| t.borrow_mut().push(timer));
    }

    frame.show(true);
    frame.centre();
    location_choice.set_focus();
}

fn build_menu_bar() -> MenuBar {
    let file = Menu::builder()
        .append_item(
            ID_ADD_LOCATION,
            "&Add Location…\tAlt+A",
            "Search for a place and save it",
        )
        .append_item(
            ID_REMOVE_LOCATION,
            "Re&move Location",
            "Remove the selected location",
        )
        .append_separator()
        .append_item(ID_REFRESH, "&Refresh\tF5", "Fetch the latest weather")
        .append_separator()
        .append_item(
            ID_SETTINGS,
            "&Settings…\tCtrl+,",
            "Change units, sources and other options",
        )
        .append_separator()
        .append_item(ID_EXIT, "&Quit\tCtrl+Q", "Quit AccessiWeather")
        .build();
    let weather = Menu::builder()
        .append_item(
            ID_ALERT_DETAILS,
            "&Alert Details",
            "Show the selected alert",
        )
        .append_item(
            ID_DISCUSSION,
            "Forecast &Discussion\tCtrl+D",
            "Read the area forecast discussion",
        )
        .append_separator()
        .append_item(
            ID_READ_ALOUD,
            "Read &Aloud\tCtrl+Shift+S",
            "Speak the current conditions",
        )
        .append_item(ID_STOP_SPEECH, "S&top Speaking", "Stop speech (Escape)")
        .build();
    MenuBar::builder()
        .append(file, "&File")
        .append(weather, "&Weather")
        .build()
}

/// Menu items and the buttons sharing their IDs all route through one handler.
fn wire_commands(ui: &MainUi, state: &Shared) {
    let (ui, state) = (*ui, state.clone());
    let dispatch = Rc::new(move |id: Id| match id {
        ID_ADD_LOCATION => open_add_location(&ui, &state),
        ID_REMOVE_LOCATION => remove_current_location(&ui, &state),
        ID_REFRESH => start_refresh(&ui, &state),
        ID_SETTINGS => open_settings(&ui, &state),
        ID_ALERT_DETAILS => show_alert_details(&ui, &state),
        ID_DISCUSSION => show_discussion(&ui, &state),
        ID_READ_ALOUD => speak_current(&state),
        ID_STOP_SPEECH => state.borrow().speaker.stop(),
        ID_EXIT => ui.frame.close(true),
        _ => {}
    });
    let state = with_state().expect("app state");

    let d = dispatch.clone();
    ui.frame.on_menu(move |e| d(e.get_id()));
    let d = dispatch;
    ui.frame
        .bind_internal(EventType::COMMAND_BUTTON_CLICKED, move |e: Event| {
            d(e.get_id())
        });

    {
        let (ui, state) = (ui, state.clone());
        ui.location_choice.on_selection_changed(move |e| {
            if let Some(index) = e.get_selection() {
                select_location(&ui, &state, index.max(0) as usize);
            }
        });
    }
    {
        let (ui, state) = (ui, state.clone());
        ui.alerts
            .on_item_double_clicked(move |_| show_alert_details(&ui, &state));
    }
    {
        let (ui, state) = (ui, state.clone());
        ui.alerts.on_key_down(move |e| {
            if let WindowEventData::Keyboard(k) = e {
                match k.get_key_code() {
                    Some(WXK_RETURN) | Some(WXK_NUMPAD_ENTER) => show_alert_details(&ui, &state),
                    _ => k.event.skip(true),
                }
            }
        });
    }
}

/// Shortcuts that are not menu accelerators: Escape, Ctrl+R and Ctrl+1…5.
fn wire_keys(ui: &MainUi, state: &Shared) {
    let (ui, state) = (*ui, state.clone());
    ui.frame
        .bind_internal(EventType::CHAR_HOOK, move |e: Event| {
            let code = e.get_key_code().unwrap_or(0);
            let ctrl = e.control_down() || e.cmd_down();
            let handled = match (ctrl, code) {
                (false, WXK_ESCAPE) => {
                    state.borrow().speaker.stop();
                    false
                }
                (true, c) if c == 'R' as i32 || c == 'r' as i32 => {
                    start_refresh(&ui, &state);
                    true
                }
                (true, c) if c == '1' as i32 => ui.location_choice.set_focus_ok(),
                (true, c) if c == '2' as i32 => ui.current.set_focus_ok(),
                (true, c) if c == '3' as i32 => ui.hourly.set_focus_ok(),
                (true, c) if c == '4' as i32 => ui.daily.set_focus_ok(),
                (true, c) if c == '5' as i32 => ui.alerts.set_focus_ok(),
                _ => false,
            };
            e.skip(!handled);
        });
}

trait FocusOk {
    fn set_focus_ok(&self) -> bool;
}
impl<W: WxWidget> FocusOk for W {
    fn set_focus_ok(&self) -> bool {
        self.set_focus();
        true
    }
}

// ---------------------------------------------------------------------------
// Main window state updates
// ---------------------------------------------------------------------------

fn sync_locations(ui: &MainUi, st: &State) {
    ui.location_choice.clear();
    for l in &st.config.locations {
        ui.location_choice.append(&l.name);
    }
    let current = st
        .config
        .current_location
        .as_ref()
        .and_then(|c| st.config.locations.iter().position(|l| l.name == c.name));
    if let Some(i) = current {
        ui.location_choice.set_selection(i as u32);
    }
    ui.remove_button.enable(current.is_some());
    ui.refresh_button.enable(current.is_some());
}

fn clear_weather(ui: &MainUi) {
    ui.summary
        .set_label("No location selected. Press Alt+A to add a location.");
    ui.current.set_value("");
    ui.hourly.set_value("");
    ui.daily.set_value("");
    ui.alerts.clear();
    ui.alerts.append(NO_ALERTS);
    ui.details_button.enable(false);
    ui.discussion_button.enable(false);
}

fn set_status(ui: &MainUi, text: &str) {
    ui.status.set_label(text);
    ui.frame.layout();
}

/// Update the status line and, if enabled, speak it.
fn announce(ui: &MainUi, state: &Shared, text: &str) {
    set_status(ui, text);
    let st = state.borrow();
    if st.config.settings.speech_announcements {
        st.speaker.speak(text, true);
    }
}

fn speak_current(state: &Shared) {
    let st = state.borrow();
    let text = st
        .last_presentation
        .as_ref()
        .map(|p| format!("{}\n{}", p.summary_text, p.current_text))
        .unwrap_or_else(|| "No weather data loaded yet.".to_string());
    st.speaker.speak(text, true);
}

fn select_location(ui: &MainUi, state: &Shared, index: usize) {
    let name = {
        let mut st = state.borrow_mut();
        let Some(loc) = st.config.locations.get(index).cloned() else {
            return;
        };
        st.config.set_current_location(&loc.name);
        let _ = save(&st);
        loc.name
    };
    set_status(ui, &format!("Selected {name}. Refreshing…"));
    start_refresh(ui, state);
}

fn remove_current_location(ui: &MainUi, state: &Shared) {
    let removed = {
        let mut st = state.borrow_mut();
        let Some(current) = st.config.current_location.clone() else {
            return;
        };
        st.config.remove_location(&current.name);
        st.config.normalize();
        let _ = save(&st);
        st.last_data = None;
        st.last_presentation = None;
        current.name
    };
    sync_locations(ui, &state.borrow());
    clear_weather(ui);
    announce(ui, state, &format!("Removed {removed}."));
    if state.borrow().config.current_location.is_some() {
        start_refresh(ui, state);
    }
}

fn schedule_refresh_timer(state: &Shared) {
    let Some(ui) = main_ui() else { return };
    TIMERS.with(|t| t.borrow_mut().retain(|timer| !timer.is_running()));
    let minutes = state.borrow().config.settings.update_interval_minutes();
    let timer = Timer::new(&ui.frame);
    let state = state.clone();
    timer.on_tick(move |_| {
        if let Some(ui) = main_ui() {
            start_refresh(&ui, &state);
        }
    });
    timer.start((minutes * 60 * 1000).min(i32::MAX as u64) as i32, false);
    TIMERS.with(|t| t.borrow_mut().push(timer));
}

fn start_refresh(ui: &MainUi, state: &Shared) {
    let (location, settings, client) = {
        let mut st = state.borrow_mut();
        let Some(loc) = st.config.current_location.clone() else {
            set_status(ui, "Add a location first.");
            return;
        };
        if st.busy {
            return;
        }
        st.busy = true;
        (loc, st.config.settings.clone(), st.client.clone())
    };
    ui.refresh_button.enable(false);
    set_status(ui, &format!("Refreshing weather for {}…", location.name));

    std::thread::Builder::new()
        .name("aw-refresh".into())
        .spawn(move || {
            let data = client.fetch(&settings, &location);
            let presentation = WeatherPresenter::new(&settings).present(&data);
            post_to_ui(move || {
                let (Some(ui), Some(state)) = (main_ui(), with_state()) else {
                    return;
                };
                let status = status_for(&data, &presentation);
                apply_weather(&ui, &presentation, data.discussion.is_some());
                {
                    let mut st = state.borrow_mut();
                    st.busy = false;
                    remember_weather(&mut st, data, presentation);
                }
                ui.refresh_button.enable(true);
                announce(&ui, &state, &status);
            });
        })
        .expect("spawn refresh thread");
}

fn apply_weather(ui: &MainUi, p: &WeatherPresentation, has_discussion: bool) {
    ui.summary.set_label(&p.summary_text);
    ui.current.set_value(&p.current_text);
    ui.hourly.set_value(&p.hourly_text);
    ui.daily.set_value(&p.daily_text);
    ui.alerts.clear();
    if p.alert_labels.is_empty() {
        ui.alerts.append(NO_ALERTS);
    } else {
        for label in &p.alert_labels {
            ui.alerts.append(label);
        }
        ui.alerts.set_selection(0, true);
    }
    ui.details_button.enable(!p.alert_labels.is_empty());
    ui.discussion_button.enable(has_discussion);
    ui.frame.layout();
}

fn show_alert_details(ui: &MainUi, state: &Shared) {
    let index = ui.alerts.get_selection().unwrap_or(0) as usize;
    let (label, detail) = {
        let st = state.borrow();
        let Some(p) = &st.last_presentation else {
            set_status(ui, "No alerts loaded.");
            return;
        };
        match (p.alert_labels.get(index), p.alert_details.get(index)) {
            (Some(l), Some(d)) => (l.clone(), d.clone()),
            _ => {
                set_status(ui, "There are no active alerts for this location.");
                return;
            }
        }
    };
    open_text_dialog(ui, state, &label, &detail, "Alert details");
}

fn show_discussion(ui: &MainUi, state: &Shared) {
    let text = state
        .borrow()
        .last_data
        .as_ref()
        .and_then(|d| d.discussion.clone());
    match text {
        Some(t) => open_text_dialog(
            ui,
            state,
            "Area Forecast Discussion",
            &t,
            "Forecast discussion text",
        ),
        None => set_status(ui, "No forecast discussion is available for this location."),
    }
}

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

fn dialog_frame(parent: &Frame, title: &str, w: i32, h: i32) -> Dialog {
    Dialog::builder(parent, title)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(w, h)
        .build()
}

fn open_text_dialog(ui: &MainUi, state: &Shared, heading: &str, body: &str, label: &str) {
    let dlg = dialog_frame(&ui.frame, heading, 640, 480);
    let root = BoxSizer::builder(Orientation::Vertical).build();
    let text = TextCtrl::builder(&dlg)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::WordWrap)
        .with_value(body)
        .build();
    label_control(&text, label, None);
    root.add(&text, 1, SizerFlag::Expand | SizerFlag::All, 8);

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    let speak = Button::builder(&dlg)
        .with_id(ID_READ_ALOUD)
        .with_label("Read a&loud")
        .build();
    label_control(&speak, "Read aloud", Some("Speak this text"));
    let close = Button::builder(&dlg)
        .with_id(ID_CANCEL)
        .with_label("&Close")
        .build();
    buttons.add(&speak, 0, SizerFlag::Right, 6);
    buttons.add(&close, 0, SizerFlag::Right, 0);
    root.add_sizer(
        &buttons,
        0,
        SizerFlag::AlignRight | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        8,
    );
    dlg.set_sizer(root, true);
    dlg.set_escape_id(ID_CANCEL);
    close.set_default();

    {
        let state = state.clone();
        let spoken = format!("{heading}. {body}");
        speak.on_click(move |_| state.borrow().speaker.speak(spoken.clone(), true));
    }
    text.set_focus();
    text.set_insertion_point(0);
    dlg.show_modal();
    dlg.destroy();
}

#[derive(Clone, Copy)]
struct AddDialogUi {
    dialog: Dialog,
    query: TextCtrl,
    results: ListBox,
    status: StaticText,
    add_button: Button,
}

fn open_add_location(ui: &MainUi, state: &Shared) {
    let dlg = dialog_frame(&ui.frame, "Add Location", 560, 420);
    let root = BoxSizer::builder(Orientation::Vertical).build();

    let query_label = StaticText::builder(&dlg)
        .with_label("&Search for a place, address or coordinates:")
        .build();
    let query = TextCtrl::builder(&dlg)
        .with_style(TextCtrlStyle::ProcessEnter)
        .build();
    label_control(
        &query,
        "Search for a place",
        Some("Type a city, address or latitude, longitude and press Enter"),
    );
    let search = Button::builder(&dlg)
        .with_id(ID_SEARCH)
        .with_label("Searc&h")
        .build();
    let row = BoxSizer::builder(Orientation::Horizontal).build();
    row.add(&query, 1, SizerFlag::Right, 6);
    row.add(&search, 0, SizerFlag::Right, 0);
    root.add(
        &query_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        8,
    );
    root.add_sizer(&row, 0, SizerFlag::Expand | SizerFlag::All, 8);

    let results_label = StaticText::builder(&dlg).with_label("&Results:").build();
    let results = ListBox::builder(&dlg).with_size(Size::new(-1, 160)).build();
    label_control(
        &results,
        "Search results",
        Some("Choose a result and press Enter to add it"),
    );
    root.add(&results_label, 0, SizerFlag::Left | SizerFlag::Right, 8);
    root.add(&results, 1, SizerFlag::Expand | SizerFlag::All, 8);

    let name_label = StaticText::builder(&dlg)
        .with_label("Custom &name (optional):")
        .build();
    let name = TextCtrl::builder(&dlg).build();
    label_control(
        &name,
        "Custom name",
        Some("Optional display name for this location"),
    );
    root.add(&name_label, 0, SizerFlag::Left | SizerFlag::Right, 8);
    root.add(&name, 0, SizerFlag::Expand | SizerFlag::All, 8);

    let status = StaticText::builder(&dlg)
        .with_label("Enter a place name and press Enter to search.")
        .build();
    label_control(&status, "Search status", None);
    root.add(
        &status,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        8,
    );

    let buttons = StdDialogButtonSizerBuilder::new().build();
    let add_button = Button::builder(&dlg)
        .with_id(ID_OK)
        .with_label("&Add")
        .build();
    let cancel = Button::builder(&dlg)
        .with_id(ID_CANCEL)
        .with_label("Cancel")
        .build();
    buttons.add_button(&add_button);
    buttons.add_button(&cancel);
    buttons.realize();
    root.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 8);
    dlg.set_sizer(root, true);
    dlg.set_escape_id(ID_CANCEL);
    add_button.enable(false);

    let add_ui = AddDialogUi {
        dialog: dlg,
        query,
        results,
        status,
        add_button,
    };
    ADD_DIALOG.with(|d| *d.borrow_mut() = Some(add_ui));
    SEARCH_RESULTS.with(|r| r.borrow_mut().clear());

    {
        let state = state.clone();
        let run_search = move || run_geocode_search(&add_ui, &state);
        let s = run_search.clone();
        search.on_click(move |_| s());
        let s = run_search.clone();
        query.on_text_enter(move |_| s());
    }
    results.on_item_double_clicked(move |_| {
        if results.get_selection().is_some() {
            dlg.end_modal(ID_OK);
        }
    });
    results.on_key_down(move |e| {
        if let WindowEventData::Keyboard(k) = e {
            match k.get_key_code() {
                Some(WXK_RETURN) | Some(WXK_NUMPAD_ENTER) if results.get_selection().is_some() => {
                    dlg.end_modal(ID_OK)
                }
                _ => k.event.skip(true),
            }
        }
    });

    query.set_focus();
    let accepted = dlg.show_modal() == ID_OK;
    let picked = SEARCH_RESULTS.with(|r| {
        results
            .get_selection()
            .and_then(|i| r.borrow().get(i as usize).cloned())
    });
    let custom = name.get_value().trim().to_string();
    ADD_DIALOG.with(|d| *d.borrow_mut() = None);
    dlg.destroy();

    if !accepted {
        return;
    }
    let Some(mut loc) = picked else {
        set_status(ui, "No search result was chosen.");
        return;
    };
    if !custom.is_empty() {
        loc.name = custom;
    }
    {
        let mut st = state.borrow_mut();
        st.config.upsert_location(loc.clone());
        st.config.set_current_location(&loc.name);
        if let Err(e) = save(&st) {
            drop(st);
            set_status(ui, &format!("Could not save location: {e}"));
            return;
        }
    }
    sync_locations(ui, &state.borrow());
    announce(ui, state, &format!("Added {}. Refreshing…", loc.name));
    start_refresh(ui, state);
}

fn run_geocode_search(d: &AddDialogUi, state: &Shared) {
    let query = d.query.get_value().trim().to_string();
    if query.is_empty() {
        d.status
            .set_label("Enter a place name, address or coordinates first.");
        return;
    }
    d.status.set_label(&format!("Searching for \"{query}\"…"));
    d.dialog.layout();
    let client = state.borrow().client.clone();
    std::thread::Builder::new()
        .name("aw-geocode".into())
        .spawn(move || {
            let outcome = Geocoder::new(client.http()).search(&query, 8);
            post_to_ui(move || {
                let Some(d) = ADD_DIALOG.with(|d| *d.borrow()) else { return };
                d.results.clear();
                match outcome {
                    Ok(found) if found.is_empty() => {
                        d.status.set_label(&format!("No matches for \"{query}\"."));
                        d.add_button.enable(false);
                        SEARCH_RESULTS.with(|r| r.borrow_mut().clear());
                    }
                    Ok(found) => {
                        for r in &found {
                            d.results.append(&r.display_name);
                        }
                        d.results.set_selection(0, true);
                        d.add_button.enable(true);
                        d.status.set_label(&format!(
                            "{} result{} found. Use the arrow keys to choose one, then press Enter.",
                            found.len(),
                            if found.len() == 1 { "" } else { "s" }
                        ));
                        SEARCH_RESULTS.with(|r| {
                            *r.borrow_mut() = found.into_iter().map(|r| r.location).collect()
                        });
                        d.results.set_focus();
                    }
                    Err(e) => d.status.set_label(&format!("Search failed: {e}")),
                }
                d.dialog.layout();
            });
        })
        .expect("spawn geocode thread");
}

const TEMP_UNITS: [(&str, &str); 3] = [("f", "Fahrenheit"), ("c", "Celsius"), ("both", "Both")];
const SOURCES: [(&str, &str); 4] = [
    ("auto", "Automatic"),
    ("nws", "National Weather Service"),
    ("openmeteo", "Open-Meteo"),
    ("pirateweather", "Pirate Weather"),
];
const VERBOSITY: [(&str, &str); 3] = [
    ("minimal", "Minimal"),
    ("standard", "Standard"),
    ("detailed", "Detailed"),
];
const BUDGETS: [(&str, &str); 3] = [
    ("economy", "Economy"),
    ("balanced", "Balanced"),
    ("max_coverage", "Maximum coverage"),
];

fn index_of(options: &[(&str, &str)], value: &str, default: u32) -> u32 {
    options
        .iter()
        .position(|(k, _)| k.eq_ignore_ascii_case(value.trim()))
        .map_or(default, |i| i as u32)
}

fn pick(options: &[(&str, &str)], index: Option<u32>) -> String {
    let i = (index.unwrap_or(0) as usize).min(options.len() - 1);
    options[i].0.to_string()
}

fn choice_row(
    dlg: &Dialog,
    root: &BoxSizer,
    label: &str,
    name: &str,
    options: &[(&str, &str)],
    selected: u32,
) -> Choice {
    let row = BoxSizer::builder(Orientation::Horizontal).build();
    let text = StaticText::builder(dlg).with_label(label).build();
    let choice = Choice::builder(dlg)
        .with_choices(options.iter().map(|(_, l)| l.to_string()).collect())
        .with_selection(Some(selected))
        .build();
    label_control(&choice, name, None);
    row.add(
        &text,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        6,
    );
    row.add(&choice, 1, SizerFlag::AlignCenterVertical, 0);
    root.add_sizer(
        &row,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        8,
    );
    choice
}

fn spin_row(
    dlg: &Dialog,
    root: &BoxSizer,
    label: &str,
    name: &str,
    min: i32,
    max: i32,
    value: i32,
) -> SpinCtrl {
    let row = BoxSizer::builder(Orientation::Horizontal).build();
    let text = StaticText::builder(dlg).with_label(label).build();
    let spin = SpinCtrl::builder(dlg)
        .with_min_value(min)
        .with_max_value(max)
        .with_initial_value(value.clamp(min, max))
        .build();
    let hint = format!("{name}, {min} to {max}");
    label_control(&spin, name, Some(&hint));
    row.add(
        &text,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        6,
    );
    row.add(&spin, 0, SizerFlag::AlignCenterVertical, 0);
    root.add_sizer(
        &row,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        8,
    );
    spin
}

fn check(dlg: &Dialog, root: &BoxSizer, label: &str, value: bool) -> CheckBox {
    let cb = CheckBox::builder(dlg)
        .with_label(label)
        .with_value(value)
        .build();
    root.add(
        &cb,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        8,
    );
    cb
}

fn open_settings(ui: &MainUi, state: &Shared) {
    let dlg = dialog_frame(&ui.frame, "Settings", 520, 640);
    let root = BoxSizer::builder(Orientation::Vertical).build();
    let s = state.borrow().config.settings.clone();

    let temp = choice_row(
        &dlg,
        &root,
        "&Temperature unit:",
        "Temperature unit",
        &TEMP_UNITS,
        index_of(&TEMP_UNITS, &s.temperature_unit, 2),
    );
    let source = choice_row(
        &dlg,
        &root,
        "&Data source:",
        "Data source",
        &SOURCES,
        index_of(&SOURCES, &s.data_source, 0),
    );
    let budget = choice_row(
        &dlg,
        &root,
        "Automatic mode API &budget:",
        "API budget",
        &BUDGETS,
        index_of(&BUDGETS, &s.auto_mode_api_budget, 2),
    );
    let verbosity = choice_row(
        &dlg,
        &root,
        "Forecast &verbosity:",
        "Forecast verbosity",
        &VERBOSITY,
        index_of(&VERBOSITY, &s.verbosity_level, 1),
    );
    let interval = spin_row(
        &dlg,
        &root,
        "&Update interval (minutes):",
        "Update interval in minutes",
        1,
        1440,
        s.update_interval_minutes() as i32,
    );
    let days = spin_row(
        &dlg,
        &root,
        "&Forecast days:",
        "Forecast days",
        3,
        16,
        s.forecast_days() as i32,
    );
    let hours = spin_row(
        &dlg,
        &root,
        "&Hourly forecast hours:",
        "Hourly forecast hours",
        1,
        48,
        s.hourly_hours().min(48) as i32,
    );

    let key_label = StaticText::builder(&dlg)
        .with_label("&Pirate Weather API key:")
        .build();
    let key = TextCtrl::builder(&dlg)
        .with_style(TextCtrlStyle::Password)
        .with_value(&s.pirate_weather_api_key)
        .build();
    label_control(&key, "Pirate Weather API key", None);
    root.add(
        &key_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        8,
    );
    root.add(
        &key,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        8,
    );

    let alerts = check(&dlg, &root, "Show weather &alerts", s.enable_alerts);
    let speech = check(&dlg, &root, "&Speak status updates", s.speech_announcements);
    let dewpoint = check(&dlg, &root, "Show de&wpoint", s.show_dewpoint);
    let pressure = check(&dlg, &root, "Show pressure t&rend", s.show_pressure_trend);
    let visibility = check(&dlg, &root, "Show visi&bility", s.show_visibility);
    let uv = check(&dlg, &root, "Show UV inde&x", s.show_uv_index);
    let tray = check(&dlg, &root, "Minimize to tra&y", s.minimize_to_tray);

    let buttons = StdDialogButtonSizerBuilder::new().build();
    let save_button = Button::builder(&dlg)
        .with_id(ID_OK)
        .with_label("&Save")
        .build();
    let cancel = Button::builder(&dlg)
        .with_id(ID_CANCEL)
        .with_label("Cancel")
        .build();
    buttons.add_button(&save_button);
    buttons.add_button(&cancel);
    buttons.realize();
    root.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 8);
    dlg.set_sizer(root, true);
    dlg.set_escape_id(ID_CANCEL);
    save_button.set_default();
    temp.set_focus();

    let accepted = dlg.show_modal() == ID_OK;
    if !accepted {
        dlg.destroy();
        return;
    }
    let interval_changed;
    {
        let mut st = state.borrow_mut();
        let s = &mut st.config.settings;
        let old_interval = s.update_interval_minutes;
        s.temperature_unit = pick(&TEMP_UNITS, temp.get_selection());
        s.data_source = pick(&SOURCES, source.get_selection());
        s.auto_mode_api_budget = pick(&BUDGETS, budget.get_selection());
        s.verbosity_level = pick(&VERBOSITY, verbosity.get_selection());
        s.update_interval_minutes = interval.value() as i64;
        s.forecast_duration_days = days.value() as i64;
        s.hourly_forecast_hours = hours.value() as i64;
        s.pirate_weather_api_key = key.get_value().trim().to_string();
        s.enable_alerts = alerts.is_checked();
        s.speech_announcements = speech.is_checked();
        s.show_dewpoint = dewpoint.is_checked();
        s.show_pressure_trend = pressure.is_checked();
        s.show_visibility = visibility.is_checked();
        s.show_uv_index = uv.is_checked();
        s.minimize_to_tray = tray.is_checked();
        interval_changed = old_interval != s.update_interval_minutes;
        if let Err(e) = save(&st) {
            drop(st);
            dlg.destroy();
            set_status(ui, &format!("Could not save settings: {e}"));
            return;
        }
    }
    dlg.destroy();
    if interval_changed {
        schedule_refresh_timer(state);
    }
    announce(ui, state, "Settings saved. Refreshing…");
    start_refresh(ui, state);
}
