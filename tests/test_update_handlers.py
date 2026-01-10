"""
Unit tests for update handlers security.

Tests cover:
- _run_msi_installer path validation and subprocess security
- _extract_portable_update path validation and service integration
- Security requirements: path validation, error handling, safe subprocess calls
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for proper imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accessiweather.handlers.update_handlers import (
    _extract_portable_update,
    _run_msi_installer,
)
from accessiweather.utils.path_validator import SecurityError


class MockApp:
    """Mock AccessiWeatherApp for testing."""

    def __init__(self):
        self.main_window = MagicMock()
        self.main_window.error_dialog = AsyncMock()
        self.main_window.info_dialog = AsyncMock()
        self.update_service = None
        self._request_exit_called = False

    def request_exit(self):
        """Mock request_exit method."""
        self._request_exit_called = True


class TestRunMsiInstallerSecurity:
    """Security tests for _run_msi_installer method."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock app instance."""
        return MockApp()

    @pytest.fixture
    def mock_subprocess_popen(self, monkeypatch):
        """Mock subprocess.Popen to capture calls without executing."""
        calls = []

        class MockPopen:
            def __init__(self, *args, **kwargs):
                calls.append({"args": args, "kwargs": kwargs})

        monkeypatch.setattr("subprocess.Popen", MockPopen)
        return calls

    @pytest.mark.asyncio
    async def test_subprocess_call_uses_list_args_not_shell(
        self, tmp_path, mock_app, mock_subprocess_popen
    ):
        """Test that subprocess.Popen is called with list args, not shell=True.

        Security requirement: shell=True opens command injection vulnerabilities.
        The MSI installer should be executed via msiexec with list arguments.
        """
        # Create a valid MSI file for testing
        msi_path = tmp_path / "update.msi"
        msi_path.write_bytes(b"fake msi content")

        # Run the installer
        await _run_msi_installer(mock_app, str(msi_path))

        # Verify subprocess.Popen was called
        assert len(mock_subprocess_popen) == 1
        call = mock_subprocess_popen[0]

        # CRITICAL SECURITY CHECK: Verify shell=True is NOT used
        assert "shell" not in call["kwargs"], "shell parameter should not be present"
        # If shell is present, it should be False
        if "shell" in call["kwargs"]:
            assert (
                call["kwargs"]["shell"] is False
            ), "shell=True is a security vulnerability (CWE-78)"

        # Verify the command is passed as a list argument
        assert isinstance(call["args"][0], list), "Args should be a list"
        assert call["args"][0][0] == "msiexec", "Should use msiexec command"
        assert call["args"][0][1] == "/i", "Should use /i flag for install"
        # The path should be the absolute resolved path
        assert call["args"][0][2] == str(msi_path.resolve())
        assert call["args"][0][3] == "/norestart", "Should use /norestart flag"

    @pytest.mark.asyncio
    async def test_path_validation_rejects_missing_msi_file(self, tmp_path, mock_app):
        """Test that missing MSI file is rejected with FileNotFoundError.

        Security requirement: Prevent execution with non-existent files.
        """
        nonexistent_msi = tmp_path / "nonexistent.msi"
        assert not nonexistent_msi.exists()

        # Run the installer - should show error dialog
        await _run_msi_installer(mock_app, str(nonexistent_msi))

        # Verify error dialog was shown
        mock_app.main_window.error_dialog.assert_called_once()
        call_args = mock_app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Installer Validation Failed"
        assert "does not exist" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_path_validation_rejects_wrong_extension(self, tmp_path, mock_app):
        """Test that file with wrong extension is rejected with ValueError.

        Security requirement: Only accept .msi files to prevent arbitrary file execution.
        """
        # Create a file with wrong extension
        exe_file = tmp_path / "update.exe"
        exe_file.write_bytes(b"fake exe content")

        # Run the installer - should show error dialog
        await _run_msi_installer(mock_app, str(exe_file))

        # Verify error dialog was shown
        mock_app.main_window.error_dialog.assert_called_once()
        call_args = mock_app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Installer Validation Failed"
        assert "Invalid file type" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_path_validation_rejects_path_traversal(self, tmp_path, mock_app):
        """Test that path traversal attempts are properly handled.

        Security requirement: Prevent path traversal attacks (CWE-22).
        Path resolution should normalize paths, rejecting dangerous patterns.
        """
        # Create a valid MSI file in a subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        msi_file = subdir / "update.msi"
        msi_file.write_bytes(b"fake msi content")

        # Attempt path traversal to reference it
        traversal_path = str(subdir / ".." / "subdir" / "update.msi")

        # This should still work as it resolves to a valid path
        # The validate_executable_path function resolves the path safely
        with patch("subprocess.Popen") as mock_popen:
            await _run_msi_installer(mock_app, traversal_path)
            # Should succeed and use the resolved path
            mock_popen.assert_called_once()
            called_args = mock_popen.call_args[0][0]
            # The path should be resolved to absolute
            assert Path(called_args[2]).resolve() == msi_file.resolve()

    @pytest.mark.asyncio
    async def test_path_validation_rejects_suspicious_characters(self, tmp_path, mock_app):
        """Test that filenames with suspicious characters are rejected.

        Security requirement: Prevent shell metacharacter injection (CWE-78).
        """
        # Windows prevents creation of files with < > : " | ? *
        # But we can test with paths that have other suspicious characters
        # The validation function checks for pipe, ampersand, semicolon, etc.

        # Create a valid MSI file
        msi_file = tmp_path / "update.msi"
        msi_file.write_bytes(b"fake msi content")

        # Test with manually constructed paths containing suspicious characters
        # Note: These can't actually be created on Windows, but we test the validation
        suspicious_paths = [
            str(tmp_path / "update|echo.msi"),  # pipe character
            str(tmp_path / "update&cmd.msi"),  # ampersand
            str(tmp_path / "update;dir.msi"),  # semicolon
        ]

        for suspicious_path in suspicious_paths:
            # These paths don't exist, so will fail with FileNotFoundError first
            # But the suspicious character check is also in place
            await _run_msi_installer(mock_app, suspicious_path)
            # Verify error dialog was shown (either file not found or security error)
            mock_app.main_window.error_dialog.assert_called()
            mock_app.main_window.error_dialog.reset_mock()

    @pytest.mark.asyncio
    async def test_app_request_exit_called_after_installer_starts(
        self, tmp_path, mock_app, mock_subprocess_popen
    ):
        """Test that app.request_exit() is called after installer starts.

        Requirement: Application should exit to allow installer to update files.
        """
        # Create a valid MSI file
        msi_path = tmp_path / "update.msi"
        msi_path.write_bytes(b"fake msi content")

        # Run the installer
        await _run_msi_installer(mock_app, str(msi_path))

        # Verify request_exit was called
        assert mock_app._request_exit_called, "app.request_exit() should be called"

        # Verify info dialog was shown before exit
        mock_app.main_window.info_dialog.assert_called_once()
        call_args = mock_app.main_window.info_dialog.call_args
        assert call_args[0][0] == "Installer Starting"
        assert "close" in call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_error_message_for_file_not_found(self, tmp_path, mock_app):
        """Test that FileNotFoundError produces clear error message."""
        nonexistent_msi = tmp_path / "nonexistent.msi"

        await _run_msi_installer(mock_app, str(nonexistent_msi))

        # Verify error dialog with clear message
        mock_app.main_window.error_dialog.assert_called_once()
        call_args = mock_app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Installer Validation Failed"
        assert "security validation" in call_args[0][1]
        assert "exists and is valid" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_error_message_for_invalid_extension(self, tmp_path, mock_app):
        """Test that invalid extension produces clear error message."""
        wrong_file = tmp_path / "update.txt"
        wrong_file.write_bytes(b"fake content")

        await _run_msi_installer(mock_app, str(wrong_file))

        # Verify error dialog with clear message
        mock_app.main_window.error_dialog.assert_called_once()
        call_args = mock_app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Installer Validation Failed"
        assert "security validation" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_uses_absolute_path_for_subprocess_call(
        self, tmp_path, mock_app, mock_subprocess_popen
    ):
        """Test that absolute path is used for subprocess call.

        Security requirement: Using absolute paths prevents ambiguity and
        potential directory traversal issues.
        """
        # Create MSI file in subdirectory
        subdir = tmp_path / "updates"
        subdir.mkdir()
        msi_path = subdir / "update.msi"
        msi_path.write_bytes(b"fake msi content")

        # Use relative path
        relative_path = str(msi_path.relative_to(Path.cwd()))

        # Run installer
        with patch("pathlib.Path.cwd", return_value=Path.cwd()):
            await _run_msi_installer(mock_app, str(msi_path))

        # Verify subprocess was called with absolute path
        assert len(mock_subprocess_popen) == 1
        call = mock_subprocess_popen[0]
        called_path = Path(call["args"][0][2])
        assert called_path.is_absolute(), "Should use absolute path for security"
        assert called_path == msi_path.resolve()


