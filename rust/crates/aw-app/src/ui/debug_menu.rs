//! Help > Debug (only with `--debug`): the handlers from
//! `ui/main_window_commands.py` and the "Test Alert Notification" dialog
//! (`ui/dialogs/debug_alert_dialog.py`). Presets, toasts and diagnostics
//! come from `aw_notify::debug`.

use std::cell::OnceCell;

use aw_core::model::WeatherData;
use aw_core::settings::AppSettings;
use aw_notify::debug::{self, AlertPreset, ALERT_PRESETS};
use aw_notify::toast::APP_NAME;
use aw_notify::{ActivationRequest, Notifier, Toast};
use chrono::{Local, Utc};
use wxdragon::prelude::*;

use super::main_window::{main_frame, message_box};
use crate::app::with_state;

/// A `wx.MessageBox` call: message, caption and style.
type Message = (&'static str, &'static str, MessageDialogStyle);

const DISCUSSION_FAILED: Message = (
    "Discussion notification could not be sent.\n\
     Check that desktop notifications are enabled on your system.",
    "Debug: Discussion Notification",
    MessageDialogStyle::OK.union(MessageDialogStyle::IconWarning),
);
const NO_CURRENT_LOCATION: Message = (
    "No current location.",
    "Debug",
    MessageDialogStyle::OK.union(MessageDialogStyle::IconWarning),
);
const DIAGNOSTICS_TITLE: &str = "Notification Test Results";
/// `run_notification_test` shows its direct toast under this app name.
const DIAGNOSTICS_APP_NAME: &str = "AccessiWeather Debug Test";

const DIALOG_TITLE: &str = "Test Alert Notification";
const DIALOG_SIZE: (i32, i32) = (520, 440);
const LIST_LABEL: &str = "Select alert type to send:";
const LIST_NAME: &str = "Select alert type to send";
const CANDIDATES_LABEL: &str = "Sound event candidates (tried in order):";
const CANDIDATES_NAME: &str = "Sound event candidates";
const CANDIDATES_HEIGHT: i32 = 48;
const SEND_LABEL: &str = "&Send Test Notification";
const SEND_NAME: &str = "Send test notification";
const CLOSE_LABEL: &str = "&Close";
const CLOSE_NAME: &str = "Close test alert notification dialog";

thread_local! {
    /// Stands in for `app.notifier` until the notification integration
    /// provides the app's own.
    static NOTIFIER: OnceCell<Notifier> = const { OnceCell::new() };
}

fn show((message, caption, style): Message) {
    if let Some(frame) = main_frame() {
        message_box(&frame, message, caption, style);
    }
}

fn settings() -> AppSettings {
    with_state()
        .map(|s| s.borrow().config.settings.clone())
        .unwrap_or_default()
}

/// `notifier.send_notification(...)`: show the toast and play its sound
/// cue from the current sound pack (whether or not the toast showed).
fn send_notification(toast: &Toast, settings: &AppSettings) -> bool {
    let sent = NOTIFIER.with(|n| n.get_or_init(|| Notifier::new(APP_NAME)).send(toast));
    if let Some(keys) = toast.sound_keys(settings) {
        aw_audio::player().play_candidates(
            &keys,
            &settings.sound_pack,
            None,
            &settings.muted_sound_events,
        );
    }
    sent
}

fn discussion_test_toast() -> Toast {
    Toast {
        title: "NWS Discussion Updated".into(),
        message: "The Area Forecast Discussion for your location has been updated. \
                  This is a debug test notification."
            .into(),
        timeout: 10,
        sound_event: None,
        sound_candidates: Some(vec!["discussion_update".into(), "notify".into()]),
        play_sound: true,
        activation: Some(ActivationRequest::discussion()),
    }
}

/// Help > Debug > Test: Discussion Updated.
pub(crate) fn on_test_discussion_notification() {
    if !send_notification(&discussion_test_toast(), &settings()) {
        show(DISCUSSION_FAILED);
    }
}

/// Help > Debug > Test: Alert Notification.
pub(crate) fn on_test_alert_notification() {
    if let Some(frame) = main_frame() {
        show_debug_alert_dialog(&frame);
    }
}

/// Help > Debug > Test: Simulate Alert Change (poll cycle): a fake new
/// tornado warning through the lightweight event-check path. (Python's
/// "Weather client not ready." case cannot happen here: the client always
/// exists once the window does.)
pub(crate) fn on_debug_simulate_alert() {
    let location = with_state().and_then(|s| s.borrow().config.current_location.clone());
    let Some(location) = location else {
        show(NO_CURRENT_LOCATION);
        return;
    };
    on_notification_event_data_received(debug::simulated_poll_data(location));
}

