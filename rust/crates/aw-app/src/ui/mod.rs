//! wxDragon user interface, mirroring the Python `accessiweather.ui` package:
//! the main window, its menus and shortcuts, and the location and alert dialogs.

mod alert_dialog;
mod commands;
mod display;
mod location_dialog;
mod locations;
mod main_window;
mod menus;
mod refresh;
mod settings_dialog;
mod shortcuts;
mod weather_source;

#[cfg(test)]
mod golden_tests;

#[allow(unused_imports)] // Entry points for toast activation and immediate alert popups.
pub(crate) use alert_dialog::{show_alert_details, show_alerts_summary};
#[allow(unused_imports)]
pub(crate) use commands::show_alert_details_at;
pub(crate) use main_window::{build_main_window, main_frame};
pub(crate) use refresh::refresh_now;

// Used by the lifecycle, tray and hotkey modules.
pub(crate) use commands::{
    on_discussion, on_test_alert_notification, on_test_discussion_notification, request_exit,
};
pub(crate) use main_window::{
    message_box, set_initial_focus, set_status, start_background_updates, window_state,
};
pub(crate) use weather_source::get_cached_weather;
