//! Settings, locations and encrypted API key import/export, backup/restore
//! and resets (`config/import_export*.py`, `config/settings.py`) and the
//! installed-to-portable copy (`ui/dialogs/settings_dialog_portable.py`).
//!
//! Functions return `bool` like Python's and log the reason on failure; the
//! UI shows its own success/failure messages. Functions that save take the
//! config file (or folder) as an `Option`: sample-data runs pass `None` and
//! only the in-memory config changes.
//!
//! Deliberate divergences from Python: importing settings keeps the active
//! API keys (Python blanks them, so the next Save deletes them from the
//! keyring or the portable bundle), and resetting to defaults keeps the saved
//! locations, the current location and the API keys (Python empties the
//! locations its confirmation promises to keep).

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use aw_core::display::pyfmt::py_str;
use aw_core::settings::{AppConfig, AppSettings};
use aw_core::Location;
use aw_store::secrets::{self, API_KEY_NAMES};
use serde_json::{json, Map, Value};

/// Where API keys are read from and written to. Tests use a map so they never
/// touch the real keyring.
pub trait KeyStore {
    fn get(&self, name: &str) -> Option<String>;
    fn set(&mut self, name: &str, value: &str) -> bool;
}

/// The system keyring (`SecureStorage`).
pub struct SystemKeyring;

impl KeyStore for SystemKeyring {
    fn get(&self, name: &str) -> Option<String> {
        secrets::get_password(name)
    }

    fn set(&mut self, name: &str, value: &str) -> bool {
        secrets::set_password(name, value)
    }
}

impl KeyStore for BTreeMap<String, String> {
    fn get(&self, name: &str) -> Option<String> {
        BTreeMap::get(self, name).cloned()
    }

    fn set(&mut self, name: &str, value: &str) -> bool {
        self.insert(name.into(), value.into());
        true
    }
}

/// `str(datetime.now())`: microseconds only when non-zero.
pub fn exported_at(now: chrono::NaiveDateTime) -> String {
    if now.and_utc().timestamp_subsec_micros() == 0 {
        now.format("%Y-%m-%d %H:%M:%S").to_string()
    } else {
        now.format("%Y-%m-%d %H:%M:%S%.6f").to_string()
    }
}

fn now_string() -> String {
    exported_at(chrono::Local::now().naive_local())
}

fn location_json(location: &Location, with_country: bool) -> Value {
    let mut entry = json!({
        "name": location.name,
        "latitude": location.latitude,
        "longitude": location.longitude,
    });
    if let Some(code) = location
        .country_code
        .as_deref()
        .filter(|c| with_country && !c.is_empty())
    {
        entry["country_code"] = json!(code);
    }
    entry
}

/// The document `export_settings` writes: settings without API keys, and
/// locations with their country code.
pub fn settings_export(config: &AppConfig, exported_at: &str) -> Value {
    json!({
        "settings": serde_json::to_value(&config.settings).unwrap_or_default(),
        "locations": config.locations.iter().map(|l| location_json(l, true)).collect::<Vec<_>>(),
        "exported_at": exported_at,
    })
}

/// The document `export_locations` writes (no country codes, as in Python).
pub fn locations_export(config: &AppConfig, exported_at: &str) -> Value {
    json!({
        "locations": config.locations.iter().map(|l| location_json(l, false)).collect::<Vec<_>>(),
        "exported_at": exported_at,
    })
}

fn write_json(path: &Path, value: &Value) -> std::io::Result<()> {
    let text = serde_json::to_string_pretty(value).map_err(std::io::Error::other)?;
    std::fs::write(path, text)
}

fn read_json(path: &Path) -> Result<Value, String> {
    let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| format!("invalid JSON: {e}"))
}

pub fn export_settings(config: &AppConfig, path: &Path) -> bool {
    match write_json(path, &settings_export(config, &now_string())) {
        Ok(()) => {
            tracing::info!("Settings exported to {}", path.display());
            true
        }
        Err(e) => {
            tracing::error!("Failed to export settings: {e}");
            false
        }
    }
}

