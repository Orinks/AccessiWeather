//! Windows toasts through WinRT, plus the toast identity setup
//! (`windows_toast_identity.py`, `windows_toast_identity_shortcuts.py` and
//! `toasted.Toast.register_app_id`).

use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Sender};

use serde_json::{json, Value};
use windows::core::{Interface, GUID, HSTRING, PCWSTR, PWSTR};
use windows::Data::Xml::Dom::XmlDocument;
use windows::Win32::Foundation::{ERROR_SUCCESS, MAX_PATH, PROPERTYKEY};
use windows::Win32::Storage::EnhancedStorage::{
    PKEY_AppUserModel_ID, PKEY_AppUserModel_ToastActivatorCLSID,
};
use windows::Win32::System::Com::StructuredStorage::{InitPropVariantFromCLSID, PROPVARIANT};
use windows::Win32::System::Com::{
    CoCreateInstance, CoInitializeEx, CoTaskMemAlloc, IPersistFile, CLSCTX_INPROC_SERVER,
    COINIT_APARTMENTTHREADED, STGM_READ,
};
use windows::Win32::System::Registry::{
    RegCloseKey, RegCreateKeyExW, RegOpenKeyExW, RegSetValueExW, HKEY, HKEY_CURRENT_USER, KEY_READ,
    KEY_WRITE, REG_DWORD, REG_EXPAND_SZ, REG_OPTION_NON_VOLATILE, REG_SZ, REG_VALUE_TYPE,
};
use windows::Win32::System::Variant::{VT_CLSID, VT_LPWSTR};
use windows::Win32::System::WinRT::{RoInitialize, RO_INIT_MULTITHREADED};
use windows::Win32::UI::Shell::PropertiesSystem::{
    IPropertyStore, SHGetPropertyStoreFromParsingName, GPS_DEFAULT, GPS_READWRITE,
};
use windows::Win32::UI::Shell::{IShellLinkW, SetCurrentProcessExplicitAppUserModelID, ShellLink};
use windows::UI::Notifications::{ToastNotification, ToastNotificationManager};

use super::{
    APP_NAME, WINDOWS_APP_USER_MODEL_ID, WINDOWS_TOAST_ACTIVATOR_CLSID,
    WINDOWS_TOAST_PROTOCOL_SCHEME,
};
use crate::py;

/// WinRT drops a toast's handlers once nothing references it; Python keeps
/// the last 20 alive for Action Center.
const MAX_LIVE_NOTIFICATIONS: usize = 20;
const TOAST_IDENTITY_SCHEMA_VERSION: i64 = 2;

pub(super) struct Backend {
    tx: Sender<String>,
}

impl Backend {
    pub(super) fn new(app_name: &str) -> Self {
        let (tx, rx) = mpsc::channel::<String>();
        let app_name = app_name.to_string();
        let spawned = std::thread::Builder::new()
            .name("ToastedNotifierWorker".into())
            .spawn(move || {
                // SAFETY: plain WinRT apartment initialisation for this thread.
                if let Err(e) = unsafe { RoInitialize(RO_INIT_MULTITHREADED) } {
                    tracing::debug!("[toasted] RoInitialize: {e}");
                }
                register_app_id(&app_name);
                let mut live = VecDeque::new();
                for xml in rx {
                    match show_toast(&xml) {
                        Ok(n) => {
                            live.push_back(n);
                            if live.len() > MAX_LIVE_NOTIFICATIONS {
                                live.pop_front();
                            }
                        }
                        Err(e) => tracing::warn!("[toasted] Direct WinRT show failed: {e}"),
                    }
                }
            });
        if let Err(e) = spawned {
            tracing::error!("Toasted worker thread failed to start: {e}");
        }
        Self { tx }
    }

    pub(super) fn show(&self, xml: String) -> bool {
        self.tx.send(xml).is_ok()
    }
}

