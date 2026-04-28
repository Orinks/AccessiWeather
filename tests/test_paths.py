"""Tests for the cross-platform Paths helper."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

from accessiweather.paths import (
    Paths,
    RuntimeStoragePaths,
    detect_portable_mode,
    resolve_default_config_root,
    resolve_default_runtime_storage,
    resolve_runtime_storage,
)
from accessiweather.runtime_env import is_compiled_runtime


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

    def test_windows_without_localappdata(self, tmp_path):
        p = Paths()
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict("os.environ", {}, clear=True),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = p._get_base_path()
        assert result == tmp_path / "AppData" / "Local" / "Orinks" / "AccessiWeather"

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

    def test_linux_without_xdg(self, tmp_path):
        p = Paths()
        with (
            patch.object(sys, "platform", "linux"),
            patch.dict("os.environ", {}, clear=True),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = p._get_base_path()
        assert result == tmp_path / ".local" / "share" / "accessiweather"

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


class TestPortableFrozenBasePath:
    """Test frozen portable-marker and force override branches."""

    def test_frozen_with_force_portable_uses_exe_dir(self, tmp_path):
        exe = tmp_path / "AccessiWeather.exe"
        exe.write_text("x")
        p = Paths()
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", str(exe)),
            patch.dict("os.environ", {"ACCESSIWEATHER_FORCE_PORTABLE": "1"}, clear=False),
            patch.object(sys, "platform", "win32"),
        ):
            result = p._get_base_path()
        assert result == tmp_path


class TestPortableDetection:
    """Test the canonical portable-mode detection helper."""

    def test_not_frozen_returns_false(self):
        with (
            patch.object(sys, "frozen", False, create=True),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("ACCESSIWEATHER_FORCE_PORTABLE", None)
            assert detect_portable_mode() is False

    def test_force_portable_env_var(self):
        with patch.dict(os.environ, {"ACCESSIWEATHER_FORCE_PORTABLE": "1"}):
            assert detect_portable_mode() is True

    def test_nuitka_compiled_runtime_detects_portable_marker(self, tmp_path):
        exe_path = str(tmp_path / "app.exe")
        (tmp_path / ".portable").write_text("1")
        main_module = sys.modules["__main__"]
        original_compiled = getattr(main_module, "__compiled__", None)

        try:
            if hasattr(main_module, "__compiled__"):
                delattr(main_module, "__compiled__")
            main_module.__compiled__ = True
            with (
                patch.object(sys, "frozen", False, create=True),
                patch.object(sys, "executable", exe_path),
                patch.dict(os.environ, {"ACCESSIWEATHER_FORCE_PORTABLE": ""}, clear=False),
            ):
                assert is_compiled_runtime() is True
                assert detect_portable_mode() is True
        finally:
            if original_compiled is None:
                delattr(main_module, "__compiled__")
            else:
                main_module.__compiled__ = original_compiled

    def test_frozen_portable_marker_file_is_portable(self, tmp_path):
        exe_path = str(tmp_path / "app.exe")
        (tmp_path / ".portable").write_text("1")

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", exe_path),
            patch.dict(os.environ, {"ACCESSIWEATHER_FORCE_PORTABLE": ""}, clear=False),
        ):
            assert detect_portable_mode() is True

    def test_frozen_config_dir_marker_is_portable(self, tmp_path):
        exe_path = str(tmp_path / "app.exe")
        (tmp_path / "config").mkdir()

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", exe_path),
            patch.dict(os.environ, {"ACCESSIWEATHER_FORCE_PORTABLE": ""}, clear=False),
        ):
            assert detect_portable_mode() is True


class TestRuntimeStorageResolution:
    """Test canonical runtime storage resolution."""

    def test_runtime_paths_expose_noaa_radio_availability_file(self, tmp_path):
        runtime = RuntimeStoragePaths(config_root=tmp_path)

        assert runtime.noaa_radio_availability_file == tmp_path / "noaa_radio_availability.json"

    def test_default_layout_uses_app_config_root(self, tmp_path):
        paths = Paths()
        paths._base_path = tmp_path

        runtime = resolve_runtime_storage(paths)

        assert runtime == RuntimeStoragePaths(config_root=tmp_path / "Config")
        assert runtime.config_file == tmp_path / "Config" / "accessiweather.json"
        assert runtime.runtime_state_file == tmp_path / "Config" / "state" / "runtime_state.json"
        assert runtime.cache_dir == tmp_path / "Config" / "weather_cache"
        assert runtime.noaa_radio_preferences_file == tmp_path / "Config" / "noaa_radio_prefs.json"
        assert runtime.lock_file == tmp_path / "Config" / "state" / "accessiweather.lock"

    def test_custom_config_dir_wins(self, tmp_path):
        paths = Paths()
        custom = tmp_path / "custom-root"

        runtime = resolve_runtime_storage(paths, config_dir=custom)

        assert runtime.config_root == custom
        assert runtime.custom_config_dir is True
        assert runtime.portable_mode is False

    def test_portable_layout_uses_cwd_config_when_not_frozen(self, tmp_path):
        paths = Paths()

        with patch("accessiweather.paths.Path.cwd", return_value=tmp_path):
            runtime = resolve_runtime_storage(paths, portable_mode=True)

        assert runtime.config_root == tmp_path / "config"
        assert runtime.portable_mode is True

    def test_frozen_with_portable_marker_uses_exe_dir(self, tmp_path):
        exe = tmp_path / "AccessiWeather.exe"
        exe.write_text("x")
        (tmp_path / ".portable").write_text("1")

        p = Paths()
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", str(exe)),
            patch.dict("os.environ", {}, clear=True),
            patch.object(sys, "platform", "win32"),
        ):
            result = p._get_base_path()
        assert result == tmp_path

    def test_resolve_default_runtime_storage_uses_normalized_linux_config_root(self, tmp_path):
        with (
            patch.object(sys, "platform", "linux"),
            patch.dict("os.environ", {"XDG_DATA_HOME": str(tmp_path)}),
        ):
            runtime = resolve_default_runtime_storage()

        assert runtime.config_root == tmp_path / "accessiweather" / "Config"

    def test_resolve_default_config_root_uses_normalized_windows_config_root(self, tmp_path):
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}),
        ):
            config_root = resolve_default_config_root()

        assert config_root == tmp_path / "Orinks" / "AccessiWeather" / "Config"

    def test_frozen_with_config_dir_marker_uses_exe_dir(self, tmp_path):
        exe = tmp_path / "AccessiWeather.exe"
        exe.write_text("x")
        (tmp_path / "config").mkdir()

        p = Paths()
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", str(exe)),
            patch.dict("os.environ", {}, clear=True),
            patch.object(sys, "platform", "win32"),
        ):
            result = p._get_base_path()
        assert result == tmp_path
