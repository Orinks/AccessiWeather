//! Launch at login (`services/startup_utils.py`, plus the
//! `ConfigManager.enable_startup`/`disable_startup`/`ensure_startup_registration`
//! wrappers), pointing at the Rust executable.
//!
//! The registration names are Python's (Run value `AccessiWeather`, the
//! LaunchAgent label, `accessiweather.desktop`) on purpose: both editions share
//! `startup_enabled` in one settings file, so they must share one login entry
//! too. Separate entries would start both editions at login; with one entry
//! the startup repair re-points it at whichever edition ran last.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::LazyLock;

use regex::Regex;

pub const MACOS_PLIST_LABEL: &str = "net.orinks.accessiweather.startup";
pub const LINUX_DESKTOP_FILENAME: &str = "accessiweather.desktop";
pub const WINDOWS_RUN_VALUE_NAME: &str = "AccessiWeather";
pub const WINDOWS_RUN_KEY_PATH: &str = r"Software\Microsoft\Windows\CurrentVersion\Run";
/// Task Manager / Settings "Startup apps" keep their on/off toggles here.
pub const WINDOWS_STARTUP_APPROVED_RUN_KEY_PATH: &str =
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run";
pub const WINDOWS_STARTUP_APPROVED_FOLDER_KEY_PATH: &str =
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder";
/// Startup-folder shortcut older releases created; only cleaned up now.
pub const WINDOWS_STARTUP_SHORTCUT_NAME: &str = "AccessiWeather.lnk";

pub const STARTUP_ENABLED: &str = "Startup enabled successfully";
pub const STARTUP_ENABLE_FAILED: &str =
    "Failed to enable startup. Check permissions and try again.";
pub const STARTUP_DISABLED: &str = "Startup disabled successfully";
pub const STARTUP_DISABLE_FAILED: &str =
    "Failed to disable startup. Check permissions and try again.";
/// Title of the message box that shows the failure text above.
pub const STARTUP_FAILED_TITLE: &str = "Startup Setting Failed";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Platform {
    Windows,
    MacOs,
    Linux,
}

impl Platform {
    pub fn current() -> Self {
        if cfg!(windows) {
            Self::Windows
        } else if cfg!(target_os = "macos") {
            Self::MacOs
        } else {
            Self::Linux
        }
    }
}

/// What `ensure_startup_registration` decided.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StartupSync {
    /// Registration and setting agree (or the registration was repaired).
    InSync,
    /// Save `startup_enabled` with this value so the setting matches the OS.
    SetSetting(bool),
    /// A repair was needed but failed.
    RepairFailed,
}

/// Manages the login entry for one executable.
#[derive(Debug, Clone)]
pub struct StartupManager {
    pub platform: Platform,
    pub executable: PathBuf,
    /// `Path.home()`: parent of `Library/LaunchAgents` and `.config/autostart`.
    pub home: PathBuf,
    /// `%APPDATA%`, parent of the legacy Startup folder.
    pub appdata: Option<PathBuf>,
    pub run_key: String,
    pub approved_run_key: String,
    pub approved_folder_key: String,
}

impl Default for StartupManager {
    fn default() -> Self {
        Self::new()
    }
}

impl StartupManager {
    /// The running executable on this platform.
    pub fn new() -> Self {
        let home = std::env::var_os("HOME")
            .or_else(|| std::env::var_os("USERPROFILE"))
            .map(PathBuf::from)
            .unwrap_or_default();
        Self {
            platform: Platform::current(),
            executable: crate::exe_path(),
            home,
            appdata: std::env::var_os("APPDATA")
                .filter(|v| !v.is_empty())
                .map(PathBuf::from),
            run_key: WINDOWS_RUN_KEY_PATH.into(),
            approved_run_key: WINDOWS_STARTUP_APPROVED_RUN_KEY_PATH.into(),
            approved_folder_key: WINDOWS_STARTUP_APPROVED_FOLDER_KEY_PATH.into(),
        }
    }

    /// Python's `_get_app_name`: the executable's folder name.
    pub fn app_name(&self) -> String {
        self.executable
            .parent()
            .and_then(Path::file_name)
            .map(|n| n.to_string_lossy().into_owned())
            .filter(|n| !n.is_empty())
            .unwrap_or_else(|| "AccessiWeather".into())
    }

    /// `(executable, args)`; only the Windows Run entry passes `--startup`.
    pub fn launch_command(&self, for_startup: bool) -> (PathBuf, Vec<String>) {
        let args = if for_startup {
            vec!["--startup".to_string()]
        } else {
            Vec::new()
        };
        (self.executable.clone(), args)
    }

