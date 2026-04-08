"""
Windows toast notification identity management for AccessiWeather.

Handles AppUserModelID registration, Start Menu shortcut creation/repair,
and identity stamp caching so Windows toast notifications — including
Action Center clicks — work reliably across source, portable, and
installer builds.

Uses pure Python ctypes COM calls (no PowerShell subprocess) to avoid
visible terminal popups.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .constants import WINDOWS_APP_USER_MODEL_ID

logger = logging.getLogger(__name__)

_ole32 = None
_shell32 = None


# ---------------------------------------------------------------------------
# COM GUIDs and structures for IShellLink / IPropertyStore
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    from ctypes import HRESULT, POINTER, byref, c_int, c_void_p, windll
    from ctypes.wintypes import DWORD, LPCWSTR, LPWSTR, MAX_PATH, WORD

    _ole32 = windll.ole32
    _shell32 = windll.shell32

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", DWORD),
            ("Data2", WORD),
            ("Data3", WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class PROPERTYKEY(ctypes.Structure):
        _fields_ = [("fmtid", GUID), ("pid", DWORD)]

    class PROPVARIANT(ctypes.Structure):
        _fields_ = [
            ("vt", WORD),
            ("wReserved1", WORD),
            ("wReserved2", WORD),
            ("wReserved3", WORD),
            ("pwszVal", ctypes.c_wchar_p),
        ]

    # System.AppUserModel.ID property key
    # {9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}, pid 5
    _PKEY_AppUserModel_ID = PROPERTYKEY(
        GUID(0x9F4C2855, 0x9F79, 0x4B39, (0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)),
        5,
    )

    # IID_IPropertyStore = {886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}
    _IID_IPropertyStore = GUID(
        0x886D8EEB, 0x8CF2, 0x4446, (0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99)
    )

    # VT_LPWSTR = 0x001F
    _VT_LPWSTR = 0x001F

    # GPS_READWRITE = 2
    _GPS_READWRITE = 2


def _is_unc_path(path: str) -> bool:
    """Return True when *path* points to a UNC/network location."""
    normalized = path.replace("/", "\\")
    return normalized.startswith("\\\\")


def _needs_shortcut_repair(
    *, expected_target: str, current_target: str | None, current_app_id: str | None, app_id: str
) -> bool:
    """Determine whether Start Menu shortcut should be recreated/repaired."""
    if not current_target:
        return True
    if Path(current_target).resolve() != Path(expected_target).resolve():
        return True
    return (current_app_id or "") != app_id


def _run_powershell_json(script: str, **args: str) -> dict[str, str | bool | None]:
    """Run a small PowerShell script and parse JSON output."""
    if sys.platform != "win32":
        return {}

    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    for key, value in args.items():
        cmd.extend([f"-{key}", value])

    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"powershell exit {result.returncode}")

    payload = (result.stdout or "").strip()
    if not payload:
        return {}
    return json.loads(payload)


def set_windows_app_user_model_id(app_id: str = WINDOWS_APP_USER_MODEL_ID) -> None:
    """
    Register a Windows AppUserModelID for every Windows run.

    Setting the AppUserModelID explicitly ensures source, portable, and
    installer builds share the same identity (the shortcut uses this value),
    so toast notifications work consistently without conflicting with the
    registered shortcut AppID.
    """
    if sys.platform != "win32":
        return

    try:
        ctypes_module = sys.modules.get("ctypes", ctypes)
        ctypes_module.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        logger.debug("App User Model ID set: %s", app_id)
    except Exception as exc:
        logger.debug("Failed to set App User Model ID: %s", exc)


# ---------------------------------------------------------------------------
# Pure Python shortcut + AUMID helpers
# ---------------------------------------------------------------------------


def _resolve_start_menu_shortcut_path(display_name: str) -> Path:
    """Find the real Start Menu shortcut path, including nested subfolders."""
    appdata = Path.home() / "AppData" / "Roaming"
    programs_dir = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"

    nested_default = programs_dir / display_name / f"{display_name}.lnk"
    top_level_default = programs_dir / f"{display_name}.lnk"

    if nested_default.exists():
        return nested_default
    if top_level_default.exists():
        return top_level_default

    for candidate in sorted(programs_dir.rglob(f"{display_name}.lnk")):
        if candidate.is_file():
            return candidate

    return nested_default


def _read_shortcut_target_wscript(shortcut_path: Path) -> str | None:
    """Read shortcut target using the Windows Script Host COM object."""
    if sys.platform != "win32":
        return None
    try:
        import win32com.client  # type: ignore[import-untyped]

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        return shortcut.TargetPath or None
    except ImportError:
        pass

    # Fallback: pythoncom/comtypes not available — try ctypes-only approach
    try:
        return _read_shortcut_target_ctypes(shortcut_path)
    except Exception as exc:
        logger.debug("ctypes shortcut read failed: %s", exc)
        return None


def _read_shortcut_target_ctypes(shortcut_path: Path) -> str | None:
    """Read shortcut target using raw ctypes COM (IShellLinkW + IPersistFile)."""
    if sys.platform != "win32":
        return None

    CLSID_ShellLink = GUID(
        0x00021401, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )
    IID_IShellLinkW = GUID(
        0x000214F9, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )
    IID_IPersistFile = GUID(
        0x0000010B, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )

    CLSCTX_INPROC_SERVER = 1
    p_shell_link = c_void_p()

    hr = _ole32.CoCreateInstance(
        byref(CLSID_ShellLink),
        None,
        CLSCTX_INPROC_SERVER,
        byref(IID_IShellLinkW),
        byref(p_shell_link),
    )
    if hr != 0:
        return None

    # Query IPersistFile
    p_persist_file = c_void_p()
    # Get vtable for IShellLinkW — we need QueryInterface at vtable[0]
    vtable = ctypes.cast(p_shell_link, POINTER(POINTER(c_void_p)))[0]
    query_interface = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(GUID), POINTER(c_void_p))(
        vtable[0]
    )
    hr = query_interface(p_shell_link, byref(IID_IPersistFile), byref(p_persist_file))
    if hr != 0:
        # Release IShellLinkW
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(vtable[2])
        release(p_shell_link)
        return None

    # IPersistFile::Load (vtable index 5)
    pf_vtable = ctypes.cast(p_persist_file, POINTER(POINTER(c_void_p)))[0]
    pf_load = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR, DWORD)(pf_vtable[5])
    hr = pf_load(p_persist_file, str(shortcut_path), 0)

    target = None
    if hr == 0:
        # IShellLinkW::GetPath (vtable index 3)
        get_path = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPWSTR, c_int, c_void_p, DWORD)(vtable[3])
        buf = ctypes.create_unicode_buffer(MAX_PATH)
        hr2 = get_path(p_shell_link, buf, MAX_PATH, None, 0)
        if hr2 == 0 and buf.value:
            target = buf.value

    # Release both interfaces
    pf_release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(pf_vtable[2])
    pf_release(p_persist_file)
    sl_release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(vtable[2])
    sl_release(p_shell_link)

    return target


def _create_shortcut(shortcut_path: Path, target_path: str, display_name: str) -> bool:
    """Create a .lnk shortcut file."""
    if sys.platform != "win32":
        return False

    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    # Try win32com first (most reliable for shortcut creation)
    try:
        import win32com.client  # type: ignore[import-untyped]

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = target_path
        shortcut.WorkingDirectory = str(Path(target_path).parent)
        shortcut.Description = display_name
        shortcut.IconLocation = f"{target_path},0"
        shortcut.Save()
        return True
    except ImportError:
        pass

    # Fallback: raw ctypes COM with IShellLinkW + IPersistFile
    return _create_shortcut_ctypes(shortcut_path, target_path, display_name)


def _create_shortcut_ctypes(shortcut_path: Path, target_path: str, display_name: str) -> bool:
    """Create a .lnk shortcut using raw ctypes COM."""
    if sys.platform != "win32":
        return False

    CLSID_ShellLink = GUID(
        0x00021401, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )
    IID_IShellLinkW = GUID(
        0x000214F9, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )
    IID_IPersistFile = GUID(
        0x0000010B, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )

    CLSCTX_INPROC_SERVER = 1
    p_shell_link = c_void_p()

    hr = _ole32.CoCreateInstance(
        byref(CLSID_ShellLink),
        None,
        CLSCTX_INPROC_SERVER,
        byref(IID_IShellLinkW),
        byref(p_shell_link),
    )
    if hr != 0:
        logger.warning(
            "[notify-init] CoCreateInstance(ShellLink) failed: HR=0x%08X", hr & 0xFFFFFFFF
        )
        return False

    vtable = ctypes.cast(p_shell_link, POINTER(POINTER(c_void_p)))[0]

    # IShellLinkW::SetPath (vtable index 20)
    set_path = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR)(vtable[20])
    set_path(p_shell_link, target_path)

    # IShellLinkW::SetWorkingDirectory (vtable index 10)
    set_working_dir = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR)(vtable[10])
    set_working_dir(p_shell_link, str(Path(target_path).parent))

    # IShellLinkW::SetDescription (vtable index 8)
    set_description = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR)(vtable[8])
    set_description(p_shell_link, display_name)

    # IShellLinkW::SetIconLocation (vtable index 18)
    set_icon = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR, c_int)(vtable[18])
    set_icon(p_shell_link, target_path, 0)

    # QueryInterface for IPersistFile
    p_persist_file = c_void_p()
    query_interface = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(GUID), POINTER(c_void_p))(
        vtable[0]
    )
    hr = query_interface(p_shell_link, byref(IID_IPersistFile), byref(p_persist_file))
    if hr != 0:
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(vtable[2])
        release(p_shell_link)
        return False

    # IPersistFile::Save (vtable index 6)
    pf_vtable = ctypes.cast(p_persist_file, POINTER(POINTER(c_void_p)))[0]
    pf_save = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR, ctypes.c_bool)(pf_vtable[6])
    hr = pf_save(p_persist_file, str(shortcut_path), True)

    # Release both
    pf_release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(pf_vtable[2])
    pf_release(p_persist_file)
    sl_release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(vtable[2])
    sl_release(p_shell_link)

    if hr != 0:
        logger.warning("[notify-init] IPersistFile::Save failed: HR=0x%08X", hr & 0xFFFFFFFF)
        return False
    return True


def _read_shortcut_app_id(shortcut_path: Path) -> str | None:
    """Read the AppUserModelID property from a shortcut via IPropertyStore."""
    if sys.platform != "win32" or not shortcut_path.exists():
        return None

    try:
        p_store = c_void_p()
        hr = _shell32.SHGetPropertyStoreFromParsingName(
            str(shortcut_path),
            None,
            0,  # GPS_DEFAULT (read-only)
            byref(_IID_IPropertyStore),
            byref(p_store),
        )
        if hr != 0:
            return None

        store_vtable = ctypes.cast(p_store, POINTER(POINTER(c_void_p)))[0]

        # IPropertyStore::GetValue (vtable index 5)
        pv = PROPVARIANT()
        get_value = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(
            store_vtable[5]
        )
        hr = get_value(p_store, byref(_PKEY_AppUserModel_ID), byref(pv))

        result = None
        if hr == 0 and pv.vt == _VT_LPWSTR and pv.pwszVal:
            result = pv.pwszVal

        # Release
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(store_vtable[2])
        release(p_store)
        return result
    except Exception as exc:
        logger.debug("[notify-init] Failed to read shortcut AppUserModelID: %s", exc)
        return None


def _set_shortcut_app_id(shortcut_path: Path, app_id: str) -> bool:
    """Set the AppUserModelID property on a shortcut via IPropertyStore."""
    if sys.platform != "win32":
        return False

    try:
        p_store = c_void_p()
        hr = _shell32.SHGetPropertyStoreFromParsingName(
            str(shortcut_path),
            None,
            _GPS_READWRITE,
            byref(_IID_IPropertyStore),
            byref(p_store),
        )
        if hr != 0:
            logger.warning(
                "[notify-init] SHGetPropertyStoreFromParsingName(READWRITE) failed: HR=0x%08X",
                hr & 0xFFFFFFFF,
            )
            return False

        store_vtable = ctypes.cast(p_store, POINTER(POINTER(c_void_p)))[0]

        # IPropertyStore::SetValue (vtable index 6)
        pv = PROPVARIANT()
        pv.vt = _VT_LPWSTR
        pv.pwszVal = app_id
        set_value = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(
            store_vtable[6]
        )
        hr = set_value(p_store, byref(_PKEY_AppUserModel_ID), byref(pv))
        if hr != 0:
            logger.warning(
                "[notify-init] IPropertyStore::SetValue failed: HR=0x%08X", hr & 0xFFFFFFFF
            )
            release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(store_vtable[2])
            release(p_store)
            return False

        # IPropertyStore::Commit (vtable index 7)
        commit = ctypes.CFUNCTYPE(HRESULT, c_void_p)(store_vtable[7])
        hr = commit(p_store)

        # Release
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(store_vtable[2])
        release(p_store)

        if hr != 0:
            logger.warning(
                "[notify-init] IPropertyStore::Commit failed: HR=0x%08X", hr & 0xFFFFFFFF
            )
            return False
        return True
    except Exception as exc:
        logger.warning("[notify-init] Failed to set shortcut AppUserModelID: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Identity stamp caching (unchanged from before)
# ---------------------------------------------------------------------------


def _toast_identity_stamp_path(appdata: Path, display_name: str) -> Path:
    return appdata / display_name / "toast_identity_stamp.json"


def _load_toast_identity_stamp(stamp_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(stamp_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _should_repair_shortcut(
    *,
    stamp: dict[str, Any] | None,
    shortcut_path: Path,
    exe_path: str,
    app_version: str,
) -> bool:
    if not shortcut_path.exists():
        return True
    if not stamp:
        return True

    return not (
        bool(stamp.get("verified"))
        and stamp.get("exe_path") == exe_path
        and stamp.get("app_version") == app_version
        and stamp.get("shortcut_path") == str(shortcut_path)
    )


def _write_toast_identity_stamp(
    *,
    stamp_path: Path,
    shortcut_path: Path,
    exe_path: str,
    app_version: str,
    verified: bool,
    readback_app_id: str | None,
) -> None:
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(
        json.dumps(
            {
                "verified": bool(verified),
                "exe_path": exe_path,
                "app_version": app_version,
                "shortcut_path": str(shortcut_path),
                "readback_app_id": readback_app_id,
            }
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_TOAST_IDENTITY_ENSURED_THIS_STARTUP = False


def _ensure_windows_toast_identity_via_powershell(
    *,
    shortcut_path: Path,
    exe_path: str,
    app_id: str,
    display_name: str,
    stamp_path: Path,
    app_version: str,
) -> None:
    """Legacy fallback used when ctypes COM access is unavailable."""
    script = r"""
