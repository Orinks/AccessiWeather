//! The work behind the Settings dialog's buttons, mirroring
//! `config/import_export*.py`, `config/settings.py`,
//! `settings_dialog_portable.py`, `notifications/sound_pack_helpers.py` and
//! the key checks in `settings_dialog_handlers.py`. Buttons whose backend is
//! a single call elsewhere (model catalogs, AI key checks, sounds, update
//! checks, launch at login) call it from the dialog directly.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use aw_core::display::tray::TaskbarIconUpdater;
use aw_core::model::WeatherData;
use aw_core::settings::{AppConfig, AppSettings};
use aw_core::sound_events::LEGACY_SOUND_EVENT_KEYS;
use aw_core::Location;
use aw_providers::environmental::airnow::AirNowClient;
use aw_providers::pirateweather::PirateWeatherClient;
use aw_providers::{HttpClient, ReqwestClient};
use aw_store::secrets;
use serde_json::{json, Map, Value};

use super::settings_form::SoundPack;
use crate::app::State;

// ---------------------------------------------------------------------------
// Folders, links and sound packs
// ---------------------------------------------------------------------------

/// Open a folder in the file manager (`subprocess.Popen(["explorer", ...])`).
pub(crate) fn open_folder(path: &Path) {
    let program = if cfg!(windows) {
        "explorer"
    } else if cfg!(target_os = "macos") {
        "open"
    } else {
        "xdg-open"
    };
    if let Err(e) = std::process::Command::new(program).arg(path).spawn() {
        tracing::error!("Failed to open {}: {e}", path.display());
    }
}

/// Open a web page in the default browser; false when that failed.
pub(crate) fn open_url(url: &str) -> bool {
    wxdragon::prelude::launch_default_browser(url, wxdragon::prelude::BrowserLaunchFlags::Default)
}

/// `get_available_sound_packs` plus `sound_pack_uses_specific_alert_sounds`:
/// every folder with a readable `pack.json`, in directory order.
pub(crate) fn available_sound_packs(dir: &Path) -> Vec<SoundPack> {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut packs = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        let pack_json = path.join("pack.json");
        if !path.is_dir() || !pack_json.exists() {
            continue;
        }
        let id = entry.file_name().to_string_lossy().into_owned();
        let data: Value = match std::fs::read_to_string(&pack_json)
            .map_err(|e| e.to_string())
            .and_then(|t| serde_json::from_str(&t).map_err(|e| e.to_string()))
        {
            Ok(v) => v,
            Err(e) => {
                tracing::error!("Failed to load sound pack {id}: {e}");
                continue;
            }
        };
        let name = data
            .get("name")
            .and_then(Value::as_str)
            .unwrap_or(&id)
            .to_string();
        let specific_alert_sounds = match data.get("specific_alert_sounds") {
            Some(Value::Bool(explicit)) => *explicit,
            _ => data
                .get("sounds")
                .and_then(Value::as_object)
                .is_some_and(|sounds| {
                    sounds
                        .keys()
                        .any(|k| LEGACY_SOUND_EVENT_KEYS.contains(&k.as_str()))
                }),
        };
        packs.push(SoundPack {
            id,
            name,
            specific_alert_sounds,
        });
    }
    packs
}

// ---------------------------------------------------------------------------
// Settings export / import (`config/import_export_settings.py`)
// ---------------------------------------------------------------------------

/// `str(datetime.now())`.
fn python_now() -> String {
    let now = chrono::Local::now();
    let micros = now.timestamp_subsec_micros();
    if micros == 0 {
        now.format("%Y-%m-%d %H:%M:%S").to_string()
    } else {
        format!("{}.{micros:06}", now.format("%Y-%m-%d %H:%M:%S"))
    }
}

