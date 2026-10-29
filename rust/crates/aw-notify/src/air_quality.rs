//! Air quality alerts: one notification each time a location's air quality
//! index reaches the user's alert level.
//!
//! [`AirQualityAlertTracker`] remembers which locations are at or above
//! their level (in the `air_quality_alerts` runtime-state section), so a
//! location notifies once on the way up and again only after it has dropped
//! below and risen back. [`AlertNotificationSystem::air_quality_notification`]
//! turns an event into a toast through the weather-alert rate limits.

use std::collections::BTreeMap;

use aw_core::air_quality::{alert_threshold_key, threshold_label, threshold_rank};
use aw_core::display::pyfmt::round_int;
use aw_core::model::{AqiStandard, EnvironmentalConditions, ReadingKind};
use aw_core::settings::AppSettings;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use crate::alert_notifications::AlertNotificationSystem;
use crate::events::window::{EventCenterEntry, EVENT_TOAST_TIMEOUT_SECONDS};
use crate::py;
use crate::runtime_state::{RuntimeState, Section};
use crate::Toast;

/// Sound keys tried in order; both already exist in the sound event list.
pub const AIR_QUALITY_SOUND_CANDIDATES: [&str; 2] = ["air_quality_alert", "air_quality"];

/// A location that is at or above its alert level, and has been notified.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AboveLevel {
    /// The index the level was reached on; a different index starts over.
    pub standard: AqiStandard,
    pub category: String,
    /// When the notification went out (ISO 8601).
    pub since: String,
}

/// One location reaching its alert level.
#[derive(Debug, Clone, PartialEq)]
pub struct AirQualityEvent {
    pub location: String,
    pub standard: AqiStandard,
    pub value: Option<f64>,
    pub category: String,
    /// The alert level's category name ("Poor").
    pub threshold: &'static str,
    /// "Observed by AirNow at Philadelphia" or "Modelled by Open-Meteo".
    pub source: Option<String>,
}

impl AirQualityEvent {
    pub fn title(&self) -> String {
        format!("Air quality alert: {}", self.location)
    }

    /// "European AQI 65 (Poor) in Paris, at or above your alert level of
    /// Poor. Modelled by Open-Meteo."
    pub fn message(&self) -> String {
        let reading = match self.value {
            Some(v) => format!(
                "{} {} ({})",
                self.standard.name(),
                round_int(v),
                self.category
            ),
            None => format!("{} {}", self.standard.name(), self.category),
        };
        let mut text = format!(
            "{reading} in {}, at or above your alert level of {}.",
            self.location, self.threshold
        );
        if let Some(source) = &self.source {
            text.push(' ');
            text.push_str(source);
            text.push('.');
        }
        text
    }
}

/// A toast plus its Event Center line.
#[derive(Debug, Clone, PartialEq)]
pub struct AirQualityNotification {
    pub toast: Toast,
    pub event_center: EventCenterEntry,
}

/// Which locations are at or above their air quality alert level.
pub struct AirQualityAlertTracker {
    store: RuntimeState,
    /// Location name to its state; loaded on first use.
    above: Option<BTreeMap<String, AboveLevel>>,
}

impl AirQualityAlertTracker {
    pub fn new(store: RuntimeState) -> Self {
        Self { store, above: None }
    }

    fn states(&mut self, now: DateTime<Utc>) -> &mut BTreeMap<String, AboveLevel> {
        if self.above.is_none() {
            let data = self.store.load_section(Section::AirQualityAlerts, now);
            let above = data
                .get("locations")
                .cloned()
                .and_then(|v| serde_json::from_value(v).ok())
                .unwrap_or_default();
            self.above = Some(above);
        }
        self.above.as_mut().expect("loaded above")
    }

