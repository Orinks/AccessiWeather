"""Notification package for AccessiWeather.

This package provides functionality for weather alert notifications,
including display, processing, and persistence of alert data.
"""

from .alert_persistence import AlertPersistenceManager
from .alert_processor import AlertProcessor
from .notification_display import NotificationDisplayManager, SafeToastNotifier

# Re-export the main WeatherNotifier class for backward compatibility
from .weather_notifier import WeatherNotifier

__all__ = [
    "WeatherNotifier",
    "SafeToastNotifier",
    "NotificationDisplayManager",
    "AlertProcessor",
    "AlertPersistenceManager",
]
