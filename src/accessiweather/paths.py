"""
Cross-platform paths helper for wxPython.

This module provides a Paths class that mimics Toga's paths API,
allowing the same configuration code to work with wxPython.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def is_forced_portable_mode() -> bool:
    """Return True when portable mode is forced via environment override."""
    return os.environ.get("ACCESSIWEATHER_FORCE_PORTABLE", "").lower() in {
        "1",
        "true",
        "yes",
    }


def detect_portable_mode() -> bool:
    """Detect portable mode using the canonical runtime marker rules."""
    if is_forced_portable_mode():
        return True

    if not getattr(sys, "frozen", False):
        return False

    exe_dir = Path(sys.executable).parent
    return (exe_dir / ".portable").exists() or (exe_dir / "config").is_dir()


class Paths:
    """
    Cross-platform application paths.

    Provides standard paths for application data, config, cache, and logs
    following platform conventions:
    - Windows: %LOCALAPPDATA%/Orinks/AccessiWeather/
    - macOS: ~/Library/Application Support/AccessiWeather/
    - Linux: ~/.local/share/accessiweather/ (XDG spec)
    """

    def __init__(self, app_name: str = "AccessiWeather", author: str = "Orinks"):
        """
        Initialize paths for the application.

        Args:
            app_name: Application name for directory naming
            author: Author/organization name (used on Windows)

        """
        self._app_name = app_name
        self._author = author
        self._base_path: Path | None = None

    def _get_base_path(self) -> Path:
        """Get the base path for application data."""
        if self._base_path is not None:
            return self._base_path

        # Portable mode override for frozen builds:
        # if explicit marker exists (or forced), keep all app data beside the exe.
        if getattr(sys, "frozen", False) and detect_portable_mode():
            self._base_path = Path(sys.executable).parent
            return self._base_path

        if sys.platform == "win32":
            # Windows: %LOCALAPPDATA%/Author/AppName/
            local_app_data = os.environ.get("LOCALAPPDATA")
            if local_app_data:
                self._base_path = Path(local_app_data) / self._author / self._app_name
            else:
                self._base_path = Path.home() / "AppData" / "Local" / self._author / self._app_name
        elif sys.platform == "darwin":
            # macOS: ~/Library/Application Support/AppName/
            self._base_path = Path.home() / "Library" / "Application Support" / self._app_name
        else:
            # Linux/other: ~/.local/share/appname/ (XDG spec)
            xdg_data = os.environ.get("XDG_DATA_HOME")
            if xdg_data:
                self._base_path = Path(xdg_data) / self._app_name.lower()
            else:
                self._base_path = Path.home() / ".local" / "share" / self._app_name.lower()

        return self._base_path

    @property
    def app(self) -> Path:
        """The path to the application installation directory."""
        if getattr(sys, "frozen", False):
            # Running as compiled executable
            return Path(sys.executable).parent
        # Running as script
        return Path(__file__).parent

    @property
    def data(self) -> Path:
        """The path for application data files."""
        path = self._get_base_path() / "Data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def config(self) -> Path:
        """The path for configuration files."""
        path = self._get_base_path() / "Config"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cache(self) -> Path:
        """The path for cache files."""
        path = self._get_base_path() / "Cache"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs(self) -> Path:
        """The path for log files."""
        path = self._get_base_path() / "Logs"
        path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass(frozen=True)
class RuntimeStoragePaths:
    """Canonical writable runtime storage layout resolved once at startup."""

    config_root: Path
    portable_mode: bool = False
    custom_config_dir: bool = False

    @property
    def config_file(self) -> Path:
        return self.config_root / "accessiweather.json"

    @property
    def state_dir(self) -> Path:
        return self.config_root / "state"

    @property
    def runtime_state_file(self) -> Path:
        return self.state_dir / "runtime_state.json"

    @property
    def cache_dir(self) -> Path:
        return self.config_root / "weather_cache"

    @property
    def noaa_radio_preferences_file(self) -> Path:
        return self.config_root / "noaa_radio_prefs.json"

    @property
    def lock_file(self) -> Path:
        return self.state_dir / "accessiweather.lock"

    @property
    def activation_request_file(self) -> Path:
        return self.state_dir / "activation_request.json"


def resolve_runtime_storage(
    app_paths: Paths,
    *,
    config_dir: str | Path | None = None,
    portable_mode: bool = False,
) -> RuntimeStoragePaths:
    """Resolve the canonical writable runtime storage layout."""
    if config_dir is not None:
        return RuntimeStoragePaths(
            config_root=Path(config_dir),
            portable_mode=portable_mode,
            custom_config_dir=True,
        )

    if portable_mode:
        app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
        return RuntimeStoragePaths(config_root=app_dir / "config", portable_mode=True)

    return RuntimeStoragePaths(config_root=Path(app_paths.config))


def resolve_default_runtime_storage(
    *, config_dir: str | Path | None = None, portable_mode: bool = False
) -> RuntimeStoragePaths:
    """Resolve runtime storage without needing an app instance."""
    return resolve_runtime_storage(
        Paths(),
        config_dir=config_dir,
        portable_mode=portable_mode,
    )


def resolve_default_config_root(
    *, config_dir: str | Path | None = None, portable_mode: bool = False
) -> Path:
    """Return the canonical default config root for the current runtime."""
    return resolve_default_runtime_storage(
        config_dir=config_dir,
        portable_mode=portable_mode,
    ).config_root
