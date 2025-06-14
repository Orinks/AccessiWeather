"""Dialog components for AccessiWeather

This module provides dialog windows for user interaction.
"""

# Re-export dialog classes for backward compatibility
from .dialogs.advanced_location_dialog import AdvancedLocationDialog
from .dialogs.location_dialog import LocationDialog
from .dialogs.national_discussion_dialog import NationalDiscussionDialog
from .dialogs.weather_discussion_dialog import WeatherDiscussionDialog

# Export all dialog classes for backward compatibility
__all__ = [
    "AdvancedLocationDialog",
    "LocationDialog",
    "NationalDiscussionDialog",
    "WeatherDiscussionDialog",
]
