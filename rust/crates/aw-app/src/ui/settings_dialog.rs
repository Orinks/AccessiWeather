//! Interim settings dialog carried over from the first Rust UI. It stays
//! reachable from File > Settings, Ctrl+S and the Settings button until the
//! settings workstream ports `ui/dialogs/settings_dialog.py`.

use wxdragon::prelude::*;

use crate::app::{save, Shared};

/// Control labels with `&` mnemonics. wxOSX turns mnemonic letters on buttons
/// into Cmd+letter shortcuts that shadow menu accelerators, so strip them there.
#[cfg(target_os = "macos")]
fn mn(label: &str) -> String {
    label.replace('&', "")
}
#[cfg(not(target_os = "macos"))]
fn mn(label: &str) -> String {
    label.to_string()
}

fn label_control<W: WxWidget>(w: &W, name: &str, description: Option<&str>) {
    w.set_name(name);
    w.set_accessibility_label(name);
    if let Some(d) = description {
        w.set_accessibility_description(d);
        w.set_tooltip(d);
    }
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

/// Returns true when the user saved.
pub(crate) fn show_settings_dialog(parent: &Frame, state: &Shared) -> bool {
    let dlg = Dialog::builder(parent, "Settings")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(520, 640)
        .build();
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
        .with_label(&mn("&Pirate Weather API key:"))
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
    let dewpoint = check(&dlg, &root, "Show de&wpoint", s.show_dewpoint);
    let pressure = check(&dlg, &root, "Show pressure t&rend", s.show_pressure_trend);
    let visibility = check(&dlg, &root, "Show visi&bility", s.show_visibility);
    let uv = check(&dlg, &root, "Show UV inde&x", s.show_uv_index);
    let tray = check(&dlg, &root, "Minimize to tra&y", s.minimize_to_tray);

    let buttons = StdDialogButtonSizerBuilder::new().build();
    let save_button = Button::builder(&dlg)
        .with_id(ID_OK)
        .with_label(&mn("&Save"))
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
        return false;
    }
    {
        let mut st = state.borrow_mut();
        let s = &mut st.config.settings;
        s.temperature_unit = pick(&TEMP_UNITS, temp.get_selection());
        s.data_source = pick(&SOURCES, source.get_selection());
        s.auto_mode_api_budget = pick(&BUDGETS, budget.get_selection());
        s.verbosity_level = pick(&VERBOSITY, verbosity.get_selection());
        s.update_interval_minutes = interval.value() as i64;
        s.forecast_duration_days = days.value() as i64;
        s.hourly_forecast_hours = hours.value() as i64;
        s.enable_alerts = alerts.is_checked();
        s.show_dewpoint = dewpoint.is_checked();
        s.show_pressure_trend = pressure.is_checked();
        s.show_visibility = visibility.is_checked();
        s.show_uv_index = uv.is_checked();
        s.minimize_to_tray = tray.is_checked();
        let new_key = key.get_value();
        if new_key.trim() != s.pirate_weather_api_key {
            crate::app::save_api_key(&mut st, "pirate_weather_api_key", &new_key);
        }
        let _ = save(&st);
    }
    dlg.destroy();
    true
}
