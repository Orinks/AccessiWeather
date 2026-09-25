//! The Settings dialog's own modals: Advanced Alert Timing
//! (`AlertAdvancedSettingsDialog` in `settings_dialog.py`), Configure Event
//! Sounds and Configure Source Settings (`settings_dialog_modals.py`).

use aw_core::sound_events::{user_mutable_sound_events, SOUND_EVENT_SECTIONS};
use wxdragon::prelude::*;

use super::settings_form::SourceSettings;

const STATION_STRATEGY_CHOICES: [&str; 4] = [
    "Hybrid default (recommended: fresh + major station with distance guardrail)",
    "Nearest station (pure distance)",
    "Major airport preferred (within radius, else nearest)",
    "Freshest observation (among nearest stations)",
];
const AUTO_BUDGET_CHOICES: [&str; 3] = [
    "Economy (use the fewest API calls that still cover the basics)",
    "Balanced (allow one useful fallback when Automatic mode needs it)",
    "Max coverage (fan out to every enabled source)",
];

/// `_configure_modal_dialog_buttons`.
fn configure_buttons(dialog: &Dialog, ok: &Button, focus: &dyn WxWidget) {
    dialog.set_affirmative_id(ID_OK);
    dialog.set_escape_id(ID_CANCEL);
    ok.set_default();
    focus.set_focus();
}

/// A right-aligned row of "OK" and "Cancel" (or "Cancel" then "OK");
/// returns the OK button.
fn button_row(dialog: &Dialog, sizer: &BoxSizer, ok_first: bool) -> Button {
    let row = BoxSizer::builder(Orientation::Horizontal).build();
    row.add_stretch_spacer(1);
    let make = |id, label| {
        Button::builder(dialog)
            .with_id(id)
            .with_label(label)
            .build()
    };
    let (first, second) = if ok_first {
        (make(ID_OK, "OK"), make(ID_CANCEL, "Cancel"))
    } else {
        (make(ID_CANCEL, "Cancel"), make(ID_OK, "OK"))
    };
    row.add(&first, 0, SizerFlag::Right, 10);
    row.add(&second, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(
        &row,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );
    if ok_first {
        first
    } else {
        second
    }
}

/// `AlertAdvancedSettingsDialog`: the three hidden timing values, returned
/// changed on OK.
pub(crate) fn show_alert_timing_dialog(
    parent: &dyn WxWidget,
    values: (i32, i32, i32),
) -> Option<(i32, i32, i32)> {
    let dialog = Dialog::builder(parent, "Advanced Alert Timing")
        .with_style(DialogStyle::DefaultDialogStyle)
        .build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();
    let spin_row = |label: &str, min, max, initial, flags, name: &str| {
        let row = BoxSizer::builder(Orientation::Horizontal).build();
        let text = StaticText::builder(&dialog).with_label(label).build();
        row.add(
            &text,
            0,
            SizerFlag::AlignCenterVertical | SizerFlag::Right,
            10,
        );
        let spin = SpinCtrl::builder(&dialog)
            .with_range(min, max)
            .with_initial_value(initial)
            .build();
        spin.set_name(name);
        row.add(&spin, 0, SizerFlag::empty(), 0);
        sizer.add_sizer(&row, 0, flags, 10);
        spin
    };
    let later = SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom;
    let global = spin_row(
        "Minimum time between any alert notifications (minutes):",
        0,
        60,
        5,
        SizerFlag::All,
        "Minimum time between any alert notifications (minutes)",
    );
    let per_alert = spin_row(
        "Re-notify for same alert after (minutes):",
        0,
        1440,
        60,
        later,
        "Re-notify for same alert after (minutes)",
    );
    let freshness = spin_row(
        "Only notify for alerts issued within (minutes):",
        0,
        120,
        15,
        later,
        "Only notify for alerts issued within (minutes)",
    );
    let buttons = StdDialogButtonSizerBuilder::new().build();
    let ok = Button::builder(&dialog).with_id(ID_OK).build();
    ok.set_default();
    buttons.add_button(&ok);
    let cancel = Button::builder(&dialog).with_id(ID_CANCEL).build();
    buttons.add_button(&cancel);
    buttons.realize();
    sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 10);
    dialog.set_sizer(sizer, true);
    dialog.fit();

    global.set_value(values.0);
    per_alert.set_value(values.1);
    freshness.set_value(values.2);

    let accepted = dialog.show_modal() == ID_OK;
    let result = (global.value(), per_alert.value(), freshness.value());
    dialog.destroy();
    accepted.then_some(result)
}

