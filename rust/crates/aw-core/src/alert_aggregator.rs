//! Alert aggregation across sources. Port of `AlertAggregator` in
//! `accessiweather/weather_client_alerts.py`.

use std::collections::BTreeSet;

use chrono::Duration;

use crate::model::{WeatherAlert, WeatherAlerts};

/// Merges NWS and secondary-provider (Pirate Weather) alerts, collapsing
/// duplicates (same event, overlapping areas, onsets within the window).
#[derive(Debug, Clone)]
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

    /// `aggregate_alerts`: tag untagged alerts with their source ("nws" or
    /// "pirateweather") and merge duplicates, preferring NWS metadata.
    pub fn aggregate_alerts(
        &self,
        nws_alerts: Option<&WeatherAlerts>,
        secondary_alerts: Option<&WeatherAlerts>,
    ) -> WeatherAlerts {
        let mut all: Vec<WeatherAlert> = Vec::new();
        for (alerts, default_source) in [(nws_alerts, "nws"), (secondary_alerts, "pirateweather")] {
            for alert in alerts.map(|a| a.alerts.as_slice()).unwrap_or_default() {
                let mut alert = alert.clone();
                if alert.source.as_deref().is_none_or(str::is_empty) {
                    alert.source = Some(default_source.to_string());
                }
                all.push(alert);
            }
        }

        let mut groups: Vec<Vec<WeatherAlert>> = Vec::new();
        for alert in all {
            match groups.iter_mut().find(|g| self.is_duplicate(&alert, &g[0])) {
                Some(group) => group.push(alert),
                None => groups.push(vec![alert]),
            }
        }
        WeatherAlerts {
            alerts: groups.into_iter().map(merge_duplicate_alerts).collect(),
        }
    }

    fn is_duplicate(&self, a: &WeatherAlert, b: &WeatherAlert) -> bool {
        if a.event != b.event || !areas_overlap(&a.areas, &b.areas) {
            return false;
        }
        match (a.onset, b.onset) {
            (Some(x), Some(y)) => (x - y).abs() <= self.dedup_time_window,
            _ => true,
        }
    }
}

fn areas_overlap(a: &[String], b: &[String]) -> bool {
    if a.is_empty() || b.is_empty() {
        return true;
    }
    let normalize = |s: &String| s.trim().to_lowercase();
    let a: BTreeSet<String> = a.iter().map(normalize).collect();
    b.iter().map(normalize).any(|s| a.contains(&s))
}

fn char_len(s: Option<&str>) -> usize {
    s.map_or(0, |s| s.chars().count())
}

/// Merge a duplicate group, keeping the most detailed text. NWS alerts are
/// the base because their severity/urgency/certainty metadata is better.
fn merge_duplicate_alerts(mut group: Vec<WeatherAlert>) -> WeatherAlert {
    if group.len() == 1 {
        return group.pop().expect("non-empty group");
    }
    group.sort_by_key(|a| {
        let source = a.source.as_deref().unwrap_or("").to_lowercase();
        usize::from(!source.contains("nws"))
    });
    let base = &group[0];
    let mut description = base.description.clone();
    let mut instruction = base.instruction.clone();
    let mut headline = base.headline.clone();
    let mut sources: BTreeSet<String> = base
        .source
        .iter()
        .filter(|s| !s.is_empty())
        .cloned()
        .collect();
    // Python unions the areas through a set, so their order is arbitrary
    // there; sorted here.
    let mut areas: BTreeSet<String> = base.areas.iter().cloned().collect();
    let mut severity = base.severity.clone();
    let mut urgency = base.urgency.clone();
    let mut certainty = base.certainty.clone();

    for alert in &group[1..] {
        if !alert.description.is_empty()
            && char_len(Some(&alert.description)) > char_len(Some(&description))
        {
            description = alert.description.clone();
        }
        let longer = |candidate: &Option<String>, best: &Option<String>| {
            candidate
                .as_deref()
                .is_some_and(|c| !c.is_empty() && char_len(Some(c)) > char_len(best.as_deref()))
        };
        if longer(&alert.instruction, &instruction) {
            instruction = alert.instruction.clone();
        }
        if longer(&alert.headline, &headline) {
            headline = alert.headline.clone();
        }
        if let Some(source) = alert.source.as_deref().filter(|s| !s.is_empty()) {
            sources.insert(source.to_string());
        }
        areas.extend(alert.areas.iter().cloned());
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

    let base = &group[0];
    let merged_source =
        (!sources.is_empty()).then(|| sources.into_iter().collect::<Vec<_>>().join(", "));
    WeatherAlert {
        title: base.title.clone(),
        description: if description.is_empty() {
            base.description.clone()
        } else {
            description
        },
        severity,
        urgency,
        certainty,
        event: base.event.clone(),
        headline,
        instruction,
        onset: base.onset,
        expires: base.expires,
        sent: base.sent,
        effective: base.effective,
        areas: areas.into_iter().collect(),
        id: base.id.clone(),
        source: merged_source,
        ..WeatherAlert::new("", "")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::golden::{self, field};

    #[test]
    fn golden_aggregate_alerts() {
        let cases = golden::load("alerts/aggregate.json");
        for case in cases.as_array().unwrap() {
            let nws: Option<WeatherAlerts> = field(case, "nws");
            let secondary: Option<WeatherAlerts> = field(case, "secondary");
            let window: i64 = field(case, "window_minutes");
            let result =
                AlertAggregator::new(window).aggregate_alerts(nws.as_ref(), secondary.as_ref());
            let expected: WeatherAlerts = field(case, "result");
            assert_eq!(result, expected, "{}", case["name"]);
        }
    }

    fn alert(title: &str, event: &str) -> WeatherAlert {
        WeatherAlert {
            event: Some(event.into()),
            ..WeatherAlert::new(title, format!("{title} description"))
        }
    }

    #[test]
    fn untagged_alerts_get_their_source() {
        let nws = WeatherAlerts {
            alerts: vec![alert("A", "Flood")],
        };
        let pw = WeatherAlerts {
            alerts: vec![alert("B", "Heat")],
        };
        let out = AlertAggregator::default().aggregate_alerts(Some(&nws), Some(&pw));
        assert_eq!(out.alerts[0].source.as_deref(), Some("nws"));
        assert_eq!(out.alerts[1].source.as_deref(), Some("pirateweather"));
    }

    #[test]
    fn duplicates_merge_areas_and_sources() {
        let mut a = alert("A", "Flood");
        a.areas = vec!["Kings".into()];
        let mut b = alert("B", "Flood");
        b.areas = vec![" kings ".into(), "Bronx".into()];
        b.description = "much longer description".into();
        let out = AlertAggregator::default().aggregate_alerts(
            Some(&WeatherAlerts { alerts: vec![a] }),
            Some(&WeatherAlerts { alerts: vec![b] }),
        );
        assert_eq!(out.alerts.len(), 1);
        let merged = &out.alerts[0];
        assert_eq!(merged.title, "A");
        assert_eq!(merged.description, "much longer description");
        assert_eq!(merged.source.as_deref(), Some("nws, pirateweather"));
        assert_eq!(merged.areas, vec![" kings ", "Bronx", "Kings"]);
    }

    #[test]
    fn empty_inputs_give_empty_alerts() {
        let out = AlertAggregator::default().aggregate_alerts(None, None);
        assert!(out.alerts.is_empty());
    }
}
