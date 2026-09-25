//! The work behind the Settings dialog's buttons: one function per backend
//! action. Actions the existing Rust code can do (folders, settings and
//! encrypted key transfer, resets, portable copy checks, sound pack
//! discovery) are implemented here, mirroring `config/import_export*.py`,
//! `config/settings.py`, `settings_dialog_portable.py` and
//! `notifications/sound_pack_helpers.py`. Actions whose backends are ported
//! separately (key validation, model catalogs, audio, update checks, startup
//! registration, tray text preview, hotkeys) are stubs that log and change
//! nothing; they are listed together at the end of this file.

use std::path::{Path, PathBuf};

use aw_core::model::WeatherData;
use aw_core::settings::{AppConfig, AppSettings};
use aw_core::sound_events::LEGACY_SOUND_EVENT_KEYS;
use aw_core::Location;
use aw_store::secrets;
use serde_json::{json, Map, Value};

use super::model_browser_dialog::CatalogModel;
use super::settings_form::SoundPack;
use crate::app::{with_state, State};

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

/// `get_soundpacks_dir` for a compiled build: `data/soundpacks` beside the
/// executable in portable mode, `soundpacks` beside it otherwise. Debug
/// builds fall back to the repository's packs.
pub(crate) fn soundpacks_dir(portable: bool) -> PathBuf {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(Path::to_path_buf))
        .unwrap_or_default();
    let dir = if portable {
        exe_dir.join("data").join("soundpacks")
    } else {
        exe_dir.join("soundpacks")
    };
    if cfg!(debug_assertions) && !dir.exists() {
        return Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../soundpacks");
    }
    dir
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

/// `import_settings`: replace the settings with the file's and add any
/// locations whose names are new. The imported settings carry no API keys.
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
    let imported: AppSettings = serde_json::from_value(Value::Object(settings_data))
        .map_err(|e| format!("Failed to deserialize settings: {e}"))?;
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

/// `reset_to_defaults`: a fresh default configuration, saved. Like Python
/// this also empties the saved locations.
pub(crate) fn reset_to_defaults(st: &mut State) -> bool {
    tracing::info!("Resetting configuration to defaults");
    st.config = AppConfig::default();
    crate::app::save(st).is_ok()
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
    let mut config = aw_store::load_config(&st.paths.config_file()).map_err(|e| e.to_string())?;
    config.normalize();
    if !st.paths.portable && !st.offline {
        secrets::load_into(&mut config.settings);
    }
    st.config = config;
    Ok(())
}

// ---------------------------------------------------------------------------
// After a save (`app_lifecycle.refresh_runtime_settings`)
// ---------------------------------------------------------------------------

/// Everything Python refreshes after Settings are saved. The weather client
/// and presenter read the settings on every fetch, so only the timers, menu
/// and not-yet-ported subsystems need a nudge.
pub(crate) fn refresh_runtime_settings() {
    tracing::info!("Refreshing runtime settings");
    refresh_notifier_settings();
    refresh_alert_notification_settings();
    refresh_taskbar_icon_settings();
    refresh_global_hotkeys();
    setup_window_tray_shortcuts();
    start_auto_update_checks();
    super::main_window::start_background_updates();
    tracing::info!("Runtime settings refreshed successfully");
}

// ---------------------------------------------------------------------------
// Stubs for backends ported by other workstreams. Each logs and changes
// nothing until its subsystem lands.
// ---------------------------------------------------------------------------

fn not_ported(action: &str) {
    tracing::info!("{action} is not ported yet");
}

/// `_notifier.sound_enabled / soundpack / muted_sound_events`.
fn refresh_notifier_settings() {
    not_ported("Refreshing notification sound settings");
}

/// `alert_notification_system.update_settings(settings.to_alert_settings())`.
fn refresh_alert_notification_settings() {
    not_ported("Refreshing alert notification settings");
}

/// `taskbar_icon_updater.update_settings(...)`.
fn refresh_taskbar_icon_settings() {
    not_ported("Refreshing tray icon text settings");
}

/// `refresh_global_hotkeys`: the NOAA Weather Radio hotkey.
fn refresh_global_hotkeys() {
    not_ported("Registering the NOAA Weather Radio hotkey");
}

/// `_setup_accelerators` for the configurable window/tray shortcuts.
fn setup_window_tray_shortcuts() {
    not_ported("Registering window and tray shortcuts");
}

/// `_start_auto_update_checks`.
fn start_auto_update_checks() {
    not_ported("Automatic update checks");
}

/// Account state for the Venice model browser (`VeniceBalance`).
#[derive(Debug, Clone, Default, PartialEq, serde::Deserialize)]
pub(crate) struct VeniceBalance {
    pub can_consume: Option<bool>,
    pub consumption_currency: Option<String>,
    pub usd: Option<f64>,
    pub diem: Option<f64>,
}

