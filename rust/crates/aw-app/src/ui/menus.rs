//! Menu bar, as built by `MainWindowUIMixin._create_menu_bar`
//! (`ui/main_window_ui.py`). Every item routes through [`on_menu`].

use wxdragon::prelude::*;

use super::display::check_updates_label;
use super::{commands, locations};

/// wx stock ids wxDragon does not export (values from wx/defs.h).
pub(crate) const ID_PREFERENCES: Id = 5022;
pub(crate) const ID_REFRESH: Id = 5123;

pub(crate) const ID_ADD_LOCATION: Id = ID_HIGHEST + 1;
pub(crate) const ID_EDIT_LOCATION: Id = ID_HIGHEST + 2;
pub(crate) const ID_REMOVE_LOCATION: Id = ID_HIGHEST + 3;
pub(crate) const ID_REORDER_LOCATIONS: Id = ID_HIGHEST + 4;
pub(crate) const ID_EXPLAIN: Id = ID_HIGHEST + 5;
pub(crate) const ID_HISTORY: Id = ID_HIGHEST + 6;
pub(crate) const ID_PRECIPITATION_TIMELINE: Id = ID_HIGHEST + 7;
pub(crate) const ID_TOGGLE_EVENT_CENTER: Id = ID_HIGHEST + 8;
pub(crate) const ID_DISCUSSION: Id = ID_HIGHEST + 9;
pub(crate) const ID_AVIATION: Id = ID_HIGHEST + 10;
pub(crate) const ID_AIR_QUALITY: Id = ID_HIGHEST + 11;
pub(crate) const ID_UV_INDEX: Id = ID_HIGHEST + 12;
pub(crate) const ID_NOAA_RADIO: Id = ID_HIGHEST + 13;
pub(crate) const ID_WEATHER_CHAT: Id = ID_HIGHEST + 14;
pub(crate) const ID_SOUNDPACK_MANAGER: Id = ID_HIGHEST + 15;
pub(crate) const ID_CHECK_UPDATES: Id = ID_HIGHEST + 16;
pub(crate) const ID_USER_MANUAL: Id = ID_HIGHEST + 17;
pub(crate) const ID_DEBUG_DISCUSSION: Id = ID_HIGHEST + 18;
pub(crate) const ID_DEBUG_ALERT: Id = ID_HIGHEST + 19;
pub(crate) const ID_DEBUG_SIMULATE_ALERT: Id = ID_HIGHEST + 20;
pub(crate) const ID_DEBUG_DIAGNOSTICS: Id = ID_HIGHEST + 21;
pub(crate) const ID_REPORT_ISSUE: Id = ID_HIGHEST + 22;

