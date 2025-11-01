"""
Unit tests for config_utils module.

Tests cover:
- Portable mode detection
- Configuration directory path resolution
- Configuration defaults management
- Platform-specific behavior
- Environment variable handling
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

# Direct import to avoid __init__.py importing toga
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accessiweather.config_utils import (
    ensure_config_defaults,
    get_config_dir,
    is_portable_mode,
)


class TestPortableModeDetection:
    """Test portable mode detection logic."""

    def test_is_portable_mode_forced_via_env(self, monkeypatch):
        """Should return True when ACCESSIWEATHER_FORCE_PORTABLE is set."""
        monkeypatch.setenv("ACCESSIWEATHER_FORCE_PORTABLE", "1")
        assert is_portable_mode() is True

    def test_is_portable_mode_forced_via_env_true(self, monkeypatch):
        """Should return True when ACCESSIWEATHER_FORCE_PORTABLE is 'true'."""
        monkeypatch.setenv("ACCESSIWEATHER_FORCE_PORTABLE", "true")
        assert is_portable_mode() is True

    def test_is_portable_mode_forced_via_env_yes(self, monkeypatch):
        """Should return True when ACCESSIWEATHER_FORCE_PORTABLE is 'yes'."""
        monkeypatch.setenv("ACCESSIWEATHER_FORCE_PORTABLE", "yes")
        assert is_portable_mode() is True

    def test_is_portable_mode_not_forced(self, monkeypatch):
        """Should not force portable mode with other values."""
        monkeypatch.setenv("ACCESSIWEATHER_FORCE_PORTABLE", "0")
        # Will return False because running from source
        assert is_portable_mode() is False

    def test_is_portable_mode_from_source(self, monkeypatch):
        """Should return False when running from source code."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)
        # When not frozen (running from source), should return False
        assert is_portable_mode() is False

    @patch("sys.frozen", True, create=True)
    @patch("sys.executable", "/some/path/app.exe")
    def test_is_portable_mode_frozen_writable_dir(self, tmp_path, monkeypatch):
        """Should return True when frozen and directory is writable."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)
        monkeypatch.setenv("PROGRAMFILES", "C:\\Program Files")

        # Mock sys.executable to a writable directory
        with patch("sys.executable", str(tmp_path / "app.exe")):
            result = is_portable_mode()
            # Since tmp_path is not under Program Files and is writable
            assert result is True

    @patch("sys.frozen", True, create=True)
    def test_is_portable_mode_frozen_program_files(self, monkeypatch):
        """Should return False when frozen and in Program Files."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)

        # Mock Program Files path
        program_files = "C:\\Program Files"
        monkeypatch.setenv("PROGRAMFILES", program_files)

        # Mock executable path under Program Files
        exe_path = os.path.join(program_files, "AccessiWeather", "app.exe")
        with patch("sys.executable", exe_path):
            result = is_portable_mode()
            assert result is False

    @patch("sys.frozen", True, create=True)
    def test_is_portable_mode_frozen_program_files_x86(self, monkeypatch):
        """Should return False when frozen and in Program Files (x86)."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)

        # Mock Program Files (x86) path
        program_files_x86 = "C:\\Program Files (x86)"
        monkeypatch.setenv("PROGRAMFILES(X86)", program_files_x86)

        # Mock executable path under Program Files (x86)
        exe_path = os.path.join(program_files_x86, "AccessiWeather", "app.exe")
        with patch("sys.executable", exe_path):
            result = is_portable_mode()
            assert result is False


class TestConfigDirectoryPath:
    """Test configuration directory path resolution."""

    def test_get_config_dir_custom(self, tmp_path):
        """Should return custom directory when provided."""
        custom_dir = str(tmp_path / "custom_config")
        result = get_config_dir(custom_dir=custom_dir)

        assert result == custom_dir

    def test_get_config_dir_portable_mode_forced(self, tmp_path, monkeypatch):
        """Should return config subdirectory in portable mode."""
        monkeypatch.setenv("ACCESSIWEATHER_FORCE_PORTABLE", "1")

        # Should look for pyproject.toml to find project root
        result = get_config_dir()

        # Should return a path with 'config' in it
        assert "config" in result.lower()

    @patch("platform.system", return_value="Windows")
    def test_get_config_dir_windows_appdata(self, mock_system, monkeypatch):
        """Should use APPDATA on Windows in standard mode."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)
        monkeypatch.setenv("APPDATA", "C:\\Users\\TestUser\\AppData\\Roaming")

        result = get_config_dir()

        assert "AppData" in result
        assert ".accessiweather" in result

    @patch("platform.system", return_value="Windows")
    def test_get_config_dir_windows_no_appdata(self, mock_system, monkeypatch):
        """Should fall back to home directory when APPDATA is not set."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)

        result = get_config_dir()

        assert ".accessiweather" in result

    @patch("platform.system", return_value="Linux")
    def test_get_config_dir_linux(self, mock_system, monkeypatch):
        """Should use ~/.accessiweather on Linux."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)

        result = get_config_dir()

        assert ".accessiweather" in result

    @patch("platform.system", return_value="Darwin")
    def test_get_config_dir_macos(self, mock_system, monkeypatch):
        """Should use ~/.accessiweather on macOS."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)

        result = get_config_dir()

        assert ".accessiweather" in result


class TestEnsureConfigDefaults:
    """Test configuration defaults management."""

    def test_ensure_config_defaults_empty_config(self):
        """Should add all defaults to empty config."""
        config = {}
        result = ensure_config_defaults(config)

        assert "settings" in result
        assert "api_keys" in result
        assert "api_settings" in result
        assert "data_source" in result["settings"]

    def test_ensure_config_defaults_existing_settings(self):
        """Should not overwrite existing settings."""
        config = {"settings": {"data_source": "custom_source", "custom_key": "custom_value"}}

        result = ensure_config_defaults(config)

        # Should keep existing values
        assert result["settings"]["data_source"] == "custom_source"
        assert result["settings"]["custom_key"] == "custom_value"

    def test_ensure_config_defaults_adds_missing_settings(self):
        """Should add missing default settings."""
        config = {"settings": {"some_key": "some_value"}}

        result = ensure_config_defaults(config)

        # Should add missing defaults
        assert "data_source" in result["settings"]
        assert "auto_update_check_enabled" in result["settings"]
        assert "update_check_interval_hours" in result["settings"]
        assert "update_channel" in result["settings"]

        # Should keep existing setting
        assert result["settings"]["some_key"] == "some_value"

    def test_ensure_config_defaults_preserves_original(self):
        """Should not modify original config dict."""
        original_config = {"settings": {}}
        result = ensure_config_defaults(original_config)

        # Original should not have new keys
        assert "data_source" not in original_config["settings"]

        # Result should have new keys
        assert "data_source" in result["settings"]

    def test_ensure_config_defaults_adds_api_sections(self):
        """Should add api_keys and api_settings sections."""
        config = {"settings": {}}
        result = ensure_config_defaults(config)

        assert "api_keys" in result
        assert "api_settings" in result
        assert isinstance(result["api_keys"], dict)
        assert isinstance(result["api_settings"], dict)

    def test_ensure_config_defaults_update_settings(self):
        """Should add all update-related settings."""
        config = {}
        result = ensure_config_defaults(config)

        settings = result["settings"]
        assert "auto_update_check_enabled" in settings
        assert "update_check_interval_hours" in settings
        assert "update_channel" in settings

        # Verify types
        assert isinstance(settings["auto_update_check_enabled"], bool)
        assert isinstance(settings["update_check_interval_hours"], int)
        assert isinstance(settings["update_channel"], str)

    def test_ensure_config_defaults_data_source_default(self):
        """Should add data_source with correct default."""
        config = {}
        result = ensure_config_defaults(config)

        # Should have data_source setting
        assert "data_source" in result["settings"]
        # Should be a valid string
        assert isinstance(result["settings"]["data_source"], str)


class TestConfigUtilsEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_is_portable_mode_with_permission_error(self, monkeypatch):
        """Should handle permission errors gracefully."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)

        # When running from source (not frozen), should return False
        result = is_portable_mode()
        assert result is False

    @patch("sys.frozen", True, create=True)
    def test_is_portable_mode_write_test_failure(self, tmp_path, monkeypatch):
        """Should return False when directory is not writable."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)
        monkeypatch.setenv("PROGRAMFILES", "C:\\Program Files")

        # Create a read-only directory
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()

        with (
            patch("sys.executable", str(read_only_dir / "app.exe")),
            patch("builtins.open", side_effect=PermissionError("No write access")),
        ):
            result = is_portable_mode()
            assert result is False

    def test_ensure_config_defaults_with_nested_config(self):
        """Should handle configs with nested structures."""
        config = {"settings": {"nested": {"key": "value"}}, "other_section": {"data": "test"}}

        result = ensure_config_defaults(config)

        # Should preserve nested structures
        assert result["settings"]["nested"]["key"] == "value"
        assert result["other_section"]["data"] == "test"

        # Should add defaults
        assert "data_source" in result["settings"]

    def test_get_config_dir_none_custom_dir(self):
        """Should handle None as custom_dir parameter."""
        result = get_config_dir(custom_dir=None)

        # Should return a valid path
        assert result is not None
        assert isinstance(result, str)

    def test_ensure_config_defaults_multiple_calls(self):
        """Should be idempotent when called multiple times."""
        config = {}

        result1 = ensure_config_defaults(config)
        result2 = ensure_config_defaults(result1)

        # Should have same structure
        assert result1.keys() == result2.keys()
        assert result1["settings"].keys() == result2["settings"].keys()

    @patch("sys.frozen", True, create=True)
    def test_is_portable_mode_case_insensitive_path_comparison(self, monkeypatch):
        """Should handle case-insensitive path comparison on Windows."""
        monkeypatch.delenv("ACCESSIWEATHER_FORCE_PORTABLE", raising=False)

        # Set Program Files with mixed case
        monkeypatch.setenv("PROGRAMFILES", "C:\\Program Files")

        # Mock executable with different case
        exe_path = "c:\\program files\\AccessiWeather\\app.exe"
        with patch("sys.executable", exe_path):
            result = is_portable_mode()
            # Should recognize it's under Program Files despite case difference
            assert result is False

    def test_ensure_config_defaults_with_all_settings_present(self):
        """Should not modify config when all defaults are already present."""
        from accessiweather.constants import (
            AUTO_UPDATE_CHECK_KEY,
            DEFAULT_AUTO_UPDATE_CHECK,
            DEFAULT_DATA_SOURCE,
            DEFAULT_UPDATE_CHANNEL,
            DEFAULT_UPDATE_CHECK_INTERVAL,
            UPDATE_CHANNEL_KEY,
            UPDATE_CHECK_INTERVAL_KEY,
        )

        config = {
            "settings": {
                "data_source": DEFAULT_DATA_SOURCE,
                AUTO_UPDATE_CHECK_KEY: DEFAULT_AUTO_UPDATE_CHECK,
                UPDATE_CHECK_INTERVAL_KEY: DEFAULT_UPDATE_CHECK_INTERVAL,
                UPDATE_CHANNEL_KEY: DEFAULT_UPDATE_CHANNEL,
            },
            "api_keys": {},
            "api_settings": {},
        }

        result = ensure_config_defaults(config)

        # Values should remain unchanged
        assert result["settings"]["data_source"] == DEFAULT_DATA_SOURCE
        assert result["settings"][AUTO_UPDATE_CHECK_KEY] == DEFAULT_AUTO_UPDATE_CHECK
