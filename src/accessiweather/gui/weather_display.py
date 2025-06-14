"""Weather data display utilities for AccessiWeather.

This module provides functions for displaying weather data in the UI,
including formatting and presenting forecast, current conditions, and alerts.
"""

import logging
from typing import Any, Dict, List, Optional

from accessiweather.utils.temperature_utils import format_temperature

from .taskbar_data_extraction import (
    extract_nws_data_for_taskbar,
    extract_weatherapi_data_for_taskbar,
)
from .weather_formatting import format_combined_wind, get_temperature_precision, is_weatherapi_data
from .weather_source_detection import format_error_message, get_temperature_unit_preference

logger = logging.getLogger(__name__)


def display_loading_state(frame, location_name=None, is_nationwide=False):
    """Display loading state in the UI.

    Args:
        frame: The main WeatherApp frame instance
        location_name: Optional location name for status text
        is_nationwide: Whether this is a nationwide forecast
    """
    # Disable refresh button
    frame.refresh_btn.Disable()

    # Set loading text based on type
    loading_text = "Loading nationwide forecast..." if is_nationwide else "Loading forecast..."
    frame.forecast_text.SetValue(loading_text)

    # Set loading text for current conditions
    if not is_nationwide:
        frame.current_conditions_text.SetValue("Loading current conditions...")
    else:
        frame.current_conditions_text.SetValue(
            "Current conditions not available for nationwide view"
        )

    # Clear and set loading text in alerts list
    frame.alerts_list.DeleteAllItems()
    frame.alerts_list.InsertItem(0, "Loading alerts...")

    # Set status text
    if location_name:
        status = f"Updating weather data for {location_name}..."
        if is_nationwide:
            status = "Updating nationwide weather data..."
    else:
        status = "Updating weather data..."
    frame.SetStatusText(status)


def display_ready_state(frame):
    """Display ready state in the UI.

    Args:
        frame: The main WeatherApp frame instance
    """
    frame.refresh_btn.Enable()
    frame.SetStatusText("Ready")


def display_forecast_error(frame, error):
    """Display forecast error in the UI.

    Args:
        frame: The main WeatherApp frame instance
        error: Error message or exception object
    """
    error_msg = format_error_message(error)
    frame.forecast_text.SetValue(f"Error fetching forecast: {error_msg}")
    frame.current_conditions_text.SetValue("Error fetching current conditions")


def display_current_conditions(frame, conditions_data):
    """Display current weather conditions in the UI.

    Args:
        frame: The main WeatherApp frame instance
        conditions_data: Dictionary with current conditions data
    """
    logger.debug(f"display_current_conditions received: {conditions_data}")

    if not conditions_data:
        frame.current_conditions_text.SetValue("No current conditions data available")
        return

    # Check if this is WeatherAPI.com data
    if is_weatherapi_data(conditions_data):
        try:
            text = format_weatherapi_current_conditions(conditions_data, frame)
            frame.current_conditions_text.SetValue(text)

            # Extract data for taskbar icon
            taskbar_data = extract_weatherapi_data_for_taskbar(conditions_data, frame)

            # Update taskbar icon with weather data
            if hasattr(frame, "taskbar_icon") and frame.taskbar_icon:
                frame.taskbar_icon.update_weather_data(taskbar_data)

            return
        except Exception as e:
            logger.exception("Error formatting WeatherAPI.com current conditions")
            frame.current_conditions_text.SetValue(f"Error formatting current conditions: {e}")
            return

    # Handle NWS API data
    if "properties" not in conditions_data:
        frame.current_conditions_text.SetValue("Invalid current conditions data")
        return

    properties = conditions_data["properties"]

    # Get user's temperature unit preference
    unit_pref = get_temperature_unit_preference(frame)

    # Extract temperature
    temperature = properties.get("temperature", {}).get("value")
    if temperature is not None:
        # Convert units if needed - check the actual unit codes from the API
        temp_unit_code = properties.get("temperature", {}).get("unitCode", "")
        if "degF" in temp_unit_code:
            # Temperature is already in Fahrenheit
            temperature_f = temperature
            temperature_c = (temperature - 32) * 5 / 9
        else:
            # Temperature is in Celsius, convert to Fahrenheit
            temperature_f = (temperature * 9 / 5) + 32
            temperature_c = temperature

        # Format based on user preference
        temperature_str = format_temperature(
            temperature_f,
            unit_pref,
            temperature_c=temperature_c,
            precision=get_temperature_precision(unit_pref),
        )
    else:
        temperature_str = "N/A"

    # Extract other data
    description = properties.get("textDescription", "N/A")
    humidity = properties.get("relativeHumidity", {}).get("value")
    humidity_str = f"{humidity}%" if humidity is not None else "N/A"

    # Wind data
    wind_speed = properties.get("windSpeed", {}).get("value")
    wind_direction = properties.get("windDirection", {}).get("value")
    wind_str = format_combined_wind(wind_speed, wind_direction, "mph")
    if not wind_str:
        wind_str = "N/A"

    # Pressure
    pressure = properties.get("barometricPressure", {}).get("value")
    pressure_str = "N/A"
    if pressure is not None:
        # Convert from Pa to inHg
        pressure_inhg = pressure * 0.0002953
        pressure_str = f"{pressure_inhg:.2f} inHg"

    # Visibility
    visibility = properties.get("visibility", {}).get("value")
    visibility_str = "N/A"
    if visibility is not None:
        # Convert from meters to miles
        visibility_miles = visibility * 0.000621371
        visibility_str = f"{visibility_miles:.1f} miles"

    # Format the text
    text = f"""Temperature: {temperature_str}
Conditions: {description}
Humidity: {humidity_str}
Wind: {wind_str}
Pressure: {pressure_str}
Visibility: {visibility_str}"""

    frame.current_conditions_text.SetValue(text)

    # Extract data for taskbar icon
    taskbar_data = extract_nws_data_for_taskbar(conditions_data, frame)

    # Update taskbar icon with weather data
    if hasattr(frame, "taskbar_icon") and frame.taskbar_icon:
        frame.taskbar_icon.update_weather_data(taskbar_data)


