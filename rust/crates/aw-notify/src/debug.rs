//! Debug-menu data: the test-alert presets from
//! `ui/dialogs/debug_alert_dialog.py`, the simulated poll alert from
//! `MainWindow._on_debug_simulate_alert`, and the "Run Notification
//! Diagnostics" checks from `notifications/notification_test.py` with both
//! of Python's result renderings.

use aw_core::model::{
    AlertChange, AlertChangeKind, AlertLifecycleDiff, Location, WeatherAlert, WeatherAlerts,
    WeatherData,
};
use aw_core::settings::AppSettings;
use chrono::{DateTime, Duration, DurationRound, FixedOffset, Utc};

use crate::alert_manager::{AlertManager, AlertSettings};
use crate::alert_notifications::AlertNotificationSystem;
use crate::events::NotificationEventManager;
use crate::runtime_state::RuntimeState;
use crate::sound;
use crate::Toast;

/// `AlertPreset`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AlertPreset {
    pub label: &'static str,
    pub event: &'static str,
    pub severity: &'static str,
    pub urgency: &'static str,
    pub headline: &'static str,
    pub description: &'static str,
}

/// `ALERT_PRESETS`, in list-box order.
pub const ALERT_PRESETS: &[AlertPreset] = &[
    AlertPreset {
        label: "Tornado Warning (Extreme)",
        event: "Tornado Warning",
        severity: "Extreme",
        urgency: "Immediate",
        headline: "Tornado Warning in effect until 9:15 PM EDT.",
        description: "A tornado warning has been issued for your area. Take cover now in a sturdy building.",
    },
    AlertPreset {
        label: "Severe Thunderstorm Warning (Severe)",
        event: "Severe Thunderstorm Warning",
        severity: "Severe",
        urgency: "Immediate",
        headline: "Severe Thunderstorm Warning until 7:45 PM EDT.",
        description: "A severe thunderstorm capable of producing golf ball sized hail and damaging winds is approaching.",
    },
    AlertPreset {
        label: "Flash Flood Warning (Severe)",
        event: "Flash Flood Warning",
        severity: "Severe",
        urgency: "Immediate",
        headline: "Flash Flood Warning until midnight EDT.",
        description: "Flash flooding is occurring or imminent. Do not attempt to travel in flooded areas.",
    },
    AlertPreset {
        label: "Flash Flood Watch (Moderate)",
        event: "Flash Flood Watch",
        severity: "Moderate",
        urgency: "Expected",
        headline: "Flash Flood Watch in effect through Wednesday morning.",
        description: "Conditions are favorable for flash flooding.",
    },
    AlertPreset {
        label: "Hurricane Warning (Extreme)",
        event: "Hurricane Warning",
        severity: "Extreme",
        urgency: "Immediate",
        headline: "Hurricane Warning in effect.",
        description: "Hurricane conditions expected within 36 hours. Complete preparations immediately.",
    },
    AlertPreset {
        label: "Winter Storm Watch (Moderate)",
        event: "Winter Storm Watch",
        severity: "Moderate",
        urgency: "Expected",
        headline: "Winter Storm Watch from late tonight through Thursday morning.",
        description: "Heavy snow possible. Total snowfall accumulations of 8 to 14 inches possible.",
    },
    AlertPreset {
        label: "Winter Storm Warning (Severe)",
        event: "Winter Storm Warning",
        severity: "Severe",
        urgency: "Expected",
        headline: "Winter Storm Warning until 6 AM EST Thursday.",
        description: "Heavy snow expected. Total snowfall accumulations of 10 to 16 inches.",
    },
    AlertPreset {
        label: "Dense Fog Advisory (Minor)",
        event: "Dense Fog Advisory",
        severity: "Minor",
        urgency: "Expected",
        headline: "Dense Fog Advisory until 10 AM EDT.",
        description: "Visibility of one quarter mile or less expected.",
    },
    AlertPreset {
        label: "Frost Advisory (Minor)",
        event: "Frost Advisory",
        severity: "Minor",
        urgency: "Expected",
        headline: "Frost Advisory from 2 AM to 8 AM EDT.",
        description: "Temperatures in the upper 20s to low 30s with light winds will result in frost formation.",
    },
    AlertPreset {
        label: "Heat Advisory (Moderate)",
        event: "Heat Advisory",
        severity: "Moderate",
        urgency: "Expected",
        headline: "Heat Advisory until 8 PM EDT this evening.",
        description: "Heat index values up to 105 expected. Drink plenty of fluids.",
    },
    AlertPreset {
        label: "Special Weather Statement (Minor)",
        event: "Special Weather Statement",
        severity: "Minor",
        urgency: "Future",
        headline: "Special Weather Statement.",
        description: "A hazardous weather outlook is in effect for the area.",
    },
    AlertPreset {
        label: "Air Quality Alert (Unknown)",
        event: "Air Quality Alert",
        severity: "Unknown",
        urgency: "Expected",
        headline: "Air Quality Alert in effect.",
        description: "Air quality index values are forecast to reach the Unhealthy for Sensitive Groups range.",
    },
];

