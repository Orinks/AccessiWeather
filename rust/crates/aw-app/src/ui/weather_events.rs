//! The one place weather data reaches notifications, sounds and the tray.
//!
//! Ported from the notification half of `_on_weather_data_received`
//! (`ui/main_window_refresh.py`), `on_notification_event_data_received` and
//! `process_notification_events` (`ui/main_window_notification_events.py`),
//! the refresh/error sounds (`ui/main_window_display.py`), the Forecaster
//! Notes daily climate check (`forecast_products_dialog.py`), the immediate
//! alert popups (`app_activation.py`) and the notifier and alert parts of
//! `refresh_runtime_settings` (`app_lifecycle.py`).
//!
//! [`Notifications`] makes every decision with the clock passed in and hands
//! the results to a [`Sinks`]: the app's shows toasts, plays sounds, opens
//! dialogs, tunes the radio and writes the Event Center; the golden test
//! records them.

use std::cell::RefCell;
use std::path::PathBuf;
use std::sync::Arc;

use aw_core::model::{Location, TextProduct, WeatherAlert, WeatherData};
use aw_core::settings::AppSettings;
use aw_notify::events::window::{
    process_notification_events, CachedProducts, EventCenterEntry, EVENT_TOAST_TIMEOUT_SECONDS,
};
use aw_notify::{
    sound, AlertDispatch, AlertManager, AlertNotificationSystem, AlertSettings,
    NotificationEventManager, RuntimeState, Toast,
};
use aw_providers::products::{ForecastProductService, ProductResult};
use chrono::{DateTime, FixedOffset, Local, Utc};

use super::main_window as mw;
use crate::app::{post_to_ui, with_state};

/// Where the data came from; Python treats the two differently.
pub(crate) enum WeatherUpdate<'a> {
    /// `_on_weather_data_received`: a full refresh, or cached data shown
    /// while switching locations (`play_refresh_sound` false). The caller
    /// has already updated the tray tooltip.
    Displayed {
        weather_data: &'a WeatherData,
        location_name: &'a str,
        play_refresh_sound: bool,
    },
    /// `on_notification_event_data_received`: the 60 s lightweight poll
    /// (`WeatherClient::get_notification_event_data`, which also owns the
    /// minutely polling cadence and the NWS cancel confirmation). Only
    /// alerts and their lifecycle changes are processed here.
    EventPoll { weather_data: &'a WeatherData },
}

// ---------------------------------------------------------------------------
// Decisions
// ---------------------------------------------------------------------------

/// A sound the notifier or the window asks the audio layer for, with muted
/// events already removed.
#[derive(Debug, Clone, PartialEq)]
pub(crate) enum SoundCue {
    /// `play_notification_sound(event, pack)`.
    Event { pack: String, event: String },
    /// `play_notification_sound_candidates`: the first key the pack has.
    Candidates { pack: String, keys: Vec<String> },
}

/// `_show_immediate_alert_popup`.
#[derive(Debug, Clone, PartialEq)]
pub(crate) enum Popup {
    Details(Box<WeatherAlert>),
    Summary(Vec<WeatherAlert>),
}

/// What the notification flow asks the app to do.
pub(crate) trait Sinks {
    fn toast(&mut self, toast: &Toast);
    fn sound(&mut self, cue: SoundCue);
    fn popup(&mut self, popup: Popup);
    fn auto_tune(&mut self, alerts: &[WeatherAlert]);
    fn event_center(&mut self, entry: &EventCenterEntry);
}

/// The sound settings `app._notifier` holds; only `refresh_runtime_settings`
/// changes them.
struct NotifierSound {
    enabled: bool,
    pack: String,
    muted: Vec<String>,
}

impl NotifierSound {
    fn from_settings(settings: &AppSettings) -> Self {
        Self {
            enabled: settings.sound_enabled,
            pack: settings.sound_pack.clone(),
            muted: settings.muted_sound_events.clone(),
        }
    }
}

/// `app.alert_notification_system`, `app._notifier`'s sound settings and the
/// main window's notification event manager.
pub(crate) struct Notifications {
    alerts: AlertNotificationSystem,
    events: NotificationEventManager,
    notifier: NotifierSound,
    /// `_suppress_startup_text_product_notifications`: the first refresh
    /// only sets discussion/HWO/SPS/CLI baselines.
    suppress_startup: bool,
}

