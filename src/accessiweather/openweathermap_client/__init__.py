"""OpenWeatherMap API client package.

This package provides a comprehensive OpenWeatherMap API client implementation
with support for current weather, forecasts, and weather alerts.
"""

from .client import OpenWeatherMapClient
from .exceptions import (
    OpenWeatherMapError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "OpenWeatherMapClient",
    "OpenWeatherMapError",
    "AuthenticationError", 
    "RateLimitError",
    "NotFoundError",
    "ValidationError",
]
