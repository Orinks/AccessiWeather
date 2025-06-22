"""Notification module for NOAA weather alerts, watches, and warnings.

This module provides functionality to display desktop notifications
for weather alerts.
"""

from .toast_notifier import SafeToastNotifier
from .weather_notifier import WeatherNotifier

__all__ = ["SafeToastNotifier", "WeatherNotifier"]