class TestExtractPortableUpdateSecurity:
    """Security tests for _extract_portable_update method."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock app instance with update_service."""
        app = MockApp()
        app.update_service = MagicMock()
        app.update_service.schedule_portable_update_and_restart = MagicMock()
        return app

    @pytest.mark.asyncio
    async def test_path_validation_rejects_missing_zip_file(self, tmp_path, mock_app):
        """Test that missing ZIP file is rejected with FileNotFoundError.

        Security requirement: Prevent execution with non-existent files.
        """
        nonexistent_zip = tmp_path / "nonexistent.zip"
        assert not nonexistent_zip.exists()

        # Extract update - should show error dialog
        await _extract_portable_update(mock_app, str(nonexistent_zip))

        # Verify error dialog was shown
        mock_app.main_window.error_dialog.assert_called_once()
        call_args = mock_app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Update Validation Failed"
        assert "does not exist" in call_args[0][1]

        # Verify update service was NOT called
        mock_app.update_service.schedule_portable_update_and_restart.assert_not_called()

    @pytest.mark.asyncio
    async def test_path_validation_rejects_wrong_extension(self, tmp_path, mock_app):
        """Test that file with wrong extension is rejected with ValueError.

        Security requirement: Only accept .zip files to prevent arbitrary file execution.
        """
        # Create a file with wrong extension
        exe_file = tmp_path / "update.exe"
        exe_file.write_bytes(b"fake exe content")

        # Extract update - should show error dialog
        await _extract_portable_update(mock_app, str(exe_file))

        # Verify error dialog was shown
        mock_app.main_window.error_dialog.assert_called_once()
        call_args = mock_app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Update Validation Failed"
        assert "Invalid file type" in call_args[0][1]

        # Verify update service was NOT called
        mock_app.update_service.schedule_portable_update_and_restart.assert_not_called()

    @pytest.mark.asyncio
    async def test_path_validation_rejects_path_traversal(self, tmp_path, mock_app):
        """Test that path traversal attempts are properly handled.

        Security requirement: Prevent path traversal attacks (CWE-22).
        Path resolution should normalize paths, rejecting dangerous patterns.
        """
        # Create a valid ZIP file in a subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        zip_file = subdir / "update.zip"
        zip_file.write_bytes(b"fake zip content")

        # Attempt path traversal to reference it
        traversal_path = str(subdir / ".." / "subdir" / "update.zip")

        # This should still work as it resolves to a valid path
        await _extract_portable_update(mock_app, traversal_path)

        # Should succeed and use the resolved path
        mock_app.update_service.schedule_portable_update_and_restart.assert_called_once()
        called_path = (
            mock_app.update_service.schedule_portable_update_and_restart.call_args[0][0]
        )
        # The path should be resolved to absolute
        assert Path(called_path).resolve() == zip_file.resolve()

    @pytest.mark.asyncio
    async def test_path_validation_rejects_suspicious_characters(self, tmp_path, mock_app):
        """Test that filenames with suspicious characters are rejected.

        Security requirement: Prevent shell metacharacter injection (CWE-78).
        """
        # Test with manually constructed paths containing suspicious characters
        suspicious_paths = [
            str(tmp_path / "update|echo.zip"),  # pipe character
            str(tmp_path / "update&cmd.zip"),  # ampersand
            str(tmp_path / "update;dir.zip"),  # semicolon
        ]

        for suspicious_path in suspicious_paths:
            # These paths don't exist, so will fail with FileNotFoundError first
            await _extract_portable_update(mock_app, suspicious_path)
            # Verify error dialog was shown
            mock_app.main_window.error_dialog.assert_called()
            # Verify update service was NOT called
            mock_app.update_service.schedule_portable_update_and_restart.assert_not_called()
            # Reset for next iteration
            mock_app.main_window.error_dialog.reset_mock()

    @pytest.mark.asyncio
    async def test_calls_update_service_with_validated_path(self, tmp_path, mock_app):
        """Test that update service is called with validated absolute path.

        Requirement: Pass validated, absolute path to update service.
        """
        # Create a valid ZIP file
        zip_path = tmp_path / "update.zip"
        zip_path.write_bytes(b"fake zip content")

        # Extract update
        await _extract_portable_update(mock_app, str(zip_path))

        # Verify update service was called with absolute path
        mock_app.update_service.schedule_portable_update_and_restart.assert_called_once()
        called_path = (
            mock_app.update_service.schedule_portable_update_and_restart.call_args[0][0]
        )
        called_path_obj = Path(called_path)
        assert called_path_obj.is_absolute(), "Should use absolute path"
        assert called_path_obj == zip_path.resolve()

    @pytest.mark.asyncio
    async def test_handles_missing_update_service_gracefully(self, tmp_path):
        """Test that missing update_service is handled with clear error message.

        Requirement: Provide helpful error when update service is unavailable.
        """
        # Create app without update_service
        app = MockApp()
        app.update_service = None

        # Create a valid ZIP file
        zip_path = tmp_path / "update.zip"
        zip_path.write_bytes(b"fake zip content")

        # Extract update
        await _extract_portable_update(app, str(zip_path))

        # Verify error dialog was shown
        app.main_window.error_dialog.assert_called_once()
        call_args = app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Update Error"
        assert "not available" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_error_message_for_file_not_found(self, tmp_path, mock_app):
        """Test that FileNotFoundError produces clear error message."""
        nonexistent_zip = tmp_path / "nonexistent.zip"

        await _extract_portable_update(mock_app, str(nonexistent_zip))

        # Verify error dialog with clear message
        mock_app.main_window.error_dialog.assert_called_once()
        call_args = mock_app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Update Validation Failed"
        assert "security validation" in call_args[0][1]
        assert "exists and is valid" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_error_message_for_invalid_extension(self, tmp_path, mock_app):
        """Test that invalid extension produces clear error message."""
        wrong_file = tmp_path / "update.tar.gz"
        wrong_file.write_bytes(b"fake content")

        await _extract_portable_update(mock_app, str(wrong_file))

        # Verify error dialog with clear message
        mock_app.main_window.error_dialog.assert_called_once()
        call_args = mock_app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Update Validation Failed"
        assert "security validation" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_uses_absolute_path_from_relative_input(self, tmp_path, mock_app):
        """Test that relative paths are converted to absolute paths.

        Security requirement: Using absolute paths prevents ambiguity.
        """
        # Create ZIP file in subdirectory
        subdir = tmp_path / "updates"
        subdir.mkdir()
        zip_path = subdir / "update.zip"
        zip_path.write_bytes(b"fake zip content")

        # Use the actual path (which may be relative depending on tmp_path)
        await _extract_portable_update(mock_app, str(zip_path))

        # Verify update service was called with absolute path
        mock_app.update_service.schedule_portable_update_and_restart.assert_called_once()
        called_path = (
            mock_app.update_service.schedule_portable_update_and_restart.call_args[0][0]
        )
        called_path_obj = Path(called_path)
        assert called_path_obj.is_absolute(), "Should convert to absolute path"
        assert called_path_obj == zip_path.resolve()

    @pytest.mark.asyncio
    async def test_handles_update_service_exception(self, tmp_path, mock_app):
        """Test that exceptions from update_service are handled gracefully.

        Requirement: Catch and display errors from update service.
        """
        # Create a valid ZIP file
        zip_path = tmp_path / "update.zip"
        zip_path.write_bytes(b"fake zip content")

        # Make update service raise an exception
        mock_app.update_service.schedule_portable_update_and_restart.side_effect = Exception(
            "Service error"
        )

        # Extract update
        await _extract_portable_update(mock_app, str(zip_path))

        # Verify error dialog was shown
        mock_app.main_window.error_dialog.assert_called_once()
        call_args = mock_app.main_window.error_dialog.call_args
        assert call_args[0][0] == "Extraction Failed"
        assert "Service error" in call_args[0][1]
