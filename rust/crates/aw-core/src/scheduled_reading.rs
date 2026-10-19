//! Scheduled weather readings: speak the weather for a saved location on a
//! fixed schedule (every half hour, every hour, ...), like WeatherAloud did.
//!
//! This module holds the parts that need no UI: the saved schedule, the
//! clock that decides when a reading is due, and the text that gets spoken.

use std::collections::BTreeMap;

use chrono::{NaiveDateTime, Timelike};
use serde::{Deserialize, Serialize};

use crate::display::models::{AlertPresentation, WeatherPresentation};

/// WeatherAloud allowed five locations; so do we.
pub const MAX_SCHEDULED_READINGS: usize = 5;

/// The intervals offered, in minutes. Each divides a day evenly, so readings
/// land on the same clock times every day (every 30 minutes means :00 and :30).
pub const INTERVAL_CHOICES: [i64; 7] = [15, 30, 60, 120, 180, 360, 720];

pub const DEFAULT_INTERVAL_MINUTES: i64 = 60;

/// How late a reading may still start after its slot begins. A computer
/// waking from sleep hours later skips the missed reading instead of
/// speaking at a random time.
const GRACE_MINUTES: i64 = 3;

/// How many forecast periods a reading includes (e.g. "Today" and "Tonight").
const FORECAST_PERIODS: usize = 2;

fn d_true() -> bool {
    true
}

fn d_interval() -> i64 {
    DEFAULT_INTERVAL_MINUTES
}

/// One saved schedule: what to read, for which location, how often.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScheduledReading {
    #[serde(default = "d_true")]
    pub enabled: bool,
    /// The saved location's name.
    #[serde(default)]
    pub location: String,
    #[serde(default = "d_interval")]
    pub interval_minutes: i64,
    #[serde(default = "d_true")]
    pub read_current: bool,
    #[serde(default = "d_true")]
    pub read_forecast: bool,
    #[serde(default = "d_true")]
    pub read_alerts: bool,
}

impl ScheduledReading {
    pub fn new(location: impl Into<String>) -> Self {
        Self {
            enabled: true,
            location: location.into(),
            interval_minutes: DEFAULT_INTERVAL_MINUTES,
            read_current: true,
            read_forecast: true,
            read_alerts: true,
        }
    }

    /// The saved interval, snapped to the nearest offered choice so a
    /// hand-edited config can never schedule something odd.
    pub fn interval(&self) -> i64 {
        INTERVAL_CHOICES
            .iter()
            .copied()
            .min_by_key(|choice| (choice - self.interval_minutes).abs())
            .unwrap_or(DEFAULT_INTERVAL_MINUTES)
    }

    pub fn reads_anything(&self) -> bool {
        self.read_current || self.read_forecast || self.read_alerts
    }

    /// "current conditions, forecast and alerts".
    pub fn contents_label(&self) -> String {
        let parts: Vec<&str> = [
            (self.read_current, "current conditions"),
            (self.read_forecast, "forecast"),
            (self.read_alerts, "alerts"),
        ]
        .into_iter()
        .filter_map(|(on, label)| on.then_some(label))
        .collect();
        match parts.as_slice() {
            [] => "nothing".into(),
            [one] => (*one).into(),
            [rest @ .., last] => format!("{} and {last}", rest.join(", ")),
        }
    }

    /// The list entry: "Philadelphia, PA: every hour, current conditions,
    /// forecast and alerts" (with "(off)" when disabled).
    pub fn summary(&self) -> String {
        let off = if self.enabled { "" } else { " (off)" };
        format!(
            "{}: {}, {}{off}",
            self.location,
            interval_label(self.interval()).to_lowercase(),
            self.contents_label()
        )
    }
}

/// "Every 15 minutes", "Every hour", "Every 2 hours".
pub fn interval_label(minutes: i64) -> String {
    match minutes {
        60 => "Every hour".into(),
        m if m % 60 == 0 => format!("Every {} hours", m / 60),
        m => format!("Every {m} minutes"),
    }
}

/// Tracks which time slot each schedule last saw, so every slot is read once.
#[derive(Debug, Default)]
pub struct ReadingClock {
    last_slot: BTreeMap<String, i64>,
}

impl ReadingClock {
    pub fn new() -> Self {
        Self::default()
    }

