//! Unified runtime-state file shared with the Python app
//! (`accessiweather/runtime_state.py`): `<config>/state/runtime_state.json`.
//!
//! The file is kept as a JSON value so sections this crate does not own (and
//! keys added by future Python versions) round-trip untouched, in their
//! original order. Loads are cached in memory exactly like Python's
//! `RuntimeStateManager`.
//!
//! Python gives the alert manager and the notification-event manager two
//! separate `RuntimeStateManager` instances, so each one's save rewrites the
//! other's section from a stale cache. Here [`RuntimeState`] is a cheap
//! cloneable handle: hand the same one to both managers and they share one
//! cache.

use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, MutexGuard};

use chrono::{DateTime, Utc};
use serde_json::{json, Map, Value};

use crate::py;

pub const STATE_DIR_NAME: &str = "state";
pub const STATE_FILE_NAME: &str = "runtime_state.json";
pub const LEGACY_ALERT_STATE_FILE: &str = "alert_state.json";
pub const LEGACY_NOTIFICATION_EVENT_STATE_FILE: &str = "notification_event_state.json";

/// The two sections Python's `_SECTION_DEFAULTS` knows about.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Section {
    Alerts,
    NotificationEvents,
}

impl Section {
    pub fn key(self) -> &'static str {
        match self {
            Section::Alerts => "alerts",
            Section::NotificationEvents => "notification_events",
        }
    }

    fn legacy_file_name(self) -> &'static str {
        match self {
            Section::Alerts => LEGACY_ALERT_STATE_FILE,
            Section::NotificationEvents => LEGACY_NOTIFICATION_EVENT_STATE_FILE,
        }
    }

    fn defaults(self) -> Map<String, Value> {
        as_map(default_state().remove(self.key()).unwrap_or_default())
    }
}

/// `_DEFAULT_RUNTIME_STATE`, key order included.
pub fn default_state() -> Map<String, Value> {
    as_map(json!({
        "schema_version": 1,
        "alerts": {
            "schema_version": 1,
            "last_global_notification": null,
            "alert_states": [],
        },
        "notification_events": {
            "schema_version": 1,
            "discussion": {
                "last_issuance_time": null,
                "last_text": null,
                "last_check_time": null,
            },
            "severe_risk": {
                "last_value": null,
                "last_check_time": null,
            },
            "hwo": {
                "last_issuance_time": null,
                "last_text": null,
                "last_summary_signature": null,
                "last_check_time": null,
            },
            "sps": {
                "last_product_ids": [],
                "last_check_time": null,
            },
        },
        "meta": {
            "migrated_from": [],
            "migrated_at": null,
        },
    }))
}

fn as_map(v: Value) -> Map<String, Value> {
    match v {
        Value::Object(m) => m,
        _ => Map::new(),
    }
}

/// `_merge_nested`: overlay `loaded` onto `defaults` without dropping keys.
pub fn merge_nested(
    defaults: &Map<String, Value>,
    loaded: &Map<String, Value>,
) -> Map<String, Value> {
    let mut merged = defaults.clone();
    for (key, value) in loaded {
        let nested = match (value, merged.get(key)) {
            (Value::Object(l), Some(Value::Object(d))) => Some(merge_nested(d, l)),
            _ => None,
        };
        merged.insert(
            key.clone(),
            nested.map(Value::Object).unwrap_or_else(|| value.clone()),
        );
    }
    merged
}

struct Inner {
    config_root: PathBuf,
    cache: Option<Map<String, Value>>,
}

/// Shared handle to the runtime-state file (Python's `RuntimeStateManager`).
#[derive(Clone)]
pub struct RuntimeState(Arc<Mutex<Inner>>);

impl RuntimeState {
    pub fn open(config_root: impl Into<PathBuf>) -> Self {
        Self(Arc::new(Mutex::new(Inner {
            config_root: config_root.into(),
            cache: None,
        })))
    }

