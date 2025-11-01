"""
Unit tests for single_instance module.

Tests cover:
- Lock file acquisition and release
- Stale lock file detection
- Process running checks
- Context manager functionality
- Cross-platform behavior
- Error handling
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Direct import to avoid __init__.py importing toga
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accessiweather.single_instance import SingleInstanceManager


class TestSingleInstanceManagerInitialization:
    """Test SingleInstanceManager initialization."""

    @pytest.fixture
    def mock_app(self, tmp_path):
        """Create mock Toga app."""
        app = Mock()
        app.formal_name = "TestApp"
        app.paths = Mock()
        app.paths.data = tmp_path / "data"
        app.paths.data.mkdir(parents=True, exist_ok=True)
        app.main_window = Mock()
        return app

    def test_initialization(self, mock_app):
        """Should initialize with app and lock filename."""
        manager = SingleInstanceManager(mock_app, lock_filename="test.lock")

        assert manager.app == mock_app
        assert manager.lock_filename == "test.lock"
        assert manager.lock_file_path is None
        assert manager._lock_acquired is False

    def test_initialization_default_filename(self, mock_app):
        """Should use default lock filename."""
        manager = SingleInstanceManager(mock_app)

        assert manager.lock_filename == "accessiweather.lock"


class TestLockAcquisition:
    """Test lock file acquisition logic."""

    @pytest.fixture
    def mock_app(self, tmp_path):
        """Create mock Toga app."""
        app = Mock()
        app.formal_name = "TestApp"
        app.paths = Mock()
        app.paths.data = tmp_path / "data"
        app.paths.data.mkdir(parents=True, exist_ok=True)
        app.main_window = Mock()
        return app

    def test_try_acquire_lock_success(self, mock_app):
        """Should successfully acquire lock when no other instance."""
        manager = SingleInstanceManager(mock_app)

        result = manager.try_acquire_lock()

        assert result is True
        assert manager._lock_acquired is True
        assert manager.lock_file_path is not None
        assert manager.lock_file_path.exists()

    def test_try_acquire_lock_creates_lock_file(self, mock_app):
        """Should create lock file with process info."""
        manager = SingleInstanceManager(mock_app)
        manager.try_acquire_lock()

        # Verify lock file contains PID and timestamp
        content = manager.lock_file_path.read_text()
        lines = content.strip().split("\n")

        assert len(lines) >= 3
        assert lines[0].isdigit()  # PID
        assert float(lines[1]) > 0  # Timestamp
        assert lines[2] == "TestApp"  # App name

    def test_try_acquire_lock_already_running(self, mock_app):
        """Should fail to acquire lock when another instance running."""
        # First instance
        manager1 = SingleInstanceManager(mock_app)
        manager1.try_acquire_lock()

        # Second instance
        manager2 = SingleInstanceManager(mock_app)
        result = manager2.try_acquire_lock()

        assert result is False
        assert manager2._lock_acquired is False

        # Cleanup
        manager1.release_lock()

    def test_try_acquire_lock_stale_file(self, mock_app):
        """Should acquire lock when lock file is stale."""
        manager = SingleInstanceManager(mock_app)

        # Create stale lock file with non-existent PID
        lock_dir = mock_app.paths.data
        lock_path = lock_dir / "accessiweather.lock"
        lock_path.write_text("999999\n1.0\nOldApp\n")  # Very old timestamp and unlikely PID

        # Should successfully acquire lock
        result = manager.try_acquire_lock()

        assert result is True
        assert manager._lock_acquired is True

    def test_try_acquire_lock_exception_handling(self, mock_app):
        """Should return True on exception to avoid blocking."""
        manager = SingleInstanceManager(mock_app)

        # Mock _create_lock_file to raise exception
        with patch.object(manager, "_create_lock_file", side_effect=Exception("Test error")):
            result = manager.try_acquire_lock()

            # Should return True to allow app to start
            assert result is True


class TestStaleLockFileDetection:
    """Test stale lock file detection logic."""

    @pytest.fixture
    def mock_app(self, tmp_path):
        """Create mock Toga app."""
        app = Mock()
        app.formal_name = "TestApp"
        app.paths = Mock()
        app.paths.data = tmp_path / "data"
        app.paths.data.mkdir(parents=True, exist_ok=True)
        app.main_window = Mock()
        return app

    def test_is_lock_file_stale_no_file(self, mock_app):
        """Should return False when lock file doesn't exist."""
        manager = SingleInstanceManager(mock_app)
        manager.lock_file_path = mock_app.paths.data / "nonexistent.lock"

        result = manager._is_lock_file_stale()

        assert result is False

    def test_is_lock_file_stale_invalid_format(self, mock_app):
        """Should return True for invalid lock file format."""
        manager = SingleInstanceManager(mock_app)
        manager.lock_file_path = mock_app.paths.data / "test.lock"
        manager.lock_file_path.write_text("invalid content")

        result = manager._is_lock_file_stale()

        assert result is True

    def test_is_lock_file_stale_invalid_pid(self, mock_app):
        """Should return True when PID is not a number."""
        manager = SingleInstanceManager(mock_app)
        manager.lock_file_path = mock_app.paths.data / "test.lock"
        manager.lock_file_path.write_text("not_a_number\n1.0\nApp\n")

        result = manager._is_lock_file_stale()

        assert result is True

    def test_is_lock_file_stale_invalid_timestamp(self, mock_app):
        """Should return True when timestamp is not a number."""
        manager = SingleInstanceManager(mock_app)
        manager.lock_file_path = mock_app.paths.data / "test.lock"
        manager.lock_file_path.write_text(f"{os.getpid()}\ninvalid_timestamp\nApp\n")

        result = manager._is_lock_file_stale()

        assert result is True

    def test_is_lock_file_stale_process_not_running(self, mock_app):
        """Should return True when process is not running."""
        manager = SingleInstanceManager(mock_app)
        manager.lock_file_path = mock_app.paths.data / "test.lock"

        # Use unlikely PID that's not running
        fake_pid = 999999
        current_time = time.time()
        manager.lock_file_path.write_text(f"{fake_pid}\n{current_time}\nApp\n")

        with patch.object(manager, "_is_process_running", return_value=False):
            result = manager._is_lock_file_stale()

            assert result is True

    def test_is_lock_file_stale_old_timestamp(self, mock_app):
        """Should return True when lock file is older than 24 hours."""
        manager = SingleInstanceManager(mock_app)
        manager.lock_file_path = mock_app.paths.data / "test.lock"

        # Create lock file with very old timestamp
        old_timestamp = time.time() - (25 * 60 * 60)  # 25 hours ago
        manager.lock_file_path.write_text(f"{os.getpid()}\n{old_timestamp}\nApp\n")

        result = manager._is_lock_file_stale()

        assert result is True

    def test_is_lock_file_stale_recent_and_running(self, mock_app):
        """Should return False when process is running and file is recent."""
        manager = SingleInstanceManager(mock_app)
        manager.lock_file_path = mock_app.paths.data / "test.lock"

        # Current process and recent timestamp
        current_time = time.time()
        manager.lock_file_path.write_text(f"{os.getpid()}\n{current_time}\nApp\n")

        with patch.object(manager, "_is_process_running", return_value=True):
            result = manager._is_lock_file_stale()

            assert result is False


