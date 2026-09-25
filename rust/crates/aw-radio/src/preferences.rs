//! NOAA radio preferences: preferred streams, favorites, the last station
//! played and the finder's result limit, in `<config>/noaa_radio_prefs.json`.
//!
//! Ports `noaa_radio/preferences.py`; the file format is shared with the
//! Python app.

use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use serde_json::{json, Map, Value};

pub const PREFS_FILE_NAME: &str = "noaa_radio_prefs.json";
pub const DEFAULT_STATION_LIMIT: usize = 10;

/// One preferences object shared by the playback session, the dialog, the
/// hotkey and alert auto-tune, so whatever plays last is what the hotkey
/// resumes and nobody overwrites another's changes.
pub type SharedPreferences = Arc<Mutex<RadioPreferences>>;

#[derive(Debug, Clone, PartialEq)]
pub struct RadioPreferences {
    /// Call sign → preferred URL, in insertion order (the file keeps it).
    preferred: Vec<(String, String)>,
    favorite_stations: Vec<String>,
    last_station: Option<String>,
    station_limit: Option<usize>,
    path: Option<PathBuf>,
}

impl RadioPreferences {
    /// Load from `path`; `None` keeps preferences in memory only.
    pub fn new(path: Option<PathBuf>) -> Self {
        let mut prefs = Self {
            preferred: Vec::new(),
            favorite_stations: Vec::new(),
            last_station: None,
            station_limit: Some(DEFAULT_STATION_LIMIT),
            path,
        };
        prefs.load();
        prefs
    }

    /// `<config_dir>/noaa_radio_prefs.json`.
    pub fn in_config_dir(config_dir: &Path) -> Self {
        Self::new(Some(config_dir.join(PREFS_FILE_NAME)))
    }

    pub fn shared(self) -> SharedPreferences {
        Arc::new(Mutex::new(self))
    }

    fn load(&mut self) {
        let Some(path) = &self.path else { return };
        let Ok(text) = std::fs::read_to_string(path) else {
            return;
        };
        let data: Map<String, Value> = match serde_json::from_str(&text) {
            Ok(Value::Object(data)) => data,
            Ok(_) => {
                tracing::warn!("Failed to load radio preferences: expected JSON object");
                return;
            }
            Err(e) => {
                tracing::warn!("Failed to load radio preferences: {e}");
                return;
            }
        };

        let string_urls = |map: &Map<String, Value>| {
            map.iter()
                .filter_map(|(k, v)| Some((k.to_uppercase(), v.as_str()?.to_string())))
                .fold(Vec::new(), |mut acc: Vec<(String, String)>, (k, v)| {
                    set_entry(&mut acc, k, v);
                    acc
                })
        };

        if data.contains_key("preferred_streams") || data.contains_key("station_limit") {
            if let Some(Value::Object(streams)) = data.get("preferred_streams") {
                self.preferred = string_urls(streams);
            }
            self.favorite_stations =
                normalize_favorites(data.get("favorite_stations").unwrap_or(&Value::Null));
            self.last_station = data
                .get("last_station")
                .and_then(Value::as_str)
                .and_then(normalize_call_sign);
            self.station_limit = match data.get("station_limit") {
                None => Some(DEFAULT_STATION_LIMIT),
                Some(value) => normalize_station_limit_value(value),
            };
        } else {
            // Legacy format: the whole object is call sign → URL.
            self.preferred = string_urls(&data);
            self.favorite_stations.clear();
            self.station_limit = Some(DEFAULT_STATION_LIMIT);
        }
    }

    fn save(&self) {
        let Some(path) = &self.path else { return };
        let streams: Map<String, Value> = self
            .preferred
            .iter()
            .map(|(k, v)| (k.clone(), Value::String(v.clone())))
            .collect();
        let payload = json!({
            "preferred_streams": streams,
            "station_limit": self.station_limit,
            "favorite_stations": self.favorite_stations,
            "last_station": self.last_station,
        });
        let result = path
            .parent()
            .map_or(Ok(()), std::fs::create_dir_all)
            .and_then(|()| std::fs::write(path, crate::python_json(&payload)));
        if let Err(e) = result {
            tracing::warn!("Failed to save radio preferences: {e}");
        }
    }