/// `export_settings`: settings (never API keys), saved locations and a time
/// stamp.
pub(crate) fn export_settings(path: &Path, config: &AppConfig) -> Result<(), String> {
    let locations: Vec<Value> = config
        .locations
        .iter()
        .map(|l| {
            let mut entry =
                json!({"name": l.name, "latitude": l.latitude, "longitude": l.longitude});
            if let Some(cc) = l.country_code.as_deref().filter(|c| !c.is_empty()) {
                entry["country_code"] = cc.into();
            }
            entry
        })
        .collect();
    let data = json!({
        "settings": serde_json::to_value(&config.settings).map_err(|e| e.to_string())?,
        "locations": locations,
        "exported_at": python_now(),
    });
    let text = serde_json::to_string_pretty(&data).map_err(|e| e.to_string())?;
    std::fs::write(path, text).map_err(|e| e.to_string())?;
    tracing::info!("Settings exported to {}", path.display());
    Ok(())
}

/// Carry the API keys active in `from` over to `to` where `to` has none.
fn keep_api_keys(to: &mut AppSettings, from: &mut AppSettings) {
    for name in secrets::API_KEY_NAMES {
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

/// `import_settings`: replace the settings with the file's and add any
/// locations whose names are new.
///
/// Deliberate divergence: Python also replaces the in-memory API keys with
/// the file's (an export has none), so the next Save deletes every key from
/// the keyring or the portable bundle. Here the active keys stay.
pub(crate) fn import_settings(path: &Path, config: &mut AppConfig) -> Result<(), String> {
    let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let data: Value = serde_json::from_str(&text)
        .map_err(|e| format!("Failed to parse settings file (invalid JSON): {e}"))?;
    let mut settings_data = data
        .get("settings")
        .and_then(Value::as_object)
        .cloned()
        .ok_or("Invalid settings file: missing or invalid 'settings' key (expected object)")?;
    if let Some(source) = settings_data.get("data_source").filter(|v| !v.is_null()) {
        let valid = ["auto", "nws", "openmeteo", "pirateweather"];
        if !source.as_str().is_some_and(|s| valid.contains(&s)) {
            tracing::warn!("Invalid data_source {source} in imported settings, will use 'auto'");
            settings_data.insert("data_source".into(), "auto".into());
        }
    }
    let mut imported = AppSettings::from_python_dict(settings_data);
    keep_api_keys(&mut imported, &mut config.settings);
    config.settings = imported;
    for entry in data
        .get("locations")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        let Some((name, lat, lon, country)) = coerce_location_entry(entry) else {
            continue;
        };
        if config.locations.iter().any(|l| l.name == name) {
            tracing::info!("Skipped existing location: {name}");
            continue;
        }
        let mut location = Location::new(&name, lat, lon);
        location.country_code = country;
        config.locations.push(location);
        tracing::info!("Imported location: {name}");
    }
    Ok(())
}

/// `_coerce_location_entry`.
fn coerce_location_entry(entry: &Value) -> Option<(String, f64, f64, Option<String>)> {
    let obj = entry.as_object()?;
    let name = match obj.get("name")? {
        Value::String(s) => s.clone(),
        Value::Number(n) if n.as_f64() != Some(0.0) => n.to_string(),
        Value::Bool(true) => "True".to_string(),
        _ => return None,
    };
    if name.is_empty() {
        return None;
    }
    let number = |v: &Value| match v {
        Value::Number(n) => n.as_f64(),
        Value::String(s) => s.trim().parse().ok(),
        Value::Bool(b) => Some(f64::from(u8::from(*b))),
        _ => None,
    };
    let lat = number(obj.get("latitude").filter(|v| !v.is_null())?)?;
    let lon = number(obj.get("longitude").filter(|v| !v.is_null())?)?;
    let country = obj
        .get("country_code")
        .and_then(Value::as_str)
        .map(str::to_string);
    Some((name, lat, lon, country))
}

// ---------------------------------------------------------------------------
// Encrypted API keys (`config/import_export_secrets.py`)
// ---------------------------------------------------------------------------

/// `_collect_api_key_secrets`: in-memory keys first, then the keyring.
fn collect_api_keys(
    settings: &mut AppSettings,
    offline: bool,
) -> std::collections::BTreeMap<String, String> {
    let mut keys = std::collections::BTreeMap::new();
    for name in secrets::API_KEY_NAMES {
        let mut value = secrets::api_key_mut(settings, name)
            .map(|v| v.clone())
            .unwrap_or_default();
        if value.is_empty() && !offline {
            value = secrets::get_password(name).unwrap_or_default();
        }
        if !value.is_empty() {
            keys.insert(name.to_string(), value);
        }
    }
    keys
}

/// `export_encrypted_api_keys`: false when there is no key to export or the
/// bundle could not be written.
pub(crate) fn export_encrypted_api_keys(st: &mut State, path: &Path, passphrase: &str) -> bool {
    let keys = collect_api_keys(&mut st.config.settings, st.offline);
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

/// `import_encrypted_api_keys`: decrypt the bundle into the keyring and make
/// the keys active.
pub(crate) fn import_encrypted_api_keys(st: &mut State, path: &Path, passphrase: &str) -> bool {
    let keys = match secrets::read_bundle(path, passphrase) {
        Ok(keys) => keys,
        Err(e) => {
            tracing::error!("Failed to import encrypted API keys: {e}");
            return false;
        }
    };
    let mut imported = 0;
    let mut failed = Vec::new();
    for name in secrets::API_KEY_NAMES {
        let Some(value) = keys.get(name).filter(|v| !v.is_empty()) else {
            continue;
        };
        if st.offline || secrets::set_password(name, value) {
            imported += 1;
        } else {
            tracing::error!("Failed to import API key into secure storage: {name}");
            failed.push(name);
        }
    }
    if imported == 0 && failed.is_empty() {
        tracing::warn!("Encrypted API key bundle did not contain supported keys");
        return false;
    }
    tracing::info!("Imported {imported} API keys into secure storage");
    if st.paths.portable || st.offline {
        secrets::apply(&mut st.config.settings, &keys);
    } else {
        secrets::load_into(&mut st.config.settings);
    }
    failed.is_empty()
}

// ---------------------------------------------------------------------------
// Resets (`config/settings.py`)
// ---------------------------------------------------------------------------

/// `reset_to_defaults`: default settings, saved.
///
/// Deliberate divergence: Python replaces the whole config with
/// `AppConfig.default()`, emptying the saved locations its confirmation
/// promises to keep and blanking the active API keys. Here the locations,
/// the current location and the keys stay.
pub(crate) fn reset_to_defaults(st: &mut State) -> bool {
    tracing::info!("Resetting configuration to defaults");
    reset_settings(&mut st.config);
    crate::app::save(st).is_ok()
}

fn reset_settings(config: &mut AppConfig) {
    let mut settings = AppSettings::default();
    keep_api_keys(&mut settings, &mut config.settings);
    config.settings = settings;
}

/// `reset_all_data`: delete everything in the config folder, then save a
/// default configuration. Sample-data runs only reset memory.
pub(crate) fn reset_all_data(st: &mut State) -> bool {
    let dir = st.paths.config_dir.clone();
    if !st.offline {
        match std::fs::read_dir(&dir) {
            Ok(entries) => {
                for entry in entries.flatten() {
                    let path = entry.path();
                    let removed = if path.is_dir() {
                        std::fs::remove_dir_all(&path)
                    } else {
                        std::fs::remove_file(&path)
                    };
                    if let Err(e) = removed {
                        tracing::warn!("Failed to remove {}: {e}", path.display());
                    }
                }
            }
            Err(e) => {
                tracing::error!("Failed to reset all data: {e}");
                return false;
            }
        }
    }
    st.config = AppConfig::default();
    if let Err(e) = std::fs::create_dir_all(&dir) {
        tracing::error!("Failed to reset all data: {e}");
        return false;
    }
    crate::app::save(st).is_ok()
}

// ---------------------------------------------------------------------------
// Portable mode config copy (`settings_dialog_portable.py`)
// ---------------------------------------------------------------------------

/// `_get_installed_config_dir`.
pub(crate) fn installed_config_dir() -> PathBuf {
    let base = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("USERPROFILE")
                .or_else(|| std::env::var_os("HOME"))
                .map(|h| PathBuf::from(h).join("AppData").join("Local"))
        })
        .unwrap_or_default();
    base.join(aw_core::APP_AUTHOR)
        .join(aw_core::APP_NAME)
        .join("Config")
}