impl AlertPreset {
    /// `_make_alert`.
    pub fn alert(&self, now: DateTime<Utc>) -> WeatherAlert {
        let mut a = WeatherAlert::new(self.event, self.description);
        a.id = Some(format!(
            "debug-test-{}",
            self.event.to_lowercase().replace(' ', "-")
        ));
        a.event = Some(self.event.into());
        a.severity = self.severity.into();
        a.urgency = self.urgency.into();
        a.headline = Some(self.headline.into());
        a.expires = Some((now + Duration::hours(2)).fixed_offset());
        a
    }

    /// The preview in the dialog's read-only field (severity sounds only,
    /// like the dialog).
    pub fn sound_candidates(&self, now: DateTime<Utc>) -> Vec<String> {
        sound::get_candidate_sound_events(&self.alert(now), false, None)
    }

    pub fn sound_candidates_text(&self, now: DateTime<Utc>) -> String {
        self.sound_candidates(now).join(" → ")
    }

    /// The toast "Send Test Notification" shows.
    pub fn toast(&self, now: DateTime<Utc>) -> Toast {
        let mut message = self.headline.to_string();
        if !self.description.is_empty() {
            message.push('\n');
            message.push_str(self.description);
        }
        Toast {
            title: format!("{} ALERT: {}", self.severity.to_uppercase(), self.event),
            message,
            timeout: 10,
            sound_event: None,
            sound_candidates: Some(self.sound_candidates(now)),
            play_sound: true,
            activation: None,
        }
    }

    /// The dialog's status line after sending.
    pub fn status_text(&self, sent: bool) -> String {
        if sent {
            format!("✓ Sent: {}", self.label)
        } else {
            "✗ Notification not sent — check system permissions".to_string()
        }
    }
}

/// "Test: Simulate Alert Change (poll cycle)": a fake new tornado warning to
/// feed through the lightweight poll path.
pub fn simulated_poll_data(location: Location) -> WeatherData {
    let mut alert = WeatherAlert::new(
        "Tornado Warning",
        "This is a simulated alert injected via the debug menu to test the event polling notification path.",
    );
    alert.severity = "Extreme".into();
    alert.urgency = "Immediate".into();
    alert.certainty = "Observed".into();
    alert.event = Some("Tornado Warning".into());
    alert.headline = Some("DEBUG: Simulated Tornado Warning for testing".into());
    alert.areas = vec!["Test County".into()];
    alert.id = Some("debug-simulate-001".into());
    alert.message_type = Some("Alert".into());
    let change = AlertChange {
        kind: AlertChangeKind::New,
        alert_id: alert.unique_id(),
        title: alert.title.clone(),
        alert: Some(alert.clone()),
        old_severity: None,
        new_severity: None,
    };
    let mut data = WeatherData::new(location);
    data.alerts = Some(WeatherAlerts {
        alerts: vec![alert],
    });
    data.alert_lifecycle_diff = Some(AlertLifecycleDiff {
        new_alerts: vec![change],
        ..Default::default()
    });
    data
}