    /// The indexes of the schedules due at local wall-clock time `now`.
    ///
    /// A schedule is due when `now` has moved into a new slot (for every 30
    /// minutes: a new half hour) within the last few minutes. The first look
    /// at a schedule only records its slot, so starting the app or saving a
    /// new schedule never speaks straight away.
    pub fn due(&mut self, schedules: &[ScheduledReading], now: NaiveDateTime) -> Vec<usize> {
        let minute = now.and_utc().timestamp().div_euclid(60);
        let mut seen = BTreeMap::new();
        let mut due = Vec::new();
        for (index, schedule) in schedules.iter().enumerate() {
            if !schedule.enabled || !schedule.reads_anything() {
                continue;
            }
            let interval = schedule.interval();
            let key = format!("{index}|{}|{interval}", schedule.location);
            let slot = minute.div_euclid(interval);
            let previous = self.last_slot.get(&key).copied();
            if previous.is_some_and(|p| p != slot) && minute - slot * interval < GRACE_MINUTES {
                due.push(index);
            }
            seen.insert(key, slot);
        }
        // Forget schedules that were removed or changed.
        self.last_slot = seen;
        due
    }
}

/// "3:00 PM" or "15:00", following the 12-hour clock setting.
pub fn spoken_time(now: NaiveDateTime, twelve_hour: bool) -> String {
    if twelve_hour {
        let (pm, hour) = now.hour12();
        format!(
            "{hour}:{:02} {}",
            now.minute(),
            if pm { "PM" } else { "AM" }
        )
    } else {
        format!("{:02}:{:02}", now.hour(), now.minute())
    }
}

fn sentence(text: &str) -> String {
    let text = text.trim();
    if text.ends_with(['.', '!', '?']) {
        text.to_string()
    } else {
        format!("{text}.")
    }
}

fn metric<'a>(p: &'a WeatherPresentation, label: &str) -> Option<&'a str> {
    p.current_conditions
        .as_ref()?
        .metrics
        .iter()
        .find(|m| m.label == label)
        .map(|m| m.value.as_str())
        .filter(|v| !v.trim().is_empty())
}

fn current_text(p: &WeatherPresentation) -> String {
    let Some(current) = p.current_conditions.as_ref() else {
        return "Current conditions are unavailable.".into();
    };
    let description = current.description.trim();
    let mut first = String::from("Currently");
    if !description.is_empty() {
        first.push(' ');
        first.push_str(description);
    }
    if let Some(temperature) = metric(p, "Temperature") {
        if description.is_empty() {
            first.push(' ');
        } else {
            first.push_str(", ");
        }
        first.push_str(temperature);
    }
    let mut parts = vec![sentence(&first)];
    if let Some(wind) = metric(p, "Wind") {
        parts.push(sentence(&format!("Wind {wind}")));
    }
    if let Some(humidity) = metric(p, "Humidity") {
        parts.push(sentence(&format!("Humidity {humidity}")));
    }
    parts.join(" ")
}