    pub fn enable_startup(&self) -> bool {
        tracing::debug!("Enabling startup for platform: {:?}", self.platform);
        match self.platform {
            Platform::Windows => self.enable_windows(),
            Platform::MacOs => self.enable_macos(),
            Platform::Linux => self.enable_linux(),
        }
    }

    pub fn disable_startup(&self) -> bool {
        tracing::debug!("Disabling startup for platform: {:?}", self.platform);
        match self.platform {
            Platform::Windows => self.disable_windows(),
            Platform::MacOs => self.disable_macos(),
            Platform::Linux => self.disable_linux(),
        }
    }

    /// `ConfigManager.enable_startup` / `disable_startup`: success and the
    /// message the settings dialog shows on failure.
    pub fn set_startup(&self, enabled: bool) -> (bool, &'static str) {
        if enabled {
            if self.enable_startup() {
                (true, STARTUP_ENABLED)
            } else {
                (false, STARTUP_ENABLE_FAILED)
            }
        } else if self.disable_startup() {
            (true, STARTUP_DISABLED)
        } else {
            (false, STARTUP_DISABLE_FAILED)
        }
    }

    pub fn is_startup_enabled(&self) -> bool {
        match self.platform {
            Platform::Windows => self.is_windows_enabled(),
            Platform::MacOs => self.is_macos_enabled(),
            Platform::Linux => self.is_linux_enabled(),
        }
    }

    /// Registered, but switched off in Task Manager / Settings "Startup apps".
    pub fn is_startup_disabled_by_os(&self) -> bool {
        if self.platform != Platform::Windows {
            return false;
        }
        if self.read_run_value().is_some() {
            return self.approved_disabled(&self.approved_run_key, WINDOWS_RUN_VALUE_NAME);
        }
        for shortcut in self.legacy_shortcuts() {
            if shortcut.exists() {
                return self.approved_disabled(&self.approved_folder_key, &file_name(&shortcut));
            }
        }
        false
    }

    /// True when the registration launches this executable; a stale path,
    /// a legacy shortcut or an OS-level disable report false.
    pub fn is_startup_registration_current(&self) -> bool {
        if self.platform != Platform::Windows {
            return self.is_startup_enabled();
        }
        if self.read_run_value().as_deref() != Some(self.windows_run_command().as_str()) {
            return false;
        }
        if self.approved_disabled(&self.approved_run_key, WINDOWS_RUN_VALUE_NAME) {
            return false;
        }
        // Leftover legacy shortcuts would double-launch the app at logon.
        !self.legacy_shortcuts().iter().any(|s| s.exists())
    }

    /// Repair the login entry to match the saved `startup_enabled` setting,
    /// respecting an OS-level disable instead of overriding it.
    pub fn ensure_startup_registration(&self, startup_enabled: bool) -> StartupSync {
        if !startup_enabled {
            if self.is_startup_enabled() {
                tracing::info!("Found existing startup registration; enabling setting to match");
                return StartupSync::SetSetting(true);
            }
            return StartupSync::InSync;
        }
        if self.is_startup_disabled_by_os() {
            tracing::info!("Startup was disabled at the OS level; updating setting to match");
            return StartupSync::SetSetting(false);
        }
        if self.is_startup_registration_current() {
            return StartupSync::InSync;
        }
        tracing::info!("Startup registration is missing or stale; re-registering");
        if self.enable_startup() {
            StartupSync::InSync
        } else {
            tracing::warn!("Failed to repair startup registration");
            StartupSync::RepairFailed
        }
    }

    // Windows -------------------------------------------------------------

    pub fn windows_run_command(&self) -> String {
        let (exe, args) = self.launch_command(true);
        let mut all = vec![exe.display().to_string()];
        all.extend(args);
        list2cmdline(&all)
    }

    fn read_run_value(&self) -> Option<String> {
        registry::get_string(&self.run_key, WINDOWS_RUN_VALUE_NAME).filter(|v| !v.is_empty())
    }

    /// StartupApproved flags are REG_BINARY; an odd first byte means disabled.
    fn approved_disabled(&self, key: &str, value: &str) -> bool {
        registry::get_bytes(key, value)
            .and_then(|b| b.first().copied())
            .is_some_and(|b| b & 1 == 1)
    }

    fn startup_folder(&self) -> Option<PathBuf> {
        Some(
            self.appdata
                .as_ref()?
                .join("Microsoft")
                .join("Windows")
                .join("Start Menu")
                .join("Programs")
                .join("Startup"),
        )
    }

