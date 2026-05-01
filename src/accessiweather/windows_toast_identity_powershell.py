"""PowerShell fallback for Windows toast identity repair."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_powershell_identity_fallback(
    *,
    shortcut_path: Path,
    exe_path: str,
    app_id: str,
    display_name: str,
    stamp_path: Path,
    app_version: str,
    protocol_handler_registered: bool,
    run_powershell_json: Callable[..., dict[str, Any]],
    write_toast_identity_stamp: Callable[..., None],
    toast_activator_clsid: str,
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

    state = run_powershell_json(
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
        fallback_state = run_powershell_json(
            fallback_script,
            ShortcutPath=str(shortcut_path),
            AppId=app_id,
        )
        state["fallback_verified"] = fallback_state.get("verified")
        state["fallback_error"] = fallback_state.get("set_error")
        state["readback_app_id"] = fallback_state.get("readback_app_id") or state.get(
            "readback_app_id"
        )

    write_toast_identity_stamp(
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
        toast_activator_clsid=(toast_activator_clsid if state.get("verified") is True else None),
        protocol_handler_registered=protocol_handler_registered,
    )
