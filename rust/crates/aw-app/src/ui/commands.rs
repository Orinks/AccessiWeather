//! Menu command handlers, ported from `ui/main_window_commands.py`. Commands
//! whose dialogs other workstreams port log and return for now; each has
//! its own function so those ports have one place to fill in.

use wxdragon::prelude::*;

use super::display;
use super::main_window::{self as mw, message_box, window, window_state};
use crate::app::with_state;

pub(crate) const MSG_SELECT_LOCATION_FIRST: &str = "Please select a location first.";

fn not_ported(feature: &str) {
    tracing::info!("{feature} is not ported yet");
}

/// View > Explain Weather (Ctrl+E) and the Explain Conditions button.
pub(crate) fn on_explain_weather() {
    not_ported("Explain Weather");
}

/// View > Precipitation Timeline.
pub(crate) fn on_precipitation_timeline() {
    not_ported("Precipitation Timeline");
}

/// View > Event Center.
pub(crate) fn toggle_event_center() {
    mw::toggle_event_center();
}

/// View > Forecaster Notes and the Forecaster Notes button
/// (`_on_discussion` -> `_on_forecast_products`).
pub(crate) fn on_discussion() {
    let Some(w) = window() else { return };
    let current = with_state().and_then(|s| s.borrow().config.current_location.clone());
    if current.is_none() {
        message_box(
            &w.frame,
            MSG_SELECT_LOCATION_FIRST,
            super::locations::CAPTION_NO_LOCATION,
            MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
        );
        return;
    }
    not_ported("Forecaster Notes");
}

/// View > Aviation Weather.
pub(crate) fn on_aviation() {
    not_ported("Aviation Weather");
}

/// View > Air Quality.
pub(crate) fn on_air_quality() {
    not_ported("Air Quality");
}

/// View > UV Index.
pub(crate) fn on_uv_index() {
    not_ported("UV Index");
}

/// View > NOAA Weather Radio (Ctrl+N).
pub(crate) fn on_noaa_radio() {
    not_ported("NOAA Weather Radio");
}

/// View > Weather Assistant (Ctrl+T).
pub(crate) fn on_weather_chat() {
    not_ported("Weather Assistant");
}

/// Tools > Soundpack Manager.
pub(crate) fn on_soundpack_manager() {
    if let Some(w) = window() {
        super::soundpack_manager::open_soundpack_manager(&w.frame);
    }
}

/// Help > Check for Updates.
pub(crate) fn on_check_updates() {
    not_ported("Check for Updates");
}

/// Help > User Manual.
pub(crate) fn on_open_user_manual() {
    not_ported("User Manual");
}

/// Help > Report Issue.
pub(crate) fn on_report_issue() {
    not_ported("Report Issue");
}

/// Help > Debug > Test: Discussion Updated.
pub(crate) fn on_test_discussion_notification() {
    not_ported("Debug discussion notification");
}

/// Help > Debug > Test: Alert Notification.
pub(crate) fn on_test_alert_notification() {
    not_ported("Debug alert notification dialog");
}

/// Help > Debug > Test: Simulate Alert Change.
pub(crate) fn on_debug_simulate_alert() {
    not_ported("Debug alert simulation");
}

/// Help > Debug > Run Notification Diagnostics.
pub(crate) fn on_test_notifications() {
    not_ported("Notification diagnostics");
}

/// Help > About.
pub(crate) fn on_about() {
    let (Some(w), Some(state)) = (window(), with_state()) else {
        return;
    };
    let text = {
        let st = state.borrow();
        display::about_text(
            aw_core::VERSION,
            st.paths.portable,
            &st.paths.config_dir.display().to_string(),
        )
    };
    message_box(
        &w.frame,
        &text,
        "About AccessiWeather",
        MessageDialogStyle::OK | MessageDialogStyle::IconInformation,
    );
}

/// File > Exit (Ctrl+Q): `app.request_exit`. Closing with `force` skips the
/// minimize-to-tray veto, as Python's direct exit does.
pub(crate) fn request_exit() {
    tracing::info!("Application exit requested");
    if let Some(frame) = mw::main_frame() {
        frame.close(true);
    }
}

/// View Alert Details button, double-click or Enter/Space on the list.
pub(crate) fn on_view_alert() {
    let Some(index) = window().and_then(|w| w.alerts_list.get_selection()) else {
        return;
    };
    show_alert_details(index as usize);
}

/// `_show_alert_details`.
fn show_alert_details(alert_index: usize) {
    let alert = if window_state(|s| s.all_locations_active) {
        window_state(|s| {
            s.all_locations_alerts_data
                .get(alert_index)
                .map(|(_, a)| a.clone())
        })
    } else {
        with_state().and_then(|state| {
            let st = state.borrow();
            let alerts = st.current_weather_data.as_ref()?.alerts.as_ref()?;
            alerts
                .active(chrono::Utc::now())
                .get(alert_index)
                .map(|a| (*a).clone())
        })
    };
    if let Some(alert) = alert {
        show_alert_dialog(&alert);
    }
}

/// `show_alert_dialog`. Until `alert_dialog.py` is ported this shows the
/// alert text in a plain read-only dialog so alerts stay readable.
fn show_alert_dialog(alert: &aw_core::model::WeatherAlert) {
    let Some(w) = window() else { return };
    let event = alert.event.as_deref().unwrap_or("Unknown");
    let dlg = Dialog::builder(&w.frame, &format!("Alert: {event}"))
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(640, 480)
        .build();
    let body = [
        alert.headline.as_deref().unwrap_or(&alert.title),
        &alert.description,
        alert.instruction.as_deref().unwrap_or(""),
    ]
    .into_iter()
    .filter(|s| !s.is_empty())
    .collect::<Vec<_>>()
    .join("\n\n");
    let root = BoxSizer::builder(Orientation::Vertical).build();
    let text = TextCtrl::builder(&dlg)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::WordWrap)
        .with_value(&body)
        .build();
    root.add(&text, 1, SizerFlag::Expand | SizerFlag::All, 8);
    let close = Button::builder(&dlg)
        .with_id(ID_CANCEL)
        .with_label("&Close")
        .build();
    root.add(&close, 0, SizerFlag::AlignRight | SizerFlag::All, 8);
    dlg.set_sizer(root, true);
    dlg.set_escape_id(ID_CANCEL);
    text.set_focus();
    text.set_insertion_point(0);
    dlg.show_modal();
    dlg.destroy();
}
