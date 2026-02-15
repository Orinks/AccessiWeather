"""Tests for file permissions functionality."""

from __future__ import annotations

import os
import subprocess
from unittest.mock import patch

import pytest

from accessiweather.config.file_permissions import (
    POSIX_PERMISSIONS,
    SUBPROCESS_TIMEOUT,
    _set_posix_permissions,
    _set_windows_permissions,
    set_secure_file_permissions,
)


class TestSetSecureFilePermissions:
    """Tests for set_secure_file_permissions function."""

    def test_string_path_converted_to_path(self, tmp_path):
        """Test that string paths are converted to Path objects."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("accessiweather.config.file_permissions._set_posix_permissions", return_value=True):
            result = set_secure_file_permissions(str(test_file))

            assert result is True

    def test_nonexistent_file_returns_false(self, tmp_path):
        """Test that function returns False for nonexistent files."""
        nonexistent = tmp_path / "nonexistent.txt"

        result = set_secure_file_permissions(nonexistent)

        assert result is False

    @patch("os.name", "posix")
    def test_posix_system_uses_posix_permissions(self, tmp_path):
        """Test that POSIX systems use POSIX permission setting."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("accessiweather.config.file_permissions._set_posix_permissions", return_value=True) as mock_posix:
            result = set_secure_file_permissions(test_file)

            assert result is True
            mock_posix.assert_called_once_with(test_file)

    @patch("os.name", "nt")
    def test_windows_system_uses_windows_permissions(self, tmp_path):
        """Test that Windows systems use Windows permission setting."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("accessiweather.config.file_permissions._set_windows_permissions", return_value=True) as mock_windows:
            result = set_secure_file_permissions(test_file)

            assert result is True
            mock_windows.assert_called_once_with(test_file)

    def test_unexpected_exception_handled(self, tmp_path):
        """Test that unexpected exceptions are caught and handled."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("accessiweather.config.file_permissions._set_posix_permissions",
                  side_effect=RuntimeError("Unexpected error")):
            result = set_secure_file_permissions(test_file)

            assert result is False


class TestSetPosixPermissions:
    """Tests for _set_posix_permissions function."""

    def test_successful_chmod(self, tmp_path):
        """Test successful permission setting with os.chmod."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("os.chmod") as mock_chmod:
            result = _set_posix_permissions(test_file)

            assert result is True
            mock_chmod.assert_called_once_with(test_file, POSIX_PERMISSIONS)

    def test_permission_error_handled(self, tmp_path):
        """Test that PermissionError is handled gracefully."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("os.chmod", side_effect=PermissionError("Access denied")):
            result = _set_posix_permissions(test_file)

            assert result is False

    def test_os_error_handled(self, tmp_path):
        """Test that OSError is handled gracefully."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("os.chmod", side_effect=OSError("Filesystem error")):
            result = _set_posix_permissions(test_file)

            assert result is False

    def test_unexpected_exception_handled(self, tmp_path):
        """Test that unexpected exceptions are handled gracefully."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch("os.chmod", side_effect=ValueError("Unexpected error")):
            result = _set_posix_permissions(test_file)

            assert result is False

    def test_correct_permissions_value(self):
        """Test that POSIX_PERMISSIONS has the correct octal value."""
        assert POSIX_PERMISSIONS == 0o600


