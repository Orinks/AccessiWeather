//! wxDragon user interface, mirroring the Python `accessiweather.ui` package:
//! the main window, its menus and shortcuts, the location dialogs and the
//! Settings dialog.

mod commands;
mod display;
mod location_dialog;
mod locations;
mod main_window;
mod menus;
mod model_browser_dialog;
mod refresh;
mod settings_actions;
mod settings_dialog;
mod settings_form;
mod settings_modals;
mod settings_tabs;
mod shortcuts;
mod tray_text_format_dialog;
mod weather_source;

#[cfg(test)]
mod golden_tests;
#[cfg(test)]
mod settings_golden_tests;

pub(crate) use main_window::{build_main_window, main_frame};
pub(crate) use refresh::refresh_now;
