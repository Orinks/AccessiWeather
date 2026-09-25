//! Alert state tracking, change detection and notification gating, ported
//! from `alert_manager.py` and `alert_manager_state.py`.
//!
//! Every method that Python drives off the wall clock takes `now` instead
//! (`datetime.now(UTC)` and `time.time()` are both derived from it), so the
//! decisions are deterministic under test.

use std::collections::{BTreeSet, VecDeque};

use aw_core::model::{severity_priority, WeatherAlert, WeatherAlerts};
use aw_core::settings::AppSettings;
use chrono::{DateTime, Duration, DurationRound, FixedOffset, Utc};
use serde_json::{json, Map, Value};

use crate::py;
use crate::runtime_state::{RuntimeState, Section};

pub const ALERT_HISTORY_MAX_LENGTH: usize = 15;
pub const ALERT_STATE_RETENTION_DAYS: i64 = 7;
pub const SECONDS_PER_HOUR: f64 = 3600.0;

/// Notification reasons produced by [`AlertManager::process_alerts`].
pub const REASON_NEW_ALERT: &str = "new_alert";
pub const REASON_CONTENT_CHANGED: &str = "content_changed";
pub const REASON_ESCALATION: &str = "escalation";
pub const REASON_FRESH_ALERT: &str = "fresh_alert";
/// Used for lifecycle "extended" notifications.
pub const REASON_EXTENDED: &str = "extended";

/// `time.time()` equivalent of `now`.
pub fn epoch_seconds(now: DateTime<Utc>) -> f64 {
    now.timestamp_micros() as f64 / 1_000_000.0
}

/// `AlertSettings`: the alert manager's view of the user's settings.
#[derive(Debug, Clone, PartialEq)]
pub struct AlertSettings {
    pub min_severity_priority: i64,
    pub global_cooldown: i64,
    pub per_alert_cooldown: i64,
    pub escalation_cooldown: i64,
    pub freshness_window_minutes: i64,
    pub ignored_categories: BTreeSet<String>,
    pub notifications_enabled: bool,
    pub sound_enabled: bool,
    pub max_notifications_per_hour: i64,
}

impl Default for AlertSettings {
    fn default() -> Self {
        Self {
            min_severity_priority: 2,
            global_cooldown: 5,
            per_alert_cooldown: 0,
            escalation_cooldown: 15,
            freshness_window_minutes: 15,
            ignored_categories: BTreeSet::new(),
            notifications_enabled: true,
            sound_enabled: true,
            max_notifications_per_hour: 10,
        }
    }
}

impl AlertSettings {
    /// `AppSettings.to_alert_settings()`. The lowest checked severity is the
    /// minimum: checking "minor" notifies for minor and everything above it,
    /// whatever the higher boxes say.
    pub fn from_app_settings(s: &AppSettings) -> Self {
        let min_severity_priority = if s.alert_notify_unknown {
            1
        } else if s.alert_notify_minor {
            2
        } else if s.alert_notify_moderate {
            3
        } else if s.alert_notify_severe {
            4
        } else if s.alert_notify_extreme {
            5
        } else {
            6
        };
        Self {
            min_severity_priority,
            global_cooldown: s.alert_global_cooldown_minutes,
            per_alert_cooldown: s.alert_per_alert_cooldown_minutes,
            escalation_cooldown: s.alert_escalation_cooldown_minutes,
            freshness_window_minutes: s.alert_freshness_window_minutes,
            ignored_categories: s.alert_ignored_categories.iter().cloned().collect(),
            notifications_enabled: s.alert_notifications_enabled,
            sound_enabled: s.sound_enabled,
            max_notifications_per_hour: s.alert_max_notifications_per_hour,
        }
    }

    pub fn should_notify_severity(&self, severity: &str) -> bool {
        self.notifications_enabled
            && i64::from(severity_priority(severity)) >= self.min_severity_priority
    }

    /// Case-insensitive match against the ignored categories.
    pub fn should_notify_category(&self, event: &str) -> bool {
        if event.is_empty() {
            return true;
        }
        let event = event.to_lowercase();
        !self
            .ignored_categories
            .iter()
            .any(|c| c.to_lowercase() == event)
    }
}