def format_weatherapi_current_conditions(conditions_data, frame):
    """Format WeatherAPI.com current conditions data for display.

    Args:
        conditions_data: WeatherAPI.com current conditions data
        frame: The main WeatherApp frame instance

    Returns:
        str: Formatted current conditions text
    """
    if not conditions_data or "current" not in conditions_data:
        return "No current conditions data available"

    current = conditions_data["current"]

    # Get user's temperature unit preference
    unit_pref = get_temperature_unit_preference(frame)

    # Temperature
    temp_f = current.get("temp_f")
    temp_c = current.get("temp_c")
    if temp_f is not None and temp_c is not None:
        temperature_str = format_temperature(
            temp_f,
            unit_pref,
            temperature_c=temp_c,
            precision=get_temperature_precision(unit_pref),
        )
    else:
        temperature_str = "N/A"

    # Feels like temperature
    feels_like_f = current.get("feelslike_f")
    feels_like_c = current.get("feelslike_c")
    if feels_like_f is not None and feels_like_c is not None:
        feels_like_str = format_temperature(
            feels_like_f,
            unit_pref,
            temperature_c=feels_like_c,
            precision=get_temperature_precision(unit_pref),
        )
    else:
        feels_like_str = "N/A"

    # Other data
    condition = current.get("condition", {}).get("text", "N/A")
    humidity = current.get("humidity")
    humidity_str = f"{humidity}%" if humidity is not None else "N/A"

    # Wind
    wind_speed = current.get("wind_mph")
    wind_dir = current.get("wind_dir", "")
    wind_str = format_combined_wind(wind_speed, wind_dir, "mph")
    if not wind_str:
        wind_str = "N/A"

    # Pressure
    pressure = current.get("pressure_in")
    pressure_str = f"{pressure:.2f} inHg" if pressure is not None else "N/A"

    # UV Index
    uv = current.get("uv")
    uv_str = str(uv) if uv is not None else "N/A"

    # Visibility
    visibility = current.get("vis_miles")
    visibility_str = f"{visibility:.1f} miles" if visibility is not None else "N/A"

    # Format the text
    text = f"""Temperature: {temperature_str}
Feels Like: {feels_like_str}
Conditions: {condition}
Humidity: {humidity_str}
Wind: {wind_str}
Pressure: {pressure_str}
UV Index: {uv_str}
Visibility: {visibility_str}"""

    return text