/// `_on_notification_event_data_received`: hands a lightweight poll result
/// (alerts plus their lifecycle diff) to the alert notification pipeline.
/// The notifications integration replaces this body with the real path.
pub(crate) fn on_notification_event_data_received(data: WeatherData) {
    tracing::info!(
        "Alert event check for {} is not wired to notifications yet",
        data.location.name
    );
}

/// Help > Debug > Run Notification Diagnostics.
pub(crate) fn on_test_notifications() {
    let (settings, location_name) = match with_state() {
        Some(state) => {
            let st = state.borrow();
            (
                st.config.settings.clone(),
                st.config.current_location.as_ref().map(|l| l.name.clone()),
            )
        }
        None => (AppSettings::default(), None),
    };
    let results = debug::run_notification_diagnostics(
        &settings,
        location_name.as_deref(),
        |toast| Notifier::new(DIAGNOSTICS_APP_NAME).send(toast),
        Local::now().fixed_offset(),
    );
    if let Some(frame) = main_frame() {
        message_box(
            &frame,
            &results.menu_report(),
            DIAGNOSTICS_TITLE,
            diagnostics_style(results.all_passed()),
        );
    }
}

fn diagnostics_style(all_passed: bool) -> MessageDialogStyle {
    MessageDialogStyle::OK
        | if all_passed {
            MessageDialogStyle::IconInformation
        } else {
            MessageDialogStyle::IconWarning
        }
}

fn selected_preset(list: &ListBox) -> &'static AlertPreset {
    let index = list.get_selection().unwrap_or(0) as usize;
    ALERT_PRESETS.get(index).unwrap_or(&ALERT_PRESETS[0])
}

/// `DebugAlertDialog`.
fn show_debug_alert_dialog(parent: &Frame) {
    let dialog = Dialog::builder(parent, DIALOG_TITLE)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let panel = Panel::builder(&dialog).build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();

    let list_label = StaticText::builder(&panel).with_label(LIST_LABEL).build();
    sizer.add(&list_label, 0, SizerFlag::All, 8);
    let list = ListBox::builder(&panel)
        .with_choices(ALERT_PRESETS.iter().map(|p| p.label.to_string()).collect())
        .build();
    list.set_selection(0, true);
    sizer.add(
        &list,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        8,
    );

    let candidates_label = StaticText::builder(&panel)
        .with_label(CANDIDATES_LABEL)
        .build();
    sizer.add(&candidates_label, 0, SizerFlag::Left | SizerFlag::Right, 8);
    let candidates = TextCtrl::builder(&panel)
        .with_style(TextCtrlStyle::ReadOnly | TextCtrlStyle::MultiLine | TextCtrlStyle::NoVScroll)
        .with_size(Size::new(-1, CANDIDATES_HEIGHT))
        .build();
    sizer.add(&candidates, 0, SizerFlag::Expand | SizerFlag::All, 8);

    let status = StaticText::builder(&panel).with_label("").build();
    sizer.add(
        &status,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        8,
    );

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    let send = Button::builder(&panel).with_label(SEND_LABEL).build();
    let close = Button::builder(&panel)
        .with_id(ID_CLOSE)
        .with_label(CLOSE_LABEL)
        .build();
    buttons.add(&send, 0, SizerFlag::Right, 8);
    buttons.add(&close, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(&buttons, 0, SizerFlag::AlignRight | SizerFlag::All, 8);
    panel.set_sizer(sizer, true);
    panel.layout();
    send.set_default();

    list.set_name(LIST_NAME);
    candidates.set_name(CANDIDATES_NAME);
    send.set_name(SEND_NAME);
    close.set_name(CLOSE_NAME);

    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            dialog.end_modal(ID_CLOSE);
        } else {
            e.skip(true);
        }
    });
    close.on_click(move |e| {
        e.event.skip(false);
        dialog.end_modal(ID_CLOSE);
    });
    let update_candidates =
        move || candidates.set_value(&selected_preset(&list).sound_candidates_text(Utc::now()));
    list.on_selection_changed(move |_| {
        update_candidates();
        status.set_label("");
    });
    send.on_click(move |_| {
        let settings = settings();
        let preset = selected_preset(&list);
        let toast = preset.toast(Utc::now());
        tracing::debug!(
            "[debug] Sending test alert: title={:?}, sound_candidates={:?}",
            toast.title,
            toast.sound_candidates
        );
        let sent = send_notification(&toast, &settings);
        status.set_label(&preset.status_text(sent));
        if sent {
            tracing::info!("[debug] Test alert notification sent: {:?}", toast.title);
        } else {
            tracing::warn!(
                "[debug] Test alert notification returned False: {:?}",
                toast.title
            );
        }
        dialog.layout();
    });

    update_candidates();
    dialog.set_size(Size::new(DIALOG_SIZE.0, DIALOG_SIZE.1));
    dialog.center();
    dialog.show_modal();
    dialog.destroy();
}