    fn save(&mut self, now: DateTime<Utc>) {
        let locations = serde_json::to_value(self.states(now)).unwrap_or(Value::Null);
        let mut data = Map::new();
        data.insert("schema_version".into(), Value::from(1));
        data.insert("locations".into(), locations);
        if !self
            .store
            .save_section(Section::AirQualityAlerts, &data, None, now)
        {
            tracing::error!("Failed to save air quality alert state");
        }
    }

    /// Whether `location` is remembered as at or above its level.
    pub fn is_above(&mut self, location: &str, now: DateTime<Utc>) -> bool {
        self.states(now).contains_key(location)
    }

    /// The event to notify about, if `env` has just reached the alert level
    /// for `location`. A reading below the level clears the location so the
    /// next rise notifies again. Nothing happens (and nothing is written)
    /// while alerts are off or the reading has no known index standard.
    /// The location is only marked once [`Self::mark_notified`] runs.
    pub fn check(
        &mut self,
        location: &str,
        env: Option<&EnvironmentalConditions>,
        settings: &AppSettings,
        now: DateTime<Utc>,
    ) -> Option<AirQualityEvent> {
        if !settings.air_quality_alerts_enabled {
            return None;
        }
        let env = env?;
        let standard = env.air_quality_index_standard?;
        let category = env.air_quality_category.as_deref()?.trim();
        let rank = standard.rank(category)?;
        let key = alert_threshold_key(standard, settings);
        let threshold = threshold_rank(standard, key);

        let states = self.states(now);
        let previous = states.get(location).map(|p| p.standard);
        let still_above = previous == Some(standard);
        // Below the level, or read on another index: start over.
        let reset = previous.is_some() && (rank < threshold || !still_above);
        if reset {
            states.remove(location);
            self.save(now);
        }
        if rank < threshold || still_above {
            return None;
        }
        let source = env.air_quality_provenance.as_ref().map(|p| match p.kind {
            ReadingKind::Observed => {
                format!("Observed by {}", aw_core::air_quality::source_text(p))
            }
            ReadingKind::Modelled => format!("Modelled by {}", p.provider.trim()),
        });
        Some(AirQualityEvent {
            location: location.to_string(),
            standard,
            value: env.air_quality_index,
            category: standard.categories()[rank].to_string(),
            threshold: threshold_label(standard, key),
            source,
        })
    }

    /// Remember that `event`'s location was notified, so it stays quiet
    /// until the reading drops below the level.
    pub fn mark_notified(&mut self, event: &AirQualityEvent, now: DateTime<Utc>) {
        self.states(now).insert(
            event.location.clone(),
            AboveLevel {
                standard: event.standard,
                category: event.category.clone(),
                since: py::isoformat_utc(&now),
            },
        );
        self.save(now);
    }
}

