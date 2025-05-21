"""Tests for configuration utilities."""

import os
import sys
from unittest.mock import mock_open, patch

from accessiweather.config_utils import get_config_dir, is_portable_mode, migrate_config
from accessiweather.gui.settings_dialog import (
    API_KEYS_SECTION,
    DATA_SOURCE_KEY,
    DEFAULT_DATA_SOURCE,
    WEATHERAPI_KEY,
)

# --- Tests for is_portable_mode ---


def test_is_portable_mode_not_frozen():
    """Test that is_portable_mode returns False when not frozen."""
    with patch("sys.frozen", False, create=True):
        assert is_portable_mode() is False


def test_is_portable_mode_in_program_files():
    """Test that is_portable_mode returns False when in Program Files."""
    with patch.multiple(sys, frozen=True, executable=r"C:\Program Files\App\app.exe", create=True):
        with patch.dict(os.environ, {"PROGRAMFILES": "Program Files"}):
            assert is_portable_mode() is False


def test_is_portable_mode_in_program_files_x86():
    """Test that is_portable_mode returns False when in Program Files (x86)."""
    with patch.multiple(
        sys, frozen=True, executable=r"C:\Program Files (x86)\App\app.exe", create=True
    ):
        with patch.dict(os.environ, {"PROGRAMFILES(X86)": "Program Files (x86)"}):
            assert is_portable_mode() is False


def test_is_portable_mode_writable():
    """Test that is_portable_mode returns True when directory is writable."""
    with patch.multiple(sys, frozen=True, executable=r"D:\Portable\App\app.exe", create=True):
        with patch.dict(
            os.environ,
            {"PROGRAMFILES": "Program Files", "PROGRAMFILES(X86)": "Program Files (x86)"},
        ):
            with patch("builtins.open", mock_open()) as mock_file:
                with patch("os.remove") as mock_remove:
                    assert is_portable_mode() is True
                    mock_file.assert_called_once()
                    mock_remove.assert_called_once()


def test_is_portable_mode_not_writable():
    """Test that is_portable_mode returns False when directory is not writable."""
    with patch.multiple(sys, frozen=True, executable=r"D:\Portable\App\app.exe", create=True):
        with patch.dict(
            os.environ,
            {"PROGRAMFILES": "Program Files", "PROGRAMFILES(X86)": "Program Files (x86)"},
        ):
            with patch("builtins.open", side_effect=PermissionError):
                assert is_portable_mode() is False


# --- Tests for get_config_dir ---


def test_get_config_dir_custom():
    """Test that get_config_dir returns custom_dir when provided."""
    custom_dir = "/path/to/config"
    assert get_config_dir(custom_dir) == custom_dir


def test_get_config_dir_portable():
    """Test that get_config_dir returns portable config path when in portable mode."""
    with patch("accessiweather.config_utils.is_portable_mode", return_value=True):
        with patch.multiple(sys, frozen=True, executable=r"D:\Portable\App\app.exe", create=True):
            expected = os.path.join(os.path.dirname(sys.executable), "config")
            assert get_config_dir() == expected


def test_get_config_dir_windows():
    """Test that get_config_dir returns APPDATA path on Windows."""
    with patch("accessiweather.config_utils.is_portable_mode", return_value=False):
        with patch("platform.system", return_value="Windows"):
            with patch.dict(os.environ, {"APPDATA": r"C:\Users\Test\AppData\Roaming"}):
                expected = r"C:\Users\Test\AppData\Roaming\.accessiweather"
                assert get_config_dir() == expected


def test_get_config_dir_non_windows():
    """Test that get_config_dir returns ~/.accessiweather on non-Windows platforms."""
    with patch("accessiweather.config_utils.is_portable_mode", return_value=False):
        with patch("platform.system", return_value="Linux"):
            with patch("os.path.expanduser") as mock_expanduser:
                mock_expanduser.return_value = "/home/user/.accessiweather"
                assert get_config_dir() == "/home/user/.accessiweather"
                mock_expanduser.assert_called_once_with("~/.accessiweather")


def test_get_config_dir_windows_no_appdata():
    """Test that get_config_dir falls back to ~/.accessiweather when APPDATA is not set."""
    with patch("accessiweather.config_utils.is_portable_mode", return_value=False):
        with patch("platform.system", return_value="Windows"):
            with patch.dict(os.environ, clear=True):  # Remove all env vars
                with patch("os.path.expanduser") as mock_expanduser:
                    mock_expanduser.return_value = r"C:\Users\Test\.accessiweather"
                    assert get_config_dir() == r"C:\Users\Test\.accessiweather"
                    mock_expanduser.assert_called_once_with("~/.accessiweather")


# --- Tests for migrate_config ---


def test_migrate_config_adds_weatherapi_fields():
    """Test that migrate_config adds WeatherAPI fields to the configuration."""
    # Create a config without WeatherAPI fields
    config = {
        "settings": {
            "update_interval_minutes": 10,
            "alert_radius_miles": 25,
            "precise_location_alerts": True,
        },
        "api_settings": {"api_contact": "test@example.com"},
    }

    # Migrate the config
    migrated = migrate_config(config)

    # Check that WeatherAPI fields were added
    assert DATA_SOURCE_KEY in migrated["settings"]
    assert migrated["settings"][DATA_SOURCE_KEY] == DEFAULT_DATA_SOURCE
    assert API_KEYS_SECTION in migrated
    assert WEATHERAPI_KEY in migrated[API_KEYS_SECTION]
    assert migrated[API_KEYS_SECTION][WEATHERAPI_KEY] == ""


def test_migrate_config_preserves_existing_values():
    """Test that migrate_config preserves existing WeatherAPI values."""
    # Create a config with existing WeatherAPI fields
    config = {
        "settings": {
            "update_interval_minutes": 10,
            "alert_radius_miles": 25,
            "precise_location_alerts": True,
            DATA_SOURCE_KEY: "weatherapi",
        },
        "api_settings": {"api_contact": "test@example.com"},
        API_KEYS_SECTION: {WEATHERAPI_KEY: "existing-api-key"},
    }

    # Migrate the config
    migrated = migrate_config(config)

    # Check that existing values were preserved
    assert migrated["settings"][DATA_SOURCE_KEY] == "weatherapi"
    assert migrated[API_KEYS_SECTION][WEATHERAPI_KEY] == "existing-api-key"


def test_migrate_config_removes_obsolete_settings():
    """Test that migrate_config removes obsolete settings."""
    # Create a config with obsolete alert_update_interval
    config = {
        "settings": {
            "update_interval_minutes": 10,
            "alert_radius_miles": 25,
            "precise_location_alerts": True,
            "alert_update_interval": 15,  # Obsolete setting
        },
        "api_settings": {"api_contact": "test@example.com"},
    }

    # Migrate the config
    migrated = migrate_config(config)

    # Check that obsolete setting was removed
    assert "alert_update_interval" not in migrated["settings"]