impl Notifications {
    /// Both managers share one handle to the runtime-state file. (Python
    /// gives the event manager its own, and the two caches overwrite each
    /// other's sections on save.)
    pub(crate) fn new(
        store: RuntimeState,
        settings: &AppSettings,
        soundpacks_dir: Option<PathBuf>,
        now: DateTime<Utc>,
    ) -> Self {
        let manager = AlertManager::new(
            store.clone(),
            AlertSettings::from_app_settings(settings),
            now,
        );
        Self {
            alerts: AlertNotificationSystem::new(manager, settings.clone(), soundpacks_dir),
            events: NotificationEventManager::new(Some(store), now),
            notifier: NotifierSound::from_settings(settings),
            suppress_startup: true,
        }
    }

    /// `_notifier.sound_enabled / soundpack / muted_sound_events = ...`.
    pub(crate) fn refresh_notifier_settings(&mut self, settings: &AppSettings) {
        self.notifier = NotifierSound::from_settings(settings);
    }

    /// `alert_notification_system.settings = settings` and
    /// `update_settings(settings.to_alert_settings())`.
    pub(crate) fn refresh_alert_settings(&mut self, settings: &AppSettings) {
        self.alerts.update_settings(settings.clone());
    }

    /// `notifier.send_notification`: the sound (when the notifier's sound is
    /// on and the toast wants one), then the toast.
    fn send(&self, sinks: &mut dyn Sinks, toast: &Toast) {
        if self.notifier.enabled && toast.play_sound {
            let candidates = toast.sound_candidates.as_deref().filter(|c| !c.is_empty());
            if let Some(mut keys) = sound::sound_keys_to_try(
                toast.sound_event.as_deref(),
                candidates,
                &self.notifier.muted,
            ) {
                let pack = self.notifier.pack.clone();
                sinks.sound(match candidates {
                    Some(_) => SoundCue::Candidates { pack, keys },
                    None => SoundCue::Event {
                        pack,
                        event: keys.swap_remove(0),
                    },
                });
            }
        }
        sinks.toast(toast);
    }

    /// The rest of `process_and_notify` / `notify_lifecycle_changes`: the
    /// popup, the radio, then the toasts.
    fn deliver_alerts(&self, sinks: &mut dyn Sinks, dispatch: AlertDispatch) {
        let AlertDispatch {
            toasts,
            mut popup_alerts,
            radio_auto_tune_alerts,
        } = dispatch;
        match popup_alerts.len() {
            0 => {}
            1 => sinks.popup(Popup::Details(Box::new(popup_alerts.remove(0)))),
            _ => sinks.popup(Popup::Summary(popup_alerts)),
        }
        if !radio_auto_tune_alerts.is_empty() {
            sinks.auto_tune(&radio_auto_tune_alerts);
        }
        for toast in &toasts {
            self.send(sinks, toast);
        }
    }

    /// `_on_weather_data_received` from the alert processing on: alert
    /// toasts, the event checks, then the `data_updated` sound. `settings`
    /// and `location` are the live ones; `now` is local wall-clock time.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn displayed(
        &mut self,
        sinks: &mut dyn Sinks,
        weather_data: &WeatherData,
        settings: &AppSettings,
        location: Option<&Location>,
        products: CachedProducts<'_>,
        play_refresh_sound: bool,
        now: DateTime<FixedOffset>,
    ) {
        let now_utc = now.with_timezone(&Utc);
        if let Some(alerts) = weather_data.alerts.as_ref().filter(|a| a.has_alerts()) {
            tracing::info!(
                "[notify-ui] full refresh scheduling alert processing for {} active alert(s)",
                alerts.active(now_utc).len()
            );
            let dispatch = self.alerts.process_and_notify(alerts, now_utc);
            self.deliver_alerts(sinks, dispatch);
        }
        // SPS statements already shown as alerts are not repeated.
        let active: Vec<WeatherAlert> = weather_data
            .alerts
            .as_ref()
            .map(|a| a.active(now_utc).into_iter().cloned().collect())
            .unwrap_or_default();
        let events = process_notification_events(
            &mut self.events,
            weather_data,
            settings,
            location,
            products,
            &active,
            &mut self.suppress_startup,
            now,
        );
        for entry in &events.event_center {
            sinks.event_center(entry);
        }
        for toast in &events.toasts {
            self.send(sinks, toast);
        }
        if play_refresh_sound {
            window_sound(sinks, settings, "data_updated");
        }
    }

    /// `on_notification_event_data_received`.
    pub(crate) fn event_poll(
        &mut self,
        sinks: &mut dyn Sinks,
        weather_data: &WeatherData,
        now: DateTime<Utc>,
    ) {
        if let Some(alerts) = weather_data.alerts.as_ref().filter(|a| a.has_alerts()) {
            tracing::info!(
                "[notify-ui] lightweight poll scheduling alert processing for {} active alert(s)",
                alerts.active(now).len()
            );
        }
        let dispatch = self.alerts.on_event_poll(weather_data, now);
        self.deliver_alerts(sinks, dispatch);
    }

    /// `_check_daily_climate_notification`, after Forecaster Notes loads a
    /// report: unlike the refresh-time check, no Event Center line and no
    /// click action.
    pub(crate) fn daily_climate_from_dialog(
        &mut self,
        sinks: &mut dyn Sinks,
        product: &TextProduct,
        settings: &AppSettings,
        location_name: &str,
        now: DateTime<Utc>,
    ) {
        if !settings.notify_daily_climate_report_update {
            return;
        }
        let Some(event) =
            self.events
                .check_daily_climate_report(Some(product), settings, location_name, now)
        else {
            return;
        };
        let toast = Toast {
            title: event.title,
            message: event.message,
            timeout: EVENT_TOAST_TIMEOUT_SECONDS,
            sound_event: Some(event.sound_event),
            sound_candidates: None,
            play_sound: settings.sound_enabled,
            activation: None,
        };
        self.send(sinks, &toast);
    }
}

