"""Single instance checker for AccessiWeather.

This module provides functionality to ensure only one instance of the application
can run at a time using a lock file mechanism.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

class SingleInstanceChecker:
    """Ensures only one instance of the application can run at a time."""

    def __init__(self, app_name="accessiweather"):
        """Initialize the single instance checker.

        Args:
            app_name: Name of the application for the lock file
        """
        self.app_name = app_name
        self.lock_file = Path(tempfile.gettempdir()) / f"{app_name}.lock"
        self.lock_handle = None

    def try_acquire_lock(self) -> bool:
        """Try to acquire the lock file.

        Returns:
            bool: True if lock was acquired, False if another instance is running
        """
        try:
            # Try to create and lock the file
            if sys.platform == "win32":
                # Windows implementation
                try:
                    if self.lock_file.exists():
                        # Try to remove existing lock file in case of improper shutdown
                        try:
                            self.lock_file.unlink()
                        except Exception as e:
                            logger.debug(f"Could not remove existing lock file: {e}")
                            return False  # Another instance is running

                    # Create and hold the lock file
                    self.lock_handle = open(self.lock_file, 'w')
                    self.lock_handle.write(str(os.getpid()))
                    return True
                except Exception as e:
                    logger.debug(f"Could not create/write lock file: {e}")
                    return False
            else:
                # Unix implementation using fcntl
                import fcntl
                self.lock_handle = open(self.lock_file, 'w')
                fcntl.lockf(self.lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.lock_handle.write(str(os.getpid()))
                return True

        except Exception as e:
            logger.debug(f"Lock acquisition failed: {e}")
            return False

    def release_lock(self):
        """Release the lock file."""
        try:
            if self.lock_handle:
                self.lock_handle.close()
                self.lock_handle = None

            if sys.platform == "win32":
                # Windows cleanup
                try:
                    if self.lock_file.exists():
                        self.lock_file.unlink()
                except Exception as e:
                    logger.error(f"Error removing lock file: {e}")
            # On Unix, closing the file automatically releases the lock

        except Exception as e:
            logger.error(f"Error releasing lock: {e}")