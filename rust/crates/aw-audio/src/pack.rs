//! Sound pack lookup and validation (`notifications/sound_pack_helpers.py`)
//! and the soundpacks directory (`soundpack_paths.py`).
//!
//! A pack is a folder under the soundpacks directory holding `pack.json` and
//! audio files. `sounds` maps an event key to either a file name or
//! `{"file": ..., "volume": 0.0-1.0}`; an optional `volumes` object gives
//! per-event volumes for plain file-name entries.

use std::fs;
use std::path::{Path, PathBuf};

use serde_json::{Map, Value};

use crate::py::{clamp_volume, py_float, py_str, py_truthy, py_type_name};

pub const DEFAULT_PACK: &str = "default";
pub const DEFAULT_EVENT: &str = "alert";

type JsonMap = Map<String, Value>;

/// Soundpacks directory for this run (`get_soundpacks_dir`).
///
/// Python ships the default pack beside the executable (`soundpacks/`), uses
/// `data/soundpacks/` in portable builds and the repo's `soundpacks/` when
/// run from source. The Rust packages ship `soundpacks/default` beside the
/// executable (`Contents/Resources/soundpacks` in the macOS bundle); a
/// portable run uses `data/soundpacks` when it exists, so a Python portable
/// folder keeps working. Development builds read the repository copy.
pub fn soundpacks_dir() -> PathBuf {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(Path::to_path_buf))
        .unwrap_or_else(|| PathBuf::from("."));
    let portable = aw_store::detect_portable_mode(&exe_dir);
    resolve_soundpacks_dir(&exe_dir, portable)
}

fn resolve_soundpacks_dir(exe_dir: &Path, portable: bool) -> PathBuf {
    let bundled = exe_dir.join("soundpacks");
    if portable {
        let data = exe_dir.join("data").join("soundpacks");
        return if data.is_dir() || !bundled.is_dir() {
            data
        } else {
            bundled
        };
    }
    if bundled.is_dir() {
        return bundled;
    }
    let mac_resources = exe_dir.join("../Resources/soundpacks");
    if cfg!(target_os = "macos") && mac_resources.is_dir() {
        return mac_resources;
    }
    let repo = repo_soundpacks_dir();
    if repo.is_dir() {
        return repo;
    }
    bundled
}

/// The repository's `soundpacks/` folder (source of the bundled default pack).
pub fn repo_soundpacks_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../soundpacks")
}

/// Read `pack.json` as a JSON value.
pub(crate) fn read_json(path: &Path) -> Result<Value, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

/// `load_pack_sounds`: the `sounds` and `volumes` objects (empty when absent
/// or not objects). Errors when the file is unreadable or not a JSON object.
pub fn load_pack_sounds(pack_json: &Path) -> Result<(JsonMap, JsonMap), String> {
    let meta = read_json(pack_json)?;
    let Value::Object(meta) = meta else {
        return Err(format!(
            "'{}' object has no attribute 'get'",
            py_type_name(&meta)
        ));
    };
    let obj = |key: &str| match meta.get(key) {
        Some(Value::Object(m)) => m.clone(),
        _ => JsonMap::new(),
    };
    Ok((obj("sounds"), obj("volumes")))
}

/// `parse_sound_entry`: file name and clamped volume for a `sounds` entry.
pub fn parse_sound_entry(entry: &Value, event: &str, volumes: &JsonMap) -> (String, f64) {
    let (filename, volume) = match entry {
        Value::Object(obj) => (
            obj.get("file")
                .map(py_str)
                .unwrap_or_else(|| format!("{event}.ogg")),
            obj.get("volume").cloned().unwrap_or(Value::from(1.0)),
        ),
        _ => (
            if py_truthy(entry) {
                py_str(entry)
            } else {
                format!("{event}.ogg")
            },
            volumes.get(event).cloned().unwrap_or(Value::from(1.0)),
        ),
    };
    let volume = py_float(&volume).map(clamp_volume).unwrap_or(1.0);
    (filename, volume)
}