fn show_toast(xml: &str) -> windows::core::Result<ToastNotification> {
    let doc = XmlDocument::new()?;
    doc.LoadXml(&HSTRING::from(xml))?;
    let notification = ToastNotification::CreateToastNotification(&doc)?;
    ToastNotificationManager::CreateToastNotifierWithId(&HSTRING::from(WINDOWS_APP_USER_MODEL_ID))?
        .Show(&notification)?;
    Ok(notification)
}

// ---------------------------------------------------------------------------
// Registry helpers
// ---------------------------------------------------------------------------

struct RegKey(HKEY);

impl Drop for RegKey {
    fn drop(&mut self) {
        // SAFETY: the handle came from RegCreateKeyExW/RegOpenKeyExW.
        unsafe {
            let _ = RegCloseKey(self.0);
        }
    }
}

fn reg_create(path: &str) -> Option<RegKey> {
    let mut key = HKEY::default();
    // SAFETY: valid NUL-terminated strings and an out pointer we own.
    let status = unsafe {
        RegCreateKeyExW(
            HKEY_CURRENT_USER,
            &HSTRING::from(path),
            None,
            PCWSTR::null(),
            REG_OPTION_NON_VOLATILE,
            KEY_WRITE,
            None,
            &mut key,
            None,
        )
    };
    (status == ERROR_SUCCESS).then_some(RegKey(key))
}

fn reg_exists(path: &str) -> bool {
    let mut key = HKEY::default();
    // SAFETY: as above.
    let status = unsafe {
        RegOpenKeyExW(
            HKEY_CURRENT_USER,
            &HSTRING::from(path),
            None,
            KEY_READ,
            &mut key,
        )
    };
    if status == ERROR_SUCCESS {
        drop(RegKey(key));
        true
    } else {
        false
    }
}

fn reg_set(key: &RegKey, name: Option<&str>, kind: REG_VALUE_TYPE, data: &[u8]) -> bool {
    let name = name.map(HSTRING::from);
    let name_ptr = name.as_ref().map_or(PCWSTR::null(), |n| PCWSTR(n.as_ptr()));
    // SAFETY: the name outlives the call and `data` is a valid byte slice.
    unsafe { RegSetValueExW(key.0, name_ptr, None, kind, Some(data)) == ERROR_SUCCESS }
}

fn reg_set_string(key: &RegKey, name: Option<&str>, value: &str, kind: REG_VALUE_TYPE) -> bool {
    let bytes: Vec<u8> = value
        .encode_utf16()
        .chain(std::iter::once(0))
        .flat_map(u16::to_le_bytes)
        .collect();
    reg_set(key, name, kind, &bytes)
}

/// `toasted.Toast.register_app_id`, only when the AUMID is not registered yet.
fn register_app_id(display_name: &str) {
    let path = format!(r"SOFTWARE\Classes\AppUserModelId\{WINDOWS_APP_USER_MODEL_ID}");
    if reg_exists(&path) {
        return;
    }
    let Some(key) = reg_create(&path) else {
        tracing::warn!("Failed to register toasted app ID: {WINDOWS_APP_USER_MODEL_ID}");
        return;
    };
    reg_set_string(&key, Some("DisplayName"), display_name, REG_EXPAND_SZ);
    reg_set_string(&key, Some("IconBackgroundColor"), "00000000", REG_SZ);
    reg_set_string(&key, Some("IconUri"), "", REG_SZ);
    reg_set(&key, Some("ShowInSettings"), REG_DWORD, &1u32.to_le_bytes());
}

// ---------------------------------------------------------------------------
// Toast identity (shortcut + AUMID + protocol handler)
// ---------------------------------------------------------------------------

static IDENTITY_ENSURED: AtomicBool = AtomicBool::new(false);

