//! GitHub release update checks (`services/simple_update.py`), the automatic
//! check schedule (`app_timer_manager.py`, `app_lifecycle.py`), release notes
//! as shown by `ui/dialogs/update_dialog.py`, and the messages of the
//! check/download/apply flow (`ui/main_window_commands.py`,
//! `ui/dialogs/settings_dialog_handlers.py`).
//!
//! Channels, tag parsing, version comparison and asset selection are
//! Python's: releases carry the same asset names (`cargo xtask package`
//! mirrors the Python build), so either edition updates into the other.

use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::LazyLock;
use std::time::{Duration, Instant};

use aw_core::settings::AppSettings;
use regex::Regex;
use serde_json::Value;

use crate::pep440::Version;
use crate::update_integrity::{
    asset_name, assets, find_checksum_asset, parse_checksum_file, verify_file_checksum,
};
use crate::{py_strip, splitlines};

pub const GITHUB_RELEASES_URL: &str =
    "https://api.github.com/repos/orinks/accessiweather/releases?per_page=20";

/// How often the scheduler wakes to see whether a check is due.
pub const AUTO_UPDATE_POLL_INTERVAL: Duration = Duration::from_secs(15 * 60);

static COMMIT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\bcommit(?:\s+hash)?\s*[:=]\s*([0-9a-f]{7,40})\b").expect("valid regex")
});
static FALLBACK_HASH: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)\b[0-9a-f]{7,40}\b").expect("valid regex"));
static NIGHTLY_TAG: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)nightly-(\d{8})").expect("valid regex"));

/// The version compared against release tags (the workspace version).
pub fn app_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// `nightly-YYYYMMDD` for nightly builds, baked in at compile time from
/// `ACCESSIWEATHER_BUILD_TAG` (Python's generated `_build_meta.BUILD_TAG`).
pub fn build_tag() -> Option<&'static str> {
    option_env!("ACCESSIWEATHER_BUILD_TAG").filter(|t| !t.is_empty())
}

/// The update channel a config without `update_channel` gets
/// (`ConfigManager._default_update_channel_for_current_build`).
pub fn default_update_channel(build_tag: Option<&str>) -> &'static str {
    if build_tag.is_some_and(|t| t.to_lowercase().starts_with("nightly-")) {
        "nightly"
    } else {
        "stable"
    }
}

/// An available update (`simple_update.UpdateInfo`).
#[derive(Debug, Clone, PartialEq)]
pub struct UpdateInfo {
    pub version: String,
    pub download_url: String,
    pub artifact_name: String,
    pub release_notes: String,
    pub commit_hash: Option<String>,
    pub is_nightly: bool,
    pub is_prerelease: bool,
    /// The GitHub release, kept so the download can find its checksum.
    pub release: Option<Value>,
}

#[derive(Debug, thiserror::Error)]
pub enum UpdateError {
    #[error("{0}")]
    Http(#[from] reqwest::Error),
    /// Python's `ChecksumVerificationError`.
    #[error("{0}")]
    Checksum(String),
    #[error("{0}")]
    Io(#[from] std::io::Error),
}

fn str_field<'a>(value: &'a Value, key: &str) -> &'a str {
    value.get(key).and_then(Value::as_str).unwrap_or("")
}

fn truthy(value: Option<&Value>) -> bool {
    match value {
        None | Some(Value::Null) => false,
        Some(Value::Bool(b)) => *b,
        Some(Value::Number(n)) => n.as_f64() != Some(0.0),
        Some(Value::String(s)) => !s.is_empty(),
        Some(Value::Array(a)) => !a.is_empty(),
        Some(Value::Object(o)) => !o.is_empty(),
    }
}

pub fn parse_commit_hash(release_notes: &str) -> Option<String> {
    if let Some(caps) = COMMIT.captures(release_notes) {
        return Some(caps[1].to_lowercase());
    }
    FALLBACK_HASH
        .find(release_notes)
        .map(|m| m.as_str().to_lowercase())
}

/// `nightly-20260131` -> `20260131`.
pub fn parse_nightly_date(tag_name: &str) -> Option<String> {
    NIGHTLY_TAG.captures(tag_name).map(|c| c[1].to_string())
}

pub fn is_nightly_release(release: &Value) -> bool {
    parse_nightly_date(str_field(release, "tag_name")).is_some()
}

