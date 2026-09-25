//! Merging NWS alerts with a secondary provider's (`weather_client_alerts.py`).

use aw_core::model::{WeatherAlert, WeatherAlerts};
use chrono::Duration;

/// `AlertAggregator`: deduplicates alerts across sources by event, area
/// overlap and onset proximity, keeping the most detailed text.
#[derive(Debug, Clone, Copy)]
pub struct AlertAggregator {
    pub dedup_time_window: Duration,
}

impl Default for AlertAggregator {
    fn default() -> Self {
        Self::new(60)
    }
}

impl AlertAggregator {
    pub fn new(dedup_time_window_minutes: i64) -> Self {
        Self {
            dedup_time_window: Duration::minutes(dedup_time_window_minutes),
        }
    }

    /// `aggregate_alerts`: unlabelled alerts are tagged "nws" or
    /// "pirateweather" by the list they came in.
    pub fn aggregate_alerts(
        &self,
        nws_alerts: Option<WeatherAlerts>,
        secondary_alerts: Option<WeatherAlerts>,
    ) -> WeatherAlerts {
        let mut all: Vec<WeatherAlert> = Vec::new();
        for (alerts, source) in [(nws_alerts, "nws"), (secondary_alerts, "pirateweather")] {
            for mut alert in alerts.map(|a| a.alerts).unwrap_or_default() {
                if alert.source.as_deref().is_none_or(str::is_empty) {
                    alert.source = Some(source.to_string());
                }
                all.push(alert);
            }
        }
        WeatherAlerts {
            alerts: self.deduplicate(all),
        }
    }

    fn deduplicate(&self, alerts: Vec<WeatherAlert>) -> Vec<WeatherAlert> {
        let mut groups: Vec<Vec<WeatherAlert>> = Vec::new();
        for alert in alerts {
            match groups.iter_mut().find(|g| self.is_duplicate(&alert, &g[0])) {
                Some(group) => group.push(alert),
                None => groups.push(vec![alert]),
            }
        }
        groups.into_iter().map(merge_duplicates).collect()
    }

    /// `_is_duplicate`: same event, overlapping areas, onsets within the window.
    pub fn is_duplicate(&self, a: &WeatherAlert, b: &WeatherAlert) -> bool {
        if a.event != b.event || !areas_overlap(&a.areas, &b.areas) {
            return false;
        }
        match (a.onset, b.onset) {
            (Some(x), Some(y)) => (x - y).abs() <= self.dedup_time_window,
            _ => true,
        }
    }
}

/// `_areas_overlap`: an empty list overlaps anything.
fn areas_overlap(a: &[String], b: &[String]) -> bool {
    if a.is_empty() || b.is_empty() {
        return true;
    }
    let norm = |s: &String| s.trim().to_lowercase();
    a.iter().any(|x| b.iter().any(|y| norm(x) == norm(y)))
}