fn forecast_text(p: &WeatherPresentation) -> String {
    let periods = p
        .forecast
        .as_ref()
        .map(|f| f.periods.as_slice())
        .unwrap_or_default();
    if periods.is_empty() {
        return "The forecast is unavailable.".into();
    }
    periods
        .iter()
        .take(FORECAST_PERIODS)
        .map(|period| {
            let detailed = period.details.as_deref().map(str::trim).unwrap_or("");
            if !detailed.is_empty() {
                return sentence(&format!("{}: {detailed}", period.name));
            }
            let summary: Vec<&str> = [&period.conditions, &period.temperature]
                .into_iter()
                .filter_map(|v| v.as_deref().map(str::trim).filter(|v| !v.is_empty()))
                .collect();
            let mut text = sentence(&format!("{}: {}", period.name, summary.join(", ")));
            if let Some(chance) = period
                .precipitation_probability
                .as_deref()
                .filter(|c| !c.trim().is_empty())
            {
                text.push(' ');
                text.push_str(&sentence(&format!("Chance of precipitation {chance}")));
            }
            text
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn alert_name(alert: &AlertPresentation) -> &str {
    alert
        .event
        .as_deref()
        .filter(|e| !e.trim().is_empty())
        .unwrap_or(&alert.title)
}

fn alerts_text(p: &WeatherPresentation) -> String {
    let alerts = p
        .alerts
        .as_ref()
        .map(|a| a.alerts.as_slice())
        .unwrap_or_default();
    match alerts {
        [] => "No active weather alerts.".into(),
        [one] => sentence(&format!("1 active alert: {}", alert_name(one))),
        many => {
            let names: Vec<&str> = many.iter().map(alert_name).collect();
            sentence(&format!(
                "{} active alerts: {}",
                many.len(),
                names.join(", ")
            ))
        }
    }
}

/// What gets spoken for one schedule: a heading with the place and time, then
/// the parts the schedule asks for.
pub fn compose_reading(
    schedule: &ScheduledReading,
    presentation: &WeatherPresentation,
    time: &str,
) -> String {
    let mut parts = vec![sentence(&format!(
        "Weather for {} at {time}",
        schedule.location
    ))];
    if schedule.read_current {
        parts.push(current_text(presentation));
    }
    if schedule.read_forecast {
        parts.push(forecast_text(presentation));
    }
    if schedule.read_alerts {
        parts.push(alerts_text(presentation));
    }
    parts.join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::display::models::{
        AlertsPresentation, CurrentConditionsPresentation, ForecastPeriodPresentation,
        ForecastPresentation, Metric,
    };
    use chrono::NaiveDate;

    fn at(h: u32, m: u32) -> NaiveDateTime {
        NaiveDate::from_ymd_opt(2026, 10, 19)
            .unwrap()
            .and_hms_opt(h, m, 0)
            .unwrap()
    }

    fn every(minutes: i64) -> ScheduledReading {
        ScheduledReading {
            interval_minutes: minutes,
            ..ScheduledReading::new("Home")
        }
    }

    #[test]
    fn first_look_never_speaks() {
        let mut clock = ReadingClock::new();
        assert!(clock.due(&[every(30)], at(9, 0)).is_empty());
    }

    #[test]
    fn reads_once_when_a_new_slot_starts() {
        let mut clock = ReadingClock::new();
        let schedules = [every(30)];
        assert!(clock.due(&schedules, at(9, 20)).is_empty());
        assert!(clock.due(&schedules, at(9, 29)).is_empty());
        assert_eq!(clock.due(&schedules, at(9, 30)), [0]);
        assert!(clock.due(&schedules, at(9, 30)).is_empty());
        assert!(clock.due(&schedules, at(9, 45)).is_empty());
        assert_eq!(clock.due(&schedules, at(10, 1)), [0]);
    }

    #[test]
    fn hourly_and_two_hourly_schedules_land_on_the_clock() {
        let mut clock = ReadingClock::new();
        let schedules = [every(60), every(120)];
        assert!(clock.due(&schedules, at(10, 59)).is_empty());
        assert_eq!(clock.due(&schedules, at(11, 0)), [0]);
        assert!(clock.due(&schedules, at(11, 59)).is_empty());
        assert_eq!(clock.due(&schedules, at(12, 0)), [0, 1]);
    }

    #[test]
    fn a_slot_missed_while_asleep_is_skipped() {
        let mut clock = ReadingClock::new();
        let schedules = [every(60)];
        clock.due(&schedules, at(1, 10));
        assert!(clock.due(&schedules, at(7, 25)).is_empty());
        assert_eq!(clock.due(&schedules, at(8, 0)), [0]);
    }

    #[test]
    fn disabled_or_empty_schedules_never_read() {
        let mut clock = ReadingClock::new();
        let off = ScheduledReading {
            enabled: false,
            ..every(15)
        };
        let nothing = ScheduledReading {
            read_current: false,
            read_forecast: false,
            read_alerts: false,
            ..every(15)
        };
        let schedules = [off, nothing];
        clock.due(&schedules, at(9, 10));
        assert!(clock.due(&schedules, at(9, 15)).is_empty());
    }

    #[test]
    fn changing_a_schedule_starts_it_fresh() {
        let mut clock = ReadingClock::new();
        clock.due(&[every(60)], at(8, 50));
        // Switched to every 15 minutes: the first look only records.
        assert!(clock.due(&[every(15)], at(9, 0)).is_empty());
        assert_eq!(clock.due(&[every(15)], at(9, 15)), [0]);
    }

    #[test]
    fn odd_intervals_snap_to_an_offered_choice() {
        assert_eq!(every(45).interval(), 30);
        assert_eq!(every(0).interval(), 15);
        assert_eq!(every(10_000).interval(), 720);
        assert_eq!(every(120).interval(), 120);
    }

    #[test]
    fn labels_read_naturally() {
        assert_eq!(interval_label(15), "Every 15 minutes");
        assert_eq!(interval_label(60), "Every hour");
        assert_eq!(interval_label(180), "Every 3 hours");
        let mut s = every(30);
        assert_eq!(
            s.summary(),
            "Home: every 30 minutes, current conditions, forecast and alerts"
        );
        s.read_forecast = false;
        s.enabled = false;
        assert_eq!(
            s.summary(),
            "Home: every 30 minutes, current conditions and alerts (off)"
        );
        s.read_current = false;
        assert_eq!(s.contents_label(), "alerts");
    }

    #[test]
    fn spoken_time_follows_the_clock_setting() {
        assert_eq!(spoken_time(at(15, 0), true), "3:00 PM");
        assert_eq!(spoken_time(at(0, 30), true), "12:30 AM");
        assert_eq!(spoken_time(at(15, 0), false), "15:00");
    }

    fn sample() -> WeatherPresentation {
        WeatherPresentation {
            location_name: "Home".into(),
            current_conditions: Some(CurrentConditionsPresentation {
                description: "Partly Cloudy".into(),
                metrics: vec![
                    Metric::new("Temperature", "72°F"),
                    Metric::new("Wind", "W at 9 mph"),
                    Metric::new("Humidity", "40%"),
                    Metric::new("Pressure", "30.1 inHg"),
                ],
                ..Default::default()
            }),
            forecast: Some(ForecastPresentation {
                periods: vec![
                    ForecastPeriodPresentation {
                        name: "Tonight".into(),
                        conditions: Some("Mostly Clear".into()),
                        temperature: Some("55°F".into()),
                        precipitation_probability: Some("10%".into()),
                        ..Default::default()
                    },
                    ForecastPeriodPresentation {
                        name: "Tuesday".into(),
                        details: Some("Sunny, with a high near 75".into()),
                        conditions: Some("Sunny".into()),
                        ..Default::default()
                    },
                    ForecastPeriodPresentation {
                        name: "Tuesday Night".into(),
                        ..Default::default()
                    },
                ],
                ..Default::default()
            }),
            alerts: Some(AlertsPresentation::default()),
            ..Default::default()
        }
    }

    #[test]
    fn a_full_reading() {
        assert_eq!(
            compose_reading(&every(60), &sample(), "3:00 PM"),
            "Weather for Home at 3:00 PM. Currently Partly Cloudy, 72°F. Wind W at 9 mph. \
             Humidity 40%. Tonight: Mostly Clear, 55°F. Chance of precipitation 10%. \
             Tuesday: Sunny, with a high near 75. No active weather alerts."
        );
    }

    #[test]
    fn only_the_chosen_parts_are_read() {
        let mut presentation = sample();
        presentation.alerts = Some(AlertsPresentation {
            alerts: vec![
                AlertPresentation {
                    title: "Heat Advisory issued".into(),
                    event: Some("Heat Advisory".into()),
                    ..Default::default()
                },
                AlertPresentation {
                    title: "Air Quality Alert".into(),
                    ..Default::default()
                },
            ],
            ..Default::default()
        });
        let schedule = ScheduledReading {
            read_current: false,
            read_forecast: false,
            ..every(60)
        };
        assert_eq!(
            compose_reading(&schedule, &presentation, "15:00"),
            "Weather for Home at 15:00. 2 active alerts: Heat Advisory, Air Quality Alert."
        );
    }

    #[test]
    fn missing_data_is_said_plainly() {
        let schedule = every(60);
        assert_eq!(
            compose_reading(&schedule, &WeatherPresentation::default(), "9:00 AM"),
            "Weather for Home at 9:00 AM. Current conditions are unavailable. \
             The forecast is unavailable. No active weather alerts."
        );
    }

    #[test]
    fn missing_fields_take_their_defaults() {
        let s: ScheduledReading = serde_json::from_str(r#"{"location":"Home"}"#).unwrap();
        assert_eq!(s, ScheduledReading::new("Home"));
    }
}