    fn legacy_shortcuts(&self) -> Vec<PathBuf> {
        let Some(dir) = self.startup_folder() else {
            return Vec::new();
        };
        let mut shortcuts: Vec<PathBuf> = Vec::new();
        for name in [
            WINDOWS_STARTUP_SHORTCUT_NAME.to_string(),
            format!("{}.lnk", self.app_name()),
            "accessiweather.lnk".to_string(),
        ] {
            let candidate = dir.join(name);
            let key = candidate.display().to_string().to_lowercase();
            if !shortcuts
                .iter()
                .any(|s| s.display().to_string().to_lowercase() == key)
            {
                shortcuts.push(candidate);
            }
        }
        shortcuts
    }

    fn cleanup_legacy_shortcuts(&self) -> bool {
        let mut all_removed = true;
        for shortcut in self.legacy_shortcuts() {
            if shortcut.exists() {
                match std::fs::remove_file(&shortcut) {
                    Ok(()) => tracing::info!(
                        "Removed legacy Windows startup shortcut at {}",
                        shortcut.display()
                    ),
                    Err(e) => tracing::warn!(
                        "Could not remove legacy startup shortcut {}: {e}",
                        shortcut.display()
                    ),
                }
            }
            if shortcut.exists() {
                all_removed = false;
            } else {
                // Drop the Task Manager flag so it cannot affect a future shortcut.
                registry::delete_value(&self.approved_folder_key, &file_name(&shortcut));
            }
        }
        all_removed
    }

    fn enable_windows(&self) -> bool {
        let command = self.windows_run_command();
        if !registry::set_string(&self.run_key, WINDOWS_RUN_VALUE_NAME, &command) {
            return false;
        }
        // Enabling is an explicit request, so clear a stale Task Manager "off".
        registry::delete_value(&self.approved_run_key, WINDOWS_RUN_VALUE_NAME);
        self.cleanup_legacy_shortcuts();
        tracing::info!("Registered Windows startup Run entry: {command}");
        true
    }

    fn disable_windows(&self) -> bool {
        let run_removed = registry::delete_value(&self.run_key, WINDOWS_RUN_VALUE_NAME);
        registry::delete_value(&self.approved_run_key, WINDOWS_RUN_VALUE_NAME);
        let shortcuts_removed = self.cleanup_legacy_shortcuts();
        let removed = run_removed && shortcuts_removed;
        if removed {
            tracing::info!("Windows startup registration removed");
        }
        removed
    }

    fn is_windows_enabled(&self) -> bool {
        // Keyed on the value name, not the command: a stale path after an
        // update still means "start with Windows" and gets repaired.
        if self.read_run_value().is_some() {
            return !self.approved_disabled(&self.approved_run_key, WINDOWS_RUN_VALUE_NAME);
        }
        for shortcut in self.legacy_shortcuts() {
            if shortcut.exists() {
                return !self.approved_disabled(&self.approved_folder_key, &file_name(&shortcut));
            }
        }
        false
    }

    // macOS ---------------------------------------------------------------

    fn plist_path(&self) -> std::io::Result<PathBuf> {
        let dir = self.home.join("Library").join("LaunchAgents");
        std::fs::create_dir_all(&dir)?;
        Ok(dir.join(format!("{MACOS_PLIST_LABEL}.plist")))
    }