class TestProcessRunningCheck:
    """Test process running check functionality."""

    @pytest.fixture
    def mock_app(self, tmp_path):
        """Create mock Toga app."""
        app = Mock()
        app.formal_name = "TestApp"
        app.paths = Mock()
        app.paths.data = tmp_path / "data"
        app.main_window = Mock()
        return app

    def test_is_process_running_current_process(self, mock_app):
        """Should return True for current process."""
        manager = SingleInstanceManager(mock_app)

        result = manager._is_process_running(os.getpid())

        assert result is True

    def test_is_process_running_nonexistent_process(self, mock_app):
        """Should return False for nonexistent process."""
        manager = SingleInstanceManager(mock_app)

        # Use very unlikely PID
        result = manager._is_process_running(999999)

        assert result is False

    @patch("os.name", "nt")
    def test_is_process_running_windows(self, mock_app):
        """Should use tasklist on Windows."""
        manager = SingleInstanceManager(mock_app)

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.stdout = f"PID: {os.getpid()}"
            mock_run.return_value = mock_result

            result = manager._is_process_running(os.getpid())

            assert result is True
            mock_run.assert_called_once()

    @patch("os.name", "posix")
    def test_is_process_running_unix(self, mock_app):
        """Should use os.kill on Unix systems."""
        manager = SingleInstanceManager(mock_app)

        # Current process should be running
        result = manager._is_process_running(os.getpid())

        assert result is True

    @patch("os.name", "nt")
    def test_is_process_running_windows_timeout(self, mock_app):
        """Should handle subprocess timeout on Windows."""
        manager = SingleInstanceManager(mock_app)

        with patch("subprocess.run", side_effect=Exception("Timeout")):
            result = manager._is_process_running(12345)

            assert result is False


class TestLockRelease:
    """Test lock release functionality."""

    @pytest.fixture
    def mock_app(self, tmp_path):
        """Create mock Toga app."""
        app = Mock()
        app.formal_name = "TestApp"
        app.paths = Mock()
        app.paths.data = tmp_path / "data"
        app.paths.data.mkdir(parents=True, exist_ok=True)
        app.main_window = Mock()
        return app

    def test_release_lock(self, mock_app):
        """Should release lock and remove lock file."""
        manager = SingleInstanceManager(mock_app)
        manager.try_acquire_lock()

        lock_path = manager.lock_file_path
        assert lock_path.exists()

        manager.release_lock()

        assert not lock_path.exists()
        assert manager._lock_acquired is False

    def test_release_lock_not_acquired(self, mock_app):
        """Should handle releasing lock when not acquired."""
        manager = SingleInstanceManager(mock_app)

        # Should not raise error
        manager.release_lock()

        assert manager._lock_acquired is False

    def test_release_lock_file_already_removed(self, mock_app):
        """Should handle missing lock file gracefully."""
        manager = SingleInstanceManager(mock_app)
        manager.try_acquire_lock()

        # Manually remove the lock file
        manager.lock_file_path.unlink()

        # Should not raise error
        manager.release_lock()

        assert manager._lock_acquired is False