fn exe_path() -> Option<String> {
    let exe = std::env::current_exe().ok()?;
    let s = exe.to_string_lossy();
    Some(s.strip_prefix(r"\\?\").unwrap_or(&s).to_string())
}

fn roaming_appdata() -> Option<PathBuf> {
    let home = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME"))?;
    Some(PathBuf::from(home).join("AppData").join("Roaming"))
}

/// `subprocess.list2cmdline`.
fn list2cmdline(args: &[&str]) -> String {
    let mut out = String::new();
    for arg in args {
        if !out.is_empty() {
            out.push(' ');
        }
        let quote = arg.is_empty() || arg.contains([' ', '\t']);
        if quote {
            out.push('"');
        }
        let mut backslashes = 0;
        for c in arg.chars() {
            match c {
                '\\' => backslashes += 1,
                '"' => {
                    out.push_str(&"\\".repeat(backslashes * 2 + 1));
                    out.push('"');
                    backslashes = 0;
                }
                c => {
                    out.push_str(&"\\".repeat(backslashes));
                    backslashes = 0;
                    out.push(c);
                }
            }
        }
        out.push_str(&"\\".repeat(if quote { backslashes * 2 } else { backslashes }));
        if quote {
            out.push('"');
        }
    }
    out
}

/// `_register_protocol_activation_handler`: `accessiweather-toast:` URIs
/// relaunch this exe with the URI as its argument.
fn register_protocol_handler(exe: &str) -> bool {
    let base = format!(r"Software\Classes\{WINDOWS_TOAST_PROTOCOL_SCHEME}");
    let command = list2cmdline(&[exe, "%1"]);
    let ok = (|| {
        let root = reg_create(&base)?;
        (reg_set_string(&root, None, "URL:AccessiWeather Toast", REG_SZ)
            && reg_set_string(&root, Some("URL Protocol"), "", REG_SZ))
        .then_some(())?;
        let icon = reg_create(&format!(r"{base}\DefaultIcon"))?;
        reg_set_string(&icon, None, exe, REG_SZ).then_some(())?;
        let cmd = reg_create(&format!(r"{base}\shell\open\command"))?;
        reg_set_string(&cmd, None, &command, REG_SZ).then_some(())
    })()
    .is_some();
    if !ok {
        tracing::warn!(
            "[notify-init] Failed to register protocol handler {WINDOWS_TOAST_PROTOCOL_SCHEME}"
        );
    }
    ok
}

/// `_resolve_start_menu_shortcut_path`.
fn resolve_start_menu_shortcut_path(appdata: &Path) -> PathBuf {
    let programs = appdata
        .join("Microsoft")
        .join("Windows")
        .join("Start Menu")
        .join("Programs");
    let file = format!("{APP_NAME}.lnk");
    let nested = programs.join(APP_NAME).join(&file);
    let top = programs.join(&file);
    if nested.exists() {
        return nested;
    }
    if top.exists() {
        return top;
    }
    let mut found = Vec::new();
    find_files(&programs, &file, &mut found);
    found.sort_by_key(|p| p.to_string_lossy().to_lowercase());
    found.into_iter().next().unwrap_or(nested)
}

fn find_files(dir: &Path, name: &str, out: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        match entry.file_type() {
            Ok(t) if t.is_dir() => find_files(&path, name, out),
            Ok(t)
                if t.is_file()
                    && entry
                        .file_name()
                        .to_string_lossy()
                        .eq_ignore_ascii_case(name) =>
            {
                out.push(path)
            }
            _ => {}
        }
    }
}

fn normalize_clsid(clsid: Option<&str>) -> Option<String> {
    let hex: String = clsid?.chars().filter(|c| c.is_ascii_hexdigit()).collect();
    let v = u128::from_str_radix(&hex, 16)
        .ok()
        .filter(|_| hex.len() == 32)?;
    Some(guid_to_string(&GUID::from_u128(v)))
}

fn guid_to_string(g: &GUID) -> String {
    format!(
        "{{{:08X}-{:04X}-{:04X}-{:02X}{:02X}-{:02X}{:02X}{:02X}{:02X}{:02X}{:02X}}}",
        g.data1,
        g.data2,
        g.data3,
        g.data4[0],
        g.data4[1],
        g.data4[2],
        g.data4[3],
        g.data4[4],
        g.data4[5],
        g.data4[6],
        g.data4[7]
    )
}

fn activator_guid() -> GUID {
    GUID::from_u128(0x0D3C3F8E_7303_4C9B_81C7_FF8D8C1AFC07)
}

fn create_shortcut(shortcut: &Path, target: &str) -> bool {
    if let Some(parent) = shortcut.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let working_dir = Path::new(target)
        .parent()
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_default();
    // SAFETY: COM calls on interfaces we created; strings outlive the calls.
    let result = unsafe {
        (|| -> windows::core::Result<()> {
            let link: IShellLinkW = CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER)?;
            link.SetPath(&HSTRING::from(target))?;
            link.SetWorkingDirectory(&HSTRING::from(working_dir.as_str()))?;
            link.SetDescription(&HSTRING::from(APP_NAME))?;
            link.SetIconLocation(&HSTRING::from(target), 0)?;
            link.cast::<IPersistFile>()?
                .Save(&HSTRING::from(shortcut.as_os_str()), true)
        })()
    };
    if let Err(e) = &result {
        tracing::warn!("[notify-init] Shortcut creation failed: {e}");
    }
    result.is_ok()
}

