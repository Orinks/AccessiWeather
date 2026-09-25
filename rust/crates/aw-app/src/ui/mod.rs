//! wxDragon user interface, mirroring the Python `accessiweather.ui` package:
//! the main window, its menus and shortcuts, and the location and alert dialogs.

mod alert_dialog;
mod commands;
mod community_packs_dialog;
mod display;
mod forecast_products;
mod location_dialog;
mod locations;
mod main_window;
mod menus;
mod progress_dialog;
mod refresh;
mod settings_dialog;
mod shortcuts;
mod soundpack_manager;
mod soundpack_wizard;
mod weather_source;

#[cfg(test)]
mod golden_tests;

#[allow(unused_imports)] // Entry points for toast activation and immediate alert popups.
pub(crate) use alert_dialog::{show_alert_details, show_alerts_summary};
#[allow(unused_imports)]
pub(crate) use commands::show_alert_details_at;
pub(crate) use main_window::{build_main_window, main_frame};
pub(crate) use refresh::refresh_now;
