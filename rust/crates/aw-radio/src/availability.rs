//! Temporary per-station suppression after every stream failed, and the
//! finder's "Available / Temporarily unavailable" station entries.
//!
//! Ports `noaa_radio/availability_cache.py` and
//! `noaa_radio/station_availability.py`. The cache file
//! (`<config>/noaa_radio_availability.json`) is shared with the Python app.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use serde_json::{Map, Value};

use crate::stations::Station;
use crate::weatherindex::WeatherIndexClient;

pub const AVAILABILITY_FILE_NAME: &str = "noaa_radio_availability.json";
pub const TEMPORARILY_UNAVAILABLE: &str = "temporarily unavailable";

pub type Clock = Box<dyn Fn() -> f64 + Send + Sync>;

/// Wall-clock seconds since the Unix epoch (Python `time.time()`).
pub fn unix_time() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0.0, |d| d.as_secs_f64())
}

#[derive(Debug, Clone, PartialEq)]
pub struct AvailabilityRecord {
    pub reason: String,
    pub expires_at: f64,
}

/// Stations suppressed until a deadline, persisted as a small JSON file.
pub struct StationAvailabilityCache {
    path: PathBuf,
    time_fn: Clock,
    records: BTreeMap<String, AvailabilityRecord>,
}

impl StationAvailabilityCache {
    pub fn new(path: PathBuf) -> Self {
        Self::with_clock(path, Box::new(unix_time))
    }

    /// `<config_dir>/noaa_radio_availability.json`.
    pub fn in_config_dir(config_dir: &Path) -> Self {
        Self::new(config_dir.join(AVAILABILITY_FILE_NAME))
    }

    pub fn with_clock(path: PathBuf, time_fn: Clock) -> Self {
        let mut cache = Self {
            path,
            time_fn,
            records: BTreeMap::new(),
        };
        cache.load();
        cache
    }

    pub fn suppress(&mut self, call_sign: &str, ttl_seconds: u64, reason: &str) {
        let normalized = normalize(call_sign);
        if normalized.is_empty() {
            return;
        }
        let expires_at = (self.time_fn)() + ttl_seconds as f64;
        self.records.insert(
            normalized,
            AvailabilityRecord {
                reason: reason.to_string(),
                expires_at,
            },
        );
        self.save();
    }

    pub fn clear(&mut self, call_sign: &str) {
        let normalized = normalize(call_sign);
        if !normalized.is_empty() && self.records.remove(&normalized).is_some() {
            self.save();
        }
    }

    pub fn is_suppressed(&mut self, call_sign: &str) -> bool {
        self.get_record(call_sign).is_some()
    }

    pub fn get_record(&mut self, call_sign: &str) -> Option<AvailabilityRecord> {
        self.prune_expired();
        self.records.get(&normalize(call_sign)).cloned()
    }

    /// Currently suppressed call signs, sorted.
    pub fn get_suppressed_call_signs(&mut self) -> Vec<String> {
        self.prune_expired();
        self.records.keys().cloned().collect()
    }

    fn load(&mut self) {
        let Ok(text) = std::fs::read_to_string(&self.path) else {
            return;
        };
        let payload: Value = match serde_json::from_str(&text) {
            Ok(payload) => payload,
            Err(e) => {
                tracing::warn!("Failed to load NOAA radio availability cache: {e}");
                return;
            }
        };
        let Value::Object(payload) = payload else {
            return;
        };
        let mut records = BTreeMap::new();
        for (call_sign, record) in &payload {
            let Some(record) = record.as_object() else {
                continue;
            };
            let (Some(expires_at), Some(reason)) = (
                number(record.get("expires_at")),
                record.get("reason").and_then(Value::as_str),
            ) else {
                continue;
            };
            let normalized = normalize(call_sign);
            if !normalized.is_empty() {
                records.insert(
                    normalized,
                    AvailabilityRecord {
                        reason: reason.to_string(),
                        expires_at,
                    },
                );
            }
        }
        self.records = records;
        self.prune_expired();
    }

    fn save(&mut self) {
        self.prune_expired();
        self.write();
    }

    fn write(&self) {
        // `json.dumps(records, indent=2, sort_keys=True)`: BTreeMap keys are
        // sorted and each record's keys are written alphabetically.
        let payload: Map<String, Value> = self
            .records
            .iter()
            .map(|(call_sign, record)| {
                let mut entry = Map::new();
                entry.insert("expires_at".into(), Value::from(record.expires_at));
                entry.insert("reason".into(), Value::from(record.reason.clone()));
                (call_sign.clone(), Value::Object(entry))
            })
            .collect();
        let result = self
            .path
            .parent()
            .map_or(Ok(()), std::fs::create_dir_all)
            .and_then(|()| std::fs::write(&self.path, crate::python_json(&Value::Object(payload))));
        if let Err(e) = result {
            tracing::warn!("Failed to save NOAA radio availability cache: {e}");
        }
    }

    fn prune_expired(&mut self) {
        let now = (self.time_fn)();
        let before = self.records.len();
        self.records.retain(|_, r| r.expires_at > now);
        if self.records.len() != before && self.path.exists() {
            self.write();
        }
    }
}

/// Python `isinstance(v, int | float)` (bools count as ints).
fn number(value: Option<&Value>) -> Option<f64> {
    match value? {
        Value::Number(n) => n.as_f64(),
        Value::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        _ => None,
    }
}

fn normalize(call_sign: &str) -> String {
    call_sign.trim().to_uppercase()
}

/// A finder result row.
#[derive(Debug, Clone, PartialEq)]
pub struct StationAvailabilityEntry {
    pub station: Station,
    pub available: bool,
    pub label: String,
    pub unavailable_reason: Option<String>,
}