fn read_shortcut_target(shortcut: &Path) -> Option<String> {
    // SAFETY: as above; the buffer is ours.
    unsafe {
        let link: IShellLinkW = CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER).ok()?;
        link.cast::<IPersistFile>()
            .ok()?
            .Load(&HSTRING::from(shortcut.as_os_str()), STGM_READ)
            .ok()?;
        let mut buf = [0u16; MAX_PATH as usize];
        link.GetPath(&mut buf, std::ptr::null_mut(), 0).ok()?;
        let len = buf.iter().position(|c| *c == 0).unwrap_or(buf.len());
        (len > 0).then(|| String::from_utf16_lossy(&buf[..len]))
    }
}

fn property_store(shortcut: &Path, writable: bool) -> Option<IPropertyStore> {
    let flags = if writable { GPS_READWRITE } else { GPS_DEFAULT };
    // SAFETY: the path string outlives the call.
    unsafe {
        SHGetPropertyStoreFromParsingName(&HSTRING::from(shortcut.as_os_str()), None, flags).ok()
    }
}

/// Read a string or CLSID property (`_read_shortcut_*_property`).
fn read_property(shortcut: &Path, key: &PROPERTYKEY) -> Option<String> {
    if !shortcut.exists() {
        return None;
    }
    let store = property_store(shortcut, false)?;
    // SAFETY: the union field read matches the reported `vt`; the
    // PROPVARIANT clears itself on drop.
    unsafe {
        let pv = store.GetValue(key).ok()?;
        let inner = &pv.Anonymous.Anonymous;
        if inner.vt == VT_LPWSTR && !inner.Anonymous.pwszVal.is_null() {
            inner.Anonymous.pwszVal.to_string().ok()
        } else if inner.vt == VT_CLSID && !inner.Anonymous.puuid.is_null() {
            Some(guid_to_string(&*inner.Anonymous.puuid))
        } else {
            None
        }
    }
}

fn write_property(shortcut: &Path, key: &PROPERTYKEY, value: &PROPVARIANT) -> bool {
    let Some(store) = property_store(shortcut, true) else {
        tracing::warn!("[notify-init] SHGetPropertyStoreFromParsingName(READWRITE) failed");
        return false;
    };
    // SAFETY: `value` is a valid PROPVARIANT for the duration of the call.
    let result = unsafe { store.SetValue(key, value).and_then(|_| store.Commit()) };
    if let Err(e) = &result {
        tracing::warn!("[notify-init] IPropertyStore::SetValue/Commit failed: {e}");
    }
    result.is_ok()
}

