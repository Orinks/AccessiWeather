"""
Windows toast notification identity management for AccessiWeather.

Handles AppUserModelID registration, Start Menu shortcut repair, and
identity stamp caching so Windows toast notifications work reliably
across source, portable, and installer builds.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from .constants import WINDOWS_APP_USER_MODEL_ID

logger = logging.getLogger(__name__)


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

    try:  # pragma: no cover
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        logger.debug("App User Model ID set: %s", app_id)
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to set App User Model ID: %s", exc)


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


def _toast_identity_stamp_path(appdata: Path, display_name: str) -> Path:
    return appdata / display_name / "toast_identity_stamp.json"


def _load_toast_identity_stamp(stamp_path: Path) -> dict[str, str | bool] | None:
    try:
        payload = json.loads(stamp_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _should_repair_shortcut(
    *,
    stamp: dict[str, str | bool] | None,
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


_TOAST_IDENTITY_ENSURED_THIS_STARTUP = False


def ensure_windows_toast_identity(
    app_id: str = WINDOWS_APP_USER_MODEL_ID,
    display_name: str = "AccessiWeather",
) -> None:
    """Ensure registry + Start Menu shortcut identity for reliable Windows toasts."""
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
        "[notify-init] Windows toast identity: exe_path=%s shortcut_path=%s exe_is_unc=%s",
        exe_path,
        shortcut_path,
        _is_unc_path(exe_path),
    )

    set_windows_app_user_model_id(app_id=app_id)

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

    # Do not run repair more than once in the same process startup.
    _TOAST_IDENTITY_ENSURED_THIS_STARTUP = True

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

    try:  # pragma: no cover - windows only integration path
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

        logger.info(
            "[notify-init] Windows toast identity result: shortcut=%s exists=%s repaired=%s verified=%s fallback_verified=%s readback_app_id=%s notifier_app_id=%s",
            state.get("shortcut_path"),
            state.get("shortcut_exists"),
            state.get("repaired"),
            state.get("verified"),
            state.get("fallback_verified"),
            state.get("readback_app_id"),
            app_id,
        )

        if state.get("fallback_verified") is not True and state.get("verified") is not True:
            logger.warning(
                "[notify-init] Fallback shortcut AppID set failed: %s",
                state.get("fallback_error") or state.get("set_error") or "unknown error",
            )

        verified = (state.get("verified") is True and state.get("readback_app_id") == app_id) or (
            state.get("fallback_verified") is True and state.get("readback_app_id") == app_id
        )
        _write_toast_identity_stamp(
            stamp_path=stamp_path,
            shortcut_path=Path(str(state.get("shortcut_path") or shortcut_path)),
            exe_path=exe_path,
            app_version=app_version,
            verified=verified,
            readback_app_id=(
                None if state.get("readback_app_id") is None else str(state.get("readback_app_id"))
            ),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("[notify-init] Failed to validate/repair Start menu shortcut: %s", exc)