/// `play_data_updated_sound` / `play_fetch_error_sound`: the window reads
/// the live settings, not the notifier's.
fn window_sound(sinks: &mut dyn Sinks, settings: &AppSettings, event: &str) {
    if settings.sound_enabled && !sound::is_sound_event_muted(event, &settings.muted_sound_events) {
        sinks.sound(SoundCue::Event {
            pack: settings.sound_pack.clone(),
            event: event.into(),
        });
    }
}

// ---------------------------------------------------------------------------
// The app's side
// ---------------------------------------------------------------------------

thread_local! {
    static NOTIFICATIONS: RefCell<Option<Notifications>> = const { RefCell::new(None) };
}

/// What the flow reads from the app state, copied out so no borrow is held
/// while the sinks run (the radio reads the state).
struct AppContext {
    settings: AppSettings,
    location: Option<Location>,
    products: Arc<ForecastProductService>,
    state_root: PathBuf,
}

fn app_context() -> Option<AppContext> {
    let state = with_state()?;
    let st = state.borrow();
    Some(AppContext {
        settings: st.config.settings.clone(),
        location: st.config.current_location.clone(),
        products: st.products.clone(),
        // Sample-data runs keep their alert history out of the user's.
        state_root: if st.offline {
            std::env::temp_dir().join("accessiweather-offline-state")
        } else {
            st.paths.config_dir.clone()
        },
    })
}

/// Run `f` on the app's [`Notifications`], built on first use.
fn with_notifications<R>(app: &AppContext, f: impl FnOnce(&mut Notifications) -> R) -> R {
    NOTIFICATIONS.with(|n| {
        let mut n = n.borrow_mut();
        let n = n.get_or_insert_with(|| {
            Notifications::new(
                RuntimeState::open(&app.state_root),
                &app.settings,
                Some(aw_audio::player().soundpacks_dir().to_path_buf()),
                Utc::now(),
            )
        });
        f(n)
    })
}

/// The text products the refresh pre-warmed for the current location
/// (`_check_hwo_from_cache`, `_check_sps_from_cache`,
/// `_check_daily_climate_from_cache`).
#[derive(Default)]
struct CachedTextProducts {
    hwo: Option<ProductResult>,
    sps: Option<Vec<TextProduct>>,
    daily_climate: Option<TextProduct>,
}

impl CachedTextProducts {
    fn peek(service: &ForecastProductService, location: Option<&Location>) -> Self {
        let Some(location) = location else {
            return Self::default();
        };
        let cwa = location.cwa_office.as_deref().filter(|c| !c.is_empty());
        Self {
            hwo: cwa.and_then(|c| service.peek("HWO", c)),
            sps: cwa
                .and_then(|c| service.peek("SPS", c))
                .map(ProductResult::into_products),
            daily_climate: ForecastProductService::daily_climate_station_candidates(location)
                .iter()
                .find_map(|station| service.peek_daily_climate_report(station)),
        }
    }

    fn as_cached(&self) -> CachedProducts<'_> {
        CachedProducts {
            hwo: self.hwo.as_ref().and_then(ProductResult::first),
            sps: self.sps.as_deref(),
            daily_climate: self.daily_climate.as_ref(),
        }
    }
}

