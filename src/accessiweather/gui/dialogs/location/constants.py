"""
Constants and configuration values for location dialog components.

This module centralizes all constants, default values, UI text, and configuration
settings used throughout the location dialog system.
"""

# Dialog titles and labels
ADVANCED_DIALOG_TITLE = "Advanced Location Options"
LOCATION_DIALOG_TITLE = "Add Location"

# UI Labels and text
LATITUDE_LABEL = "Latitude:"
LONGITUDE_LABEL = "Longitude:"
LOCATION_NAME_LABEL = "Location Name:"
SEARCH_BUTTON_TEXT = "Search"
ADVANCED_BUTTON_TEXT = "Advanced (Lat/Lon)"
SAVE_BUTTON_TEXT = "Save"
CANCEL_BUTTON_TEXT = "Cancel"

# Help text
LOCATION_HELP_TEXT = (
    "Enter a location name (e.g., 'New York, NY' or 'Chicago') and click Search. "
    "You can also use the Advanced button to enter latitude and longitude coordinates directly."
)

# Search results
SEARCH_RESULTS_LABEL = "Search Results:"
SEARCH_RESULTS_COLUMNS = ["Location", "Coordinates"]

# Validation messages
VALIDATION_ERROR_TITLE = "Validation Error"
LATITUDE_RANGE_ERROR = "Latitude must be between -90 and 90 degrees"
LONGITUDE_RANGE_ERROR = "Longitude must be between -180 and 180 degrees"
INVALID_NUMBERS_ERROR = "Please enter valid numbers for latitude and longitude"
EMPTY_NAME_ERROR = "Please enter a name for the location"
NO_COORDINATES_ERROR = "Please search for a location or enter coordinates manually"

# Coordinate validation limits
MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0

# Search configuration
MAX_HISTORY_ITEMS = 10
GEOCODING_TIMEOUT = 15  # seconds

# UI sizing
SEARCH_RESULTS_HEIGHT = 150
DIALOG_BORDER = 10
BUTTON_BORDER = 5
TEXT_CTRL_MIN_WIDTH = 100
TEXT_CTRL_MIN_HEIGHT = 60

# Result text formatting
FOUND_RESULT_FORMAT = "Found: {address}\nCoordinates: {lat}, {lon}"
CUSTOM_COORDINATES_FORMAT = "Custom coordinates: {lat}, {lon}"

# Threading and search
SEARCH_THREAD_JOIN_TIMEOUT = 0.5  # seconds

# Default values
DEFAULT_LAT = None
DEFAULT_LON = None
DEFAULT_LOCATION_NAME = ""
DEFAULT_DATA_SOURCE = "nws"