    #[cfg(test)]
    pub(crate) fn preferred_streams(&self) -> &[(String, String)] {
        &self.preferred
    }

    pub fn get_preferred_url(&self, call_sign: &str) -> Option<String> {
        let key = call_sign.to_uppercase();
        self.preferred
            .iter()
            .find(|(k, _)| *k == key)
            .map(|(_, v)| v.clone())
    }

    pub fn set_preferred_url(&mut self, call_sign: &str, url: &str) {
        set_entry(
            &mut self.preferred,
            call_sign.to_uppercase(),
            url.to_string(),
        );
        self.save();
    }

    pub fn clear_preferred_url(&mut self, call_sign: &str) {
        let key = call_sign.to_uppercase();
        let before = self.preferred.len();
        self.preferred.retain(|(k, _)| *k != key);
        if self.preferred.len() != before {
            self.save();
        }
    }

    /// Move the preferred URL (if set and present) to the front.
    pub fn reorder_urls(&self, call_sign: &str, urls: &[String]) -> Vec<String> {
        match self.get_preferred_url(call_sign) {
            Some(preferred) if urls.contains(&preferred) => std::iter::once(preferred.clone())
                .chain(urls.iter().filter(|u| **u != preferred).cloned())
                .collect(),
            _ => urls.to_vec(),
        }
    }

    pub fn get_favorite_stations(&self) -> Vec<String> {
        self.favorite_stations.clone()
    }

    pub fn is_favorite_station(&self, call_sign: &str) -> bool {
        self.favorite_stations
            .contains(&call_sign.trim().to_uppercase())
    }

    pub fn set_favorite_stations<S: AsRef<str>>(&mut self, call_signs: &[S]) {
        let values: Vec<Value> = call_signs
            .iter()
            .map(|s| Value::String(s.as_ref().to_string()))
            .collect();
        self.favorite_stations = normalize_favorites(&Value::Array(values));
        self.save();
    }

    pub fn add_favorite_station(&mut self, call_sign: &str) {
        let normalized = call_sign.trim().to_uppercase();
        if normalized.is_empty() || self.favorite_stations.contains(&normalized) {
            return;
        }
        self.favorite_stations.push(normalized);
        self.save();
    }

    pub fn remove_favorite_station(&mut self, call_sign: &str) {
        let normalized = call_sign.trim().to_uppercase();
        if !self.favorite_stations.contains(&normalized) {
            return;
        }
        self.favorite_stations.retain(|f| *f != normalized);
        self.save();
    }

    /// The station that played most recently.
    pub fn get_last_station(&self) -> Option<String> {
        self.last_station.clone()
    }

    /// Remember the last station; blank clears it. Saves only on change.
    pub fn set_last_station(&mut self, call_sign: Option<&str>) {
        let normalized = call_sign.and_then(normalize_call_sign);
        if normalized == self.last_station {
            return;
        }
        self.last_station = normalized;
        self.save();
    }

    /// Finder result limit; `None` means all stations.
    pub fn get_station_limit(&self) -> Option<usize> {
        self.station_limit
    }

    pub fn set_station_limit(&mut self, limit: Option<usize>) {
        self.station_limit = match limit {
            Some(0) => Some(DEFAULT_STATION_LIMIT),
            other => other,
        };
        self.save();
    }
}

fn set_entry(entries: &mut Vec<(String, String)>, key: String, value: String) {
    match entries.iter_mut().find(|(k, _)| *k == key) {
        Some(entry) => entry.1 = value,
        None => entries.push((key, value)),
    }
}

