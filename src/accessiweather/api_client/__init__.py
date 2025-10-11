"""
API Client package for AccessiWeather.

This package contains modular API client components extracted from the original
large api_client.py file for better maintainability and separation of concerns.
"""

from .core_client import NoaaApiClient

# Re-export location type constants for backward compatibility
from .exceptions import (
    LOCATION_TYPE_COUNTY,
    LOCATION_TYPE_FIRE,
    LOCATION_TYPE_FORECAST,
    LOCATION_TYPE_STATE,
    ApiClientError,
    NoaaApiError,
)

__all__ = [
    "ApiClientError",
    "NoaaApiError",
    "NoaaApiClient",
    "LOCATION_TYPE_COUNTY",
    "LOCATION_TYPE_FORECAST",
    "LOCATION_TYPE_FIRE",
    "LOCATION_TYPE_STATE",
]
