//! Alert toasts, ported from `alert_notification_system.py` and
//! `alert_notification_formatting.py`.

use std::path::PathBuf;

use aw_core::model::{AlertLifecycleDiff, WeatherAlert, WeatherAlerts, WeatherData};
use aw_core::settings::AppSettings;
use chrono::{DateTime, FixedOffset, Utc};

use crate::activation::ActivationRequest;
use crate::alert_manager::{
    AlertManager, AlertSettings, REASON_CONTENT_CHANGED, REASON_ESCALATION, REASON_EXTENDED,
    REASON_NEW_ALERT,
};
use crate::py;
use crate::sound;
use crate::Toast;

pub const MAX_NOTIFICATION_DESCRIPTION_LENGTH: usize = 100;
pub const MAX_DISPLAYED_AREAS: usize = 2;
/// Alert toasts stay up longer than other notifications.
pub const ALERT_TOAST_TIMEOUT_SECONDS: u32 = 15;
pub const CANCELLED_TOAST_TIMEOUT_SECONDS: u32 = 10;

/// `format_display_datetime` with the `"%b %d"` date format.
pub fn format_display_datetime(
    value: &DateTime<FixedOffset>,
    time_display_mode: &str,
    use_12hour: bool,
    show_timezone: bool,
) -> String {
    let fmt = |dt: &DateTime<FixedOffset>| {
        let time = if use_12hour {
            py::clock_12h(dt)
        } else {
            dt.format("%H:%M").to_string()
        };
        format!("{} {time}", dt.format("%b %d"))
    };
    let utc = value.with_timezone(&Utc).fixed_offset();
    match time_display_mode {
        "utc" => {
            let s = fmt(&utc);
            if show_timezone {
                format!("{s} UTC")
            } else {
                s
            }
        }
        "both" => {
            let mut local = fmt(value);
            if show_timezone {
                local.push(' ');
                local.push_str(&py::fixed_tzname(value.offset()));
            }
            format!("{local} ({} UTC)", fmt(&utc))
        }
        _ => {
            let mut s = fmt(value);
            if show_timezone {
                s.push(' ');
                s.push_str(&py::fixed_tzname(value.offset()));
            }
            s
        }
    }
}

/// `format_accessible_message`: (title, body) for an alert toast.
pub fn format_accessible_message(
    alert: &WeatherAlert,
    reason: &str,
    include_areas: bool,
    include_expiration: bool,
    settings: Option<&AppSettings>,
) -> (String, String) {
    let severity = if alert.severity.is_empty() {
        "UNKNOWN".to_string()
    } else {
        alert.severity.to_uppercase()
    };
    let event = alert
        .event
        .as_deref()
        .filter(|e| !e.is_empty())
        .unwrap_or("Weather Alert");
    let title = match reason {
        REASON_ESCALATION => format!("ESCALATED {severity}: {event}"),
        REASON_CONTENT_CHANGED => format!("UPDATED {severity}: {event}"),
        "reminder" => format!("ACTIVE {severity}: {event}"),
        _ => format!("{severity} ALERT: {event}"),
    };

    let mut parts: Vec<String> = Vec::new();
    let urgency = alert.urgency.to_lowercase();
    if urgency == "immediate" || urgency == "expected" {
        parts.push(format!(
            "{}{} action may be required.",
            urgency[..1].to_uppercase(),
            &urgency[1..]
        ));
    }
    match alert
        .headline
        .as_deref()
        .filter(|h| !h.is_empty())
        .or(Some(alert.title.as_str()).filter(|t| !t.is_empty()))
    {
        Some(headline) => parts.push(headline.to_string()),
        None => parts.push(format!(
            "A {} weather alert has been issued.",
            severity.to_lowercase()
        )),
    }
    if !alert.description.is_empty() {
        let mut desc =
            py::truncate_chars(&alert.description, MAX_NOTIFICATION_DESCRIPTION_LENGTH).to_string();
        if alert.description.chars().count() > MAX_NOTIFICATION_DESCRIPTION_LENGTH {
            desc.push_str("...");
        }
        parts.push(desc);
    }
    if include_areas && !alert.areas.is_empty() {
        let mut text = alert
            .areas
            .iter()
            .take(MAX_DISPLAYED_AREAS)
            .cloned()
            .collect::<Vec<_>>()
            .join(", ");
        if alert.areas.len() > MAX_DISPLAYED_AREAS {
            text.push_str(&format!(
                " and {} more",
                alert.areas.len() - MAX_DISPLAYED_AREAS
            ));
        }
        parts.push(format!("Areas: {text}"));
    }
    if include_expiration {
        if let Some(expires) = &alert.expires {
            let (mode, h12, tz) = settings.map_or(("local", true, false), |s| {
                (
                    s.time_display_mode.as_str(),
                    s.time_format_12hour,
                    s.show_timezone_suffix,
                )
            });
            parts.push(format!(
                "Expires: {}",
                format_display_datetime(expires, mode, h12, tz)
            ));
        }
    }
    (title, parts.join("\n\n"))
}

