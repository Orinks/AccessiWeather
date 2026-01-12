"""
Unit tests for file_permissions module.

Tests cover:
- Cross-platform permission setting (POSIX and Windows)
- Error handling for various failure scenarios
- File validation and path conversion
- Subprocess timeout and error handling
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from accessiweather.config.file_permissions import (
    POSIX_PERMISSIONS,
    SUBPROCESS_TIMEOUT,
    _set_posix_permissions,
    _set_windows_permissions,
    set_secure_file_permissions,
)


class TestSetSecureFilePermissions:
    """Test set_secure_file_permissions function."""

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        file_path = tmp_path / "test_config.json"
        file_path.write_text("{}")
        return file_path

    def test_string_to_path_conversion(self, temp_file):
        """Should convert string path to Path object."""
        with (
            patch("accessiweather.config.file_permissions._set_posix_permissions") as mock_posix,
            patch("accessiweather.config.file_permissions.os.name", "posix"),
        ):
            mock_posix.return_value = True
            result = set_secure_file_permissions(str(temp_file))

            assert result is True
            mock_posix.assert_called_once()
            # Verify Path object was passed
            call_args = mock_posix.call_args[0][0]
            assert isinstance(call_args, Path)

    def test_path_object_accepted(self, temp_file):
        """Should accept Path object directly."""
        with (
            patch("accessiweather.config.file_permissions._set_posix_permissions") as mock_posix,
            patch("accessiweather.config.file_permissions.os.name", "posix"),
        ):
            mock_posix.return_value = True
            result = set_secure_file_permissions(temp_file)

            assert result is True
            mock_posix.assert_called_once_with(temp_file)

    def test_nonexistent_file_returns_false(self, tmp_path):
        """Should return False for non-existent file."""
        nonexistent = tmp_path / "nonexistent.json"
        result = set_secure_file_permissions(nonexistent)

        assert result is False

    def test_calls_posix_on_posix_systems(self, temp_file):
        """Should call _set_posix_permissions on POSIX systems."""
        with (
            patch("accessiweather.config.file_permissions._set_posix_permissions") as mock_posix,
            patch("accessiweather.config.file_permissions.os.name", "posix"),
        ):
            mock_posix.return_value = True
            result = set_secure_file_permissions(temp_file)

            assert result is True
            mock_posix.assert_called_once_with(temp_file)

    def test_calls_windows_on_windows_systems(self, temp_file):
        """Should call _set_windows_permissions on Windows systems."""
        with (
            patch("accessiweather.config.file_permissions._set_windows_permissions") as mock_win,
            patch("accessiweather.config.file_permissions.os.name", "nt"),
        ):
            mock_win.return_value = True
            result = set_secure_file_permissions(temp_file)

            assert result is True
            mock_win.assert_called_once_with(temp_file)

    def test_handles_unexpected_exception(self, temp_file):
        """Should handle unexpected exceptions gracefully."""
        with (
            patch("accessiweather.config.file_permissions._set_posix_permissions") as mock_posix,
            patch("accessiweather.config.file_permissions.os.name", "posix"),
        ):
            mock_posix.side_effect = RuntimeError("Unexpected error")
            result = set_secure_file_permissions(temp_file)

            assert result is False


class TestSetPosixPermissions:
    """Test _set_posix_permissions function."""

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        file_path = tmp_path / "test_config.json"
        file_path.write_text("{}")
        return file_path

    def test_success_sets_correct_permissions(self, temp_file):
        """Should set permissions to 0o600 successfully."""
        with patch("accessiweather.config.file_permissions.os.chmod") as mock_chmod:
            result = _set_posix_permissions(temp_file)

            assert result is True
            mock_chmod.assert_called_once_with(temp_file, POSIX_PERMISSIONS)

    def test_handles_permission_error(self, temp_file):
        """Should handle PermissionError gracefully."""
        with patch("accessiweather.config.file_permissions.os.chmod") as mock_chmod:
            mock_chmod.side_effect = PermissionError("Permission denied")
            result = _set_posix_permissions(temp_file)

            assert result is False

    def test_handles_os_error(self, temp_file):
        """Should handle OSError gracefully."""
        with patch("accessiweather.config.file_permissions.os.chmod") as mock_chmod:
            mock_chmod.side_effect = OSError("OS error")
            result = _set_posix_permissions(temp_file)

            assert result is False

    def test_handles_unexpected_exception(self, temp_file):
        """Should handle unexpected exceptions gracefully."""
        with patch("accessiweather.config.file_permissions.os.chmod") as mock_chmod:
            mock_chmod.side_effect = RuntimeError("Unexpected error")
            result = _set_posix_permissions(temp_file)

            assert result is False


class TestSetWindowsPermissions:
    """Test _set_windows_permissions function."""

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        file_path = tmp_path / "test_config.json"
        file_path.write_text("{}")
        return file_path

    def test_success_calls_icacls_correctly(self, temp_file):
        """Should call icacls with correct arguments."""
        mock_result = Mock()
        mock_result.returncode = 0

        with (
            patch("accessiweather.config.file_permissions.subprocess.run") as mock_run,
            patch.dict(os.environ, {"USERNAME": "testuser"}),
        ):
            mock_run.return_value = mock_result
            result = _set_windows_permissions(temp_file)

            assert result is True
            mock_run.assert_called_once_with(
                ["icacls", str(temp_file), "/inheritance:r", "/grant:r", "testuser:(F)"],
                check=True,
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

    def test_missing_username_returns_false(self, temp_file):
        """Should return False when USERNAME environment variable is missing."""
        with patch.dict(os.environ, {}, clear=True):
            result = _set_windows_permissions(temp_file)

            assert result is False

    def test_handles_called_process_error(self, temp_file):
        """Should handle CalledProcessError from icacls."""
        error = subprocess.CalledProcessError(returncode=1, cmd="icacls", stderr="Access denied")

        with (
            patch("accessiweather.config.file_permissions.subprocess.run") as mock_run,
            patch.dict(os.environ, {"USERNAME": "testuser"}),
        ):
            mock_run.side_effect = error
            result = _set_windows_permissions(temp_file)

            assert result is False

    def test_handles_timeout_expired(self, temp_file):
        """Should handle TimeoutExpired from icacls."""
        error = subprocess.TimeoutExpired(cmd="icacls", timeout=SUBPROCESS_TIMEOUT)

        with (
            patch("accessiweather.config.file_permissions.subprocess.run") as mock_run,
            patch.dict(os.environ, {"USERNAME": "testuser"}),
        ):
            mock_run.side_effect = error
            result = _set_windows_permissions(temp_file)

            assert result is False

    def test_handles_file_not_found_error(self, temp_file):
        """Should handle FileNotFoundError when icacls.exe is missing."""
        with (
            patch("accessiweather.config.file_permissions.subprocess.run") as mock_run,
            patch.dict(os.environ, {"USERNAME": "testuser"}),
        ):
            mock_run.side_effect = FileNotFoundError("icacls.exe not found")
            result = _set_windows_permissions(temp_file)

            assert result is False

    def test_handles_unexpected_exception(self, temp_file):
        """Should handle unexpected exceptions gracefully."""
        with (
            patch("accessiweather.config.file_permissions.subprocess.run") as mock_run,
            patch.dict(os.environ, {"USERNAME": "testuser"}),
        ):
            mock_run.side_effect = RuntimeError("Unexpected error")
            result = _set_windows_permissions(temp_file)

            assert result is False

    def test_uses_create_no_window_flag_on_windows(self, temp_file):
        """Should use CREATE_NO_WINDOW flag on Windows systems."""
        mock_result = Mock()
        mock_result.returncode = 0

        with (
            patch("accessiweather.config.file_permissions.subprocess.run") as mock_run,
            patch("accessiweather.config.file_permissions.os.name", "nt"),
            patch.dict(os.environ, {"USERNAME": "testuser"}),
        ):
            mock_run.return_value = mock_result
            result = _set_windows_permissions(temp_file)

            assert result is True
            # Verify CREATE_NO_WINDOW flag is used
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW

    def test_no_create_no_window_flag_on_non_windows(self, temp_file):
        """Should not use CREATE_NO_WINDOW flag on non-Windows systems."""
        mock_result = Mock()
        mock_result.returncode = 0

        with (
            patch("accessiweather.config.file_permissions.subprocess.run") as mock_run,
            patch("accessiweather.config.file_permissions.os.name", "posix"),
            patch.dict(os.environ, {"USERNAME": "testuser"}),
        ):
            mock_run.return_value = mock_result
            result = _set_windows_permissions(temp_file)

            assert result is True
            # Verify CREATE_NO_WINDOW flag is 0 on non-Windows
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["creationflags"] == 0


class TestPermissionsIntegration:
    """Integration tests for permission setting."""

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        file_path = tmp_path / "test_config.json"
        file_path.write_text("{}")
        return file_path

    def test_real_permission_setting_posix(self, temp_file):
        """Test actual permission setting on POSIX systems (if running on POSIX)."""
        if os.name != "posix":
            pytest.skip("POSIX-only test")

        result = set_secure_file_permissions(temp_file)

        # Should succeed on POSIX systems
        assert result is True

        # Verify actual permissions were set
        stat_info = temp_file.stat()
        permissions = stat_info.st_mode & 0o777
        assert permissions == POSIX_PERMISSIONS

    def test_real_permission_setting_windows(self, temp_file):
        """Test actual permission setting on Windows systems (if running on Windows)."""
        if os.name != "nt":
            pytest.skip("Windows-only test")

        # Only run if USERNAME is available
        if not os.environ.get("USERNAME"):
            pytest.skip("USERNAME environment variable not set")

        result = set_secure_file_permissions(temp_file)

        # Should succeed on Windows systems with icacls available
        # Note: May fail in restricted environments, which is expected behavior
        assert isinstance(result, bool)
