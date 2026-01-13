"""
Single instance manager for AccessiWeather Toga application.

This module provides functionality to ensure only one instance of the application
can run at a time using a lock file approach, since Toga/BeeWare does not provide
built-in single-instance management.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import toga

from accessiweather.performance.timer import measure

logger = logging.getLogger(__name__)

# Import ctypes at module level (stdlib, always available)
# Cache kernel32 reference on Windows for better performance
import ctypes

_kernel32: Any = None
if os.name == "nt":
    _kernel32 = ctypes.windll.kernel32


class SingleInstanceManager:
    """Manages single instance functionality using a lock file approach."""

    def __init__(self, app: toga.App, lock_filename: str = "accessiweather.lock"):
        """
        Initialize the single instance manager.

        Args:
        ----
            app: The Toga application instance
            lock_filename: Name of the lock file to create

        """
        self.app = app
        self.lock_filename = lock_filename
        self.lock_file_path: Path | None = None
        self._lock_acquired = False

    def _read_lock_info(self) -> tuple[int, float, str] | None:
        """
        Read lock file info in a single operation.

        Returns
        -------
            tuple[int, float, str] | None: (pid, timestamp, app_name) or None if invalid format

        Raises
        ------
            Exception: Re-raises read errors (permission denied, etc.) to be handled by caller

        """
        if not self.lock_file_path:
            return None
        try:
            # Use explicit open() for better testability (builtins.open can be mocked)
            # Single read operation - more efficient than multiple reads
            with open(self.lock_file_path, encoding="utf-8") as f:
                content = f.read().strip()
            lines = content.split("\n")
            if len(lines) < 2:
                return None
            return int(lines[0]), float(lines[1]), lines[2] if len(lines) > 2 else ""
        except FileNotFoundError:
            # File doesn't exist - return None (not an error)
            return None
        except (ValueError, IndexError):
            # Invalid content format - return None
            return None
        # Let other exceptions (PermissionError, OSError, etc.) propagate up

    def _lock_file_exists(self) -> bool:
        """
        Check if lock file exists using exception-based approach.

        Using stat() with exception handling can be faster than exists() in some cases
        because it avoids double system calls.

        Returns
        -------
            bool: True if lock file exists

        """
        if not self.lock_file_path:
            return False
        try:
            self.lock_file_path.stat()
            return True
        except (FileNotFoundError, OSError):
            return False

    def try_acquire_lock(self) -> bool:
        """
        Try to acquire the single instance lock.

        Returns
        -------
            bool: True if lock was acquired successfully, False if another instance is running

        """
        with measure("single_instance_lock_acquisition"):
            try:
                # Use app.paths.data for the lock file location (cross-platform data directory)
                lock_dir = self.app.paths.data
                lock_dir.mkdir(parents=True, exist_ok=True)
                self.lock_file_path = lock_dir / self.lock_filename

                logger.info(
                    f"Checking for existing instance using lock file: {self.lock_file_path}"
                )

                # Early return: if no lock file exists, skip all stale checks
                if not self._lock_file_exists():
                    self._create_lock_file()
                    self._lock_acquired = True
                    logger.info("Successfully acquired single instance lock (no existing lock)")
                    return True

                # Lock file exists - check if it's stale
                if self._is_lock_file_stale():
                    logger.info("Found stale lock file, removing it")
                    self._remove_lock_file()
                    self._create_lock_file()
                    self._lock_acquired = True
                    logger.info("Successfully acquired single instance lock (replaced stale)")
                    return True

                # Lock file exists and is not stale - another instance is running
                logger.info("Another instance is already running")
                return False

            except Exception as e:
                logger.error(f"Error checking for another instance: {e}")
                # If there's an error, assume no other instance is running
                # to avoid blocking the application unnecessarily
                return True

    def _is_lock_file_stale(self) -> bool:
        """
        Check if the lock file is stale (from a crashed instance).

        Uses the optimized _read_lock_info() helper for single-read operation.

        Returns
        -------
            bool: True if the lock file is stale and should be removed

        """
        try:
            # Early return if lock file path not set
            if not self.lock_file_path:
                return False

            # Use consolidated read operation - returns None if file doesn't exist or is invalid
            lock_info = self._read_lock_info()

            if lock_info is None:
                # File doesn't exist, or has invalid format
                # Check if it's due to missing file vs invalid content
                if self._lock_file_exists():
                    logger.warning("Invalid lock file format, considering it stale")
                    return True
                return False

            pid, timestamp, _app_name = lock_info

            # Check if the process is still running (cross-platform approach)
            # This is the most expensive check, so do it before timestamp check
            if not self._is_process_running(pid):
                logger.info(f"Process {pid} is no longer running, lock file is stale")
                return True

            # Check if the lock file is very old (more than 24 hours)
            current_time = time.time()
            if current_time - timestamp > 24 * 60 * 60:  # 24 hours
                logger.info("Lock file is older than 24 hours, considering it stale")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking if lock file is stale: {e}")
            # If we can't determine, assume it's not stale to be safe
            return False

    def _is_process_running(self, pid: int) -> bool:
        """
        Check if a process with the given PID is running.

        Args:
        ----
            pid: Process ID to check

        Returns:
        -------
            bool: True if the process is running, False otherwise

        """
        try:
            if os.name == "nt":  # Windows - use ctypes for fast, silent check
                return self._is_windows_process_running(pid)
            # Unix-like systems (macOS, Linux)
            # Send signal 0 to check if process exists
            os.kill(pid, 0)
            return True
        except Exception:
            # Catch all exceptions to avoid blocking the app
            # This includes OSError, subprocess errors, and any other unexpected issues
            return False

    def _is_windows_process_running(self, pid: int) -> bool:
        """
        Check if a Windows process is running using the Windows API.

        This is much faster than spawning tasklist.exe and doesn't create
        a visible terminal window.

        Uses the module-level cached _kernel32 reference for better performance.
        """
        try:
            # Use the module-level cached kernel32 reference for performance
            # _kernel32 is cached at module load time when os.name == "nt"
            if _kernel32 is None:
                raise RuntimeError("kernel32 not available")

            # OpenProcess with PROCESS_QUERY_LIMITED_INFORMATION (0x1000)
            # This is the minimum access right needed to query process info
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)

            if handle:
                # Process exists, close the handle
                _kernel32.CloseHandle(handle)
                return True

            # Check if access was denied (process exists but we can't open it)
            ERROR_ACCESS_DENIED = 5
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED

        except Exception as e:
            logger.debug(f"Windows process check failed, falling back to tasklist: {e}")
            # Fallback to tasklist if ctypes fails (shouldn't happen on Windows)
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                return str(pid) in result.stdout
            except Exception:
                return False

    def _create_lock_file(self) -> None:
        """Create the lock file with current process information."""
        try:
            if not self.lock_file_path:
                raise RuntimeError("Lock file path not set")

            # Get current process ID and timestamp
            pid = os.getpid()
            timestamp = time.time()

            # Write lock file content
            lock_content = f"{pid}\n{timestamp}\n{self.app.formal_name}\n"

            with open(self.lock_file_path, "w", encoding="utf-8") as f:
                f.write(lock_content)

            logger.info(f"Created lock file with PID {pid} at {self.lock_file_path}")

        except Exception as e:
            logger.error(f"Failed to create lock file: {e}")
            raise

    def _remove_lock_file(self) -> None:
        """Remove the lock file."""
        try:
            if self.lock_file_path and self.lock_file_path.exists():
                self.lock_file_path.unlink()
                logger.info(f"Removed lock file: {self.lock_file_path}")
        except Exception as e:
            logger.error(f"Failed to remove lock file: {e}")

    def release_lock(self) -> None:
        """Release the single instance lock."""
        if self._lock_acquired:
            self._remove_lock_file()
            self._lock_acquired = False
            logger.info("Released single instance lock")

    async def show_already_running_dialog(self) -> None:
        """Show a user-friendly dialog when another instance is already running."""
        try:
            await self.app.main_window.info_dialog(
                "AccessiWeather Already Running",
                "AccessiWeather is already running.\n\n"
                "Please check your system tray or taskbar for the existing instance.\n"
                "If you cannot find it, please wait a moment and try again.",
            )
        except Exception as e:
            logger.error(f"Failed to show already running dialog: {e}")
            # Fallback to console message
            print("AccessiWeather is already running. Please check your system tray.")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit - ensure lock is released."""
        self.release_lock()
