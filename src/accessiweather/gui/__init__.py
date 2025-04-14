"""GUI Components for AccessiWeather

This package contains all graphical user interface components for the
application.
"""

# Define exported symbols
__all__ = [
    "AdvancedLocationDialog",
    "LocationDialog",
    "WeatherDiscussionDialog",
    "AlertDetailsDialog",
    "AccessibleStaticText",
    "AccessibleTextCtrl",
    "AccessibleChoice",
    "AccessibleButton",
    "AccessibleListCtrl",
    "WeatherApp",
    "AccessiWeatherApp",
]

# Import app classes last to avoid circular import issues
from .app import AccessiWeatherApp

# Import dialog classes
from .dialogs import AdvancedLocationDialog, LocationDialog, WeatherDiscussionDialog
from .alert_dialog import AlertDetailsDialog

# Import UI components
from .ui_components import (
    AccessibleButton,
    AccessibleChoice,
    AccessibleListCtrl,
    AccessibleStaticText,
    AccessibleTextCtrl,
)
from .weather_app import WeatherApp

# Constants (UPDATE_INTERVAL moved to accessiweather.constants)

# Version
__version__ = "0.9.0"