/// Everything one `process_and_notify` batch asks the app to do.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct AlertDispatch {
    /// Most severe first; only the first plays a sound.
    pub toasts: Vec<Toast>,
    /// Non-empty only when `immediate_alert_details_popups` is on: open the
    /// alert dialog (one alert) or the summary dialog (several) without
    /// restoring the main window.
    pub popup_alerts: Vec<WeatherAlert>,
    /// Alerts that should start NOAA weather-radio auto-tune (new, initial
    /// issuances only; the radio layer applies its own settings).
    pub radio_auto_tune_alerts: Vec<WeatherAlert>,
}

/// `_is_initial_alert_message_type`.
fn is_initial_message_type(alert: &WeatherAlert) -> bool {
    alert
        .message_type
        .as_deref()
        .is_none_or(|m| matches!(m.trim().to_lowercase().as_str(), "" | "alert"))
}

/// `_should_auto_tune_for_alert_notification`. Python also accepts a
/// `severity_escalated` reason, which the alert manager never produces
/// (it says `escalation`), so escalations never auto-tune.
fn should_auto_tune(alert: &WeatherAlert, reason: &str) -> bool {
    reason == REASON_NEW_ALERT && is_initial_message_type(alert)
}

/// `AlertNotificationSystem`.
pub struct AlertNotificationSystem {
    pub manager: AlertManager,
    pub settings: AppSettings,
    /// Where sound packs live, to see whether the active pack wants specific
    /// alert sounds. `None` skips the `pack.json` check.
    pub soundpacks_dir: Option<PathBuf>,
}

impl AlertNotificationSystem {
    pub fn new(
        manager: AlertManager,
        settings: AppSettings,
        soundpacks_dir: Option<PathBuf>,
    ) -> Self {
        Self {
            manager,
            settings,
            soundpacks_dir,
        }
    }

    /// `update_settings` (plus the `.settings = settings` the app does first).
    pub fn update_settings(&mut self, settings: AppSettings) {
        self.manager
            .update_settings(AlertSettings::from_app_settings(&settings));
        self.settings = settings;
    }

    fn alert_toast(&self, alert: &WeatherAlert, reason: &str, play_sound: bool) -> Toast {
        let (title, message) =
            format_accessible_message(alert, reason, true, true, Some(&self.settings));
        let sound_candidates = play_sound.then(|| {
            sound::get_candidate_sound_events(
                alert,
                sound::should_use_specific_alert_sounds(
                    &self.settings,
                    self.soundpacks_dir.as_deref(),
                ),
                Some(reason),
            )
        });
        Toast {
            title,
            message,
            timeout: ALERT_TOAST_TIMEOUT_SECONDS,
            sound_event: None,
            sound_candidates,
            play_sound,
            activation: Some(ActivationRequest::alert_details(alert.unique_id())),
        }
    }