/// `(identifier, is_nightly)`: the nightly date, or the tag without leading `v`s.
pub fn release_identifier(release: &Value) -> (String, bool) {
    let tag = str_field(release, "tag_name");
    match parse_nightly_date(tag) {
        Some(date) => (date, true),
        None => (tag.trim_start_matches('v').to_string(), false),
    }
}

/// Whether `release` is newer than the running build.
pub fn is_update_available(
    release: &Value,
    current_version: &str,
    current_nightly_date: Option<&str>,
) -> bool {
    let (identifier, nightly) = release_identifier(release);
    if nightly {
        // A stable build checking the nightly channel takes any nightly.
        return current_nightly_date.is_none_or(|date| identifier.as_str() > date);
    }
    match (
        Version::parse(&identifier),
        Version::parse(current_version.trim_start_matches('v')),
    ) {
        (Some(new), Some(current)) => new > current,
        _ => false,
    }
}

/// The newest release on `channel` (by `published_at`, then `created_at`).
/// Unknown channels keep every release, as in Python.
pub fn select_latest_release<'a>(releases: &'a [Value], channel: &str) -> Option<&'a Value> {
    let channel = channel.to_lowercase();
    let key = |r: &Value| {
        [r.get("published_at"), r.get("created_at")]
            .into_iter()
            .flatten()
            .find(|v| truthy(Some(v)))
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string()
    };
    let mut best: Option<(&Value, String)> = None;
    for release in releases {
        let prerelease = truthy(release.get("prerelease"));
        let nightly = is_nightly_release(release);
        if (channel == "stable" && (prerelease || nightly)) || (channel == "nightly" && !nightly) {
            continue;
        }
        let k = key(release);
        // Python's max() keeps the first of equal keys.
        if best.as_ref().is_none_or(|(_, b)| k > *b) {
            best = Some((release, k));
        }
    }
    best.map(|(r, _)| r)
}

/// This platform's asset in `release` (`select_asset`; `os` in
/// `std::env::consts::OS` naming): on Windows the portable zip for a
/// portable run, else the installer; the disk image on macOS; the AppImage,
/// else a package or tarball, on Linux. Unlike Python there is no "first
/// asset" fallback, which hands a Mac the Linux AppImage when a release has
/// no disk image.
pub fn select_asset<'a>(release: &'a Value, portable: bool, os: &str) -> Option<&'a Value> {
    const DENY_EXTENSIONS: [&str; 7] = [
        ".sha256", ".sha512", ".md5", ".sig", ".asc", ".txt", ".json",
    ];
    let name = |asset: &Value| asset_name(asset).to_lowercase();
    let filtered: Vec<&Value> = assets(release)
        .iter()
        .filter(|a| {
            let n = name(a);
            !DENY_EXTENSIONS.iter().any(|ext| n.ends_with(ext))
                && !n.contains("signature")
                && !n.contains("verify")
        })
        .collect();
    let first = |pick: &dyn Fn(&str) -> bool| filtered.iter().copied().find(|a| pick(&name(a)));
    let system = os.to_lowercase();
    if system.contains("windows") {
        if portable {
            let zip = first(&|n| n.contains("portable") && n.ends_with(".zip"))
                .or_else(|| first(&|n| n.ends_with(".zip")));
            if zip.is_some() {
                return zip;
            }
        }
        [".exe", ".msi"]
            .into_iter()
            .find_map(|ext| first(&|n| n.ends_with(ext)))
    } else if system.contains("darwin") || system.contains("mac") {
        [".dmg", ".pkg"]
            .into_iter()
            .find_map(|ext| first(&|n| n.ends_with(ext)))
    } else {
        [".appimage", ".deb", ".rpm", ".tar.gz", ".zip"]
            .into_iter()
            .find_map(|ext| first(&|n| n.ends_with(ext) && (n.contains("linux") || ext != ".zip")))
    }
}

/// The pure part of `check_for_updates`: pick the release and asset.
pub fn update_from_releases(
    releases: &[Value],
    current_version: &str,
    current_nightly_date: Option<&str>,
    channel: &str,
    portable: bool,
    os: &str,
) -> Option<UpdateInfo> {
    let latest = select_latest_release(releases, channel)?;
    if !is_update_available(latest, current_version, current_nightly_date) {
        return None;
    }
    let asset = select_asset(latest, portable, os)?;
    let (version, is_nightly) = release_identifier(latest);
    let notes = str_field(latest, "body");
    Some(UpdateInfo {
        version,
        download_url: str_field(asset, "browser_download_url").to_string(),
        artifact_name: asset_name(asset).to_string(),
        release_notes: notes.to_string(),
        commit_hash: parse_commit_hash(notes),
        is_nightly,
        is_prerelease: truthy(latest.get("prerelease")),
        release: Some(latest.clone()),
    })
}