fn normalize_call_sign(value: &str) -> Option<String> {
    Some(value.trim().to_uppercase()).filter(|s| !s.is_empty())
}

/// Python `_normalize_station_limit` for a value read from disk.
fn normalize_station_limit_value(value: &Value) -> Option<usize> {
    match value {
        Value::Null => None,
        Value::String(s) if s.to_lowercase() == "all" => None,
        Value::Number(n) => match n.as_u64() {
            Some(n) if n > 0 => Some(n as usize),
            _ => Some(DEFAULT_STATION_LIMIT),
        },
        _ => Some(DEFAULT_STATION_LIMIT),
    }
}

/// Unique upper-case favorites in saved order; `str(item)` for non-strings.
fn normalize_favorites(value: &Value) -> Vec<String> {
    let Value::Array(items) = value else {
        return Vec::new();
    };
    let mut favorites: Vec<String> = Vec::new();
    for item in items {
        let text = match item {
            Value::Null => String::new(),
            Value::String(s) => s.clone(),
            Value::Bool(true) => "True".into(),
            Value::Bool(false) => "False".into(),
            other => other.to_string(),
        };
        let call_sign = text.trim().to_uppercase();
        if !call_sign.is_empty() && !favorites.contains(&call_sign) {
            favorites.push(call_sign);
        }
    }
    favorites
}

#[cfg(test)]
mod tests {
    use super::*;

    fn prefs_at(dir: &Path) -> RadioPreferences {
        RadioPreferences::in_config_dir(dir)
    }

    #[test]
    fn preferred_urls_persist_and_reorder() {
        let dir = tempfile::tempdir().unwrap();
        let mut prefs = prefs_at(dir.path());
        assert_eq!(prefs.get_preferred_url("KEC49"), None);
        prefs.set_preferred_url("kec49", "https://b");
        assert_eq!(
            prefs_at(dir.path()).get_preferred_url("KEC49").as_deref(),
            Some("https://b")
        );

        let urls = vec![
            "https://a".to_string(),
            "https://b".into(),
            "https://c".into(),
        ];
        assert_eq!(
            prefs.reorder_urls("KEC49", &urls),
            ["https://b", "https://a", "https://c"]
        );
        assert_eq!(prefs.reorder_urls("WXK27", &urls), urls);
        prefs.set_preferred_url("WXK27", "https://z");
        assert_eq!(prefs.reorder_urls("WXK27", &urls), urls);

        prefs.clear_preferred_url("kec49");
        assert_eq!(prefs_at(dir.path()).get_preferred_url("KEC49"), None);
    }

    #[test]
    fn station_limit_defaults_persists_and_all_is_none() {
        let dir = tempfile::tempdir().unwrap();
        let mut prefs = prefs_at(dir.path());
        assert_eq!(prefs.get_station_limit(), Some(10));
        prefs.set_station_limit(Some(50));
        assert_eq!(prefs_at(dir.path()).get_station_limit(), Some(50));
        prefs.set_station_limit(None);
        assert_eq!(prefs_at(dir.path()).get_station_limit(), None);
        let text = std::fs::read_to_string(dir.path().join(PREFS_FILE_NAME)).unwrap();
        assert!(text.contains("\"station_limit\": null"), "{text}");
    }