param([string]$ShortcutPath,[string]$TargetPath,[string]$AppId,[string]$DisplayName)
$state = [ordered]@{ shortcut_path = $ShortcutPath; shortcut_exists = $false; current_target = $null; readback_app_id = $null; repaired = $false; verified = $false; set_error = $null }
$dir = Split-Path -Parent $ShortcutPath
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
if (Test-Path $ShortcutPath) {
  $state.shortcut_exists = $true
  try {
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($ShortcutPath)
    $state.current_target = $s.TargetPath
  } catch {}
  try {
    $shell = New-Object -ComObject Shell.Application
    $folder = $shell.Namespace((Split-Path -Parent $ShortcutPath))
    if ($folder) {
      $item = $folder.ParseName((Split-Path -Leaf $ShortcutPath))
      if ($item) { $state.readback_app_id = $item.ExtendedProperty('System.AppUserModel.ID') }
    }
  } catch {}
}
$needsRepair = (-not $state.current_target) -or (([IO.Path]::GetFullPath($state.current_target)) -ne ([IO.Path]::GetFullPath($TargetPath))) -or (($state.readback_app_id ?? '') -ne $AppId)
if ($needsRepair) {
  try {
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($ShortcutPath)
    $s.TargetPath = $TargetPath
    $s.WorkingDirectory = [IO.Path]::GetDirectoryName($TargetPath)
    $s.IconLocation = "$TargetPath,0"
    $s.Description = $DisplayName
    $s.Save()

    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
[Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropertyStore { void GetCount(out uint c); void GetAt(uint i, out PropKey k); void GetValue(ref PropKey k, out object v); void SetValue(ref PropKey k, ref PropVariantW v); void Commit(); }
[StructLayout(LayoutKind.Sequential, Pack=4)]
public struct PropKey { public Guid fmt; public uint pid; }
[StructLayout(LayoutKind.Explicit)]
public struct PropVariantW { [FieldOffset(0)] public ushort vt; [FieldOffset(8)] public IntPtr pwszVal; }
public class PropStoreHelper {
  [DllImport("shell32.dll", CharSet=CharSet.Unicode)]
  public static extern int SHGetPropertyStoreFromParsingName(string path, IntPtr pbc, int flags, [MarshalAs(UnmanagedType.LPStruct)] Guid riid, [MarshalAs(UnmanagedType.Interface)] out IPropertyStore ppv);
}
"@ -Language CSharp
    $iid = [Guid]"886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"
    $store = $null
    $hr = [PropStoreHelper]::SHGetPropertyStoreFromParsingName($ShortcutPath, [IntPtr]::Zero, 2, $iid, [ref]$store)
    if ($hr -ne 0) {
      $state.set_error = "SHGetPropertyStoreFromParsingName failed: HR=0x{0:X8}" -f ($hr -band 0xffffffff)
    } else {
      $key = [PropKey]@{ fmt = [Guid]"9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"; pid = 5 }
      $ptr = [Runtime.InteropServices.Marshal]::StringToCoTaskMemUni($AppId)
      try {
        $pv = [PropVariantW]@{ vt = 0x1F; pwszVal = $ptr }
        $store.SetValue([ref]$key, [ref]$pv)
        $store.Commit()
      } finally {
        [Runtime.InteropServices.Marshal]::FreeCoTaskMem($ptr)
      }
    }

    $shell = New-Object -ComObject Shell.Application
    $folder = $shell.Namespace((Split-Path -Parent $ShortcutPath))
    if ($folder) {
      $item = $folder.ParseName((Split-Path -Leaf $ShortcutPath))
      if ($item) { $state.readback_app_id = $item.ExtendedProperty('System.AppUserModel.ID') }
    }

    $state.verified = (($state.readback_app_id ?? '') -eq $AppId)
    $state.repaired = $state.verified
    if (-not $state.verified -and -not $state.set_error) {
      $state.set_error = "AppUserModelID verification failed after property-store commit"
    }
  } catch {
    $state.set_error = $_.Exception.Message
  }
}
$state | ConvertTo-Json -Compress
"""

    fallback_script = r"""
param([string]$ShortcutPath,[string]$AppId)
$state = [ordered]@{ readback_app_id = $null; verified = $false; set_error = $null }
try {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
[Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropertyStore { void GetCount(out uint c); void GetAt(uint i, out PropKey k); void GetValue(ref PropKey k, out object v); void SetValue(ref PropKey k, ref PropVariantW v); void Commit(); }
[StructLayout(LayoutKind.Sequential, Pack=4)]
public struct PropKey { public Guid fmt; public uint pid; }
[StructLayout(LayoutKind.Explicit)]
public struct PropVariantW { [FieldOffset(0)] public ushort vt; [FieldOffset(8)] public IntPtr pwszVal; }
public class PropStoreHelper {
  [DllImport("shell32.dll", CharSet=CharSet.Unicode)]
  public static extern int SHGetPropertyStoreFromParsingName(string path, IntPtr pbc, int flags, [MarshalAs(UnmanagedType.LPStruct)] Guid riid, [MarshalAs(UnmanagedType.Interface)] out IPropertyStore ppv);
}
"@ -Language CSharp
  $iid = [Guid]"886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"
  $store = $null
  $hr = [PropStoreHelper]::SHGetPropertyStoreFromParsingName($ShortcutPath, [IntPtr]::Zero, 2, $iid, [ref]$store)
  if ($hr -ne 0) {
    $state.set_error = "fallback SHGetPropertyStoreFromParsingName failed: HR=0x{0:X8}" -f ($hr -band 0xffffffff)
  } else {
    $key = [PropKey]@{ fmt = [Guid]"9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"; pid = 5 }
    $ptr = [Runtime.InteropServices.Marshal]::StringToCoTaskMemUni($AppId)
    try {
      $pv = [PropVariantW]@{ vt = 0x1F; pwszVal = $ptr }
      $store.SetValue([ref]$key, [ref]$pv)
      $store.Commit()
    } finally {
      [Runtime.InteropServices.Marshal]::FreeCoTaskMem($ptr)
    }

    $shell = New-Object -ComObject Shell.Application
    $folder = $shell.Namespace((Split-Path -Parent $ShortcutPath))
    if ($folder) {
      $item = $folder.ParseName((Split-Path -Leaf $ShortcutPath))
      if ($item) { $state.readback_app_id = $item.ExtendedProperty('System.AppUserModel.ID') }
    }
    $state.verified = (($state.readback_app_id ?? '') -eq $AppId)
    if (-not $state.verified) {
      $state.set_error = "fallback verification failed after property-store commit"
    }
  }
} catch {
  $state.set_error = $_.Exception.Message
}
$state | ConvertTo-Json -Compress
"""

    state = _run_powershell_json(
        script,
        ShortcutPath=str(shortcut_path),
        TargetPath=exe_path,
        AppId=app_id,
        DisplayName=display_name,
    )

    if state.get("verified") is not True:
        logger.warning(
            "[notify-init] Primary shortcut AppID set failed: %s",
            state.get("set_error") or "unknown error",
        )
        fallback_state = _run_powershell_json(
            fallback_script,
            ShortcutPath=str(shortcut_path),
            AppId=app_id,
        )
        state["fallback_verified"] = fallback_state.get("verified")
        state["fallback_error"] = fallback_state.get("set_error")
        state["readback_app_id"] = fallback_state.get("readback_app_id") or state.get(
            "readback_app_id"
        )

    _write_toast_identity_stamp(
        stamp_path=stamp_path,
        shortcut_path=Path(str(state.get("shortcut_path") or shortcut_path)),
        exe_path=exe_path,
        app_version=app_version,
        verified=(
            (state.get("verified") is True and state.get("readback_app_id") == app_id)
            or (state.get("fallback_verified") is True and state.get("readback_app_id") == app_id)
        ),
        readback_app_id=(
            None if state.get("readback_app_id") is None else str(state.get("readback_app_id"))
        ),
    )


def ensure_windows_toast_identity(
    app_id: str = WINDOWS_APP_USER_MODEL_ID,
    display_name: str = "AccessiWeather",
) -> None:
    """
    Ensure registry + Start Menu shortcut identity for reliable Windows toasts.

    Uses pure Python ctypes COM calls — no PowerShell subprocess, no visible
    terminal window.
    """
    global _TOAST_IDENTITY_ENSURED_THIS_STARTUP

    if sys.platform != "win32":
        return

    if _TOAST_IDENTITY_ENSURED_THIS_STARTUP:
        logger.debug("[notify-init] Windows toast identity already ensured this startup; skipping")
        return

    from . import __version__

    exe_path = str(Path(sys.executable).resolve())
    appdata = Path.home() / "AppData" / "Roaming"
    shortcut_path = _resolve_start_menu_shortcut_path(display_name)
    stamp_path = _toast_identity_stamp_path(appdata, display_name)
    app_version = __version__

    logger.info(
        "[notify-init] Windows toast identity: exe_path=%s shortcut_path=%s",
        exe_path,
        shortcut_path,
    )

    # Always set the process-level AUMID
    set_windows_app_user_model_id(app_id=app_id)

    # Check cached stamp to see if repair is needed
    stamp = _load_toast_identity_stamp(stamp_path)
    if not _should_repair_shortcut(
        stamp=stamp,
        shortcut_path=shortcut_path,
        exe_path=exe_path,
        app_version=app_version,
    ):
        _TOAST_IDENTITY_ENSURED_THIS_STARTUP = True
        logger.info(
            "[notify-init] Windows toast identity: verified stamp valid, skipping shortcut repair"
        )
        return

    # Don't run repair more than once per startup
    _TOAST_IDENTITY_ENSURED_THIS_STARTUP = True

    try:
        if _ole32 is None or _shell32 is None:
            _ensure_windows_toast_identity_via_powershell(
                shortcut_path=shortcut_path,
                exe_path=exe_path,
                app_id=app_id,
                display_name=display_name,
                stamp_path=stamp_path,
                app_version=app_version,
            )
            return

        # Initialize COM (idempotent — safe to call multiple times)
        _ole32.CoInitialize(None)

        # Step 1: Ensure shortcut exists
        if not shortcut_path.exists():
            logger.info(
                "[notify-init] Creating Start Menu shortcut: %s -> %s", shortcut_path, exe_path
            )
            if not _create_shortcut(shortcut_path, exe_path, display_name):
                logger.warning("[notify-init] Failed to create shortcut")
                return
        else:
            # Verify target matches current exe
            current_target = _read_shortcut_target_wscript(shortcut_path)
            if current_target and Path(current_target).resolve() != Path(exe_path).resolve():
                logger.info(
                    "[notify-init] Shortcut target mismatch: %s != %s — recreating",
                    current_target,
                    exe_path,
                )
                if not _create_shortcut(shortcut_path, exe_path, display_name):
                    logger.warning("[notify-init] Failed to recreate shortcut")

        # Step 2: Read current AUMID
        current_app_id = _read_shortcut_app_id(shortcut_path)
        logger.info(
            "[notify-init] Current shortcut AUMID: %r (expected: %r)", current_app_id, app_id
        )

        # Step 3: Set AUMID if missing or wrong
        if current_app_id != app_id:
            logger.info("[notify-init] Setting AUMID on shortcut: %s", app_id)
            if not _set_shortcut_app_id(shortcut_path, app_id):
                logger.warning("[notify-init] Failed to set AUMID on shortcut")
                _write_toast_identity_stamp(
                    stamp_path=stamp_path,
                    shortcut_path=shortcut_path,
                    exe_path=exe_path,
                    app_version=app_version,
                    verified=False,
                    readback_app_id=current_app_id,
                )
                return

        # Step 4: Verify readback
        readback_app_id = _read_shortcut_app_id(shortcut_path)
        verified = readback_app_id == app_id

        logger.info(
            "[notify-init] Windows toast identity result: shortcut=%s verified=%s readback=%r",
            shortcut_path,
            verified,
            readback_app_id,
        )

        _write_toast_identity_stamp(
            stamp_path=stamp_path,
            shortcut_path=shortcut_path,
            exe_path=exe_path,
            app_version=app_version,
            verified=verified,
            readback_app_id=readback_app_id,
        )

    except Exception as exc:
        logger.warning("[notify-init] Failed to ensure toast identity: %s", exc)