/// `get_sound_entry`: resolve an event in a pack, falling back to the same
/// event in the default pack, then to the selected pack's `notify` sound.
pub fn get_sound_entry(
    event: &str,
    pack_dir: &str,
    soundpacks_dir: &Path,
) -> (Option<PathBuf>, f64) {
    let mut pack_path = soundpacks_dir.join(pack_dir);
    let mut pack_json = pack_path.join("pack.json");
    if !pack_json.exists() {
        tracing::warn!(
            "pack.json not found in {}, falling back to default.",
            pack_path.display()
        );
        pack_path = soundpacks_dir.join(DEFAULT_PACK);
        pack_json = pack_path.join("pack.json");
        if !pack_json.exists() {
            tracing::error!("Default sound pack is missing!");
            return (None, 1.0);
        }
    }
    let (sounds, volumes) = match load_pack_sounds(&pack_json) {
        Ok(loaded) => loaded,
        Err(e) => {
            tracing::error!("Error reading sound pack: {e}");
            if pack_dir != DEFAULT_PACK {
                tracing::info!("Falling back to default sound pack due to error");
                return get_sound_entry(event, DEFAULT_PACK, soundpacks_dir);
            }
            return (None, 1.0);
        }
    };
    let default_entry = Value::String(format!("{event}.ogg"));
    let (filename, volume) =
        parse_sound_entry(sounds.get(event).unwrap_or(&default_entry), event, &volumes);
    let sound_file = pack_path.join(&filename);
    if sound_file.exists() {
        return (Some(sound_file), volume);
    }
    if pack_dir != DEFAULT_PACK {
        if let (Some(default_file), default_volume) =
            get_sound_entry(event, DEFAULT_PACK, soundpacks_dir)
        {
            tracing::warn!(
                "Sound file {} not found, using {} from default pack.",
                sound_file.display(),
                default_file.display()
            );
            return (Some(default_file), default_volume);
        }
    }
    if pack_dir != DEFAULT_PACK && event != "notify" {
        let notify_default = Value::String("notify.ogg".into());
        let (fallback_file, fallback_volume) = parse_sound_entry(
            sounds.get("notify").unwrap_or(&notify_default),
            "notify",
            &volumes,
        );
        let fallback_path = pack_path.join(fallback_file);
        if fallback_path.exists() {
            tracing::warn!(
                "Sound file {} not found, using {} from selected pack.",
                sound_file.display(),
                fallback_path.display()
            );
            return (Some(fallback_path), fallback_volume);
        }
    }
    tracing::warn!("Sound file {} not found.", sound_file.display());
    (None, 1.0)
}

/// `find_candidate_sound`: first candidate whose file exists in the pack.
/// A candidate without a mapping tries `<event>.ogg` at its `volumes` level
/// (not clamped, as in Python; playback clamps).
fn find_candidate_sound(
    candidates: &[String],
    pack_path: &Path,
    sounds: &JsonMap,
    volumes: &JsonMap,
) -> Option<(PathBuf, f64)> {
    candidates.iter().find_map(|event| {
        let (filename, volume) = match sounds.get(event).filter(|v| !v.is_null()) {
            Some(entry) => parse_sound_entry(entry, event, volumes),
            None => (
                format!("{event}.ogg"),
                volumes.get(event).and_then(py_float).unwrap_or(1.0),
            ),
        };
        let path = pack_path.join(filename);
        path.exists().then_some((path, volume))
    })
}

/// `get_sound_entry_for_candidates`: the selected pack's first available
/// candidate, then the default pack's, then the default pack's `alert`.
/// An unreadable selected or default `pack.json` yields no sound (Python
/// raises there, so nothing plays).
pub fn get_sound_entry_for_candidates(
    candidates: &[String],
    pack_dir: &str,
    soundpacks_dir: &Path,
) -> (Option<PathBuf>, f64) {
    for pack in [pack_dir, DEFAULT_PACK] {
        let pack_path = soundpacks_dir.join(pack);
        let pack_json = pack_path.join("pack.json");
        if !pack_json.exists() {
            continue;
        }
        match load_pack_sounds(&pack_json) {
            Ok((sounds, volumes)) => {
                if let Some((path, volume)) =
                    find_candidate_sound(candidates, &pack_path, &sounds, &volumes)
                {
                    return (Some(path), volume);
                }
            }
            Err(e) => {
                tracing::debug!("Sound playback failed: {e}");
                return (None, 1.0);
            }
        }
    }
    get_sound_entry(DEFAULT_EVENT, DEFAULT_PACK, soundpacks_dir)
}

/// One installed pack as listed by `get_available_sound_packs`.
#[derive(Debug, Clone, PartialEq)]
pub struct AvailablePack {
    /// Folder name, the value stored in `settings.sound_pack`.
    pub directory: String,
    pub path: PathBuf,
    /// The whole `pack.json` object.
    pub data: JsonMap,
}

impl AvailablePack {
    /// `packs[pid].get("name", pid)` as shown in Settings > Audio.
    pub fn name(&self) -> String {
        self.data
            .get("name")
            .map(py_str)
            .unwrap_or_else(|| self.directory.clone())
    }
}

/// `get_available_sound_packs`: every folder with a readable `pack.json`,
/// in directory iteration order.
pub fn get_available_sound_packs(soundpacks_dir: &Path) -> Vec<AvailablePack> {
    let Ok(entries) = fs::read_dir(soundpacks_dir) else {
        return Vec::new();
    };
    let mut packs = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let pack_json = path.join("pack.json");
        if !pack_json.exists() {
            continue;
        }
        let directory = entry.file_name().to_string_lossy().into_owned();
        match read_json(&pack_json) {
            Ok(Value::Object(data)) => packs.push(AvailablePack {
                directory,
                path,
                data,
            }),
            Ok(other) => tracing::error!(
                "Failed to load sound pack {directory}: '{}' object does not support item assignment",
                py_type_name(&other)
            ),
            Err(e) => tracing::error!("Failed to load sound pack {directory}: {e}"),
        }
    }
    packs
}

