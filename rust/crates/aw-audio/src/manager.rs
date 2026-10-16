//! Logic behind the Sound Pack Manager and the Create Sound Pack wizard
//! (`ui/dialogs/soundpack_manager_*.py`, `soundpack_wizard_*.py`). The
//! dialogs call these and show Python's message boxes around them.

use std::fs;
use std::io::{self, Write};
use std::path::{Component, Path, PathBuf};

use serde_json::{Map, Value};

use crate::events::friendly_event_name;
use crate::installer::{copy_tree, safe_extractall};
use crate::pack::{read_json, DEFAULT_PACK};
use crate::py::{get_str, py_float, py_int, py_str, py_truthy, py_type_name, write_python_json};

type JsonMap = Map<String, Value>;

/// `SoundPackInfo`.
#[derive(Debug, Clone, PartialEq)]
pub struct SoundPackInfo {
    pub pack_id: String,
    pub name: String,
    pub author: String,
    pub description: String,
    pub path: PathBuf,
    pub sounds: JsonMap,
}

impl SoundPackInfo {
    /// Pack list entry: `"{name} (by {author})"`.
    pub fn list_label(&self) -> String {
        format!("{} (by {})", self.name, self.author)
    }

    /// Details panel author line.
    pub fn author_label(&self) -> String {
        format!("Author: {}", self.author)
    }

    /// Details panel description (`"No description available"` when blank).
    pub fn description_label(&self) -> &str {
        if self.description.is_empty() {
            "No description available"
        } else {
            &self.description
        }
    }

    /// Sharing and deleting are disabled for the bundled default pack.
    pub fn is_default(&self) -> bool {
        self.pack_id == DEFAULT_PACK
    }
}

/// `_load_sound_packs`: every folder with a readable `pack.json`, in
/// directory iteration order.
pub fn load_sound_packs(soundpacks_dir: &Path) -> Vec<SoundPackInfo> {
    let Ok(entries) = fs::read_dir(soundpacks_dir) else {
        return Vec::new();
    };
    let mut packs = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() || !path.join("pack.json").exists() {
            continue;
        }
        let pack_id = entry.file_name().to_string_lossy().into_owned();
        match read_json(&path.join("pack.json")) {
            Ok(Value::Object(data)) => packs.push(SoundPackInfo {
                name: get_str(&data, "name", &pack_id),
                author: get_str(&data, "author", "Unknown"),
                description: get_str(&data, "description", ""),
                sounds: match data.get("sounds") {
                    Some(Value::Object(s)) => s.clone(),
                    _ => JsonMap::new(),
                },
                pack_id,
                path,
            }),
            Ok(other) => tracing::error!(
                "Failed to load sound pack {pack_id}: '{}' object has no attribute 'get'",
                py_type_name(&other)
            ),
            Err(e) => tracing::error!("Failed to load sound pack {pack_id}: {e}"),
        }
    }
    packs
}

/// `_refresh_pack_list` order: sorted by display name (stable).
pub fn sorted_by_name(packs: &[SoundPackInfo]) -> Vec<&SoundPackInfo> {
    let mut sorted: Vec<&SoundPackInfo> = packs.iter().collect();
    sorted.sort_by(|a, b| a.name.cmp(&b.name));
    sorted
}

/// A `sounds` entry's file name and volume, reading plain entries' volume
/// from the pack's `volumes` object.
fn entry_file_and_volume(entry: &Value, key: &str, volumes: &JsonMap) -> (String, f64) {
    match entry {
        Value::Object(obj) => (
            obj.get("file").map(py_str).unwrap_or_default(),
            obj.get("volume").and_then(py_float).unwrap_or(1.0),
        ),
        other => (
            py_str(other),
            volumes.get(key).and_then(py_float).unwrap_or(1.0),
        ),
    }
}

fn pack_volumes(pack_path: &Path) -> JsonMap {
    match read_json(&pack_path.join("pack.json")) {
        Ok(Value::Object(data)) => match data.get("volumes") {
            Some(Value::Object(v)) => v.clone(),
            _ => JsonMap::new(),
        },
        _ => JsonMap::new(),
    }
}

