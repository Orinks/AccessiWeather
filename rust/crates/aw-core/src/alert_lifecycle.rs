//! Alert lifecycle: diff two alert snapshots and label NWS alerts.
//! Port of `accessiweather/alert_lifecycle.py`. The result types live in
//! [`crate::model`].

use std::collections::{BTreeMap, HashSet};

use chrono::{DateTime, Duration, Utc};

use crate::model::{AlertChange, AlertChangeKind, AlertLifecycleDiff, WeatherAlert, WeatherAlerts};

/// `SEVERITY_PRIORITY_MAP.get(severity.lower(), 0)`: unrecognised values rank
/// below "unknown" here (unlike `WeatherAlert::severity_priority`).
fn severity_rank(severity: Option<&str>) -> u8 {
    match severity.unwrap_or("").to_lowercase().as_str() {
        "unknown" => 1,
        "minor" => 2,
        "moderate" => 3,
        "severe" => 4,
        "extreme" => 5,
        _ => 0,
    }
}

impl AlertChange {
    fn new(kind: AlertChangeKind, alert_id: &str, alert: &WeatherAlert) -> Self {
        Self {
            kind,
            alert: None,
            alert_id: alert_id.to_string(),
            title: alert.title.clone(),
            old_severity: None,
            new_severity: None,
        }
    }

    /// True when the severity moved to a higher priority tier.
    pub fn is_severity_upgrade(&self) -> bool {
        match (&self.old_severity, &self.new_severity) {
            (Some(old), Some(new)) => severity_rank(Some(new)) > severity_rank(Some(old)),
            _ => false,
        }
    }
}

impl AlertLifecycleDiff {
    pub fn has_changes(&self) -> bool {
        !(self.new_alerts.is_empty()
            && self.updated_alerts.is_empty()
            && self.escalated_alerts.is_empty()
            && self.extended_alerts.is_empty()
            && self.cancelled_alerts.is_empty())
    }
}

/// `compute_lifecycle_labels`: alert id -> "New"/"Updated" from the NWS
/// `messageType`. Other sources get no label.
pub fn compute_lifecycle_labels(alerts: &[WeatherAlert]) -> BTreeMap<String, String> {
    let mut labels = BTreeMap::new();
    for alert in alerts {
        let Some(message_type) = alert.message_type.as_deref().filter(|m| !m.is_empty()) else {
            continue;
        };
        if alert.source.as_deref() != Some("NWS") {
            continue;
        }
        let label = match message_type.to_lowercase().as_str() {
            "alert" => "New",
            "update" => "Updated",
            _ => continue,
        };
        labels.insert(alert.unique_id(), label.to_string());
    }
    labels
}

fn count_label(count: usize, singular: &str) -> String {
    if count == 1 {
        format!("{count} {singular}")
    } else {
        format!("{count} {singular}s")
    }
}

/// Python's `str.capitalize()`: first character upper, the rest lower.
fn capitalize(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        Some(first) => first
            .to_uppercase()
            .chain(chars.flat_map(char::to_lowercase))
            .collect(),
        None => String::new(),
    }
}

fn highest_new_severity(changes: &[AlertChange]) -> String {
    // Python's max() keeps the first of equal keys.
    let mut best = &changes[0];
    for change in &changes[1..] {
        if severity_rank(change.new_severity.as_deref())
            > severity_rank(best.new_severity.as_deref())
        {
            best = change;
        }
    }
    capitalize(
        best.new_severity
            .as_deref()
            .filter(|s| !s.is_empty())
            .unwrap_or("higher"),
    )
}

fn build_summary(diff: &AlertLifecycleDiff) -> String {
    let mut parts = Vec::new();
    if !diff.new_alerts.is_empty() {
        parts.push(count_label(diff.new_alerts.len(), "new alert"));
    }
    if !diff.updated_alerts.is_empty() {
        let label = count_label(diff.updated_alerts.len(), "updated");
        let upgrades: Vec<AlertChange> = diff
            .updated_alerts
            .iter()
            .filter(|c| c.is_severity_upgrade())
            .cloned()
            .collect();
        if upgrades.is_empty() {
            parts.push(label);
        } else {
            let note = highest_new_severity(&upgrades);
            parts.push(format!("{label} (severity upgraded to {note})"));
        }
    }
    if !diff.escalated_alerts.is_empty() {
        let note = highest_new_severity(&diff.escalated_alerts);
        let label = count_label(diff.escalated_alerts.len(), "escalated");
        parts.push(format!("{label} (to {note})"));
    }
    if !diff.extended_alerts.is_empty() {
        parts.push(count_label(diff.extended_alerts.len(), "extended"));
    }
    if !diff.cancelled_alerts.is_empty() {
        parts.push(count_label(diff.cancelled_alerts.len(), "cancelled"));
    }
    if parts.is_empty() {
        "No changes".into()
    } else {
        parts.join(", ")
    }
}

