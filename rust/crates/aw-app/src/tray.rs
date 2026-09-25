//! System tray icon (`ui/system_tray.py`) and its tooltip
//! (`AppLifecycleMixin.update_tray_tooltip`,
//! `MainWindowDisplayMixin._get_all_locations_tray_data`).
//!
//! The icon is Python's `resources/app.ico` at 16, 24, 32 and 48 px as raw
//! RGBA (`ui/tray_<size>.rgba`, extracted with Pillow), so wx picks the size
//! the display scaling asks for.
//!
//! Menu commands run one event-loop turn later: wxDragon deletes the tray
//! icon immediately, and "Quit" would otherwise delete it while its popup
//! menu is still on the stack.

use std::cell::{Cell, RefCell};

use aw_core::display::tray::TaskbarIconUpdater;
use aw_core::model::WeatherData;
use aw_core::settings::AppSettings;
use aw_core::Location;
use chrono::{DateTime, Utc};
use wxdragon::prelude::*;

use crate::app::{post_to_ui, with_state};
use crate::{lifecycle, ui};

const DEFAULT_TOOLTIP: &str = "AccessiWeather";
const SEVERITY_ORDER: [&str; 5] = ["Extreme", "Severe", "Moderate", "Minor", "Unknown"];

const ID_SHOW: Id = ID_HIGHEST + 101;
const ID_DEBUG_DISCUSSION: Id = ID_HIGHEST + 102;
const ID_DEBUG_ALERT: Id = ID_HIGHEST + 103;
const ID_DEBUG_DIAGNOSTICS: Id = ID_HIGHEST + 104;

const ICON_SIZES: [(u32, &[u8]); 4] = [
    (16, include_bytes!("../ui/tray_16.rgba")),
    (24, include_bytes!("../ui/tray_24.rgba")),
    (32, include_bytes!("../ui/tray_32.rgba")),
    (48, include_bytes!("../ui/tray_48.rgba")),
];

struct Tray {
    icon: TaskBarIcon,
    bundle: BitmapBundle,
}

thread_local! {
    /// Leaked so handlers can hold it without a borrow; `destroy` takes it.
    static TRAY: Cell<Option<&'static Tray>> = const { Cell::new(None) };
    static TOOLTIP: RefCell<String> = RefCell::new(DEFAULT_TOOLTIP.into());
    static UPDATER: RefCell<Option<TaskbarIconUpdater>> = const { RefCell::new(None) };
}

fn tray() -> Option<&'static Tray> {
    TRAY.with(Cell::get)
}

/// Whether the tray icon is up (`app.tray_icon is not None`).
pub(crate) fn exists() -> bool {
    tray().is_some()
}

fn icon_bundle() -> BitmapBundle {
    let bitmaps: Vec<Bitmap> = ICON_SIZES
        .iter()
        .filter_map(|(size, rgba)| Bitmap::from_rgba(rgba, *size, *size))
        .collect();
    BitmapBundle::from_bitmaps(&bitmaps)
}

/// `_initialize_tray_icon` / `SystemTrayIcon.__init__`.
pub(crate) fn initialize(debug_mode: bool) {
    let icon = TaskBarIcon::builder().build();
    let bundle = icon_bundle();
    if !icon.set_icon_bundle(&bundle, DEFAULT_TOOLTIP) {
        // Without a visible icon nothing could bring a hidden window back,
        // so the app runs as if it had no tray.
        tracing::warn!("Failed to set system tray icon");
        icon.destroy();
        return;
    }
    tracing::debug!("System tray icon set successfully");
    icon.bind_internal(EventType::TASKBAR_LEFT_DOWN, |_| show_main_window());
    icon.bind_internal(EventType::TASKBAR_LEFT_DCLICK, |_| show_main_window());
    icon.bind_internal(EventType::TASKBAR_RIGHT_DOWN, move |_| {
        popup_menu(debug_mode)
    });
    icon.on_menu(|e| {
        let id = e.get_id();
        post_to_ui(move || on_menu(id));
    });
    TOOLTIP.with(|t| *t.borrow_mut() = DEFAULT_TOOLTIP.into());
    TRAY.with(|t| t.set(Some(Box::leak(Box::new(Tray { icon, bundle })))));
    tracing::info!("System tray icon initialized");
}

/// Remove the icon (`RemoveIcon` + `Destroy` in `request_exit`).
pub(crate) fn destroy() {
    if let Some(tray) = TRAY.with(|t| t.take()) {
        tray.icon.remove_icon();
        tray.icon.destroy();
    }
}

/// `_create_popup_menu`.
fn popup_menu(debug_mode: bool) {
    let Some(tray) = tray() else { return };
    let mut menu = Menu::builder()
        .append_item(ID_SHOW, "&Show AccessiWeather", "")
        .build();
    if debug_mode {
        menu.append_separator();
        let debug = Menu::builder()
            .append_item(ID_DEBUG_DISCUSSION, "Test: &Discussion Updated", "")
            .append_item(ID_DEBUG_ALERT, "Test: &Alert Notification...", "")
            .append_separator()
            .append_item(ID_DEBUG_DIAGNOSTICS, "Run Notification &Diagnostics", "")
            .build();
        menu.append_submenu(debug, "&Debug", "");
    }
    menu.append_separator();
    menu.append(ID_EXIT, "&Quit", "", ItemKind::Normal);
    tray.icon.popup_menu(&mut menu);
}

