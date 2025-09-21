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

from .platform_detector import PlatformDetector

logger = logging.getLogger(__name__)


class StartupManager:
    """Manage application startup behaviour across supported platforms."""

    _MACOS_PLIST_LABEL = "net.orinks.accessiweather.startup"
    _LINUX_DESKTOP_FILENAME = "accessiweather.desktop"

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

    def _get_platform_name(self) -> str:
        platform_info = self._platform_detector.get_platform_info()
        return platform_info.platform

    def _get_app_name(self) -> str:
        platform_info = self._platform_detector.get_platform_info()
        candidate = platform_info.app_directory.name
        if candidate:
            return candidate
        if getattr(sys, "frozen", False):
            executable = self._get_app_executable()
            return executable.stem or "AccessiWeather"
        if sys.argv and sys.argv[0]:
            script_name = Path(sys.argv[0]).stem
            if script_name:
                return script_name
        executable = self._get_app_executable()
        return executable.stem or "AccessiWeather"

    def _get_app_executable(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve()
        if sys.executable:
            return Path(sys.executable).resolve()
        if sys.argv and sys.argv[0]:
            return Path(sys.argv[0]).resolve()
        return Path.cwd()

    def _get_launch_command(self) -> tuple[Path, list[str]]:
        if getattr(sys, "frozen", False):
            executable = self._get_app_executable()
            return executable, []

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

    # Windows helpers ---------------------------------------------------
    def _get_windows_startup_shortcut(self) -> Path:
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise FileNotFoundError("APPDATA environment variable not set")
        startup_dir = (
            Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        )
        if not self._ensure_directory_exists(startup_dir):
            raise OSError(f"Unable to create startup directory: {startup_dir}")
        return startup_dir / f"{self._get_app_name()}.lnk"

    def _enable_windows_startup(self) -> bool:
        try:
            shortcut_path = self._get_windows_startup_shortcut()
            executable, args = self._get_launch_command()
            self._create_windows_shortcut(executable, shortcut_path, args)
            logger.info("Created Windows startup shortcut at %s", shortcut_path)
            return True
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Failed enabling Windows startup: %s", exc)
        except RuntimeError as exc:
            logger.error("Failed creating Windows shortcut: %s", exc)
        return False

    def _disable_windows_startup(self) -> bool:
        try:
            shortcut_path = self._get_windows_startup_shortcut()
            if shortcut_path.exists():
                shortcut_path.unlink()
                logger.info("Removed Windows startup shortcut at %s", shortcut_path)
            return True
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Failed disabling Windows startup: %s", exc)
        return False

    def _is_windows_startup_enabled(self) -> bool:
        try:
            shortcut_path = self._get_windows_startup_shortcut()
            return shortcut_path.exists()
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error("Failed checking Windows startup status: %s", exc)
            return False

    def _escape_powershell_single_quotes(self, value: str) -> str:
        return value.replace("'", "''")

    def _create_windows_shortcut(
        self, target: Path, shortcut_path: Path, args: list[str] | None = None
    ) -> None:
        if not target.exists():
            raise FileNotFoundError(f"Target executable does not exist: {target}")

        target_str = self._escape_powershell_single_quotes(str(target))
        working_dir_str = self._escape_powershell_single_quotes(str(target.parent))
        shortcut_str = self._escape_powershell_single_quotes(str(shortcut_path))
        args_cmd = subprocess.list2cmdline(args) if args else ""
        args_script_line = ""
        if args_cmd:
            escaped_args = self._escape_powershell_single_quotes(args_cmd)
            args_script_line = f"$shortcut.Arguments = '{escaped_args}';"

        script = (
            "$shell = New-Object -COMObject WScript.Shell;"
            f"$shortcut = $shell.CreateShortcut('{shortcut_str}');"
            f"$shortcut.TargetPath = '{target_str}';"
            f"$shortcut.WorkingDirectory = '{working_dir_str}';"
            "$shortcut.WindowStyle = 1;"
            f"$shortcut.Description = '{self._escape_powershell_single_quotes(self._get_app_name())} startup shortcut';"
            f"{args_script_line}"
            "$shortcut.Save();"
        )

        commands = [
            ["powershell.exe", "-NoProfile", "-Command", script],
            ["pwsh", "-NoProfile", "-Command", script],
        ]

        missing_errors: list[FileNotFoundError] = []
        for command in commands:
            try:
                subprocess.run(command, check=True, capture_output=True)
                return
            except FileNotFoundError as exc:
                missing_errors.append(exc)
                continue
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
                raise RuntimeError(f"Failed to create shortcut via PowerShell: {stderr}") from exc

        raise RuntimeError(
            "PowerShell is required to create shortcuts on Windows; neither powershell.exe nor pwsh was found"
        ) from (missing_errors[-1] if missing_errors else None)

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
            if not getattr(sys, "frozen", False) and sys.argv and sys.argv[0]:
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