/// `_read_config_json`.
pub(crate) fn read_config_json(dir: &Path) -> Result<Map<String, Value>, String> {
    let file = dir.join(aw_store::CONFIG_FILE_NAME);
    if !file.exists() {
        return Err(format!(
            "Required config file not found: {}",
            file.display()
        ));
    }
    let text = std::fs::read_to_string(&file).map_err(|e| e.to_string())?;
    match serde_json::from_str(&text).map_err(|e| e.to_string())? {
        Value::Object(map) => Ok(map),
        _ => Err(format!(
            "Invalid config payload in {}: expected object",
            file.display()
        )),
    }
}

fn list_len(config: &Map<String, Value>, key: &str) -> usize {
    config
        .get(key)
        .and_then(Value::as_array)
        .map_or(0, Vec::len)
}

fn settings_of(config: &Map<String, Value>) -> Map<String, Value> {
    config
        .get("settings")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default()
}

/// `_has_meaningful_installed_config_data`: why there is nothing to copy.
pub(crate) fn installed_config_precheck(dir: &Path) -> Result<(), String> {
    if !dir.is_dir() {
        return Err("Installed config directory not found.".into());
    }
    let has_entries = std::fs::read_dir(dir).is_ok_and(|mut e| e.next().is_some());
    if !has_entries {
        return Err("Installed config directory is empty.".into());
    }
    let file = dir.join(aw_store::CONFIG_FILE_NAME);
    if !file.is_file() {
        return Err("Required config file accessiweather.json is missing.".into());
    }
    match std::fs::metadata(&file) {
        Ok(m) if m.len() == 0 => return Err("Config file accessiweather.json is empty.".into()),
        Ok(_) => {}
        Err(_) => return Err("Could not read accessiweather.json.".into()),
    }
    let config = read_config_json(dir)
        .map_err(|_| "Config file accessiweather.json is invalid or unreadable.".to_string())?;
    if list_len(&config, "locations") == 0 {
        return Err("Installed config has no saved locations to transfer.".into());
    }
    Ok(())
}

