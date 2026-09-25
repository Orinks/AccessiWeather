//! The alert details dialog (`ui/dialogs/alert_dialog.py`) and the summary
//! dialog for several new alerts at once (`ui/dialogs/alerts_summary_dialog.py`).

use std::rc::Rc;

use aw_core::model::{Timestamp, WeatherAlert};
use aw_core::settings::AppSettings;
use wxdragon::prelude::*;

use super::main_window::window;
use crate::app::with_state;

const COPY_LABEL: &str = "Cop&y to clipboard";
const COPY_NAME: &str = "Copy alert text to clipboard";
const CLOSE_LABEL: &str = "&Close";
const SUMMARY_TITLE: &str = "New Weather Alerts";
const SUMMARY_INTRO: &str =
    "Multiple new alerts arrived in this update. Review the summaries below.";
const SUMMARY_NAME: &str = "New alert summaries";
/// The summary dialog's Close button has no mnemonic.
const SUMMARY_CLOSE_LABEL: &str = "Close";
/// wxID_COPY, which wxDragon does not export.
const ID_COPY: i32 = wxdragon::ffi::WXD_ID_COPY as i32;

/// Open the details dialog for `alert` over the main window, with the current
/// settings: `show_alert_dialog(main_window, alert, get_settings())`.
pub(crate) fn show_alert_details(alert: &WeatherAlert) {
    let (Some(w), Some(state)) = (window(), with_state()) else {
        return;
    };
    let settings = state.borrow().config.settings.clone();
    show_alert_dialog(&w.frame, alert, &settings);
}

/// Open the "New Weather Alerts" summary over the main window:
/// `show_alerts_summary_dialog(main_window, alerts)`.
// Called by the immediate alert popups, which the notification port wires up.
#[allow(dead_code)]
pub(crate) fn show_alerts_summary(alerts: &[WeatherAlert]) {
    if let Some(w) = window() {
        show_alerts_summary_dialog(&w.frame, alerts);
    }
}

// ---------------------------------------------------------------------------
// Text builders
// ---------------------------------------------------------------------------

fn non_empty(s: Option<&str>) -> Option<&str> {
    s.filter(|s| !s.is_empty())
}

/// The dialog title. Python formats the attribute as-is, so an alert without
/// an event is titled "Alert: None".
fn dialog_title(alert: &WeatherAlert) -> String {
    format!("Alert: {}", alert.event.as_deref().unwrap_or("None"))
}

/// `_build_subject_text`: the headline, else the event, else "Weather Alert".
fn subject_text(alert: &WeatherAlert) -> &str {
    non_empty(alert.headline.as_deref())
        .or(non_empty(alert.event.as_deref()))
        .unwrap_or("Weather Alert")
}

/// `_build_info_text`: "Severity: X, Urgency: Y, Certainty: Z", skipping empty values.
fn info_text(alert: &WeatherAlert) -> String {
    [
        ("Severity", &alert.severity),
        ("Urgency", &alert.urgency),
        ("Certainty", &alert.certainty),
    ]
    .iter()
    .filter(|(_, v)| !v.is_empty())
    .map(|(k, v)| format!("{k}: {v}"))
    .collect::<Vec<_>>()
    .join(", ")
}

/// `format_datetime` (`display/presentation/time_formatters.py`), in the
/// timestamp's own offset.
fn format_datetime(dt: &Timestamp, date_style: &str, time_12hour: bool) -> String {
    let date_fmt = match date_style {
        "us_short" => "%m/%d/%Y",
        "us_long" => "%B %d, %Y",
        "eu" => "%d/%m/%Y",
        _ => "%Y-%m-%d",
    };
    let time = if time_12hour {
        dt.format("%I:%M %p")
            .to_string()
            .trim_start_matches('0')
            .to_string()
    } else {
        dt.format("%H:%M").to_string()
    };
    format!("{} {time}", dt.format(date_fmt))
}

/// `_build_combined_text`: subject, description, instruction and the
/// Issued/Expires lines as blank-line separated blocks. It is also the
/// clipboard text in both display styles (`_copy_payload`).
fn combined_text(alert: &WeatherAlert, settings: &AppSettings) -> String {
    let fmt = |dt| format_datetime(dt, &settings.date_format, settings.time_format_12hour);
    let mut blocks = vec![subject_text(alert).to_string()];
    blocks.extend(non_empty(Some(alert.description.as_str())).map(str::to_string));
    blocks.extend(non_empty(alert.instruction.as_deref()).map(str::to_string));
    let times: Vec<String> = [("Issued", &alert.sent), ("Expires", &alert.expires)]
        .into_iter()
        .filter_map(|(k, dt)| dt.as_ref().map(|dt| format!("{k}: {}", fmt(dt))))
        .collect();
    if !times.is_empty() {
        blocks.push(times.join("\n"));
    }
    blocks.join("\n\n")
}

