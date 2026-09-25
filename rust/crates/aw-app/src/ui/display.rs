//! Text the main window shows, kept free of wx so it can be golden-tested.
//! Ported from `ui/main_window_display.py`, `_update_title_for_location` in
//! `ui/main_window_ui.py` and the panel filling in `_on_weather_data_received`
//! (`ui/main_window_refresh.py`).

use std::collections::BTreeMap;

use aw_core::display::units::{format_temperature, resolve_temperature_unit_preference};
use aw_core::display::WeatherPresentation;
use aw_core::model::{WeatherAlert, WeatherData};
use aw_core::settings::AppSettings;
use aw_core::Location;
use chrono::{DateTime, NaiveTime, Utc};

/// The first dropdown entry: a cached summary of every saved location.
pub(crate) const ALL_LOCATIONS_SENTINEL: &str = "All Locations";

pub(crate) const NO_LOCATIONS_TEXT: &str =
    "No locations configured.\nUse the Add button or Ctrl+L to add a location.";

/// `_update_title_for_location`.
pub(crate) fn window_title(location_name: Option<&str>) -> String {
    match location_name {
        Some(name) if !name.is_empty() && name != ALL_LOCATIONS_SENTINEL => {
            format!("AccessiWeather \u{2014} {name}")
        }
        _ => "AccessiWeather".to_string(),
    }
}

/// `datetime.now().strftime("%I:%M %p").lstrip("0")`.
pub(crate) fn clock_12h(time: NaiveTime) -> String {
    time.format("%I:%M %p")
        .to_string()
        .trim_start_matches('0')
        .to_string()
}

/// `append_event_center_entry`: the line appended to Recent Events.
pub(crate) fn event_center_entry(
    text: &str,
    category: Option<&str>,
    now: NaiveTime,
) -> Option<String> {
    if text.is_empty() {
        return None;
    }
    let prefix = category
        .filter(|c| !c.is_empty())
        .map(|c| format!("{c}: "))
        .unwrap_or_default();
    Some(format!("[{}] {prefix}{text}\n", clock_12h(now)))
}

/// `_set_last_updated_status`.
pub(crate) fn last_updated_status(now: NaiveTime) -> String {
    format!("Last updated {}", clock_12h(now))
}

/// Python formats `alert.event` with an f-string, so a missing event reads "None".
fn event_text(alert: &WeatherAlert) -> &str {
    alert.event.as_deref().unwrap_or("None")
}

/// `_update_alerts`: "{event} ({severity})" plus an optional lifecycle label.
pub(crate) fn alert_list_items(
    active: &[&WeatherAlert],
    lifecycle_labels: &BTreeMap<String, String>,
) -> Vec<String> {
    active
        .iter()
        .map(|alert| {
            let item = format!("{} ({})", event_text(alert), alert.severity);
            match lifecycle_labels
                .get(&alert.unique_id())
                .filter(|l| !l.is_empty())
            {
                Some(label) => format!("{item} ({label})"),
                None => item,
            }
        })
        .collect()
}

/// `_update_all_locations_alerts`: each item names its location.
pub(crate) fn all_locations_alert_items(location_alerts: &[(String, WeatherAlert)]) -> Vec<String> {
    location_alerts
        .iter()
        .map(|(name, alert)| format!("{name}: {} ({})", event_text(alert), alert.severity))
        .collect()
}

/// `_show_all_locations_summary` for a non-empty location list: the summary
/// text and the (location name, alert) pairs behind the alerts list.
pub(crate) fn all_locations_summary(
    locations: &[Location],
    cached: impl Fn(&Location) -> Option<WeatherData>,
    settings: &AppSettings,
    now: DateTime<Utc>,
) -> (String, Vec<(String, WeatherAlert)>) {
    let mut lines = vec!["All Locations Summary".to_string(), String::new()];
    let mut location_alerts = Vec::new();
    for loc in locations {
        lines.push(format!("--- {} ---", loc.name));
        match cached(loc) {
            Some(data) if data.has_any_data() && data.current.is_some() => {
                let cc = data.current.as_ref().expect("checked above");
                let unit =
                    resolve_temperature_unit_preference(&settings.temperature_unit, Some(loc));
                // get_temperature_precision() is always 1.
                let precision = if settings.round_values { 0 } else { 1 };
                let temp = format_temperature(cc.temperature_f, unit, cc.temperature_c, precision);
                let condition = cc
                    .condition
                    .as_deref()
                    .filter(|c| !c.is_empty())
                    .unwrap_or("Unknown");
                lines.push(format!("  Temperature: {temp}"));
                lines.push(format!("  Condition: {condition}"));

                let active = data
                    .alerts
                    .as_ref()
                    .map(|a| a.active(now))
                    .unwrap_or_default();
                if active.is_empty() {
                    lines.push("  Active Alerts: None".to_string());
                } else {
                    lines.push(format!("  Active Alerts: {}", active.len()));
                    for alert in active {
                        lines.push(format!("    • {} ({})", event_text(alert), alert.severity));
                        location_alerts.push((loc.name.clone(), alert.clone()));
                    }
                }
                if data.stale {
                    lines.push("  (Cached — data may be outdated)".to_string());
                }
            }
            _ => lines.push(
                "  (No cached data — select this location to load current conditions)".to_string(),
            ),
        }
        lines.push(String::new());
    }
    (lines.join("\n"), location_alerts)
}