/// Delivers to the desktop: toasts through the app notifier, sounds through
/// the audio layer, dialogs after the current event, the radio auto-tuner
/// and the main window's Event Center.
struct AppSinks;

impl Sinks for AppSinks {
    fn toast(&mut self, toast: &Toast) {
        if !crate::lifecycle::with_notifier(|n| n.send(toast)) {
            tracing::warn!(
                "[notify] notifier.send_notification returned False: {:?}",
                toast.title
            );
        }
    }

    fn sound(&mut self, cue: SoundCue) {
        let player = aw_audio::player();
        match cue {
            SoundCue::Event { pack, event } => player.play_event::<&str>(&pack, &event, &[]),
            SoundCue::Candidates { pack, keys } => {
                player.play_candidates::<&str>(&keys, &pack, None, &[])
            }
        }
    }

    fn popup(&mut self, popup: Popup) {
        // `wx.CallAfter`: the dialogs are modal.
        post_to_ui(move || match popup {
            Popup::Details(alert) => super::show_alert_details(&alert),
            Popup::Summary(alerts) => super::show_alerts_summary(&alerts),
        });
    }

    fn auto_tune(&mut self, alerts: &[WeatherAlert]) {
        if let Some(tuner) = crate::radio::auto_tuner() {
            tuner.tune_for_alerts(alerts);
        }
    }

    fn event_center(&mut self, entry: &EventCenterEntry) {
        mw::append_event_center_entry(&entry.text, Some(&entry.category));
    }
}

/// Called on the UI thread after the main window shows new data and after
/// every lightweight event poll.
pub(crate) fn weather_updated(update: WeatherUpdate<'_>) {
    let Some(app) = app_context() else { return };
    match update {
        WeatherUpdate::Displayed {
            weather_data,
            location_name,
            play_refresh_sound,
        } => {
            tracing::debug!("Weather shown for {location_name}");
            let products = CachedTextProducts::peek(&app.products, app.location.as_ref());
            with_notifications(&app, |n| {
                n.displayed(
                    &mut AppSinks,
                    weather_data,
                    &app.settings,
                    app.location.as_ref(),
                    products.as_cached(),
                    play_refresh_sound,
                    Local::now().fixed_offset(),
                )
            });
        }
        WeatherUpdate::EventPoll { weather_data } => {
            with_notifications(&app, |n| {
                n.event_poll(&mut AppSinks, weather_data, Utc::now())
            });
        }
    }
}

/// `_on_weather_error`'s `fetch_error` sound.
pub(crate) fn on_fetch_error() {
    if let Some(app) = app_context() {
        window_sound(&mut AppSinks, &app.settings, "fetch_error");
    }
}

/// Forecaster Notes loaded `product` as the daily climate report for
/// `location_name` (any thread).
pub(crate) fn on_daily_climate_report_loaded(product: TextProduct, location_name: String) {
    post_to_ui(move || {
        let Some(app) = app_context() else { return };
        with_notifications(&app, |n| {
            n.daily_climate_from_dialog(
                &mut AppSinks,
                &product,
                &app.settings,
                &location_name,
                Utc::now(),
            )
        });
    });
}

/// `refresh_runtime_settings`: the notifier's sound pack and mutes.
pub(crate) fn refresh_notifier_settings() {
    if let Some(app) = app_context() {
        with_notifications(&app, |n| n.refresh_notifier_settings(&app.settings));
    }
}

/// `refresh_runtime_settings`: the alert thresholds, cooldowns and popups.
pub(crate) fn refresh_alert_notification_settings() {
    if let Some(app) = app_context() {
        with_notifications(&app, |n| n.refresh_alert_settings(&app.settings));
    }
}

#[cfg(test)]
mod tests {
    //! Replays `rust/tools/golden/notifywire.py`: the Python main-window
    //! glue over sequences of refreshes, polls, errors, settings saves and
    //! a restart, recording every toast, sound, popup, auto-tune and Event
    //! Center line.

    use super::*;
    use serde_json::{json, Value};

    #[derive(Default)]
    struct Recorded {
        toasts: Vec<Value>,
        sounds: Vec<Value>,
        popups: Vec<Value>,
        radio: Vec<Value>,
        event_center: Vec<Value>,
    }

    fn ids(alerts: &[WeatherAlert]) -> Vec<String> {
        alerts.iter().map(WeatherAlert::unique_id).collect()
    }