pub fn export_locations(config: &AppConfig, path: &Path) -> bool {
    match write_json(path, &locations_export(config, &now_string())) {
        Ok(()) => {
            tracing::info!("Locations exported to {}", path.display());
            true
        }
        Err(e) => {
            tracing::error!("Failed to export locations: {e}");
            false
        }
    }
}

/// `_coerce_location_entry`: `(name, lat, lon, country_code)` or `None`.
fn coerce_location(entry: &Value) -> Option<Location> {
    let obj = entry.as_object()?;
    // `str(name)` of a truthy name.
    let name = match obj.get("name")? {
        Value::String(s) if !s.is_empty() => s.clone(),
        v @ Value::Number(n) if n.as_f64() != Some(0.0) => py_str(v),
        Value::Bool(true) => "True".into(),
        _ => return None,
    };
    let float = |v: Option<&Value>| -> Option<f64> {
        match v? {
            Value::Number(n) => n.as_f64(),
            Value::Bool(b) => Some(f64::from(u8::from(*b))),
            Value::String(s) => crate::py_strip(s).parse().ok(),
            _ => None,
        }
    };
    let mut location = Location::new(
        name,
        float(obj.get("latitude"))?,
        float(obj.get("longitude"))?,
    );
    location.country_code = obj
        .get("country_code")
        .and_then(Value::as_str)
        .filter(|c| !c.is_empty())
        .map(str::to_uppercase);
    Some(location)
}

/// Add locations whose names are new; returns `(imported, invalid)`.
fn merge_locations(
    data: &Map<String, Value>,
    locations: &mut Vec<Location>,
) -> Option<(usize, usize)> {
    let entries = match data.get("locations") {
        None => return Some((0, 0)),
        Some(Value::Array(entries)) => entries,
        Some(_) => return None,
    };
    let (mut imported, mut invalid) = (0, 0);
    for entry in entries {
        let Some(location) = coerce_location(entry) else {
            invalid += 1;
            tracing::warn!("Skipped invalid location entry: {entry}");
            continue;
        };
        if locations.iter().any(|l| l.name == location.name) {
            tracing::info!("Skipped existing location: {}", location.name);
            continue;
        }
        tracing::info!("Imported location: {}", location.name);
        locations.push(location);
        imported += 1;
    }
    Some((imported, invalid))
}

/// Import locations from an export file, saving when any were added. Fails
/// when the file is unreadable or every new entry was invalid.
pub fn import_locations(config: &mut AppConfig, path: &Path, config_file: &Path) -> bool {
    let data = match read_json(path) {
        Ok(Value::Object(data)) => data,
        Ok(_) => {
            tracing::error!("Failed to import locations: root must be a JSON object");
            return false;
        }
        Err(e) => {
            tracing::error!("Failed to import locations: {e}");
            return false;
        }
    };
    let Some((imported, invalid)) = merge_locations(&data, &mut config.locations) else {
        tracing::error!("Failed to import locations: 'locations' must be a list");
        return false;
    };
    let success = if imported > 0 {
        aw_store::save_config(config_file, config).is_ok()
    } else {
        invalid == 0
    };
    tracing::info!("Imported {imported} new locations; skipped {invalid} invalid entries");
    success
}

/// Save `config`; `None` (sample-data runs) keeps it in memory only.
fn save(config: &AppConfig, config_file: Option<&Path>) -> bool {
    config_file.is_none_or(|file| {
        aw_store::save_config(file, config)
            .inspect_err(|e| tracing::error!("Failed to save config: {e}"))
            .is_ok()
    })
}

/// Carry the API keys active in `from` over to `to` where `to` has none.
fn keep_api_keys(to: &mut AppSettings, from: &mut AppSettings) {
    for name in API_KEY_NAMES {
        if let (Some(new), Some(old)) = (
            secrets::api_key_mut(to, name),
            secrets::api_key_mut(from, name),
        ) {
            if new.is_empty() {
                *new = std::mem::take(old);
            }
        }
    }
}