/// Checks and downloads updates from GitHub releases (`simple_update.UpdateService`).
pub struct UpdateService {
    client: reqwest::blocking::Client,
    releases_url: String,
}

impl UpdateService {
    pub fn new() -> Result<Self, UpdateError> {
        Self::with_releases_url(GITHUB_RELEASES_URL)
    }

    pub fn with_releases_url(url: &str) -> Result<Self, UpdateError> {
        let client = reqwest::blocking::Client::builder()
            .user_agent("AccessiWeather")
            .timeout(Duration::from_secs(30))
            .build()?;
        Ok(Self {
            client,
            releases_url: url.to_string(),
        })
    }

    pub fn fetch_releases(&self) -> Result<Vec<Value>, UpdateError> {
        let data: Value = self
            .client
            .get(&self.releases_url)
            .send()?
            .error_for_status()?
            .json()?;
        Ok(match data {
            Value::Array(items) => items,
            _ => Vec::new(),
        })
    }

    /// `Some(update)` when `channel` has a newer build for this platform
    /// (the portable zip instead of the installer when `portable`).
    pub fn check_for_updates(
        &self,
        current_version: &str,
        current_nightly_date: Option<&str>,
        channel: &str,
        portable: bool,
    ) -> Result<Option<UpdateInfo>, UpdateError> {
        let releases = self.fetch_releases()?;
        Ok(update_from_releases(
            &releases,
            current_version,
            current_nightly_date,
            channel,
            portable,
            std::env::consts::OS,
        ))
    }

    /// Download `info` into `dest_dir` and verify it against the release's
    /// checksum; `progress(downloaded, total)` runs after every chunk. A
    /// release without any checksum asset is accepted with a warning; every
    /// other verification failure deletes the file (fail-closed).
    pub fn download_update(
        &self,
        info: &UpdateInfo,
        dest_dir: &Path,
        mut progress: impl FnMut(u64, u64),
    ) -> Result<PathBuf, UpdateError> {
        std::fs::create_dir_all(dest_dir)?;
        let dest = dest_dir.join(&info.artifact_name);
        let mut response = self
            .client
            .get(&info.download_url)
            .send()?
            .error_for_status()?;
        let total = response
            .headers()
            .get(reqwest::header::CONTENT_LENGTH)
            .and_then(|v| v.to_str().ok()?.parse().ok())
            .unwrap_or(0);
        let mut file = std::fs::File::create(&dest)?;
        let mut buf = vec![0u8; 65536];
        let mut downloaded = 0u64;
        loop {
            let n = response.read(&mut buf)?;
            if n == 0 {
                break;
            }
            file.write_all(&buf[..n])?;
            downloaded += n as u64;
            progress(downloaded, total);
        }
        drop(file);
        tracing::info!("Downloaded update to {}", dest.display());
        self.verify_download(info, &dest)
            .inspect_err(|_| {
                let _ = std::fs::remove_file(&dest);
            })
            .map(|()| dest)
    }

    fn verify_download(&self, info: &UpdateInfo, dest: &Path) -> Result<(), UpdateError> {
        let name = &info.artifact_name;
        let fail = |msg: String| Err(UpdateError::Checksum(msg));
        let Some(release) = &info.release else {
            return fail(format!(
                "Cannot verify {name}: no release metadata available. \
                 Refusing to install an unverified update."
            ));
        };
        let Some(checksum_asset) = find_checksum_asset(release, name) else {
            tracing::warn!("No checksum asset found for {name}; integrity could not be verified");
            return Ok(());
        };
        let url = str_field(checksum_asset, "browser_download_url");
        if url.is_empty() {
            return fail(format!(
                "Checksum asset for {name} has no download URL; cannot verify integrity."
            ));
        }
        let content = self
            .client
            .get(url)
            .send()
            .and_then(reqwest::blocking::Response::error_for_status)
            .and_then(reqwest::blocking::Response::text);
        let Ok(content) = content else {
            return fail(format!(
                "Failed to download checksum file for {name}; cannot verify integrity."
            ));
        };
        let Some((algo, expected)) = parse_checksum_file(&content, name) else {
            return fail(format!(
                "Could not find a checksum for {name} in the published checksum file; \
                 cannot verify integrity."
            ));
        };
        if !verify_file_checksum(dest, algo, &expected)? {
            return fail(format!(
                "Checksum verification failed for {name}. Expected {algo}:{expected}. \
                 The downloaded file may be corrupted or tampered with."
            ));
        }
        tracing::info!("Checksum verified ({algo}) for {name}");
        Ok(())
    }
}

