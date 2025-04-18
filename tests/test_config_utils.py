"""Tests for configuration utilities"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import pytest

from accessiweather.config_utils import get_config_dir, is_portable_mode


class TestConfigUtils:
    """Test suite for configuration utilities"""

    def test_get_config_dir_custom(self):
        """Test get_config_dir with custom directory"""
        custom_dir = "/custom/dir"
        result = get_config_dir(custom_dir)
        assert result == custom_dir

    @patch("accessiweather.config_utils.is_portable_mode")
    @patch("accessiweather.config_utils.platform.system")
    @patch("accessiweather.config_utils.os.environ.get")
    def test_get_config_dir_windows(self, mock_environ_get, mock_system, mock_is_portable):
        """Test get_config_dir on Windows"""
        # Set up mocks
        mock_is_portable.return_value = False
        mock_system.return_value = "Windows"
        mock_environ_get.return_value = "C:\\Users\\Test\\AppData\\Roaming"

        # Call function
        result = get_config_dir()

        # Verify result
        assert result == "C:\\Users\\Test\\AppData\\Roaming\\.accessiweather"
        mock_environ_get.assert_called_once_with("APPDATA")

    @patch("accessiweather.config_utils.is_portable_mode")
    @patch("accessiweather.config_utils.platform.system")
    @patch("accessiweather.config_utils.os.path.expanduser")
    def test_get_config_dir_non_windows(self, mock_expanduser, mock_system, mock_is_portable):
        """Test get_config_dir on non-Windows platforms"""
        # Set up mocks
        mock_is_portable.return_value = False
        mock_system.return_value = "Linux"
        mock_expanduser.return_value = "/home/test/.accessiweather"

        # Call function
        result = get_config_dir()

        # Verify result
        assert result == "/home/test/.accessiweather"
        mock_expanduser.assert_called_once_with("~/.accessiweather")

    @patch("accessiweather.config_utils.is_portable_mode")
    @patch("accessiweather.config_utils.sys.frozen", True, create=True)
    @patch("accessiweather.config_utils.sys.executable", "C:\\portable\\AccessiWeather.exe")
    def test_get_config_dir_portable(self, mock_is_portable):
        """Test get_config_dir in portable mode"""
        # Set up mocks
        mock_is_portable.return_value = True

        # Call function with patched sys.executable
        with patch("accessiweather.config_utils.os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "C:\\portable"
            result = get_config_dir()

        # Verify result
        assert result == "C:\\portable\\config"

    @patch("accessiweather.config_utils.getattr")
    def test_is_portable_mode_source_code(self, mock_getattr):
        """Test is_portable_mode when running from source code"""
        # Set up mock to indicate we're running from source
        mock_getattr.return_value = False

        # Call function
        result = is_portable_mode()

        # Verify result
        assert result is False
        mock_getattr.assert_called_once_with(sys, 'frozen', False)

    @patch("accessiweather.config_utils.getattr")
    @patch("accessiweather.config_utils.os.path.dirname")
    @patch("accessiweather.config_utils.os.environ.get")
    def test_is_portable_mode_program_files(self, mock_environ_get, mock_dirname, mock_getattr):
        """Test is_portable_mode when running from Program Files"""
        # Set up mocks
        mock_getattr.return_value = True  # Running as frozen executable
        mock_dirname.return_value = "C:\\Program Files\\AccessiWeather"
        mock_environ_get.side_effect = lambda key, default: {
            "PROGRAMFILES": "C:\\Program Files",
            "PROGRAMFILES(X86)": "C:\\Program Files (x86)"
        }.get(key, default)

        # Call function
        result = is_portable_mode()

        # Verify result
        assert result is False

    @patch("accessiweather.config_utils.getattr")
    @patch("accessiweather.config_utils.os.path.dirname")
    @patch("accessiweather.config_utils.os.environ.get")
    @patch("accessiweather.config_utils.os.path.join")
    @patch("builtins.open")
    @patch("accessiweather.config_utils.os.remove")
    def test_is_portable_mode_writable(
        self, mock_remove, mock_open, mock_join, mock_environ_get, mock_dirname, mock_getattr
    ):
        """Test is_portable_mode when directory is writable"""
        # Set up mocks
        mock_getattr.return_value = True  # Running as frozen executable
        mock_dirname.return_value = "C:\\portable"
        mock_environ_get.side_effect = lambda key, default: {
            "PROGRAMFILES": "C:\\Program Files",
            "PROGRAMFILES(X86)": "C:\\Program Files (x86)"
        }.get(key, default)
        mock_join.return_value = "C:\\portable\\.write_test"
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Call function
        result = is_portable_mode()

        # Verify result
        assert result is True
        mock_file.write.assert_called_once_with("test")
        mock_remove.assert_called_once_with("C:\\portable\\.write_test")

    @patch("accessiweather.config_utils.getattr")
    @patch("accessiweather.config_utils.os.path.dirname")
    @patch("accessiweather.config_utils.os.environ.get")
    @patch("accessiweather.config_utils.os.path.join")
    @patch("builtins.open")
    def test_is_portable_mode_not_writable(
        self, mock_open, mock_join, mock_environ_get, mock_dirname, mock_getattr
    ):
        """Test is_portable_mode when directory is not writable"""
        # Set up mocks
        mock_getattr.return_value = True  # Running as frozen executable
        mock_dirname.return_value = "C:\\portable"
        mock_environ_get.side_effect = lambda key, default: {
            "PROGRAMFILES": "C:\\Program Files",
            "PROGRAMFILES(X86)": "C:\\Program Files (x86)"
        }.get(key, default)
        mock_join.return_value = "C:\\portable\\.write_test"
        mock_open.side_effect = PermissionError("Permission denied")

        # Call function
        result = is_portable_mode()

        # Verify result
        assert result is False
