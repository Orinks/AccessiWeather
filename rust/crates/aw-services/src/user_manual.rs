//! Help > User Manual (`user_manual.py`): the bundled manual, else the
//! online one.

use std::path::{Path, PathBuf};

pub const ONLINE_USER_MANUAL_URL: &str = "https://www.orinks.net/accessiweather/user-manual";
pub const MANUAL_UNAVAILABLE_TITLE: &str = "User Manual Unavailable";
pub const MANUAL_UNAVAILABLE: &str = "AccessiWeather could not open the user manual.";

/// The repository root when running from source: the ancestor of this
/// crate holding `pyproject.toml` (Python's `_find_project_root`).
pub(crate) fn source_project_root() -> Option<PathBuf> {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .find(|dir| dir.join("pyproject.toml").exists())
        .map(Path::to_path_buf)
}

/// `get_bundled_user_manual_path`: `accessiweather/docs/user_manual.md` beside
/// a packaged executable, `docs/user_manual.md` in a source checkout.
pub fn bundled_user_manual_path() -> Option<PathBuf> {
    let candidate = if crate::is_running_from_source() {
        source_project_root()?.join("docs").join("user_manual.md")
    } else {
        crate::exe_dir()
            .join("accessiweather")
            .join("docs")
            .join("user_manual.md")
    };
    candidate.exists().then_some(candidate)
}

/// Open the local manual, falling back to the website. False when neither
/// could be launched (show [`MANUAL_UNAVAILABLE`]).
pub fn open_user_manual() -> bool {
    if let Some(path) = bundled_user_manual_path() {
        let target = url::Url::from_file_path(&path)
            .map(String::from)
            .unwrap_or_else(|()| path.display().to_string());
        if crate::open_in_shell(target) {
            return true;
        }
        tracing::error!("Failed to open local user manual at {}", path.display());
    }
    crate::open_in_shell(ONLINE_USER_MANUAL_URL)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn source_runs_use_the_checkout_manual() {
        let path = bundled_user_manual_path().expect("docs/user_manual.md in the checkout");
        assert!(path.ends_with(Path::new("docs").join("user_manual.md")));
    }
}