/// Python's `repr()` of a JSON value, for copy validation messages.
fn py_value_repr(v: Option<&Value>) -> String {
    match v {
        None | Some(Value::Null) => "None".into(),
        Some(Value::Bool(b)) => if *b { "True" } else { "False" }.into(),
        Some(Value::String(s)) => aw_core::shortcut_preferences::py_repr(s),
        Some(other) => other.to_string(),
    }
}

/// `_validate_portable_copy`: the settings and locations that must match.
pub(crate) fn validate_portable_copy(installed: &Path, portable: &Path) -> Result<(), Vec<String>> {
    let (src, dst) = match (read_config_json(installed), read_config_json(portable)) {
        (Ok(src), Ok(dst)) => (src, dst),
        (Err(e), _) | (_, Err(e)) => return Err(vec![e]),
    };
    let (src_settings, dst_settings) = (settings_of(&src), settings_of(&dst));
    let mut messages = Vec::new();
    for key in ["ai_model_preference", "data_source", "temperature_unit"] {
        let (a, b) = (src_settings.get(key), dst_settings.get(key));
        if a != b {
            messages.push(format!(
                "Setting '{key}' did not copy correctly (installed={}, portable={}).",
                py_value_repr(a),
                py_value_repr(b)
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

/// `_build_portable_copy_summary`.
pub(crate) fn portable_copy_summary(dir: &Path) -> Result<Vec<String>, String> {
    let config = read_config_json(dir)?;
    let settings = settings_of(&config);
    let custom_prompt = [
        "custom_system_prompt",
        "custom_instructions",
        "prompt",
        "assistant_prompt",
    ]
    .iter()
    .filter_map(|k| settings.get(*k))
    // `str(value).strip()`: only a blank string counts as no prompt.
    .any(|v| v.as_str().is_none_or(|s| !s.trim().is_empty()));
    let setting = |key: &str| match settings.get(key) {
        None => "not set".to_string(),
        Some(Value::String(s)) => s.clone(),
        Some(Value::Null) => "None".to_string(),
        Some(Value::Bool(b)) => if *b { "True" } else { "False" }.to_string(),
        Some(other) => other.to_string(),
    };
    Ok(vec![
        format!("• locations: {}", list_len(&config, "locations")),
        format!("• data source: {}", setting("data_source")),
        format!("• AI model preference: {}", setting("ai_model_preference")),
        format!("• temperature unit: {}", setting("temperature_unit")),
        format!(
            "• custom prompt: {}",
            if custom_prompt { "yes" } else { "no" }
        ),
    ])
}

/// Copy the installed `accessiweather.json` over the portable one
/// (`shutil.copy2`). Returns the copied item names.
pub(crate) fn copy_installed_config(
    installed: &Path,
    portable: &Path,
) -> Result<Vec<String>, String> {
    std::fs::create_dir_all(portable).map_err(|e| e.to_string())?;
    let mut copied = Vec::new();
    for name in [aw_store::CONFIG_FILE_NAME] {
        let item = installed.join(name);
        if !item.exists() {
            continue;
        }
        std::fs::copy(&item, portable.join(name)).map_err(|e| e.to_string())?;
        copied.push(name.to_string());
    }
    Ok(copied)
}

/// `config_manager._config = None; load_config()`: reread the config file.
/// Portable mode keeps API keys in the bundle, so none are loaded here.
pub(crate) fn reload_config(st: &mut State) -> Result<(), String> {
    let build_tag = crate::lifecycle::build_tag();
    let channel = aw_services::update::default_update_channel(build_tag.as_deref());
    let (mut config, channel_defaulted) =
        aw_store::load_config(&st.paths.config_file(), channel).map_err(|e| e.to_string())?;
    if !st.paths.portable && !st.offline {
        secrets::load_into(&mut config.settings);
    }
    st.config = config;
    if channel_defaulted {
        let _ = crate::app::save(st);
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// After a save (`app_lifecycle.refresh_runtime_settings`)
// ---------------------------------------------------------------------------

/// Everything Python refreshes after Settings are saved. The weather client
/// and presenter read the settings on every fetch, so only the timers, menu
/// and notification subsystems need a nudge.
pub(crate) fn refresh_runtime_settings() {
    refresh_notifier_settings();
    refresh_alert_notification_settings();
    // Tray text, global hotkeys, window/tray shortcuts, update checks and
    // background timers.
    crate::lifecycle::refresh_runtime_settings();
}

// ---------------------------------------------------------------------------
// Notification settings
// ---------------------------------------------------------------------------

/// `_notifier.sound_enabled / soundpack / muted_sound_events`.
fn refresh_notifier_settings() {
    super::weather_events::refresh_notifier_settings();
}

/// `alert_notification_system.update_settings(settings.to_alert_settings())`.
fn refresh_alert_notification_settings() {
    super::weather_events::refresh_alert_notification_settings();
}

// ---------------------------------------------------------------------------
// Key checks and the tray text preview
// ---------------------------------------------------------------------------

fn http_client() -> Result<Arc<dyn HttpClient>, String> {
    ReqwestClient::new()
        .map(|c| Arc::new(c) as Arc<dyn HttpClient>)
        .map_err(|e| e.to_string())
}

/// `_on_validate_pw_api_key`'s check: current conditions for New York.
/// `Err` holds the reason shown after "validation failed: ". Runs on a
/// worker thread.
pub(crate) fn validate_pirate_weather_key(key: &str) -> Result<(), String> {
    check_pirate_weather_key(http_client()?, key)
}

fn check_pirate_weather_key(http: Arc<dyn HttpClient>, key: &str) -> Result<(), String> {
    let client = PirateWeatherClient::new(http, key, "AccessiWeather/1.0", "us");
    let location = Location::new("Test", 40.7128, -74.0060);
    match client.get_current_conditions(&location) {
        Ok(_) => Ok(()),
        Err(e) if e.status_code == Some(401) => Err("Invalid API key".into()),
        Err(e) if e.status_code == Some(429) => {
            Err("Rate limit exceeded — but key appears valid".into())
        }
        Err(e) => Err(e.message),
    }
}

/// `AirNowClient.validate_api_key`. Runs on a worker thread.
pub(crate) fn validate_airnow_key(key: &str) -> Result<(), String> {
    match AirNowClient::new(http_client()?, key, "AccessiWeather/2.0").validate_api_key() {
        (true, _) => Ok(()),
        (false, error) => Err(error.unwrap_or_else(|| "None".into())),
    }
}

/// What the tray text preview formats with: the updater
/// `_on_edit_taskbar_text_format` builds from the dialog, plus the weather
/// on screen.
#[derive(Debug, Clone, Default)]
pub(crate) struct TrayPreviewContext {
    pub updater: TaskbarIconUpdater,
    pub weather: Option<WeatherData>,
    pub location_name: Option<String>,
}

/// `TaskbarIconUpdater.build_preview`.
pub(crate) fn tray_text_preview(format: &str, context: &TrayPreviewContext) -> String {
    context.updater.build_preview(
        format,
        context.weather.as_ref(),
        context.location_name.as_deref(),
        chrono::Utc::now(),
    )
}

#[cfg(test)]
mod tests {
    use aw_providers::http::FixtureClient;
    use aw_providers::pirateweather::BASE_URL;

    use super::*;

    fn with_keys() -> AppConfig {
        let mut config = AppConfig::default();
        config.settings.pirate_weather_api_key = "pw".into();
        config.settings.venice_api_key = "vn".into();
        config.settings.temperature_unit = "c".into();
        config.add_location(Location::new("Home", 40.0, -75.0));
        config.add_location(Location::new("Work", 41.0, -74.0));
        config.set_current_location("Work");
        config
    }

    /// Python's reset empties the locations its message promises to keep.
    #[test]
    fn reset_keeps_locations_and_active_keys() {
        let mut config = with_keys();
        reset_settings(&mut config);
        assert_eq!(config.settings.temperature_unit, "both");
        assert_eq!(config.location_names(), ["Home", "Work"]);
        assert_eq!(config.current_location.unwrap().name, "Work");
        assert_eq!(config.settings.pirate_weather_api_key, "pw");
        assert_eq!(config.settings.venice_api_key, "vn");
    }

    /// Python's import blanks the active keys, and the next Save deletes
    /// them from the keyring; a key the file itself carries still wins.
    #[test]
    fn import_keeps_active_keys() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        std::fs::write(
            &path,
            r#"{"settings": {"temperature_unit": "f", "sound_enabled": "off",
                "venice_api_key": "from-file"}, "locations": []}"#,
        )
        .unwrap();
        let mut config = with_keys();
        import_settings(&path, &mut config).unwrap();
        let s = &config.settings;
        assert_eq!((s.temperature_unit.as_str(), s.sound_enabled), ("f", false));
        assert_eq!(s.pirate_weather_api_key, "pw");
        assert_eq!(s.venice_api_key, "from-file");
    }

    #[test]
    fn pirate_weather_key_check_reads_like_python() {
        let check = |status| {
            let http = Arc::new(FixtureClient::new().with_status(BASE_URL, status));
            check_pirate_weather_key(http, "k").unwrap_err()
        };
        assert_eq!(check(401), "Invalid API key");
        assert_eq!(check(429), "Rate limit exceeded — but key appears valid");
        assert_eq!(check(500), "API request failed: HTTP 500");
    }

    #[test]
    fn tray_preview_uses_sample_weather_and_the_dialog_format() {
        let context = TrayPreviewContext {
            updater: TaskbarIconUpdater {
                format_string: "{temp}".into(),
                temperature_unit: "f".into(),
                ..TaskbarIconUpdater::default()
            },
            ..TrayPreviewContext::default()
        };
        assert_eq!(tray_text_preview("{condition}", &context), "Partly Cloudy");
        assert_eq!(
            tray_text_preview("", &context),
            tray_text_preview("{temp}", &context)
        );
    }
}