/// Replace the settings with an export's, add its new locations and save.
/// The active API keys are kept unless the file carries its own.
pub fn import_settings(config: &mut AppConfig, path: &Path, config_file: Option<&Path>) -> bool {
    if !path.exists() {
        tracing::error!("Import file not found: {}", path.display());
        return false;
    }
    let mut data = match read_json(path) {
        Ok(Value::Object(data)) => data,
        Ok(_) => {
            tracing::error!("Invalid settings file: root element must be a JSON object");
            return false;
        }
        Err(e) => {
            tracing::error!("Failed to parse settings file ({e})");
            return false;
        }
    };
    let Some(Value::Object(mut settings_data)) = data.remove("settings") else {
        tracing::error!(
            "Invalid settings file: missing or invalid 'settings' key (expected object)"
        );
        return false;
    };
    const VALID_SOURCES: [&str; 4] = ["auto", "nws", "openmeteo", "pirateweather"];
    if let Some(source) = settings_data.get("data_source").filter(|v| !v.is_null()) {
        if !source.as_str().is_some_and(|s| VALID_SOURCES.contains(&s)) {
            tracing::warn!(
                "Invalid data_source '{source}' in imported settings, will use 'auto'. \
                 Valid values: {}",
                VALID_SOURCES.join(", ")
            );
            settings_data.insert("data_source".into(), json!("auto"));
        }
    }
    let field_count = settings_data.len();
    let present: Vec<String> = settings_data.keys().cloned().collect();
    let mut imported = AppSettings::from_python_dict(settings_data);
    keep_api_keys(&mut imported, &mut config.settings);
    config.settings = imported;
    if let Some((n, _)) = merge_locations(&data, &mut config.locations).filter(|(n, _)| *n > 0) {
        tracing::info!("Imported {n} locations from settings file");
    }
    if !save(config, config_file) {
        tracing::error!("Failed to save imported settings");
        return false;
    }
    tracing::info!("Successfully imported {field_count} settings");
    if let Ok(Value::Object(all)) = serde_json::to_value(&config.settings) {
        let missing: Vec<&String> = all.keys().filter(|k| !present.contains(k)).collect();
        if !missing.is_empty() {
            let shown: Vec<&str> = missing.iter().take(5).map(|s| s.as_str()).collect();
            tracing::info!(
                "Used defaults for {} fields not present in import: {}{}",
                missing.len(),
                shown.join(", "),
                if missing.len() > 5 { "..." } else { "" }
            );
        }
    }
    true
}

/// API keys to export: the in-memory settings first, then the keyring.
fn collect_api_keys(
    settings: &mut AppSettings,
    keyring: &dyn KeyStore,
) -> BTreeMap<String, String> {
    API_KEY_NAMES
        .iter()
        .filter_map(|name| {
            let in_memory = secrets::api_key_mut(settings, name)
                .map(|v| v.clone())
                .filter(|v| !v.is_empty());
            let value = in_memory
                .or_else(|| keyring.get(name))
                .filter(|v| !v.is_empty())?;
            Some((name.to_string(), value))
        })
        .collect()
}

/// Write the encrypted `*.keys` bundle. Fails when there is nothing to export.
pub fn export_encrypted_api_keys(
    settings: &mut AppSettings,
    keyring: &dyn KeyStore,
    path: &Path,
    passphrase: &str,
) -> bool {
    let keys = collect_api_keys(settings, keyring);
    if keys.is_empty() {
        tracing::warn!("No API keys available in secure storage to export");
        return false;
    }
    match secrets::write_bundle(path, &keys, passphrase) {
        Ok(()) => {
            tracing::info!("Encrypted API keys exported to {}", path.display());
            true
        }
        Err(e) => {
            tracing::error!("Failed to export encrypted API keys: {e}");
            false
        }
    }
}

