"""AccessiWeather NOAA API Client

This module provides access to NOAA weather data through their public APIs.
"""

# Re-export the unified client and related classes for backward compatibility
from accessiweather.api.unified_client import NoaaApiClient
from accessiweather.api.exceptions import ApiClientError, NoaaApiError
from accessiweather.api.constants import (
    LOCATION_TYPE_COUNTY,
    LOCATION_TYPE_FORECAST,
    LOCATION_TYPE_FIRE,
    LOCATION_TYPE_STATE,
)

# Export all the classes and constants for backward compatibility
__all__ = [
    "NoaaApiClient",
    "ApiClientError",
    "NoaaApiError",
    "LOCATION_TYPE_COUNTY",
    "LOCATION_TYPE_FORECAST",
    "LOCATION_TYPE_FIRE",
    "LOCATION_TYPE_STATE",
]