    impl Sinks for Recorded {
        fn toast(&mut self, t: &Toast) {
            self.toasts.push(json!({
                "title": t.title,
                "message": t.message,
                "timeout": t.timeout,
                "sound_event": t.sound_event,
                "sound_candidates": t.sound_candidates,
                "play_sound": t.play_sound,
                "activation_arguments": t.activation_arguments(),
            }));
        }

        fn sound(&mut self, cue: SoundCue) {
            self.sounds.push(match cue {
                SoundCue::Event { pack, event } => json!({"event": event, "pack": pack}),
                SoundCue::Candidates { pack, keys } => json!({"candidates": keys, "pack": pack}),
            });
        }

        fn popup(&mut self, popup: Popup) {
            self.popups.push(match popup {
                Popup::Details(a) => json!({"details": a.unique_id()}),
                Popup::Summary(a) => json!({"summary": ids(&a)}),
            });
        }

        fn auto_tune(&mut self, alerts: &[WeatherAlert]) {
            self.radio.push(json!(ids(alerts)));
        }

        fn event_center(&mut self, e: &EventCenterEntry) {
            self.event_center
                .push(json!({"category": e.category, "text": e.text}));
        }
    }

    fn from<T: serde::de::DeserializeOwned>(v: &Value) -> T {
        serde_json::from_value(v.clone()).unwrap_or_else(|e| panic!("{e}: {v}"))
    }

    fn time(v: &Value) -> DateTime<FixedOffset> {
        DateTime::parse_from_rfc3339(v.as_str().unwrap()).unwrap()
    }

    /// The cache `_pre_warm_products_for_location` left for this step.
    fn products(step: &Value) -> CachedTextProducts {
        let one = |v: &Value| (!v.is_null()).then(|| from::<TextProduct>(v));
        let stations = step["cli_stations"].as_array().cloned().unwrap_or_default();
        CachedTextProducts {
            hwo: step.get("hwo").map(|v| ProductResult::One(one(v))),
            sps: step.get("sps").map(from),
            daily_climate: stations
                .iter()
                .find_map(|s| one(&step["cli_cache"][s.as_str().unwrap()])),
        }
    }

    #[test]
    fn notification_sequences_match_python() {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../testdata/golden/notifywire/sequences.json");
        let scenarios: Value =
            serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        for sc in scenarios.as_array().unwrap() {
            let dir = tempfile::tempdir().unwrap();
            let mut settings: AppSettings = from(&sc["settings"]);
            let home: Location = from(&sc["location"]);
            let steps = sc["steps"].as_array().unwrap();
            let open = |settings: &AppSettings, now: &Value| {
                Notifications::new(
                    RuntimeState::open(dir.path()),
                    settings,
                    None,
                    time(now).with_timezone(&Utc),
                )
            };
            let mut n = open(&settings, &steps[0]["now"]);
            let results = sc["results"].as_array().unwrap();
            assert_eq!(results.len(), steps.len());
            for (i, (step, expected)) in steps.iter().zip(results).enumerate() {
                let now = time(&step["now"]).with_timezone(&Utc);
                let mut rec = Recorded::default();
                match step["kind"].as_str().unwrap() {
                    "restart" => n = open(&settings, &step["now"]),
                    "settings" => {
                        settings = from(&step["settings"]);
                        n.refresh_notifier_settings(&settings);
                        n.refresh_alert_settings(&settings);
                    }
                    "displayed" => {
                        let location: Option<Location> = from(&step["location"]);
                        let cached = products(step);
                        n.displayed(
                            &mut rec,
                            &from(&step["weather"]),
                            &settings,
                            location.as_ref(),
                            cached.as_cached(),
                            step["play_refresh_sound"].as_bool().unwrap(),
                            time(&expected["local_now"]),
                        );
                    }
                    "poll" => n.event_poll(&mut rec, &from(&step["weather"]), now),
                    "error" => window_sound(&mut rec, &settings, "fetch_error"),
                    "climate_dialog" => n.daily_climate_from_dialog(
                        &mut rec,
                        &from(&step["product"]),
                        &settings,
                        &home.name,
                        now,
                    ),
                    other => panic!("unknown step kind {other}"),
                }
                let ctx = format!("{} step {i} ({})", sc["name"], step["kind"]);
                for (key, got) in [
                    ("toasts", rec.toasts),
                    ("sounds", rec.sounds),
                    ("popups", rec.popups),
                    ("radio", rec.radio),
                    ("event_center", rec.event_center),
                ] {
                    assert_eq!(Value::Array(got), expected[key], "{ctx}: {key}");
                }
            }
        }
    }
}