/// Release Markdown as plain text (`format_release_notes_for_dialog`).
pub fn format_release_notes(release_notes: &str) -> String {
    static RULES: LazyLock<Vec<(Regex, &str)>> = LazyLock::new(|| {
        [
            (r"^#{1,6}\s+", ""),
            (r"^[-*+]\s+", "- "),
            (r"^\d+\.\s+", "- "),
            (r"\[([^\]]+)\]\([^)]+\)", "$1"),
            (r"`([^`]+)`", "$1"),
            (r"\*\*([^*]+)\*\*", "$1"),
            (r"__([^_]+)__", "$1"),
            (r"\*([^*]+)\*", "$1"),
            (r"_([^_]+)_", "$1"),
            (r"\s+", " "),
        ]
        .into_iter()
        .map(|(p, r)| (Regex::new(p).expect("valid regex"), r))
        .collect()
    });
    const EMPTY: &str = "No release notes available.";
    if py_strip(release_notes).is_empty() {
        return EMPTY.into();
    }
    let mut lines: Vec<String> = Vec::new();
    let mut previous_blank = false;
    for raw in splitlines(release_notes) {
        let mut line = py_strip(raw).to_string();
        if line.is_empty() {
            if !lines.is_empty() && !previous_blank {
                lines.push(String::new());
                previous_blank = true;
            }
            continue;
        }
        for (re, rep) in RULES.iter() {
            line = re.replace_all(&line, *rep).into_owned();
        }
        let line = py_strip(&line);
        if !line.is_empty() {
            lines.push(line.to_string());
            previous_blank = false;
        }
    }
    let text = py_strip(&lines.join("\n")).to_string();
    if text.is_empty() {
        EMPTY.into()
    } else {
        text
    }
}

/// The due threshold for automatic checks, or `None` when they are off.
/// The scheduler seeds its "last check" with the start time, so the first
/// poll is never overdue; the startup check runs separately.
pub fn auto_update_interval(settings: &AppSettings) -> Option<Duration> {
    settings
        .auto_update_enabled
        .then(|| Duration::from_secs(settings.update_check_interval_hours.max(1) as u64 * 3600))
}

/// Whether a poll at `now` should run a check (never checked counts as due).
pub fn is_update_check_due(last: Option<Instant>, now: Instant, interval: Duration) -> bool {
    last.is_none_or(|last| now.saturating_duration_since(last) >= interval)
}

/// Whether the startup/periodic automatic check may run
/// (`_check_for_updates_on_startup`).
pub fn should_run_automatic_check(
    running_from_source: bool,
    settings: &AppSettings,
    build_tag: Option<&str>,
) -> bool {
    if running_from_source {
        tracing::debug!("Running from source, skipping update check");
        return false;
    }
    if !settings.auto_update_enabled {
        tracing::debug!("Automatic update check disabled");
        return false;
    }
    // A nightly build without its tag would re-offer the same nightly forever.
    if build_tag.is_none() && settings.update_channel == "nightly" {
        tracing::warn!(
            "Skipping startup nightly update check: no build_tag available. \
             Use Help > Check for Updates to check manually."
        );
        return false;
    }
    true
}

/// The version the dialogs show: the nightly date on nightly builds.
pub fn display_version<'a>(version: &'a str, current_nightly_date: Option<&'a str>) -> &'a str {
    current_nightly_date.unwrap_or(version)
}

/// Dialog and status texts of the update flow, verbatim from Python.
pub mod messages {
    pub const RUNNING_FROM_SOURCE_TITLE: &str = "Running from Source";
    pub const RUNNING_FROM_SOURCE: &str =
        "Update checking is only available in installed builds.\n\
         You're running from source \u{2014} use git pull to update.";
    pub const NO_UPDATES_TITLE: &str = "No Updates Available";
    pub const CHECK_FAILED_TITLE: &str = "Update Check Failed";
    pub const CHECKING_STATUS: &str = "Checking for updates...";
    pub const CHECK_FAILED_STATUS: &str = "Could not check for updates";
    pub const DOWNLOADING_TITLE: &str = "Downloading Update";
    pub const DOWNLOAD_ERROR_TITLE: &str = "Download Error";
    pub const MANUAL_UPDATE_TITLE: &str = "Manual Update Required";
    pub const APPLY_TITLE: &str = "Apply Update";
    pub const APPLY: &str = "Download complete. The application will now restart to apply \
         the update.\n\nContinue?";