/// `_merge_duplicate_alerts`: NWS (or the first alert) is the base; longer
/// text wins and "Unknown" metadata is filled in from the others.
fn merge_duplicates(mut group: Vec<WeatherAlert>) -> WeatherAlert {
    if group.len() == 1 {
        return group.pop().expect("one alert");
    }
    let is_nws = |a: &WeatherAlert| {
        a.source
            .as_deref()
            .unwrap_or("")
            .to_lowercase()
            .contains("nws")
    };
    group.sort_by_key(|a| !is_nws(a));
    let base = &group[0];

    let mut description = base.description.clone();
    let mut instruction = base.instruction.clone();
    let mut headline = base.headline.clone();
    let mut sources: Vec<String> = base
        .source
        .iter()
        .filter(|s| !s.is_empty())
        .cloned()
        .collect();
    // Python unions areas through a set (arbitrary order); keep first-seen order.
    let mut areas: Vec<String> = Vec::new();
    let mut add_areas = |list: &[String]| {
        for area in list {
            if !areas.contains(area) {
                areas.push(area.clone());
            }
        }
    };
    add_areas(&base.areas);
    let (mut severity, mut urgency, mut certainty) = (
        base.severity.clone(),
        base.urgency.clone(),
        base.certainty.clone(),
    );
    let longer = |candidate: &Option<String>, best: &Option<String>| {
        candidate
            .as_ref()
            .filter(|c| {
                !c.is_empty() && c.chars().count() > best.as_deref().unwrap_or("").chars().count()
            })
            .cloned()
    };

    for alert in &group[1..] {
        if !alert.description.is_empty()
            && alert.description.chars().count() > description.chars().count()
        {
            description = alert.description.clone();
        }
        if let Some(i) = longer(&alert.instruction, &instruction) {
            instruction = Some(i);
        }
        if let Some(h) = longer(&alert.headline, &headline) {
            headline = Some(h);
        }
        if let Some(s) = alert.source.as_ref().filter(|s| !s.is_empty()) {
            if !sources.contains(s) {
                sources.push(s.clone());
            }
        }
        add_areas(&alert.areas);
        let known = |v: &str| !v.is_empty() && v != "Unknown";
        if severity == "Unknown" && known(&alert.severity) {
            severity = alert.severity.clone();
        }
        if urgency == "Unknown" && known(&alert.urgency) {
            urgency = alert.urgency.clone();
        }
        if certainty == "Unknown" && known(&alert.certainty) {
            certainty = alert.certainty.clone();
        }
    }
    sources.sort();

    let mut merged = WeatherAlert::new(
        base.title.clone(),
        if description.is_empty() {
            base.description.clone()
        } else {
            description
        },
    );
    merged.severity = severity;
    merged.urgency = urgency;
    merged.certainty = certainty;
    merged.event = base.event.clone();
    merged.headline = headline;
    merged.instruction = instruction;
    merged.onset = base.onset;
    merged.expires = base.expires;
    merged.sent = base.sent;
    merged.effective = base.effective;
    merged.areas = areas;
    merged.id = base.id.clone();
    merged.source = (!sources.is_empty()).then(|| sources.join(", "));
    merged
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::DateTime;

    fn alert(event: &str, source: Option<&str>, areas: &[&str]) -> WeatherAlert {
        let mut a = WeatherAlert::new(format!("{event} title"), "desc");
        a.event = Some(event.into());
        a.source = source.map(str::to_string);
        a.areas = areas.iter().map(|s| s.to_string()).collect();
        a
    }

    fn at(s: &str) -> Option<aw_core::model::Timestamp> {
        Some(DateTime::parse_from_rfc3339(s).unwrap())
    }

    // tests/test_alert_aggregator.py
    #[test]
    fn sources_are_tagged_and_distinct_alerts_kept() {
        let agg = AlertAggregator::default();
        assert!(agg.aggregate_alerts(None, None).alerts.is_empty());
        let out = agg.aggregate_alerts(
            Some(WeatherAlerts {
                alerts: vec![alert("Flood Warning", None, &["A"])],
            }),
            Some(WeatherAlerts {
                alerts: vec![
                    alert("Heat Advisory", None, &["A"]),
                    alert("Wind", Some("custom"), &[]),
                ],
            }),
        );
        let sources: Vec<_> = out
            .alerts
            .iter()
            .map(|a| a.source.clone().unwrap())
            .collect();
        assert_eq!(sources, ["nws", "pirateweather", "custom"]);
    }

    #[test]
    fn duplicates_merge_with_nws_as_base() {
        let mut pw = alert(
            "Flood Warning",
            Some("pirateweather"),
            &["County A", "County B"],
        );
        pw.description = "a much longer description from pirate weather".into();
        pw.instruction = Some("longer instruction text".into());
        pw.severity = "Severe".into();
        pw.onset = at("2026-01-20T12:30:00+00:00");
        let mut nws = alert("Flood Warning", Some("NWS"), &["county a "]);
        nws.id = Some("urn:nws".into());
        nws.instruction = Some("short".into());
        nws.onset = at("2026-01-20T12:00:00+00:00");
        let out = AlertAggregator::default().aggregate_alerts(
            Some(WeatherAlerts { alerts: vec![nws] }),
            Some(WeatherAlerts { alerts: vec![pw] }),
        );
        assert_eq!(out.alerts.len(), 1);
        let m = &out.alerts[0];
        assert_eq!(m.id.as_deref(), Some("urn:nws"));
        assert_eq!(
            m.description,
            "a much longer description from pirate weather"
        );
        assert_eq!(m.instruction.as_deref(), Some("longer instruction text"));
        assert_eq!(m.severity, "Severe");
        assert_eq!(m.source.as_deref(), Some("NWS, pirateweather"));
        assert_eq!(m.areas, ["county a ", "County A", "County B"]);
    }

    #[test]
    fn duplicate_rules() {
        let agg = AlertAggregator::default();
        let mut a = alert("X", None, &["A"]);
        let mut b = alert("X", None, &["B"]);
        assert!(!agg.is_duplicate(&a, &b), "disjoint areas");
        b.areas.clear();
        assert!(agg.is_duplicate(&a, &b), "empty areas overlap");
        a.onset = at("2026-01-20T12:00:00+00:00");
        b.onset = at("2026-01-20T13:01:00+00:00");
        assert!(!agg.is_duplicate(&a, &b), "outside the hour");
        b.onset = at("2026-01-20T13:00:00+00:00");
        assert!(agg.is_duplicate(&a, &b));
        b.onset = None;
        assert!(agg.is_duplicate(&a, &b));
        assert!(!agg.is_duplicate(&a, &alert("Y", None, &["A"])));
    }
}
