//! wxDragon user interface, mirroring the Python `accessiweather.ui` package:
//! the main window, its menus and shortcuts, and the location, alert and NOAA
//! Weather Radio dialogs.

mod alert_dialog;
mod commands;
mod display;
mod location_dialog;
mod locations;
mod main_window;
mod menus;
mod noaa_radio_dialog;
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
pub(crate) use main_window::{build_main_window, main_frame, set_status};
pub(crate) use noaa_radio_dialog::close_noaa_radio_dialog;
pub(crate) use refresh::refresh_now;
