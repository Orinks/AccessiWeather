"""Tests for configuration utilities."""

import os
import sys
from unittest.mock import mock_open, patch

import pytest

from accessiweather.config_utils import ensure_config_defaults, get_config_dir, is_portable_mode

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


def test_is_portable_mode_substring_false_positive():
    """Test that is_portable_mode correctly handles paths containing 'Program Files' as substring."""
    # This tests the fix for the bug where substring matching would incorrectly
    # identify portable apps as standard installations
    with patch.multiple(
        sys, frozen=True, executable=r"D:\My Program Files App\AccessiWeather\app.exe", create=True
    ):
        with patch.dict(
            os.environ,
            {"PROGRAMFILES": r"C:\Program Files", "PROGRAMFILES(X86)": r"C:\Program Files (x86)"},
        ):
            with patch("builtins.open", mock_open()) as mock_file:
                with patch("os.remove") as mock_remove:
                    # Should return True because it's not actually in Program Files
                    assert is_portable_mode() is True
                    mock_file.assert_called_once()
                    mock_remove.assert_called_once()


def test_is_portable_mode_exact_program_files_match():
    """Test that is_portable_mode correctly identifies when app is exactly in Program Files root."""
    with patch.multiple(sys, frozen=True, executable=r"C:\Program Files\app.exe", create=True):
        with patch.dict(
            os.environ,
            {"PROGRAMFILES": r"C:\Program Files", "PROGRAMFILES(X86)": r"C:\Program Files (x86)"},
        ):
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


# --- Tests for ensure_config_defaults ---


@pytest.mark.unit
def test_ensure_config_defaults_empty_config():
    """Test ensure_config_defaults with empty config."""
    config: dict = {}

    with patch("accessiweather.gui.settings_dialog.DEFAULT_DATA_SOURCE", "auto"):
        result = ensure_config_defaults(config)

    expected = {
        "settings": {
            "data_source": "auto",
            "auto_update_check_enabled": True,
            "update_check_interval_hours": 24,
            "update_channel": "stable",
        },
        "api_keys": {},
        "api_settings": {},
    }
    assert result == expected
    # Ensure original config is not modified
    assert config == {}


@pytest.mark.unit
def test_ensure_config_defaults_existing_settings():
    """Test ensure_config_defaults with existing settings."""
    config = {"settings": {"update_interval": 10, "data_source": "openmeteo"}}

    result = ensure_config_defaults(config)

    expected = {
        "settings": {
            "update_interval": 10,
            "data_source": "openmeteo",
            "auto_update_check_enabled": True,
            "update_check_interval_hours": 24,
            "update_channel": "stable",
        },
        "api_keys": {},
        "api_settings": {},
    }
    assert result == expected


@pytest.mark.unit
def test_ensure_config_defaults_missing_data_source():
    """Test ensure_config_defaults adds missing data_source."""
    config = {"settings": {"update_interval": 10}}

    with patch("accessiweather.gui.settings_dialog.DEFAULT_DATA_SOURCE", "auto"):
        result = ensure_config_defaults(config)

    expected = {
        "settings": {
            "update_interval": 10,
            "data_source": "auto",
            "auto_update_check_enabled": True,
            "update_check_interval_hours": 24,
            "update_channel": "stable",
        },
        "api_keys": {},
        "api_settings": {},
    }
    assert result == expected


@pytest.mark.unit
def test_ensure_config_defaults_existing_api_keys():
    """Test ensure_config_defaults preserves existing api_keys."""
    config = {"settings": {"data_source": "weatherapi"}, "api_keys": {"weatherapi": "test_key"}}

    result = ensure_config_defaults(config)

    expected = {
        "settings": {
            "data_source": "weatherapi",
            "auto_update_check_enabled": True,
            "update_check_interval_hours": 24,
            "update_channel": "stable",
        },
        "api_keys": {"weatherapi": "test_key"},
        "api_settings": {},
    }
    assert result == expected


@pytest.mark.unit
def test_ensure_config_defaults_no_settings_section():
    """Test ensure_config_defaults creates settings section when missing."""
    config = {"other_section": {"some_key": "some_value"}}

    with patch("accessiweather.gui.settings_dialog.DEFAULT_DATA_SOURCE", "auto"):
        result = ensure_config_defaults(config)

    expected = {
        "other_section": {"some_key": "some_value"},
        "settings": {
            "data_source": "auto",
            "auto_update_check_enabled": True,
            "update_check_interval_hours": 24,
            "update_channel": "stable",
        },
        "api_keys": {},
        "api_settings": {},
    }
    assert result == expected