/// One tracked alert with its bounded content-hash history.
#[derive(Debug, Clone, PartialEq)]
pub struct AlertState {
    pub alert_id: String,
    pub first_seen: DateTime<FixedOffset>,
    pub last_notified: Option<DateTime<FixedOffset>>,
    pub notification_count: i64,
    pub alert_sent_time: Option<DateTime<FixedOffset>>,
    /// `(content_hash, severity_priority, epoch_seconds)`.
    pub hash_history: VecDeque<(String, i64, f64)>,
}

impl AlertState {
    pub fn new(
        alert_id: String,
        content_hash: String,
        first_seen: DateTime<FixedOffset>,
        severity_priority: i64,
        alert_sent_time: Option<DateTime<FixedOffset>>,
        now_ts: f64,
    ) -> Self {
        let mut state = Self {
            alert_id,
            first_seen,
            last_notified: None,
            notification_count: 0,
            alert_sent_time,
            hash_history: VecDeque::new(),
        };
        state.add_hash(content_hash, severity_priority, now_ts);
        state
    }

    pub fn content_hash(&self) -> &str {
        self.hash_history.back().map_or("", |h| h.0.as_str())
    }

    pub fn add_hash(&mut self, content_hash: String, severity_priority: i64, timestamp: f64) {
        if self.hash_history.len() == ALERT_HISTORY_MAX_LENGTH {
            self.hash_history.pop_front();
        }
        self.hash_history
            .push_back((content_hash, severity_priority, timestamp));
    }

    pub fn has_changed(&self, new_hash: &str) -> bool {
        self.hash_history.back().is_none_or(|h| h.0 != new_hash)
    }

    /// Escalated against the highest severity ever seen for this alert.
    pub fn is_escalated(&self, new_priority: i64) -> bool {
        self.hash_history
            .iter()
            .map(|h| h.1)
            .max()
            .is_some_and(|max| new_priority > max)
    }

    pub fn to_json(&self) -> Value {
        json!({
            "alert_id": self.alert_id,
            "first_seen": py::isoformat(&self.first_seen),
            "last_notified": self.last_notified.as_ref().map(py::isoformat),
            "notification_count": self.notification_count,
            "alert_sent_time": self.alert_sent_time.as_ref().map(py::isoformat),
            "hash_history": self.hash_history.iter()
                .map(|(h, p, t)| json!([h, p, t]))
                .collect::<Vec<_>>(),
        })
    }

    /// `AlertState.from_dict`; `None` where Python would raise.
    pub fn from_json(data: &Value, now_ts: f64) -> Option<Self> {
        let alert_id = data.get("alert_id")?.as_str()?.to_string();
        let first_seen = py::parse_aware(data.get("first_seen")?.as_str()?)?;
        let opt_time = |key: &str| -> Option<Option<DateTime<FixedOffset>>> {
            match data.get(key) {
                None | Some(Value::Null) => Some(None),
                Some(Value::String(s)) if s.is_empty() => Some(None),
                Some(Value::String(s)) => py::parse_aware(s).map(Some),
                Some(_) => None,
            }
        };
        let last_notified = opt_time("last_notified")?;
        let alert_sent_time = opt_time("alert_sent_time")?;
        let notification_count = data
            .get("notification_count")
            .map_or(Some(0), Value::as_i64)?;
        if let Some(history) = data.get("hash_history") {
            let mut hash_history = VecDeque::new();
            for entry in history.as_array()? {
                let [h, p, t] = entry.as_array()?.as_slice() else {
                    return None;
                };
                if hash_history.len() == ALERT_HISTORY_MAX_LENGTH {
                    hash_history.pop_front();
                }
                hash_history.push_back((h.as_str()?.to_string(), p.as_i64()?, t.as_f64()?));
            }
            return Some(Self {
                alert_id,
                first_seen,
                last_notified,
                notification_count,
                alert_sent_time,
                hash_history,
            });
        }
        let content_hash = data
            .get("content_hash")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let mut state = Self::new(
            alert_id,
            content_hash,
            first_seen,
            1,
            alert_sent_time,
            now_ts,
        );
        state.last_notified = last_notified;
        state.notification_count = notification_count;
        Some(state)
    }
}

