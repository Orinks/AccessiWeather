//! Weather alert models, ported from `accessiweather.models.alerts`.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct WeatherAlert {
    pub id: Option<String>,
    pub title: String,
    pub description: String,
    pub severity: String,
    pub urgency: String,
    pub certainty: String,
    pub event: Option<String>,
    pub headline: Option<String>,
    pub instruction: Option<String>,
    pub onset: Option<DateTime<Utc>>,
    pub expires: Option<DateTime<Utc>>,
    pub sent: Option<DateTime<Utc>>,
    pub effective: Option<DateTime<Utc>>,
    pub areas: Vec<String>,
    pub references: Vec<String>,
    pub source: Option<String>,
    pub message_type: Option<String>,
    pub affected_zones: Vec<String>,
    pub same_codes: Vec<String>,
    pub same_event_codes: Vec<String>,
}

impl WeatherAlert {
    /// Stable identifier. Mirrors Python `get_unique_id`.
    pub fn unique_id(&self) -> String {
        if let Some(id) = self.id.as_deref().filter(|s| !s.is_empty()) {
            return id.to_string();
        }
        let mut parts: Vec<String> = vec![
            self.event.clone().unwrap_or_else(|| "unknown".into()),
            if self.severity.is_empty() {
                "unknown".into()
            } else {
                self.severity.clone()
            },
            self.headline
                .clone()
                .filter(|h| !h.is_empty())
                .unwrap_or_else(|| {
                    if self.title.is_empty() {
                        "unknown".into()
                    } else {
                        self.title.clone()
                    }
                }),
        ];
        if let Some(src) = &self.source {
            parts.push(src.clone());
        }
        if !self.areas.is_empty() {
            let mut areas = self.areas.clone();
            areas.sort();
            parts.push(areas.join(","));
        }
        parts
            .iter()
            .map(|p| p.to_lowercase().replace(' ', "_"))
            .collect::<Vec<_>>()
            .join("-")
    }

    pub fn is_expired(&self, now: DateTime<Utc>) -> bool {
        self.expires.is_some_and(|e| now > e)
    }

    /// Higher value = more severe. Mirrors `SEVERITY_PRIORITY_MAP`.
    pub fn severity_priority(&self) -> u8 {
        match self.severity.to_lowercase().as_str() {
            "extreme" => 5,
            "severe" => 4,
            "moderate" => 3,
            "minor" => 2,
            _ => 1,
        }
    }

    /// One-line label for lists: "Severe: Tornado Warning".
    pub fn list_label(&self) -> String {
        let name = self
            .event
            .clone()
            .or_else(|| self.headline.clone())
            .unwrap_or_else(|| self.title.clone());
        if self.severity.is_empty() || self.severity.eq_ignore_ascii_case("unknown") {
            name
        } else {
            format!("{}: {}", self.severity, name)
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct WeatherAlerts {
    pub alerts: Vec<WeatherAlert>,
}

impl WeatherAlerts {
    pub fn has_alerts(&self) -> bool {
        !self.alerts.is_empty()
    }

    pub fn active(&self, now: DateTime<Utc>) -> Vec<&WeatherAlert> {
        self.alerts.iter().filter(|a| !a.is_expired(now)).collect()
    }

    /// Drop duplicate ids, keeping the first occurrence, then sort by
    /// descending severity.
    pub fn dedupe_and_sort(&mut self) {
        let mut seen = std::collections::HashSet::new();
        self.alerts.retain(|a| seen.insert(a.unique_id()));
        self.alerts
            .sort_by_key(|a| std::cmp::Reverse(a.severity_priority()));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unique_id_without_id_is_derived_and_area_order_independent() {
        let mk = |areas: &[&str]| WeatherAlert {
            event: Some("Wind Advisory".into()),
            severity: "Moderate".into(),
            headline: Some("Wind Advisory issued".into()),
            source: Some("NWS".into()),
            areas: areas.iter().map(|s| s.to_string()).collect(),
            ..Default::default()
        };
        assert_eq!(mk(&["A", "B"]).unique_id(), mk(&["B", "A"]).unique_id());
        assert_eq!(
            mk(&["A"]).unique_id(),
            "wind_advisory-moderate-wind_advisory_issued-nws-a"
        );
    }

    #[test]
    fn dedupe_and_sort_by_severity() {
        let mut alerts = WeatherAlerts {
            alerts: vec![
                WeatherAlert {
                    id: Some("1".into()),
                    severity: "Minor".into(),
                    ..Default::default()
                },
                WeatherAlert {
                    id: Some("2".into()),
                    severity: "Extreme".into(),
                    ..Default::default()
                },
                WeatherAlert {
                    id: Some("1".into()),
                    severity: "Minor".into(),
                    ..Default::default()
                },
            ],
        };
        alerts.dedupe_and_sort();
        assert_eq!(alerts.alerts.len(), 2);
        assert_eq!(alerts.alerts[0].id.as_deref(), Some("2"));
    }
}