/// Import a `*.keys` / legacy `*.awkeys` bundle: every key goes into the
/// keyring (in portable mode too, as Python does), then becomes active in
/// `settings`: straight from the bundle when `portable` (sample-data runs
/// too), otherwise reread from the keyring. Keys the bundle lacks are never
/// deleted. False when the bundle is unreadable, the passphrase is wrong, it
/// holds no supported key, or a keyring write failed.
pub fn import_encrypted_api_keys(
    settings: &mut AppSettings,
    keyring: &mut dyn KeyStore,
    path: &Path,
    passphrase: &str,
    portable: bool,
) -> bool {
    let envelope = match read_json(path) {
        Ok(v @ Value::Object(_)) => v,
        Ok(_) => {
            tracing::error!("Invalid encrypted API key bundle format");
            return false;
        }
        Err(e) => {
            tracing::error!("Failed to import encrypted API keys: {e}");
            return false;
        }
    };
    let keys = match secrets::decrypt_bundle(&envelope, passphrase) {
        Ok(keys) => keys,
        Err(e) => {
            tracing::error!("Failed to import encrypted API keys: {e}");
            return false;
        }
    };
    let (mut imported, mut failed) = (0, false);
    for name in API_KEY_NAMES {
        let Some(value) = keys.get(name).filter(|v| !v.is_empty()) else {
            continue;
        };
        if keyring.set(name, value) {
            imported += 1;
        } else {
            tracing::error!("Failed to import API key into secure storage: {name}");
            failed = true;
        }
    }
    if imported == 0 && !failed {
        tracing::warn!("Encrypted API key bundle did not contain supported keys");
        return false;
    }
    tracing::info!("Imported {imported} API keys into secure storage");
    for name in API_KEY_NAMES {
        let Some(field) = secrets::api_key_mut(settings, name) else {
            continue;
        };
        if portable {
            if let Some(value) = keys.get(name).filter(|v| !v.is_empty()) {
                *field = value.clone();
            }
        } else {
            *field = keyring.get(name).unwrap_or_default();
        }
    }
    !failed
}

/// Copy the config file to `backup_path` (default `accessiweather.json.backup`).
pub fn backup_config(config_file: &Path, backup_path: Option<&Path>) -> bool {
    let target = backup_path.map_or_else(
        || config_file.with_extension("json.backup"),
        Path::to_path_buf,
    );
    if !config_file.exists() {
        tracing::warn!("No config file to backup");
        return false;
    }
    match std::fs::copy(config_file, &target) {
        Ok(_) => {
            tracing::info!("Config backed up to {}", target.display());
            true
        }
        Err(e) => {
            tracing::error!("Failed to backup config: {e}");
            false
        }
    }
}

/// Copy a backup over the config file and load it.
pub fn restore_config(config_file: &Path, backup_path: &Path) -> Option<AppConfig> {
    if !backup_path.exists() {
        tracing::error!("Backup file not found: {}", backup_path.display());
        return None;
    }
    if let Err(e) = std::fs::copy(backup_path, config_file) {
        tracing::error!("Failed to restore config: {e}");
        return None;
    }
    let channel = crate::update::default_update_channel(crate::update::build_tag());
    let config = match aw_store::load_config(config_file, channel) {
        Ok((config, defaulted)) => {
            if defaulted {
                let _ = aw_store::save_config(config_file, &config);
            }
            config
        }
        Err(e) => {
            tracing::error!("Failed to load config: {e}");
            AppConfig::default()
        }
    };
    tracing::info!("Config restored from {}", backup_path.display());
    Some(config)
}

/// Settings > Advanced > Reset: default settings, saved. The saved
/// locations, the current location and the active API keys stay.
pub fn reset_to_defaults(config: &mut AppConfig, config_file: Option<&Path>) -> bool {
    tracing::info!("Resetting configuration to defaults");
    let mut settings = AppSettings::default();
    keep_api_keys(&mut settings, &mut config.settings);
    config.settings = settings;
    save(config, config_file)
}

/// Delete everything in the config folder (settings, locations, caches,
/// state, a portable key bundle) and save a default configuration. With no
/// folder (sample-data runs) only the in-memory config is reset.
pub fn reset_all_data(config: &mut AppConfig, config_dir: Option<&Path>) -> bool {
    let Some(dir) = config_dir else {
        *config = AppConfig::default();
        return true;
    };
    let entries = match std::fs::read_dir(dir) {
        Ok(entries) => entries,
        Err(e) => {
            tracing::error!("Failed to reset all data: {e}");
            return false;
        }
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let result = if path.is_dir() {
            std::fs::remove_dir_all(&path)
        } else {
            std::fs::remove_file(&path)
        };
        if let Err(e) = result {
            tracing::warn!("Failed to remove {}: {e}", path.display());
        }
    }
    *config = AppConfig::default();
    if let Err(e) = std::fs::create_dir_all(dir) {
        tracing::error!("Failed to reset all data: {e}");
        return false;
    }
    save(config, Some(&dir.join(aw_store::CONFIG_FILE_NAME)))
}