class TestContextManager:
    """Test context manager functionality."""

    @pytest.fixture
    def mock_app(self, tmp_path):
        """Create mock Toga app."""
        app = Mock()
        app.formal_name = "TestApp"
        app.paths = Mock()
        app.paths.data = tmp_path / "data"
        app.paths.data.mkdir(parents=True, exist_ok=True)
        app.main_window = Mock()
        return app

    def test_context_manager_enters(self, mock_app):
        """Should enter context successfully."""
        manager = SingleInstanceManager(mock_app)

        with manager as mgr:
            assert mgr is manager

    def test_context_manager_releases_lock(self, mock_app):
        """Should release lock on exit."""
        manager = SingleInstanceManager(mock_app)
        manager.try_acquire_lock()

        lock_path = manager.lock_file_path

        with manager:
            assert lock_path.exists()

        # Lock should be released after context
        assert not lock_path.exists()
        assert manager._lock_acquired is False

    def test_context_manager_releases_lock_on_exception(self, mock_app):
        """Should release lock even when exception occurs."""
        manager = SingleInstanceManager(mock_app)
        manager.try_acquire_lock()

        lock_path = manager.lock_file_path

        try:
            with manager:
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Lock should still be released
        assert not lock_path.exists()
        assert manager._lock_acquired is False


class TestShowAlreadyRunningDialog:
    """Test dialog for already running instance."""

    @pytest.fixture
    def mock_app(self, tmp_path):
        """Create mock Toga app."""
        app = Mock()
        app.formal_name = "TestApp"
        app.paths = Mock()
        app.paths.data = tmp_path / "data"
        app.main_window = Mock()
        app.main_window.info_dialog = Mock(return_value=None)
        return app

    @pytest.mark.asyncio
    async def test_show_already_running_dialog_success(self, mock_app):
        """Should show dialog successfully."""
        manager = SingleInstanceManager(mock_app)

        # Should not raise error
        await manager.show_already_running_dialog()

    @pytest.mark.asyncio
    async def test_show_already_running_dialog_exception(self, mock_app, capsys):
        """Should handle dialog exception and print fallback message."""
        manager = SingleInstanceManager(mock_app)

        # Mock dialog to raise exception
        mock_app.main_window.info_dialog = Mock(side_effect=Exception("Dialog error"))

        await manager.show_already_running_dialog()

        # Should print fallback message
        captured = capsys.readouterr()
        assert "already running" in captured.out.lower()


class TestSingleInstanceManagerEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def mock_app(self, tmp_path):
        """Create mock Toga app."""
        app = Mock()
        app.formal_name = "TestApp"
        app.paths = Mock()
        app.paths.data = tmp_path / "data"
        app.paths.data.mkdir(parents=True, exist_ok=True)
        app.main_window = Mock()
        return app

    def test_lock_file_with_special_characters_in_app_name(self, mock_app):
        """Should handle app names with special characters."""
        mock_app.formal_name = "Test App! v1.0"
        manager = SingleInstanceManager(mock_app)

        result = manager.try_acquire_lock()

        assert result is True
        assert manager.lock_file_path.exists()

    def test_multiple_acquire_attempts(self, mock_app):
        """Should handle multiple acquire attempts."""
        manager = SingleInstanceManager(mock_app)

        # First acquire
        result1 = manager.try_acquire_lock()
        assert result1 is True

        # Second acquire (already acquired)
        result2 = manager.try_acquire_lock()
        # Will try to acquire again, checking existing file
        assert result2 is False  # Own lock file exists

    def test_lock_file_path_not_set(self, mock_app):
        """Should handle operations when lock_file_path is None."""
        manager = SingleInstanceManager(mock_app)

        # Should not raise error
        manager.release_lock()

    def test_create_lock_file_without_path(self, mock_app):
        """Should raise RuntimeError when creating lock without path."""
        manager = SingleInstanceManager(mock_app)
        manager.lock_file_path = None

        with pytest.raises(RuntimeError, match="Lock file path not set"):
            manager._create_lock_file()

    def test_is_lock_file_stale_with_read_error(self, mock_app):
        """Should return False when unable to read lock file."""
        manager = SingleInstanceManager(mock_app)
        manager.lock_file_path = mock_app.paths.data / "test.lock"
        manager.lock_file_path.write_text("content")

        # Mock read to raise exception
        with patch("builtins.open", side_effect=Exception("Read error")):
            result = manager._is_lock_file_stale()

            # Should return False to be safe
            assert result is False
