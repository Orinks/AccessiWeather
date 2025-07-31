"""Single instance checker for AccessiWeather.

DEPRECATED: This module is part of the legacy wxPython implementation and is no longer used.
The Toga-based implementation uses a different single instance manager in single_instance.py.

This module provides functionality to ensure only one instance of the application
can run at a time using wxPython's SingleInstanceChecker.
"""

import logging

import wx

logger = logging.getLogger(__name__)


class SingleInstanceChecker:
    """Ensures only one instance of the application can run at a time using wxPython."""

    def __init__(self, app_name="accessiweather"):
        """Initialize the single instance checker.

        Args:
            app_name: Name of the application for the lock file

        """
        self.app_name = app_name
        self.checker = None
        # We'll initialize the wx.SingleInstanceChecker in try_acquire_lock
        # to avoid creating it before wx.App is initialized

    def try_acquire_lock(self) -> bool:
        """Try to acquire the lock using wxPython's SingleInstanceChecker.

        Returns:
            bool: True if lock was acquired, False if another instance is running

        """
        try:
            # Create a unique name for this user
            instance_name = f"{self.app_name}-{wx.GetUserId()}"
            logger.debug(f"Creating SingleInstanceChecker with name: {instance_name}")

            # Create the checker
            self.checker = wx.SingleInstanceChecker(instance_name)

            # Check if another instance is running
            if self.checker.IsAnotherRunning():
                logger.debug("Another instance is already running")
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking for another instance: {e}")
            # If there's an error, assume no other instance is running
            # to avoid blocking the application unnecessarily
            return True

    def release_lock(self):
        """Release the lock."""
        # The wx.SingleInstanceChecker will be automatically cleaned up
        # when it goes out of scope, so we don't need to do anything here
        self.checker = None
