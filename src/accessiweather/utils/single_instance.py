"""Single instance checker for AccessiWeather.

This module provides functionality to ensure only one instance of the app runs.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

class SingleInstanceChecker:
    """Ensures only one instance of the application runs."""

    def __init__(self, app_name="accessiweather"):
        """Initialize the single instance checker.
        
        Args:
            app_name: Name of the application for the lock file
        """
        self.app_name = app_name
        self.lock_file = None
        self.lock_path = None

    def try_acquire_lock(self) -> bool:
        """Try to acquire the lock file.
        
        Returns:
            bool: True if lock was acquired, False if another instance exists
        """
        # Use system temp directory for lock file
        temp_dir = tempfile.gettempdir()
        self.lock_path = os.path.join(temp_dir, f"{self.app_name}.lock")

        try:
            # Try to create and lock the file
            if sys.platform == "win32":
                try:
                    # Windows implementation
                    if os.path.exists(self.lock_path):
                        # Check if the existing lock file is stale
                        try:
                            with open(self.lock_path, 'r+') as f:
                                # If we can open it for writing, previous instance crashed
                                f.write("lock")
                                self.lock_file = f
                                return True
                        except IOError:
                            # File is locked by another instance
                            return False
                    
                    # Create new lock file
                    self.lock_file = open(self.lock_path, 'w')
                    self.lock_file.write("lock")
                    return True
                except IOError:
                    return False
            else:
                # Unix implementation
                import fcntl
                self.lock_file = open(self.lock_path, 'w')
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.lock_file.write(str(os.getpid()))
                self.lock_file.flush()
                return True
                
        except (IOError, OSError) as e:
            logger.debug(f"Could not acquire lock: {e}")
            return False

    def release_lock(self):
        """Release the lock file."""
        try:
            if self.lock_file:
                self.lock_file.close()
            if self.lock_path and os.path.exists(self.lock_path):
                os.unlink(self.lock_path)
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")