    fn lock(&self) -> MutexGuard<'_, Inner> {
        self.0.lock().unwrap_or_else(|e| e.into_inner())
    }

    pub fn config_root(&self) -> PathBuf {
        self.lock().config_root.clone()
    }

    pub fn state_file(&self) -> PathBuf {
        state_file(&self.lock().config_root)
    }

    /// `load_state`: a copy of the whole cached state.
    pub fn load_state(&self) -> Map<String, Value> {
        let mut inner = self.lock();
        inner.cached().clone()
    }

    /// `load_section`: the section from the unified file, else migrated from
    /// the legacy per-feature file (saving it), else the defaults.
    pub fn load_section(&self, section: Section, now: DateTime<Utc>) -> Map<String, Value> {
        let mut inner = self.lock();
        let populated = state_file(&inner.config_root).exists()
            && matches!(inner.cached().get(section.key()), Some(Value::Object(_)));
        if populated {
            return as_map(inner.cached()[section.key()].clone());
        }
        let Some(legacy) = load_legacy_section(&inner.config_root, section) else {
            return section.defaults();
        };
        inner.save_section(section, &legacy, Some(section.legacy_file_name()), now);
        legacy
    }

    /// `save_section`: replace one section (merged over its defaults) and
    /// write the whole file. Returns whether the write succeeded; the cache is
    /// updated either way, as in Python.
    pub fn save_section(
        &self,
        section: Section,
        data: &Map<String, Value>,
        migrated_from: Option<&str>,
        now: DateTime<Utc>,
    ) -> bool {
        self.lock().save_section(section, data, migrated_from, now)
    }

    /// `save_state`: write `state` and make it the cache on success.
    pub fn save_state(&self, state: Map<String, Value>) -> bool {
        self.lock().save_state(state)
    }
}

impl Inner {
    fn cached(&mut self) -> &mut Map<String, Value> {
        if self.cache.is_none() {
            let loaded = load_raw_state(&state_file(&self.config_root));
            self.cache = Some(match loaded {
                Some(l) => merge_nested(&default_state(), &l),
                None => default_state(),
            });
        }
        self.cache.as_mut().expect("cache filled above")
    }

    fn save_section(
        &mut self,
        section: Section,
        data: &Map<String, Value>,
        migrated_from: Option<&str>,
        now: DateTime<Utc>,
    ) -> bool {
        let cached = self.cached();
        cached.insert(
            section.key().into(),
            Value::Object(merge_nested(&section.defaults(), data)),
        );
        if let Some(name) = migrated_from {
            if let Some(Value::Object(meta)) = cached.get_mut("meta") {
                let mut migrated: Vec<Value> = meta
                    .get("migrated_from")
                    .and_then(Value::as_array)
                    .cloned()
                    .unwrap_or_default();
                if !migrated.iter().any(|v| v.as_str() == Some(name)) {
                    migrated.push(name.into());
                }
                meta.insert("migrated_from".into(), Value::Array(migrated));
                if meta.get("migrated_at").is_none_or(Value::is_null) {
                    meta.insert("migrated_at".into(), py::isoformat_utc(&now).into());
                }
            }
        }
        let state = cached.clone();
        self.save_state(state)
    }

    fn save_state(&mut self, state: Map<String, Value>) -> bool {
        let path = state_file(&self.config_root);
        let text = py::json_dumps_indent2(&Value::Object(state.clone()));
        match aw_store::write_atomic(&path, text.as_bytes()) {
            Ok(()) => {
                self.cache = Some(state);
                true
            }
            Err(e) => {
                tracing::warn!("Failed to save runtime state to {}: {e}", path.display());
                false
            }
        }
    }
}

pub fn state_file(config_root: &Path) -> PathBuf {
    config_root.join(STATE_DIR_NAME).join(STATE_FILE_NAME)
}

fn load_json_object(path: &Path) -> Option<Map<String, Value>> {
    let text = std::fs::read_to_string(path).ok()?;
    match serde_json::from_str::<Value>(&text) {
        Ok(Value::Object(m)) => Some(m),
        Ok(_) => {
            tracing::warn!("{} did not contain a JSON object", path.display());
            None
        }
        Err(e) => {
            tracing::warn!("Failed to load runtime state from {}: {e}", path.display());
            None
        }
    }
}

fn load_raw_state(path: &Path) -> Option<Map<String, Value>> {
    load_json_object(path)
}

