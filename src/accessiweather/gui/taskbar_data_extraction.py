"""Taskbar data extraction utilities for AccessiWeather.

This module provides functions for extracting weather data from different APIs
and formatting it for use in taskbar icons.
"""

import logging

from .weather_formatting import (
    convert_wind_direction_to_cardinal,
    create_standardized_taskbar_data,
    format_combined_wind,
    safe_get_location_name,
)
from .weather_source_detection import get_temperature_unit_preference
from accessiweather.utils.temperature_utils import format_temperature
from accessiweather.utils.unit_utils import format_pressure, format_wind_speed

logger = logging.getLogger(__name__)


def extract_weatherapi_data_for_taskbar(conditions_data, frame):
    """Extract relevant data from WeatherAPI.com conditions for the taskbar icon.

    Args:
        conditions_data: WeatherAPI.com current conditions data
        frame: The main WeatherApp frame instance

    Returns:
        dict: Standardized taskbar data dictionary
    """
    logger.debug("Extracting WeatherAPI.com data for taskbar")

    if not conditions_data or "current" not in conditions_data:
        logger.warning("Invalid WeatherAPI.com conditions data for taskbar extraction")
        return create_standardized_taskbar_data()

    current = conditions_data["current"]
    location_data = conditions_data.get("location", {})

    # Get user's temperature unit preference
    unit_pref = get_temperature_unit_preference(frame)

    # Extract temperature data
    temp_f = current.get("temp_f")
    temp_c = current.get("temp_c")
    feels_like_f = current.get("feelslike_f")
    feels_like_c = current.get("feelslike_c")

    # Format temperature based on user preference
    temp_str = ""
    if temp_f is not None and temp_c is not None:
        temp_str = format_temperature(
            temp_f,
            unit_pref,
            temperature_c=temp_c,
            precision=0 if unit_pref.value == "both" else 1,
        )

    feels_like_str = ""
    if feels_like_f is not None and feels_like_c is not None:
        feels_like_str = format_temperature(
            feels_like_f,
            unit_pref,
            temperature_c=feels_like_c,
            precision=0 if unit_pref.value == "both" else 1,
        )

    # Extract other weather data
    condition = current.get("condition", {}).get("text", "")
    weather_code = current.get("condition", {}).get("code")
    wind_speed = current.get("wind_mph")
    wind_dir = current.get("wind_dir", "")
    humidity = current.get("humidity")
    pressure = current.get("pressure_in")
    uv = current.get("uv")
    visibility = current.get("vis_miles")
    precip = current.get("precip_in")

    # Format wind information
    wind_str = format_combined_wind(wind_speed, wind_dir, "mph")

    # Get location name
    location_name = location_data.get("name", "")
    if not location_name:
        location_name = safe_get_location_name(
            getattr(frame, "weather_service", {}).get("location_service") if hasattr(frame, "weather_service") else None,
            fallback="Unknown Location"
        )

    return create_standardized_taskbar_data(
        temp=temp_str,
        temp_f=temp_f,
        temp_c=temp_c,
        feels_like=feels_like_str,
        feels_like_f=feels_like_f,
        feels_like_c=feels_like_c,
        condition=condition,
        weather_code=weather_code,
        wind_speed=wind_speed,
        wind_dir=wind_dir,
        wind=wind_str,
        humidity=humidity,
        pressure=pressure,
        uv=uv,
        visibility=visibility,
        precip=precip,
        location=location_name,
    )


def extract_nws_data_for_taskbar(conditions_data, frame):
    """Extract relevant data from NWS API conditions for the taskbar icon.

    Args:
        conditions_data: NWS API current conditions data
        frame: The main WeatherApp frame instance

    Returns:
        dict: Standardized taskbar data dictionary
    """
    logger.debug("Extracting NWS data for taskbar")

    if not conditions_data or "properties" not in conditions_data:
        logger.warning("Invalid NWS conditions data for taskbar extraction")
        return create_standardized_taskbar_data()

    properties = conditions_data["properties"]

    # Get user's temperature unit preference
    unit_pref = get_temperature_unit_preference(frame)

    # Extract temperature data
    temperature = properties.get("temperature", {}).get("value")
    temp_unit_code = properties.get("temperature", {}).get("unitCode", "")

    # Convert temperature if needed
    temp_f = None
    temp_c = None
    if temperature is not None:
        if "degF" in temp_unit_code:
            # Temperature is already in Fahrenheit
            temp_f = temperature
            temp_c = (temperature - 32) * 5 / 9
        else:
            # Temperature is in Celsius, convert to Fahrenheit
            temp_f = (temperature * 9 / 5) + 32
            temp_c = temperature

    # Format temperature based on user preference
    temp_str = ""
    if temp_f is not None and temp_c is not None:
        temp_str = format_temperature(
            temp_f,
            unit_pref,
            temperature_c=temp_c,
            precision=0 if unit_pref.value == "both" else 1,
        )

    # Extract other weather data
    condition = properties.get("textDescription", "")
    
    # Wind data
    wind_speed_raw = properties.get("windSpeed", {}).get("value")
    wind_direction_raw = properties.get("windDirection", {}).get("value")
    
    # Convert wind speed to mph if needed
    wind_speed = None
    if wind_speed_raw is not None:
        wind_speed_unit = properties.get("windSpeed", {}).get("unitCode", "")
        if "km_h" in wind_speed_unit:
            # Convert km/h to mph
            wind_speed = wind_speed_raw * 0.621371
        else:
            # Assume mph
            wind_speed = wind_speed_raw

    # Convert wind direction to cardinal
    wind_dir = convert_wind_direction_to_cardinal(wind_direction_raw) if wind_direction_raw else ""

    # Format wind information
    wind_str = format_combined_wind(wind_speed, wind_dir, "mph")

    # Other weather data
    humidity = properties.get("relativeHumidity", {}).get("value")
    pressure_raw = properties.get("barometricPressure", {}).get("value")
    
    # Convert pressure to inHg if needed
    pressure = None
    if pressure_raw is not None:
        pressure_unit = properties.get("barometricPressure", {}).get("unitCode", "")
        if "Pa" in pressure_unit:
            # Convert Pa to inHg
            pressure = pressure_raw * 0.0002953
        else:
            # Assume inHg
            pressure = pressure_raw

    visibility_raw = properties.get("visibility", {}).get("value")
    visibility = None
    if visibility_raw is not None:
        visibility_unit = properties.get("visibility", {}).get("unitCode", "")
        if "m" in visibility_unit:
            # Convert meters to miles
            visibility = visibility_raw * 0.000621371
        else:
            # Assume miles
            visibility = visibility_raw

    # Get location name
    location_name = safe_get_location_name(
        getattr(frame, "weather_service", {}).get("location_service") if hasattr(frame, "weather_service") else None,
        fallback="Unknown Location"
    )

    return create_standardized_taskbar_data(
        temp=temp_str,
        temp_f=temp_f,
        temp_c=temp_c,
        condition=condition,
        wind_speed=wind_speed,
        wind_dir=wind_dir,
        wind=wind_str,
        humidity=humidity,
        pressure=pressure,
        visibility=visibility,
        location=location_name,
    )
