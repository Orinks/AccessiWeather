"""
Single instance manager for AccessiWeather Toga application.

This module provides functionality to ensure only one instance of the application
can run at a time using a lock file approach, since Toga/BeeWare does not provide
built-in single-instance management.
"""

import logging
import os
import subprocess
import time
from pathlib import Path

import toga

logger = logging.getLogger(__name__)


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

    def try_acquire_lock(self) -> bool:
        """
        Try to acquire the single instance lock.

        Returns
        -------
            bool: True if lock was acquired successfully, False if another instance is running

        """
        try:
            # Use app.paths.data for the lock file location (cross-platform data directory)
            lock_dir = self.app.paths.data
            lock_dir.mkdir(parents=True, exist_ok=True)
            self.lock_file_path = lock_dir / self.lock_filename

            logger.info(f"Checking for existing instance using lock file: {self.lock_file_path}")

            # Check if lock file exists and is valid
            if self.lock_file_path and self.lock_file_path.exists():
                if self._is_lock_file_stale():
                    logger.info("Found stale lock file, removing it")
                    self._remove_lock_file()
                else:
                    logger.info("Another instance is already running")
                    return False

            # Create lock file with current process info
            self._create_lock_file()
            self._lock_acquired = True
            logger.info("Successfully acquired single instance lock")
            return True

        except Exception as e:
            logger.error(f"Error checking for another instance: {e}")
            # If there's an error, assume no other instance is running
            # to avoid blocking the application unnecessarily
            return True

    def _is_lock_file_stale(self) -> bool:
        """
        Check if the lock file is stale (from a crashed instance).

        Returns
        -------
            bool: True if the lock file is stale and should be removed

        """
        try:
            if not self.lock_file_path or not self.lock_file_path.exists():
                return False

            # Read the lock file content
            with open(self.lock_file_path, encoding="utf-8") as f:
                content = f.read().strip()

            # Parse the lock file content
            lines = content.split("\n")
            if len(lines) < 2:
                logger.warning("Invalid lock file format, considering it stale")
                return True

            try:
                pid = int(lines[0])
                timestamp = float(lines[1])
            except (ValueError, IndexError):
                logger.warning("Invalid lock file content, considering it stale")
                return True

            # Check if the process is still running (cross-platform approach)
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
            # Cross-platform way to check if process is running
            if os.name == "nt":  # Windows
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, timeout=5
                )
                return str(pid) in result.stdout
            # Unix-like systems (macOS, Linux)
            # Send signal 0 to check if process exists
            os.kill(pid, 0)
            return True
        except Exception:
            # Catch all exceptions to avoid blocking the app
            # This includes OSError, subprocess errors, and any other unexpected issues
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