/// `AlertManager`: decides which active alerts deserve a notification and
/// persists what it has seen in the `alerts` runtime-state section.
pub struct AlertManager {
    store: RuntimeState,
    pub settings: AlertSettings,
    alert_states: Vec<AlertState>,
    last_global_notification: Option<DateTime<FixedOffset>>,
    notifications_this_hour: i64,
    hour_reset_time: DateTime<Utc>,
    rate_limit_tokens: f64,
    rate_limit_capacity: f64,
    rate_limit_refill_rate: f64,
    rate_limit_last_refill: f64,
    state_loaded: bool,
}

impl AlertManager {
    pub fn new(store: RuntimeState, settings: AlertSettings, now: DateTime<Utc>) -> Self {
        let max = settings.max_notifications_per_hour as f64;
        Self {
            store,
            settings,
            alert_states: Vec::new(),
            last_global_notification: None,
            notifications_this_hour: 0,
            hour_reset_time: truncate_to_hour(now),
            rate_limit_tokens: max,
            rate_limit_capacity: max,
            rate_limit_refill_rate: max / SECONDS_PER_HOUR,
            rate_limit_last_refill: epoch_seconds(now),
            state_loaded: false,
        }
    }

    pub fn alert_states(&self) -> &[AlertState] {
        &self.alert_states
    }

    pub fn last_global_notification(&self) -> Option<DateTime<FixedOffset>> {
        self.last_global_notification
    }

    pub fn set_last_global_notification(&mut self, value: Option<DateTime<FixedOffset>>) {
        self.last_global_notification = value;
    }

    pub fn rate_limit_tokens(&self) -> f64 {
        self.rate_limit_tokens
    }

    pub fn set_rate_limit_tokens(&mut self, tokens: f64) {
        self.rate_limit_tokens = tokens;
    }

    pub fn notifications_this_hour(&self) -> i64 {
        self.notifications_this_hour
    }

