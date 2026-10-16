//! Storage layer: platform paths, portable mode and atomic JSON persistence
//! of `accessiweather.json`, compatible with the Python application.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use aw_core::settings::AppConfig;
use aw_core::APP_NAME;

pub mod secrets;
pub mod weather_cache;

pub const CONFIG_FILE_NAME: &str = "accessiweather.json";
pub const PORTABLE_DIR_NAME: &str = "config";

#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error("I/O error at {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
    #[error("invalid JSON in {path}: {source}")]
    Json {
        path: PathBuf,
        #[source]
        source: serde_json::Error,
    },
    #[error("could not determine a configuration directory for this platform")]
    NoConfigDir,
}

/// Where the application keeps its data.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Paths {
    pub config_dir: PathBuf,
    pub portable: bool,
}

impl Paths {
    /// Resolve the config root like Python's `resolve_runtime_storage`: an
    /// explicit `--config-dir`, then portable mode (`<exe dir>/config`), then
    /// the platform default `<base>/Config`.
    pub fn resolve(explicit: Option<PathBuf>, force_portable: bool) -> Result<Self, StoreError> {
        if let Some(dir) = explicit {
            return Ok(Self {
                config_dir: dir,
                portable: force_portable,
            });
        }
        if let Some(exe_dir) = exe_dir() {
            if force_portable || detect_portable_mode(&exe_dir) {
                return Ok(Self {
                    config_dir: exe_dir.join(PORTABLE_DIR_NAME),
                    portable: true,
                });
            }
        }
        Ok(Self {
            config_dir: platform_base_dir()
                .ok_or(StoreError::NoConfigDir)?
                .join("Config"),
            portable: false,
        })
    }

    pub fn config_file(&self) -> PathBuf {
        self.config_dir.join(CONFIG_FILE_NAME)
    }

    pub fn state_dir(&self) -> PathBuf {
        self.config_dir.join("state")
    }

    pub fn cache_dir(&self) -> PathBuf {
        self.config_dir.join("weather_cache")
    }

    pub fn log_dir(&self) -> PathBuf {
        self.config_dir.join("logs")
    }
}

fn exe_dir() -> Option<PathBuf> {
    Some(std::env::current_exe().ok()?.parent()?.to_path_buf())
}

/// Python's `detect_portable_mode`: forced by `ACCESSIWEATHER_FORCE_PORTABLE`,
/// a `.portable` marker, or a legacy `config` folder in a build that has no
/// uninstaller beside it.
pub fn detect_portable_mode(exe_dir: &Path) -> bool {
    let forced = std::env::var("ACCESSIWEATHER_FORCE_PORTABLE")
        .map(|v| matches!(v.to_lowercase().as_str(), "1" | "true" | "yes"))
        .unwrap_or(false);
    if forced || exe_dir.join(".portable").exists() {
        return true;
    }
    let has_uninstaller = fs::read_dir(exe_dir).is_ok_and(|entries| {
        entries.flatten().any(|e| {
            let name = e.file_name().to_string_lossy().to_lowercase();
            name.starts_with("unins") && (name.ends_with(".exe") || name.ends_with(".dat"))
        })
    });
    !has_uninstaller && exe_dir.join(PORTABLE_DIR_NAME).is_dir()
}

/// Per-user application base directory, matching `accessiweather.paths.Paths`:
///
/// * Windows: `%LOCALAPPDATA%\Orinks\AccessiWeather`
/// * macOS:   `~/Library/Application Support/AccessiWeather`
/// * Linux:   `$XDG_DATA_HOME/accessiweather` (default `~/.local/share/accessiweather`)
pub fn platform_base_dir() -> Option<PathBuf> {
    if cfg!(target_os = "windows") {
        let base = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .or_else(|| home_dir().map(|h| h.join("AppData").join("Local")))?;
        Some(base.join(aw_core::APP_AUTHOR).join(APP_NAME))
    } else if cfg!(target_os = "macos") {
        Some(
            home_dir()?
                .join("Library")
                .join("Application Support")
                .join(APP_NAME),
        )
    } else {
        let base = std::env::var_os("XDG_DATA_HOME")
            .filter(|v| !v.is_empty())
            .map(PathBuf::from)
            .or_else(|| home_dir().map(|h| h.join(".local").join("share")))?;
        Some(base.join(APP_NAME.to_lowercase()))
    }
}

