"""
AccessiWeather wxPython application.

This module provides the main wxPython application class with excellent
screen reader accessibility.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
from contextlib import suppress
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


def _cleanup_local_appdata_dirs_in_portable_mode() -> None:
    """Remove empty LocalAppData app folders when running in portable mode."""
    if sys.platform != "win32":
        return

    try:
        from .config_utils import is_portable_mode

        if not is_portable_mode():
            return
    except Exception:
        return

    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return

    # Resolve appdata location from Paths metadata (avoid hardcoded author/app names).
    paths = Paths()
    author = getattr(paths, "_author", "Orinks")
    app_name = getattr(paths, "_app_name", "AccessiWeather")
    root = Path(local_appdata) / str(author) / str(app_name)
    if not root.exists():
        return

    # Only remove if effectively empty (allows harmless cleanup without data loss).
    contents = [p for p in root.rglob("*") if p.exists()]
    if not contents:
        root.rmdir()
        return

    non_empty_files = [p for p in contents if p.is_file() and p.stat().st_size > 0]
    if non_empty_files:
        return

    # Remove empty/zero-byte scaffold folders and files.
    for p in sorted(contents, key=lambda x: len(x.parts), reverse=True):
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
            elif p.is_dir():
                p.rmdir()
        except Exception:
            pass
    with suppress(Exception):
        root.rmdir()


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


def register_app_id_in_registry(
    app_id: str = WINDOWS_APP_USER_MODEL_ID,
    display_name: str = "AccessiWeather",
    icon_path: str | None = None,
) -> None:
    r"""
    Register the AppUserModelID in HKCU registry for portable/unpackaged builds.

    Windows 10 v1903+ converts Shell_NotifyIcon balloon tips to WinRT toasts.
    Without a registered AppID (via Start Menu shortcut OR registry), those toasts
    are silently dropped. Writing to HKCU\\Software\\Classes\\AppUserModelId\\{app_id}
    satisfies Windows without requiring a Start Menu shortcut — enabling toast
    notifications in portable builds.
    """
    if sys.platform != "win32":
        return

    try:  # pragma: no cover
        import winreg

        key_path = rf"Software\Classes\AppUserModelId\{app_id}"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, display_name)
            if icon_path:
                winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, icon_path)
        logger.debug("Registered AppUserModelID in registry: %s", app_id)
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to register AppUserModelID in registry: %s", exc)


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

    register_app_id_in_registry(app_id=app_id, display_name=display_name, icon_path=exe_path)
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

        verified = (
            state.get("verified") is True and state.get("readback_app_id") == app_id
        ) or (
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
    ):
        """
        Initialize the AccessiWeather application.

        Args:
            config_dir: Optional custom configuration directory path
            portable_mode: If True, use portable mode (config in app directory)
            debug: If True, enable debug mode (enables debug logging and extra UI tools)

        """
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

        # Keep portable mode fully self-contained.
        _cleanup_local_appdata_dirs_in_portable_mode()

        # Startup identity repair disabled to avoid visible terminal popups.
        # Toast behavior now relies on installer/runtime defaults without shelling out.

        try:
            # Check for single instance
            self.single_instance_manager = SingleInstanceManager(self)
            if not self.single_instance_manager.try_acquire_lock():
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

            # Check for updates on startup (if enabled)
            self._check_for_updates_on_startup()

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

    def _start_background_updates(self) -> None:
        """Start periodic background weather updates."""
        try:
            settings = self.config_manager.get_settings()
            interval_minutes = getattr(settings, "update_interval_minutes", 10)
            interval_ms = interval_minutes * 60 * 1000

            self._update_timer = wx.Timer()
            self._update_timer.Bind(wx.EVT_TIMER, self._on_background_update)
            self._update_timer.Start(interval_ms)
            logger.info(f"Background updates started (every {interval_minutes} minutes)")
        except Exception as e:
            logger.error(f"Failed to start background updates: {e}")

    def _on_background_update(self, event) -> None:
        """Handle background update timer event."""
        if self.main_window and not self.is_updating:
            self.main_window.refresh_weather_async()

    def _play_startup_sound(self) -> None:
        """Play startup sound if enabled."""
        try:
            settings = self.config_manager.get_settings()
            if getattr(settings, "sound_enabled", True):
                from .notifications.sound_player import play_startup_sound

                sound_pack = getattr(settings, "sound_pack", "default")
                play_startup_sound(sound_pack)
        except Exception as e:
            logger.debug(f"Could not play startup sound: {e}")

    def request_exit(self) -> None:
        """Request application exit with cleanup."""
        logger.info("Application exit requested")

        # Stop background updates
        if self._update_timer:
            self._update_timer.Stop()

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
                frozen = bool(getattr(sys, "frozen", False))
                logger.debug(
                    "[packaging-diag] exit sound: frozen=%s sound_pack=%s sound_lib=%s playsound3=%s",
                    frozen,
                    sound_pack,
                    SOUND_LIB_AVAILABLE,
                    PLAYSOUND_AVAILABLE,
                )

                play_exit_sound(sound_pack)
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

            logger.info("Runtime settings refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh runtime settings: {e}")


def main(
    config_dir: str | None = None,
    portable_mode: bool = False,
    debug: bool = False,
    fake_version: str | None = None,
    fake_nightly: str | None = None,
):
    """
    Run AccessiWeather application.

    Args:
        config_dir: Custom configuration directory path.
        portable_mode: Run in portable mode.
        debug: Enable debug mode.
        fake_version: Fake version for testing updates (e.g., '0.1.0').
        fake_nightly: Fake nightly tag for testing updates (e.g., 'nightly-20250101').

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

    app = AccessiWeatherApp(config_dir=config_dir, portable_mode=portable_mode, debug=debug)

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
