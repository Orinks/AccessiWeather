"""
Single instance manager for AccessiWeather.

This module provides functionality to ensure only one instance of the application
can run at a time using a lock file approach.
"""

import atexit
import contextlib
import logging
import os
import signal
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Global reference for cleanup handlers (needed for atexit and signal handlers)
_active_manager: "SingleInstanceManager | None" = None


class SingleInstanceManager:
    """Manages single instance functionality using a lock file approach."""

    def __init__(self, app, lock_filename: str = "accessiweather.lock"):
        """
        Initialize the single instance manager.

        Args:
        ----
            app: The application instance (must have a paths.data attribute)
            lock_filename: Name of the lock file to create

        """
        self.app = app
        self.lock_filename = lock_filename
        self.lock_file_path: Path | None = None
        self._lock_acquired = False
        self._cleanup_registered = False

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

            # Register cleanup handlers for various termination scenarios
            self._register_cleanup_handlers()

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
        """
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            # Set up function signatures for proper error handling
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL

            # OpenProcess with PROCESS_QUERY_LIMITED_INFORMATION (0x1000)
            # This is the minimum access right needed to query process info
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)

            if handle:
                # Process exists, close the handle
                kernel32.CloseHandle(handle)
                return True

            # Check if access was denied (process exists but we can't open it)
            ERROR_ACCESS_DENIED = 5
            last_error = ctypes.get_last_error()
            return last_error == ERROR_ACCESS_DENIED

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
            app_name = getattr(self.app, "formal_name", "AccessiWeather")
            lock_content = f"{pid}\n{timestamp}\n{app_name}\n"

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

    def _register_cleanup_handlers(self) -> None:
        """
        Register cleanup handlers for various termination scenarios.

        This ensures the lock file is cleaned up when:
        - Python exits normally (atexit)
        - Process receives SIGTERM or SIGINT (signal handlers)
        - On Windows: SIGBREAK (Ctrl+Break)

        Note: SIGKILL (kill -9) and Windows Task Manager "End Process"
        cannot be caught - the stale lock detection handles those cases.
        """
        global _active_manager

        if self._cleanup_registered:
            return

        _active_manager = self

        # Register atexit handler for normal Python exit
        atexit.register(_cleanup_lock_file)

        # Register signal handlers for graceful termination
        # SIGTERM: Standard termination signal (kill command default)
        # SIGINT: Interrupt signal (Ctrl+C)
        try:
            signal.signal(signal.SIGTERM, _signal_handler)
            signal.signal(signal.SIGINT, _signal_handler)
        except (ValueError, OSError) as e:
            # Signal handlers can fail in some environments (e.g., threads)
            logger.debug(f"Could not register signal handlers: {e}")

        # Windows-specific: SIGBREAK (Ctrl+Break)
        if os.name == "nt":
            with contextlib.suppress(ValueError, OSError, AttributeError):
                signal.signal(signal.SIGBREAK, _signal_handler)

        self._cleanup_registered = True
        logger.debug("Registered cleanup handlers for lock file")

    def release_lock(self) -> None:
        """Release the single instance lock."""
        global _active_manager

        if self._lock_acquired:
            self._remove_lock_file()
            self._lock_acquired = False
            _active_manager = None
            logger.info("Released single instance lock")

    def force_remove_lock(self) -> bool:
        """
        Force remove the lock file regardless of ownership.

        This is used when the user explicitly chooses to force start the app,
        typically when a previous instance crashed and left a stale lock.

        Returns
        -------
            bool: True if lock was removed successfully, False otherwise

        """
        try:
            if self.lock_file_path is None:
                # Initialize lock file path if not already done
                lock_dir = self.app.paths.data
                lock_dir.mkdir(parents=True, exist_ok=True)
                self.lock_file_path = lock_dir / self.lock_filename

            if self.lock_file_path.exists():
                self.lock_file_path.unlink()
                logger.info(f"Force removed lock file: {self.lock_file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to force remove lock file: {e}")
            return False

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


def _cleanup_lock_file() -> None:
    """
    Cleanup function called by atexit.

    This is a module-level function because atexit requires a callable
    that doesn't hold references that might be garbage collected.
    """
    global _active_manager
    if _active_manager and _active_manager._lock_acquired:
        try:
            _active_manager._remove_lock_file()
            logger.debug("Lock file cleaned up via atexit handler")
        except Exception as e:
            logger.debug(f"Failed to clean up lock file in atexit: {e}")


def _signal_handler(signum: int, frame) -> None:
    """
    Signal handler for SIGTERM, SIGINT, and SIGBREAK.

    Cleans up the lock file before the process terminates.
    """
    global _active_manager
    signal_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    logger.info(f"Received signal {signal_name}, cleaning up lock file")

    if _active_manager and _active_manager._lock_acquired:
        try:
            _active_manager._remove_lock_file()
            _active_manager._lock_acquired = False
        except Exception as e:
            logger.debug(f"Failed to clean up lock file in signal handler: {e}")

    # Re-raise the signal with default handler to allow normal termination
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)