impl AlertNotificationSystem {
    /// Check one location's air quality and build its notification. It
    /// shares the weather alerts' master switch, hourly cap and global
    /// cooldown; when those hold it back, the location is not marked, so
    /// the next check tries again.
    pub fn air_quality_notification(
        &mut self,
        tracker: &mut AirQualityAlertTracker,
        location: &str,
        env: Option<&EnvironmentalConditions>,
        now: DateTime<Utc>,
    ) -> Option<AirQualityNotification> {
        let event = tracker.check(location, env, &self.settings, now)?;
        if !self.manager.settings.notifications_enabled {
            tracing::info!("[airquality] Skipping {location}: notifications disabled");
            return None;
        }
        if let Err(reason) = self.manager.reserve_notification(now) {
            tracing::info!("[airquality] Skipping {location}: {reason}");
            return None;
        }
        tracker.mark_notified(&event, now);
        let title = event.title();
        let message = event.message();
        Some(AirQualityNotification {
            event_center: EventCenterEntry {
                category: title.clone(),
                text: message.clone(),
            },
            toast: Toast {
                title,
                message,
                timeout: EVENT_TOAST_TIMEOUT_SECONDS,
                sound_event: None,
                sound_candidates: Some(
                    AIR_QUALITY_SOUND_CANDIDATES
                        .iter()
                        .map(|s| s.to_string())
                        .collect(),
                ),
                play_sound: self.settings.sound_enabled,
                activation: None,
            },
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::alert_manager::{AlertManager, AlertSettings};
    use aw_core::model::AirQualityProvenance;
    use chrono::Duration;

    fn now() -> DateTime<Utc> {
        "2026-10-20T12:00:00Z".parse().unwrap()
    }

    fn settings(enabled: bool) -> AppSettings {
        AppSettings {
            air_quality_alerts_enabled: enabled,
            ..AppSettings::default()
        }
    }

    fn env(standard: Option<AqiStandard>, value: f64) -> EnvironmentalConditions {
        let category = standard.unwrap_or(AqiStandard::Us).category(value);
        EnvironmentalConditions {
            air_quality_index: Some(value),
            air_quality_category: Some(category.into()),
            air_quality_index_standard: standard,
            air_quality_provenance: Some(AirQualityProvenance {
                kind: ReadingKind::Modelled,
                provider: "Open-Meteo".into(),
                detail: Some("CAMS European model, about 11 km grid".into()),
                station_name: None,
                station_distance_km: None,
                time: None,
            }),
            ..EnvironmentalConditions::default()
        }
    }

    const EU: Option<AqiStandard> = Some(AqiStandard::European);
    const US: Option<AqiStandard> = Some(AqiStandard::Us);

    /// Run one check and mark the location when it fires.
    fn step(
        t: &mut AirQualityAlertTracker,
        e: &EnvironmentalConditions,
        s: &AppSettings,
        at: DateTime<Utc>,
    ) -> Option<AirQualityEvent> {
        let event = t.check("Paris", Some(e), s, at)?;
        t.mark_notified(&event, at);
        Some(event)
    }

    #[test]
    fn notifies_once_per_rise() {
        let dir = tempfile::tempdir().unwrap();
        let mut t = AirQualityAlertTracker::new(RuntimeState::open(dir.path()));
        let s = settings(true);
        // Fair (35) is below Poor.
        assert!(step(&mut t, &env(EU, 35.0), &s, now()).is_none());
        // Poor (65) reaches it.
        let event = step(&mut t, &env(EU, 65.0), &s, now()).unwrap();
        assert_eq!(event.title(), "Air quality alert: Paris");
        assert_eq!(
            event.message(),
            "European AQI 65 (Poor) in Paris, at or above your alert level of Poor. \
             Modelled by Open-Meteo."
        );
        // Staying above, even getting worse, stays quiet.
        assert!(step(&mut t, &env(EU, 70.0), &s, now()).is_none());
        assert!(step(&mut t, &env(EU, 90.0), &s, now()).is_none());
        // Dropping below, then rising again, notifies again.
        assert!(step(&mut t, &env(EU, 50.0), &s, now()).is_none());
        assert!(!t.is_above("Paris", now()));
        assert!(step(&mut t, &env(EU, 61.0), &s, now()).is_some());
    }

    #[test]
    fn exactly_the_threshold_notifies() {
        let dir = tempfile::tempdir().unwrap();
        let mut t = AirQualityAlertTracker::new(RuntimeState::open(dir.path()));
        let mut s = settings(true);
        s.air_quality_alert_threshold_us = "moderate".into();
        // 51 is the first Moderate value; 50 is still Good.
        assert!(step(&mut t, &env(US, 50.0), &s, now()).is_none());
        let event = step(&mut t, &env(US, 51.0), &s, now()).unwrap();
        assert_eq!(event.category, "Moderate");
        assert_eq!(event.threshold, "Moderate");
    }

    #[test]
    fn a_standard_switch_starts_over() {
        let dir = tempfile::tempdir().unwrap();
        let mut t = AirQualityAlertTracker::new(RuntimeState::open(dir.path()));
        let mut s = settings(true);
        s.air_quality_alert_threshold_us = "moderate".into();
        assert!(step(&mut t, &env(EU, 65.0), &s, now()).is_some());
        // The same place read on the US AQI is a new reading.
        let event = step(&mut t, &env(US, 120.0), &s, now()).unwrap();
        assert_eq!(event.standard, AqiStandard::Us);
        assert!(step(&mut t, &env(US, 120.0), &s, now()).is_none());
    }

    #[test]
    fn unknown_standard_and_disabled_are_ignored() {
        let dir = tempfile::tempdir().unwrap();
        let rs = RuntimeState::open(dir.path());
        let mut t = AirQualityAlertTracker::new(rs.clone());
        // Legacy data with no standard.
        assert!(step(&mut t, &env(None, 250.0), &settings(true), now()).is_none());
        // Off: nothing fires and nothing is written.
        assert!(step(&mut t, &env(EU, 95.0), &settings(false), now()).is_none());
        assert!(!rs.state_file().exists());
        assert!(t.check("Paris", None, &settings(true), now()).is_none());
        assert!(!rs.state_file().exists());
    }

    #[test]
    fn state_survives_a_restart() {
        let dir = tempfile::tempdir().unwrap();
        let s = settings(true);
        let mut t = AirQualityAlertTracker::new(RuntimeState::open(dir.path()));
        assert!(step(&mut t, &env(EU, 65.0), &s, now()).is_some());
        let state: Value = serde_json::from_str(
            &std::fs::read_to_string(RuntimeState::open(dir.path()).state_file()).unwrap(),
        )
        .unwrap();
        assert_eq!(
            state["air_quality_alerts"]["locations"]["Paris"]["standard"],
            "european"
        );
        let mut reopened = AirQualityAlertTracker::new(RuntimeState::open(dir.path()));
        assert!(reopened.is_above("Paris", now()));
        assert!(step(&mut reopened, &env(EU, 65.0), &s, now()).is_none());
    }

    fn system(dir: &std::path::Path, settings: AppSettings) -> AlertNotificationSystem {
        let manager = AlertManager::new(
            RuntimeState::open(dir),
            AlertSettings::from_app_settings(&settings),
            now(),
        );
        AlertNotificationSystem::new(manager, settings, None)
    }

    #[test]
    fn notification_uses_the_alert_rate_limits() {
        let dir = tempfile::tempdir().unwrap();
        let rs = RuntimeState::open(dir.path());
        let mut sys = system(dir.path(), settings(true));
        let mut t = AirQualityAlertTracker::new(rs);
        let poor = env(EU, 65.0);

        let n = sys
            .air_quality_notification(&mut t, "Paris", Some(&poor), now())
            .unwrap();
        assert_eq!(n.toast.title, "Air quality alert: Paris");
        assert_eq!(
            n.toast.sound_candidates.as_deref().unwrap(),
            ["air_quality_alert", "air_quality"]
        );
        assert_eq!(n.toast.activation, None);
        assert_eq!(n.event_center.category, "Air quality alert: Paris");

        // A second location inside the global cooldown is held back and
        // left unmarked, so it fires once the cooldown has passed.
        let later = now() + Duration::minutes(1);
        assert!(sys
            .air_quality_notification(&mut t, "Lyon", Some(&poor), later)
            .is_none());
        assert!(!t.is_above("Lyon", later));
        let after = now() + Duration::minutes(6);
        assert!(sys
            .air_quality_notification(&mut t, "Lyon", Some(&poor), after)
            .is_some());
    }

    #[test]
    fn master_switch_off_sends_nothing() {
        let dir = tempfile::tempdir().unwrap();
        let mut s = settings(true);
        s.alert_notifications_enabled = false;
        let mut sys = system(dir.path(), s);
        let mut t = AirQualityAlertTracker::new(RuntimeState::open(dir.path()));
        assert!(sys
            .air_quality_notification(&mut t, "Paris", Some(&env(EU, 65.0)), now())
            .is_none());
        assert!(!t.is_above("Paris", now()));
    }
}
