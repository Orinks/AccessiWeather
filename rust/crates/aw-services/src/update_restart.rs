//! Restart planning and the update scripts (`services/update_restart.py`,
//! `apply_update` / `can_auto_apply` from `services/simple_update.py`).
//!
//! The Rust edition ships a zip on Windows and macOS and a tarball on Linux
//! (`rust/packaging/package.sh`), so Windows always takes Python's portable
//! path (unzip over the running folder), macOS its `.app` zip path, and Linux
//! is a manual install exactly like a Python tarball run.

use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RestartKind {
    Portable,
    MacosScript,
    Unsupported,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RestartPlan {
    pub kind: RestartKind,
    pub command: Vec<String>,
    pub script_path: Option<PathBuf>,
}

/// Python's `build_portable_update_script`: wait for `pid` to exit, unzip over
/// `target_dir` and relaunch `exe_path --updated`.
pub fn build_portable_update_script(
    zip_path: &Path,
    target_dir: &Path,
    exe_path: &Path,
    pid: u32,
) -> String {
    let zip = zip_path.display();
    let target = target_dir.display();
    let exe = exe_path.display();
    let extract = target_dir.join("update_tmp");
    let extract = extract.display();
    format!(
        r#"@echo off
set "PID={pid}"
set "ZIP_PATH={zip}"
set "TARGET_DIR={target}"
set "EXE_PATH={exe}"
set "EXTRACT_DIR={extract}"

:WAIT_LOOP
tasklist /FI "PID eq %PID%" 2>NUL | find /I /N "%PID%" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >NUL
    goto WAIT_LOOP
)

if exist "%EXTRACT_DIR%" rd /s /q "%EXTRACT_DIR%"
powershell -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%EXTRACT_DIR%' -Force"

REM Find actual content dir (zip may have a subfolder)
set "COPY_SRC=%EXTRACT_DIR%"
if not exist "%EXTRACT_DIR%\AccessiWeather.exe" (
    for /d %%D in ("%EXTRACT_DIR%\*") do (
        if exist "%%D\AccessiWeather.exe" set "COPY_SRC=%%D"
    )
)

xcopy "%COPY_SRC%\*" "%TARGET_DIR%\" /E /H /Y /Q
rd /s /q "%EXTRACT_DIR%"
del "%ZIP_PATH%"
timeout /t 2 /nobreak >NUL
start "" "%EXE_PATH%" --updated
(goto) 2>nul & del "%~f0""#
    )
}