/// One row of "Sounds in this pack:".
#[derive(Debug, Clone, PartialEq)]
pub struct SoundListItem {
    pub key: String,
    pub file: String,
    pub volume: f64,
    /// `"{friendly} ({file}) @ {pct}% - ✓"` (✗ when the file is missing).
    pub label: String,
    pub exists: bool,
}

/// `_update_pack_details`' sound list, in `pack.json` order.
pub fn sound_list_items(info: &SoundPackInfo) -> Vec<SoundListItem> {
    let volumes = pack_volumes(&info.path);
    info.sounds
        .iter()
        .map(|(key, entry)| {
            let (file, volume) = entry_file_and_volume(entry, key, &volumes);
            let exists = info.path.join(&file).exists();
            let label = format!(
                "{} ({file}) @ {}% - {}",
                friendly_event_name(key),
                py_int(volume * 100.0),
                if exists { "✓" } else { "✗" }
            );
            SoundListItem {
                key: key.clone(),
                file,
                volume,
                label,
                exists,
            }
        })
        .collect()
}

/// `_on_category_changed`: the file mapped to `key`, the volume spinner
/// value (percent) and whether "Set Vol" is enabled.
pub fn category_mapping(info: &SoundPackInfo, key: &str) -> (String, i64, bool) {
    let unmapped = Value::from("");
    let entry = info.sounds.get(key).unwrap_or(&unmapped);
    let (file, volume) = entry_file_and_volume(entry, key, &pack_volumes(&info.path));
    let enabled = !file.is_empty() && info.path.join(&file).exists();
    (file, py_int(volume * 100.0), enabled)
}

/// The file mapped to `key` for "Set Vol" on a category, `None` when the
/// category has no sound ("No sound mapped to this category yet.").
pub fn mapped_file(info: &SoundPackInfo, key: &str) -> Option<String> {
    let entry = info.sounds.get(key).filter(|e| py_truthy(e))?;
    Some(match entry {
        Value::Object(obj) => obj.get("file").map(py_str).unwrap_or_default(),
        other => py_str(other),
    })
}

/// Custom mapping keys are trimmed and lower-cased.
pub fn normalize_custom_key(text: &str) -> String {
    text.trim().to_lowercase()
}

fn load_pack_object(pack_json: &Path) -> Result<JsonMap, String> {
    match read_json(pack_json)? {
        Value::Object(data) => Ok(data),
        other => Err(format!(
            "'{}' object has no attribute 'get'",
            py_type_name(&other)
        )),
    }
}

/// Map `key` to `file` at `volume` (0.0-1.0) in `pack.json`: an inline
/// `{"file", "volume"}` entry below full volume, a plain file name (and no
/// `volumes` override) at full volume. Used by "Set Vol" and the mapping
/// buttons.
pub fn set_sound_mapping(
    pack_path: &Path,
    key: &str,
    file: &str,
    volume: f64,
) -> Result<(), String> {
    let pack_json = pack_path.join("pack.json");
    let mut data = load_pack_object(&pack_json)?;
    let mut sounds = match data.get("sounds") {
        Some(Value::Object(s)) => s.clone(),
        _ => JsonMap::new(),
    };
    if volume < 1.0 {
        let mut entry = JsonMap::new();
        entry.insert("file".into(), Value::from(file));
        entry.insert("volume".into(), Value::from(volume));
        sounds.insert(key.into(), Value::Object(entry));
    } else {
        sounds.insert(key.into(), Value::from(file));
        if let Some(Value::Object(volumes)) = data.get_mut("volumes") {
            volumes.shift_remove(key);
        }
    }
    data.insert("sounds".into(), Value::Object(sounds));
    write_python_json(&pack_json, &Value::Object(data), 2).map_err(|e| e.to_string())
}

fn same_file(a: &Path, b: &Path) -> bool {
    match (a.canonicalize(), b.canonicalize()) {
        (Ok(a), Ok(b)) => a == b,
        _ => false,
    }
}

/// `_apply_mapping`: copy `src` into the pack and map `key` to it. Returns
/// the confirmation, e.g. `Mapped 'severe' to 'siren.wav' at 50%.`
pub fn apply_mapping(
    info: &SoundPackInfo,
    key: &str,
    src: &Path,
    volume: f64,
) -> Result<String, String> {
    let file_name = src
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();
    let dest = info.path.join(&file_name);
    if !same_file(src, &dest) {
        fs::copy(src, &dest).map_err(|e| e.to_string())?;
    }
    set_sound_mapping(&info.path, key, &file_name, volume)?;
    let vol_str = if volume < 1.0 {
        format!(" at {}%", py_int(volume * 100.0))
    } else {
        String::new()
    };
    Ok(format!("Mapped '{key}' to '{file_name}'{vol_str}."))
}

