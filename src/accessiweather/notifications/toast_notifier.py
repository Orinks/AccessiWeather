"""Toast notification module for AccessiWeather.

This module provides cross-platform toast notification functionality
with safe error handling for test environments.
"""

import logging
import sys

# Type checking will report this as missing, but it's a runtime dependency
from plyer import notification  # type: ignore

logger = logging.getLogger(__name__)


class SafeToastNotifier:
    """
    A wrapper around the notification system that handles exceptions.
    Provides cross-platform notification support using plyer.
    """

    def __init__(self):
        """Initialize the safe toast notifier"""
        # No initialization needed for plyer
        pass

    def show_toast(self, **kwargs):
        """Show a toast notification"""
        try:
            # If we're running tests, just log the notification
            if "pytest" in sys.modules:
                # For tests, just log the notification and return success
                title = kwargs.get("title", "")
                msg = kwargs.get("msg", "")
                logger.info(f"Toast notification: {title} - {msg}")
                return True

            # Map win10toast parameters to plyer parameters
            title = kwargs.get("title", "Notification")
            message = kwargs.get("msg", "")
            app_name = "AccessiWeather"
            timeout = kwargs.get("duration", 10)

            # Use plyer's cross-platform notification
            notification.notify(title=title, message=message, app_name=app_name, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"Failed to show toast notification: {str(e)}")
            logger.info(
                f"Toast notification would show: {kwargs.get('title')} - " f"{kwargs.get('msg')}"
            )
            return False
