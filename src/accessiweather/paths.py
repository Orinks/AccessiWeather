"""
Cross-platform paths helper for wxPython.

This module provides a Paths class that mimics Toga's paths API,
allowing the same configuration code to work with wxPython.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


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