/// `_on_remove_mapping`: `Ok(false)` when `key` is not mapped
/// ("No mapping exists for '{key}'.").
pub fn remove_mapping(info: &SoundPackInfo, key: &str) -> Result<bool, String> {
    let pack_json = info.path.join("pack.json");
    let mut data = load_pack_object(&pack_json)?;
    let mut sounds = match data.get("sounds") {
        Some(Value::Object(s)) => s.clone(),
        _ => JsonMap::new(),
    };
    if sounds.shift_remove(key).is_none() {
        return Ok(false);
    }
    data.insert("sounds".into(), Value::Object(sounds));
    write_python_json(&pack_json, &Value::Object(data), 2).map_err(|e| e.to_string())?;
    Ok(true)
}

/// `_on_duplicate_pack`: copy to `<id>_copy` (then `<id>_copy2`, ...) named
/// `"{name} (Copy)"`. Returns the new pack id.
pub fn duplicate_pack(soundpacks_dir: &Path, info: &SoundPackInfo) -> io::Result<String> {
    let base = format!("{}_copy", info.pack_id);
    let mut candidate = base.clone();
    let mut suffix = 2;
    while soundpacks_dir.join(&candidate).exists() {
        candidate = format!("{base}{suffix}");
        suffix += 1;
    }
    let dest = soundpacks_dir.join(&candidate);
    copy_tree(&info.path, &dest)?;
    let pack_json = dest.join("pack.json");
    let renamed = load_pack_object(&pack_json).and_then(|mut data| {
        data.insert("name".into(), Value::from(format!("{} (Copy)", info.name)));
        write_python_json(&pack_json, &Value::Object(data), 2).map_err(|e| e.to_string())
    });
    if let Err(e) = renamed {
        tracing::error!("Failed to update pack.json: {e}");
    }
    Ok(candidate)
}

/// Edit dialog Save: trimmed fields; a blank name keeps the old one.
pub fn edit_metadata(
    info: &SoundPackInfo,
    name: &str,
    author: &str,
    description: &str,
) -> Result<(), String> {
    let pack_json = info.path.join("pack.json");
    let mut data = load_pack_object(&pack_json)?;
    let name = match name.trim() {
        "" => info.name.as_str(),
        n => n,
    };
    data.insert("name".into(), Value::from(name));
    data.insert("author".into(), Value::from(author.trim()));
    data.insert("description".into(), Value::from(description.trim()));
    write_python_json(&pack_json, &Value::Object(data), 2).map_err(|e| e.to_string())
}

/// `_on_delete_pack` after confirmation. The default pack is never deleted
/// (returns `Ok(false)`).
pub fn delete_pack(info: &SoundPackInfo) -> io::Result<bool> {
    if info.is_default() {
        return Ok(false);
    }
    fs::remove_dir_all(&info.path)?;
    Ok(true)
}

/// Every file under `dir` as `(zip name with '/', path)`.
pub(crate) fn files_for_zip(dir: &Path) -> io::Result<Vec<(String, PathBuf)>> {
    fn walk(root: &Path, dir: &Path, out: &mut Vec<(String, PathBuf)>) -> io::Result<()> {
        for entry in fs::read_dir(dir)? {
            let path = entry?.path();
            if path.is_dir() {
                walk(root, &path, out)?;
            } else if path.is_file() {
                let rel = path.strip_prefix(root).unwrap_or(&path);
                let name: Vec<String> = rel
                    .components()
                    .map(|c| c.as_os_str().to_string_lossy().into_owned())
                    .collect();
                out.push((name.join("/"), path));
            }
        }
        Ok(())
    }
    let mut out = Vec::new();
    walk(dir, dir, &mut out)?;
    Ok(out)
}

