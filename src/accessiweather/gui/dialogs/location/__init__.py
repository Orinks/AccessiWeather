"""
Location dialog components package for AccessiWeather.

This package provides modular components for location-related dialogs,
organized by functionality for better maintainability and separation of concerns.

The package includes:
- dialog_components: Main dialog classes for location input and search
- input_validators: Validation utilities for location input fields
- geocoding_manager: Geocoding service integration and search management
- constants: Configuration values and UI text constants

This refactoring maintains full backward compatibility with the original
location_dialogs.py module while providing better code organization.
"""

# Import main dialog classes for backward compatibility
from .dialog_components import AdvancedLocationDialog, LocationDialog

# Import validation utilities for advanced usage
from .input_validators import (
    AdvancedDialogValidator,
    CoordinateValidator,
    LocationDialogValidator,
    LocationInputValidator,
    ValidationErrorHandler,
)

# Import geocoding management components for advanced usage
from .geocoding_manager import (
    GeocodingSearchManager,
    LocationSearchResultProcessor,
    SearchHistoryManager,
    SearchResultHandler,
)

# Import constants for configuration
from .constants import (
    ADVANCED_DIALOG_TITLE,
    CUSTOM_COORDINATES_FORMAT,
    DEFAULT_DATA_SOURCE,
    EMPTY_NAME_ERROR,
    FOUND_RESULT_FORMAT,
    GEOCODING_TIMEOUT,
    INVALID_NUMBERS_ERROR,
    LATITUDE_RANGE_ERROR,
    LOCATION_DIALOG_TITLE,
    LONGITUDE_RANGE_ERROR,
    MAX_HISTORY_ITEMS,
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    NO_COORDINATES_ERROR,
    VALIDATION_ERROR_TITLE,
)

# Define public API for backward compatibility
__all__ = [
    # Main dialog classes (primary public API)
    "AdvancedLocationDialog",
    "LocationDialog",
    
    # Validation utilities
    "AdvancedDialogValidator",
    "CoordinateValidator", 
    "LocationDialogValidator",
    "LocationInputValidator",
    "ValidationErrorHandler",
    
    # Geocoding management
    "GeocodingSearchManager",
    "LocationSearchResultProcessor", 
    "SearchHistoryManager",
    "SearchResultHandler",
    
    # Configuration constants
    "ADVANCED_DIALOG_TITLE",
    "CUSTOM_COORDINATES_FORMAT",
    "DEFAULT_DATA_SOURCE",
    "EMPTY_NAME_ERROR",
    "FOUND_RESULT_FORMAT", 
    "GEOCODING_TIMEOUT",
    "INVALID_NUMBERS_ERROR",
    "LATITUDE_RANGE_ERROR",
    "LOCATION_DIALOG_TITLE",
    "LONGITUDE_RANGE_ERROR",
    "MAX_HISTORY_ITEMS",
    "MAX_LATITUDE",
    "MAX_LONGITUDE",
    "MIN_LATITUDE",
    "MIN_LONGITUDE",
    "NO_COORDINATES_ERROR",
    "VALIDATION_ERROR_TITLE",
]
