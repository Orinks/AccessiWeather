//! Location selection and management, ported from
//! `ui/main_window_locations.py`.

use wxdragon::prelude::*;

use super::display::ALL_LOCATIONS_SENTINEL;
use super::main_window::{self as mw, message_box, window, window_state};
use super::{location_dialog, refresh, settings_dialog, weather_source};
use crate::app::{post_to_ui, save, with_state};

pub(crate) const MSG_SELECT_TO_EDIT: &str = "Please select a specific location to edit.";
pub(crate) const MSG_SELECT_TO_REMOVE: &str = "Please select a specific location to remove.";
pub(crate) const CAPTION_NO_LOCATION: &str = "No Location Selected";
pub(crate) const MSG_LAST_LOCATION: &str =
    "Cannot remove the last location. Add another location first.";
pub(crate) const CAPTION_CANNOT_REMOVE: &str = "Cannot Remove";
pub(crate) const CAPTION_CONFIRM_REMOVAL: &str = "Confirm Removal";
pub(crate) const MSG_NOT_ENOUGH_LOCATIONS: &str =
    "Add at least two saved locations before reordering them.";
pub(crate) const CAPTION_NOT_ENOUGH_LOCATIONS: &str = "Not Enough Locations";

pub(crate) fn confirm_removal_message(name: &str) -> String {
    format!("Are you sure you want to remove '{name}'?")
}

fn selected_location_name() -> Option<String> {
    window()?
        .location_dropdown
        .get_string_selection()
        .filter(|s| !s.is_empty())
}

fn warn(message: &str, caption: &str) {
    if let Some(w) = window() {
        message_box(
            &w.frame,
            message,
            caption,
            MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
        );
    }
}

/// `_on_location_changed`: show cached data at once, then fetch after a
/// 500 ms pause so arrowing through the list stays quick.
pub(crate) fn on_location_changed() {
    let Some(selected) = selected_location_name() else {
        return;
    };
    tracing::info!("Location changed to: {selected}");
    window_state(|s| s.alert_lifecycle_labels.clear());

    if selected == ALL_LOCATIONS_SENTINEL {
        window_state(|s| {
            s.all_locations_active = true;
            s.fetch_generation += 1;
        });
        mw::update_title_for_location(Some(ALL_LOCATIONS_SENTINEL));
        mw::update_precipitation_timeline_menu_state(None);
        // After anything already queued (e.g. a finished fetch), so stale
        // single-location data cannot overwrite the summary.
        post_to_ui(mw::show_all_locations_summary);
        refresh::fetch_all_locations_data();
        return;
    }

    window_state(|s| {
        s.all_locations_active = false;
        s.all_locations_alerts_data.clear();
        s.last_single_location_name = Some(selected.clone());
    });
    mw::set_forecast_sections_visible(true);
    mw::update_title_for_location(Some(&selected));
    refresh::set_current_location(&selected);

    let location = with_state().and_then(|s| s.borrow().config.current_location.clone());
    if let Some(location) = location {
        if let Some(cached) =
            weather_source::get_cached_weather(&location).filter(|d| d.has_any_data())
        {
            tracing::info!("Showing cached data for {selected} while refreshing");
            refresh::on_weather_data_received(cached, false);
        }
        // Python also runs a lightweight alert/event check here.
    }
    mw::restart_location_debounce();
}

/// `on_add_location`.
pub(crate) fn on_add_location() {
    let Some(w) = window() else { return };
    let Some(new_name) = location_dialog::show_add_location_dialog(&w.frame) else {
        return;
    };
    mw::populate_locations();
    // Land on the new location.
    if let Some(index) = mw::find_location_index(&new_name) {
        w.location_dropdown.set_selection(index);
        refresh::set_current_location(&new_name);
    }
    refresh::refresh_weather_async(false);
}

