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

use crate::stations::{Station, StationDatabase};
use crate::weatherindex::WeatherIndexClient;

pub const AVAILABILITY_FILE_NAME: &str = "noaa_radio_availability.json";
pub const TEMPORARILY_UNAVAILABLE: &str = "temporarily unavailable";
pub const OUT_OF_SERVICE: &str = "out of service";
pub const NO_ONLINE_STREAM: &str = "no online stream";

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
        if let Err(e) = crate::write_python_json(&self.path, &Value::Object(payload)) {
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

    /// Stations without WeatherIndex feeds are dropped; out-of-service and
    /// suppressed stations are dropped unless `show_unavailable`.
    pub fn build_entries(
        &self,
        stations: &[Station],
        show_unavailable: bool,
    ) -> Vec<StationAvailabilityEntry> {
        self.build_finder_entries(stations, show_unavailable, false)
    }

    /// The finder's station list: `db`, plus (with `include_unstreamed`)
    /// every weather.gov transmitter nobody streams. Those are only added
    /// once the WeatherIndex directory is loaded, so telling them apart
    /// never takes a request per station.
    pub fn finder_database(
        &self,
        db: &Arc<StationDatabase>,
        include_unstreamed: bool,
    ) -> Arc<StationDatabase> {
        if !include_unstreamed || !self.weatherindex.has_station_directory() {
            return db.clone();
        }
        Arc::new(StationDatabase::with_stations(
            crate::transmitters::with_unstreamed(db.get_all_stations()),
        ))
    }

    /// [`Self::build_entries`], except that with `include_unstreamed` (and
    /// `show_unavailable`) stations without a feed stay in the list as
    /// "No online stream", so people can see which transmitter covers them.
    pub fn build_finder_entries(
        &self,
        stations: &[Station],
        show_unavailable: bool,
        include_unstreamed: bool,
    ) -> Vec<StationAvailabilityEntry> {
        let mut entries = Vec::new();
        for station in stations {
            let label = base_label(station);
            if self
                .weatherindex
                .get_stream_urls(&station.call_sign)
                .is_empty()
            {
                if show_unavailable && include_unstreamed {
                    let status = if station.is_out_of_service() {
                        "Out of service"
                    } else {
                        "No online stream"
                    };
                    entries.push(StationAvailabilityEntry {
                        station: station.clone(),
                        available: false,
                        label: format!("{label} - {status}"),
                        unavailable_reason: Some(NO_ONLINE_STREAM.into()),
                    });
                }
                continue;
            }
            if station.is_out_of_service() {
                if !show_unavailable {
                    continue;
                }
                entries.push(StationAvailabilityEntry {
                    station: station.clone(),
                    available: false,
                    label: format!("{label} - Out of service"),
                    unavailable_reason: Some(OUT_OF_SERVICE.into()),
                });
                continue;
            }
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
                label: if station.is_degraded() {
                    format!("{label} - Available, transmitter degraded")
                } else {
                    format!("{label} - Available")
                },
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
    fn out_of_service_stations_show_only_with_unavailable() {
        let dir = tempfile::tempdir().unwrap();
        let http = Arc::new(FixtureClient::new().with(
            "https://api.wxindex.org/v1/stations/WXK27",
            json!({"feeds": [{"stream_url": "https://a"}]}),
        ));
        let service = StationAvailabilityService::new(
            Arc::new(WeatherIndexClient::new(http)),
            Arc::new(Mutex::new(StationAvailabilityCache::new(
                dir.path().join(AVAILABILITY_FILE_NAME),
            ))),
        );
        let mut station = Station::new("WXK27", 162.4, "Austin", 30.32, -97.8, "TX");
        station.status = "OUT OF SERVICE".into();
        assert!(service.build_entries(&[station.clone()], false).is_empty());
        let entries = service.build_entries(&[station], true);
        assert_eq!(entries.len(), 1);
        assert!(!entries[0].available);
        assert_eq!(
            entries[0].label,
            "WXK27 - Austin, TX - 162.400 MHz - Out of service"
        );
        assert_eq!(
            entries[0].unavailable_reason.as_deref(),
            Some(OUT_OF_SERVICE)
        );
    }

    #[test]
    fn unstreamed_transmitters_show_with_unavailable_once_the_directory_loads() {
        let dir = tempfile::tempdir().unwrap();
        let directory = json!([{
            "callsign": "KID77", "city": "Kansas City", "state_slug": "MO",
            "frequency": 162.55, "latitude": 39.0, "longitude": -94.5,
            "status": "NORMAL", "feeds": [{"stream_url": "https://a"}]
        }]);
        let http = Arc::new(
            FixtureClient::new().with(crate::weatherindex::WEATHERINDEX_DIRECTORY_URL, directory),
        );
        let weatherindex = Arc::new(WeatherIndexClient::new(http.clone()));
        let service = StationAvailabilityService::new(
            weatherindex.clone(),
            Arc::new(Mutex::new(StationAvailabilityCache::new(
                dir.path().join(AVAILABILITY_FILE_NAME),
            ))),
        );
        let db = Arc::new(StationDatabase::with_directory(weatherindex.clone()));

        // Not loaded yet: nothing is added.
        assert!(Arc::ptr_eq(&service.finder_database(&db, true), &db));
        weatherindex.get_all_stations();
        assert!(Arc::ptr_eq(&service.finder_database(&db, false), &db));

        let finder = service.finder_database(&db, true);
        let kzz34 = finder.get_stations_by_call_signs(&["KZZ34"]);
        assert_eq!(kzz34.len(), 1);
        let stations = finder.get_stations_by_call_signs(&["KID77", "KZZ34"]);

        let labels = |show, unstreamed| -> Vec<String> {
            service
                .build_finder_entries(&stations, show, unstreamed)
                .into_iter()
                .map(|e| e.label)
                .collect()
        };
        assert_eq!(labels(true, false).len(), 1);
        assert_eq!(labels(false, true).len(), 1);
        let shown = service.build_finder_entries(&stations, true, true);
        assert_eq!(shown.len(), 2);
        assert!(shown[0].available);
        assert!(!shown[1].available);
        assert!(shown[1]
            .label
            .starts_with("KZZ34 - Carrollton, MO - 162.450 MHz"));
        assert!(shown[1].label.ends_with(" - No online stream"));
        assert_eq!(
            shown[1].unavailable_reason.as_deref(),
            Some(NO_ONLINE_STREAM)
        );
        // Telling streamed from unstreamed took only the directory request.
        assert_eq!(http.request_log().len(), 1);
    }

    #[test]
    fn degraded_stations_stay_playable_and_say_so() {
        let dir = tempfile::tempdir().unwrap();
        let http = Arc::new(FixtureClient::new().with(
            "https://api.wxindex.org/v1/stations/WXK27",
            json!({"feeds": [{"stream_url": "https://a"}]}),
        ));
        let service = StationAvailabilityService::new(
            Arc::new(WeatherIndexClient::new(http)),
            Arc::new(Mutex::new(StationAvailabilityCache::new(
                dir.path().join(AVAILABILITY_FILE_NAME),
            ))),
        );
        let mut station = Station::new("WXK27", 162.4, "Austin", 30.32, -97.8, "TX");
        station.status = "degraded".into();
        let entries = service.build_entries(&[station], false);
        assert_eq!(entries.len(), 1);
        assert!(entries[0].available);
        assert_eq!(
            entries[0].label,
            "WXK27 - Austin, TX - 162.400 MHz - Available, transmitter degraded"
        );
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

    #[test]
    fn golden_labels() {
        let golden = crate::golden("stations.json");
        for case in golden["base_labels"].as_array().unwrap() {
            let s = &case["station"];
            let station = Station::new(
                s["call_sign"].as_str().unwrap(),
                s["frequency"].as_f64().unwrap(),
                s["name"].as_str().unwrap(),
                s["lat"].as_f64().unwrap(),
                s["lon"].as_f64().unwrap(),
                s["state"].as_str().unwrap(),
            );
            assert_eq!(base_label(&station), case["label"].as_str().unwrap());
        }
    }

    #[test]
    fn golden_cache_file_round_trips() {
        let golden = crate::golden("files.json");
        let dir = tempfile::tempdir().unwrap();
        for case in golden["availability"].as_array().unwrap() {
            let name = case["name"].as_str().unwrap();
            let path = dir.path().join(format!("{name}.json"));
            if let Some(text) = case["file"].as_str() {
                std::fs::write(&path, text).unwrap();
            }
            let now = Arc::new(Mutex::new(case["now"].as_f64().unwrap()));
            let clock_now = now.clone();
            let mut cache = StationAvailabilityCache::with_clock(
                path.clone(),
                Box::new(move || *clock_now.lock().unwrap()),
            );
            let loaded: Map<String, Value> = cache
                .get_suppressed_call_signs()
                .into_iter()
                .map(|cs| {
                    let r = cache.get_record(&cs).unwrap();
                    (cs, json!({"reason": r.reason, "expires_at": r.expires_at}))
                })
                .collect();
            assert_eq!(Value::Object(loaded), case["loaded"], "{name}: loaded");
            for op in case["ops"].as_array().unwrap() {
                let arg = |i: usize| op[i].as_str().unwrap();
                match arg(0) {
                    "advance" => *now.lock().unwrap() += op[1].as_f64().unwrap(),
                    "suppress" => cache.suppress(arg(1), op[2].as_u64().unwrap(), arg(3)),
                    "clear" => cache.clear(arg(1)),
                    other => panic!("unknown op {other}"),
                }
            }
            let expected: Vec<String> = serde_json::from_value(case["suppressed"].clone()).unwrap();
            assert_eq!(cache.get_suppressed_call_signs(), expected, "{name}");
            // Python's read_text folds CRLF, as this does.
            let saved = std::fs::read_to_string(&path)
                .ok()
                .map(|t| t.replace("\r\n", "\n"));
            assert_eq!(
                saved.as_deref(),
                case["saved_text"].as_str(),
                "{name}: file"
            );
        }
    }
}