/// Python's `build_macos_update_script`: unzip (or copy from a DMG) next to
/// the running `.app`, then reopen it with `--updated`.
pub fn build_macos_update_script(update_path: &Path, app_path: &Path) -> String {
    let app_dir = app_path.parent().unwrap_or(Path::new(""));
    let q_update = shlex_quote(&update_path.display().to_string());
    let q_app_dir = shlex_quote(&app_dir.display().to_string());
    let q_app_path = shlex_quote(&app_path.display().to_string());
    // The DMG pipeline is one line: Python's source has a backslash-newline
    // inside a normal string literal, which joins the lines.
    format!(
        r#"#!/bin/bash
sleep 2
UPDATE_PATH={q_update}
APP_DIR={q_app_dir}
APP_PATH={q_app_path}
if [[ "$UPDATE_PATH" == *.zip ]]; then
    unzip -o "$UPDATE_PATH" -d "$APP_DIR"
elif [[ "$UPDATE_PATH" == *.dmg ]]; then
    MOUNT_DIR=$(hdiutil attach "$UPDATE_PATH" -nobrowse -quiet                 | grep -oE '/Volumes/[^[:cntrl:]]+' | tail -1)
    if [[ -n "$MOUNT_DIR" ]]; then
        cp -R "$MOUNT_DIR"/*.app "$APP_DIR/"
        hdiutil detach "$MOUNT_DIR" -quiet
    fi
fi
open "$APP_PATH" --args --updated
rm -f "$0" "$UPDATE_PATH""#
    )
}

/// Python's `shlex.quote`.
pub(crate) fn shlex_quote(text: &str) -> String {
    if text.is_empty() {
        return "''".into();
    }
    let safe = |c: char| c.is_alphanumeric() || c == '_' || "@%+=:,./-".contains(c);
    if text.chars().all(safe) {
        return text.to_string();
    }
    format!("'{}'", text.replace('\'', r#"'"'"'"#))
}

/// How to apply `update_path` on `os` (`std::env::consts::OS` naming).
pub fn plan_restart(update_path: &Path, os: &str) -> std::io::Result<RestartPlan> {
    match os {
        "windows" => {
            let script = crate::exe_dir().join("accessiweather_portable_update.bat");
            Ok(RestartPlan {
                kind: RestartKind::Portable,
                command: vec![script.display().to_string()],
                script_path: Some(script),
            })
        }
        "macos" => {
            let dir = tempfile::Builder::new()
                .prefix("accessiweather_update_")
                .tempdir()?
                .keep();
            let script = dir.join("accessiweather_update.sh");
            Ok(RestartPlan {
                kind: RestartKind::MacosScript,
                command: vec!["bash".into(), script.display().to_string()],
                script_path: Some(script),
            })
        }
        _ => Ok(RestartPlan {
            kind: RestartKind::Unsupported,
            command: vec![update_path.display().to_string()],
            script_path: None,
        }),
    }
}

/// Whether [`apply_update`] can install this download; when false the UI
/// shows the "Manual Update Required" message with the file location.
pub fn can_auto_apply(update_path: &Path) -> bool {
    plan_restart(update_path, std::env::consts::OS)
        .is_ok_and(|plan| plan.kind != RestartKind::Unsupported)
}

/// Launch the update script and exit the process. Returns `Ok(false)` when
/// the update needs a manual install. The caller must close its windows
/// first so no file stays locked.
pub fn apply_update(update_path: &Path) -> std::io::Result<bool> {
    let plan = plan_restart(update_path, std::env::consts::OS)?;
    let exe = crate::exe_path();
    match (plan.kind, plan.script_path) {
        (RestartKind::Portable, Some(script)) => {
            let target_dir = exe.parent().unwrap_or(Path::new("."));
            let text =
                build_portable_update_script(update_path, target_dir, &exe, std::process::id());
            // Python's write_text translates newlines; cmd needs CRLF for labels.
            std::fs::write(&script, text.replace('\n', "\r\n"))?;
            Command::new(&script).current_dir(target_dir).spawn()?;
            std::process::exit(0);
        }
        (RestartKind::MacosScript, Some(script)) => {
            // Typically /path/to/App.app/Contents/MacOS/executable
            let app_path = exe
                .ancestors()
                .nth(3)
                .map(Path::to_path_buf)
                .unwrap_or_default();
            std::fs::write(&script, build_macos_update_script(update_path, &app_path))?;
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                std::fs::set_permissions(&script, std::fs::Permissions::from_mode(0o700))?;
            }
            Command::new("bash").arg(&script).spawn()?;
            std::process::exit(0);
        }
        _ => {
            tracing::warn!(
                "Update requires manual installation: {}",
                update_path.display()
            );
            Ok(false)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn windows_always_replaces_the_unzipped_install() {
        let plan = plan_restart(Path::new("C:/temp/update.zip"), "windows").unwrap();
        assert_eq!(plan.kind, RestartKind::Portable);
        let script = plan.script_path.unwrap();
        assert_eq!(
            script.file_name().unwrap(),
            "accessiweather_portable_update.bat"
        );
        assert_eq!(script.parent().unwrap(), crate::exe_dir());
    }

    #[test]
    fn macos_writes_its_script_to_a_private_temp_dir() {
        let plan = plan_restart(Path::new("/tmp/update.zip"), "macos").unwrap();
        assert_eq!(plan.kind, RestartKind::MacosScript);
        let script = plan.script_path.unwrap();
        assert_eq!(script.file_name().unwrap(), "accessiweather_update.sh");
        let dir = script.parent().unwrap();
        assert!(dir
            .file_name()
            .unwrap()
            .to_string_lossy()
            .starts_with("accessiweather_update_"));
        std::fs::remove_dir(dir).unwrap();
    }

    #[test]
    fn linux_tarballs_need_a_manual_install() {
        let plan = plan_restart(Path::new("/tmp/a.tar.gz"), "linux").unwrap();
        assert_eq!(plan.kind, RestartKind::Unsupported);
        assert_eq!(plan.command, ["/tmp/a.tar.gz"]);
    }

    #[test]
    fn scripts_quote_paths_and_restart_with_updated_flag() {
        let script = build_macos_update_script(
            Path::new("/tmp/it's here.zip"),
            Path::new("/Applications/AccessiWeather.app"),
        );
        assert!(script.contains(r#"UPDATE_PATH='/tmp/it'"'"'s here.zip'"#));
        assert!(script.contains("APP_DIR=/Applications\n"));
        assert!(script.contains("unzip -o") && script.contains("hdiutil detach"));
        let bat = build_portable_update_script(
            Path::new("C:/t/u.zip"),
            Path::new("C:/A"),
            Path::new("C:/A/AccessiWeather.exe"),
            42,
        );
        assert!(bat.starts_with("@echo off\nset \"PID=42\""));
        assert!(bat.contains("Expand-Archive") && bat.contains("--updated"));
    }
}