/// `on_edit_location`.
pub(crate) fn on_edit_location() {
    let Some(w) = window() else { return };
    let selected = selected_location_name().filter(|s| s != ALL_LOCATIONS_SENTINEL);
    let Some(selected) = selected else {
        warn(MSG_SELECT_TO_EDIT, CAPTION_NO_LOCATION);
        return;
    };
    let Some(state) = with_state() else { return };
    let Some(location) = state.borrow().config.find_location(&selected).cloned() else {
        return;
    };
    let Some(edit) = location_dialog::show_edit_location_dialog(&w.frame, &location) else {
        return;
    };
    let updated = {
        let mut st = state.borrow_mut();
        st.config.update_location_details(
            &selected,
            edit.latitude,
            edit.longitude,
            edit.country_code,
            edit.marine_mode,
            Some(&edit.display_name),
        ) && save(&st).is_ok()
    };
    if updated {
        mw::populate_locations();
        if let Some(index) = mw::find_location_index(&edit.display_name) {
            w.location_dropdown.set_selection(index);
            refresh::set_current_location(&edit.display_name);
        }
    } else {
        warn(
            &format!("Could not update '{selected}'. Your changes were not saved."),
            "Update Failed",
        );
    }
    refresh::refresh_weather_async(true);
}

/// `on_remove_location`: never the last one, and only after confirmation.
pub(crate) fn on_remove_location() {
    let Some(w) = window() else { return };
    let selected = selected_location_name().filter(|s| s != ALL_LOCATIONS_SENTINEL);
    let Some(selected) = selected else {
        warn(MSG_SELECT_TO_REMOVE, CAPTION_NO_LOCATION);
        return;
    };
    let Some(state) = with_state() else { return };
    if state.borrow().config.locations.len() <= 1 {
        warn(MSG_LAST_LOCATION, CAPTION_CANNOT_REMOVE);
        return;
    }
    let answer = message_box(
        &w.frame,
        &confirm_removal_message(&selected),
        CAPTION_CONFIRM_REMOVAL,
        MessageDialogStyle::YesNo | MessageDialogStyle::IconQuestion,
    );
    if answer == ID_YES {
        {
            let mut st = state.borrow_mut();
            st.config.remove_location(&selected);
            let _ = save(&st);
        }
        mw::populate_locations();
        refresh::refresh_weather_async(false);
    }
}

/// `on_reorder_locations`: saving a custom order switches the sort to manual.
pub(crate) fn on_reorder_locations() {
    let Some(w) = window() else { return };
    let Some(state) = with_state() else { return };
    if state.borrow().config.locations.len() < 2 {
        message_box(
            &w.frame,
            MSG_NOT_ENOUGH_LOCATIONS,
            CAPTION_NOT_ENOUGH_LOCATIONS,
            MessageDialogStyle::OK | MessageDialogStyle::IconInformation,
        );
        return;
    }
    let Some(ordered_names) = location_dialog::show_reorder_locations_dialog(&w.frame) else {
        return;
    };
    let reordered = {
        let mut st = state.borrow_mut();
        st.config.reorder_locations(&ordered_names) && save(&st).is_ok()
    };
    if !reordered {
        warn(
            "Could not save the new saved-location order.",
            "Reorder Failed",
        );
        return;
    }
    {
        let mut st = state.borrow_mut();
        st.config.settings.location_sort_order = "manual".to_string();
        let _ = save(&st);
    }
    mw::populate_locations();
    if window_state(|s| s.all_locations_active) {
        mw::show_all_locations_summary();
    }
}

/// `on_refresh`.
pub(crate) fn on_refresh() {
    refresh::refresh_weather_async(true);
}

/// `on_settings` / `open_settings`.
pub(crate) fn on_settings() {
    let (Some(w), Some(state)) = (window(), with_state()) else {
        return;
    };
    if settings_dialog::show_settings_dialog(&w.frame, &state) {
        // `refresh_runtime_settings`: the update interval may have changed.
        mw::start_background_updates();
        mw::populate_locations();
        mw::update_check_updates_menu_label();
        refresh::refresh_weather_async(true);
    }
}

/// `on_view_history` (Ctrl+H): the Weather History dialog is ported separately.
pub(crate) fn on_view_history() {
    tracing::info!("Weather History dialog is not ported yet");
}
