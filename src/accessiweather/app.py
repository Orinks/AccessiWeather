"""
AccessiWeather wxPython application.

This module provides the main wxPython application class with excellent
screen reader accessibility.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

import wx

from .constants import WINDOWS_APP_USER_MODEL_ID
from .models import WeatherData
from .paths import Paths
from .single_instance import SingleInstanceManager

if TYPE_CHECKING:
    from .alert_manager import AlertManager
    from .alert_notification_system import AlertNotificationSystem
    from .config import ConfigManager
    from .display import WeatherPresenter
    from .location_manager import LocationManager
    from .ui.main_window import MainWindow
    from .weather_client import WeatherClient

# Configure logging
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

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


class AccessiWeatherApp(wx.App):
    """AccessiWeather application using wxPython."""

    def __init__(
        self,
        config_dir: str | None = None,
        portable_mode: bool = False,
        debug: bool = False,
        force_wizard: bool = False,
        updated: bool = False,
    ):
        """
        Initialize the AccessiWeather application.

        Args:
            config_dir: Optional custom configuration directory path
            portable_mode: If True, use portable mode (config in app directory)
            debug: If True, enable debug mode (enables debug logging and extra UI tools)
            force_wizard: If True, force the onboarding wizard even if already shown
            updated: If True, skip lock-file prompt (app was restarted after an update)

        """
        self._updated = updated
        self._config_dir = config_dir

        # Auto-detect portable mode for frozen builds unless explicitly overridden
        # via --portable or --config-dir.
        if not portable_mode and config_dir is None:
            try:
                from .config_utils import is_portable_mode

                portable_mode = is_portable_mode()
            except Exception:
                portable_mode = False

        self._portable_mode = portable_mode
        self.debug_mode = bool(debug)
        self._force_wizard = bool(force_wizard)
        self._portable_keys_imported_this_session: bool = False

        # App version and build info (import locally to avoid circular import)
        from . import __version__

        self.version = __version__

        # Build tag for nightly builds (from generated _build_meta.py or legacy _build_info.py)
        try:
            from ._build_meta import BUILD_TAG  # pragma: no cover — build only

            self.build_tag: str | None = BUILD_TAG  # pragma: no cover
        except ImportError:
            try:
                from ._build_info import BUILD_TAG

                self.build_tag = BUILD_TAG
            except ImportError:
                self.build_tag = None

        # Set up paths (similar to Toga's paths API)
        self.paths = Paths()

        # Core components (initialized in OnInit)
        self.config_manager: ConfigManager | None = None
        self.weather_client: WeatherClient | None = None
        self.location_manager: LocationManager | None = None
        self.presenter: WeatherPresenter | None = None
        self.update_service = None
        self.single_instance_manager: SingleInstanceManager | None = None
        self.weather_history_service = None

        # UI components
        self.main_window: MainWindow | None = None

        # Background update
        self._update_timer: wx.Timer | None = None
        self._auto_update_check_timer: wx.Timer | None = None
        self._startup_update_check_deferred: bool = False
        self.is_updating: bool = False

        # Weather data storage
        self.current_weather_data: WeatherData | None = None

        # Alert management
        self.alert_manager: AlertManager | None = None
        self.alert_notification_system: AlertNotificationSystem | None = None

        # Notification system
        self._notifier = None

        # System tray icon (initialized after main window)
        self.tray_icon = None

        # Taskbar icon text updater for dynamic tooltips
        self.taskbar_icon_updater = None

        # Async event loop for background tasks
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None

        super().__init__()

    @property
    def notifier(self):
        """Public accessor for the app-level notifier (used by notification subsystems)."""
        return self._notifier

    @notifier.setter
    def notifier(self, value) -> None:
        self._notifier = value

    def OnInit(self) -> bool:
        """Initialize the application (wxPython entry point)."""
        logger.info("Starting AccessiWeather application (wxPython)")

        # Startup identity repair disabled to avoid visible terminal popups.
        # Toast behavior now relies on installer/runtime defaults without shelling out.

        try:
            # Check for single instance
            self.single_instance_manager = SingleInstanceManager(self)
            if not self.single_instance_manager.try_acquire_lock():
                if self._updated:
                    # After an update restart the old lock file is stale; force-acquire it
                    logger.info("Post-update restart: forcing lock acquisition")
                    self.single_instance_manager.force_remove_lock()
                    self.single_instance_manager.try_acquire_lock()
                else:
                    logger.info("Another instance is already running, showing force start dialog")
                    if not self._show_force_start_dialog():
                        return False

            # Start async event loop in background thread
            self._start_async_loop()

            # Initialize core components
            self._initialize_components()

            # Create main window
            from .ui.main_window import MainWindow

            self.main_window = MainWindow(app=self)

            # Set up keyboard accelerators (shortcuts)
            self._setup_accelerators()

            # Initialize system tray icon
            self._initialize_tray_icon()

            # Load initial data
            self._load_initial_data()

            # Start background update timer
            self._start_background_updates()

            # Play startup sound
            self._play_startup_sound()

            # Initialize taskbar icon updater for dynamic tooltips
            self._initialize_taskbar_updater()

            # Show window (or minimize to tray if setting enabled)
            self._show_or_minimize_window()

            # Show one-time startup guidance prompts (non-blocking).
            self._schedule_startup_guidance_prompts()

            # Start periodic automatic update checks
            self._start_auto_update_checks()

            # Check for updates on startup, after onboarding completes when shown.
            self._check_for_updates_after_startup_guidance()

            logger.info("AccessiWeather application started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start application: {e}", exc_info=True)
            wx.MessageBox(
                f"Failed to start application: {e}",
                "Startup Error",
                wx.OK | wx.ICON_ERROR,
            )
            return False

    def _schedule_startup_guidance_prompts(self) -> None:
        """Schedule lightweight first-run and portable hints after startup."""
        wx.CallLater(400, self._maybe_auto_import_keys_file)
        wx.CallLater(800, self._maybe_show_first_start_onboarding)
        wx.CallLater(1400, self._maybe_show_portable_missing_keys_hint)

    # Keyring key used to cache the portable bundle passphrase for convenience.
    # Only the passphrase is stored here — API keys always live in the bundle.
    _PORTABLE_PASSPHRASE_KEYRING_KEY: str = "portable_bundle_passphrase"

    def _maybe_auto_import_keys_file(self) -> None:
        """
        Auto-import an encrypted API key bundle on startup (portable mode only).

        API keys always live in the bundle — keyring is not used for key storage.
        The bundle passphrase is cached in keyring purely for convenience so the
        user is not prompted on every launch.  On first launch (or new machine)
        the user is prompted once; on success the passphrase is stored in keyring
        for silent auto-import on subsequent launches.
        """
        if not self.main_window or not self.config_manager:
            return
        if not self._portable_mode:
            return

        # Skip if already imported this session.
        if self._portable_keys_imported_this_session:
            return

        config_dir = self.config_manager.config_dir
        candidate_names = ["api-keys.keys", "api-keys.awkeys"]
        keys_path = None
        for name in candidate_names:
            p = config_dir / name
            if p.exists():
                keys_path = p
                break

        if keys_path is None:
            return

        from .config.secure_storage import SecureStorage

        # Try cached passphrase for silent auto-import.
        stored = (SecureStorage.get_password(self._PORTABLE_PASSPHRASE_KEYRING_KEY) or "").strip()
        if stored:
            try:
                if self.config_manager.import_encrypted_api_keys(keys_path, stored):
                    self._portable_keys_imported_this_session = True
                    self._write_keys_file_after_import(config_dir, stored)
                    logger.info("Portable API keys auto-imported silently.")
                    return
            except Exception as exc:
                logger.warning("Silent auto-import failed: %s", exc)
            # Cached passphrase is stale — clear and fall through to prompt.
            SecureStorage.delete_password(self._PORTABLE_PASSPHRASE_KEYRING_KEY)

        # Prompt for passphrase with retry loop.
        while True:
            with wx.TextEntryDialog(
                self.main_window,
                "An encrypted API key bundle was found. Enter your passphrase to import your keys.",
                "Import API keys",
                style=wx.OK | wx.CANCEL | wx.TE_PASSWORD,
            ) as dlg:
                result = dlg.ShowModal()
                if result != wx.ID_OK:
                    return
                passphrase = dlg.GetValue().strip()

            if not passphrase:
                return

            try:
                success = self.config_manager.import_encrypted_api_keys(keys_path, passphrase)
            except Exception as exc:
                logger.warning("Auto-import of API keys failed: %s", exc)
                success = False

            if success:
                self._portable_keys_imported_this_session = True
                # Cache passphrase in keyring so next launch is silent.
                SecureStorage.set_password(self._PORTABLE_PASSPHRASE_KEYRING_KEY, passphrase)
                self._write_keys_file_after_import(config_dir, passphrase)
                wx.MessageBox(
                    "API keys imported successfully. They are now active.",
                    "Keys imported",
                    wx.OK | wx.ICON_INFORMATION,
                )
                return

            # Wrong passphrase or other failure — offer retry or skip.
            retry_dlg = wx.MessageDialog(
                self.main_window,
                "The passphrase was incorrect or the key bundle could not be read.\n\n"
                "Would you like to try again?",
                "Import failed",
                wx.YES_NO | wx.ICON_WARNING,
            )
            retry_dlg.SetYesNoLabels("Try again", "Skip")
            retry_result = retry_dlg.ShowModal()
            retry_dlg.Destroy()
            if retry_result != wx.ID_YES:
                return

    def _write_keys_file_after_import(self, config_dir: Path, passphrase: str) -> None:
        """
        Write api-keys.keys to the portable config dir after a successful import.

        This ensures the canonical bundle file is always present so that a new
        machine or clean keyring can re-import from it.
        """
        keys_dest = config_dir / "api-keys.keys"
        try:
            self.config_manager.export_encrypted_api_keys(keys_dest, passphrase)
        except Exception as exc:
            logger.warning("Failed to write api-keys.keys after import: %s", exc)

    def _should_show_first_start_onboarding(self) -> bool:
        """Return True when first-start onboarding should be shown."""
        if not self.main_window or not self.config_manager:
            return False

        if self._force_wizard:
            if self.debug_mode:
                logger.debug("Wizard forced via --wizard flag")
            return True

        config = self.config_manager.get_config()
        settings = config.settings
        return not getattr(settings, "onboarding_wizard_shown", False) and not bool(
            config.locations
        )

    def _check_for_updates_after_startup_guidance(self) -> None:
        """Run startup update checks now, or defer until onboarding closes."""
        self._startup_update_check_deferred = self._should_show_first_start_onboarding()
        if self._startup_update_check_deferred:
            return
        self._check_for_updates_on_startup()

    def _run_deferred_startup_update_check(self) -> None:
        """Run the deferred startup update check once after onboarding finishes."""
        if not getattr(self, "_startup_update_check_deferred", False):
            return
        self._startup_update_check_deferred = False
        self._check_for_updates_on_startup()

    def _maybe_show_portable_missing_keys_hint(self) -> None:
        """Show a one-time hint when portable mode has no bundle and no keys entered."""
        if not self.main_window or not self.config_manager or not self._portable_mode:
            return

        settings = self.config_manager.get_settings()
        if getattr(settings, "portable_missing_api_keys_hint_shown", False):
            return

        # If the onboarding wizard is going to run (or did run), it covers key setup.
        if self._should_show_first_start_onboarding():
            return

        # If a bundle exists the import flow already handled it — no hint needed.
        config_dir = self.config_manager.config_dir
        bundle_exists = any(
            (config_dir / name).exists() for name in ("api-keys.keys", "api-keys.awkeys")
        )
        if bundle_exists:
            return

        # If keys were imported this session, no hint needed.
        if self._portable_keys_imported_this_session:
            return

        dialog = wx.MessageDialog(
            self.main_window,
            "This portable copy has no API keys yet.\n\n"
            "Visual Crossing weather provider keys can be entered in Settings > Data Sources. "
            "OpenRouter AI keys can be entered in Settings > AI.\n\n"
            "You can also create an encrypted key bundle to carry your keys with the portable install.",
            "Portable setup hint",
            wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION,
        )
        dialog.SetYesNoCancelLabels("Open Settings", "Later", "Cancel")
        result = dialog.ShowModal()
        dialog.Destroy()

        self.config_manager.update_settings(portable_missing_api_keys_hint_shown=True)

        if result == wx.ID_YES and self.main_window:
            self.main_window.open_settings()

    def _prompt_optional_secret(self, title: str, message: str) -> str | None:
        """Prompt for optional secret text value. Empty input means skip."""
        with wx.TextEntryDialog(
            self.main_window, message, title, style=wx.OK | wx.CANCEL | wx.TE_PASSWORD
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            return dlg.GetValue().strip() or ""

    def _prompt_optional_secret_with_link(
        self,
        title: str,
        message: str,
        key_page_url: str,
        key_page_action_label: str,
    ) -> str | None:
        """Prompt for an optional secret with an action to open its key page."""
        while True:
            choice_dialog = wx.MessageDialog(
                self.main_window,
                f"{message}\n\nChoose Enter key to type it now, {key_page_action_label}, or Skip.",
                title,
                wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION,
            )
            choice_dialog.SetYesNoCancelLabels("Enter key", key_page_action_label, "Skip")
            result = choice_dialog.ShowModal()
            choice_dialog.Destroy()

            if result == wx.ID_YES:
                return self._prompt_optional_secret(title, message)
            if result == wx.ID_NO:
                try:
                    webbrowser.open(key_page_url)
                except Exception as exc:
                    logger.warning("Failed opening API key page %s: %s", key_page_url, exc)
                continue
            return ""

    def _maybe_offer_test_key_now(self, key_name: str) -> None:
        """Offer to open settings so users can validate the entered key immediately."""
        if not self.main_window:
            return

        test_dialog = wx.MessageDialog(
            self.main_window,
            f"{key_name} saved. Test key now in Settings > AI?",
            "Key saved",
            wx.YES_NO | wx.ICON_INFORMATION,
        )
        test_dialog.SetYesNoLabels("Test key now", "Later")
        result = test_dialog.ShowModal()
        test_dialog.Destroy()

        if result == wx.ID_YES:
            self.main_window.open_settings(tab="AI")

    def _has_saved_api_key(self, key_name: str) -> bool:
        """Return True when a specific API key exists (in-memory config for portable, keyring for installed)."""
        if self._portable_mode:
            # In portable mode keys live in the bundle / in-memory config, not keyring.
            val = getattr(self.config_manager.get_config().settings, key_name, None)
            return bool((str(val).strip()) if val else "")
        from .config.secure_storage import SecureStorage

        return bool((SecureStorage.get_password(key_name) or "").strip())

    @staticmethod
    def _onboarding_status_text(enabled: bool) -> str:
        return "Yes" if enabled else "No"

    def _show_onboarding_readiness_summary(self) -> None:
        """Show an end-of-onboarding summary of key setup readiness."""
        if not self.main_window or not self.config_manager:
            return

        config = self.config_manager.get_config()
        summary_lines = [
            "Setup summary:",
            f"- Location configured: {self._onboarding_status_text(bool(config.locations))}",
            f"- OpenRouter key set: {self._onboarding_status_text(self._has_saved_api_key('openrouter_api_key'))}",
            f"- Visual Crossing weather provider key set: {self._onboarding_status_text(self._has_saved_api_key('visual_crossing_api_key'))}",
            *(
                [
                    f"- Portable key bundle created: {self._onboarding_status_text(self._portable_keys_imported_this_session)}"
                ]
                if self._portable_mode
                else []
            ),
        ]

        summary_dialog = wx.MessageDialog(
            self.main_window,
            "\n".join(summary_lines),
            "Onboarding readiness",
            wx.OK | wx.ICON_INFORMATION,
        )
        summary_dialog.ShowModal()
        summary_dialog.Destroy()

    def _maybe_show_first_start_onboarding(self) -> None:
        """Show a minimal onboarding wizard once on fresh setup."""
        if not self._should_show_first_start_onboarding():
            self._run_deferred_startup_update_check()
            return

        total_steps = 4 if self._portable_mode else 3

        step1 = wx.MessageDialog(
            self.main_window,
            f"Welcome to AccessiWeather.\n\nStep 1 of {total_steps}: Add your first location now?",
            "Getting started",
            wx.YES_NO | wx.ICON_INFORMATION,
        )
        step1.SetYesNoLabels("Add location", "Skip")
        step1_result = step1.ShowModal()
        step1.Destroy()

        if step1_result == wx.ID_YES and self.main_window:
            self.main_window.on_add_location()

        from .config.secure_storage import is_keyring_available

        if not self._portable_mode and not is_keyring_available():
            _warn_dlg = wx.MessageDialog(
                self.main_window,
                "Your system keyring is not available.\n\n"
                "API keys you enter cannot be stored securely on this machine. "
                "On Linux, installing a keyring backend (e.g. gnome-keyring or KWallet) "
                "is recommended.\n\n"
                "You can still enter keys now; if portable mode is enabled with an encrypted "
                "bundle they will be saved there — otherwise they will be lost on exit.",
                "Secure storage unavailable",
                wx.OK | wx.ICON_WARNING,
            )
            _warn_dlg.ShowModal()
            _warn_dlg.Destroy()

        # Collect keys entered in steps 2/3 — in portable mode we write directly to
        # the bundle rather than going through keyring (which isn't used in portable).
        _wizard_keys: dict[str, str] = {}

        openrouter_key = self._prompt_optional_secret_with_link(
            "OpenRouter API key (optional)",
            f"Step 2 of {total_steps}: Enter your OpenRouter API key now, or leave blank to skip.",
            "https://openrouter.ai/keys",
            "Get OpenRouter API key",
        )
        if openrouter_key is not None and openrouter_key:
            if not self._portable_mode:
                self.config_manager.update_settings(openrouter_api_key=openrouter_key)
                self._maybe_offer_test_key_now("OpenRouter API key")
            else:
                _wizard_keys["openrouter_api_key"] = openrouter_key

        visual_crossing_key = self._prompt_optional_secret_with_link(
            "Visual Crossing weather provider key (optional)",
            f"Step 3 of {total_steps}: Enter your Visual Crossing weather provider key now, or leave blank to skip.",
            "https://www.visualcrossing.com/sign-up",
            "Get Visual Crossing weather provider key",
        )
        if visual_crossing_key is not None and visual_crossing_key:
            if not self._portable_mode:
                self.config_manager.update_settings(visual_crossing_api_key=visual_crossing_key)
                self._maybe_offer_test_key_now("Visual Crossing weather provider key")
            else:
                _wizard_keys["visual_crossing_api_key"] = visual_crossing_key

        if self._portable_mode and _wizard_keys:
            # Keys were entered — prompt for passphrase and write bundle directly.
            passphrase = self._prompt_optional_secret(
                "Step 4 of 4: Secure your API keys",
                "Enter a passphrase to encrypt your API keys into a portable bundle.\n"
                "This bundle travels with the app so your keys work on any machine.\n\n"
                "Leave blank to skip (keys will not be saved).",
            )
            if passphrase:
                try:
                    # Set keys in-memory first so export_encrypted_api_keys can read them.
                    for k, v in _wizard_keys.items():
                        setattr(self.config_manager.get_config().settings, k, v)
                    bundle_path = self.config_manager.get_portable_api_key_bundle_path()
                    success = self.config_manager.export_encrypted_api_keys(bundle_path, passphrase)
                    if success:
                        self._portable_keys_imported_this_session = True
                        # Cache passphrase so next launch is silent.
                        from .config.secure_storage import SecureStorage

                        SecureStorage.set_password(
                            self._PORTABLE_PASSPHRASE_KEYRING_KEY, passphrase
                        )
                        wx.MessageBox(
                            "API keys saved to encrypted bundle. They are now active.",
                            "Keys saved",
                            wx.OK | wx.ICON_INFORMATION,
                        )
                    else:
                        wx.MessageBox(
                            "Failed to save the key bundle. Keys will not persist after this session.",
                            "Bundle write failed",
                            wx.OK | wx.ICON_WARNING,
                        )
                except Exception as exc:
                    logger.error("Failed to write portable bundle: %s", exc)
                    wx.MessageBox(
                        "Failed to save the key bundle. Keys will not persist after this session.",
                        "Bundle write failed",
                        wx.OK | wx.ICON_WARNING,
                    )
            else:
                wx.MessageBox(
                    "No passphrase entered — API keys will not be saved.",
                    "Keys not saved",
                    wx.OK | wx.ICON_WARNING,
                )
        # No keys entered — skip step 4 entirely, nothing to bundle.

        self._show_onboarding_readiness_summary()
        self.config_manager.update_settings(onboarding_wizard_shown=True)
        self._run_deferred_startup_update_check()

    def _show_force_start_dialog(self) -> bool:
        """
        Show a dialog offering to force start when another instance appears to be running.

        Returns
        -------
            bool: True if user chose to force start and lock was acquired, False to exit

        """
        dialog = wx.MessageDialog(
            None,
            "AccessiWeather appears to be already running, or a previous session "
            "didn't close properly.\n\n"
            "Would you like to force start? This will close any existing instance.",
            "AccessiWeather - Already Running",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        dialog.SetYesNoLabels("Force Start", "Cancel")

        result = dialog.ShowModal()
        dialog.Destroy()

        if result == wx.ID_YES:
            logger.info("User chose to force start")
            if self.single_instance_manager.force_remove_lock():
                if self.single_instance_manager.try_acquire_lock():
                    logger.info("Successfully acquired lock after force removal")
                    return True
                logger.error("Failed to acquire lock even after force removal")
                wx.MessageBox(
                    "Failed to start AccessiWeather.\n\n"
                    "Please try closing any running instances and try again.",
                    "Startup Error",
                    wx.OK | wx.ICON_ERROR,
                )
            else:
                wx.MessageBox(
                    "Failed to remove the lock file.\n\n"
                    "Please try manually deleting the lock file or restarting your computer.",
                    "Startup Error",
                    wx.OK | wx.ICON_ERROR,
                )
            return False
        logger.info("User cancelled force start")
        return False

    def _start_async_loop(self) -> None:
        """Start asyncio event loop in a background thread."""

        def run_loop():
            self._async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._async_loop)
            self._async_loop.run_forever()

        self._async_thread = threading.Thread(target=run_loop, daemon=True)
        self._async_thread.start()

    def run_async(self, coro) -> None:
        """Run a coroutine in the background async loop."""
        if self._async_loop:
            asyncio.run_coroutine_threadsafe(coro, self._async_loop)

    def call_after_async(self, callback, *args) -> None:
        """Call a function on the main thread after async operation."""
        wx.CallAfter(callback, *args)

    def _initialize_components(self) -> None:
        """Initialize core application components."""
        from .app_initialization import initialize_components

        initialize_components(self)

    def _load_initial_data(self) -> None:
        """Load initial configuration and data."""
        from .app_initialization import load_initial_data

        load_initial_data(self)

    def _setup_accelerators(self) -> None:
        """Set up keyboard accelerators (shortcuts)."""
        if not self.main_window:
            return

        # Define keyboard shortcuts
        accelerators = [
            (wx.ACCEL_CTRL, ord("R"), self._on_refresh_shortcut),
            (wx.ACCEL_CTRL, ord("L"), self._on_add_location_shortcut),
            (wx.ACCEL_CTRL, ord("D"), self._on_remove_location_shortcut),
            (wx.ACCEL_CTRL, ord("H"), self._on_history_shortcut),
            (wx.ACCEL_CTRL, ord("S"), self._on_settings_shortcut),
            (wx.ACCEL_CTRL, ord("Q"), self._on_exit_shortcut),
            (wx.ACCEL_NORMAL, wx.WXK_F5, self._on_refresh_shortcut),
        ]

        # Create accelerator table
        # Access the frame directly (MainWindow is now a SizedFrame)
        frame = self.main_window
        accel_entries = []
        for flags, key, handler in accelerators:
            cmd_id = wx.NewIdRef()
            frame.Bind(wx.EVT_MENU, handler, id=cmd_id)
            accel_entries.append(wx.AcceleratorEntry(flags, key, cmd_id))

        accel_table = wx.AcceleratorTable(accel_entries)
        frame.SetAcceleratorTable(accel_table)
        logger.info("Keyboard accelerators set up successfully")

    def _on_refresh_shortcut(self, event) -> None:
        """Handle Ctrl+R / F5 shortcut."""
        if self.main_window:
            self.main_window.on_refresh()

    def _on_add_location_shortcut(self, event) -> None:
        """Handle Ctrl+L shortcut."""
        if self.main_window:
            self.main_window.on_add_location()

    def _on_remove_location_shortcut(self, event) -> None:
        """Handle Ctrl+D shortcut."""
        if self.main_window:
            self.main_window.on_remove_location()

    def _on_history_shortcut(self, event) -> None:
        """Handle Ctrl+H shortcut."""
        if self.main_window:
            self.main_window.on_view_history()

    def _on_settings_shortcut(self, event) -> None:
        """Handle Ctrl+S shortcut."""
        if self.main_window:
            self.main_window.on_settings()

    def _on_exit_shortcut(self, event) -> None:
        """Handle Ctrl+Q shortcut."""
        self.request_exit()

    def _initialize_tray_icon(self) -> None:
        """Initialize the system tray icon."""
        try:
            from .ui.system_tray import SystemTrayIcon

            self.tray_icon = SystemTrayIcon(self)
            logger.info("System tray icon initialized")

            # Wire tray balloon fallback into the notifier so toast failures
            # (e.g. WinRT silent drop when window is hidden) still show a visual.
            notifier = getattr(self, "_notifier", None)  # pragma: no cover
            if notifier is not None and hasattr(notifier, "balloon_fn"):  # pragma: no cover
                import wx

                tray = self.tray_icon

                def _balloon(title: str, message: str) -> None:
                    # NIIF_INFO (0x1) | NIIF_NOSOUND (0x10) — show info icon,
                    # suppress the default Windows chime (our soundpack plays instead).
                    wx.CallAfter(tray.ShowBalloon, title, message, 5000, 0x11)

                notifier.balloon_fn = _balloon
                logger.debug("Tray balloon fallback wired into notifier")
        except Exception as e:
            logger.warning(f"Failed to initialize system tray icon: {e}")
            self.tray_icon = None

    def _initialize_taskbar_updater(self) -> None:
        """Initialize the taskbar icon updater for dynamic tooltips."""
        try:
            from .taskbar_icon_updater import TaskbarIconUpdater

            settings = self.config_manager.get_settings()
            self.taskbar_icon_updater = TaskbarIconUpdater(
                text_enabled=getattr(settings, "taskbar_icon_text_enabled", False),
                dynamic_enabled=getattr(settings, "taskbar_icon_dynamic_enabled", True),
                format_string=getattr(settings, "taskbar_icon_text_format", "{temp} {condition}"),
                temperature_unit=getattr(settings, "temperature_unit", "both"),
                verbosity_level=getattr(settings, "verbosity_level", "standard"),
            )
            logger.debug("Taskbar icon updater initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize taskbar icon updater: {e}")
            self.taskbar_icon_updater = None

    def _show_or_minimize_window(self) -> None:
        """Show the main window or minimize to tray based on settings."""
        if not self.main_window:
            return

        try:
            settings = self.config_manager.get_settings()
            # Only minimize to tray if setting is enabled AND tray icon is available
            if getattr(settings, "minimize_on_startup", False) and self.tray_icon:
                # Don't show the window - keep it hidden (starts minimized to tray)
                logger.info("Window minimized to tray on startup")
            else:
                # Show the window normally
                self.main_window.Show()
                if getattr(settings, "minimize_on_startup", False) and not self.tray_icon:
                    logger.warning("minimize_on_startup enabled but tray icon unavailable")
        except Exception as e:
            # On error, show the window to avoid invisible app
            logger.warning(f"Failed to check minimize setting, showing window: {e}")
            self.main_window.Show()

    def _stop_auto_update_checks(self) -> None:
        """Stop and detach the automatic update-check timer, if present."""
        timer = getattr(self, "_auto_update_check_timer", None)
        if not timer:
            return

        try:
            timer.Stop()
        except Exception as e:
            logger.debug(f"Failed to stop auto-update timer cleanly: {e}")

        # Unbind the old timer source so reconfiguration cannot stack handlers.
        with contextlib.suppress(Exception):
            self.Unbind(wx.EVT_TIMER, source=timer)

        self._auto_update_check_timer = None

    def _start_auto_update_checks(self) -> None:
        """Start periodic automatic update checks based on user settings."""
        try:
            settings = self.config_manager.get_settings()
            auto_enabled = bool(getattr(settings, "auto_update_enabled", True))

            # Stop existing timer before reconfiguring
            self._stop_auto_update_checks()

            if not auto_enabled:
                logger.debug("Automatic update checks disabled")
                return

            interval_hours = max(1, int(getattr(settings, "update_check_interval_hours", 24)))
            interval_ms = interval_hours * 60 * 60 * 1000

            timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._on_auto_update_check_timer, timer)
            timer.Start(interval_ms)
            self._auto_update_check_timer = timer

            logger.info(
                "Automatic update checks scheduled every %s hour(s)",
                interval_hours,
            )
        except Exception as e:
            logger.warning(f"Failed to start automatic update checks: {e}")

    def _on_auto_update_check_timer(self, event) -> None:
        """Run an automatic update check on timer ticks."""
        self._check_for_updates_on_startup()

    def _check_for_updates_on_startup(self) -> None:
        """Check for updates on startup if enabled in settings."""
        try:
            # Skip update checks when running from source (not a frozen PyInstaller build)
            if not getattr(sys, "frozen", False):
                logger.debug("Running from source, skipping update check")
                return

            settings = self.config_manager.get_settings()
            if not getattr(settings, "auto_update_enabled", True):
                logger.debug("Automatic update check disabled")
                return

            channel = getattr(settings, "update_channel", "stable")

            def do_check():
                import asyncio

                from .services.simple_update import UpdateService, parse_nightly_date

                try:
                    current_version = getattr(self, "version", "0.0.0")
                    build_tag = getattr(self, "build_tag", None)
                    current_nightly_date = parse_nightly_date(build_tag) if build_tag else None
                    display_version = (
                        current_nightly_date if current_nightly_date else current_version
                    )

                    # Safety: if frozen but no build_tag and checking nightly channel,
                    # skip auto-prompt to avoid infinite update loops
                    if not build_tag and channel == "nightly":
                        logger.warning(
                            "Skipping startup nightly update check: no build_tag available. "
                            "Use Help > Check for Updates to check manually."
                        )
                        return

                    async def check():
                        service = UpdateService("AccessiWeather")
                        try:
                            return await service.check_for_updates(
                                current_version=current_version,
                                current_nightly_date=current_nightly_date,
                                channel=channel,
                            )
                        finally:
                            await service.close()

                    update_info = asyncio.run(check())

                    if update_info:  # pragma: no cover — UI prompt
                        # Show changelog dialog for available update
                        channel_label = "Nightly" if update_info.is_nightly else "Stable"
                        logger.info(f"Update available: {update_info.version} ({channel_label})")

                        def show_update_notification():
                            from .ui.dialogs.update_dialog import UpdateAvailableDialog

                            main_window = self.GetTopWindow()
                            dlg = UpdateAvailableDialog(
                                parent=main_window,
                                current_version=display_version,
                                new_version=update_info.version,
                                channel_label=channel_label,
                                release_notes=update_info.release_notes,
                            )
                            result = dlg.ShowModal()
                            dlg.Destroy()
                            if result == wx.ID_OK:
                                self._download_and_apply_update(update_info)

                        wx.CallAfter(show_update_notification)
                    else:
                        logger.debug("No updates available")

                except Exception as e:
                    logger.warning(f"Startup update check failed: {e}")

            # Run in background thread to not block startup
            import threading

            thread = threading.Thread(target=do_check, daemon=True)
            thread.start()

        except Exception as e:
            logger.warning(f"Failed to initiate startup update check: {e}")

    def _download_and_apply_update(self, update_info) -> None:
        """
        Download and apply an update.

        Args:
            update_info: UpdateInfo object from the update service.

        """
        import asyncio
        import tempfile
        from pathlib import Path

        from .config_utils import is_portable_mode
        from .services.simple_update import UpdateService, apply_update

        # Create progress dialog
        parent = self.main_window if self.main_window else None
        progress_dlg = wx.ProgressDialog(
            "Downloading Update",
            f"Downloading {update_info.artifact_name}...",
            maximum=100,
            parent=parent,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
        )

        def do_download():
            try:
                dest_dir = Path(tempfile.gettempdir())

                def progress_callback(downloaded, total):
                    if total > 0:
                        percent = int((downloaded / total) * 100)
                        wx.CallAfter(
                            progress_dlg.Update,
                            percent,
                            f"Downloading... {downloaded // 1024} / {total // 1024} KB",
                        )

                async def download():
                    service = UpdateService("AccessiWeather")
                    try:
                        return await service.download_update(
                            update_info, dest_dir, progress_callback
                        )
                    finally:
                        await service.close()

                update_path = asyncio.run(download())

                wx.CallAfter(progress_dlg.Destroy)

                # Ask for confirmation before applying
                def confirm_apply():
                    result = wx.MessageBox(
                        "Download complete. The application will now restart "
                        "to apply the update.\n\n"
                        "Continue?",
                        "Apply Update",
                        wx.YES_NO | wx.ICON_QUESTION,
                    )
                    if result == wx.YES:
                        portable = is_portable_mode()
                        # Destroy all wx windows so file handles are released before exit
                        for win in wx.GetTopLevelWindows():
                            with contextlib.suppress(Exception):
                                win.Destroy()
                        wx.SafeYield()
                        apply_update(update_path, portable=portable)

                wx.CallAfter(confirm_apply)

            except Exception as e:
                logger.error(f"Error downloading update: {e}")
                wx.CallAfter(progress_dlg.Destroy)
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to download update:\n{e}",
                    "Download Error",
                    wx.OK | wx.ICON_ERROR,
                )

        # Run download in background thread
        import threading

        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()

    def update_tray_tooltip(self, weather_data=None, location_name: str | None = None) -> None:
        """
        Update the system tray icon tooltip with current weather.

        Args:
            weather_data: Current weather data
            location_name: Name of the current location

        """
        if not self.tray_icon or not self.taskbar_icon_updater:
            return

        try:
            tooltip = self.taskbar_icon_updater.format_tooltip(weather_data, location_name)
            self.tray_icon.update_tooltip(tooltip)
        except Exception as e:
            logger.debug(f"Failed to update tray tooltip: {e}")

    def _stop_background_updates(self) -> None:
        """Stop any running background timers."""
        weather_timer = getattr(self, "_update_timer", None)
        if weather_timer:
            weather_timer.Stop()

        event_timer = getattr(self, "_event_check_timer", None)
        if event_timer:
            event_timer.Stop()

    def _start_background_updates(self) -> None:
        """Start split background timers for full refreshes and lightweight event checks."""
        try:
            from .constants import ALERT_POLL_INTERVAL_SECONDS

            self._stop_background_updates()
            settings = self.config_manager.get_settings()
            interval_minutes = getattr(settings, "update_interval_minutes", 10)
            interval_ms = interval_minutes * 60 * 1000
            event_interval_ms = ALERT_POLL_INTERVAL_SECONDS * 1000

            self._update_timer = wx.Timer()
            self._update_timer.Bind(wx.EVT_TIMER, self._on_background_update)
            self._update_timer.Start(interval_ms)

            self._event_check_timer = wx.Timer()
            self._event_check_timer.Bind(wx.EVT_TIMER, self._on_event_check_update)
            self._event_check_timer.Start(event_interval_ms)

            logger.info(
                "Background updates started (weather every %s minutes, events every %ss)",
                interval_minutes,
                ALERT_POLL_INTERVAL_SECONDS,
            )
        except Exception as e:
            logger.error(f"Failed to start background updates: {e}")

    def _on_background_update(self, event) -> None:
        """Handle slower full weather refresh timer event."""
        if self.main_window and not self.is_updating:
            self.main_window.refresh_weather_async()

    def _on_event_check_update(self, event) -> None:
        """Handle fast lightweight event-check timer event."""
        if self.main_window:
            self.main_window.refresh_notification_events_async()

    def _play_startup_sound(self) -> None:
        """Play startup sound if enabled."""
        try:
            settings = self.config_manager.get_settings()
            if getattr(settings, "sound_enabled", True):
                from .notifications.sound_player import play_startup_sound

                sound_pack = getattr(settings, "sound_pack", "default")
                muted_events = getattr(settings, "muted_sound_events", ["data_updated"])
                play_startup_sound(sound_pack, muted_events=muted_events)
        except Exception as e:
            logger.debug(f"Could not play startup sound: {e}")

    def request_exit(self) -> None:
        """Request application exit with cleanup."""
        logger.info("Application exit requested")

        # Stop background updates
        self._stop_background_updates()

        self._stop_auto_update_checks()

        # Play exit sound without blocking shutdown.
        try:
            settings = self.config_manager.get_settings()
            if getattr(settings, "sound_enabled", True):
                from .notifications.sound_player import (
                    PLAYSOUND_AVAILABLE,
                    SOUND_LIB_AVAILABLE,
                    play_exit_sound,
                )

                sound_pack = getattr(settings, "sound_pack", "default")
                muted_events = getattr(settings, "muted_sound_events", ["data_updated"])
                frozen = bool(getattr(sys, "frozen", False))
                logger.debug(
                    "[packaging-diag] exit sound: frozen=%s sound_pack=%s sound_lib=%s playsound3=%s",
                    frozen,
                    sound_pack,
                    SOUND_LIB_AVAILABLE,
                    PLAYSOUND_AVAILABLE,
                )

                play_exit_sound(sound_pack, muted_events=muted_events)
        except Exception:
            pass

        # Clean up system tray icon
        if self.tray_icon:
            self.tray_icon.RemoveIcon()
            self.tray_icon.Destroy()
            self.tray_icon = None

        # Release single instance lock
        if self.single_instance_manager:
            self.single_instance_manager.release_lock()

        # Stop async loop
        if self._async_loop:
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)

        # Close main window and exit
        if self.main_window:
            self.main_window.Destroy()

        self.ExitMainLoop()

    def refresh_runtime_settings(self) -> None:
        """Refresh runtime components with current settings."""
        try:
            settings = self.config_manager.get_settings()
            logger.info("Refreshing runtime settings")

            if self.weather_client:
                self.weather_client.settings = settings
                self.weather_client.data_source = settings.data_source
                self.weather_client.alerts_enabled = bool(settings.enable_alerts)

            if self.presenter:
                self.presenter.settings = settings

            if self._notifier:
                self._notifier.sound_enabled = bool(getattr(settings, "sound_enabled", True))
                self._notifier.soundpack = getattr(settings, "sound_pack", "default")
                self._notifier.muted_sound_events = list(
                    getattr(settings, "muted_sound_events", ["data_updated"])
                )

            if self.alert_notification_system:
                self.alert_notification_system.settings = settings

            # Update taskbar icon updater settings
            if self.taskbar_icon_updater:
                self.taskbar_icon_updater.update_settings(
                    text_enabled=getattr(settings, "taskbar_icon_text_enabled", False),
                    dynamic_enabled=getattr(settings, "taskbar_icon_dynamic_enabled", True),
                    format_string=getattr(
                        settings, "taskbar_icon_text_format", "{temp} {condition}"
                    ),
                    temperature_unit=getattr(settings, "temperature_unit", "both"),
                    verbosity_level=getattr(settings, "verbosity_level", "standard"),
                )

            self._start_auto_update_checks()
            self._start_background_updates()

            logger.info("Runtime settings refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh runtime settings: {e}")


def main(
    config_dir: str | None = None,
    portable_mode: bool = False,
    debug: bool = False,
    fake_version: str | None = None,
    fake_nightly: str | None = None,
    force_wizard: bool = False,
    updated: bool = False,
):
    """
    Run AccessiWeather application.

    Args:
        config_dir: Custom configuration directory path.
        portable_mode: Run in portable mode.
        debug: Enable debug mode.
        fake_version: Fake version for testing updates (e.g., '0.1.0').
        fake_nightly: Fake nightly tag for testing updates (e.g., 'nightly-20250101').
        force_wizard: Force the onboarding wizard even if already shown.
        updated: Skip lock-file prompt (app was restarted after an update).

    """
    if config_dir is None:
        try:
            from .config_utils import _explicit_portable_config_dir

            explicit_portable_dir = _explicit_portable_config_dir()
            if explicit_portable_dir:
                config_dir = explicit_portable_dir
                portable_mode = True
        except Exception:
            pass

    app = AccessiWeatherApp(
        config_dir=config_dir,
        portable_mode=portable_mode,
        debug=debug,
        force_wizard=force_wizard,
        updated=updated,
    )

    # Override version/build_tag for update testing
    if fake_version:
        app.version = fake_version
        logger.info(f"Using fake version for testing: {fake_version}")
    if fake_nightly:
        app.build_tag = fake_nightly
        logger.info(f"Using fake nightly tag for testing: {fake_nightly}")

    app.MainLoop()
    return app


if __name__ == "__main__":
    main()