/// `AlertsSummaryDialog._build_summary_text`.
fn summary_text(alerts: &[WeatherAlert]) -> String {
    alerts
        .iter()
        .enumerate()
        .map(|(i, alert)| {
            let mut lines = vec![
                format!("{}. {}", i + 1, subject_text(alert)),
                format!("Severity: {}", alert.severity),
            ];
            let optional = [
                ("Urgency", Some(alert.urgency.as_str())),
                ("Certainty", Some(alert.certainty.as_str())),
                ("Details", Some(alert.description.as_str())),
            ];
            for (k, v) in optional {
                if let Some(v) = non_empty(v) {
                    lines.push(format!("{k}: {v}"));
                }
            }
            lines.join("\n")
        })
        .collect::<Vec<_>>()
        .join("\n\n")
}

/// One labelled read-only text field of the alert dialog.
#[derive(Debug, PartialEq)]
struct Field {
    label: &'static str,
    /// `SetName` from `_setup_accessibility`.
    name: &'static str,
    value: String,
    /// Fixed height; `None` means default height, taking the spare room.
    height: Option<i32>,
}

/// `_create_ui`: the fields for the configured `alert_display_style`, in
/// creation order. Separate: Subject, then Alert Info, Details and
/// Instructions when they have text. Combined: one field with everything.
fn alert_fields(alert: &WeatherAlert, settings: &AppSettings) -> Vec<Field> {
    if settings.alert_display_style == "combined" {
        return vec![Field {
            label: "Alert:",
            name: "Full alert text",
            value: combined_text(alert, settings),
            height: None,
        }];
    }
    let mut fields = vec![Field {
        label: "Subject:",
        name: "Subject with alert headline",
        value: subject_text(alert).to_string(),
        height: Some(60),
    }];
    let info = info_text(alert);
    if !info.is_empty() {
        fields.push(Field {
            label: "Alert Info:",
            name: "Alert information with severity, urgency, and certainty",
            value: info,
            height: Some(60),
        });
    }
    if let Some(description) = non_empty(Some(alert.description.as_str())) {
        fields.push(Field {
            label: "Details:",
            name: "Alert details",
            value: description.to_string(),
            height: None,
        });
    }
    if let Some(instruction) = non_empty(alert.instruction.as_deref()) {
        fields.push(Field {
            label: "Instructions:",
            name: "Instructions",
            value: instruction.to_string(),
            height: Some(80),
        });
    }
    fields
}

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

fn new_dialog(parent: &dyn WxWidget, title: &str, width: i32, height: i32) -> (Dialog, Panel) {
    let dialog = Dialog::builder(parent, title)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(width, height)
        .build();
    let panel = Panel::builder(&dialog).build();
    // Escape closes, like the title bar's close box.
    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            dialog.close(false);
        } else {
            e.skip(true);
        }
    });
    (dialog, panel)
}

fn read_only_text(panel: &Panel, value: &str, height: i32) -> TextCtrl {
    TextCtrl::builder(panel)
        .with_value(value)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::Rich2)
        .with_size(Size::new(-1, height))
        .build()
}

fn close_button(dialog: Dialog, panel: &Panel, label: &str) -> Button {
    let button = Button::builder(panel)
        .with_id(ID_CLOSE)
        .with_label(label)
        .build();
    button.on_click(move |_| dialog.end_modal(ID_CLOSE));
    button
}

fn finish_layout(dialog: &Dialog, panel: &Panel, sizer: BoxSizer) {
    panel.set_sizer(sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);
}

/// `show_alert_dialog` / `AlertDialog`.
fn show_alert_dialog(parent: &dyn WxWidget, alert: &WeatherAlert, settings: &AppSettings) {
    let (dialog, panel) = new_dialog(parent, &dialog_title(alert), 700, 500);
    let sizer = BoxSizer::builder(Orientation::Vertical).build();

    let mut first = None;
    for (i, field) in alert_fields(alert, settings).into_iter().enumerate() {
        let label = StaticText::builder(&panel).with_label(field.label).build();
        if let Some(mut font) = label.get_font() {
            font.make_bold();
            label.set_font(&font);
        }
        let top = if i == 0 {
            SizerFlag::Top
        } else {
            SizerFlag::empty()
        };
        sizer.add(&label, 0, SizerFlag::Left | SizerFlag::Right | top, 15);
        let ctrl = read_only_text(&panel, &field.value, field.height.unwrap_or(-1));
        ctrl.set_name(field.name);
        let proportion = i32::from(field.height.is_none());
        sizer.add(
            &ctrl,
            proportion,
            SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
            15,
        );
        first.get_or_insert(ctrl);
    }

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    buttons.add_stretch_spacer(1);
    let copy = Button::builder(&panel)
        .with_id(ID_COPY)
        .with_label(COPY_LABEL)
        .build();
    copy.set_name(COPY_NAME);
    buttons.add(&copy, 0, SizerFlag::Right, 10);
    let close = close_button(dialog, &panel, CLOSE_LABEL);
    buttons.add(&close, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 15);
    finish_layout(&dialog, &panel, sizer);
    if let Some(first) = first {
        first.set_focus();
    }

    // "Copied!" / "Copy failed" shows for two seconds, then the label returns.
    let revert = Rc::new(Timer::new(&dialog));
    revert.on_tick(move |_| {
        copy.set_label(COPY_LABEL);
        panel.layout();
    });
    let payload = combined_text(alert, settings);
    let timer = revert.clone();
    copy.on_click(move |_| {
        let copied = Clipboard::get().set_text(&payload);
        if !copied {
            tracing::warn!("Alert copy: could not open clipboard");
        }
        copy.set_label(if copied { "Copied!" } else { "Copy failed" });
        panel.layout();
        timer.stop();
        timer.start(2000, true);
    });

    dialog.show_modal();
    revert.stop();
    dialog.destroy();
}