fn set_shortcut_app_id(shortcut: &Path, app_id: &str) -> bool {
    let wide: Vec<u16> = app_id.encode_utf16().chain(std::iter::once(0)).collect();
    let mut pv = PROPVARIANT::default();
    // SAFETY: the string is copied into CoTaskMem memory, which the
    // PROPVARIANT owns and frees (PropVariantClear) when dropped.
    unsafe {
        let buf = CoTaskMemAlloc(wide.len() * 2) as *mut u16;
        if buf.is_null() {
            return false;
        }
        std::ptr::copy_nonoverlapping(wide.as_ptr(), buf, wide.len());
        let inner = &mut *pv.Anonymous.Anonymous;
        inner.vt = VT_LPWSTR;
        inner.Anonymous.pwszVal = PWSTR(buf);
    }
    write_property(shortcut, &PKEY_AppUserModel_ID, &pv)
}

fn set_shortcut_activator_clsid(shortcut: &Path) -> bool {
    let guid = activator_guid();
    // SAFETY: plain call; the PROPVARIANT frees its CLSID on drop.
    match unsafe { InitPropVariantFromCLSID(&guid) } {
        Ok(pv) => write_property(shortcut, &PKEY_AppUserModel_ToastActivatorCLSID, &pv),
        Err(_) => false,
    }
}

fn load_stamp(path: &Path) -> Option<Value> {
    let v: Value = serde_json::from_str(&std::fs::read_to_string(path).ok()?).ok()?;
    v.is_object().then_some(v)
}

fn should_repair(stamp: Option<&Value>, shortcut: &Path, exe: &str, version: &str) -> bool {
    if !shortcut.exists() {
        return true;
    }
    let Some(stamp) = stamp else {
        return true;
    };
    !(stamp
        .get("verified")
        .and_then(Value::as_bool)
        .unwrap_or(false)
        && stamp.get("exe_path").and_then(Value::as_str) == Some(exe)
        && stamp.get("app_version").and_then(Value::as_str) == Some(version)
        && stamp.get("shortcut_path").and_then(Value::as_str) == Some(&*shortcut.to_string_lossy())
        && stamp.get("schema_version").and_then(Value::as_i64)
            == Some(TOAST_IDENTITY_SCHEMA_VERSION))
}

#[allow(clippy::too_many_arguments)]
fn write_stamp(
    path: &Path,
    shortcut: &Path,
    exe: &str,
    version: &str,
    verified: bool,
    readback_app_id: Option<&str>,
    clsid: Option<&str>,
    protocol_registered: bool,
) {
    let stamp = json!({
        "schema_version": TOAST_IDENTITY_SCHEMA_VERSION,
        "verified": verified,
        "exe_path": exe,
        "app_version": version,
        "shortcut_path": shortcut.to_string_lossy(),
        "readback_app_id": readback_app_id,
        "toast_activator_clsid": normalize_clsid(clsid),
        "protocol_handler_registered": protocol_registered,
    });
    let written = path
        .parent()
        .map_or(Ok(()), std::fs::create_dir_all)
        .and_then(|_| std::fs::write(path, py::json_dumps(&stamp)));
    if let Err(e) = written {
        tracing::warn!("[notify-init] Failed to write toast identity stamp: {e}");
    }
}

fn same_path(a: &str, b: &str) -> bool {
    a.trim_end_matches('\\')
        .eq_ignore_ascii_case(b.trim_end_matches('\\'))
}

