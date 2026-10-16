//! Tray text format editor with a live preview, ported from
//! `ui/dialogs/tray_text_format_dialog.py`, plus the placeholder checks it
//! uses from `format_string_parser.py`.

use wxdragon::prelude::*;

use super::main_window::message_box;
use super::settings_actions::{self, TrayPreviewContext};

pub(crate) const DEFAULT_TOOLTIP_FORMAT: &str = "{temp} {condition}";

/// `FormatStringParser.SUPPORTED_PLACEHOLDERS`.
const SUPPORTED_PLACEHOLDERS: [(&str, &str); 18] = [
    (
        "alert",
        "Most severe active weather alert event name (e.g. 'Tornado Watch'), or empty if none",
    ),
    (
        "condition",
        "Current weather condition (e.g., 'Partly Cloudy')",
    ),
    (
        "feels_like",
        "Feels-like temperature (follows your temperature unit setting)",
    ),
    (
        "high",
        "Forecast high temperature when available (follows your temperature unit setting)",
    ),
    ("humidity", "Current humidity percentage"),
    ("location", "Current location name"),
    (
        "low",
        "Forecast low temperature when available (follows your temperature unit setting)",
    ),
    (
        "precip",
        "Precipitation amount (follows your temperature unit setting)",
    ),
    ("precip_chance", "Chance of precipitation percentage"),
    (
        "pressure",
        "Barometric pressure (follows your temperature unit setting)",
    ),
    (
        "temp",
        "Current temperature (follows your temperature unit setting)",
    ),
    ("temp_c", "Current temperature in Celsius"),
    ("temp_f", "Current temperature in Fahrenheit"),
    ("uv", "UV index"),
    (
        "visibility",
        "Visibility (follows your temperature unit setting)",
    ),
    (
        "wind",
        "Wind direction with speed text (e.g., 'NW at 5 mph')",
    ),
    ("wind_dir", "Wind direction (e.g., 'NW')"),
    (
        "wind_speed",
        "Wind speed (follows your temperature unit setting)",
    ),
];

/// `get_supported_placeholders_help`.
pub(crate) fn supported_placeholders_help() -> String {
    let mut help = String::from("Supported Placeholders:\n\n");
    for (name, description) in SUPPORTED_PLACEHOLDERS {
        help.push_str(&format!("{{{name}}}: {description}\n"));
    }
    help
}

/// `get_placeholders`: names matched by `\{([a-zA-Z_]+)\}`, left to right.
fn placeholders(format: &str) -> Vec<&str> {
    let mut found = Vec::new();
    let mut rest = format;
    while let Some(open) = rest.find('{') {
        let after = &rest[open + 1..];
        let len = after
            .find(|c: char| !(c.is_ascii_alphabetic() || c == '_'))
            .unwrap_or(after.len());
        if len > 0 && after[len..].starts_with('}') {
            found.push(&after[..len]);
            rest = &after[len + 1..];
        } else {
            rest = after;
        }
    }
    found
}

/// `validate_format_string`: the problem Python reports, if any.
pub(crate) fn validate_format_string(format: &str) -> Result<(), String> {
    if format.is_empty() {
        return Ok(());
    }
    if format.matches('{').count() != format.matches('}').count() {
        return Err("Unbalanced braces in format string".into());
    }
    let unsupported: Vec<&str> = placeholders(format)
        .into_iter()
        .filter(|p| !SUPPORTED_PLACEHOLDERS.iter().any(|(name, _)| name == p))
        .collect();
    if unsupported.is_empty() {
        return Ok(());
    }
    let supported: Vec<&str> = SUPPORTED_PLACEHOLDERS.iter().map(|(n, _)| *n).collect();
    Err(format!(
        "Unsupported placeholder(s): {}. Supported placeholders are: {}",
        unsupported.join(", "),
        supported.join(", ")
    ))
}

/// `TrayTextFormatDialog`: the edited format string on OK (blank means the
/// default), `None` on Cancel.
pub(crate) fn show_tray_text_format_dialog(
    parent: &dyn WxWidget,
    context: TrayPreviewContext,
    initial_format: &str,
) -> Option<String> {
    let dialog = Dialog::builder(parent, "Tray Text Format")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(520, 500)
        .build();
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let format_label = StaticText::builder(&dialog)
        .with_label("Tray text format:")
        .build();
    main_sizer.add(
        &format_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );
    let format_ctrl = TextCtrl::builder(&dialog)
        .with_value(initial_format)
        .build();
    main_sizer.add(&format_ctrl, 0, SizerFlag::Expand | SizerFlag::All, 10);

    let placeholders_label = StaticText::builder(&dialog)
        .with_label("Supported placeholders:")
        .build();
    main_sizer.add(
        &placeholders_label,
        0,
        SizerFlag::Left | SizerFlag::Right,
        10,
    );
    let placeholders_ctrl = TextCtrl::builder(&dialog)
        .with_value(supported_placeholders_help().trim())
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly)
        .build();
    main_sizer.add(
        &placeholders_ctrl,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );

    let preview_label = StaticText::builder(&dialog).with_label("Preview:").build();
    main_sizer.add(&preview_label, 0, SizerFlag::Left | SizerFlag::Right, 10);
    let preview_ctrl = TextCtrl::builder(&dialog)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::NoVScroll)
        .build();
    main_sizer.add(
        &preview_ctrl,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );

    let buttons = StdDialogButtonSizerBuilder::new().build();
    let ok = Button::builder(&dialog).with_id(ID_OK).build();
    let cancel = Button::builder(&dialog).with_id(ID_CANCEL).build();
    buttons.add_button(&ok);
    buttons.add_button(&cancel);
    buttons.realize();
    main_sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 10);
    dialog.set_sizer(main_sizer, true);

    let update_preview = move || {
        preview_ctrl.set_value(&settings_actions::tray_text_preview(
            &format_ctrl.get_value(),
            &context,
        ));
    };
    update_preview();
    format_ctrl.on_text_changed(move |_| update_preview());
    ok.on_click(move |e| {
        // Warn about typos like unknown placeholders or unbalanced braces.
        if let Err(problem) = validate_format_string(format_ctrl.get_value().trim()) {
            let choice = message_box(
                &dialog,
                &format!("{problem}\n\nSave this format anyway?"),
                "Tray Text Format Problem",
                MessageDialogStyle::YesNo | MessageDialogStyle::IconWarning,
            );
            if choice != ID_YES {
                e.event.skip(false);
                format_ctrl.set_focus();
            }
        }
    });

    let accepted = dialog.show_modal() == ID_OK;
    let value = format_ctrl.get_value().trim().to_string();
    dialog.destroy();
    accepted.then(|| {
        if value.is_empty() {
            DEFAULT_TOOLTIP_FORMAT.to_string()
        } else {
            value
        }
    })
}
