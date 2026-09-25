//! Restart planning and the update scripts (`services/update_restart.py`,
//! `apply_update` / `can_auto_apply` from `services/simple_update.py`).
//!
//! A portable Windows run unzips over its folder, an installed one runs the
//! setup program, macOS replaces the `.app` from the zip or disk image, and a
//! running AppImage swaps itself for the new one. Anything else (a Linux
//! tarball run) is a manual install.

use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RestartKind {
    Portable,
    WindowsInstaller,
    MacosScript,
    AppImageScript,
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

/// Python's `build_appimage_update_script`: wait for `pid` to exit, swap the
/// AppImage for the download and relaunch it with `--updated`.
pub fn build_appimage_update_script(update_path: &Path, appimage_path: &Path, pid: u32) -> String {
    let q_update = shlex_quote(&update_path.display().to_string());
    let q_appimage = shlex_quote(&appimage_path.display().to_string());
    format!(
        r#"#!/bin/bash
PID={pid}
UPDATE_PATH={q_update}
APPIMAGE_PATH={q_appimage}
while kill -0 "$PID" 2>/dev/null; do sleep 1; done
STAGED="$APPIMAGE_PATH.update-new"
cp "$UPDATE_PATH" "$STAGED" || exit 1
chmod +x "$STAGED"
mv -f "$STAGED" "$APPIMAGE_PATH" || exit 1
rm -f "$UPDATE_PATH"
cd "$HOME" || true
nohup "$APPIMAGE_PATH" --updated >/dev/null 2>&1 &
rm -f "$0""#
    )
}

/// The `.AppImage` this process runs from (`running_appimage_path`): the
/// AppImage runtime exports its path as `APPIMAGE`.
pub fn running_appimage_path() -> Option<PathBuf> {
    let path = PathBuf::from(std::env::var_os("APPIMAGE").filter(|p| !p.is_empty())?);
    path.is_file().then_some(path)
}

fn private_script(name: &str) -> std::io::Result<PathBuf> {
    let dir = tempfile::Builder::new()
        .prefix("accessiweather_update_")
        .tempdir()?
        .keep();
    Ok(dir.join(name))
}

fn script_plan(kind: RestartKind, script: PathBuf) -> RestartPlan {
    RestartPlan {
        kind,
        command: vec!["bash".into(), script.display().to_string()],
        script_path: Some(script),
    }
}

/// How to apply `update_path` (`plan_restart`; `os` in
/// `std::env::consts::OS` naming, `appimage` the running AppImage).
pub fn plan_restart(
    update_path: &Path,
    portable: bool,
    os: &str,
    appimage: Option<&Path>,
) -> std::io::Result<RestartPlan> {
    let unsupported = || RestartPlan {
        kind: RestartKind::Unsupported,
        command: vec![update_path.display().to_string()],
        script_path: None,
    };
    Ok(match os {
        "windows" if portable => {
            let script = crate::exe_dir().join("accessiweather_portable_update.bat");
            RestartPlan {
                kind: RestartKind::Portable,
                command: vec![script.display().to_string()],
                script_path: Some(script),
            }
        }
        "windows" => RestartPlan {
            kind: RestartKind::WindowsInstaller,
            command: vec![update_path.display().to_string()],
            script_path: None,
        },
        "macos" => script_plan(
            RestartKind::MacosScript,
            private_script("accessiweather_update.sh")?,
        ),
        "linux"
            if appimage.is_some()
                && update_path
                    .to_string_lossy()
                    .to_lowercase()
                    .ends_with(".appimage") =>
        {
            script_plan(
                RestartKind::AppImageScript,
                private_script("accessiweather_appimage_update.sh")?,
            )
        }
        _ => unsupported(),
    })
}

fn current_plan(update_path: &Path, portable: bool) -> std::io::Result<RestartPlan> {
    let appimage = running_appimage_path();
    plan_restart(
        update_path,
        portable,
        std::env::consts::OS,
        appimage.as_deref(),
    )
}

/// Whether [`apply_update`] can install this download; when false the UI
/// shows the "Manual Update Required" message with the file location.
pub fn can_auto_apply(update_path: &Path, portable: bool) -> bool {
    current_plan(update_path, portable).is_ok_and(|plan| plan.kind != RestartKind::Unsupported)
}

#[cfg(unix)]
fn write_private_script(path: &Path, text: &str) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::write(path, text)?;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o700))
}

