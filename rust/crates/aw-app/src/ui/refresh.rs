//! Refresh flow, ported from `ui/main_window_refresh.py`: fetch generations,
//! the refresh button, All Locations batch refreshes, cache pre-warming and
//! filling the panels from the presentation.

use aw_core::model::WeatherData;
use aw_core::Location;
use chrono::Utc;
use wxdragon::prelude::WxWidget;

use super::display;
use super::main_window::{self as mw, window, window_state};
use super::weather_source::{self, Fetched};
use crate::app::{post_to_ui, with_state};

/// `_set_current_location`: select and persist.
pub(crate) fn set_current_location(location_name: &str) {
    let Some(state) = with_state() else { return };
    let mut st = state.borrow_mut();
    if st.config.set_current_location(location_name) && crate::app::save(&st).is_ok() {
        tracing::info!("Current location set and saved: {location_name}");
    } else {
        tracing::error!(
            "Failed to set current location '{location_name}': location not found or save failed"
        );
    }
}

/// Fetch `locations` one by one on a worker thread (`pre_warm_batch`),
/// caching each result on the UI thread, then run `done` there.
fn fetch_in_background(locations: Vec<Location>, done: impl FnOnce() + Send + 'static) {
    let Some(state) = with_state() else { return };
    let (client, settings) = {
        let st = state.borrow();
        (st.client.clone(), st.config.settings.clone())
    };
    std::thread::Builder::new()
        .name("aw-prewarm".into())
        .spawn(move || {
            for location in locations {
                let fetched = weather_source::fetch(&client, &settings, &location);
                post_to_ui(move || {
                    remember(fetched);
                });
            }
            post_to_ui(done);
        })
        .expect("spawn pre-warm thread");
}

fn remember(fetched: Fetched) -> Option<WeatherData> {
    let state = with_state()?;
    let mut st = state.borrow_mut();
    Some(weather_source::remember(&mut st, fetched))
}

/// `refresh_weather_async`.
pub(crate) fn refresh_weather_async(force_refresh: bool) {
    let (Some(w), Some(state)) = (window(), with_state()) else {
        return;
    };
    // All Locations: refresh every saved location, then redraw the summary.
    if window_state(|s| s.all_locations_active) {
        w.refresh_button.enable(false);
        fetch_all_locations_data();
        return;
    }
    let (location, client, settings, generation) = {
        let mut st = state.borrow_mut();
        if st.is_updating && !force_refresh {
            tracing::debug!("Already updating, skipping refresh");
            return;
        }
        st.is_updating = true;
        let generation = window_state(|s| {
            s.fetch_generation += 1;
            s.fetch_generation
        });
        (
            st.config.current_location.clone(),
            st.client.clone(),
            st.config.settings.clone(),
            generation,
        )
    };
    w.refresh_button.enable(false);
    let Some(location) = location else {
        on_weather_error("No location selected");
        return;
    };
    std::thread::Builder::new()
        .name("aw-refresh".into())
        .spawn(move || {
            let fetched = weather_source::fetch(&client, &settings, &location);
            post_to_ui(move || {
                let Some(data) = remember(fetched) else {
                    return;
                };
                if generation != window_state(|s| s.fetch_generation) {
                    tracing::debug!("Discarding stale fetch for {}", location.name);
                    return;
                }
                on_weather_data_received(data, true);
                if !force_refresh {
                    pre_warm_other_locations(&location);
                }
            });
        })
        .expect("spawn refresh thread");
}

/// `_fetch_all_locations_data`.
pub(crate) fn fetch_all_locations_data() {
    let Some(state) = with_state() else { return };
    let locations = state.borrow().config.locations.clone();
    fetch_in_background(locations, on_all_locations_refresh_complete);
}

/// `_on_all_locations_refresh_complete`.
fn on_all_locations_refresh_complete() {
    if window_state(|s| s.all_locations_active) {
        mw::show_all_locations_summary();
    }
    if let Some(w) = window() {
        w.refresh_button.enable(true);
    }
    if let Some(state) = with_state() {
        state.borrow_mut().is_updating = false;
    }
}

/// `_pre_warm_other_locations`: fetch saved locations with nothing cached
/// so switching to them is instant.
fn pre_warm_other_locations(current: &Location) {
    let Some(state) = with_state() else { return };
    let uncached: Vec<Location> = state
        .borrow()
        .config
        .locations
        .iter()
        .filter(|l| l.name != current.name)
        .filter(|l| !weather_source::get_cached_weather(l).is_some_and(|d| d.has_any_data()))
        .cloned()
        .collect();
    if !uncached.is_empty() {
        tracing::debug!("Pre-warming cache for {} locations", uncached.len());
        fetch_in_background(uncached, || {});
    }
}

/// `_on_weather_error`.
pub(crate) fn on_weather_error(error_message: &str) {
    mw::set_status(&format!("Error: {error_message}"));
    if let Some(state) = with_state() {
        state.borrow_mut().is_updating = false;
    }
    if let Some(w) = window() {
        w.refresh_button.enable(true);
    }
    // Python also plays the fetch_error sound here.
}

/// `_on_weather_data_received`.
pub(crate) fn on_weather_data_received(weather_data: WeatherData, play_refresh_sound: bool) {
    if window_state(|s| s.all_locations_active) {
        tracing::debug!("Ignoring stale weather data received while All Locations view is active");
        return;
    }
    let (Some(w), Some(state)) = (window(), with_state()) else {
        return;
    };
    mw::update_precipitation_timeline_menu_state(Some(&weather_data));
    let presentation = {
        let mut st = state.borrow_mut();
        st.current_weather_data = Some(weather_data.clone());
        weather_source::present(&st.config.settings, &weather_data)
    };

    let texts = display::panel_texts(&presentation);
    w.current_conditions.set_value(&texts.current);
    mw::set_stale_warning(&texts.stale_warning);
    mw::set_forecast_sections(&texts.daily, &texts.hourly);
    if let Some(briefing) = &texts.briefing {
        mw::append_event_center_entry(briefing, Some("Briefing"));
    }

    if let Some(alerts) = &weather_data.alerts {
        let labels = display::compute_lifecycle_labels(&alerts.active(Utc::now()));
        window_state(|s| s.alert_lifecycle_labels = labels);
    }
    let labels = window_state(|s| s.alert_lifecycle_labels.clone());
    mw::update_alerts(weather_data.alerts.as_ref(), &labels);

    // Python also hands the alerts to the notification system, updates the
    // tray tooltip and processes AFD/severe-risk notification events here.
    mw::set_last_updated_status();
    if play_refresh_sound {
        tracing::debug!("data_updated sound belongs to the audio port");
    }

    state.borrow_mut().is_updating = false;
    w.refresh_button.enable(true);
}

/// Re-fetch after something outside the window changed (API keys imported).
pub(crate) fn refresh_now() {
    refresh_weather_async(false);
}
