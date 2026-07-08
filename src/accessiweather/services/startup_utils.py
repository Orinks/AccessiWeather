"""Startup management utilities for AccessiWeather."""

from __future__ import annotations

import configparser
import importlib.util
import logging
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

from ..runtime_env import is_compiled_runtime
from .platform_detector import PlatformDetector

if sys.platform == "win32":
    import winreg
else:  # pragma: no cover - exercised via fakes in tests
    winreg = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class StartupManager:
    """Manage application startup behaviour across supported platforms."""

    _MACOS_PLIST_LABEL = "net.orinks.accessiweather.startup"
    _LINUX_DESKTOP_FILENAME = "accessiweather.desktop"

    # Windows registration lives in the per-user Run key. Registry access is
    # in-process and instant, unlike the legacy Startup-folder .lnk approach
    # which needed a PowerShell subprocess just to read the shortcut back.
    _WINDOWS_RUN_VALUE_NAME = "AccessiWeather"
    _WINDOWS_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    # Task Manager / Settings "Startup apps" record their enable/disable
    # toggle here without touching the Run value or the .lnk itself.
    _WINDOWS_STARTUP_APPROVED_RUN_KEY_PATH = (
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
    )
    _WINDOWS_STARTUP_APPROVED_FOLDER_KEY_PATH = (
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"
    )
    # Shortcut names older releases dropped into the Startup folder. Kept only
    # so upgrades can migrate/clean them up.
    _WINDOWS_STARTUP_SHORTCUT_NAME = "AccessiWeather.lnk"

    def __init__(self, platform_detector: PlatformDetector | None = None) -> None:
        """Create a manager using an optional platform detector override."""
        self._platform_detector = platform_detector or PlatformDetector()

    def enable_startup(self) -> bool:
        """Enable launching the application when the user logs in."""
        platform_name = self._get_platform_name()
        logger.debug("Enabling startup for platform: %s", platform_name)

        if platform_name == "windows":
            return self._enable_windows_startup()
        if platform_name == "macos":
            return self._enable_macos_startup()
        if platform_name == "linux":
            return self._enable_linux_startup()

        logger.error("Unsupported platform for startup enablement: %s", platform_name)
        return False

    def disable_startup(self) -> bool:
        """Disable application launch at login."""
        platform_name = self._get_platform_name()
        logger.debug("Disabling startup for platform: %s", platform_name)

        if platform_name == "windows":
            return self._disable_windows_startup()
        if platform_name == "macos":
            return self._disable_macos_startup()
        if platform_name == "linux":
            return self._disable_linux_startup()

        logger.error("Unsupported platform for startup disablement: %s", platform_name)
        return False

    def is_startup_enabled(self) -> bool:
        """Return True if startup launch is currently configured."""
        platform_name = self._get_platform_name()
        logger.debug("Checking startup status for platform: %s", platform_name)

        if platform_name == "windows":
            return self._is_windows_startup_enabled()
        if platform_name == "macos":
            return self._is_macos_startup_enabled()
        if platform_name == "linux":
            return self._is_linux_startup_enabled()

        logger.error("Unsupported platform for startup status: %s", platform_name)
        return False

    def is_startup_disabled_by_os(self) -> bool:
        """
        Return True when startup is registered but the OS has switched it off.

        Windows Task Manager / Settings "Startup apps" disable entries via the
        StartupApproved registry flags while leaving the registration in place.
        Re-registering must not silently override that user choice.
        """
        if self._get_platform_name() != "windows" or winreg is None:
            return False

        if self._read_windows_run_value() is not None:
            return self._is_windows_startup_approved_disabled(
                self._WINDOWS_STARTUP_APPROVED_RUN_KEY_PATH,
                self._WINDOWS_RUN_VALUE_NAME,
            )

        for shortcut in self._get_legacy_windows_startup_shortcuts():
            if self._path_exists(shortcut):
                return self._is_windows_startup_approved_disabled(
                    self._WINDOWS_STARTUP_APPROVED_FOLDER_KEY_PATH,
                    shortcut.name,
                )
        return False

    def is_startup_registration_current(self) -> bool:
        """
        Return True when the registration launches the current installation.

        A stale registration (old executable path, legacy shortcut format, or
        an OS-level disable) reports False so callers can repair it.
        """
        platform_name = self._get_platform_name()
        if platform_name == "windows":
            if winreg is None:
                return False
            value = self._read_windows_run_value()
            if value is None or value != self._get_windows_run_command():
                return False
            if self._is_windows_startup_approved_disabled(
                self._WINDOWS_STARTUP_APPROVED_RUN_KEY_PATH,
                self._WINDOWS_RUN_VALUE_NAME,
            ):
                return False
            # Leftover legacy shortcuts would double-launch the app at logon.
            return not any(
                self._path_exists(shortcut)
                for shortcut in self._get_legacy_windows_startup_shortcuts()
            )
        return self.is_startup_enabled()

    def _get_platform_name(self) -> str:
        platform_info = self._platform_detector.get_platform_info()
        return platform_info.platform

    def _get_app_name(self) -> str:
        platform_info = self._platform_detector.get_platform_info()
        candidate = platform_info.app_directory.name
        if candidate:
            return candidate
        if is_compiled_runtime():
            executable = self._get_app_executable()
            return executable.stem or "AccessiWeather"
        if sys.argv and sys.argv[0]:
            script_name = Path(sys.argv[0]).stem
            if script_name:
                return script_name
        executable = self._get_app_executable()
        return executable.stem or "AccessiWeather"

    def _get_app_executable(self) -> Path:
        if is_compiled_runtime():
            return Path(sys.executable).resolve()
        if sys.executable:
            return Path(sys.executable).resolve()
        if sys.argv and sys.argv[0]:
            return Path(sys.argv[0]).resolve()
        return Path.cwd()

    def _get_launch_command(self, *, for_startup: bool = False) -> tuple[Path, list[str]]:
        if is_compiled_runtime():
            executable = self._get_app_executable()
            args: list[str] = []
            if for_startup:
                args.append("--startup")
            return executable, args

        if sys.executable:
            executable = Path(sys.executable).resolve()
        else:
            executable = self._get_app_executable()

        args: list[str]
        if importlib.util.find_spec("accessiweather") is not None:
            args = ["-m", "accessiweather"]
        elif sys.argv and sys.argv[0]:
            args = [str(Path(sys.argv[0]).resolve())]
        else:
            args = []

        if for_startup:
            args.append("--startup")
        return executable, args

    def _ensure_directory_exists(self, directory: Path) -> bool:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            return True
        except PermissionError as exc:
            logger.error("Permission denied creating directory %s: %s", directory, exc)
        except FileNotFoundError as exc:
            logger.error("Directory path not found %s: %s", directory, exc)
        except OSError as exc:
            logger.error("Failed creating directory %s: %s", directory, exc)
        return False

    @staticmethod
    def _path_exists(path: Path) -> bool:
        try:
            return path.exists()
        except OSError:
            return False

    # Windows helpers ---------------------------------------------------
    def _get_windows_run_command(self) -> str:
        executable, args = self._get_launch_command(for_startup=True)
        return subprocess.list2cmdline([str(executable), *args])

    def _read_windows_run_value(self) -> str | None:
        if winreg is None:
            return None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._WINDOWS_RUN_KEY_PATH) as key:
                value, _value_type = winreg.QueryValueEx(key, self._WINDOWS_RUN_VALUE_NAME)
        except FileNotFoundError:
            return None
        except OSError as exc:
            logger.error("Failed reading Windows startup Run value: %s", exc)
            return None
        return str(value) if value else None

    def _write_windows_run_value(self, command: str) -> bool:
        if winreg is None:
            return False
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self._WINDOWS_RUN_KEY_PATH) as key:
                winreg.SetValueEx(key, self._WINDOWS_RUN_VALUE_NAME, 0, winreg.REG_SZ, command)
            return True
        except OSError as exc:
            logger.error("Failed writing Windows startup Run value: %s", exc)
            return False

    def _delete_windows_registry_value(self, key_path: str, value_name: str) -> bool:
        """Delete a registry value, returning True when it no longer exists."""
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, value_name)
            return True
        except FileNotFoundError:
            return True
        except OSError as exc:
            logger.error("Failed deleting registry value %s\\%s: %s", key_path, value_name, exc)
            return False

    def _is_windows_startup_approved_disabled(self, key_path: str, value_name: str) -> bool:
        """
        Return True when a StartupApproved flag marks the entry disabled.

        The flag is REG_BINARY; an even first byte means enabled, an odd first
        byte means the user disabled the entry in Task Manager or Settings.
        A missing flag means enabled.
        """
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _value_type = winreg.QueryValueEx(key, value_name)
        except FileNotFoundError:
            return False
        except OSError as exc:
            logger.warning(
                "Failed reading StartupApproved flag %s\\%s: %s", key_path, value_name, exc
            )
            return False
        try:
            data = bytes(value) if value is not None else b""
        except (TypeError, ValueError):
            return False
        return bool(data) and bool(data[0] & 0x01)

    def _get_windows_startup_folder(self) -> Path | None:
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    def _get_legacy_windows_startup_shortcuts(self) -> list[Path]:
        """Startup-folder shortcuts created by older releases (cleanup targets)."""
        startup_dir = self._get_windows_startup_folder()
        if startup_dir is None:
            return []
        candidates = [
            startup_dir / self._WINDOWS_STARTUP_SHORTCUT_NAME,
            startup_dir / f"{self._get_app_name()}.lnk",
            startup_dir / "accessiweather.lnk",
        ]
        shortcuts: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = os.path.normcase(os.path.normpath(str(candidate)))
            if normalized not in seen:
                shortcuts.append(candidate)
                seen.add(normalized)
        return shortcuts

    def _cleanup_legacy_windows_startup_shortcuts(self) -> bool:
        """Remove legacy Startup-folder shortcuts; True when none remain."""
        all_removed = True
        for shortcut in self._get_legacy_windows_startup_shortcuts():
            try:
                if shortcut.exists():
                    shortcut.unlink()
                    logger.info("Removed legacy Windows startup shortcut at %s", shortcut)
            except OSError as exc:
                logger.warning("Could not remove legacy startup shortcut %s: %s", shortcut, exc)
            if self._path_exists(shortcut):
                all_removed = False
            else:
                # Drop the Task Manager flag for the shortcut so it cannot
                # affect a future shortcut with the same name.
                self._delete_windows_registry_value(
                    self._WINDOWS_STARTUP_APPROVED_FOLDER_KEY_PATH, shortcut.name
                )
        return all_removed

    def _enable_windows_startup(self) -> bool:
        if winreg is None:
            logger.error("winreg is unavailable; cannot enable Windows startup")
            return False
        command = self._get_windows_run_command()
        if not self._write_windows_run_value(command):
            return False
        # A leftover Task Manager "off" flag would silently block the fresh
        # registration; enabling here is an explicit user request to run.
        self._delete_windows_registry_value(
            self._WINDOWS_STARTUP_APPROVED_RUN_KEY_PATH, self._WINDOWS_RUN_VALUE_NAME
        )
        self._cleanup_legacy_windows_startup_shortcuts()
        logger.info("Registered Windows startup Run entry: %s", command)
        return True

    def _disable_windows_startup(self) -> bool:
        if winreg is None:
            logger.error("winreg is unavailable; cannot disable Windows startup")
            return False
        run_value_removed = self._delete_windows_registry_value(
            self._WINDOWS_RUN_KEY_PATH, self._WINDOWS_RUN_VALUE_NAME
        )
        self._delete_windows_registry_value(
            self._WINDOWS_STARTUP_APPROVED_RUN_KEY_PATH, self._WINDOWS_RUN_VALUE_NAME
        )
        shortcuts_removed = self._cleanup_legacy_windows_startup_shortcuts()
        if run_value_removed and shortcuts_removed:
            logger.info("Windows startup registration removed")
            return True
        return False

    def _is_windows_startup_enabled(self) -> bool:
        if winreg is None:
            return False
        # Presence is keyed on the value name, never on the stored command:
        # after an update the command may point at a stale path, but the user
        # intent is still "start with Windows" and callers repair the path.
        if self._read_windows_run_value() is not None:
            return not self._is_windows_startup_approved_disabled(
                self._WINDOWS_STARTUP_APPROVED_RUN_KEY_PATH,
                self._WINDOWS_RUN_VALUE_NAME,
            )
        # Legacy Startup-folder shortcut from an older release still counts as
        # enabled; the next enable_startup() migrates it to the Run key.
        for shortcut in self._get_legacy_windows_startup_shortcuts():
            if self._path_exists(shortcut):
                return not self._is_windows_startup_approved_disabled(
                    self._WINDOWS_STARTUP_APPROVED_FOLDER_KEY_PATH,
                    shortcut.name,
                )
        return False

    # macOS helpers ------------------------------------------------------
    def _get_macos_plist_path(self) -> Path:
        launch_agents = Path.home() / "Library" / "LaunchAgents"
        if not self._ensure_directory_exists(launch_agents):
            raise OSError(f"Unable to create LaunchAgents directory: {launch_agents}")
        return launch_agents / f"{self._MACOS_PLIST_LABEL}.plist"

    def _enable_macos_startup(self) -> bool:
        try:
            plist_path = self._get_macos_plist_path()
            executable, args = self._get_launch_command()
            if not is_compiled_runtime() and sys.argv and sys.argv[0]:
                working_directory = str(Path(sys.argv[0]).resolve().parent)
            else:
                working_directory = str(self._get_app_executable().parent)
            payload = {
                "Label": self._MACOS_PLIST_LABEL,
                "ProgramArguments": [str(executable)] + args,
                "RunAtLoad": True,
                "KeepAlive": False,
                "WorkingDirectory": working_directory,
            }
            with plist_path.open("wb") as plist_file:
                plistlib.dump(payload, plist_file)
            logger.info("Created macOS LaunchAgent plist at %s", plist_path)
            try:
                subprocess.run(
                    ["launchctl", "load", "-w", str(plist_path)],
                    check=True,
                    capture_output=True,
                )
            except FileNotFoundError:
                logger.warning(
                    "launchctl not found; macOS startup changes will take effect after next login"
                )
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
                logger.warning(
                    "Failed to load macOS LaunchAgent immediately via launchctl: %s", stderr
                )
            return True
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Failed enabling macOS startup: %s", exc)
        return False

    def _disable_macos_startup(self) -> bool:
        try:
            plist_path = self._get_macos_plist_path()
            if plist_path.exists():
                try:
                    subprocess.run(
                        ["launchctl", "unload", "-w", str(plist_path)],
                        check=True,
                        capture_output=True,
                    )
                except FileNotFoundError:
                    logger.warning(
                        "launchctl not found; macOS startup changes will take effect after next login"
                    )
                except subprocess.CalledProcessError as exc:
                    stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
                    logger.warning("Failed to unload macOS LaunchAgent via launchctl: %s", stderr)
                plist_path.unlink()
                logger.info("Removed macOS LaunchAgent plist at %s", plist_path)
            return True
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Failed disabling macOS startup: %s", exc)
        return False

    def _is_macos_startup_enabled(self) -> bool:
        try:
            plist_path = self._get_macos_plist_path()
            if not plist_path.exists():
                return False
            with plist_path.open("rb") as plist_file:
                payload = plistlib.load(plist_file)
            arguments = payload.get("ProgramArguments")
            if not isinstance(arguments, list) or not arguments:
                return False

            executable, args = self._get_launch_command()
            expected_arguments = [str(executable)] + args
            if arguments == expected_arguments:
                return True

            if sys.argv and sys.argv[0]:
                legacy_arguments = [str(Path(sys.argv[0]).resolve())]
                if arguments == legacy_arguments:
                    return True
            return False
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Failed checking macOS startup status: %s", exc)
        except plistlib.InvalidFileException as exc:
            logger.error("Invalid plist format for startup entry: %s", exc)
        return False

    # Linux helpers ------------------------------------------------------
    def _get_linux_desktop_entry_path(self) -> Path:
        autostart_dir = Path.home() / ".config" / "autostart"
        if not self._ensure_directory_exists(autostart_dir):
            raise OSError(f"Unable to create autostart directory: {autostart_dir}")
        return autostart_dir / self._LINUX_DESKTOP_FILENAME

    def _read_desktop_entry_exec(self, path: Path) -> str | None:
        config = configparser.ConfigParser(strict=False, interpolation=None)
        try:
            with path.open("r", encoding="utf-8") as desktop_file:
                config.read_file(desktop_file)
        except (OSError, configparser.Error) as exc:
            logger.warning("Failed reading desktop entry at %s: %s", path, exc)
            return None

        if config.has_option("Desktop Entry", "Exec"):
            return config.get("Desktop Entry", "Exec")
        return None

    def _compose_linux_exec_value(self, executable: Path, args: list[str]) -> str:
        exec_part = str(executable).replace('"', '\\"')
        parts = [f'"{exec_part}"']
        parts.extend(shlex.quote(arg) for arg in args)
        return " ".join(parts).strip()

    def _enable_linux_startup(self) -> bool:
        try:
            desktop_path = self._get_linux_desktop_entry_path()
            content = self._build_desktop_entry()
            desktop_path.write_text(content, encoding="utf-8")
            logger.info("Created Linux autostart desktop entry at %s", desktop_path)
            return True
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Failed enabling Linux startup: %s", exc)
        return False

    def _disable_linux_startup(self) -> bool:
        try:
            desktop_path = self._get_linux_desktop_entry_path()
            if desktop_path.exists():
                desktop_path.unlink()
                logger.info("Removed Linux autostart desktop entry at %s", desktop_path)
            return True
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Failed disabling Linux startup: %s", exc)
        return False

    def _is_linux_startup_enabled(self) -> bool:
        try:
            desktop_path = self._get_linux_desktop_entry_path()
            if not desktop_path.exists():
                return False
            exec_value = self._read_desktop_entry_exec(desktop_path)
            if not exec_value:
                return False

            try:
                exec_tokens = shlex.split(exec_value)
            except ValueError as exc:
                logger.warning("Failed parsing Exec entry in %s: %s", desktop_path, exc)
                return False

            executable, args = self._get_launch_command()
            expected_tokens = [str(executable)] + args
            if exec_tokens == expected_tokens:
                return True

            if sys.argv and sys.argv[0]:
                legacy_tokens = [str(Path(sys.argv[0]).resolve())]
                if exec_tokens == legacy_tokens:
                    return True
            return False
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Failed checking Linux startup status: %s", exc)
        return False

    def _build_desktop_entry(self) -> str:
        executable, args = self._get_launch_command()
        app_name = self._get_app_name()
        lines = [
            "[Desktop Entry]",
            "Type=Application",
            "Version=1.0",
            f"Name={app_name}",
            "Comment=Start AccessiWeather at login",
            f"Exec={self._compose_linux_exec_value(executable, args)}",
            "X-GNOME-Autostart-enabled=true",
        ]
        return "\n".join(lines) + "\n"