    pub fn ensure_state_loaded(&mut self, now: DateTime<Utc>) {
        if self.state_loaded {
            return;
        }
        self.state_loaded = true;
        let data = self.store.load_section(Section::Alerts, now);
        let ts = epoch_seconds(now);
        let mut states = Vec::new();
        for item in data
            .get("alert_states")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            match AlertState::from_json(item, ts) {
                Some(state) => upsert(&mut states, state),
                None => {
                    tracing::error!("Failed to load alert state: invalid entry {item}");
                    self.alert_states.clear();
                    return;
                }
            }
        }
        self.alert_states = states;
        if let Some(s) = data
            .get("last_global_notification")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
        {
            match py::parse_aware(s) {
                Some(dt) => self.last_global_notification = Some(dt),
                None => {
                    tracing::error!("Failed to load alert state: bad timestamp {s}");
                    self.alert_states.clear();
                }
            }
        }
        tracing::info!(
            "Loaded {} alert states from runtime storage",
            self.alert_states.len()
        );
    }

    fn save_state(&mut self, now: DateTime<Utc>) {
        let cutoff = now - Duration::days(ALERT_STATE_RETENTION_DAYS);
        let before = self.alert_states.len();
        self.alert_states.retain(|s| s.first_seen >= cutoff);
        if self.alert_states.len() != before {
            tracing::info!(
                "Cleaned up {} expired alert states",
                before - self.alert_states.len()
            );
        }
        let mut data = Map::new();
        data.insert(
            "alert_states".into(),
            Value::Array(self.alert_states.iter().map(AlertState::to_json).collect()),
        );
        data.insert(
            "last_global_notification".into(),
            self.last_global_notification
                .as_ref()
                .map(py::isoformat)
                .into(),
        );
        if !self.store.save_section(Section::Alerts, &data, None, now) {
            tracing::error!("Failed to save alert runtime state");
        }
    }

    fn reset_hourly_counter(&mut self, now: DateTime<Utc>) {
        let current_hour = truncate_to_hour(now);
        if current_hour > self.hour_reset_time {
            self.notifications_this_hour = 0;
            self.hour_reset_time = current_hour;
        }
    }

    fn refill_rate_limit_tokens(&mut self, now: DateTime<Utc>) {
        let current = epoch_seconds(now);
        let elapsed = current - self.rate_limit_last_refill;
        self.rate_limit_tokens = self
            .rate_limit_capacity
            .min(self.rate_limit_tokens + elapsed * self.rate_limit_refill_rate);
        self.rate_limit_last_refill = current;
    }

    fn check_rate_limit(&mut self, now: DateTime<Utc>) -> bool {
        self.refill_rate_limit_tokens(now);
        if self.rate_limit_tokens >= 1.0 {
            self.rate_limit_tokens -= 1.0;
            true
        } else {
            false
        }
    }

    fn can_send_global_notification(&self, now: DateTime<Utc>) -> bool {
        match self.last_global_notification {
            None => true,
            Some(last) => {
                now - last.with_timezone(&Utc) > Duration::minutes(self.settings.global_cooldown)
            }
        }
    }

    fn is_alert_fresh(&self, sent: Option<DateTime<FixedOffset>>, now: DateTime<Utc>) -> bool {
        let Some(sent) = sent else {
            return false;
        };
        let age = now - sent.with_timezone(&Utc);
        age <= Duration::minutes(self.settings.freshness_window_minutes) && age >= Duration::zero()
    }

    fn passes_static_filters(
        &self,
        alert: &WeatherAlert,
        now: DateTime<Utc>,
    ) -> Result<(), String> {
        if !self.settings.notifications_enabled {
            return Err("notifications_disabled".into());
        }
        if !self.settings.should_notify_severity(&alert.severity) {
            return Err(format!("severity_below_threshold_{}", alert.severity));
        }
        if let Some(event) = alert.event.as_deref().filter(|e| !e.is_empty()) {
            if !self.settings.should_notify_category(event) {
                return Err(format!("category_ignored_{event}"));
            }
        }
        if alert.is_expired(now) {
            return Err("alert_expired".into());
        }
        Ok(())
    }

    /// Token bucket first, then the global cooldown. A token is spent even
    /// when the cooldown then blocks the alert, as in Python.
    fn can_notify_now(&mut self, now: DateTime<Utc>) -> Result<(), &'static str> {
        if !self.check_rate_limit(now) {
            return Err("rate_limit_exceeded");
        }
        if !self.can_send_global_notification(now) {
            return Err("global_cooldown_active");
        }
        Ok(())
    }

    /// `process_alerts`: the active alerts to notify about, with the reason
    /// (`new_alert`, `content_changed`, `escalation` or `fresh_alert`).
    pub fn process_alerts(
        &mut self,
        alerts: &WeatherAlerts,
        now: DateTime<Utc>,
    ) -> Vec<(WeatherAlert, &'static str)> {
        self.ensure_state_loaded(now);
        if !alerts.has_alerts() {
            return Vec::new();
        }
        let now_fixed = now.fixed_offset();
        let now_ts = epoch_seconds(now);
        let active = alerts.active(now);
        let mut to_send: Vec<(WeatherAlert, &'static str)> = Vec::new();

        for alert in &active {
            let alert_id = alert.unique_id();
            let content_hash = alert.content_hash();
            let priority = i64::from(alert.severity_priority());
            let sent_time = alert.sent.or(alert.effective);

            if let Err(reason) = self.passes_static_filters(alert, now) {
                tracing::info!("[alertmgr] Skipping alert {alert_id:?}: {reason}");
                continue;
            }

            let existing = self
                .alert_states
                .iter()
                .position(|s| s.alert_id == alert_id);
            match existing {
                None => {
                    if let Err(reason) = self.can_notify_now(now) {
                        tracing::info!("[alertmgr] Skipping new alert {alert_id:?}: {reason}");
                        continue;
                    }
                    self.alert_states.push(AlertState::new(
                        alert_id,
                        content_hash,
                        now_fixed,
                        priority,
                        sent_time,
                        now_ts,
                    ));
                    to_send.push(((*alert).clone(), REASON_NEW_ALERT));
                }
                Some(i) if self.alert_states[i].has_changed(&content_hash) => {
                    if let Err(reason) = self.can_notify_now(now) {
                        tracing::info!("[alertmgr] Skipping changed alert {alert_id:?}: {reason}");
                        continue;
                    }
                    let state = &mut self.alert_states[i];
                    let escalated = state.is_escalated(priority);
                    state.add_hash(content_hash, priority, now_ts);
                    if sent_time.is_some() && sent_time != state.alert_sent_time {
                        state.alert_sent_time = sent_time;
                    }
                    let reason = if escalated {
                        REASON_ESCALATION
                    } else {
                        REASON_CONTENT_CHANGED
                    };
                    to_send.push(((*alert).clone(), reason));
                }
                Some(i) => {
                    let never_notified = self.alert_states[i].last_notified.is_none();
                    if self.is_alert_fresh(sent_time, now) && never_notified {
                        if let Err(reason) = self.can_notify_now(now) {
                            tracing::info!(
                                "[alertmgr] Skipping fresh alert {alert_id:?}: {reason}"
                            );
                            continue;
                        }
                        to_send.push(((*alert).clone(), REASON_FRESH_ALERT));
                    }
                }
            }
        }

        for (alert, _) in &to_send {
            let id = alert.unique_id();
            if let Some(state) = self.alert_states.iter_mut().find(|s| s.alert_id == id) {
                state.last_notified = Some(now_fixed);
                state.notification_count += 1;
            }
        }
        if !to_send.is_empty() {
            self.last_global_notification = Some(now_fixed);
            self.reset_hourly_counter(now);
            self.notifications_this_hour += to_send.len() as i64;
        }
        self.save_state(now);
        tracing::info!(
            "Processed {} alerts, {} notifications to send",
            active.len(),
            to_send.len()
        );
        to_send
    }

    /// `update_settings`: keeps the token ratio when the hourly cap changes.
    pub fn update_settings(&mut self, new_settings: AlertSettings) {
        let old_max = self.settings.max_notifications_per_hour;
        if old_max != new_settings.max_notifications_per_hour {
            let ratio = if self.rate_limit_capacity > 0.0 {
                self.rate_limit_tokens / self.rate_limit_capacity
            } else {
                1.0
            };
            self.rate_limit_capacity = new_settings.max_notifications_per_hour as f64;
            self.rate_limit_tokens = ratio * self.rate_limit_capacity;
            self.rate_limit_refill_rate = self.rate_limit_capacity / SECONDS_PER_HOUR;
        }
        self.settings = new_settings;
    }
}