/// `show_alerts_summary_dialog` / `AlertsSummaryDialog`.
fn show_alerts_summary_dialog(parent: &dyn WxWidget, alerts: &[WeatherAlert]) {
    let (dialog, panel) = new_dialog(parent, SUMMARY_TITLE, 720, 480);
    let sizer = BoxSizer::builder(Orientation::Vertical).build();
    let intro = StaticText::builder(&panel)
        .with_label(SUMMARY_INTRO)
        .build();
    sizer.add(&intro, 0, SizerFlag::All, 15);
    let summary = read_only_text(&panel, &summary_text(alerts), -1);
    summary.set_name(SUMMARY_NAME);
    sizer.add(
        &summary,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        15,
    );
    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    buttons.add_stretch_spacer(1);
    let close = close_button(dialog, &panel, SUMMARY_CLOSE_LABEL);
    buttons.add(&close, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 15);
    finish_layout(&dialog, &panel, sizer);
    summary.set_focus();
    dialog.show_modal();
    dialog.destroy();
}

#[cfg(test)]
mod tests {
    //! Golden parity with the Python dialogs, generated by
    //! `rust/tools/golden/alertui.py`.

    use serde_json::{json, Value};

    use super::*;

    fn golden() -> Value {
        serde_json::from_str(include_str!(
            "../../../../testdata/golden/alertui/cases.json"
        ))
        .unwrap()
    }

    fn settings(style: &str, date_format: &str, time_12h: bool) -> AppSettings {
        AppSettings {
            alert_display_style: style.into(),
            date_format: date_format.into(),
            time_format_12hour: time_12h,
            ..AppSettings::default()
        }
    }

    /// The controls `show_alert_dialog` creates, as the generator records them.
    fn controls(fields: &[Field]) -> Vec<Value> {
        let mut out = Vec::new();
        for f in fields {
            out.push(json!({"kind": "label", "label": f.label, "bold": true}));
            out.push(json!({"kind": "text", "name": f.name, "value": f.value}));
        }
        // Python names only the Copy button; "button" is wx's default name.
        out.push(json!({"kind": "button", "id": ID_COPY, "label": COPY_LABEL, "name": COPY_NAME}));
        out.push(json!({"kind": "button", "id": ID_CLOSE, "label": CLOSE_LABEL, "name": "button"}));
        out
    }

    #[test]
    fn alert_dialog_matches_python() {
        let g = golden();
        for case in g["alerts"].as_array().unwrap() {
            let alert: WeatherAlert = serde_json::from_value(case["alert"].clone()).unwrap();
            assert_eq!(dialog_title(&alert), case["title"]);
            assert_eq!(subject_text(&alert), case["subject"]);
            assert_eq!(info_text(&alert), case["info"]);
            for style in ["separate", "combined"] {
                let fields = alert_fields(&alert, &settings(style, "iso", true));
                assert_eq!(
                    Value::from(controls(&fields)),
                    case[format!("{style}_controls")],
                    "{style}: {}",
                    alert.title
                );
                // Initial focus is the first text field.
                assert_eq!(fields[0].name, case[format!("{style}_focus")]);
            }
            for (i, s) in g["settings"].as_array().unwrap().iter().enumerate() {
                let date_format = s["date_format"].as_str().unwrap();
                let time_12h = s["time_format_12hour"].as_bool().unwrap();
                let text = combined_text(&alert, &settings("separate", date_format, time_12h));
                assert_eq!(text, case["combined"][i], "{date_format} {time_12h}");
                assert_eq!(text, case["copy"][i]);
            }
        }
    }

    #[test]
    fn summary_dialog_matches_python() {
        let g = golden();
        let alerts: Vec<WeatherAlert> = g["alerts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| serde_json::from_value(c["alert"].clone()).unwrap())
            .collect();
        for case in g["summaries"].as_array().unwrap() {
            let batch: Vec<WeatherAlert> = case["alerts"]
                .as_array()
                .unwrap()
                .iter()
                .map(|i| alerts[i.as_u64().unwrap() as usize].clone())
                .collect();
            let text = summary_text(&batch);
            assert_eq!(text, case["text"]);
            assert_eq!(case["title"], SUMMARY_TITLE);
            assert_eq!(
                case["controls"],
                json!([
                    {"kind": "label", "label": SUMMARY_INTRO, "bold": false},
                    {"kind": "text", "name": SUMMARY_NAME, "value": text},
                    {"kind": "button", "id": ID_CLOSE, "label": SUMMARY_CLOSE_LABEL, "name": "button"},
                ])
            );
        }
    }
}