    /// The LaunchAgent plist `plistlib.dump` writes.
    pub fn macos_plist(&self) -> String {
        let (exe, args) = self.launch_command(false);
        let working_directory = self
            .executable
            .parent()
            .map(|p| p.display().to_string())
            .unwrap_or_default();
        let mut program = format!(
            "\t\t<string>{}</string>\n",
            xml_escape(&exe.display().to_string())
        );
        for arg in &args {
            program.push_str(&format!("\t\t<string>{}</string>\n", xml_escape(arg)));
        }
        format!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n\
             <!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n\
             <plist version=\"1.0\">\n<dict>\n\
             \t<key>KeepAlive</key>\n\t<false/>\n\
             \t<key>Label</key>\n\t<string>{MACOS_PLIST_LABEL}</string>\n\
             \t<key>ProgramArguments</key>\n\t<array>\n{program}\t</array>\n\
             \t<key>RunAtLoad</key>\n\t<true/>\n\
             \t<key>WorkingDirectory</key>\n\t<string>{}</string>\n\
             </dict>\n</plist>\n",
            xml_escape(&working_directory)
        )
    }

    fn enable_macos(&self) -> bool {
        let result = self.plist_path().and_then(|path| {
            std::fs::write(&path, self.macos_plist())?;
            tracing::info!("Created macOS LaunchAgent plist at {}", path.display());
            launchctl(
                "load",
                &path,
                "Failed to load macOS LaunchAgent immediately via launchctl",
            );
            Ok(())
        });
        result
            .inspect_err(|e| tracing::error!("Failed enabling macOS startup: {e}"))
            .is_ok()
    }

    fn disable_macos(&self) -> bool {
        let result = self.plist_path().and_then(|path| {
            if path.exists() {
                launchctl(
                    "unload",
                    &path,
                    "Failed to unload macOS LaunchAgent via launchctl",
                );
                std::fs::remove_file(&path)?;
                tracing::info!("Removed macOS LaunchAgent plist at {}", path.display());
            }
            Ok(())
        });
        result
            .inspect_err(|e| tracing::error!("Failed disabling macOS startup: {e}"))
            .is_ok()
    }

    fn is_macos_enabled(&self) -> bool {
        let Ok(path) = self.plist_path() else {
            return false;
        };
        let Ok(text) = std::fs::read_to_string(&path) else {
            return false;
        };
        let (exe, args) = self.launch_command(false);
        let mut expected = vec![exe.display().to_string()];
        expected.extend(args);
        plist_program_arguments(&text).is_some_and(|a| !a.is_empty() && a == expected)
    }

    // Linux ---------------------------------------------------------------

    fn desktop_entry_path(&self) -> std::io::Result<PathBuf> {
        let dir = self.home.join(".config").join("autostart");
        std::fs::create_dir_all(&dir)?;
        Ok(dir.join(LINUX_DESKTOP_FILENAME))
    }

    /// The autostart `.desktop` file (`_build_desktop_entry`).
    pub fn linux_desktop_entry(&self) -> String {
        let (exe, args) = self.launch_command(false);
        let mut exec = format!("\"{}\"", exe.display().to_string().replace('"', "\\\""));
        for arg in &args {
            exec.push(' ');
            exec.push_str(&crate::update_restart::shlex_quote(arg));
        }
        [
            "[Desktop Entry]".to_string(),
            "Type=Application".into(),
            "Version=1.0".into(),
            format!("Name={}", self.app_name()),
            "Comment=Start AccessiWeather at login".into(),
            format!("Exec={}", exec.trim()),
            "X-GNOME-Autostart-enabled=true".into(),
        ]
        .join("\n")
            + "\n"
    }

    fn enable_linux(&self) -> bool {
        let result = self.desktop_entry_path().and_then(|path| {
            std::fs::write(&path, self.linux_desktop_entry())?;
            tracing::info!(
                "Created Linux autostart desktop entry at {}",
                path.display()
            );
            Ok(())
        });
        result
            .inspect_err(|e| tracing::error!("Failed enabling Linux startup: {e}"))
            .is_ok()
    }

    fn disable_linux(&self) -> bool {
        let result = self.desktop_entry_path().and_then(|path| {
            if path.exists() {
                std::fs::remove_file(&path)?;
                tracing::info!(
                    "Removed Linux autostart desktop entry at {}",
                    path.display()
                );
            }
            Ok(())
        });
        result
            .inspect_err(|e| tracing::error!("Failed disabling Linux startup: {e}"))
            .is_ok()
    }

    fn is_linux_enabled(&self) -> bool {
        let Ok(path) = self.desktop_entry_path() else {
            return false;
        };
        let Ok(text) = std::fs::read_to_string(&path) else {
            return false;
        };
        let Some(exec) = desktop_entry_exec(&text).filter(|e| !e.is_empty()) else {
            return false;
        };
        let Some(tokens) = shlex_split(&exec) else {
            tracing::warn!("Failed parsing Exec entry in {}", path.display());
            return false;
        };
        let (exe, args) = self.launch_command(false);
        let mut expected = vec![exe.display().to_string()];
        expected.extend(args);
        tokens == expected
    }
}

fn file_name(path: &Path) -> String {
    path.file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default()
}

fn launchctl(action: &str, plist: &Path, failure: &str) {
    match Command::new("launchctl")
        .args([action, "-w"])
        .arg(plist)
        .output()
    {
        Ok(out) if !out.status.success() => {
            tracing::warn!("{failure}: {}", String::from_utf8_lossy(&out.stderr))
        }
        Ok(_) => {}
        Err(_) => tracing::warn!(
            "launchctl not found; macOS startup changes will take effect after next login"
        ),
    }
}

