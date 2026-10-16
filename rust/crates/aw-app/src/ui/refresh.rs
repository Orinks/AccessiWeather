//! Refresh flow, ported from `ui/main_window_refresh.py` and
//! `ui/main_window_notification_events.py`: fetch generations, the refresh
//! button, All Locations batch refreshes, cache and text-product
//! pre-warming, the lightweight event poll and filling the panels from the
//! presentation.

use std::sync::atomic::{AtomicU64, Ordering};

use aw_core::alert_lifecycle::compute_lifecycle_labels;
use aw_core::display::WeatherPresenter;
use aw_core::model::WeatherData;
use aw_core::Location;
use aw_providers::client::WeatherClient;
use aw_providers::products::ForecastProductService;
use chrono::Utc;
use wxdragon::prelude::WxWidget;

use super::display;
use super::main_window::{self as mw, window, window_state};
use super::weather_events::{weather_updated, WeatherUpdate};
use crate::app::{post_to_ui, with_state};

/// `_fetch_generation`: bumped per fetch (and on switching to All
/// Locations) so a superseded fetch never updates the display. Atomic
/// because the worker checks it before pre-warming, as Python does.
pub(crate) static FETCH_GENERATION: AtomicU64 = AtomicU64::new(0);

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

fn spawn(name: &str, work: impl FnOnce() + Send + 'static) {
    std::thread::Builder::new()
        .name(name.into())
        .spawn(work)
        .expect("spawn worker thread");
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
    let (location, locations, client, products) = {
        let mut st = state.borrow_mut();
        if st.is_updating && !force_refresh {
            tracing::debug!("Already updating, skipping refresh");
            return;
        }
        st.is_updating = true;
        (
            st.config.current_location.clone(),
            st.config.locations.clone(),
            st.client.clone(),
            st.products.clone(),
        )
    };
    let generation = FETCH_GENERATION.fetch_add(1, Ordering::SeqCst) + 1;
    w.refresh_button.enable(false);
    let Some(location) = location else {
        on_weather_error("No location selected");
        return;
    };
    spawn("aw-refresh", move || {
        let weather_data = client.get_weather_data(&location, force_refresh);
        let current = FETCH_GENERATION.load(Ordering::SeqCst);
        if generation != current {
            tracing::debug!(
                "Discarding stale fetch for {} (gen {generation} < {current})",
                location.name
            );
            return;
        }
        // Warm AFD/HWO/SPS/SRF/CLI first so the notification checks run on
        // the display update find them cached.
        products.pre_warm_location(&location);
        post_to_ui(move || on_weather_data_received(weather_data, true));
        if !force_refresh {
            pre_warm_other_locations(&client, &products, &location, &locations);
        }
    });
}

/// `_fetch_all_locations_data`: `pre_warm_batch` over every saved location.
pub(crate) fn fetch_all_locations_data() {
    let Some(state) = with_state() else { return };
    let (locations, client) = {
        let st = state.borrow();
        (st.config.locations.clone(), st.client.clone())
    };
    spawn("aw-all-locations", move || {
        if !locations.is_empty() {
            client.pre_warm_batch(&locations);
        }
        post_to_ui(on_all_locations_refresh_complete);
    });
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

/// `_pre_warm_other_locations` (worker thread): cache the saved locations
/// with nothing cached so switching is instant, then warm the text products
/// of every other location.
fn pre_warm_other_locations(
    client: &WeatherClient,
    products: &ForecastProductService,
    current: &Location,
    locations: &[Location],
) {
    let uncached: Vec<Location> = locations
        .iter()
        .filter(|l| l.name != current.name)
        .filter(|l| {
            !client
                .get_cached_weather(l)
                .is_some_and(|d| d.has_any_data())
        })
        .cloned()
        .collect();
    if !uncached.is_empty() {
        tracing::debug!("Pre-warming cache for {} locations", uncached.len());
        client.pre_warm_batch(&uncached);
    }
    for location in locations.iter().filter(|l| l.name != current.name) {
        products.pre_warm_location(location);
    }
}

/// `refresh_notification_events_async`: alerts, AFD and minutely data only,
/// without redrawing the window. Skipped during a full refresh.
pub(crate) fn refresh_notification_events_async() {
    let Some(state) = with_state() else { return };
    let (location, client) = {
        let st = state.borrow();
        if st.is_updating {
            tracing::debug!("Skipping event check while full weather refresh is in progress");
            return;
        }
        (st.config.current_location.clone(), st.client.clone())
    };
    let Some(location) = location else { return };
    spawn("aw-event-poll", move || {
        let weather_data = client.get_notification_event_data(&location);
        post_to_ui(move || {
            weather_updated(WeatherUpdate::EventPoll {
                weather_data: &weather_data,
            })
        });
    });
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
    super::weather_events::on_fetch_error();
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
    let (presentation, location_name) = {
        let mut st = state.borrow_mut();
        st.current_weather_data = Some(weather_data.clone());
        let location_name = st
            .config
            .current_location
            .as_ref()
            .map_or_else(|| "Unknown".to_string(), |l| l.name.clone());
        (
            WeatherPresenter::new(&st.config.settings).present(&weather_data),
            location_name,
        )
    };
    mw::update_precipitation_timeline_menu_state(Some(&weather_data));

    let texts = display::panel_texts(&presentation);
    w.current_conditions.set_value(&texts.current);
    mw::set_stale_warning(&texts.stale_warning);
    mw::set_forecast_sections(&texts.daily, &texts.hourly);
    if let Some(briefing) = &texts.briefing {
        mw::append_event_center_entry(briefing, Some("Briefing"));
    }

    if let Some(alerts) = &weather_data.alerts {
        let active: Vec<_> = alerts.active(Utc::now()).into_iter().cloned().collect();
        let labels = compute_lifecycle_labels(&active);
        window_state(|s| s.alert_lifecycle_labels = labels);
    }
    let labels = window_state(|s| s.alert_lifecycle_labels.clone());
    mw::update_alerts(weather_data.alerts.as_ref(), &labels);

    crate::tray::update_for_current_location(&weather_data);
    weather_updated(WeatherUpdate::Displayed {
        weather_data: &weather_data,
        location_name: &location_name,
        play_refresh_sound,
    });
    mw::set_last_updated_status();

    state.borrow_mut().is_updating = false;
    w.refresh_button.enable(true);
}
