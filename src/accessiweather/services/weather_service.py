"""Weather service for AccessiWeather.

This module provides a service layer for weather-related operations,
separating business logic from UI concerns.

This module now serves as a compatibility layer, importing the refactored
WeatherService from the weather_service package.
"""

# Import the refactored WeatherService and ConfigurationError for backward compatibility
from .weather_service.weather_service import ConfigurationError, WeatherService

# Also import ApiClientError for backward compatibility
from accessiweather.api_client import ApiClientError

# Re-export for backward compatibility
__all__ = ["WeatherService", "ConfigurationError", "ApiClientError"]