/// `subprocess.list2cmdline`: MS C runtime quoting.
pub fn list2cmdline(args: &[String]) -> String {
    let mut result = String::new();
    for arg in args {
        if !result.is_empty() {
            result.push(' ');
        }
        let needquote = arg.contains(' ') || arg.contains('\t') || arg.is_empty();
        if needquote {
            result.push('"');
        }
        let mut backslashes = 0;
        for c in arg.chars() {
            match c {
                '\\' => backslashes += 1,
                '"' => {
                    result.push_str(&"\\".repeat(backslashes * 2));
                    backslashes = 0;
                    result.push_str("\\\"");
                }
                _ => {
                    result.push_str(&"\\".repeat(backslashes));
                    backslashes = 0;
                    result.push(c);
                }
            }
        }
        result.push_str(&"\\".repeat(backslashes));
        if needquote {
            result.push_str(&"\\".repeat(backslashes));
            result.push('"');
        }
    }
    result
}

fn xml_escape(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn plist_program_arguments(text: &str) -> Option<Vec<String>> {
    static ARGS: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"(?s)<key>ProgramArguments</key>\s*<array>(.*?)</array>").expect("valid regex")
    });
    static STRING: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r"(?s)<string>(.*?)</string>").expect("valid regex"));
    let body = ARGS.captures(text)?;
    Some(
        STRING
            .captures_iter(&body[1])
            .map(|c| {
                c[1].replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&amp;", "&")
            })
            .collect(),
    )
}

/// `Exec` from the `[Desktop Entry]` section, read the way `configparser` does.
fn desktop_entry_exec(text: &str) -> Option<String> {
    let mut in_section = false;
    for line in text.lines() {
        let line = line.trim();
        if line.starts_with('[') && line.ends_with(']') {
            in_section = &line[1..line.len() - 1] == "Desktop Entry";
            continue;
        }
        if line.is_empty() || !in_section || line.starts_with('#') || line.starts_with(';') {
            continue;
        }
        let split = line.find(['=', ':'])?;
        if line[..split].trim().eq_ignore_ascii_case("exec") {
            return Some(line[split + 1..].trim().to_string());
        }
    }
    None
}

/// POSIX `shlex.split`; `None` on unbalanced quotes.
fn shlex_split(text: &str) -> Option<Vec<String>> {
    let mut tokens = Vec::new();
    let mut current: Option<String> = None;
    let mut chars = text.chars();
    while let Some(c) = chars.next() {
        match c {
            c if c.is_whitespace() => {
                if let Some(tok) = current.take() {
                    tokens.push(tok);
                }
            }
            '\'' => {
                let tok = current.get_or_insert_with(String::new);
                loop {
                    match chars.next()? {
                        '\'' => break,
                        ch => tok.push(ch),
                    }
                }
            }
            '"' => {
                let tok = current.get_or_insert_with(String::new);
                loop {
                    match chars.next()? {
                        '"' => break,
                        '\\' => match chars.next()? {
                            ch @ ('\\' | '"') => tok.push(ch),
                            ch => {
                                tok.push('\\');
                                tok.push(ch);
                            }
                        },
                        ch => tok.push(ch),
                    }
                }
            }
            '\\' => current.get_or_insert_with(String::new).push(chars.next()?),
            ch => current.get_or_insert_with(String::new).push(ch),
        }
    }
    tokens.extend(current);
    Some(tokens)
}

/// A `HKEY_LOCAL_MACHINE` string value.
#[cfg(windows)]
pub(crate) fn machine_registry_string(key: &str, value: &str) -> Option<String> {
    registry::get_string_in(
        windows_sys::Win32::System::Registry::HKEY_LOCAL_MACHINE,
        key,
        value,
    )
}

#[cfg(windows)]
mod registry {
    //! HKCU values through the single-call registry APIs.

    use std::ptr::null_mut;
    use windows_sys::Win32::Foundation::ERROR_SUCCESS;
    use windows_sys::Win32::System::Registry::{
        RegDeleteKeyValueW, RegGetValueW, RegSetKeyValueW, HKEY, HKEY_CURRENT_USER, REG_SZ,
        RRF_NOEXPAND, RRF_RT_ANY, RRF_RT_REG_EXPAND_SZ, RRF_RT_REG_SZ,
    };

    fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain(Some(0)).collect()
    }

    fn get_raw(root: HKEY, key: &str, value: &str, flags: u32) -> Option<Vec<u8>> {
        let (key, value) = (wide(key), wide(value));
        let mut size = 0u32;
        // SAFETY: NUL-terminated strings; first call only asks for the size.
        let rc = unsafe {
            RegGetValueW(
                root,
                key.as_ptr(),
                value.as_ptr(),
                flags,
                null_mut(),
                null_mut(),
                &mut size,
            )
        };
        if rc != ERROR_SUCCESS {
            return None;
        }
        let mut buf = vec![0u8; size as usize];
        // SAFETY: `buf` holds `size` bytes as the API requested.
        let rc = unsafe {
            RegGetValueW(
                root,
                key.as_ptr(),
                value.as_ptr(),
                flags,
                null_mut(),
                buf.as_mut_ptr().cast(),
                &mut size,
            )
        };
        (rc == ERROR_SUCCESS).then(|| {
            buf.truncate(size as usize);
            buf
        })
    }

    pub fn get_string(key: &str, value: &str) -> Option<String> {
        get_string_in(HKEY_CURRENT_USER, key, value)
    }

    pub fn get_string_in(root: HKEY, key: &str, value: &str) -> Option<String> {
        let raw = get_raw(
            root,
            key,
            value,
            RRF_RT_REG_SZ | RRF_RT_REG_EXPAND_SZ | RRF_NOEXPAND,
        )?;
        let units: Vec<u16> = raw
            .as_chunks::<2>()
            .0
            .iter()
            .map(|c| u16::from_le_bytes(*c))
            .take_while(|&u| u != 0)
            .collect();
        Some(String::from_utf16_lossy(&units))
    }

    pub fn get_bytes(key: &str, value: &str) -> Option<Vec<u8>> {
        get_raw(HKEY_CURRENT_USER, key, value, RRF_RT_ANY)
    }

    pub fn set_string(key: &str, value: &str, data: &str) -> bool {
        let (k, v, d) = (wide(key), wide(value), wide(data));
        // SAFETY: NUL-terminated strings; size includes the terminator.
        let rc = unsafe {
            RegSetKeyValueW(
                HKEY_CURRENT_USER,
                k.as_ptr(),
                v.as_ptr(),
                REG_SZ,
                d.as_ptr().cast(),
                (d.len() * 2) as u32,
            )
        };
        if rc != ERROR_SUCCESS {
            tracing::error!("Failed writing Windows startup Run value: error {rc}");
        }
        rc == ERROR_SUCCESS
    }

    /// True when the value no longer exists.
    pub fn delete_value(key: &str, value: &str) -> bool {
        use windows_sys::Win32::Foundation::ERROR_FILE_NOT_FOUND;
        let (k, v) = (wide(key), wide(value));
        // SAFETY: NUL-terminated strings.
        let rc = unsafe { RegDeleteKeyValueW(HKEY_CURRENT_USER, k.as_ptr(), v.as_ptr()) };
        let ok = rc == ERROR_SUCCESS || rc == ERROR_FILE_NOT_FOUND;
        if !ok {
            tracing::error!("Failed deleting registry value {key}\\{value}: error {rc}");
        }
        ok
    }

    #[cfg(test)]
    pub fn delete_tree(key: &str) {
        let k = wide(key);
        // SAFETY: NUL-terminated string.
        unsafe {
            windows_sys::Win32::System::Registry::RegDeleteTreeW(HKEY_CURRENT_USER, k.as_ptr())
        };
    }
}

#[cfg(not(windows))]
mod registry {
    //! No registry off Windows (Python's `winreg is None`).

    pub fn get_string(_key: &str, _value: &str) -> Option<String> {
        None
    }

    pub fn get_bytes(_key: &str, _value: &str) -> Option<Vec<u8>> {
        None
    }

    pub fn set_string(_key: &str, _value: &str, _data: &str) -> bool {
        false
    }