// Installed -> portable copy -----------------------------------------------

/// The installed edition's config folder (`_get_installed_config_dir`).
pub fn installed_config_dir() -> Option<PathBuf> {
    aw_store::platform_base_dir().map(|base| base.join("Config"))
}

fn read_config_object(config_dir: &Path) -> Result<Map<String, Value>, String> {
    let file = config_dir.join(aw_store::CONFIG_FILE_NAME);
    if !file.exists() {
        return Err(format!(
            "Required config file not found: {}",
            file.display()
        ));
    }
    match read_json(&file)? {
        Value::Object(map) => Ok(map),
        _ => Err(format!(
            "Invalid config payload in {}: expected object",
            file.display()
        )),
    }
}

fn list_len(map: &Map<String, Value>, key: &str) -> usize {
    map.get(key).and_then(Value::as_array).map_or(0, Vec::len)
}

fn object<'a>(map: &'a Map<String, Value>, key: &str) -> Option<&'a Map<String, Value>> {
    map.get(key).and_then(Value::as_object)
}

/// Whether the installed config has anything worth copying; the error is
/// the "Details:" reason the UI shows.
pub fn check_installed_config(installed_dir: &Path) -> Result<(), &'static str> {
    if !installed_dir.is_dir() {
        return Err("Installed config directory not found.");
    }
    if !std::fs::read_dir(installed_dir).is_ok_and(|mut e| e.next().is_some()) {
        return Err("Installed config directory is empty.");
    }
    let file = installed_dir.join(aw_store::CONFIG_FILE_NAME);
    if !file.is_file() {
        return Err("Required config file accessiweather.json is missing.");
    }
    match std::fs::metadata(&file) {
        Ok(meta) if meta.len() == 0 => return Err("Config file accessiweather.json is empty."),
        Ok(_) => {}
        Err(_) => return Err("Could not read accessiweather.json."),
    }
    let config = read_config_object(installed_dir)
        .map_err(|_| "Config file accessiweather.json is invalid or unreadable.")?;
    if list_len(&config, "locations") == 0 {
        return Err("Installed config has no saved locations to transfer.");
    }
    Ok(())
}

/// Copy the transferable files (only `accessiweather.json`); returns the
/// names copied.
pub fn copy_installed_config(
    installed_dir: &Path,
    portable_dir: &Path,
) -> std::io::Result<Vec<String>> {
    std::fs::create_dir_all(portable_dir)?;
    let mut copied = Vec::new();
    let name = aw_store::CONFIG_FILE_NAME;
    let source = installed_dir.join(name);
    if source.exists() {
        std::fs::copy(&source, portable_dir.join(name))?;
        copied.push(name.to_string());
    }
    Ok(copied)
}

/// Problems with the copied config (`_validate_portable_copy`).
pub fn validate_portable_copy(
    installed_dir: &Path,
    portable_dir: &Path,
) -> Result<(), Vec<String>> {
    let (src, dst) = match (
        read_config_object(installed_dir),
        read_config_object(portable_dir),
    ) {
        (Ok(src), Ok(dst)) => (src, dst),
        (Err(e), _) | (_, Err(e)) => return Err(vec![e]),
    };
    let empty = Map::new();
    let src_settings = object(&src, "settings").unwrap_or(&empty);
    let dst_settings = object(&dst, "settings").unwrap_or(&empty);
    let mut messages = Vec::new();
    for key in ["ai_model_preference", "data_source", "temperature_unit"] {
        let (a, b) = (src_settings.get(key), dst_settings.get(key));
        if a != b {
            messages.push(format!(
                "Setting '{key}' did not copy correctly (installed={}, portable={}).",
                py_repr(a),
                py_repr(b)
            ));
        }
    }
    let (a, b) = (list_len(&src, "locations"), list_len(&dst, "locations"));
    if a != b {
        messages.push(format!(
            "Location count mismatch after copy (installed={a}, portable={b})."
        ));
    }
    if messages.is_empty() {
        Ok(())
    } else {
        Err(messages)
    }
}