/// `ensure_windows_toast_identity`: set the process AUMID, register the
/// protocol handler, and (unless a verified stamp says nothing changed)
/// make sure the Start Menu shortcut points at this exe and carries the
/// AUMID and toast activator CLSID. Runs once per process. `app_version` is
/// recorded in `%APPDATA%\AccessiWeather\toast_identity_stamp.json`.
pub fn ensure_windows_toast_identity(app_version: &str) {
    if IDENTITY_ENSURED.load(Ordering::SeqCst) {
        return;
    }
    let (Some(exe), Some(appdata)) = (exe_path(), roaming_appdata()) else {
        return;
    };
    let shortcut = resolve_start_menu_shortcut_path(&appdata);
    let stamp_path = appdata.join(APP_NAME).join("toast_identity_stamp.json");
    tracing::info!(
        "[notify-init] Windows toast identity: exe_path={exe} shortcut_path={}",
        shortcut.display()
    );

    // SAFETY: plain Win32 call with a valid string.
    if let Err(e) = unsafe {
        SetCurrentProcessExplicitAppUserModelID(&HSTRING::from(WINDOWS_APP_USER_MODEL_ID))
    } {
        tracing::debug!("Failed to set App User Model ID: {e}");
    }
    let protocol_registered = register_protocol_handler(&exe);

    let stamp = load_stamp(&stamp_path);
    IDENTITY_ENSURED.store(true, Ordering::SeqCst);
    if !should_repair(stamp.as_ref(), &shortcut, &exe, app_version) {
        tracing::info!(
            "[notify-init] Windows toast identity: verified stamp valid, skipping shortcut repair"
        );
        return;
    }

    // SAFETY: COM initialisation for this thread; an existing apartment is fine.
    let _ = unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED) };

    if !shortcut.exists() {
        if !create_shortcut(&shortcut, &exe) {
            tracing::warn!("[notify-init] Failed to create shortcut");
            return;
        }
    } else if let Some(target) = read_shortcut_target(&shortcut) {
        if !same_path(&target, &exe) && !create_shortcut(&shortcut, &exe) {
            tracing::warn!("[notify-init] Failed to recreate shortcut");
        }
    }

    let app_id = read_property(&shortcut, &PKEY_AppUserModel_ID);
    let clsid = read_property(&shortcut, &PKEY_AppUserModel_ToastActivatorCLSID);
    let stamp_failure = |readback: Option<&str>, clsid: Option<&str>| {
        write_stamp(
            &stamp_path,
            &shortcut,
            &exe,
            app_version,
            false,
            readback,
            clsid,
            protocol_registered,
        )
    };
    if app_id.as_deref() != Some(WINDOWS_APP_USER_MODEL_ID)
        && !set_shortcut_app_id(&shortcut, WINDOWS_APP_USER_MODEL_ID)
    {
        tracing::warn!("[notify-init] Failed to set AUMID on shortcut");
        stamp_failure(app_id.as_deref(), clsid.as_deref());
        return;
    }
    let expected_clsid = normalize_clsid(Some(WINDOWS_TOAST_ACTIVATOR_CLSID));
    if normalize_clsid(clsid.as_deref()) != expected_clsid
        && !set_shortcut_activator_clsid(&shortcut)
    {
        tracing::warn!("[notify-init] Failed to set ToastActivatorCLSID on shortcut");
        stamp_failure(app_id.as_deref(), clsid.as_deref());
        return;
    }

    let readback_id = read_property(&shortcut, &PKEY_AppUserModel_ID);
    let readback_clsid = read_property(&shortcut, &PKEY_AppUserModel_ToastActivatorCLSID);
    let verified = readback_id.as_deref() == Some(WINDOWS_APP_USER_MODEL_ID)
        && normalize_clsid(readback_clsid.as_deref()) == expected_clsid
        && protocol_registered;
    tracing::info!(
        "[notify-init] Windows toast identity result: shortcut={} verified={verified}",
        shortcut.display()
    );
    write_stamp(
        &stamp_path,
        &shortcut,
        &exe,
        app_version,
        verified,
        readback_id.as_deref(),
        readback_clsid.as_deref(),
        protocol_registered,
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn list2cmdline_matches_python() {
        assert_eq!(list2cmdline(&[r"C:\AW\aw.exe", "%1"]), r"C:\AW\aw.exe %1");
        assert_eq!(
            list2cmdline(&[r"C:\Program Files\AW\aw.exe", "%1"]),
            r#""C:\Program Files\AW\aw.exe" %1"#
        );
        assert_eq!(list2cmdline(&[r"a b\", r#"x"y"#]), r#""a b\\" x\"y"#);
    }

    #[test]
    fn clsid_normalisation() {
        assert_eq!(
            normalize_clsid(Some("0d3c3f8e-7303-4c9b-81c7-ff8d8c1afc07")).as_deref(),
            Some(WINDOWS_TOAST_ACTIVATOR_CLSID)
        );
        assert_eq!(
            guid_to_string(&activator_guid()),
            WINDOWS_TOAST_ACTIVATOR_CLSID
        );
        assert_eq!(normalize_clsid(Some("junk")), None);
    }

    #[test]
    fn stamp_decides_repair() {
        let dir = tempfile::tempdir().unwrap();
        let shortcut = dir.path().join("AccessiWeather.lnk");
        let stamp_path = dir.path().join("stamp.json");
        assert!(should_repair(None, &shortcut, "exe", "1"));
        std::fs::write(&shortcut, b"").unwrap();
        write_stamp(
            &stamp_path,
            &shortcut,
            "exe",
            "1",
            true,
            Some("id"),
            Some(WINDOWS_TOAST_ACTIVATOR_CLSID),
            true,
        );
        let stamp = load_stamp(&stamp_path);
        assert!(!should_repair(stamp.as_ref(), &shortcut, "exe", "1"));
        assert!(should_repair(stamp.as_ref(), &shortcut, "exe", "2"));
        assert!(std::fs::read_to_string(&stamp_path)
            .unwrap()
            .starts_with(r#"{"schema_version": 2, "verified": true, "exe_path": "exe""#));
    }

    #[test]
    fn toast_xml_is_accepted_by_winrt() {
        let xml = super::super::toast_xml(
            "SEVERE ALERT: A & B",
            "Line one\n\nLine <two>",
            Some(&crate::ActivationRequest::alert_details("urn:oid:1&x")),
        );
        let doc = XmlDocument::new().unwrap();
        doc.LoadXml(&HSTRING::from(xml)).unwrap();
        let root = doc.DocumentElement().unwrap();
        assert_eq!(
            root.GetAttribute(&HSTRING::from("launch"))
                .unwrap()
                .to_string(),
            "accessiweather-toast:kind=alert_details&alert_id=urn%3Aoid%3A1%26x"
        );
        assert!(ToastNotification::CreateToastNotification(&doc).is_ok());
    }

    #[test]
    fn shortcut_round_trip_in_temp_dir() {
        // SAFETY: COM initialisation for the test thread.
        let _ = unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED) };
        let dir = tempfile::tempdir().unwrap();
        let shortcut = dir
            .path()
            .join("Programs")
            .join(APP_NAME)
            .join("AccessiWeather.lnk");
        let target = std::env::current_exe()
            .unwrap()
            .to_string_lossy()
            .into_owned();
        assert!(create_shortcut(&shortcut, &target));
        assert!(same_path(
            &read_shortcut_target(&shortcut).unwrap(),
            &target
        ));
        assert!(set_shortcut_app_id(&shortcut, WINDOWS_APP_USER_MODEL_ID));
        assert!(set_shortcut_activator_clsid(&shortcut));
        assert_eq!(
            read_property(&shortcut, &PKEY_AppUserModel_ID).as_deref(),
            Some(WINDOWS_APP_USER_MODEL_ID)
        );
        assert_eq!(
            read_property(&shortcut, &PKEY_AppUserModel_ToastActivatorCLSID).as_deref(),
            Some(WINDOWS_TOAST_ACTIVATOR_CLSID)
        );
    }
}