/// What `_on_weather_data_received` puts into each panel.
#[derive(Debug, PartialEq)]
pub(crate) struct PanelTexts {
    pub current: String,
    /// Second status bar field.
    pub stale_warning: String,
    pub daily: String,
    pub hourly: String,
    /// Logged to Recent Events under "Briefing".
    pub briefing: Option<String>,
}

pub(crate) fn panel_texts(presentation: &WeatherPresentation) -> PanelTexts {
    let mut current = match &presentation.current_conditions {
        Some(c) => c.fallback_text.clone(),
        None => "No current conditions available.".to_string(),
    };
    if let Some(summary) = presentation
        .source_attribution
        .as_ref()
        .map(|s| &s.summary_text)
        .filter(|s| !s.is_empty())
    {
        current.push_str(&format!("\n\n{summary}"));
    }
    let (daily, hourly, briefing) = match &presentation.forecast {
        Some(f) => {
            let daily = [
                f.daily_section_text.as_str(),
                f.marine_section_text.as_str(),
            ]
            .into_iter()
            .filter(|s| !s.is_empty())
            .collect::<Vec<_>>()
            .join("\n\n")
            .trim_end()
            .to_string();
            let hourly = if f.hourly_section_text.is_empty() {
                "No hourly forecast available.".to_string()
            } else {
                f.hourly_section_text.clone()
            };
            let briefing = f.mobility_briefing.clone().filter(|b| !b.is_empty());
            (daily, hourly, briefing)
        }
        None => (
            String::new(),
            "No hourly forecast available.".to_string(),
            None,
        ),
    };
    PanelTexts {
        current,
        stale_warning: presentation.status_messages.join(" "),
        daily: if daily.is_empty() {
            "No daily forecast available.".to_string()
        } else {
            daily
        },
        hourly,
        briefing,
    }
}

/// `get_visible_top_level_sections` labels, in focus order.
#[cfg(test)]
pub(crate) const SECTION_LABELS: [&str; 6] = [
    "Location",
    "Current conditions",
    "Hourly / near-term",
    "Daily forecast",
    "Alerts",
    "Event Center",
];

fn visible_section_count(event_center_visible: bool) -> usize {
    if event_center_visible {
        6
    } else {
        5
    }
}

/// `focus_section_by_number`: Ctrl+1..4 reach current, hourly, daily and
/// alerts; Ctrl+5 the Event Center when it is shown.
pub(crate) fn section_for_number(number: usize, event_center_visible: bool) -> Option<usize> {
    if number == 5 && !event_center_visible {
        return None;
    }
    let count = visible_section_count(event_center_visible);
    let index = if number == 5 { count - 1 } else { number };
    (index < count).then_some(index)
}

/// `cycle_section_focus` (F6): the next visible section, wrapping.
pub(crate) fn next_section(previous: Option<usize>, event_center_visible: bool) -> usize {
    let next = previous.map_or(0, |i| i + 1);
    if next >= visible_section_count(event_center_visible) {
        0
    } else {
        next
    }
}

/// Help menu label naming the update channel.
pub(crate) fn check_updates_label(channel: &str) -> String {
    format!("Check for &Updates ({})...", aw_core::py::title(channel))
}

/// `_on_about` message text; names the toolkit this edition is built with.
pub(crate) fn about_text(version: &str, portable: bool, config_path: &str) -> String {
    let mode = if portable { "Portable" } else { "Installed" };
    format!(
        "AccessiWeather v{version}\n\n\
         An accessible weather application with NOAA and Open-Meteo support.\n\n\
         Built with wxWidgets for screen reader compatibility.\n\n\
         Mode: {mode}\n\
         Config path: {config_path}\n\n\
         https://github.com/Orinks/AccessiWeather"
    )
}