    #[test]
    fn legacy_file_loads_urls_with_defaults() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join(PREFS_FILE_NAME),
            r#"{"kec49": "https://legacy", "bad": 5}"#,
        )
        .unwrap();
        let prefs = prefs_at(dir.path());
        assert_eq!(
            prefs.get_preferred_url("KEC49").as_deref(),
            Some("https://legacy")
        );
        assert_eq!(prefs.get_preferred_url("BAD"), None);
        assert_eq!(prefs.get_station_limit(), Some(10));
        assert!(prefs.get_favorite_stations().is_empty());
    }

    #[test]
    fn favorites_and_last_station() {
        let dir = tempfile::tempdir().unwrap();
        let mut prefs = prefs_at(dir.path());
        prefs.add_favorite_station(" wxk27 ");
        prefs.add_favorite_station("KEC49");
        prefs.add_favorite_station("WXK27");
        prefs.remove_favorite_station("kec49");
        prefs.add_favorite_station("KEC49");
        assert_eq!(
            prefs_at(dir.path()).get_favorite_stations(),
            ["WXK27", "KEC49"]
        );
        assert!(prefs.is_favorite_station("wxk27"));

        prefs.set_last_station(Some("wxk27"));
        assert_eq!(
            prefs_at(dir.path()).get_last_station().as_deref(),
            Some("WXK27")
        );
        prefs.set_last_station(Some("  "));
        assert_eq!(prefs_at(dir.path()).get_last_station(), None);
    }

    #[test]
    fn corrupt_or_odd_files_fail_soft() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(PREFS_FILE_NAME);
        std::fs::write(&path, "{not json").unwrap();
        assert_eq!(prefs_at(dir.path()).get_station_limit(), Some(10));
        std::fs::write(&path, r#"{"preferred_streams": {}, "last_station": 42}"#).unwrap();
        assert_eq!(prefs_at(dir.path()).get_last_station(), None);
        std::fs::write(&path, "[1, 2]").unwrap();
        assert!(prefs_at(dir.path()).get_favorite_stations().is_empty());
    }

    #[test]
    fn memory_only_and_parent_dirs() {
        let mut prefs = RadioPreferences::new(None);
        prefs.set_preferred_url("KEC49", "https://x");
        assert_eq!(
            prefs.get_preferred_url("KEC49").as_deref(),
            Some("https://x")
        );

        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("a").join("b");
        prefs_at(&nested).set_last_station(Some("KEC49"));
        assert!(nested.join(PREFS_FILE_NAME).exists());
    }

    fn state(prefs: &RadioPreferences) -> Value {
        json!({
            "preferred": prefs.preferred_streams().iter().map(|(k, v)| json!([k, v])).collect::<Vec<_>>(),
            "favorites": prefs.get_favorite_stations(),
            "last_station": prefs.get_last_station(),
            "station_limit": prefs.get_station_limit(),
        })
    }

    #[test]
    fn golden_file_round_trips() {
        let golden = crate::golden("files.json");
        let dir = tempfile::tempdir().unwrap();
        for case in golden["preferences"].as_array().unwrap() {
            let name = case["name"].as_str().unwrap();
            let path = dir.path().join(format!("{name}.json"));
            if let Some(text) = case["file"].as_str() {
                std::fs::write(&path, text).unwrap();
            }
            let mut prefs = RadioPreferences::new(Some(path.clone()));
            assert_eq!(state(&prefs), case["loaded"], "{name}: loaded");
            for op in case["ops"].as_array().unwrap() {
                let arg = |i: usize| op[i].as_str().unwrap_or_default();
                match arg(0) {
                    "set_preferred_url" => prefs.set_preferred_url(arg(1), arg(2)),
                    "clear_preferred_url" => prefs.clear_preferred_url(arg(1)),
                    "add_favorite_station" => prefs.add_favorite_station(arg(1)),
                    "remove_favorite_station" => prefs.remove_favorite_station(arg(1)),
                    "set_favorite_stations" => {
                        let list: Vec<String> = serde_json::from_value(op[1].clone()).unwrap();
                        prefs.set_favorite_stations(&list);
                    }
                    "set_last_station" => prefs.set_last_station(op[1].as_str()),
                    "set_station_limit" => {
                        prefs.set_station_limit(op[1].as_u64().map(|n| n as usize))
                    }
                    other => panic!("unknown op {other}"),
                }
            }
            assert_eq!(state(&prefs), case["after"], "{name}: after");
            let saved = std::fs::read_to_string(&path).ok();
            assert_eq!(
                saved.as_deref(),
                case["saved_text"].as_str(),
                "{name}: file"
            );
        }
    }
}