/// `sound_pack_prefers_specific_alert_sounds`: an explicit
/// `"specific_alert_sounds": true/false`, otherwise whether the pack maps any
/// legacy specific-alert key such as `tornado_warning`.
pub fn sound_pack_uses_specific_alert_sounds(pack_dir: &str, soundpacks_dir: &Path) -> bool {
    let pack_json = soundpacks_dir.join(pack_dir).join("pack.json");
    if !pack_json.exists() {
        return false;
    }
    match read_json(&pack_json) {
        Ok(Value::Object(data)) => {
            if let Some(Value::Bool(explicit)) = data.get("specific_alert_sounds") {
                return *explicit;
            }
            match data.get("sounds") {
                Some(Value::Object(sounds)) => sounds
                    .keys()
                    .any(|k| crate::events::LEGACY_SOUND_EVENT_KEYS.contains(&k.as_str())),
                _ => false,
            }
        }
        Ok(_) => false,
        Err(e) => {
            tracing::error!("Failed to inspect sound pack {pack_dir}: {e}");
            false
        }
    }
}

/// `validate_sound_pack`: `(is_valid, message)` with Python's messages.
pub fn validate_sound_pack(pack_path: &Path) -> (bool, String) {
    let fail = |msg: String| (false, msg);
    if !pack_path.exists() {
        return fail("Sound pack directory does not exist".into());
    }
    if !pack_path.is_dir() {
        return fail("Sound pack path is not a directory".into());
    }
    let pack_json = pack_path.join("pack.json");
    if !pack_json.exists() {
        return fail("Missing pack.json file".into());
    }
    let data = match read_json(&pack_json) {
        Ok(Value::Object(data)) => data,
        Ok(_) => return fail("Missing 'name' field in pack.json".into()),
        Err(e) => return fail(format!("Invalid JSON in pack.json: {e}")),
    };
    if !data.contains_key("name") {
        return fail("Missing 'name' field in pack.json".into());
    }
    let sounds = match data.get("sounds") {
        None => return fail("Missing 'sounds' field in pack.json".into()),
        Some(Value::Object(sounds)) => sounds,
        Some(other) => {
            return fail(format!(
                "Error validating sound pack: '{}' object has no attribute 'items'",
                py_type_name(other)
            ))
        }
    };
    let missing: Vec<String> = sounds
        .iter()
        .map(|(name, entry)| match entry {
            Value::Object(obj) => obj
                .get("file")
                .map(py_str)
                .unwrap_or_else(|| format!("{name}.ogg")),
            other => py_str(other),
        })
        .filter(|file| !pack_path.join(file).exists())
        .collect();
    if !missing.is_empty() {
        return fail(format!("Missing sound files: {}", missing.join(", ")));
    }
    let volumes = data
        .get("volumes")
        .cloned()
        .unwrap_or(Value::Object(JsonMap::new()));
    let volumes = match volumes {
        Value::Object(v) => v,
        v if py_truthy(&v) => return fail("'volumes' field must be a dictionary".into()),
        v => {
            return fail(format!(
                "Error validating sound pack: '{}' object has no attribute 'items'",
                py_type_name(&v)
            ))
        }
    };
    for (event, volume) in &volumes {
        let Some(vol) = py_float(volume) else {
            return fail(format!(
                "Invalid volume value for '{event}': {}",
                py_str(volume)
            ));
        };
        if vol < 0.0 || vol > 1.0 {
            return fail(format!("Volume for '{event}' must be between 0.0 and 1.0"));
        }
    }
    (true, "Sound pack is valid".into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn portable_prefers_data_folder_then_bundled() {
        let tmp = tempfile::tempdir().unwrap();
        let exe = tmp.path();
        assert_eq!(
            resolve_soundpacks_dir(exe, true),
            exe.join("data").join("soundpacks")
        );
        fs::create_dir_all(exe.join("soundpacks")).unwrap();
        assert_eq!(resolve_soundpacks_dir(exe, true), exe.join("soundpacks"));
        assert_eq!(resolve_soundpacks_dir(exe, false), exe.join("soundpacks"));
        fs::create_dir_all(exe.join("data").join("soundpacks")).unwrap();
        assert_eq!(
            resolve_soundpacks_dir(exe, true),
            exe.join("data").join("soundpacks")
        );
    }

    #[test]
    fn source_runs_use_the_repository_default_pack() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = resolve_soundpacks_dir(tmp.path(), false);
        assert!(dir.join("default").join("pack.json").is_file());
    }
}
