"""Notification module for NOAA weather alerts, watches, and warnings.

This module provides functionality to display desktop notifications
for weather alerts.

This module has been refactored for better maintainability. The actual
implementation is now in the notifications package.
"""

# Import from the new modular structure for backward compatibility
from .notifications import SafeToastNotifier, WeatherNotifier

__all__ = ["SafeToastNotifier", "WeatherNotifier"]