/// `_run_event_sounds_dialog`: each selectable event's on/off state, in
/// `USER_MUTABLE_SOUND_EVENTS` order, when accepted.
pub(crate) fn show_event_sounds_dialog(
    parent: &dyn WxWidget,
    states: &[(&'static str, bool)],
) -> Option<Vec<(&'static str, bool)>> {
    let dialog = Dialog::builder(parent, "Configure Event Sounds")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(460, 420)
        .build();
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let intro = StaticText::builder(&dialog)
        .with_label("Choose which events can play sounds.")
        .build();
    main_sizer.add(&intro, 0, SizerFlag::All | SizerFlag::Expand, 10);

    let scroll = ScrolledWindow::builder(&dialog)
        .with_style(ScrolledWindowStyle::HScroll | ScrolledWindowStyle::VScroll)
        .build();
    scroll.set_scroll_rate(0, 20);
    let scroll_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let lrbe = SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom | SizerFlag::Expand;
    let mut checkboxes: Vec<(&'static str, CheckBox)> = Vec::new();
    for (title, description, events) in SOUND_EVENT_SECTIONS {
        let section = BoxSizer::builder(Orientation::Vertical).build();
        let heading = StaticText::builder(&scroll).with_label(title).build();
        heading.wrap(380);
        section.add(&heading, 0, lrbe, 5);
        for (key, label) in events {
            let checkbox = CheckBox::builder(&scroll)
                .with_label(label)
                .with_value(
                    states
                        .iter()
                        .find(|(k, _)| k == key)
                        .is_none_or(|(_, on)| *on),
                )
                .build();
            section.add(
                &checkbox,
                0,
                SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
                5,
            );
            checkboxes.push((key, checkbox));
        }
        let description_text = StaticText::builder(&scroll).with_label(description).build();
        description_text.wrap(380);
        section.add(&description_text, 0, lrbe, 5);
        scroll_sizer.add_sizer(&section, 0, SizerFlag::All | SizerFlag::Expand, 5);
    }
    scroll.set_sizer(scroll_sizer, true);
    main_sizer.add(&scroll, 1, lrbe, 10);
    let ok = button_row(&dialog, &main_sizer, true);
    dialog.set_sizer(main_sizer, true);
    configure_buttons(&dialog, &ok, &checkboxes[0].1);

    let accepted = dialog.show_modal() == ID_OK;
    let result = accepted.then(|| {
        user_mutable_sound_events()
            .map(|(key, _)| {
                let on = checkboxes
                    .iter()
                    .find(|(k, _)| *k == key)
                    .is_none_or(|(_, cb)| cb.is_checked());
                (key, on)
            })
            .collect()
    });
    dialog.destroy();
    result
}

/// `_run_source_settings_dialog`: the two-tab source settings editor.
pub(crate) fn show_source_settings_dialog(
    parent: &dyn WxWidget,
    state: &SourceSettings,
) -> Option<SourceSettings> {
    let dialog = Dialog::builder(parent, "Configure Source Settings")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(500, 400)
        .build();
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let notebook = Notebook::builder(&dialog).build();
    let labeled_choice =
        |panel: &ScrolledWindow, sizer: &BoxSizer, label: &str, choices: &[&str]| {
            let row = BoxSizer::builder(Orientation::Horizontal).build();
            let text = StaticText::builder(panel).with_label(label).build();
            row.add(
                &text,
                0,
                SizerFlag::AlignCenterVertical | SizerFlag::Right,
                10,
            );
            let choice = Choice::builder(panel)
                .with_choices(choices.iter().map(|c| c.to_string()).collect())
                .build();
            row.add(&choice, 1, SizerFlag::Expand, 0);
            sizer.add_sizer(
                &row,
                0,
                SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom | SizerFlag::Expand,
                10,
            );
            choice
        };
    let page = || {
        let panel = ScrolledWindow::builder(&notebook)
            .with_style(ScrolledWindowStyle::HScroll | ScrolledWindowStyle::VScroll)
            .build();
        panel.set_scroll_rate(0, 20);
        (panel, BoxSizer::builder(Orientation::Vertical).build())
    };
    let intro = |panel: &ScrolledWindow, sizer: &BoxSizer, label: &str| {
        let text = StaticText::builder(panel).with_label(label).build();
        sizer.add(&text, 0, SizerFlag::All | SizerFlag::Expand, 10);
    };

    // Tab 1: Current Conditions
    let (cc_panel, cc_sizer) = page();
    intro(
        &cc_panel,
        &cc_sizer,
        "These settings control how current conditions are fetched when using NWS (US locations).",
    );
    let strategy = labeled_choice(
        &cc_panel,
        &cc_sizer,
        "NWS station selection strategy:",
        &STATION_STRATEGY_CHOICES,
    );
    strategy.set_selection(state.station_selection_strategy.max(0) as u32);
    cc_panel.set_sizer(cc_sizer, true);
    notebook.add_page(&cc_panel, "Current Conditions", false, None);

    // Tab 2: Auto Mode
    let (auto_panel, auto_sizer) = page();
    intro(
        &auto_panel,
        &auto_sizer,
        "Choose how aggressively Automatic mode should spend API calls. Max coverage keeps the historical fusion-first behavior. Economy and Balanced are reduced-call opt-in modes. Set US and international source lists separately so each region keeps its own exact ordering.",
    );
    let budget = labeled_choice(
        &auto_panel,
        &auto_sizer,
        "Automatic mode API budget:",
        &AUTO_BUDGET_CHOICES,
    );
    budget.set_selection(state.auto_mode_api_budget.max(0) as u32);
    let region = |label: &str| {
        let text = StaticText::builder(&auto_panel).with_label(label).build();
        auto_sizer.add(
            &text,
            0,
            SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
            10,
        );
    };
    let source = |label: &str, on: bool| {
        let cb = CheckBox::builder(&auto_panel)
            .with_label(label)
            .with_value(on)
            .build();
        auto_sizer.add(
            &cb,
            0,
            SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
            20,
        );
        cb
    };
    let has = |list: &[String], name: &str| list.iter().any(|s| s == name);
    region("US automatic sources:");
    let us_nws = source(
        "National Weather Service",
        has(&state.auto_sources_us, "nws"),
    );
    let us_openmeteo = source("Open-Meteo", has(&state.auto_sources_us, "openmeteo"));
    let us_pw = source(
        "Pirate Weather (requires API key)",
        has(&state.auto_sources_us, "pirateweather"),
    );
    region("International automatic sources:");
    let intl_openmeteo = source(
        "Open-Meteo",
        has(&state.auto_sources_international, "openmeteo"),
    );
    let intl_pw = source(
        "Pirate Weather (requires API key)",
        has(&state.auto_sources_international, "pirateweather"),
    );
    auto_panel.set_sizer(auto_sizer, true);
    notebook.add_page(&auto_panel, "Auto Mode", false, None);

    main_sizer.add(&notebook, 1, SizerFlag::Expand | SizerFlag::All, 10);
    let ok = button_row(&dialog, &main_sizer, false);
    dialog.set_sizer(main_sizer, true);
    configure_buttons(&dialog, &ok, &notebook);

    let accepted = dialog.show_modal() == ID_OK;
    let selection = |c: &Choice| c.get_selection().map_or(-1, |i| i as i32);
    let result = accepted.then(|| {
        SourceSettings::from_dialog(
            selection(&budget),
            selection(&strategy),
            [
                us_nws.is_checked(),
                us_openmeteo.is_checked(),
                us_pw.is_checked(),
            ],
            [intl_openmeteo.is_checked(), intl_pw.is_checked()],
        )
    });
    dialog.destroy();
    result
}