fn load_legacy_section(config_root: &Path, section: Section) -> Option<Map<String, Value>> {
    let data = load_json_object(&config_root.join(section.legacy_file_name()))?;
    let get = |k: &str| data.get(k).cloned().unwrap_or(Value::Null);
    let overlay = match section {
        Section::Alerts => json!({
            "alert_states": data.get("alert_states").cloned().unwrap_or_else(|| json!([])),
            "last_global_notification": get("last_global_notification"),
        }),
        Section::NotificationEvents => {
            let last_check = get("last_check_time");
            json!({
                "discussion": {
                    "last_issuance_time": get("last_discussion_issuance_time"),
                    "last_text": get("last_discussion_text"),
                    "last_check_time": last_check,
                },
                "severe_risk": {
                    "last_value": get("last_severe_risk"),
                    "last_check_time": last_check,
                },
            })
        }
    };
    Some(merge_nested(&section.defaults(), &as_map(overlay)))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn now() -> DateTime<Utc> {
        "2026-09-25T12:00:00Z".parse().unwrap()
    }

    #[test]
    fn defaults_when_missing_or_corrupt() {
        let dir = tempfile::tempdir().unwrap();
        let rs = RuntimeState::open(dir.path());
        let state = rs.load_state();
        assert_eq!(state["schema_version"], 1);
        assert_eq!(state["alerts"]["alert_states"], json!([]));

        std::fs::create_dir_all(dir.path().join("state")).unwrap();
        std::fs::write(rs.state_file(), "{not valid json").unwrap();
        let rs = RuntimeState::open(dir.path());
        assert_eq!(
            rs.load_state()["notification_events"]["severe_risk"]["last_value"],
            Value::Null
        );
    }

    #[test]
    fn save_state_round_trips_and_keeps_unknown_sections() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::create_dir_all(dir.path().join("state")).unwrap();
        std::fs::write(
            state_file(dir.path()),
            r#"{"future": {"x": 1}, "alerts": {"alert_states": [{"alert_id": "a"}], "extra": true}}"#,
        )
        .unwrap();
        let rs = RuntimeState::open(dir.path());
        let alerts = rs.load_section(Section::Alerts, now());
        assert_eq!(alerts["alert_states"][0]["alert_id"], "a");
        assert!(rs.save_section(Section::NotificationEvents, &Map::new(), None, now()));
        let text = std::fs::read_to_string(rs.state_file()).unwrap();
        let reloaded: Value = serde_json::from_str(&text).unwrap();
        assert_eq!(reloaded["future"]["x"], 1);
        assert_eq!(reloaded["alerts"]["extra"], true);
        let keys: Vec<_> = reloaded.as_object().unwrap().keys().cloned().collect();
        assert_eq!(
            keys,
            [
                "schema_version",
                "alerts",
                "notification_events",
                "meta",
                "future"
            ]
        );
    }

    #[test]
    fn legacy_notification_state_migrates_once() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join(LEGACY_NOTIFICATION_EVENT_STATE_FILE),
            r#"{"last_discussion_issuance_time": "2026-03-16T14:30:00+00:00",
                "last_discussion_text": "Discussion text", "last_severe_risk": 35,
                "last_check_time": "2026-03-16T14:31:00+00:00"}"#,
        )
        .unwrap();
        std::fs::write(dir.path().join(LEGACY_ALERT_STATE_FILE), "{bad json").unwrap();
        let rs = RuntimeState::open(dir.path());
        let events = rs.load_section(Section::NotificationEvents, now());
        assert_eq!(
            events["discussion"]["last_check_time"],
            "2026-03-16T14:31:00+00:00"
        );
        assert_eq!(events["severe_risk"]["last_value"], 35);
        assert_eq!(
            rs.load_section(Section::Alerts, now())["alert_states"],
            json!([])
        );
        let state = rs.load_state();
        assert_eq!(
            state["meta"]["migrated_from"],
            json!(["notification_event_state.json"])
        );
        assert_eq!(state["meta"]["migrated_at"], "2026-09-25T12:00:00+00:00");
    }
}
