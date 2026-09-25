//! Weather alert presentation.
//!
//! Port of `display/presentation/alerts.py`.

use std::collections::HashMap;

use chrono::{DateTime, Utc};
use chrono_tz::Tz;

use crate::display::models::{AlertPresentation, AlertsPresentation};
use crate::display::pyfmt::{truncate, wrap_text};
use crate::display::time::{format_display_datetime, PyDateTime};
use crate::model::{AlertLifecycleDiff, WeatherAlert, WeatherAlerts};
use crate::settings::AppSettings;

/// `AlertLifecycleDiff.has_changes`.
pub fn lifecycle_has_changes(diff: &AlertLifecycleDiff) -> bool {
    !(diff.new_alerts.is_empty()
        && diff.updated_alerts.is_empty()
        && diff.escalated_alerts.is_empty()
        && diff.extended_alerts.is_empty()
        && diff.cancelled_alerts.is_empty())
}

/// `WeatherAlerts.get_active_alerts`: no expiry, or expiring after `now`.
pub fn active_alerts(alerts: &WeatherAlerts, now: DateTime<Utc>) -> Vec<&WeatherAlert> {
    alerts
        .alerts
        .iter()
        .filter(|a| a.expires.is_none_or(|e| e > now))
        .collect()
}

fn is_pirate_weather_alert(alert: &WeatherAlert) -> bool {
    alert
        .source
        .as_deref()
        .unwrap_or("")
        .trim()
        .to_lowercase()
        .contains("pirateweather")
}

/// `build_alerts`. `lifecycle_states` maps `unique_id()` to a label such as
/// "Extended" that is appended to the alert's header line.
pub fn build_alerts(
    alerts: &WeatherAlerts,
    location_name: &str,
    settings: &AppSettings,
    location_zone: Option<Tz>,
    lifecycle_diff: Option<&AlertLifecycleDiff>,
    lifecycle_states: Option<&HashMap<String, String>>,
    now: DateTime<Utc>,
) -> AlertsPresentation {
    let title = format!("Weather alerts for {location_name}");
    let active = active_alerts(alerts, now);
    if active.is_empty() {
        return AlertsPresentation {
            fallback_text: format!("{title}:\nNo active weather alerts."),
            title,
            ..Default::default()
        };
    }

    let mut presentations = Vec::new();
    let mut fallback_lines = vec![format!("{title}:")];
    for (idx, alert) in active.into_iter().enumerate() {
        let label = lifecycle_states
            .filter(|m| !m.is_empty())
            .and_then(|m| m.get(&alert.unique_id()))
            .map(String::as_str);
        let p = build_single_alert(alert, idx + 1, settings, location_zone, label);
        fallback_lines.push(p.fallback_text.clone());
        presentations.push(p);
    }
    let mut fallback_text = fallback_lines.join("\n\n");

    let mut change_summary = None;
    if let Some(diff) = lifecycle_diff.filter(|d| lifecycle_has_changes(d)) {
        change_summary = Some(diff.summary.clone());
        fallback_text = format!("Alert changes: {}\n{fallback_text}", diff.summary);
    }

    AlertsPresentation {
        title,
        alerts: presentations,
        fallback_text,
        change_summary,
    }
}

/// `build_single_alert`.
pub fn build_single_alert(
    alert: &WeatherAlert,
    index: usize,
    settings: &AppSettings,
    location_zone: Option<Tz>,
    lifecycle_label: Option<&str>,
) -> AlertPresentation {
    let severity = (alert.severity != "Unknown").then(|| alert.severity.clone());
    let urgency = (alert.urgency != "Unknown").then(|| alert.urgency.clone());
    let areas: Vec<&String> = alert.areas.iter().take(3).collect();
    let regional = is_pirate_weather_alert(alert);

    let expires = alert.expires.map(|e| {
        format_display_datetime(
            &PyDateTime::aware(e, location_zone),
            &settings.time_display_mode,
            settings.time_format_12hour,
            settings.show_timezone_suffix,
            "%m/%d",
        )
    });
    let description = Some(alert.description.as_str())
        .filter(|d| !d.is_empty())
        .map(|d| truncate(d, 200));
    let instruction = alert
        .instruction
        .as_deref()
        .filter(|i| !i.is_empty())
        .map(|i| truncate(i, 150));

    let mut header = if alert.title.is_empty() {
        format!("Alert {index}")
    } else {
        format!("Alert {index}: {}", alert.title)
    };
    if let Some(label) = lifecycle_label.filter(|l| !l.is_empty()) {
        header = format!("{header} ({label})");
    }
    let mut parts = vec![header];
    let nonempty = |s: &Option<String>| s.clone().filter(|s| !s.is_empty());
    let mut bits = Vec::new();
    if let Some(s) = nonempty(&severity) {
        bits.push(format!("Severity: {s}"));
    }
    if let Some(u) = nonempty(&urgency) {
        bits.push(format!("Urgency: {u}"));
    }
    if !bits.is_empty() {
        parts.push(format!("  {}", bits.join(", ")));
    }
    let event = alert.event.as_deref().filter(|e| !e.is_empty());
    if let Some(e) = event {
        parts.push(format!("  Event: {e}"));
    }
    if !areas.is_empty() {
        let remaining = alert.areas.len() - areas.len();
        let mut text = areas
            .iter()
            .map(|a| a.as_str())
            .collect::<Vec<_>>()
            .join(", ");
        if remaining > 0 {
            text.push_str(&format!(" and {remaining} more"));
        }
        let label = if regional { "Regions" } else { "Areas" };
        parts.push(format!("  {label}: {text}"));
    }
    if regional {
        parts.push(
            "  Coverage: Regional alert from Pirate Weather/WMO; may not match your exact county or zone."
                .into(),
        );
    }
    if let Some(e) = &expires {
        parts.push(format!("  Expires: {e}"));
    }
    if let Some(d) = &description {
        parts.push(format!("  Description: {}", wrap_text(d, 80)));
    }
    if let Some(i) = &instruction {
        parts.push(format!("  Instructions: {}", wrap_text(i, 80)));
    }

    let title = if !alert.title.is_empty() {
        alert.title.clone()
    } else {
        event
            .map(str::to_string)
            .unwrap_or_else(|| format!("Alert {index}"))
    };
    AlertPresentation {
        title,
        severity,
        urgency,
        event: alert.event.clone(),
        areas: alert.areas.clone(),
        expires,
        description,
        instructions: instruction,
        fallback_text: parts.join("\n"),
    }
}
