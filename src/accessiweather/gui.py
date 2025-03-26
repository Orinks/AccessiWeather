"""Main GUI module for AccessiWeather

This module provides the main application window and GUI components.
It integrates accessibility features for screen readers.

Note: This file now serves as a compatibility layer importing from the
modular gui package structure.
"""

# Re-export all components from the modular gui package
from accessiweather.gui import (
    # Dialog classes
    AdvancedLocationDialog,
    LocationDialog,
    WeatherDiscussionDialog,
    
    # Main application class
    WeatherApp,
    
    # UI components
    AccessibleStaticText,
    AccessibleTextCtrl,
    AccessibleChoice,
    AccessibleButton,
    AccessibleListCtrl,
    
    # Constants
    UPDATE_INTERVAL
)

# Re-export dependencies for backward compatibility with tests
from accessiweather.api_client import NoaaApiClient
from accessiweather.notifications import WeatherNotifier
from accessiweather.location import LocationManager
from accessiweather.geocoding import GeocodingService

# Make all imports available at module level for backward compatibility
__all__ = [
    'AdvancedLocationDialog',
    'LocationDialog',
    'WeatherDiscussionDialog',
    'WeatherApp',
    'AccessibleStaticText',
    'AccessibleTextCtrl',
    'AccessibleChoice',
    'AccessibleButton',
    'AccessibleListCtrl',
    'NoaaApiClient',
    'WeatherNotifier',
    'LocationManager',
    'GeocodingService',
    'UPDATE_INTERVAL'
]