/// One diagnostic check result.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DiagnosticResult {
    pub key: &'static str,
    pub passed: bool,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NotificationDiagnostics {
    pub results: Vec<DiagnosticResult>,
}

impl NotificationDiagnostics {
    pub fn passed_count(&self) -> usize {
        self.results.iter().filter(|r| r.passed).count()
    }

    pub fn all_passed(&self) -> bool {
        self.passed_count() == self.results.len()
    }

    /// The message box the Help menu shows ("Notification Test Results",
    /// information icon when all passed, warning otherwise).
    pub fn menu_report(&self) -> String {
        let mut lines = vec!["Notification test results:".to_string()];
        for key in [
            "safe_desktop_notifier",
            "alert_notification_system",
            "discussion_update_path",
        ] {
            let result = self.results.iter().find(|r| r.key == key);
            let status = if result.is_some_and(|r| r.passed) {
                "PASS"
            } else {
                "FAIL"
            };
            lines.push(format!("- {}: {status}", title_words(key)));
            if let Some(r) = result.filter(|r| !r.message.is_empty()) {
                lines.push(format!("  {}", r.message));
            }
        }
        lines.push(String::new());
        lines.push(format!(
            "Summary: {}/{} passed",
            self.passed_count(),
            self.results.len()
        ));
        lines.join("\n")
    }

    /// The tray menu's rendering. Python prints `PASS` for every value that
    /// is truthy, so each result entry (a non-empty dict) reads `PASS` even
    /// when it failed; only the counters and `all_passed` can say `FAIL`.
    pub fn tray_report(&self) -> String {
        let mut lines: Vec<String> = self
            .results
            .iter()
            .map(|r| format!("PASS: {}", r.key))
            .collect();
        let flag = |b: bool| if b { "PASS" } else { "FAIL" };
        lines.push(format!("{}: passed_count", flag(self.passed_count() > 0)));
        lines.push(format!("{}: total_count", flag(!self.results.is_empty())));
        lines.push(format!("{}: all_passed", flag(self.all_passed())));
        lines.join("\n")
    }
}

