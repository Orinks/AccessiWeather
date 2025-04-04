"""GUI Components for AccessiWeather.

This package contains all graphical user interface components for the
application.
"""

# Define exported symbols
__all__ = [
    "AdvancedLocationDialog",
    "LocationDialog",
    "WeatherDiscussionDialog",
    "AccessibleStaticText",
    "AccessibleTextCtrl",
    "AccessibleChoice",
    "AccessibleButton",
    "AccessibleListCtrl",
    "WeatherApp",
]

from .accessible_widgets import (  # noqa: E402
    AccessibleButton,
    AccessibleChoice,
    AccessibleListCtrl,
    AccessibleStaticText,
    AccessibleTextCtrl,
)
from .dialogs import AdvancedLocationDialog, LocationDialog, WeatherDiscussionDialog  # noqa: E402
from .weather_app import WeatherApp  # noqa: E402

# Constants (UPDATE_INTERVAL moved to accessiweather.constants)

# Version
__version__ = "1.0.0"
