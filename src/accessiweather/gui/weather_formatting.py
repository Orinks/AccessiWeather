"""Weather data formatting utilities for AccessiWeather.

This module provides utility functions for formatting weather data from different APIs
and converting between units and formats.
"""

import logging

from accessiweather.utils.temperature_utils import TemperatureUnit

logger = logging.getLogger(__name__)


def convert_wind_direction_to_cardinal(degrees):
    """Convert wind direction from degrees to cardinal direction.

    Args:
        degrees: Wind direction in degrees (0-360)

    Returns:
        str: Cardinal direction (N, NE, E, SE, S, SW, W, NW)
    """
    if degrees is None:
        logger.debug("Wind direction conversion: degrees is None")
        return ""

    try:
        degrees = float(degrees)
        logger.debug(f"Wind direction conversion: input {degrees}°")

        # Normalize to 0-360 range
        degrees = degrees % 360

        # Define cardinal directions with their degree ranges
        directions = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]

        # Each direction covers 22.5 degrees (360/16)
        index = int((degrees + 11.25) / 22.5) % 16
        cardinal = directions[index]
        logger.debug(f"Wind direction conversion: {degrees}° -> {cardinal}")
        return cardinal
    except (ValueError, TypeError) as e:
        logger.warning(f"Wind direction conversion failed for value '{degrees}': {e}")
        return ""


def format_combined_wind(wind_speed, wind_direction, speed_unit="mph"):
    """Format combined wind speed and direction for display.

    Args:
        wind_speed: Wind speed value
        wind_direction: Wind direction (degrees or cardinal)
        speed_unit: Unit for wind speed display

    Returns:
        str: Formatted wind string (e.g., "15 mph NW")
    """
    logger.debug(
        f"Wind formatting: speed={wind_speed}, direction={wind_direction}, unit={speed_unit}"
    )

    if wind_speed is None:
        logger.debug("Wind formatting: speed is None, returning empty string")
        return ""

    try:
        speed_val = float(wind_speed)
        logger.debug(f"Wind formatting: parsed speed value {speed_val}")

        if speed_val == 0:
            logger.debug("Wind formatting: speed is 0, returning 'Calm'")
            return "Calm"

        # Format speed to whole number
        speed_str = f"{int(round(speed_val))} {speed_unit}"
        logger.debug(f"Wind formatting: formatted speed '{speed_str}'")

        # Handle direction
        if isinstance(wind_direction, (int, float)):
            direction = convert_wind_direction_to_cardinal(wind_direction)
        else:
            direction = str(wind_direction) if wind_direction else ""

        logger.debug(f"Wind formatting: processed direction '{direction}'")

        if direction:
            result = f"{speed_str} {direction}"
        else:
            result = speed_str

        logger.debug(f"Wind formatting: final result '{result}'")
        return result
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Wind formatting failed for speed='{wind_speed}', direction='{wind_direction}': {e}"
        )
        return ""


def safe_get_location_name(location_service=None, fallback=""):
    """Safely get location name with thread safety.

    Args:
        location_service: Location service instance
        fallback: Fallback value if location cannot be retrieved

    Returns:
        str: Location name or fallback value
    """
    logger.debug(
        f"Location name retrieval: service={location_service is not None}, fallback='{fallback}'"
    )

    if not location_service:
        logger.debug("Location name retrieval: no location service provided")
        return fallback

    try:
        # Use the proper method to get current location name
        if hasattr(location_service, "get_current_location_name"):
            location_name = location_service.get_current_location_name()
            logger.debug(
                f"Location name retrieval: got '{location_name}' from get_current_location_name()"
            )
            return location_name if location_name is not None else fallback
        else:
            logger.debug(
                "Location name retrieval: location service has no get_current_location_name method"
            )
            return fallback
    except Exception as e:
        logger.error(f"Location name retrieval failed: {e}")
        return fallback


def create_standardized_taskbar_data(**kwargs):
    """Create a standardized dictionary structure for taskbar data.

    This ensures all API extraction methods return the same keys with consistent data types.

    Args:
        **kwargs: Key-value pairs for weather data

    Returns:
        dict: Standardized dictionary with all expected keys
    """
    # Define the standard structure with default values
    standard_data = {
        # Temperature data
        "temp": None,
        "temp_f": None,
        "temp_c": None,
        "feels_like": None,
        "feels_like_f": None,
        "feels_like_c": None,
        # Weather condition
        "condition": "",
        "weather_code": None,  # Weather code for dynamic format management
        # Wind data
        "wind_speed": None,
        "wind_dir": "",
        "wind": "",  # Combined wind placeholder
        # Other weather data
        "humidity": None,
        "pressure": None,
        "uv": None,
        "visibility": None,
        "precip": None,
        # Location
        "location": "",
    }

    # Update with provided values
    for key, value in kwargs.items():
        if key in standard_data:
            standard_data[key] = value
        else:
            # Log unexpected keys for debugging
            logger.debug(f"Unexpected key in taskbar data: {key}")

    return standard_data


def get_temperature_precision(unit_pref: TemperatureUnit) -> int:
    """Get the appropriate precision for temperature formatting.

    Args:
        unit_pref: The temperature unit preference

    Returns:
        int: Precision (0 for whole numbers when 'both', 1 otherwise)
    """
    return 0 if unit_pref == TemperatureUnit.BOTH else 1


def is_weatherapi_data(data):
    """Detect if the data is from WeatherAPI.com based on its structure.

    Args:
        data: Weather data dictionary

    Returns:
        bool: True if data appears to be from WeatherAPI.com
    """
    if not isinstance(data, dict):
        return False

    # Check for WeatherAPI.com specific structure
    # WeatherAPI.com forecast data has 'forecast' key with 'forecastday' array
    if "forecast" in data and "forecastday" in data.get("forecast", {}):
        return True

    # WeatherAPI.com current conditions have 'current' key with specific fields
    if "current" in data:
        current = data["current"]
        # Check for WeatherAPI.com specific fields
        if any(key in current for key in ["temp_c", "temp_f", "condition", "wind_kph"]):
            return True

    # WeatherAPI.com alerts have 'alerts' key with 'alert' array
    if "alerts" in data and "alert" in data.get("alerts", {}):
        return True

    return False
