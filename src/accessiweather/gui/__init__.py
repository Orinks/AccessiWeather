"""GUI Components for AccessiWeather

This package contains all graphical user interface components for the
application.
"""

# Define exported symbols
__all__ = [
    'AdvancedLocationDialog', 'LocationDialog', 'WeatherDiscussionDialog',
    'AccessibleStaticText', 'AccessibleTextCtrl', 'AccessibleChoice',
    'AccessibleButton', 'AccessibleListCtrl', 'WeatherApp',
    'UPDATE_INTERVAL'
]

# Import dialog classes
from .dialogs import (
    AdvancedLocationDialog,
    LocationDialog,
    WeatherDiscussionDialog
)

# Import UI components
from .ui_components import (
    AccessibleStaticText,
    AccessibleTextCtrl,
    AccessibleChoice,
    AccessibleButton,
    AccessibleListCtrl
)

# Import WeatherApp last to avoid circular import issues
from .weather_app import WeatherApp

# Constants
UPDATE_INTERVAL = 1800  # 30 minutes in seconds

# Version
__version__ = '1.0.0'