#[cfg(not(unix))]
fn write_private_script(path: &Path, text: &str) -> std::io::Result<()> {
    std::fs::write(path, text)
}

/// Launch the update script (or installer) and exit the process. Returns
/// `Ok(false)` when the update needs a manual install. The caller must close
/// its windows first so no file stays locked.
pub fn apply_update(update_path: &Path, portable: bool) -> std::io::Result<bool> {
    let plan = current_plan(update_path, portable)?;
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
            write_private_script(&script, &build_macos_update_script(update_path, &app_path))?;
            Command::new("bash").arg(&script).spawn()?;
            std::process::exit(0);
        }
        (RestartKind::WindowsInstaller, _) => {
            Command::new(update_path).spawn()?;
            std::process::exit(0);
        }
        (RestartKind::AppImageScript, Some(script)) => {
            let Some(appimage) = running_appimage_path() else {
                return Ok(needs_manual_install(update_path));
            };
            let text = build_appimage_update_script(update_path, &appimage, std::process::id());
            write_private_script(&script, &text)?;
            Command::new("bash").arg(&script).spawn()?;
            std::process::exit(0);
        }
        _ => Ok(needs_manual_install(update_path)),
    }
}

fn needs_manual_install(update_path: &Path) -> bool {
    tracing::warn!(
        "Update requires manual installation: {}",
        update_path.display()
    );
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn windows_portable_runs_unzip_over_the_folder_and_installs_run_setup() {
        let plan = plan_restart(Path::new("C:/temp/update.zip"), true, "windows", None).unwrap();
        assert_eq!(plan.kind, RestartKind::Portable);
        let script = plan.script_path.unwrap();
        assert_eq!(
            script.file_name().unwrap(),
            "accessiweather_portable_update.bat"
        );
        assert_eq!(script.parent().unwrap(), crate::exe_dir());
        let setup = plan_restart(Path::new("C:/t/setup.exe"), false, "windows", None).unwrap();
        assert_eq!(setup.kind, RestartKind::WindowsInstaller);
        assert_eq!(setup.command, ["C:/t/setup.exe"]);
        assert_eq!(setup.script_path, None);
    }

    #[test]
    fn macos_writes_its_script_to_a_private_temp_dir() {
        let plan = plan_restart(Path::new("/tmp/update.zip"), false, "macos", None).unwrap();
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
    fn linux_swaps_a_running_appimage_and_leaves_tarballs_to_the_user() {
        let plan = plan_restart(Path::new("/tmp/a.tar.gz"), false, "linux", None).unwrap();
        assert_eq!(plan.kind, RestartKind::Unsupported);
        assert_eq!(plan.command, ["/tmp/a.tar.gz"]);
        let running = Path::new("/home/u/AccessiWeather.AppImage");
        let not_appimage =
            plan_restart(Path::new("/tmp/a.tar.gz"), false, "linux", Some(running)).unwrap();
        assert_eq!(not_appimage.kind, RestartKind::Unsupported);
        let plan = plan_restart(
            Path::new("/tmp/New.AppImage"),
            false,
            "linux",
            Some(running),
        )
        .unwrap();
        assert_eq!(plan.kind, RestartKind::AppImageScript);
        let script = plan.script_path.unwrap();
        assert_eq!(
            script.file_name().unwrap(),
            "accessiweather_appimage_update.sh"
        );
        std::fs::remove_dir(script.parent().unwrap()).unwrap();
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