/// Python keys the in-memory states by id, so a repeated id in the file
/// replaces the earlier entry in place.
fn upsert(states: &mut Vec<AlertState>, state: AlertState) {
    match states.iter_mut().find(|s| s.alert_id == state.alert_id) {
        Some(existing) => *existing = state,
        None => states.push(state),
    }
}

fn truncate_to_hour(now: DateTime<Utc>) -> DateTime<Utc> {
    now.duration_trunc(Duration::hours(1)).unwrap_or(now)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn at(s: &str) -> DateTime<Utc> {
        s.parse().unwrap()
    }

    fn alert(id: &str, severity: &str, event: &str, now: DateTime<Utc>) -> WeatherAlert {
        let mut a = WeatherAlert::new(event, format!("{event} text"));
        a.id = Some(id.into());
        a.severity = severity.into();
        a.event = Some(event.into());
        a.expires = Some((now + Duration::hours(2)).fixed_offset());
        a
    }

    fn manager(dir: &std::path::Path, now: DateTime<Utc>) -> AlertManager {
        AlertManager::new(RuntimeState::open(dir), AlertSettings::default(), now)
    }

    #[test]
    fn lowest_checked_severity_is_the_minimum() {
        let mut s = AppSettings::default();
        assert_eq!(
            AlertSettings::from_app_settings(&s).min_severity_priority,
            3
        );
        s.alert_notify_minor = true;
        s.alert_notify_severe = false;
        assert_eq!(
            AlertSettings::from_app_settings(&s).min_severity_priority,
            2
        );
        s.alert_notify_minor = false;
        s.alert_notify_moderate = false;
        s.alert_notify_extreme = false;
        assert_eq!(
            AlertSettings::from_app_settings(&s).min_severity_priority,
            6
        );
    }

    #[test]
    fn category_filter_is_case_insensitive() {
        let mut s = AlertSettings::default();
        s.ignored_categories.insert("Heat Advisory".into());
        assert!(!s.should_notify_category("heat advisory"));
        assert!(s.should_notify_category("Tornado Warning"));
        assert!(s.should_notify_category(""));
    }

    #[test]
    fn escalation_compares_against_history_max() {
        let now = at("2026-09-25T12:00:00Z");
        let mut s = AlertState::new("a".into(), "h1".into(), now.fixed_offset(), 4, None, 1.0);
        s.add_hash("h2".into(), 2, 2.0);
        assert!(!s.is_escalated(3));
        assert!(s.is_escalated(5));
        assert!(s.has_changed("h1"));
        assert!(!s.has_changed("h2"));
        for i in 0..20 {
            s.add_hash(format!("x{i}"), 1, 3.0);
        }
        assert_eq!(s.hash_history.len(), ALERT_HISTORY_MAX_LENGTH);
    }

    #[test]
    fn new_then_duplicate_then_restart() {
        let dir = tempfile::tempdir().unwrap();
        let now = at("2026-09-25T12:00:00Z");
        let a = alert("NWS-1", "Severe", "Severe Thunderstorm Warning", now);
        let alerts = WeatherAlerts {
            alerts: vec![a.clone()],
        };
        let mut m = manager(dir.path(), now);
        let sent = m.process_alerts(&alerts, now);
        assert_eq!(sent.len(), 1);
        assert_eq!(sent[0].1, REASON_NEW_ALERT);
        assert!(m
            .process_alerts(&alerts, now + Duration::minutes(10))
            .is_empty());

        let mut restarted = manager(dir.path(), now + Duration::minutes(20));
        assert!(restarted
            .process_alerts(&alerts, now + Duration::minutes(20))
            .is_empty());
        assert_eq!(restarted.alert_states()[0].notification_count, 1);
    }

    #[test]
    fn unchanged_alert_does_not_starve_new_alert() {
        let dir = tempfile::tempdir().unwrap();
        let now = at("2026-09-25T12:00:00Z");
        let old = alert("NWS-1", "Severe", "Wind Advisory", now);
        let new = alert("NWS-2", "Extreme", "Tornado Warning", now);
        let mut m = manager(dir.path(), now);
        m.process_alerts(
            &WeatherAlerts {
                alerts: vec![old.clone()],
            },
            now,
        );
        m.set_last_global_notification(None);
        m.set_rate_limit_tokens(1.0);
        let sent = m.process_alerts(
            &WeatherAlerts {
                alerts: vec![old, new],
            },
            now,
        );
        assert_eq!(sent.len(), 1);
        assert_eq!(sent[0].0.id.as_deref(), Some("NWS-2"));
    }

    #[test]
    fn rate_limit_caps_a_burst() {
        let dir = tempfile::tempdir().unwrap();
        let now = at("2026-09-25T12:00:00Z");
        let settings = AlertSettings {
            max_notifications_per_hour: 2,
            ..AlertSettings::default()
        };
        let mut m = AlertManager::new(RuntimeState::open(dir.path()), settings, now);
        let alerts = WeatherAlerts {
            alerts: (0..5)
                .map(|i| alert(&format!("a{i}"), "Severe", &format!("Event {i}"), now))
                .collect(),
        };
        assert_eq!(m.process_alerts(&alerts, now).len(), 2);
    }
}