    /// `process_and_notify`: run the batch through the alert manager and
    /// build the toasts, most severe first with one sound for the batch.
    pub fn process_and_notify(
        &mut self,
        alerts: &WeatherAlerts,
        now: DateTime<Utc>,
    ) -> AlertDispatch {
        let mut batch = self.manager.process_alerts(alerts, now);
        if batch.is_empty() {
            return AlertDispatch::default();
        }
        // Stable sort, like Python's `sorted(..., reverse=True)`.
        batch.sort_by_key(|(a, _)| std::cmp::Reverse(a.severity_priority()));
        let popup_alerts = if self.settings.immediate_alert_details_popups {
            batch.iter().map(|(a, _)| a.clone()).collect()
        } else {
            Vec::new()
        };
        let radio_auto_tune_alerts = batch
            .iter()
            .filter(|(a, r)| should_auto_tune(a, r))
            .map(|(a, _)| a.clone())
            .collect();
        let toasts = batch
            .iter()
            .enumerate()
            .map(|(i, (alert, reason))| self.alert_toast(alert, reason, i == 0))
            .collect();
        AlertDispatch {
            toasts,
            popup_alerts,
            radio_auto_tune_alerts,
        }
    }

    /// `notify_lifecycle_changes`: updated and escalated alerts (with sound),
    /// extended alerts (silent, plain alert title) and cancellations
    /// (silent, no click action). New alerts are left to
    /// [`Self::process_and_notify`]. These bypass the alert manager's
    /// filters; only the master switch applies.
    pub fn notify_lifecycle_changes(&self, diff: &AlertLifecycleDiff) -> Vec<Toast> {
        if !has_changes(diff) || !self.manager.settings.notifications_enabled {
            return Vec::new();
        }
        let mut toasts = Vec::new();
        for (changes, reason, play_sound) in [
            (&diff.updated_alerts, REASON_CONTENT_CHANGED, true),
            (&diff.escalated_alerts, REASON_ESCALATION, true),
            (&diff.extended_alerts, REASON_EXTENDED, false),
        ] {
            for change in changes {
                if let Some(alert) = &change.alert {
                    toasts.push(self.alert_toast(alert, reason, play_sound));
                }
            }
        }
        for change in &diff.cancelled_alerts {
            let (title, message) = if change.title.is_empty() {
                (
                    "Alert Cancelled".to_string(),
                    "A weather alert has been cancelled.".to_string(),
                )
            } else {
                (
                    format!("CANCELLED: {}", change.title),
                    format!(
                        "The alert '{}' has been cancelled or expired.",
                        change.title
                    ),
                )
            };
            toasts.push(Toast {
                title,
                message,
                timeout: CANCELLED_TOAST_TIMEOUT_SECONDS,
                sound_event: None,
                sound_candidates: None,
                play_sound: false,
                activation: None,
            });
        }
        toasts
    }

    /// The lightweight 60-second event poll (`on_notification_event_data_received`):
    /// alert processing, then lifecycle toasts. Discussion and other events
    /// only run after full refreshes.
    pub fn on_event_poll(&mut self, data: &WeatherData, now: DateTime<Utc>) -> AlertDispatch {
        let mut dispatch = match &data.alerts {
            Some(alerts) if alerts.has_alerts() => self.process_and_notify(alerts, now),
            _ => AlertDispatch::default(),
        };
        if let Some(diff) = &data.alert_lifecycle_diff {
            dispatch.toasts.extend(self.notify_lifecycle_changes(diff));
        }
        dispatch
    }
}