/// True when the alert was issued within `max_age_minutes` (or has no
/// timestamp, which is assumed new to be safe).
fn alert_is_recently_issued(
    alert: &WeatherAlert,
    now: DateTime<Utc>,
    max_age_minutes: i64,
) -> bool {
    match alert.effective.or(alert.onset) {
        None => true,
        Some(issued) => now - issued.with_timezone(&Utc) <= Duration::minutes(max_age_minutes),
    }
}

/// Active alerts keyed by unique id, keeping each id's first position and
/// last alert (Python dict-comprehension semantics).
fn active_by_id(alerts: Option<&WeatherAlerts>, now: DateTime<Utc>) -> Vec<(String, WeatherAlert)> {
    let mut out: Vec<(String, WeatherAlert)> = Vec::new();
    for alert in alerts.map(|a| a.active(now)).unwrap_or_default() {
        let id = alert.unique_id();
        match out.iter_mut().find(|(existing, _)| *existing == id) {
            Some(slot) => slot.1 = alert.clone(),
            None => out.push((id, alert.clone())),
        }
    }
    out
}

fn source_requires_cancel_confirmation(source: Option<&str>) -> bool {
    matches!(
        source.unwrap_or("").trim().to_lowercase().as_str(),
        "nws" | "pirateweather"
    )
}

