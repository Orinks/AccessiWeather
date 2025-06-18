"""Weather service package for AccessiWeather.

This package provides a service layer for weather-related operations,
separating business logic from UI concerns.
"""

from .weather_service import WeatherService

__all__ = ["WeatherService"]
