//! Storage layer: platform paths, portable mode and atomic JSON persistence
//! of `accessiweather.json`, compatible with the Python application.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use aw_core::settings::AppConfig;
use aw_core::APP_NAME;

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
    /// Resolve paths, honouring an explicit `--config-dir`, portable mode
    /// (a `config` folder next to the executable or `--portable`) and finally
    /// the platform default.
    pub fn resolve(explicit: Option<PathBuf>, force_portable: bool) -> Result<Self, StoreError> {
        if let Some(dir) = explicit {
            return Ok(Self {
                config_dir: dir,
                portable: false,
            });
        }
        if let Some(portable_dir) = portable_dir() {
            if force_portable || portable_dir.is_dir() {
                return Ok(Self {
                    config_dir: portable_dir,
                    portable: true,
                });
            }
        }
        Ok(Self {
            config_dir: platform_config_dir().ok_or(StoreError::NoConfigDir)?,
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

fn portable_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    Some(exe.parent()?.join(PORTABLE_DIR_NAME))
}

/// Default per-user data directory, matching `accessiweather.paths`:
///
/// * Windows: `%LOCALAPPDATA%\Orinks\AccessiWeather`
/// * macOS:   `~/Library/Application Support/AccessiWeather`
/// * Linux:   `$XDG_DATA_HOME/accessiweather` (default `~/.local/share/accessiweather`)
pub fn platform_config_dir() -> Option<PathBuf> {
    if let Some(dir) = std::env::var_os("ACCESSIWEATHER_CONFIG_DIR") {
        return Some(PathBuf::from(dir));
    }
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

/// Load the configuration file, returning defaults when it does not exist.
pub fn load_config(path: &Path) -> Result<AppConfig, StoreError> {
    match fs::read_to_string(path) {
        Ok(text) => AppConfig::from_json(&text).map_err(|source| StoreError::Json {
            path: path.to_path_buf(),
            source,
        }),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            tracing::info!("no configuration at {}, using defaults", path.display());
            Ok(AppConfig::default())
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
        let mut cfg = load_config(&path).unwrap();
        assert!(cfg.locations.is_empty());
        cfg.upsert_location(Location::new("Home", 40.0, -75.0).with_country("US"));
        save_config(&path, &cfg).unwrap();
        let loaded = load_config(&path).unwrap();
        assert_eq!(loaded.locations.len(), 1);
        assert_eq!(loaded.current_location.unwrap().name, "Home");
        assert!(!dir.path().join("nested").join(".aw-").exists());
    }

    #[test]
    fn explicit_dir_wins() {
        let p = Paths::resolve(Some(PathBuf::from("/tmp/x")), true).unwrap();
        assert_eq!(p.config_file(), PathBuf::from("/tmp/x/accessiweather.json"));
        assert!(!p.portable);
    }
}
