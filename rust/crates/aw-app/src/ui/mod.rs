//! wxDragon user interface, mirroring the Python `accessiweather.ui` package:
//! the main window, its menus and shortcuts, and the location and alert dialogs.
//! the main window, its menus and shortcuts, the location dialogs and the
//! Settings dialog.
//! the main window, its menus and shortcuts, and the location, alert and NOAA
//! Weather Radio dialogs.

mod ai_model_check;
mod alert_dialog;
mod assistant_host;
mod aviation_dialog;
mod commands;
mod community_packs_dialog;
mod data_dialogs;
mod debug_menu;
mod display;
mod explanation_dialog;
mod forecast_products;
pub(crate) mod guidance;
mod location_dialog;
mod locations;
mod main_window;
mod menus;
mod model_browser_dialog;
mod noaa_radio_dialog;
mod progress_dialog;
mod refresh;
mod report_issue;
mod settings_actions;
mod settings_dialog;
mod settings_form;
mod settings_modals;
mod settings_tabs;
mod shortcuts;
mod soundpack_manager;
mod soundpack_wizard;
mod tray_text_format_dialog;
pub(crate) mod updates;
mod weather_assistant_dialog;
mod weather_source;

#[cfg(test)]
mod golden_miscui;
#[cfg(test)]
mod golden_tests;
#[cfg(test)]
mod settings_golden_tests;

#[allow(unused_imports)] // Entry points for toast activation and immediate alert popups.
pub(crate) use alert_dialog::{show_alert_details, show_alerts_summary};
#[allow(unused_imports)]
pub(crate) use commands::show_alert_details_at;
pub(crate) use main_window::{build_main_window, main_frame};
pub(crate) use noaa_radio_dialog::close_noaa_radio_dialog;

// Used by the lifecycle, tray and hotkey modules.
pub(crate) use commands::{
    on_discussion, on_test_alert_notification, on_test_discussion_notification, request_exit,
};
pub(crate) use main_window::{
    message_box, set_initial_focus, set_status, start_background_updates, window_state,
};
pub(crate) use weather_source::get_cached_weather;
