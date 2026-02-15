"""Tests for the cross-platform Paths helper."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from accessiweather.paths import Paths


class TestPathsInit:
    """Test Paths initialization."""

    def test_default_names(self):
        p = Paths()
        assert p._app_name == "AccessiWeather"
        assert p._author == "Orinks"

    def test_custom_names(self):
        p = Paths(app_name="MyApp", author="Me")
        assert p._app_name == "MyApp"
        assert p._author == "Me"


class TestGetBasePath:
    """Test _get_base_path for each platform."""

    def test_windows_with_localappdata(self, tmp_path):
        p = Paths()
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}),
        ):
            result = p._get_base_path()
        assert result == tmp_path / "Orinks" / "AccessiWeather"

    def test_windows_without_localappdata(self):
        p = Paths()
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = p._get_base_path()
        assert result == Path.home() / "AppData" / "Local" / "Orinks" / "AccessiWeather"

    def test_macos(self):
        p = Paths()
        with patch.object(sys, "platform", "darwin"):
            result = p._get_base_path()
        assert result == Path.home() / "Library" / "Application Support" / "AccessiWeather"

    def test_linux_with_xdg(self, tmp_path):
        p = Paths()
        with (
            patch.object(sys, "platform", "linux"),
            patch.dict("os.environ", {"XDG_DATA_HOME": str(tmp_path)}),
        ):
            result = p._get_base_path()
        assert result == tmp_path / "accessiweather"

    def test_linux_without_xdg(self):
        p = Paths()
        with (
            patch.object(sys, "platform", "linux"),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = p._get_base_path()
        assert result == Path.home() / ".local" / "share" / "accessiweather"

    def test_caches_base_path(self, tmp_path):
        """Base path is computed once and cached."""
        p = Paths()
        with (
            patch.object(sys, "platform", "linux"),
            patch.dict("os.environ", {"XDG_DATA_HOME": str(tmp_path)}),
        ):
            first = p._get_base_path()
            second = p._get_base_path()
        assert first is second


class TestPropertyPaths:
    """Test the data/config/cache/logs properties."""

    def test_data_creates_directory(self, tmp_path):
        p = Paths()
        p._base_path = tmp_path
        data = p.data
        assert data == tmp_path / "Data"
        assert data.is_dir()

    def test_config_creates_directory(self, tmp_path):
        p = Paths()
        p._base_path = tmp_path
        config = p.config
        assert config == tmp_path / "Config"
        assert config.is_dir()

    def test_cache_creates_directory(self, tmp_path):
        p = Paths()
        p._base_path = tmp_path
        cache = p.cache
        assert cache == tmp_path / "Cache"
        assert cache.is_dir()

    def test_logs_creates_directory(self, tmp_path):
        p = Paths()
        p._base_path = tmp_path
        logs = p.logs
        assert logs == tmp_path / "Logs"
        assert logs.is_dir()


class TestAppPath:
    """Test the app property."""

    def test_app_not_frozen(self):
        p = Paths()
        # When not frozen, should return the parent of paths.py
        result = p.app
        assert isinstance(result, Path)
        assert result.is_dir()

    def test_app_frozen(self):
        p = Paths()
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", "/usr/bin/myapp"),
        ):
            result = p.app
        assert result == Path("/usr/bin")
