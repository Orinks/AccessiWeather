//! Menu command handlers, ported from `ui/main_window_commands.py`. Commands
//! whose dialogs other workstreams port log and return for now; each has
//! its own function so those ports have one place to fill in.

use wxdragon::prelude::*;

use super::display;
use super::main_window::{self as mw, message_box, window, window_state};
use crate::app::with_state;

pub(crate) const MSG_SELECT_LOCATION_FIRST: &str = "Please select a location first.";

/// View > Explain Weather (Ctrl+E) and the Explain Conditions button.
pub(crate) fn on_explain_weather() {
    super::explanation_dialog::show_explanation_dialog();
}

/// View > Precipitation Timeline.
pub(crate) fn on_precipitation_timeline() {
    super::data_dialogs::show_precipitation_timeline();
}

/// View > Event Center.
pub(crate) fn toggle_event_center() {
    mw::toggle_event_center();
}

/// View > Forecaster Notes and the Forecaster Notes button
/// (`_on_discussion` -> `_on_forecast_products`).
pub(crate) fn on_discussion() {
    let Some(w) = window() else { return };
    // All Locations keeps the last current location, which is what opens.
    let current = with_state().and_then(|s| s.borrow().config.current_location.clone());
    let Some(current) = current else {
        message_box(
            &w.frame,
            MSG_SELECT_LOCATION_FIRST,
            super::locations::CAPTION_NO_LOCATION,
            MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
        );
        return;
    };
    super::forecast_products::open_forecaster_notes(&current);
}

/// View > Aviation Weather.
pub(crate) fn on_aviation() {
    super::aviation_dialog::show_aviation_dialog();
}

/// View > Air Quality.
pub(crate) fn on_air_quality() {
    super::data_dialogs::show_air_quality();
}

/// View > UV Index.
pub(crate) fn on_uv_index() {
    super::data_dialogs::show_uv_index();
}

/// View > NOAA Weather Radio (Ctrl+N).
pub(crate) fn on_noaa_radio() {
    super::noaa_radio_dialog::show_noaa_radio_dialog();
}

/// View > Weather Assistant (Ctrl+T).
pub(crate) fn on_weather_chat() {
    super::weather_assistant_dialog::show_weather_assistant_dialog();
}

/// Tools > Soundpack Manager.
pub(crate) fn on_soundpack_manager() {
    if let Some(w) = window() {
        super::soundpack_manager::open_soundpack_manager(&w.frame);
    }
}

/// Help > Check for Updates.
pub(crate) fn on_check_updates() {
    super::updates::check_for_updates(true);
}

/// Help > User Manual: the bundled manual, else the online one.
pub(crate) fn on_open_user_manual() {
    use aw_services::user_manual::{
        open_user_manual, MANUAL_UNAVAILABLE, MANUAL_UNAVAILABLE_TITLE,
    };
    if open_user_manual() {
        return;
    }
    if let Some(w) = window() {
        message_box(
            &w.frame,
            MANUAL_UNAVAILABLE,
            MANUAL_UNAVAILABLE_TITLE,
            MessageDialogStyle::OK | MessageDialogStyle::IconError,
        );
    }
}

/// Help > Report Issue.
pub(crate) fn on_report_issue() {
    if let Some(w) = window() {
        super::report_issue::show_report_issue_dialog(&w.frame);
    }
}

/// Help > Debug > Test: Discussion Updated.
pub(crate) fn on_test_discussion_notification() {
    super::debug_menu::on_test_discussion_notification();
}

/// Help > Debug > Test: Alert Notification.
pub(crate) fn on_test_alert_notification() {
    super::debug_menu::on_test_alert_notification();
}

/// Help > Debug > Test: Simulate Alert Change.
pub(crate) fn on_debug_simulate_alert() {
    super::debug_menu::on_debug_simulate_alert();
}

/// Help > Debug > Run Notification Diagnostics.
pub(crate) fn on_test_notifications() {
    super::debug_menu::on_test_notifications();
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
    show_alert_details_at(index as usize);
}

/// `_show_alert_details`: the alert behind list row `alert_index`. In All
/// Locations the rows are the aggregated (location, alert) pairs; otherwise
/// they are the current location's active alerts. Toast activation also
/// lands here with an index into the active alerts.
pub(crate) fn show_alert_details_at(alert_index: usize) {
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
        super::alert_dialog::show_alert_details(&alert);
    }
}