class TestSetWindowsPermissions:
    """Tests for _set_windows_permissions function."""

    def test_successful_icacls_execution(self, tmp_path):
        """Test successful icacls execution."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.dict(os.environ, {"USERNAME": "testuser"}), patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0

                result = _set_windows_permissions(test_file)

                assert result is True
                mock_run.assert_called_once()

                # Check command arguments
                args = mock_run.call_args[0][0]
                assert args[0] == "icacls"
                assert str(test_file) in args
                assert "/inheritance:r" in args
                assert "/grant:r" in args
                assert "testuser:(F)" in args

    def test_missing_username_environment_variable(self, tmp_path):
        """Test behavior when USERNAME environment variable is missing."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.dict(os.environ, {}, clear=True):
            result = _set_windows_permissions(test_file)

            assert result is False

    def test_called_process_error_handled(self, tmp_path):
        """Test that CalledProcessError is handled gracefully."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.dict(os.environ, {"USERNAME": "testuser"}), patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "icacls", stderr="Access denied")):
                result = _set_windows_permissions(test_file)

                assert result is False

    def test_timeout_expired_handled(self, tmp_path):
        """Test that TimeoutExpired is handled gracefully."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.dict(os.environ, {"USERNAME": "testuser"}), patch("subprocess.run", side_effect=subprocess.TimeoutExpired("icacls", SUBPROCESS_TIMEOUT)):
                result = _set_windows_permissions(test_file)

                assert result is False

    def test_file_not_found_error_handled(self, tmp_path):
        """Test that FileNotFoundError is handled gracefully."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.dict(os.environ, {"USERNAME": "testuser"}), patch("subprocess.run", side_effect=FileNotFoundError("icacls.exe not found")):
                result = _set_windows_permissions(test_file)

                assert result is False

    def test_unexpected_exception_handled(self, tmp_path):
        """Test that unexpected exceptions are handled gracefully."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.dict(os.environ, {"USERNAME": "testuser"}), patch("subprocess.run", side_effect=RuntimeError("Unexpected error")):
                result = _set_windows_permissions(test_file)

                assert result is False

    def test_subprocess_arguments_correct(self, tmp_path):
        """Test that subprocess is called with correct arguments."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.dict(os.environ, {"USERNAME": "testuser"}), patch("subprocess.run") as mock_run:
                _set_windows_permissions(test_file)

                # Check all call arguments
                args, kwargs = mock_run.call_args
                command = args[0]

                assert command == [
                    "icacls",
                    str(test_file),
                    "/inheritance:r",
                    "/grant:r",
                    "testuser:(F)"
                ]

                assert kwargs["check"] is True
                assert kwargs["capture_output"] is True
                assert kwargs["text"] is True
                assert kwargs["timeout"] == SUBPROCESS_TIMEOUT

    @patch("os.name", "nt")
    def test_creation_flags_on_windows(self, tmp_path):
        """Test that CREATE_NO_WINDOW flag is used on Windows."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.dict(os.environ, {"USERNAME": "testuser"}), patch("subprocess.run") as mock_run:
                _set_windows_permissions(test_file)

                kwargs = mock_run.call_args[1]
                # Should use the CREATE_NO_WINDOW flag
                assert "creationflags" in kwargs
                assert kwargs["creationflags"] != 0

    @patch("os.name", "posix")
    def test_creation_flags_on_non_windows(self, tmp_path):
        """Test that creation flags are 0 on non-Windows systems."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.dict(os.environ, {"USERNAME": "testuser"}), patch("subprocess.run") as mock_run:
                _set_windows_permissions(test_file)

                kwargs = mock_run.call_args[1]
                # Should use 0 for creation flags on non-Windows
                assert kwargs["creationflags"] == 0


class TestConstants:
    """Tests for module constants."""

    def test_posix_permissions_value(self):
        """Test that POSIX_PERMISSIONS has the expected value."""
        assert POSIX_PERMISSIONS == 0o600

    def test_subprocess_timeout_value(self):
        """Test that SUBPROCESS_TIMEOUT has a reasonable value."""
        assert SUBPROCESS_TIMEOUT == 5
        assert isinstance(SUBPROCESS_TIMEOUT, int)

    def test_create_no_window_constant(self):
        """Test that CREATE_NO_WINDOW constant is properly defined."""
        from accessiweather.config.file_permissions import CREATE_NO_WINDOW

        # Should be a valid integer flag
        assert isinstance(CREATE_NO_WINDOW, int)
        # Should be non-zero (the actual Windows constant value)
        assert CREATE_NO_WINDOW != 0


class TestIntegration:
    """Integration tests for file permissions."""

    def test_real_file_permissions_posix(self, tmp_path):
        """Test actual permission setting on POSIX systems."""
        if os.name == "nt":
            pytest.skip("POSIX test on Windows system")

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Set initial permissions (more permissive)
        test_file.chmod(0o644)

        result = set_secure_file_permissions(test_file)

        if result:  # Only check if setting permissions succeeded
            # Verify actual file permissions
            file_stat = test_file.stat()
            file_mode = file_stat.st_mode & 0o777  # Extract permission bits
            assert file_mode == POSIX_PERMISSIONS

    def test_read_only_filesystem_handled(self, tmp_path):
        """Test behavior with read-only filesystem (simulation)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Simulate read-only filesystem by making chmod fail
        with patch("os.chmod", side_effect=OSError("Read-only filesystem")):
            result = set_secure_file_permissions(test_file)

            # Should fail gracefully
            assert result is False

    def test_network_drive_simulation(self, tmp_path):
        """Test behavior simulating a network drive with limited permission support."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Simulate network drive limitations
        with patch("os.chmod", side_effect=PermissionError("Operation not supported")):
            result = set_secure_file_permissions(test_file)

            # Should fail gracefully
            assert result is False
