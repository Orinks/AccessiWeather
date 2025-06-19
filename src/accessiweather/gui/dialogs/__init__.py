"""Dialog components for AccessiWeather

This package contains dialog windows for user interaction.
Refactored from the original dialogs.py file for better maintainability
and separation of concerns.
"""

from .discussion_dialogs import NationalDiscussionDialog, WeatherDiscussionDialog

# Import dialog classes from the refactored modules
from .location_dialogs import AdvancedLocationDialog, LocationDialog

# Define exported symbols for backward compatibility
__all__ = [
    "AdvancedLocationDialog",
    "LocationDialog",
    "WeatherDiscussionDialog",
    "NationalDiscussionDialog",
]
