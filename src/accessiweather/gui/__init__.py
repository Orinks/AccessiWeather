"""GUI Components for NOAA Weather App

This package contains all graphical user interface components for the application.
It provides backward-compatible imports for existing code.
"""

# Import dialog classes
from .dialogs import AdvancedLocationDialog, LocationDialog, WeatherDiscussionDialog

# Import UI components
from .ui_components import (
    AccessibleStaticText,
    AccessibleTextCtrl, 
    AccessibleChoice,
    AccessibleButton,
    AccessibleListCtrl
)

# Re-export dependencies for backward compatibility with tests
# We don't import these directly to avoid circular imports
from accessiweather.api_client import NoaaApiClient
from accessiweather.notifications import WeatherNotifier
from accessiweather.location import LocationManager
from accessiweather.geocoding import GeocodingService

# Import WeatherApp last to avoid circular import issues
from .weather_app import WeatherApp

# Constants
UPDATE_INTERVAL = 1800  # 30 minutes in seconds

# Version
__version__ = '1.0.0'
