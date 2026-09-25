//! wxDragon user interface, mirroring the Python `accessiweather.ui` package:
//! the main window, its menus and shortcuts, and the location dialogs.

mod commands;
mod community_packs_dialog;
mod display;
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

pub(crate) use main_window::{build_main_window, main_frame};
pub(crate) use refresh::refresh_now;