/// Deflate every file under `dir` into a ZIP rooted at `dir`.
pub(crate) fn zip_dir<W: io::Write + io::Seek>(dir: &Path, writer: W) -> Result<W, String> {
    let mut zip = zip::ZipWriter::new(writer);
    let options = zip::write::SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated);
    for (name, path) in files_for_zip(dir).map_err(|e| e.to_string())? {
        zip.start_file(name, options).map_err(|e| e.to_string())?;
        zip.write_all(&fs::read(&path).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
    }
    zip.finish().map_err(|e| e.to_string())
}

/// `_on_export_pack`: write the pack folder to `output` as a ZIP.
pub fn export_pack(info: &SoundPackInfo, output: &Path) -> Result<(), String> {
    let file = fs::File::create(output).map_err(|e| e.to_string())?;
    zip_dir(&info.path, file).map(drop)
}

/// A pack brought in by [`import_pack`].
#[derive(Debug, Clone, PartialEq)]
pub struct ImportedPack {
    pub pack_id: String,
    pub pack_name: String,
}

#[derive(Debug, thiserror::Error, PartialEq)]
pub enum ImportError {
    #[error("Invalid sound pack: missing pack.json file.")]
    MissingPackJson,
    #[error("Failed to import sound pack: {0}")]
    Failed(String),
}

/// `_on_import_pack`: the ZIP must hold `pack.json` at its root; the pack id
/// is the lower-cased name with spaces and hyphens as underscores. When the
/// pack exists, `confirm_overwrite(name)` asks "A sound pack named '{name}'
/// already exists. Overwrite?"; `Ok(None)` when declined.
///
/// Unlike Python, a name that is not a plain folder name (empty, `..`,
/// containing a path separator) is refused: Python would delete or write
/// outside the pack folder.
pub fn import_pack(
    soundpacks_dir: &Path,
    zip_path: &Path,
    confirm_overwrite: impl FnOnce(&str) -> bool,
) -> Result<Option<ImportedPack>, ImportError> {
    let failed = |e: String| {
        tracing::error!("Failed to import sound pack: {e}");
        ImportError::Failed(e)
    };
    let file = fs::File::open(zip_path).map_err(|e| failed(e.to_string()))?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| failed(e.to_string()))?;
    if archive.index_for_name("pack.json").is_none() {
        return Err(ImportError::MissingPackJson);
    }
    let data: Value = {
        let entry = archive
            .by_name("pack.json")
            .map_err(|e| failed(e.to_string()))?;
        serde_json::from_reader(entry).map_err(|e| failed(e.to_string()))?
    };
    let Value::Object(data) = data else {
        return Err(failed(format!(
            "'{}' object has no attribute 'get'",
            py_type_name(&data)
        )));
    };
    let pack_name = match data.get("name") {
        None => "Unknown Pack".to_string(),
        Some(Value::String(s)) => s.clone(),
        Some(other) => {
            return Err(failed(format!(
                "'{}' object has no attribute 'lower'",
                py_type_name(other)
            )))
        }
    };
    let pack_id = pack_name.to_lowercase().replace([' ', '-'], "_");
    let mut components = Path::new(&pack_id).components();
    if !matches!(
        (components.next(), components.next()),
        (Some(Component::Normal(_)), None)
    ) {
        return Err(failed(format!("invalid pack name '{pack_name}'")));
    }
    let pack_dir = soundpacks_dir.join(&pack_id);
    if pack_dir.exists() {
        if !confirm_overwrite(&pack_name) {
            return Ok(None);
        }
        fs::remove_dir_all(&pack_dir).map_err(|e| failed(e.to_string()))?;
    }
    fs::create_dir_all(&pack_dir).map_err(|e| failed(e.to_string()))?;
    safe_extractall(&mut archive, &pack_dir).map_err(failed)?;
    Ok(Some(ImportedPack { pack_id, pack_name }))
}

// --- Create Sound Pack wizard ---------------------------------------------

pub const WIZARD_TOTAL_STEPS: u32 = 4;

/// Events ticked by "Select Common" in step 2.
pub const WIZARD_COMMON_EVENTS: &[&str] = &[
    "alert",
    "notify",
    "error",
    "success",
    "data_updated",
    "fetch_error",
    "discussion_update",
    "severe_risk",
    "alert_updated",
    "startup",
    "exit",
    "extreme",
    "severe",
    "moderate",
    "minor",
    "unknown",
];