    pub fn delete_value(_key: &str, _value: &str) -> bool {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn manager(platform: Platform, home: &Path, exe: &str) -> StartupManager {
        StartupManager {
            platform,
            executable: PathBuf::from(exe),
            home: home.to_path_buf(),
            appdata: Some(home.join("AppData")),
            ..StartupManager::new()
        }
    }

    #[test]
    fn list2cmdline_matches_python() {
        let cmd = |a: &[&str]| list2cmdline(&a.iter().map(|s| s.to_string()).collect::<Vec<_>>());
        assert_eq!(
            cmd(&[
                r"C:\Program Files\AccessiWeather\AccessiWeather.exe",
                "--startup"
            ]),
            r#""C:\Program Files\AccessiWeather\AccessiWeather.exe" --startup"#
        );
        assert_eq!(cmd(&[r"C:\a\b.exe"]), r"C:\a\b.exe");
        assert_eq!(cmd(&[r#"a"b"#, "", r"c d\"]), r#"a\"b "" "c d\\""#);
    }

    #[test]
    fn linux_entry_round_trips_and_rejects_stale_targets() {
        let home = tempfile::tempdir().unwrap();
        let m = manager(
            Platform::Linux,
            home.path(),
            "/opt/My Apps/accessiweather/accessiweather",
        );
        assert!(!m.is_startup_enabled());
        assert!(m.enable_startup());
        let entry =
            std::fs::read_to_string(home.path().join(".config/autostart/accessiweather.desktop"))
                .unwrap();
        assert!(entry.contains("Name=accessiweather\n"));
        assert!(entry.contains("Exec=\"/opt/My Apps/accessiweather/accessiweather\"\n"));
        assert!(m.is_startup_enabled());
        assert_eq!(m.ensure_startup_registration(true), StartupSync::InSync);

        let moved = manager(Platform::Linux, home.path(), "/opt/other/accessiweather");
        assert!(!moved.is_startup_enabled());
        assert_eq!(
            moved.ensure_startup_registration(false),
            StartupSync::InSync
        );
        assert_eq!(moved.ensure_startup_registration(true), StartupSync::InSync);
        assert!(moved.is_startup_enabled());

        assert_eq!(moved.set_startup(false), (true, STARTUP_DISABLED));
        assert!(!moved.is_startup_enabled());
    }

    #[test]
    fn macos_plist_is_read_back_and_stale_arguments_rejected() {
        let home = tempfile::tempdir().unwrap();
        let m = manager(
            Platform::MacOs,
            home.path(),
            "/Applications/A & B.app/Contents/MacOS/AccessiWeather",
        );
        assert!(!m.is_startup_enabled());
        let agents = home.path().join("Library/LaunchAgents");
        std::fs::create_dir_all(&agents).unwrap();
        let plist = agents.join(format!("{MACOS_PLIST_LABEL}.plist"));
        std::fs::write(&plist, m.macos_plist()).unwrap();
        assert!(m.macos_plist().contains("A &amp; B.app"));
        assert!(m.is_startup_enabled());
        let other = manager(
            Platform::MacOs,
            home.path(),
            "/Applications/Old.app/Contents/MacOS/AccessiWeather",
        );
        assert!(!other.is_startup_enabled());
    }

    #[test]
    fn shlex_split_handles_posix_quoting() {
        assert_eq!(
            shlex_split(r#""/a b/c" 'd e' f\ g "h\"i""#).unwrap(),
            ["/a b/c", "d e", "f g", "h\"i"]
        );
        assert!(shlex_split("\"open").is_none());
    }

    #[cfg(windows)]
    mod windows_registry {
        use super::*;

        const APPROVED_DISABLED: [u8; 12] = [3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        const APPROVED_ENABLED: [u8; 12] = [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

        /// A manager writing under a throwaway HKCU key instead of the real Run key.
        struct Sandbox {
            root: String,
            home: tempfile::TempDir,
        }

        impl Sandbox {
            fn new(tag: &str) -> Self {
                Self {
                    root: format!(r"Software\AccessiWeatherTest-{}-{tag}", std::process::id()),
                    home: tempfile::tempdir().unwrap(),
                }
            }

            fn manager(&self, exe: &str) -> StartupManager {
                StartupManager {
                    run_key: format!(r"{}\Run", self.root),
                    approved_run_key: format!(r"{}\ApprovedRun", self.root),
                    approved_folder_key: format!(r"{}\ApprovedFolder", self.root),
                    ..manager(Platform::Windows, self.home.path(), exe)
                }
            }

            fn startup_dir(&self) -> PathBuf {
                let dir = self
                    .home
                    .path()
                    .join(r"AppData\Microsoft\Windows\Start Menu\Programs\Startup");
                std::fs::create_dir_all(&dir).unwrap();
                dir
            }

            fn set_flag(&self, key: &str, name: &str, flag: &[u8]) {
                use windows_sys::Win32::System::Registry::{
                    RegSetKeyValueW, HKEY_CURRENT_USER, REG_BINARY,
                };
                let k: Vec<u16> = key.encode_utf16().chain(Some(0)).collect();
                let n: Vec<u16> = name.encode_utf16().chain(Some(0)).collect();
                // SAFETY: NUL-terminated strings and a valid buffer.
                unsafe {
                    RegSetKeyValueW(
                        HKEY_CURRENT_USER,
                        k.as_ptr(),
                        n.as_ptr(),
                        REG_BINARY,
                        flag.as_ptr().cast(),
                        flag.len() as u32,
                    )
                };
            }
        }

        impl Drop for Sandbox {
            fn drop(&mut self) {
                registry::delete_tree(&self.root);
            }
        }

        const EXE: &str = r"C:\Program Files\AccessiWeather\AccessiWeather.exe";

        #[test]
        fn enable_writes_quoted_command_and_clears_task_manager_flag() {
            let sb = Sandbox::new("enable");
            let m = sb.manager(EXE);
            assert!(!m.is_startup_enabled());
            sb.set_flag(
                &m.approved_run_key,
                WINDOWS_RUN_VALUE_NAME,
                &APPROVED_DISABLED,
            );
            assert!(m.enable_startup());
            assert_eq!(
                registry::get_string(&m.run_key, WINDOWS_RUN_VALUE_NAME).unwrap(),
                format!("\"{EXE}\" --startup")
            );
            assert!(registry::get_bytes(&m.approved_run_key, WINDOWS_RUN_VALUE_NAME).is_none());
            assert!(m.is_startup_enabled());
            assert!(m.is_startup_registration_current());
            assert!(m.disable_startup());
            assert!(!m.is_startup_enabled());
        }

        #[test]
        fn stale_command_still_reads_enabled_and_is_repaired() {
            let sb = Sandbox::new("stale");
            let old = sb.manager(r"C:\Old\AccessiWeather.exe");
            assert!(old.enable_startup());
            let m = sb.manager(EXE);
            assert!(m.is_startup_enabled());
            assert!(!m.is_startup_registration_current());
            assert_eq!(m.ensure_startup_registration(true), StartupSync::InSync);
            assert!(m.is_startup_registration_current());
        }

        #[test]
        fn task_manager_disable_is_respected() {
            let sb = Sandbox::new("approved");
            let m = sb.manager(EXE);
            assert!(m.enable_startup());
            sb.set_flag(
                &m.approved_run_key,
                WINDOWS_RUN_VALUE_NAME,
                &APPROVED_ENABLED,
            );
            assert!(m.is_startup_enabled());
            sb.set_flag(
                &m.approved_run_key,
                WINDOWS_RUN_VALUE_NAME,
                &APPROVED_DISABLED,
            );
            assert!(!m.is_startup_enabled());
            assert!(m.is_startup_disabled_by_os());
            assert!(!m.is_startup_registration_current());
            assert_eq!(
                m.ensure_startup_registration(true),
                StartupSync::SetSetting(false)
            );
            assert_eq!(m.ensure_startup_registration(false), StartupSync::InSync);
        }

        #[test]
        fn setting_adopts_an_existing_registration() {
            let sb = Sandbox::new("adopt");
            let m = sb.manager(EXE);
            assert_eq!(m.ensure_startup_registration(false), StartupSync::InSync);
            assert!(m.enable_startup());
            assert_eq!(
                m.ensure_startup_registration(false),
                StartupSync::SetSetting(true)
            );
        }

        #[test]
        fn legacy_shortcuts_count_as_enabled_and_are_migrated() {
            let sb = Sandbox::new("legacy");
            let m = sb.manager(EXE);
            let shortcut = sb.startup_dir().join("AccessiWeather.lnk");
            std::fs::write(&shortcut, b"lnk").unwrap();
            assert!(m.is_startup_enabled());
            sb.set_flag(
                &m.approved_folder_key,
                "AccessiWeather.lnk",
                &APPROVED_DISABLED,
            );
            assert!(!m.is_startup_enabled());
            assert!(m.is_startup_disabled_by_os());
            sb.set_flag(
                &m.approved_folder_key,
                "AccessiWeather.lnk",
                &APPROVED_ENABLED,
            );
            assert!(!m.is_startup_registration_current());
            assert_eq!(m.ensure_startup_registration(true), StartupSync::InSync);
            assert!(!shortcut.exists());
            assert!(registry::get_bytes(&m.approved_folder_key, "AccessiWeather.lnk").is_none());
            assert!(m.is_startup_registration_current());
        }

        #[test]
        fn disable_succeeds_without_appdata() {
            let sb = Sandbox::new("noappdata");
            let m = StartupManager {
                appdata: None,
                ..sb.manager(EXE)
            };
            assert!(m.disable_startup());
            assert_eq!(m.set_startup(true), (true, STARTUP_ENABLED));
            assert!(m.is_startup_enabled());
        }
    }
}
