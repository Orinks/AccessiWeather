"""Tests for configuration utilities."""

import os
import sys
from unittest.mock import mock_open, patch

from accessiweather.config_utils import get_config_dir, is_portable_mode

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