/// Step header, e.g. `"Step 2 of 4: Select Sound Events"`.
pub fn wizard_header(step: u32) -> String {
    let title = match step {
        1 => "Pack Details",
        2 => "Select Sound Events",
        3 => "Assign Sounds",
        4 => "Preview & Finalize",
        _ => "",
    };
    format!("Step {step} of {WIZARD_TOTAL_STEPS}: {title}")
}

/// The Next button label on `step`.
pub fn wizard_next_label(step: u32) -> &'static str {
    if step == WIZARD_TOTAL_STEPS {
        "Create Pack"
    } else {
        "Next >"
    }
}

/// `WizardState` plus the staging folder chosen files are copied into
/// (removed when the wizard is dropped).
pub struct SoundPackWizard {
    pub pack_name: String,
    pub author: String,
    pub description: String,
    pub selected_alert_keys: Vec<String>,
    /// Event key -> staged file, in the order keys were first assigned.
    pub sound_mappings: Vec<(String, PathBuf)>,
    staging: tempfile::TempDir,
}

impl SoundPackWizard {
    pub fn new() -> io::Result<Self> {
        Ok(Self {
            pack_name: String::new(),
            author: String::new(),
            description: String::new(),
            selected_alert_keys: Vec::new(),
            sound_mappings: Vec::new(),
            staging: tempfile::Builder::new()
                .prefix("aw_soundpack_wizard_")
                .tempdir()?,
        })
    }