/// `"{call sign} - {name}, {state} - {frequency:.3} MHz"` (the state is not
/// repeated when the name already ends in it).
pub fn base_label(station: &Station) -> String {
    let mut location = station.name.trim().to_string();
    let state = station.state.trim().to_uppercase();
    if !state.is_empty() && !location.to_uppercase().ends_with(&format!(", {state}")) {
        location = format!("{location}, {state}");
    }
    format!(
        "{} - {} - {:.3} MHz",
        station.call_sign, location, station.frequency
    )
}

/// Builds finder entries from WeatherIndex feeds and local suppression.
pub struct StationAvailabilityService {
    weatherindex: Arc<WeatherIndexClient>,
    cache: Arc<Mutex<StationAvailabilityCache>>,
}

impl StationAvailabilityService {
    pub fn new(
        weatherindex: Arc<WeatherIndexClient>,
        cache: Arc<Mutex<StationAvailabilityCache>>,
    ) -> Self {
        Self {
            weatherindex,
            cache,
        }
    }

    /// Stations without WeatherIndex feeds are dropped; suppressed stations
    /// are dropped unless `show_unavailable`.
    pub fn build_entries(
        &self,
        stations: &[Station],
        show_unavailable: bool,
    ) -> Vec<StationAvailabilityEntry> {
        let mut entries = Vec::new();
        for station in stations {
            if self
                .weatherindex
                .get_stream_urls(&station.call_sign)
                .is_empty()
            {
                continue;
            }
            let label = base_label(station);
            if self.cache.lock().unwrap().is_suppressed(&station.call_sign) {
                if !show_unavailable {
                    continue;
                }
                entries.push(StationAvailabilityEntry {
                    station: station.clone(),
                    available: false,
                    label: format!("{label} - Temporarily unavailable"),
                    unavailable_reason: Some(TEMPORARILY_UNAVAILABLE.into()),
                });
                continue;
            }
            entries.push(StationAvailabilityEntry {
                station: station.clone(),
                available: true,
                label: format!("{label} - Available"),
                unavailable_reason: None,
            });
        }
        entries
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use aw_providers::http::FixtureClient;
    use serde_json::json;
    use std::sync::atomic::{AtomicU64, Ordering};

    fn clock(now: &Arc<AtomicU64>) -> Clock {
        let now = now.clone();
        Box::new(move || now.load(Ordering::SeqCst) as f64)
    }

    #[test]
    fn suppress_expire_clear_and_persist() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(AVAILABILITY_FILE_NAME);
        let now = Arc::new(AtomicU64::new(1000));
        let mut cache = StationAvailabilityCache::with_clock(path.clone(), clock(&now));
        cache.suppress("kec49", 60, "all_streams_failed");
        assert!(cache.is_suppressed("KEC49"));
        assert_eq!(cache.get_suppressed_call_signs(), ["KEC49"]);

        let mut reopened = StationAvailabilityCache::with_clock(path.clone(), clock(&now));
        assert_eq!(
            reopened.get_record("KEC49"),
            Some(AvailabilityRecord {
                reason: "all_streams_failed".into(),
                expires_at: 1060.0
            })
        );
        now.store(1060, Ordering::SeqCst);
        assert!(!reopened.is_suppressed("KEC49"));
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "{}");

        now.store(1000, Ordering::SeqCst);
        cache.suppress("WXK27", 60, "x");
        cache.clear("wxk27");
        assert!(!cache.is_suppressed("WXK27"));
    }

    #[test]
    fn corrupt_json_fails_soft() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(AVAILABILITY_FILE_NAME);
        std::fs::write(&path, "{nope").unwrap();
        let mut cache = StationAvailabilityCache::new(path);
        assert!(cache.get_suppressed_call_signs().is_empty());
    }

    #[test]
    fn entries_filter_feedless_and_suppressed_stations() {
        let dir = tempfile::tempdir().unwrap();
        let http = Arc::new(
            FixtureClient::new()
                .with(
                    "https://api.wxindex.org/v1/stations/WXK27",
                    json!({"feeds": [{"stream_url": "https://a"}]}),
                )
                .with(
                    "https://api.wxindex.org/v1/stations/KEC49",
                    json!({"feeds": [{"stream_url": "https://b"}]}),
                )
                .with(
                    "https://api.wxindex.org/v1/stations/KIH24",
                    json!({"feeds": []}),
                ),
        );
        let cache = Arc::new(Mutex::new(StationAvailabilityCache::in_config_dir(
            dir.path(),
        )));
        cache
            .lock()
            .unwrap()
            .suppress("KEC49", 1800, "all_streams_failed");
        let service =
            StationAvailabilityService::new(Arc::new(WeatherIndexClient::new(http)), cache);
        let stations = vec![
            Station::new("WXK27", 162.4, "Austin", 30.2672, -97.7431, "TX"),
            Station::new("KEC49", 162.55, "San Francisco Bay, CA", 37.7, -122.4, "CA"),
            Station::new("KIH24", 162.4, "Tallahassee, FL", 30.4, -84.2, "FL"),
        ];
        let labels = |show| -> Vec<String> {
            service
                .build_entries(&stations, show)
                .into_iter()
                .map(|e| e.label)
                .collect()
        };
        assert_eq!(
            labels(false),
            ["WXK27 - Austin, TX - 162.400 MHz - Available"]
        );
        assert_eq!(
            labels(true),
            [
                "WXK27 - Austin, TX - 162.400 MHz - Available",
                "KEC49 - San Francisco Bay, CA - 162.550 MHz - Temporarily unavailable"
            ]
        );
    }
}