/// The "Copied settings summary:" lines (`_build_portable_copy_summary`).
pub fn portable_copy_summary(portable_dir: &Path) -> Result<Vec<String>, String> {
    let config = read_config_object(portable_dir)?;
    let empty = Map::new();
    let settings = object(&config, "settings").unwrap_or(&empty);
    let value = |key: &str| settings.get(key).map_or("not set".to_string(), py_str);
    let custom_prompt = [
        "custom_system_prompt",
        "custom_instructions",
        "prompt",
        "assistant_prompt",
    ]
    .iter()
    .filter_map(|key| settings.get(*key))
    .any(|v| !crate::py_strip(&py_str(v)).is_empty());
    Ok(vec![
        format!("\u{2022} locations: {}", list_len(&config, "locations")),
        format!("\u{2022} data source: {}", value("data_source")),
        format!(
            "\u{2022} AI model preference: {}",
            value("ai_model_preference")
        ),
        format!("\u{2022} temperature unit: {}", value("temperature_unit")),
        format!(
            "\u{2022} custom prompt: {}",
            if custom_prompt { "yes" } else { "no" }
        ),
    ])
}

/// Python's `repr()` of a missing (`None`) or JSON value.
fn py_repr(value: Option<&Value>) -> String {
    match value {
        None => "None".into(),
        Some(Value::String(s)) => aw_core::shortcut_preferences::py_repr(s),
        Some(other) => py_str(other),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn config_with(names: &[&str]) -> AppConfig {
        let mut config = AppConfig::default();
        for name in names {
            config.locations.push(Location::new(*name, 30.0, -90.0));
        }
        config
    }

    fn write(dir: &Path, name: &str, value: Value) -> PathBuf {
        let path = dir.join(name);
        std::fs::write(&path, value.to_string()).unwrap();
        path
    }

    #[test]
    fn exported_at_matches_python_str() {
        let t = chrono::NaiveDate::from_ymd_opt(2026, 9, 25).unwrap();
        assert_eq!(
            exported_at(t.and_hms_micro_opt(14, 3, 2, 12).unwrap()),
            "2026-09-25 14:03:02.000012"
        );
        assert_eq!(
            exported_at(t.and_hms_opt(14, 3, 2).unwrap()),
            "2026-09-25 14:03:02"
        );
    }

    #[test]
    fn import_locations_skips_duplicates_and_invalid_entries() {
        let dir = tempfile::tempdir().unwrap();
        let cfg_file = dir.path().join("accessiweather.json");
        let mut config = config_with(&["Existing Location"]);
        let file = write(
            dir.path(),
            "import.json",
            json!({"locations": [
                "invalid_string_entry",
                {"name": "Missing Coords"},
                {"name": "Invalid Lat", "latitude": "not_a_number", "longitude": -80.0},
                {"name": "Existing Location", "latitude": 30.0, "longitude": -90.0},
                {"name": "Paris", "latitude": "48.8566", "longitude": 2.3522, "country_code": "fr"},
            ]}),
        );
        assert!(import_locations(&mut config, &file, &cfg_file));
        assert_eq!(config.location_names(), ["Existing Location", "Paris"]);
        assert_eq!(config.locations[1].country_code.as_deref(), Some("FR"));
        assert!(cfg_file.exists());

        let all_invalid = write(
            dir.path(),
            "bad.json",
            json!({"locations": ["x", {"name": "y"}]}),
        );
        assert!(!import_locations(&mut config, &all_invalid, &cfg_file));
        let none = write(dir.path(), "none.json", json!({"other_data": "value"}));
        assert!(import_locations(&mut config, &none, &cfg_file));
        std::fs::write(dir.path().join("broken.json"), "invalid json content").unwrap();
        assert!(!import_locations(
            &mut config,
            &dir.path().join("broken.json"),
            &cfg_file
        ));
        assert!(!import_locations(
            &mut config,
            &dir.path().join("missing.json"),
            &cfg_file
        ));
    }

    #[test]
    fn import_settings_validates_and_keeps_existing_locations_and_keys() {
        let dir = tempfile::tempdir().unwrap();
        let cfg_file = dir.path().join("accessiweather.json");
        let mut config = config_with(&["Home"]);
        config.settings.pirate_weather_api_key = "pw-key".into();

        let file = write(
            dir.path(),
            "s.json",
            json!({
                "settings": {"temperature_unit": "c", "data_source": "visualcrossing", "custom_instructions": null},
                "locations": [
                    {"name": "Home", "latitude": 1.0, "longitude": 1.0},
                    {"name": "Tokyo", "latitude": 35.6762, "longitude": 139.6503},
                ],
            }),
        );
        assert!(import_settings(&mut config, &file, Some(&cfg_file)));
        assert_eq!(config.settings.temperature_unit, "c");
        assert_eq!(config.settings.data_source, "auto");
        assert_eq!(config.settings.pirate_weather_api_key, "pw-key");
        assert_eq!(config.location_names(), ["Home", "Tokyo"]);
        assert_eq!(config.locations[0].latitude, 30.0);

        for bad in [json!([1]), json!({"other": 1}), json!({"settings": "x"})] {
            let f = write(dir.path(), "bad.json", bad);
            assert!(!import_settings(&mut config, &f, Some(&cfg_file)));
        }
        // Python imports a mistyped value as is; Rust falls back to the default.
        let wrong_type = write(
            dir.path(),
            "t.json",
            json!({"settings": {"update_interval_minutes": "soon", "sound_enabled": "off"}}),
        );
        assert!(import_settings(&mut config, &wrong_type, Some(&cfg_file)));
        assert_eq!(config.settings.update_interval_minutes, 10);
        assert!(!config.settings.sound_enabled);
        assert!(!import_settings(
            &mut config,
            &dir.path().join("nope.json"),
            Some(&cfg_file)
        ));
    }

    /// A key the file carries wins; the others stay active. Without a config
    /// file (sample-data runs) nothing is written.
    #[test]
    fn import_settings_keeps_active_keys_and_can_stay_in_memory() {
        let dir = tempfile::tempdir().unwrap();
        let mut config = config_with(&["Home"]);
        config.settings.pirate_weather_api_key = "pw".into();
        config.settings.venice_api_key = "vn".into();
        let file = write(
            dir.path(),
            "s.json",
            json!({"settings": {"temperature_unit": "f", "venice_api_key": "from-file"}}),
        );
        assert!(import_settings(&mut config, &file, None));
        let s = &config.settings;
        assert_eq!(s.temperature_unit, "f");
        assert_eq!(s.pirate_weather_api_key, "pw");
        assert_eq!(s.venice_api_key, "from-file");
        let written: Vec<_> = std::fs::read_dir(dir.path()).unwrap().flatten().collect();
        assert_eq!(written.len(), 1, "only the import file");
    }

    #[test]
    fn settings_export_has_no_secrets_and_round_trips() {
        let dir = tempfile::tempdir().unwrap();
        let mut config = config_with(&["Home"]);
        config.locations[0].country_code = Some("US".into());
        config.settings.openrouter_api_key = "secret".into();
        let path = dir.path().join("export.json");
        assert!(export_settings(&config, &path));
        let text = std::fs::read_to_string(&path).unwrap();
        assert!(!text.contains("secret") && !text.contains("openrouter_api_key"));
        let doc: Value = serde_json::from_str(&text).unwrap();
        assert_eq!(doc["locations"][0]["country_code"], "US");

        let mut fresh = AppConfig::default();
        assert!(import_settings(
            &mut fresh,
            &path,
            Some(&dir.path().join("c.json"))
        ));
        assert_eq!(fresh.location_names(), ["Home"]);
        let locations = locations_export(&config, "t");
        assert!(locations["locations"][0].get("country_code").is_none());
    }

    #[test]
    fn api_key_bundle_round_trips_through_a_keyring() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("keys.keys");
        let mut settings = AppSettings::default();
        let mut keyring = BTreeMap::from([("avwx_api_key".to_string(), "avwx".to_string())]);
        assert!(!export_encrypted_api_keys(
            &mut AppSettings::default(),
            &BTreeMap::new(),
            &path,
            "pw"
        ));
        settings.pirate_weather_api_key = "pw-key".into();
        assert!(export_encrypted_api_keys(
            &mut settings,
            &keyring,
            &path,
            "pw"
        ));

        let mut target = AppSettings::default();
        let mut other = BTreeMap::from([("venice_api_key".to_string(), "vn".to_string())]);
        assert!(!import_encrypted_api_keys(
            &mut target,
            &mut other,
            &path,
            "wrong",
            false
        ));
        assert!(import_encrypted_api_keys(
            &mut target,
            &mut other,
            &path,
            "pw",
            false
        ));
        assert_eq!(other.get("pirate_weather_api_key").unwrap(), "pw-key");
        assert_eq!(target.avwx_api_key, "avwx");
        // A stored key the bundle lacks is neither deleted nor deactivated.
        assert_eq!(other.get("venice_api_key").unwrap(), "vn");
        assert_eq!(target.venice_api_key, "vn");

        let mut portable = AppSettings {
            venice_api_key: "active".into(),
            ..AppSettings::default()
        };
        keyring.clear();
        assert!(import_encrypted_api_keys(
            &mut portable,
            &mut keyring,
            &path,
            "pw",
            true
        ));
        assert_eq!(portable.pirate_weather_api_key, "pw-key");
        assert_eq!(portable.venice_api_key, "active");
    }

    #[test]
    fn resets_keep_or_drop_the_right_things() {
        let dir = tempfile::tempdir().unwrap();
        let cfg_file = dir.path().join(aw_store::CONFIG_FILE_NAME);
        let mut config = config_with(&["Home", "Work"]);
        config.set_current_location("Work");
        config.settings.update_interval_minutes = 999;
        config.settings.venice_api_key = "v".into();
        assert!(reset_to_defaults(&mut config, None));
        assert!(!cfg_file.exists(), "sample-data runs write nothing");
        assert!(reset_to_defaults(&mut config, Some(&cfg_file)));
        assert!(cfg_file.exists());
        assert_eq!(config.settings.update_interval_minutes, 10);
        assert_eq!(config.settings.venice_api_key, "v");
        assert_eq!(config.location_names(), ["Home", "Work"]);
        assert_eq!(config.current_location.as_ref().unwrap().name, "Work");

        std::fs::create_dir_all(dir.path().join("weather_cache").join("x")).unwrap();
        std::fs::write(dir.path().join("api-keys.keys"), "{}").unwrap();
        let mut in_memory = config.clone();
        assert!(reset_all_data(&mut in_memory, None));
        assert!(in_memory.locations.is_empty());
        assert!(dir.path().join("api-keys.keys").exists(), "nothing deleted");
        assert!(reset_all_data(&mut config, Some(dir.path())));
        assert!(config.locations.is_empty());
        let left: Vec<_> = std::fs::read_dir(dir.path())
            .unwrap()
            .flatten()
            .map(|e| e.file_name())
            .collect();
        assert_eq!(left, [aw_store::CONFIG_FILE_NAME]);
    }

    #[test]
    fn backup_and_restore() {
        let dir = tempfile::tempdir().unwrap();
        let cfg_file = dir.path().join(aw_store::CONFIG_FILE_NAME);
        assert!(!backup_config(&cfg_file, None));
        aw_store::save_config(&cfg_file, &config_with(&["Backup Test"])).unwrap();
        assert!(backup_config(&cfg_file, None));
        let backup = dir.path().join("accessiweather.json.backup");
        assert!(backup.exists());
        aw_store::save_config(&cfg_file, &AppConfig::default()).unwrap();
        let restored = restore_config(&cfg_file, &backup).unwrap();
        assert_eq!(restored.location_names(), ["Backup Test"]);
        assert!(restore_config(&cfg_file, &dir.path().join("missing")).is_none());
    }
}
