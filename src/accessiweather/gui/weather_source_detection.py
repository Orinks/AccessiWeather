"""Weather source detection utilities for AccessiWeather.

This module provides functions for detecting which weather API is being used
and determining appropriate UI behavior based on the weather source.
"""

import logging

from accessiweather.gui.settings_dialog import DEFAULT_TEMPERATURE_UNIT, TEMPERATURE_UNIT_KEY
from accessiweather.utils.temperature_utils import TemperatureUnit

logger = logging.getLogger(__name__)


def get_temperature_unit_preference(frame):
    """Get the user's temperature unit preference from config.

    Args:
        frame: The main WeatherApp frame instance

    Returns:
        TemperatureUnit: The user's temperature unit preference
    """
    if not hasattr(frame, "config"):
        return TemperatureUnit.FAHRENHEIT

    settings = frame.config.get("settings", {})
    unit_pref = settings.get(TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT)

    # Convert string to enum
    if unit_pref == TemperatureUnit.FAHRENHEIT.value:
        return TemperatureUnit.FAHRENHEIT
    elif unit_pref == TemperatureUnit.CELSIUS.value:
        return TemperatureUnit.CELSIUS
    elif unit_pref == TemperatureUnit.BOTH.value:
        return TemperatureUnit.BOTH
    else:
        return TemperatureUnit.FAHRENHEIT


def is_using_openmeteo(frame) -> bool:
    """Determine if the current location is using Open-Meteo as the weather source.

    Args:
        frame: The main WeatherApp frame instance

    Returns:
        bool: True if using Open-Meteo, False otherwise
    """
    try:
        # Check if we have a weather service and location service
        if hasattr(frame, "weather_service") and frame.weather_service:
            weather_service = frame.weather_service
            if hasattr(weather_service, "location_service") and weather_service.location_service:
                location_service = weather_service.location_service
                
                # Get current location
                current_location = location_service.get_current_location()
                if current_location:
                    lat, lon = current_location
                    
                    # Check the weather source for this location
                    if hasattr(weather_service, "get_weather_source_for_location"):
                        source = weather_service.get_weather_source_for_location(lat, lon)
                        logger.debug(f"Weather source for location ({lat}, {lon}): {source}")
                        return source == "openmeteo"

        # Fallback: check config directly
        from accessiweather.gui.settings_dialog import DATA_SOURCE_AUTO, DATA_SOURCE_OPENMETEO

        data_source = frame.config.get("settings", {}).get("data_source", "nws")

        if data_source == DATA_SOURCE_OPENMETEO:
            return True
        elif data_source == DATA_SOURCE_AUTO:
            # For auto mode, check if location is outside US
            from accessiweather.geocoding import GeocodingService

            # Get current location
            if hasattr(frame, "weather_service") and frame.weather_service:
                weather_service = frame.weather_service
                if hasattr(weather_service, "location_service") and weather_service.location_service:
                    location_service = weather_service.location_service
                    current_location = location_service.get_current_location()
                    if current_location:
                        lat, lon = current_location
                        
                        geocoding_service = GeocodingService(
                            user_agent="AccessiWeather-UIManager", data_source="auto"
                        )
                        is_us = geocoding_service.validate_coordinates(lat, lon, us_only=True)
                        return not is_us

        return False

    except Exception as e:
        logger.warning(f"Error determining weather source: {e}")
        return False


def format_error_message(error):
    """Format an error message based on the error type.

    Args:
        error: Error message or exception object

    Returns:
        str: Formatted error message
    """
    from accessiweather.api_client import ApiClientError, NoaaApiError
    
    if isinstance(error, NoaaApiError):
        if error.error_type == "rate_limit":
            return "Rate limit exceeded. Please try again in a few moments."
        elif error.error_type == "network":
            return "Network error. Please check your internet connection."
        elif error.error_type == "server":
            return "Server error. The weather service may be temporarily unavailable."
        elif error.error_type == "not_found":
            return "Weather data not found for this location."
        elif error.error_type == "timeout":
            return "Request timed out. Please try again."
        else:
            return f"Weather service error: {error.message}"
    elif isinstance(error, ApiClientError):
        return f"API error: {str(error)}"
    elif isinstance(error, Exception):
        return str(error)
    else:
        return str(error)