fn on_menu(id: Id) {
    match id {
        ID_SHOW => show_main_window(),
        ID_DEBUG_DISCUSSION => ui::on_test_discussion_notification(),
        ID_DEBUG_ALERT => ui::on_test_alert_notification(),
        ID_DEBUG_DIAGNOSTICS => run_notification_diagnostics(),
        ID_EXIT => ui::request_exit(),
        _ => {}
    }
}

/// `_on_test_notifications_menu`: the tray's own rendering of the results.
fn run_notification_diagnostics() {
    let Some(state) = with_state() else { return };
    let (settings, location) = {
        let st = state.borrow();
        (
            st.config.settings.clone(),
            st.config.current_location.as_ref().map(|l| l.name.clone()),
        )
    };
    let results = aw_notify::debug::run_notification_diagnostics(
        &settings,
        location.as_deref(),
        |toast| aw_notify::Notifier::new("AccessiWeather Debug Test").send(toast),
        chrono::Local::now().fixed_offset(),
    );
    if let Some(frame) = ui::main_frame() {
        ui::message_box(
            &frame,
            &results.tray_report(),
            "Notification Test Results",
            MessageDialogStyle::OK | MessageDialogStyle::IconInformation,
        );
    }
}

/// `SystemTrayIcon.show_main_window`: show, restore and bring to the front.
pub(crate) fn show_main_window() {
    let Some(frame) = ui::main_frame() else {
        return;
    };
    lifecycle::show_frame(&frame);
    frame.iconize(false);
    #[cfg(windows)]
    lifecycle::win32::restore_to_foreground(frame.get_handle(), true);
    #[cfg(target_os = "macos")]
    frame.request_user_attention(UserAttentionFlag::Info);
    #[cfg(not(any(windows, target_os = "macos")))]
    {
        frame.raise();
        frame.set_focus();
    }
    tracing::debug!("Main window restored from tray");
}

/// `SystemTrayIcon.hide_main_window`: hide to the tray, whatever the
/// minimize-to-tray setting says.
pub(crate) fn hide_main_window() {
    lifecycle::minimize_to_tray();
}

/// `get_tooltip_text`.
pub(crate) fn tooltip_text() -> String {
    TOOLTIP.with(|t| t.borrow().clone())
}

/// `announce_tooltip`: spoken through the status bar.
pub(crate) fn announce_tooltip() {
    ui::set_status(&format!("Tray info: {}", tooltip_text()));
}

/// `update_tooltip`.
pub(crate) fn update_tooltip(text: &str) {
    let text = if text.is_empty() {
        DEFAULT_TOOLTIP
    } else {
        text
    };
    TOOLTIP.with(|t| *t.borrow_mut() = text.to_string());
    if let Some(tray) = tray() {
        tray.icon.set_icon_bundle(&tray.bundle, text);
        tracing::debug!("Tray tooltip updated: {text}");
    }
}

/// `_initialize_taskbar_updater`.
pub(crate) fn init_updater(settings: &AppSettings) {
    UPDATER.with(|u| *u.borrow_mut() = Some(TaskbarIconUpdater::from_settings(settings)));
    tracing::debug!("Taskbar icon updater initialized");
}

/// `taskbar_icon_updater.update_settings` from `refresh_runtime_settings`,
/// which (as in Python) leaves `round_values` as it was at startup.
pub(crate) fn refresh_updater(settings: &AppSettings) {
    UPDATER.with(|u| {
        if let Some(u) = u.borrow_mut().as_mut() {
            let round_values = u.round_values;
            *u = TaskbarIconUpdater::from_settings(settings);
            u.round_values = round_values;
        }
    });
}

/// `update_tray_tooltip`: the formatted tooltip, or "AccessiWeather".
pub(crate) fn update_tray_tooltip(weather_data: Option<&WeatherData>, location_name: Option<&str>) {
    if !exists() {
        return;
    }
    let tooltip = UPDATER.with(|u| {
        u.borrow()
            .as_ref()
            .map(|u| u.format_tooltip(weather_data, location_name, Utc::now()))
    });
    if let Some(tooltip) = tooltip {
        update_tooltip(&tooltip);
    }
}

/// After a single-location display update (`_on_weather_data_received`).
pub(crate) fn update_for_current_location(weather_data: &WeatherData) {
    let name = with_state()
        .and_then(|s| {
            s.borrow()
                .config
                .current_location
                .as_ref()
                .map(|l| l.name.clone())
        })
        .unwrap_or_else(|| "Unknown".into());
    update_tray_tooltip(Some(weather_data), Some(&name));
}

