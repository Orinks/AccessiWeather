"""Main GUI module for NOAA Weather App

This module provides the main application window and GUI components.
It integrates accessibility features for screen readers.

Note: This file now serves as a compatibility layer importing from the 
modular gui package structure.
"""

# Re-export all components from the modular gui package
from noaa_weather_app.gui import (
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
from noaa_weather_app.api_client import NoaaApiClient
from noaa_weather_app.notifications import WeatherNotifier
from noaa_weather_app.location import LocationManager
from noaa_weather_app.geocoding import GeocodingService

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