fn title_words(key: &str) -> String {
    key.split('_')
        .map(|w| {
            let mut c = w.chars();
            c.next()
                .map(|f| f.to_uppercase().chain(c).collect::<String>())
                .unwrap_or_default()
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn py_bool(b: bool) -> &'static str {
    if b {
        "True"
    } else {
        "False"
    }
}

/// `run_notification_test`. `send_direct` shows a real toast through a
/// fresh notifier (Python builds one with app name "AccessiWeather Debug
/// Test"); the other two checks use a recording notifier and never touch
/// the user's state. `now` is local wall-clock time.
pub fn run_notification_diagnostics(
    settings: &AppSettings,
    location_name: Option<&str>,
    send_direct: impl FnOnce(&Toast) -> bool,
    now: DateTime<FixedOffset>,
) -> NotificationDiagnostics {
    let now_utc = now.with_timezone(&Utc);
    let mut results = Vec::new();

    let direct = Toast {
        title: "AccessiWeather Notification Test".into(),
        message: "Direct SafeDesktopNotifier test".into(),
        timeout: 5,
        sound_event: None,
        sound_candidates: None,
        play_sound: false,
        activation: None,
    };
    let sent = send_direct(&direct);
    results.push(DiagnosticResult {
        key: "safe_desktop_notifier",
        passed: sent,
        message: if sent {
            "SafeDesktopNotifier.send_notification returned success".into()
        } else {
            "SafeDesktopNotifier.send_notification returned False".into()
        },
    });

    results.push(
        match tempfile::Builder::new()
            .prefix("accessiweather-alert-test-")
            .tempdir()
        {
            Ok(dir) => {
                let manager = AlertManager::new(
                    RuntimeState::open(dir.path()),
                    AlertSettings::default(),
                    now_utc,
                );
                let mut system = AlertNotificationSystem::new(manager, settings.clone(), None);
                let mut alert =
                    WeatherAlert::new("Debug Test Alert", "Alert notification system debug test.");
                alert.id = Some("debug-alert-test".into());
                alert.severity = "Moderate".into();
                alert.urgency = "Expected".into();
                alert.certainty = "Likely".into();
                alert.event = Some("Debug Notification Test".into());
                alert.expires = Some((now_utc + Duration::hours(1)).fixed_offset());
                let sent = system
                    .process_and_notify(
                        &WeatherAlerts {
                            alerts: vec![alert],
                        },
                        now_utc,
                    )
                    .toasts
                    .len();
                let called = sent > 0;
                DiagnosticResult {
                    key: "alert_notification_system",
                    passed: sent >= 1 && called,
                    message: format!(
                        "process_and_notify sent {sent} notifications; notifier_called={}",
                        py_bool(called)
                    ),
                }
            }
            Err(e) => DiagnosticResult {
                key: "alert_notification_system",
                passed: false,
                message: format!("Exception: {e}"),
            },
        },
    );

    let location_name = location_name
        .filter(|n| !n.is_empty())
        .unwrap_or("Debug Test Location");
    let mut events = NotificationEventManager::new(None, now_utc);
    let event_settings = AppSettings {
        notify_discussion_update: true,
        notify_severe_risk_change: false,
        sound_enabled: settings.sound_enabled,
        ..AppSettings::default()
    };
    let first_time = now_utc
        .duration_trunc(Duration::seconds(1))
        .unwrap_or(now_utc);
    let mut data = WeatherData::new(Location::new(location_name, 0.0, 0.0));
    data.discussion = Some("Initial forecast discussion".into());
    data.discussion_issuance_time = Some(first_time.fixed_offset());
    let initial = events.check_for_events(&data, &event_settings, location_name, now);
    data.discussion = Some("Updated forecast discussion".into());
    data.discussion_issuance_time = Some((first_time + Duration::hours(1)).fixed_offset());
    let updates = events.check_for_events(&data, &event_settings, location_name, now);
    let sent_success = !updates.is_empty();
    let passed = initial.is_empty() && !updates.is_empty() && sent_success;
    results.push(DiagnosticResult {
        key: "discussion_update_path",
        passed,
        message: if passed {
            "initial_events=0, update_events>=1, notifier_send=True".into()
        } else {
            format!(
                "initial_events={}, update_events={}, notifier_send={}",
                initial.len(),
                updates.len(),
                py_bool(sent_success)
            )
        },
    });

    NotificationDiagnostics { results }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preset_data() {
        let now: DateTime<Utc> = "2026-09-25T12:00:00Z".parse().unwrap();
        let p = &ALERT_PRESETS[0];
        assert_eq!(
            p.alert(now).id.as_deref(),
            Some("debug-test-tornado-warning")
        );
        assert_eq!(p.sound_candidates_text(now), "extreme → alert → notify");
        let t = p.toast(now);
        assert_eq!(t.title, "EXTREME ALERT: Tornado Warning");
        assert!(t
            .message
            .starts_with("Tornado Warning in effect until 9:15 PM EDT.\nA tornado"));
        assert_eq!(ALERT_PRESETS.len(), 12);
    }

    #[test]
    fn diagnostics_all_pass_and_render() {
        let now = DateTime::parse_from_rfc3339("2026-09-25T08:00:00-04:00").unwrap();
        let d = run_notification_diagnostics(&AppSettings::default(), None, |_| true, now);
        assert!(d.all_passed(), "{d:?}");
        assert_eq!(
            d.menu_report(),
            "Notification test results:\n- Safe Desktop Notifier: PASS\n  SafeDesktopNotifier.send_notification returned success\n\
             - Alert Notification System: PASS\n  process_and_notify sent 1 notifications; notifier_called=True\n\
             - Discussion Update Path: PASS\n  initial_events=0, update_events>=1, notifier_send=True\n\nSummary: 3/3 passed"
        );
        let failed = run_notification_diagnostics(&AppSettings::default(), None, |_| false, now);
        assert_eq!(
            failed.tray_report(),
            "PASS: safe_desktop_notifier\nPASS: alert_notification_system\nPASS: discussion_update_path\n\
             PASS: passed_count\nPASS: total_count\nFAIL: all_passed"
        );
    }
}
