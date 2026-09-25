//! Application services with no UI: update checks, launch at login, single
//! instance activation, settings import/export, logging, the Report Issue URL
//! and the first-run onboarding flow. Each module names the Python file it
//! ports.

use std::ffi::OsStr;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

pub mod import_export;
pub mod logging;
pub mod onboarding;
pub mod pep440;
pub mod report_issue;
pub mod single_instance;
pub mod startup;
pub mod update;
pub mod update_integrity;
pub mod update_restart;
pub mod user_manual;

/// The running executable (Python's `Path(sys.executable).resolve()`).
///
/// Windows keeps `current_exe()` as is: `canonicalize` would return a
/// `\\?\` verbatim path that must never end up in a Run key or a script.
pub fn exe_path() -> PathBuf {
    let exe = std::env::current_exe().unwrap_or_default();
    if cfg!(windows) {
        exe
    } else {
        exe.canonicalize().unwrap_or(exe)
    }
}

/// The folder holding the executable (Python's `app_directory`).
pub fn exe_dir() -> PathBuf {
    exe_path()
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_default()
}

/// The Rust equivalent of Python's `not is_compiled_runtime()`: a binary
/// still sitting in a cargo target directory (`cargo run`, `cargo test`,
/// `target/release/...`). Cargo keeps a `.cargo-lock` in every profile
/// directory; packaged builds never ship one.
pub fn is_running_from_source() -> bool {
    running_from_cargo_target(&exe_dir())
}

fn running_from_cargo_target(exe_dir: &Path) -> bool {
    exe_dir
        .ancestors()
        .take(2)
        .any(|dir| dir.join(".cargo-lock").is_file())
}

/// Open a folder, file or URL with the desktop's handler, like Python's
/// `subprocess.Popen(["explorer", path])` / `webbrowser.open(url)`.
pub fn open_in_shell(target: impl AsRef<OsStr>) -> bool {
    let program = if cfg!(windows) {
        "explorer"
    } else if cfg!(target_os = "macos") {
        "open"
    } else {
        "xdg-open"
    };
    Command::new(program)
        .arg(target)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .inspect_err(|e| tracing::warn!("Failed to launch {program}: {e}"))
        .is_ok()
}

/// Python's `str.splitlines()` (without keepends).
pub(crate) fn splitlines(text: &str) -> Vec<&str> {
    const BREAKS: [char; 10] = [
        '\n', '\r', '\x0b', '\x0c', '\x1c', '\x1d', '\x1e', '\u{85}', '\u{2028}', '\u{2029}',
    ];
    let mut lines = Vec::new();
    let mut start = 0;
    let mut chars = text.char_indices().peekable();
    while let Some((i, c)) = chars.next() {
        if BREAKS.contains(&c) {
            lines.push(&text[start..i]);
            let mut end = i + c.len_utf8();
            if c == '\r' && chars.peek().is_some_and(|&(_, n)| n == '\n') {
                chars.next();
                end += 1;
            }
            start = end;
        }
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

/// Python's `str.strip()` whitespace, which also covers the ASCII
/// separators `\x1c`..`\x1f` that Rust's `trim` keeps.
pub(crate) fn py_strip(text: &str) -> &str {
    text.trim_matches(|c: char| c.is_whitespace() || ('\x1c'..='\x1f').contains(&c))
}

/// `urllib.parse.urlencode` (quote_plus) of ordered key/value pairs.
pub(crate) fn urlencode(pairs: &[(&str, &str)]) -> String {
    pairs
        .iter()
        .map(|(k, v)| format!("{}={}", quote_plus(k), quote_plus(v)))
        .collect::<Vec<_>>()
        .join("&")
}

fn quote_plus(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for b in text.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'_' | b'.' | b'-' | b'~' => {
                out.push(b as char)
            }
            b' ' => out.push('+'),
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splitlines_matches_python() {
        assert_eq!(splitlines("a\r\nb\rc\nd"), ["a", "b", "c", "d"]);
        assert_eq!(splitlines("a\n\nb\n"), ["a", "", "b"]);
        assert!(splitlines("").is_empty());
    }

    #[test]
    fn quote_plus_matches_python() {
        assert_eq!(
            urlencode(&[("title", "Test & Title"), ("body", "<x>~*é")]),
            "title=Test+%26+Title&body=%3Cx%3E~%2A%C3%A9"
        );
    }

    #[test]
    fn cargo_target_dirs_count_as_source_runs() {
        let dir = tempfile::tempdir().unwrap();
        let deps = dir.path().join("debug").join("deps");
        std::fs::create_dir_all(&deps).unwrap();
        assert!(!running_from_cargo_target(&deps));
        std::fs::write(dir.path().join("debug").join(".cargo-lock"), b"").unwrap();
        assert!(running_from_cargo_target(&deps));
        assert!(running_from_cargo_target(&dir.path().join("debug")));
        // The test binary itself runs from target/<profile>/deps.
        assert!(is_running_from_source());
    }
}
