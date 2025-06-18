"""API Client compatibility layer for AccessiWeather.

This module provides backward compatibility for imports from the original api_client.py file.
The actual implementation has been refactored into the api_client package for better
maintainability and separation of concerns.

This compatibility layer re-exports all classes and constants from the new package structure
to ensure existing code continues to work without modification.
"""

import warnings

# Import all classes and constants from the new api_client package
from .api_client import (
    LOCATION_TYPE_COUNTY,
    LOCATION_TYPE_FIRE,
    LOCATION_TYPE_FORECAST,
    LOCATION_TYPE_STATE,
    ApiClientError,
    NoaaApiClient,
    NoaaApiError,
)

# Re-export everything for backward compatibility
__all__ = [
    "ApiClientError",
    "NoaaApiError",
    "NoaaApiClient",
    "LOCATION_TYPE_COUNTY",
    "LOCATION_TYPE_FORECAST",
    "LOCATION_TYPE_FIRE",
    "LOCATION_TYPE_STATE",
]

# Optional: Issue a deprecation warning for direct imports from this module
# Uncomment the following lines if you want to encourage migration to the new package structure
# warnings.warn(
#     "Importing from 'accessiweather.api_client' is deprecated. "
#     "Please import from 'accessiweather.api_client' package instead.",
#     DeprecationWarning,
#     stacklevel=2
# )