    /// Step 1 validation; stores the trimmed fields.
    pub fn set_details(
        &mut self,
        name: &str,
        author: &str,
        description: &str,
    ) -> Result<(), &'static str> {
        self.pack_name = name.trim().to_string();
        self.author = author.trim().to_string();
        self.description = description.trim().to_string();
        if self.pack_name.is_empty() {
            return Err("Please enter a pack name to continue.");
        }
        Ok(())
    }

    /// Step 2 validation; `keys` are the ticked events in display order.
    pub fn set_selected_events(&mut self, keys: Vec<String>) -> Result<(), &'static str> {
        self.selected_alert_keys = keys;
        if self.selected_alert_keys.is_empty() {
            return Err("Please select at least one sound event.");
        }
        Ok(())
    }

    /// Step 3 "Choose...": copy `src` into staging and assign it to `key`.
    /// Returns the file name shown beside the event.
    pub fn stage_sound(&mut self, key: &str, src: &Path) -> io::Result<String> {
        let file_name = src
            .file_name()
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "no file name"))?;
        let dest = self.staging.path().join(file_name);
        if !same_file(src, &dest) {
            fs::copy(src, &dest)?;
        }
        match self.sound_mappings.iter_mut().find(|(k, _)| k == key) {
            Some(slot) => slot.1 = dest,
            None => self.sound_mappings.push((key.to_string(), dest)),
        }
        Ok(file_name.to_string_lossy().into_owned())
    }

    pub fn mapped_path(&self, key: &str) -> Option<&Path> {
        self.sound_mappings
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, p)| p.as_path())
    }

    /// File label in steps 3 and 4 (`"(default)"` in step 4 when unassigned).
    pub fn mapped_file_name(&self, key: &str) -> Option<String> {
        self.mapped_path(key)
            .and_then(Path::file_name)
            .map(|n| n.to_string_lossy().into_owned())
    }

    /// Step 4 summary: `"Pack: {name}  |  Author: {author or 'Unknown'}"`.
    pub fn summary(&self) -> String {
        let author = if self.author.is_empty() {
            "Unknown"
        } else {
            &self.author
        };
        format!("Pack: {}  |  Author: {author}", self.pack_name)
    }

    /// Step 4: `"Sounds assigned: {n} of {selected}"`.
    pub fn assigned_summary(&self) -> String {
        let count = self
            .selected_alert_keys
            .iter()
            .filter(|k| self.mapped_path(k).is_some())
            .count();
        format!(
            "Sounds assigned: {count} of {}",
            self.selected_alert_keys.len()
        )
    }

    /// "Test All Sounds": the first five selected events' files (played
    /// 500 ms apart).
    pub fn test_all_files(&self) -> Vec<PathBuf> {
        self.selected_alert_keys
            .iter()
            .take(5)
            .filter_map(|k| self.mapped_path(k).map(Path::to_path_buf))
            .collect()
    }

    /// Cancel asks "Discard changes and close the wizard?" when true.
    pub fn has_changes(&self) -> bool {
        !self.pack_name.is_empty()
            || !self.author.is_empty()
            || !self.description.is_empty()
            || !self.selected_alert_keys.is_empty()
            || !self.sound_mappings.is_empty()
    }

    /// "Create Pack": a unique folder from the name slug, the staged files
    /// and `pack.json`. Returns the new pack id; on failure the partial
    /// folder is removed and the error is shown as
    /// "Failed to create sound pack:\n{error}".
    pub fn create_pack(&self, soundpacks_dir: &Path) -> Result<String, String> {
        let slug: String = self
            .pack_name
            .trim()
            .to_lowercase()
            .replace([' ', '-'], "_")
            .chars()
            .filter(|c| c.is_alphanumeric() || *c == '_')
            .collect();
        let mut pack_id = slug.clone();
        let mut suffix = 2;
        while soundpacks_dir.join(&pack_id).exists() {
            pack_id = format!("{slug}_{suffix}");
            suffix += 1;
        }
        let pack_dir = soundpacks_dir.join(&pack_id);
        let written = (|| -> io::Result<()> {
            fs::create_dir_all(soundpacks_dir)?;
            fs::create_dir(&pack_dir)?;
            let mut sounds = JsonMap::new();
            for (key, src) in &self.sound_mappings {
                if !src.exists() {
                    continue;
                }
                let name = src.file_name().unwrap_or_default();
                fs::copy(src, pack_dir.join(name))?;
                sounds.insert(key.clone(), Value::from(name.to_string_lossy()));
            }
            let mut data = JsonMap::new();
            data.insert("name".into(), Value::from(self.pack_name.as_str()));
            let author = if self.author.is_empty() {
                "Unknown"
            } else {
                &self.author
            };
            data.insert("author".into(), Value::from(author));
            data.insert("description".into(), Value::from(self.description.as_str()));
            data.insert("version".into(), Value::from("1.0.0"));
            data.insert("sounds".into(), Value::Object(sounds));
            write_python_json(&pack_dir.join("pack.json"), &Value::Object(data), 2)
        })();
        match written {
            Ok(()) => Ok(pack_id),
            Err(e) => {
                tracing::error!("Failed to create sound pack {pack_id}: {e}");
                let _ = fs::remove_dir_all(&pack_dir);
                Err(e.to_string())
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wizard_steps_and_validation() {
        assert_eq!(wizard_header(4), "Step 4 of 4: Preview & Finalize");
        assert_eq!(wizard_next_label(3), "Next >");
        assert_eq!(wizard_next_label(4), "Create Pack");
        let mut wizard = SoundPackWizard::new().unwrap();
        assert!(!wizard.has_changes());
        assert_eq!(
            wizard.set_details("  ", "a", ""),
            Err("Please enter a pack name to continue.")
        );
        assert!(wizard.has_changes());
        assert_eq!(
            wizard.set_selected_events(vec![]),
            Err("Please select at least one sound event.")
        );
    }

    #[test]
    fn common_events_are_the_user_catalog() {
        let catalog: Vec<&str> = crate::events::user_mutable_sound_events()
            .map(|(k, _)| k)
            .collect();
        let mut common = WIZARD_COMMON_EVENTS.to_vec();
        common.sort();
        let mut sorted = catalog.clone();
        sorted.sort();
        assert_eq!(common, sorted);
    }

    #[test]
    fn import_refuses_names_that_escape_the_pack_folder() {
        let tmp = tempfile::tempdir().unwrap();
        let packs = tmp.path().join("soundpacks");
        fs::create_dir_all(packs.join("default")).unwrap();
        for name in ["", "..", "a/b"] {
            let zip_path = tmp.path().join("p.zip");
            let mut w = zip::ZipWriter::new(fs::File::create(&zip_path).unwrap());
            w.start_file("pack.json", zip::write::SimpleFileOptions::default())
                .unwrap();
            w.write_all(serde_json::json!({ "name": name }).to_string().as_bytes())
                .unwrap();
            w.finish().unwrap();
            let result = import_pack(&packs, &zip_path, |_| true);
            assert!(matches!(result, Err(ImportError::Failed(_))), "{name}");
            assert!(packs.join("default").exists());
        }
    }
}