/// `diff_alerts`: compare two snapshots.
///
/// `confirmed_cancel_ids` are the NWS cancel references; NWS / Pirate Weather
/// alerts that merely disappear are only reported cancelled when listed there
/// (`None` suppresses them all). On first load (`previous` is `None`) alerts
/// issued more than 10 minutes before `now` are not reported as new.
pub fn diff_alerts(
    previous: Option<&WeatherAlerts>,
    current: Option<&WeatherAlerts>,
    confirmed_cancel_ids: Option<&HashSet<String>>,
    now: DateTime<Utc>,
) -> AlertLifecycleDiff {
    let prev_map = active_by_id(previous, now);
    let curr_map = active_by_id(current, now);
    let find = |map: &[(String, WeatherAlert)], id: &str| -> Option<WeatherAlert> {
        map.iter().find(|(k, _)| k == id).map(|(_, a)| a.clone())
    };
    let mut diff = AlertLifecycleDiff::default();

    for (id, alert) in &curr_map {
        if find(&prev_map, id).is_none() {
            diff.new_alerts.push(AlertChange {
                alert: Some(alert.clone()),
                ..AlertChange::new(AlertChangeKind::New, id, alert)
            });
        }
    }

    for (id, prev_alert) in &prev_map {
        if find(&curr_map, id).is_some() {
            continue;
        }
        let announce = if source_requires_cancel_confirmation(prev_alert.source.as_deref()) {
            confirmed_cancel_ids.is_some_and(|ids| ids.contains(id))
        } else {
            true
        };
        if announce {
            diff.cancelled_alerts.push(AlertChange::new(
                AlertChangeKind::Cancelled,
                id,
                prev_alert,
            ));
        }
    }

    for (id, alert) in &curr_map {
        let Some(prev_alert) = find(&prev_map, id) else {
            continue;
        };
        let content_changed = alert.content_hash() != prev_alert.content_hash();
        let severity_changed = alert.severity != prev_alert.severity;
        let urgency_changed = alert.urgency != prev_alert.urgency;
        let escalated = severity_changed
            && severity_rank(Some(&alert.severity)) > severity_rank(Some(&prev_alert.severity));
        let with_severities = |kind| AlertChange {
            alert: Some(alert.clone()),
            old_severity: Some(prev_alert.severity.clone()),
            new_severity: Some(alert.severity.clone()),
            ..AlertChange::new(kind, id, alert)
        };
        if escalated {
            diff.escalated_alerts
                .push(with_severities(AlertChangeKind::Escalated));
        } else if content_changed || severity_changed || urgency_changed {
            diff.updated_alerts
                .push(with_severities(AlertChangeKind::Updated));
        } else if matches!((prev_alert.expires, alert.expires), (Some(p), Some(c)) if c > p) {
            diff.extended_alerts.push(AlertChange {
                alert: Some(alert.clone()),
                ..AlertChange::new(AlertChangeKind::Extended, id, alert)
            });
        }
    }

    if previous.is_none() {
        diff.new_alerts.retain(|c| {
            c.alert
                .as_ref()
                .is_none_or(|a| alert_is_recently_issued(a, now, 10))
        });
    }
    diff.summary = build_summary(&diff);
    diff
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::golden::{self, field};

    #[test]
    fn golden_diff_alerts() {
        let cases = golden::load("alerts/lifecycle.json");
        for case in cases.as_array().unwrap() {
            let now: DateTime<Utc> = field(case, "now");
            let previous: Option<WeatherAlerts> = field(case, "previous");
            let current: Option<WeatherAlerts> = field(case, "current");
            let ids: Option<HashSet<String>> = field(case, "confirmed_cancel_ids");
            let diff = diff_alerts(previous.as_ref(), current.as_ref(), ids.as_ref(), now);
            let expected: AlertLifecycleDiff = field(case, "diff");
            assert_eq!(diff, expected, "{}", case["name"]);
            assert_eq!(diff.has_changes(), case["has_changes"].as_bool().unwrap());
        }
    }

    #[test]
    fn golden_lifecycle_labels() {
        let case = golden::load("alerts/labels.json");
        let alerts: Vec<WeatherAlert> = field(&case, "alerts");
        let expected: BTreeMap<String, String> = field(&case, "labels");
        assert_eq!(compute_lifecycle_labels(&alerts), expected);
    }

    fn change(old: Option<&str>, new: Option<&str>) -> AlertChange {
        AlertChange {
            kind: AlertChangeKind::Updated,
            alert: None,
            alert_id: String::new(),
            title: String::new(),
            old_severity: old.map(Into::into),
            new_severity: new.map(Into::into),
        }
    }

    #[test]
    fn severity_upgrade_detection() {
        assert!(change(Some("Moderate"), Some("Extreme")).is_severity_upgrade());
        assert!(!change(Some("Extreme"), Some("Minor")).is_severity_upgrade());
        assert!(!change(Some("Severe"), Some("Severe")).is_severity_upgrade());
        assert!(!change(None, Some("Severe")).is_severity_upgrade());
        assert!(!change(Some("Severe"), None).is_severity_upgrade());
    }

    fn alert(id: &str, source: &str) -> WeatherAlert {
        WeatherAlert {
            id: Some(id.into()),
            source: Some(source.into()),
            ..WeatherAlert::new("T", "D")
        }
    }

    #[test]
    fn nws_cancel_requires_confirmation() {
        let now = Utc::now();
        let prev = WeatherAlerts {
            alerts: vec![alert("n1", "NWS")],
        };
        let empty = WeatherAlerts::default();
        let unconfirmed = diff_alerts(Some(&prev), Some(&empty), None, now);
        assert!(unconfirmed.cancelled_alerts.is_empty());
        let ids: HashSet<String> = ["n1".to_string()].into();
        let confirmed = diff_alerts(Some(&prev), Some(&empty), Some(&ids), now);
        assert_eq!(confirmed.cancelled_alerts.len(), 1);
        assert_eq!(confirmed.summary, "1 cancelled");
    }

    #[test]
    fn first_load_skips_old_alerts() {
        let now = Utc::now();
        let mut old = alert("old", "NWS");
        old.effective = Some((now - Duration::hours(2)).fixed_offset());
        let mut recent = alert("recent", "NWS");
        recent.effective = Some((now - Duration::minutes(5)).fixed_offset());
        let current = WeatherAlerts {
            alerts: vec![old, recent],
        };
        let diff = diff_alerts(None, Some(&current), None, now);
        assert_eq!(diff.new_alerts.len(), 1);
        assert_eq!(diff.new_alerts[0].alert_id, "recent");
    }
}