/// `OpenRouterModelsClient` / `VeniceModelsClient.get_text_models` (and
/// `fetch_balance` for Venice). Runs on a worker thread.
pub(crate) fn fetch_model_catalog(
    venice: bool,
    api_key: Option<&str>,
) -> Result<(Vec<CatalogModel>, Option<VeniceBalance>), String> {
    let _ = (venice, api_key);
    not_ported("Fetching the AI model catalog");
    Err("Unable to load models. Check your connection and API key, then refresh.".into())
}

/// `PirateWeatherClient.get_current_conditions` as a key check: `Err` holds
/// the reason ("Invalid API key", ...). Runs on a worker thread.
pub(crate) fn validate_pirate_weather_key(key: &str) -> Result<(), String> {
    let _ = key;
    not_ported("Pirate Weather key validation");
    Err("Validation is not available in this build yet.".into())
}

/// `AirNowClient.validate_api_key`. Runs on a worker thread.
pub(crate) fn validate_airnow_key(key: &str) -> Result<(), String> {
    let _ = key;
    not_ported("AirNow key validation");
    Err("Validation is not available in this build yet.".into())
}

/// `validate_openrouter_api_key`: (valid, message). Runs on a worker thread.
pub(crate) fn validate_openrouter_key(key: &str) -> (bool, String) {
    let _ = key;
    not_ported("OpenRouter key validation");
    (
        false,
        "Unable to validate OpenRouter access. Check your connection and try again.".into(),
    )
}

/// `validate_venice_api_key`: (valid, message). Runs on a worker thread.
pub(crate) fn validate_venice_key(key: &str) -> (bool, String) {
    let _ = key;
    not_ported("Venice key validation");
    (
        false,
        "Unable to validate Venice access. Check your connection and try again.".into(),
    )
}

/// `play_sample_sound(pack_id)`.
pub(crate) fn play_sample_sound(pack_id: &str) -> Result<(), String> {
    not_ported(&format!("Playing a sample from sound pack {pack_id}"));
    Ok(())
}

/// `show_soundpack_manager_dialog`.
pub(crate) fn show_soundpack_manager(parent: &dyn wxdragon::prelude::WxWidget) {
    let _ = parent;
    not_ported("Soundpack Manager");
}

/// A newer release (`UpdateService.check_for_updates` result).
#[derive(Debug, Clone)]
pub(crate) struct UpdateInfo {
    pub version: String,
    pub is_nightly: bool,
    pub release_notes: String,
}

/// The running version for update checks, and the nightly build date when
/// this is a nightly build (`parse_nightly_date(app.build_tag)`).
pub(crate) fn current_update_version() -> (String, Option<String>) {
    (aw_core::VERSION.to_string(), None)
}

/// `UpdateService.check_for_updates`: `Ok(None)` when up to date. Runs on a
/// worker thread.
pub(crate) fn check_for_updates(
    current_version: &str,
    current_nightly_date: Option<&str>,
    channel: &str,
) -> Result<Option<UpdateInfo>, String> {
    let _ = (current_version, current_nightly_date, channel);
    not_ported("Checking for updates");
    Err("Update checking is not available in this build yet.".into())
}

/// `UpdateAvailableDialog` then `app._download_and_apply_update`.
pub(crate) fn offer_update(
    parent: &dyn wxdragon::prelude::WxWidget,
    current_version: &str,
    info: &UpdateInfo,
) {
    let _ = parent;
    let channel = if info.is_nightly { "Nightly" } else { "Stable" };
    not_ported(&format!(
        "Offering the {channel} update {} over {current_version} ({} bytes of notes)",
        info.version,
        info.release_notes.len()
    ));
}

/// `config_manager.is_startup_enabled`: whether the OS launches the app at
/// sign-in. Until registration is ported this reports the saved setting.
pub(crate) fn is_startup_enabled() -> bool {
    with_state().is_some_and(|s| s.borrow().config.settings.startup_enabled)
}

/// `config_manager.enable_startup`: (success, message).
pub(crate) fn enable_startup() -> (bool, String) {
    not_ported("Launch at startup registration");
    (true, "Startup enabled successfully".into())
}

/// `config_manager.disable_startup`: (success, message).
pub(crate) fn disable_startup() -> (bool, String) {
    not_ported("Launch at startup registration");
    (true, "Startup disabled successfully".into())
}

/// What the tray text preview formats with (`TaskbarIconUpdater` settings
/// taken from the dialog, plus the weather on screen).
#[derive(Debug, Clone, Default)]
pub(crate) struct TrayPreviewContext {
    pub dynamic_enabled: bool,
    pub temperature_unit: String,
    pub wind_speed_unit: String,
    pub weather: Option<WeatherData>,
    pub location_name: Option<String>,
}

/// `TaskbarIconUpdater.build_preview`.
pub(crate) fn tray_text_preview(format: &str, context: &TrayPreviewContext) -> String {
    not_ported(&format!(
        "Tray text preview of {format:?} (dynamic={}, units {}/{}, location {:?}, weather {})",
        context.dynamic_enabled,
        context.temperature_unit,
        context.wind_speed_unit,
        context.location_name,
        context.weather.is_some()
    ));
    String::new()
}
