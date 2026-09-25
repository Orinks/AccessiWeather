//! The one place weather data reaches notifications, sounds and the tray.
//!
//! Python does this work inline in `_on_weather_data_received`
//! (`ui/main_window_refresh.py`) and `on_notification_event_data_received`
//! (`ui/main_window_notification_events.py`); the notification, sound and
//! tray ports hook in here.

use aw_core::model::WeatherData;

/// Where the data came from; Python treats the two differently.
pub(crate) enum WeatherUpdate<'a> {
    /// `_on_weather_data_received`: a full refresh, or cached data shown
    /// while switching locations (`play_refresh_sound` false). Python then:
    /// - when `alerts.has_alerts()`, schedules
    ///   `alert_notification_system.process_and_notify(weather_data.alerts)`
    ///   (logging the active alerts' id/event/severity);
    /// - `update_tray_tooltip(weather_data, location_name)`;
    /// - `_process_notification_events(weather_data)`: AFD update, severe
    ///   risk, minutely precipitation start/stop and likelihood, then the
    ///   HWO / SPS / daily climate checks against the pre-warmed
    ///   `State::products` cache (suppressed on the first run after start);
    /// - plays the `data_updated` sound when `play_refresh_sound` and
    ///   `sound_enabled`.
    Displayed {
        weather_data: &'a WeatherData,
        location_name: &'a str,
        play_refresh_sound: bool,
    },
    /// `on_notification_event_data_received`: the 60 s lightweight poll
    /// (`WeatherClient::get_notification_event_data`). Python then:
    /// - when `alerts.has_alerts()`, schedules `process_and_notify(alerts)`;
    /// - when `alert_lifecycle_diff.has_changes`, schedules
    ///   `notify_lifecycle_changes(diff)`.
    ///
    /// Discussion and risk events are deliberately not processed here.
    EventPoll { weather_data: &'a WeatherData },
}

/// Called on the UI thread after the main window shows new data and after
/// every lightweight event poll.
pub(crate) fn weather_updated(update: WeatherUpdate<'_>) {
    match update {
        WeatherUpdate::Displayed {
            weather_data,
            location_name,
            play_refresh_sound,
        } => tracing::debug!(
            "Weather shown for {location_name} ({} alert(s), refresh sound: {play_refresh_sound})",
            weather_data.alerts.as_ref().map_or(0, |a| a.alerts.len())
        ),
        WeatherUpdate::EventPoll { weather_data } => tracing::debug!(
            "Event poll for {} ({} alert(s))",
            weather_data.location.name,
            weather_data.alerts.as_ref().map_or(0, |a| a.alerts.len())
        ),
    }
}