pub(crate) fn build_menu_bar(update_channel: &str, debug_mode: bool) -> MenuBar {
    let file = Menu::builder()
        .append_item(ID_PREFERENCES, "&Settings\tCtrl+S", "Open settings")
        .append_separator()
        .append_item(ID_EXIT, "E&xit\tCtrl+Q", "Exit the application")
        .build();

    let location = Menu::builder()
        .append_item(
            ID_ADD_LOCATION,
            "&Add Location\tCtrl+L",
            "Add a new location",
        )
        .append_item(
            ID_EDIT_LOCATION,
            "&Edit Location...\tF2",
            "Edit the selected location (e.g. enable Marine Mode)",
        )
        .append_item(
            ID_REMOVE_LOCATION,
            "&Remove Location\tCtrl+D",
            "Remove selected location",
        )
        .append_item(
            ID_REORDER_LOCATIONS,
            "Re&order Locations...",
            "Choose a custom order for saved locations",
        )
        .build();

    let view = Menu::builder()
        .append_item(ID_REFRESH, "Re&fresh\tF5", "Refresh weather data")
        .append_separator()
        .append_item(
            ID_EXPLAIN,
            "&Explain Weather\tCtrl+E",
            "Get AI explanation of weather",
        )
        .append_separator()
        .append_item(
            ID_HISTORY,
            "Weather &History\tCtrl+H",
            "View weather history",
        )
        .append_item(
            ID_PRECIPITATION_TIMELINE,
            "Precipitation &Timeline...",
            "View Pirate Weather minute-by-minute precipitation guidance",
        )
        .append_check_item(
            ID_TOGGLE_EVENT_CENTER,
            "Event &Center",
            "Show or hide the Event Center",
        )
        .append_item(
            ID_DISCUSSION,
            "Forecaster &Notes...",
            "View forecaster notes and surf or beach conditions",
        )
        .append_item(ID_AVIATION, "&Aviation Weather...", "View aviation weather")
        .append_item(
            ID_AIR_QUALITY,
            "Air &Quality...",
            "View air quality information",
        )
        .append_item(ID_UV_INDEX, "&UV Index...", "View UV index information")
        .append_item(
            ID_NOAA_RADIO,
            "NOAA Weather &Radio...\tCtrl+N",
            "Listen to NOAA Weather Radio",
        )
        .append_separator()
        .append_item(
            ID_WEATHER_CHAT,
            "Weather Assistan&t...\tCtrl+T",
            "Chat with AI weather assistant",
        )
        .build();
    view.check_item(ID_TOGGLE_EVENT_CENTER, true);

    let tools = Menu::builder()
        .append_item(
            ID_SOUNDPACK_MANAGER,
            "&Soundpack Manager...",
            "Manage sound packs",
        )
        .build();

    let help = Menu::builder()
        .append_item(
            ID_CHECK_UPDATES,
            &check_updates_label(update_channel),
            "Check for application updates",
        )
        .append_item(
            ID_USER_MANUAL,
            "User &Manual",
            "Open the AccessiWeather user manual",
        )
        .build();
    if debug_mode {
        let debug = Menu::builder()
            .append_item(
                ID_DEBUG_DISCUSSION,
                "Test: &Discussion Updated",
                "Fire a test notification as if the NWS discussion was updated",
            )
            .append_item(
                ID_DEBUG_ALERT,
                "Test: &Alert Notification...",
                "Send a test alert notification (choose type and severity)",
            )
            .append_item(
                ID_DEBUG_SIMULATE_ALERT,
                "Test: &Simulate Alert Change (poll cycle)",
                "Inject a mock alert into the next event check cycle to test the full polling path",
            )
            .append_separator()
            .append_item(
                ID_DEBUG_DIAGNOSTICS,
                "Run Notification &Diagnostics",
                "Run pass/fail notification system diagnostics",
            )
            .build();
        help.append_submenu(debug, "&Debug", "Debug and test tools");
    }
    help.append_separator();
    help.append(
        ID_REPORT_ISSUE,
        "&Report Issue...",
        "Report a bug or request a feature",
        ItemKind::Normal,
    );
    help.append_separator();
    help.append(ID_ABOUT, "&About", "About AccessiWeather", ItemKind::Normal);

    let bar = MenuBar::builder()
        .append(file, "&File")
        .append(location, "&Location")
        .append(view, "&View")
        .append(tools, "&Tools")
        .append(help, "&Help")
        .build();
    // Nothing to show until minutely data arrives.
    bar.enable_item(ID_PRECIPITATION_TIMELINE, false);
    bar
}

/// One dispatch point for every menu command.
pub(crate) fn on_menu(id: Id) {
    match id {
        ID_PREFERENCES => locations::on_settings(),
        ID_EXIT => commands::request_exit(),
        ID_ADD_LOCATION => locations::on_add_location(),
        ID_EDIT_LOCATION => locations::on_edit_location(),
        ID_REMOVE_LOCATION => locations::on_remove_location(),
        ID_REORDER_LOCATIONS => locations::on_reorder_locations(),
        ID_REFRESH => locations::on_refresh(),
        ID_EXPLAIN => commands::on_explain_weather(),
        ID_HISTORY => locations::on_view_history(),
        ID_PRECIPITATION_TIMELINE => commands::on_precipitation_timeline(),
        ID_TOGGLE_EVENT_CENTER => commands::toggle_event_center(),
        ID_DISCUSSION => commands::on_discussion(),
        ID_AVIATION => commands::on_aviation(),
        ID_AIR_QUALITY => commands::on_air_quality(),
        ID_UV_INDEX => commands::on_uv_index(),
        ID_NOAA_RADIO => commands::on_noaa_radio(),
        ID_WEATHER_CHAT => commands::on_weather_chat(),
        ID_SOUNDPACK_MANAGER => commands::on_soundpack_manager(),
        ID_CHECK_UPDATES => commands::on_check_updates(),
        ID_USER_MANUAL => commands::on_open_user_manual(),
        ID_DEBUG_DISCUSSION => commands::on_test_discussion_notification(),
        ID_DEBUG_ALERT => commands::on_test_alert_notification(),
        ID_DEBUG_SIMULATE_ALERT => commands::on_debug_simulate_alert(),
        ID_DEBUG_DIAGNOSTICS => commands::on_test_notifications(),
        ID_REPORT_ISSUE => commands::on_report_issue(),
        ID_ABOUT => commands::on_about(),
        _ => {}
    }
}