/// `AlertLifecycleDiff.has_changes`.
pub fn has_changes(diff: &AlertLifecycleDiff) -> bool {
    !(diff.new_alerts.is_empty()
        && diff.updated_alerts.is_empty()
        && diff.escalated_alerts.is_empty()
        && diff.extended_alerts.is_empty()
        && diff.cancelled_alerts.is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::runtime_state::RuntimeState;
    use aw_core::model::{AlertChange, AlertChangeKind};

    fn now() -> DateTime<Utc> {
        "2026-09-25T16:00:00Z".parse().unwrap()
    }

    fn alert(id: &str, severity: &str, event: &str) -> WeatherAlert {
        let mut a = WeatherAlert::new(event, format!("{event} description."));
        a.id = Some(id.into());
        a.severity = severity.into();
        a.urgency = "Immediate".into();
        a.event = Some(event.into());
        a.headline = Some(format!("{event} in effect"));
        a.expires = Some(DateTime::parse_from_rfc3339("2026-09-25T15:30:00-04:00").unwrap());
        a.areas = vec!["A".into(), "B".into(), "C".into()];
        a
    }

    fn system(dir: &std::path::Path) -> AlertNotificationSystem {
        let settings = AppSettings::default();
        let manager = AlertManager::new(
            RuntimeState::open(dir),
            AlertSettings::from_app_settings(&settings),
            now(),
        );
        AlertNotificationSystem::new(manager, settings, None)
    }

    #[test]
    fn message_layout() {
        let (title, body) = format_accessible_message(
            &alert("x", "Severe", "Wind Advisory"),
            "new_alert",
            true,
            true,
            None,
        );
        assert_eq!(title, "SEVERE ALERT: Wind Advisory");
        assert_eq!(
            body,
            "Immediate action may be required.\n\nWind Advisory in effect\n\nWind Advisory description.\n\nAreas: A, B and 1 more\n\nExpires: Sep 25 3:30 PM"
        );
        let s = AppSettings {
            time_display_mode: "both".into(),
            show_timezone_suffix: true,
            ..AppSettings::default()
        };
        let (_, body) = format_accessible_message(
            &alert("x", "Severe", "Wind Advisory"),
            "escalation",
            false,
            true,
            Some(&s),
        );
        assert!(body.ends_with("Expires: Sep 25 3:30 PM UTC-04:00 (Sep 25 7:30 PM UTC)"));
    }

    #[test]
    fn batch_is_sorted_with_one_sound() {
        let dir = tempfile::tempdir().unwrap();
        let mut sys = system(dir.path());
        let alerts = WeatherAlerts {
            alerts: vec![
                alert("a", "Moderate", "Flood Watch"),
                alert("b", "Extreme", "Tornado Warning"),
                alert("c", "Severe", "Severe Thunderstorm Warning"),
            ],
        };
        let d = sys.process_and_notify(&alerts, now());
        let titles: Vec<_> = d.toasts.iter().map(|t| t.title.as_str()).collect();
        assert_eq!(
            titles,
            [
                "EXTREME ALERT: Tornado Warning",
                "SEVERE ALERT: Severe Thunderstorm Warning",
                "MODERATE ALERT: Flood Watch"
            ]
        );
        assert_eq!(d.toasts.iter().filter(|t| t.play_sound).count(), 1);
        assert_eq!(
            d.toasts[0].sound_candidates.as_deref().unwrap(),
            ["extreme", "alert", "notify"]
        );
        assert_eq!(
            d.toasts[0].activation,
            Some(ActivationRequest::alert_details("b"))
        );
        assert_eq!(d.radio_auto_tune_alerts.len(), 3);
        assert!(d.popup_alerts.is_empty());
    }

    #[test]
    fn lifecycle_toasts() {
        let dir = tempfile::tempdir().unwrap();
        let sys = system(dir.path());
        let change = |kind, a: Option<WeatherAlert>, title: &str| AlertChange {
            kind,
            alert: a,
            alert_id: "id".into(),
            title: title.into(),
            old_severity: None,
            new_severity: None,
        };
        let diff = AlertLifecycleDiff {
            updated_alerts: vec![change(
                AlertChangeKind::Updated,
                Some(alert("u", "Moderate", "Flood Watch")),
                "Flood Watch",
            )],
            extended_alerts: vec![change(
                AlertChangeKind::Extended,
                Some(alert("e", "Minor", "Frost Advisory")),
                "Frost Advisory",
            )],
            cancelled_alerts: vec![change(
                AlertChangeKind::Cancelled,
                None,
                "Winter Storm Warning",
            )],
            ..Default::default()
        };
        let toasts = sys.notify_lifecycle_changes(&diff);
        assert_eq!(toasts[0].title, "UPDATED MODERATE: Flood Watch");
        assert_eq!(
            toasts[0].sound_candidates.as_ref().unwrap()[0],
            "alert_updated"
        );
        assert_eq!(toasts[1].title, "MINOR ALERT: Frost Advisory");
        assert!(!toasts[1].play_sound);
        assert_eq!(toasts[2].title, "CANCELLED: Winter Storm Warning");
        assert_eq!(
            toasts[2].message,
            "The alert 'Winter Storm Warning' has been cancelled or expired."
        );
        assert_eq!(toasts[2].activation, None);
    }
}