#[cfg(test)]
mod tests {
    //! Golden parity with the Python dialog and handlers
    //! (`rust/tools/golden/miscui.py`).

    use serde_json::{json, Value};

    use super::*;
    use crate::ui::golden_miscui::golden;

    fn message_json((message, caption, style): Message) -> Value {
        json!(["message_box", message, caption, style.bits()])
    }

    #[test]
    fn alert_dialog_matches_python() {
        let g = &golden()["debug_alert"];
        let now = Utc::now();
        assert_eq!(g["title"], DIALOG_TITLE);
        assert_eq!(g["resizable"], true);
        assert_eq!(g["size"], json!([DIALOG_SIZE.0, DIALOG_SIZE.1]));
        let labels: Vec<&str> = ALERT_PRESETS.iter().map(|p| p.label).collect();
        assert_eq!(
            g["controls"],
            json!([
                {"kind": "label", "label": LIST_LABEL},
                {"kind": "listbox", "name": LIST_NAME, "items": labels, "selection": 0, "single": true},
                {"kind": "label", "label": CANDIDATES_LABEL},
                {"kind": "text", "name": CANDIDATES_NAME,
                    "value": ALERT_PRESETS[0].sound_candidates_text(now), "hint": "",
                    "multiline": true, "readonly": true, "rich2": false,
                    "dont_wrap": false, "no_vscroll": true},
                {"kind": "label", "label": ""},
                {"kind": "button", "id": "auto", "label": SEND_LABEL, "name": SEND_NAME},
                {"kind": "button", "id": ID_CLOSE, "label": CLOSE_LABEL, "name": CLOSE_NAME},
            ])
        );
        assert_eq!(g["default"], SEND_LABEL);
        assert_eq!(g["candidates_height"], CANDIDATES_HEIGHT);
        for (preset, case) in ALERT_PRESETS
            .iter()
            .zip(g["candidates"].as_array().unwrap())
        {
            assert_eq!(case["label"], preset.label);
            assert_eq!(case["text"], preset.sound_candidates_text(now));
        }
        for send in g["sends"].as_array().unwrap() {
            let preset = &ALERT_PRESETS[send["preset"].as_u64().unwrap() as usize];
            let toast = preset.toast(now);
            assert_eq!(
                send["kwargs"],
                json!({"title": toast.title, "message": toast.message, "timeout": toast.timeout,
                    "sound_candidates": toast.sound_candidates, "play_sound": toast.play_sound})
            );
            let sent = send["status"].as_str().unwrap().starts_with('✓');
            assert_eq!(send["status"], preset.status_text(sent));
        }
    }

    #[test]
    fn debug_commands_match_python() {
        let g = &golden()["debug_commands"];
        let toast = discussion_test_toast();
        assert_eq!(
            g["discussion"]["kwargs"],
            json!({"title": toast.title, "message": toast.message, "timeout": toast.timeout,
                "sound_candidates": toast.sound_candidates, "play_sound": toast.play_sound,
                "activation_arguments": toast.activation_arguments()})
        );
        assert_eq!(
            g["discussion"]["events"],
            json!([message_json(DISCUSSION_FAILED)])
        );
        assert_eq!(g["simulate"][0], message_json(NO_CURRENT_LOCATION));
        for case in g["diagnostics"].as_array().unwrap() {
            let passed: Vec<bool> = serde_json::from_value(case["passed"].clone()).unwrap();
            let keys = [
                "safe_desktop_notifier",
                "alert_notification_system",
                "discussion_update_path",
            ];
            let results = debug::NotificationDiagnostics {
                results: keys
                    .iter()
                    .zip(&passed)
                    .map(|(key, &passed)| debug::DiagnosticResult {
                        key,
                        passed,
                        message: format!("{key} detail"),
                    })
                    .collect(),
            };
            assert_eq!(
                case["events"],
                json!([[
                    "message_box",
                    results.menu_report(),
                    DIAGNOSTICS_TITLE,
                    diagnostics_style(results.all_passed()).bits()
                ]])
            );
        }
    }
}