/// In All Locations (`_show_all_locations_summary`): the location with the
/// most severe alert.
pub(crate) fn update_for_all_locations() {
    let Some(state) = with_state() else { return };
    let (locations, client) = {
        let st = state.borrow();
        (st.config.locations.clone(), st.client.clone())
    };
    let last = ui::window_state(|s| s.last_single_location_name.clone());
    let picked = all_locations_tray_data(
        &locations,
        |l| client.get_cached_weather(l),
        last.as_deref(),
        Utc::now(),
    );
    update_tray_tooltip(
        picked.as_ref().map(|(d, _)| d),
        picked.as_ref().map(|(_, n)| n.as_str()),
    );
}

/// `_get_all_locations_tray_data`: the location with the most severe active
/// alert (Extreme > Severe > Moderate > Minor > Unknown, first wins a tie),
/// else the last single location viewed, else the first with cached data.
pub(crate) fn all_locations_tray_data(
    locations: &[Location],
    cached_weather: impl Fn(&Location) -> Option<WeatherData>,
    last_single_location_name: Option<&str>,
    now: DateTime<Utc>,
) -> Option<(WeatherData, String)> {
    let mut best: Option<(WeatherData, String)> = None;
    let mut best_rank = SEVERITY_ORDER.len();
    let mut first_with_data: Option<(WeatherData, String)> = None;
    for location in locations {
        let Some(data) = cached_weather(location).filter(WeatherData::has_any_data) else {
            continue;
        };
        if first_with_data.is_none() {
            first_with_data = Some((data.clone(), location.name.clone()));
        }
        let ranks: Vec<usize> = data
            .alerts
            .as_ref()
            .map(|a| a.active(now))
            .unwrap_or_default()
            .iter()
            .map(|alert| {
                SEVERITY_ORDER
                    .iter()
                    .position(|s| *s == alert.severity)
                    .unwrap_or(SEVERITY_ORDER.len() - 1)
            })
            .collect();
        if let Some(rank) = ranks.into_iter().min().filter(|r| *r < best_rank) {
            best_rank = rank;
            best = Some((data, location.name.clone()));
        }
    }
    if best.is_some() {
        return best;
    }
    if let Some(name) = last_single_location_name.filter(|n| !n.is_empty()) {
        if let Some(location) = locations.iter().find(|l| l.name == name) {
            if let Some(data) = cached_weather(location).filter(WeatherData::has_any_data) {
                return Some((data, name.to_string()));
            }
        }
    }
    first_with_data
}

#[cfg(test)]
mod tests {
    use super::*;
    use aw_core::model::{CurrentConditions, WeatherAlert, WeatherAlerts};
    use std::collections::HashMap;

    fn data(alerts: &[(&str, Option<&str>)]) -> WeatherData {
        WeatherData {
            current: Some(CurrentConditions {
                temperature_f: Some(70.0),
                ..Default::default()
            }),
            alerts: Some(WeatherAlerts {
                alerts: alerts
                    .iter()
                    .map(|(severity, expires)| {
                        let mut a = WeatherAlert::new("t", "d");
                        a.severity = severity.to_string();
                        a.expires = expires.map(|e| e.parse().unwrap());
                        a
                    })
                    .collect(),
            }),
            ..Default::default()
        }
    }

    fn pick(
        cache: &HashMap<&str, WeatherData>,
        names: &[&str],
        last: Option<&str>,
    ) -> Option<String> {
        let locations: Vec<Location> = names
            .iter()
            .map(|n| Location::new(*n, 40.0, -75.0))
            .collect();
        let now = "2026-09-25T12:00:00Z".parse().unwrap();
        all_locations_tray_data(
            &locations,
            |l| cache.get(l.name.as_str()).cloned(),
            last,
            now,
        )
        .map(|(_, name)| name)
    }

    #[test]
    fn most_severe_active_alert_wins() {
        let cache = HashMap::from([
            ("A", data(&[("Moderate", None)])),
            ("B", data(&[("Minor", None), ("Severe", None)])),
            // Expired, so it does not count.
            ("C", data(&[("Extreme", Some("2026-09-25T11:00:00Z"))])),
            ("D", data(&[("Severe", None)])),
        ]);
        assert_eq!(
            pick(&cache, &["A", "B", "C", "D"], None).as_deref(),
            Some("B")
        );
    }

    #[test]
    fn unknown_severities_rank_last_but_still_beat_no_alerts() {
        let cache = HashMap::from([("A", data(&[])), ("B", data(&[("Bogus", None)]))]);
        assert_eq!(pick(&cache, &["A", "B"], Some("A")).as_deref(), Some("B"));
    }

    #[test]
    fn without_alerts_the_last_viewed_location_then_the_first_with_data() {
        let cache = HashMap::from([("B", data(&[])), ("C", data(&[]))]);
        assert_eq!(
            pick(&cache, &["A", "B", "C"], Some("C")).as_deref(),
            Some("C")
        );
        assert_eq!(
            pick(&cache, &["A", "B", "C"], Some("A")).as_deref(),
            Some("B")
        );
        assert_eq!(pick(&cache, &["A", "B", "C"], None).as_deref(), Some("B"));
        assert_eq!(pick(&HashMap::new(), &["A"], None), None);
    }
}