fn home_dir() -> Option<PathBuf> {
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
}

/// `ConfigManager.load_config`: the configuration file, or defaults when it
/// does not exist. A new config, or settings without `update_channel`, get
/// the running build's `default_update_channel`; the flag says so, and the
/// caller saves as Python does.
pub fn load_config(
    path: &Path,
    default_update_channel: &str,
) -> Result<(AppConfig, bool), StoreError> {
    match fs::read_to_string(path) {
        Ok(text) => AppConfig::from_json_for_build(&text, default_update_channel)
            .inspect(|(_, defaulted)| {
                if *defaulted {
                    tracing::info!(
                        "Applying build-aware default update channel for legacy config: {default_update_channel}"
                    );
                }
            })
            .map_err(|source| StoreError::Json {
                path: path.to_path_buf(),
                source,
            }),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            tracing::info!("no configuration at {}, using defaults", path.display());
            let mut config = AppConfig::default();
            config.settings.update_channel = default_update_channel.to_string();
            Ok((config, true))
        }
        Err(source) => Err(StoreError::Io {
            path: path.to_path_buf(),
            source,
        }),
    }
}

/// Atomically write the configuration (temp file + rename), creating the
/// parent directory. On Unix the file is restricted to the current user.
pub fn save_config(path: &Path, config: &AppConfig) -> Result<(), StoreError> {
    let text = config.to_json().map_err(|source| StoreError::Json {
        path: path.to_path_buf(),
        source,
    })?;
    write_atomic(path, text.as_bytes())
}

pub fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), StoreError> {
    let io = |source: std::io::Error| StoreError::Io {
        path: path.to_path_buf(),
        source,
    };
    let dir = path.parent().ok_or_else(|| {
        io(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "path has no parent",
        ))
    })?;
    fs::create_dir_all(dir).map_err(io)?;
    let mut tmp = tempfile::Builder::new()
        .prefix(".aw-")
        .suffix(".tmp")
        .tempfile_in(dir)
        .map_err(io)?;
    tmp.write_all(bytes).map_err(io)?;
    tmp.as_file().sync_all().map_err(io)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(tmp.path(), fs::Permissions::from_mode(0o600));
    }
    tmp.persist(path).map_err(|e| io(e.error))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use aw_core::Location;

    #[test]
    fn round_trip_config_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("nested").join(CONFIG_FILE_NAME);
        let (mut cfg, new) = load_config(&path, "nightly").unwrap();
        assert!(new && cfg.locations.is_empty());
        assert_eq!(cfg.settings.update_channel, "nightly");
        assert!(cfg.add_location(Location::new("Home", 40.0, -75.0).with_country("US")));
        save_config(&path, &cfg).unwrap();
        let (loaded, defaulted) = load_config(&path, "stable").unwrap();
        assert!(!defaulted);
        assert_eq!(loaded.settings.update_channel, "nightly");
        assert_eq!(loaded.locations.len(), 1);
        assert_eq!(loaded.current_location.unwrap().name, "Home");
        assert!(!dir.path().join("nested").join(".aw-").exists());
    }

    #[test]
    fn explicit_dir_wins() {
        let p = Paths::resolve(Some(PathBuf::from("/tmp/x")), false).unwrap();
        assert_eq!(p.config_file(), PathBuf::from("/tmp/x/accessiweather.json"));
        assert!(!p.portable);
    }

    #[test]
    fn default_config_lives_in_config_subfolder_like_python() {
        let p = Paths::resolve(None, false).unwrap();
        assert!(!p.portable);
        assert_eq!(p.config_dir.file_name().unwrap(), "Config");
        assert_eq!(p.config_dir.parent(), platform_base_dir().as_deref());
    }

    #[test]
    fn portable_detection_follows_python_markers() {
        let dir = tempfile::tempdir().unwrap();
        assert!(!detect_portable_mode(dir.path()));
        fs::create_dir(dir.path().join("config")).unwrap();
        assert!(detect_portable_mode(dir.path()));
        fs::write(dir.path().join("unins000.exe"), b"").unwrap();
        assert!(!detect_portable_mode(dir.path()));
        fs::write(dir.path().join(".portable"), b"").unwrap();
        assert!(detect_portable_mode(dir.path()));
    }
}