    pub fn no_update(current_nightly_date: Option<&str>, channel: &str, version: &str) -> String {
        match current_nightly_date {
            Some(date) if channel == "stable" => {
                format!("You're on nightly ({date}).\nNo newer stable release available.")
            }
            Some(date) => format!("You're on the latest nightly ({date})."),
            None => format!("You're up to date ({version})."),
        }
    }

    pub fn check_failed(error: &str) -> String {
        format!("Failed to check for updates:\n{error}")
    }

    pub fn update_available_status(version: &str) -> String {
        format!("Update available: {version}")
    }

    pub fn channel_label(is_nightly: bool) -> &'static str {
        if is_nightly {
            "Nightly"
        } else {
            "Stable"
        }
    }

    pub fn downloading(artifact_name: &str) -> String {
        format!("Downloading {artifact_name}...")
    }

    /// `(percent, text)` for the progress dialog; nothing while the size is unknown.
    /// Percent is Python's `int((downloaded / total) * 100)`, float rounding included.
    pub fn download_progress(downloaded: u64, total: u64) -> Option<(u32, String)> {
        (total > 0).then(|| {
            (
                (downloaded as f64 / total as f64 * 100.0) as u32,
                format!("Downloading... {} / {} KB", downloaded / 1024, total / 1024),
            )
        })
    }

    pub fn download_failed(error: &str) -> String {
        format!("Failed to download update:\n{error}")
    }

    pub fn manual_update(path: &std::path::Path) -> String {
        format!(
            "The update was downloaded, but this type of install can't update itself \
             automatically.\n\nThe new version was saved to:\n{}\n\nInstall it manually, \
             then restart AccessiWeather.",
            path.display()
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn release(tag: &str, prerelease: bool, published: &str) -> Value {
        json!({"tag_name": tag, "prerelease": prerelease, "body": "", "published_at": published, "assets": []})
    }

    #[test]
    fn stable_channel_skips_prereleases_and_nightlies() {
        let releases = [
            release("v1.0.0", false, "2025-01-01T00:00:00Z"),
            release("v1.1.0", true, "2025-02-01T00:00:00Z"),
            release("nightly-20250202", false, "2025-02-02T00:00:00Z"),
        ];
        let tag = |r: Option<&Value>| r.map(|r| r["tag_name"].as_str().unwrap().to_string());
        assert_eq!(
            tag(select_latest_release(&releases, "stable")).unwrap(),
            "v1.0.0"
        );
        assert_eq!(
            tag(select_latest_release(&releases, "Nightly")).unwrap(),
            "nightly-20250202"
        );
        assert_eq!(
            tag(select_latest_release(&releases, "dev")).unwrap(),
            "nightly-20250202"
        );
        assert!(select_latest_release(&releases[1..2], "stable").is_none());
    }

    #[test]
    fn ties_keep_the_first_release_like_python_max() {
        let releases = [
            release("v1.0.0", false, "2025-01-01T00:00:00Z"),
            release("v2.0.0", false, "2025-01-01T00:00:00Z"),
        ];
        assert_eq!(
            select_latest_release(&releases, "stable").unwrap()["tag_name"],
            "v1.0.0"
        );
    }

    #[test]
    fn nightly_and_stable_comparisons() {
        let nightly = release("nightly-20260201", true, "");
        assert!(is_update_available(&nightly, "1.0.0", Some("20260131")));
        assert!(!is_update_available(&nightly, "1.0.0", Some("20260201")));
        assert!(is_update_available(&nightly, "1.0.0", None));
        let stable = release("v1.2.0", false, "");
        assert!(is_update_available(&stable, "1.1.0", None));
        assert!(!is_update_available(&stable, "1.2.0", None));
        assert!(!is_update_available(&stable, "not-a-version", None));
    }

    #[test]
    fn asset_selection_follows_the_release_names() {
        let r = json!({"assets": [
            {"name": "AccessiWeather-0.11.0-linux-x86_64.AppImage"},
            {"name": "AccessiWeather-0.11.0-linux.tar.gz"},
            {"name": "AccessiWeather-0.11.0-macOS.dmg"},
            {"name": "AccessiWeather-0.11.0-macOS.zip"},
            {"name": "AccessiWeather-0.11.0-windows-portable.zip"},
            {"name": "AccessiWeather-0.11.0-windows-setup.exe"},
            {"name": "checksums.txt"},
        ]});
        let pick = |portable, os| select_asset(&r, portable, os).map(|a| asset_name(a).to_string());
        let name = |suffix: &str| Some(format!("AccessiWeather-0.11.0-{suffix}"));
        assert_eq!(pick(false, "windows"), name("windows-setup.exe"));
        assert_eq!(pick(true, "windows"), name("windows-portable.zip"));
        assert_eq!(pick(false, "macos"), name("macOS.dmg"));
        assert_eq!(pick(true, "linux"), name("linux-x86_64.AppImage"));
        let zip_only = json!({"assets": [{"name": "AccessiWeather-0.10.1-macOS.zip"}]});
        assert!(select_asset(&zip_only, false, "macos").is_none());
    }

    #[test]
    fn version_is_pep440() {
        assert!(Version::parse(app_version()).is_some());
        assert_eq!(default_update_channel(Some("Nightly-20260101")), "nightly");
        assert_eq!(default_update_channel(None), "stable");
    }

    #[test]
    fn schedule_rules() {
        let mut s = AppSettings::default();
        assert_eq!(
            auto_update_interval(&s),
            Some(Duration::from_secs(24 * 3600))
        );
        s.update_check_interval_hours = 0;
        assert_eq!(auto_update_interval(&s), Some(Duration::from_secs(3600)));
        s.auto_update_enabled = false;
        assert_eq!(auto_update_interval(&s), None);

        let day = Duration::from_secs(24 * 3600);
        let now = Instant::now();
        assert!(is_update_check_due(None, now, day));
        assert!(!is_update_check_due(Some(now), now, day));
        assert!(is_update_check_due(
            Some(now),
            now + day + Duration::from_secs(3600),
            day
        ));
    }

    #[test]
    fn automatic_check_gating() {
        let mut s = AppSettings::default();
        assert!(!should_run_automatic_check(true, &s, None));
        assert!(should_run_automatic_check(false, &s, None));
        s.update_channel = "nightly".into();
        assert!(!should_run_automatic_check(false, &s, None));
        assert!(should_run_automatic_check(
            false,
            &s,
            Some("nightly-20260101")
        ));
        s.auto_update_enabled = false;
        assert!(!should_run_automatic_check(
            false,
            &s,
            Some("nightly-20260101")
        ));
    }

    #[test]
    fn messages_match_python() {
        use messages::*;
        assert_eq!(
            no_update(Some("20260131"), "stable", "20260131"),
            "You're on nightly (20260131).\nNo newer stable release available."
        );
        assert_eq!(
            no_update(Some("20260131"), "nightly", "20260131"),
            "You're on the latest nightly (20260131)."
        );
        assert_eq!(
            no_update(None, "stable", "0.10.1"),
            "You're up to date (0.10.1)."
        );
        assert_eq!(
            download_progress(51_200, 102_400).unwrap(),
            (50, "Downloading... 50 / 100 KB".to_string())
        );
        assert!(download_progress(10, 0).is_none());
        // (29 / 100) * 100 is 28.999999999999996 in Python too.
        assert_eq!(download_progress(29, 100).unwrap().0, 28);
        assert_eq!(display_version("0.10.1", Some("20260101")), "20260101");
    }

    #[test]
    fn release_notes_lose_markdown_noise() {
        let raw = "## Added\n- **National Products** now use `IEM AFOS` text.\n\
                   - See [CHANGELOG.md](https://example.com/changelog) for details.\n\n\
                   ## Fixed\n- Pirate Weather handles _freezing rain_ correctly.\n";
        assert_eq!(
            format_release_notes(raw),
            "Added\n- National Products now use IEM AFOS text.\n- See CHANGELOG.md for details.\n\n\
             Fixed\n- Pirate Weather handles freezing rain correctly."
        );
        assert_eq!(format_release_notes(" \n"), "No release notes available.");
        assert_eq!(
            format_release_notes("### Changed\n1. First numbered item.\n* Second starred item.\n"),
            "Changed\n- First numbered item.\n- Second starred item."
        );
    }
}
