"""Dialog components for AccessiWeather

This package contains dialog windows for user interaction.
Refactored from the original dialogs.py file for better maintainability
and separation of concerns.
"""

# Import dialog classes from the refactored modules
from .location_dialogs import AdvancedLocationDialog, LocationDialog
from .discussion_dialogs import WeatherDiscussionDialog, NationalDiscussionDialog

# Define exported symbols for backward compatibility
__all__ = [
    "AdvancedLocationDialog",
    "LocationDialog",
    "WeatherDiscussionDialog",
    "NationalDiscussionDialog",
]
