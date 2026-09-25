//! The work behind the Settings dialog's buttons, mirroring
//! `config/import_export*.py`, `config/settings.py`,
//! `settings_dialog_portable.py`, `notifications/sound_pack_helpers.py` and
//! the key checks in `settings_dialog_handlers.py`. Buttons whose backend is
//! a single call elsewhere (model catalogs, AI key checks, sounds, update
//! checks, launch at login) call it from the dialog directly.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use aw_core::display::tray::TaskbarIconUpdater;
use aw_core::model::WeatherData;
use aw_core::sound_events::LEGACY_SOUND_EVENT_KEYS;
use aw_core::Location;
use aw_providers::environmental::airnow::AirNowClient;
use aw_providers::pirateweather::PirateWeatherClient;
use aw_providers::{HttpClient, ReqwestClient};
use aw_services::import_export::{self, KeyStore, SystemKeyring};
use aw_store::secrets;
use serde_json::Value;

use super::settings_form::SoundPack;
use crate::app::State;

// ---------------------------------------------------------------------------
// Links and sound packs
// ---------------------------------------------------------------------------

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
// Settings import, API key bundles, resets and the portable copy
// (`aw_services::import_export`). Sample-data runs get no config file and a
// throwaway keyring, so they never touch the user's files or secrets.
// ---------------------------------------------------------------------------

/// The config file to save to; `None` in sample-data runs.
fn config_file(st: &State) -> Option<PathBuf> {
    (!st.offline).then(|| st.paths.config_file())
}

fn keyring(st: &State) -> Box<dyn KeyStore> {
    if st.offline {
        Box::new(BTreeMap::<String, String>::new())
    } else {
        Box::new(SystemKeyring)
    }
}

/// `import_settings`: the file's settings and new locations, saved.
pub(crate) fn import_settings(st: &mut State, path: &Path) -> bool {
    let file = config_file(st);
    import_export::import_settings(&mut st.config, path, file.as_deref())
}

/// `export_encrypted_api_keys`: false when there is no key to export or the
/// bundle could not be written.
pub(crate) fn export_encrypted_api_keys(st: &mut State, path: &Path, passphrase: &str) -> bool {
    let keyring = keyring(st);
    import_export::export_encrypted_api_keys(&mut st.config.settings, &*keyring, path, passphrase)
}

/// `import_encrypted_api_keys`: decrypt the bundle into the keyring and make
/// the keys active.
pub(crate) fn import_encrypted_api_keys(st: &mut State, path: &Path, passphrase: &str) -> bool {
    let mut keyring = keyring(st);
    let from_bundle = st.paths.portable || st.offline;
    import_export::import_encrypted_api_keys(
        &mut st.config.settings,
        &mut *keyring,
        path,
        passphrase,
        from_bundle,
    )
}

/// `reset_to_defaults`: default settings, saved.
pub(crate) fn reset_to_defaults(st: &mut State) -> bool {
    let file = config_file(st);
    import_export::reset_to_defaults(&mut st.config, file.as_deref())
}

/// `reset_all_data`: delete everything in the config folder, then save a
/// default configuration.
pub(crate) fn reset_all_data(st: &mut State) -> bool {
    let dir = (!st.offline).then(|| st.paths.config_dir.clone());
    import_export::reset_all_data(&mut st.config, dir.as_deref())
}

/// Copy the installed `accessiweather.json` over the portable one
/// (`shutil.copy2`); sample-data runs copy nothing.
pub(crate) fn copy_installed_config(
    st: &State,
    installed: &Path,
    portable: &Path,
) -> std::io::Result<Vec<String>> {
    if st.offline {
        return Ok(Vec::new());
    }
    import_export::copy_installed_config(installed, portable)
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
// Hooks the notifications workstream fills in
// ---------------------------------------------------------------------------

/// Hook: `_notifier.sound_enabled / soundpack / muted_sound_events`.
fn refresh_notifier_settings() {
    tracing::debug!("Notification sound settings refresh hook: nothing to refresh yet");
}

/// Hook: `alert_notification_system.update_settings(settings.to_alert_settings())`.
fn refresh_alert_notification_settings() {
    tracing::debug!("Alert notification settings refresh hook: nothing to refresh yet");
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
