"""Forecast display utilities for AccessiWeather.

This module provides functions for displaying forecast data in the UI.
"""

import logging

from .weather_formatting import get_temperature_precision, is_weatherapi_data
from .weather_source_detection import get_temperature_unit_preference
from accessiweather.utils.temperature_utils import format_temperature

logger = logging.getLogger(__name__)


def display_forecast(frame, forecast_data, hourly_forecast_data=None):
    """Display forecast data in the UI.

    Args:
        frame: The main WeatherApp frame instance
        forecast_data: Dictionary with forecast data
        hourly_forecast_data: Optional dictionary with hourly forecast data
    """
    logger.debug(f"display_forecast received: {forecast_data}")

    # Detect nationwide data by presence of national_discussion_summaries key
    if "national_discussion_summaries" in forecast_data:
        try:
            formatted = format_national_forecast(forecast_data)
            frame.forecast_text.SetValue(formatted)
            # Clear current conditions for nationwide view
            frame.current_conditions_text.SetValue(
                "Current conditions not available for nationwide view"
            )
        except Exception as e:
            logger.exception("Error formatting national forecast")
            frame.forecast_text.SetValue(f"Error formatting national forecast: {e}")
        return

    # Check if this is WeatherAPI.com data
    if is_weatherapi_data(forecast_data):
        try:
            formatted = format_weatherapi_forecast(forecast_data, hourly_forecast_data, frame)
            frame.forecast_text.SetValue(formatted)
            return
        except Exception as e:
            logger.exception("Error formatting WeatherAPI.com forecast")
            frame.forecast_text.SetValue(f"Error formatting forecast: {e}")
            return

    # Handle NWS API location forecast data
    if not forecast_data or "properties" not in forecast_data:
        frame.forecast_text.SetValue("No forecast data available")
        return

    periods = forecast_data.get("properties", {}).get("periods", [])
    if not periods:
        frame.forecast_text.SetValue("No forecast periods available")
        return

    # Format forecast text
    text = ""

    # Add hourly forecast summary if available
    if hourly_forecast_data and "properties" in hourly_forecast_data:
        hourly_periods = hourly_forecast_data.get("properties", {}).get("periods", [])
        if hourly_periods:
            text += "Next 6 Hours:\n"
            for period in hourly_periods[:6]:  # Show next 6 hours
                start_time = period.get("startTime", "")
                # Extract just the time portion (HH:MM)
                if start_time:
                    try:
                        # Format: 2023-01-01T12:00:00-05:00
                        time_part = start_time.split("T")[1][:5]  # Get "12:00"
                        hour = int(time_part.split(":")[0])
                        am_pm = "AM" if hour < 12 else "PM"
                        if hour == 0:
                            hour = 12
                        elif hour > 12:
                            hour -= 12
                        formatted_time = f"{hour}:{time_part.split(':')[1]} {am_pm}"
                    except (IndexError, ValueError):
                        formatted_time = start_time
                else:
                    formatted_time = "Unknown"

                temp = period.get("temperature", "?")
                unit = period.get("temperatureUnit", "F")
                short_forecast = period.get("shortForecast", "")

                # Convert temperature if needed
                unit_pref = get_temperature_unit_preference(frame)
                if temp != "?" and isinstance(temp, (int, float)):
                    if unit == "F":
                        temp_f = temp
                        temp_c = (temp - 32) * 5 / 9
                    else:
                        temp_c = temp
                        temp_f = (temp * 9 / 5) + 32

                    temp_str = format_temperature(
                        temp_f,
                        unit_pref,
                        temperature_c=temp_c,
                        precision=get_temperature_precision(unit_pref),
                    )
                else:
                    temp_str = f"{temp}°{unit}"

                text += f"  {formatted_time}: {temp_str}, {short_forecast}\n"

            text += "\n"

    # Add main forecast periods
    for period in periods:
        name = period.get("name", "Unknown")
        temperature = period.get("temperature", "?")
        unit = period.get("temperatureUnit", "F")
        detailed_forecast = period.get("detailedForecast", "No details available")

        # Convert temperature if needed
        unit_pref = get_temperature_unit_preference(frame)
        if temperature != "?" and isinstance(temperature, (int, float)):
            if unit == "F":
                temp_f = temperature
                temp_c = (temperature - 32) * 5 / 9
            else:
                temp_c = temperature
                temp_f = (temperature * 9 / 5) + 32

            temp_str = format_temperature(
                temp_f,
                unit_pref,
                temperature_c=temp_c,
                precision=get_temperature_precision(unit_pref),
            )
        else:
            temp_str = f"{temperature}°{unit}"

        text += f"{name}: {temp_str}\n{detailed_forecast}\n\n"

    frame.forecast_text.SetValue(text.strip())


def format_national_forecast(forecast_data):
    """Format national forecast data for display.

    Args:
        forecast_data: Dictionary with national forecast data

    Returns:
        str: Formatted national forecast text
    """
    if not forecast_data or "national_discussion_summaries" not in forecast_data:
        return "No national forecast data available"

    summaries = forecast_data["national_discussion_summaries"]
    text = "National Weather Forecast Discussions:\n\n"

    for center, summary in summaries.items():
        if summary:
            text += f"{center.upper()}:\n{summary}\n\n"

    return text.strip()


def format_weatherapi_forecast(forecast_data, hourly_forecast_data, frame):
    """Format WeatherAPI.com forecast data for display.

    Args:
        forecast_data: WeatherAPI.com forecast data
        hourly_forecast_data: Optional hourly forecast data
        frame: The main WeatherApp frame instance

    Returns:
        str: Formatted forecast text
    """
    if not forecast_data or "forecast" not in forecast_data:
        return "No forecast data available"

    forecast = forecast_data["forecast"]
    if "forecastday" not in forecast:
        return "No forecast periods available"

    forecastdays = forecast["forecastday"]
    if not forecastdays:
        return "No forecast periods available"

    # Get user's temperature unit preference
    unit_pref = get_temperature_unit_preference(frame)

    text = ""

    # Add hourly forecast summary if available
    if hourly_forecast_data and "forecast" in hourly_forecast_data:
        hourly_forecast = hourly_forecast_data["forecast"]
        if "forecastday" in hourly_forecast and hourly_forecast["forecastday"]:
            first_day = hourly_forecast["forecastday"][0]
            if "hour" in first_day:
                hours = first_day["hour"][:6]  # Next 6 hours
                if hours:
                    text += "Next 6 Hours:\n"
                    for hour in hours:
                        time_str = hour.get("time", "")
                        if time_str:
                            # Extract time portion (HH:MM)
                            try:
                                time_part = time_str.split(" ")[1]  # Get "12:00"
                                hour_num = int(time_part.split(":")[0])
                                am_pm = "AM" if hour_num < 12 else "PM"
                                if hour_num == 0:
                                    hour_num = 12
                                elif hour_num > 12:
                                    hour_num -= 12
                                formatted_time = f"{hour_num}:{time_part.split(':')[1]} {am_pm}"
                            except (IndexError, ValueError):
                                formatted_time = time_str
                        else:
                            formatted_time = "Unknown"

                        temp_f = hour.get("temp_f")
                        temp_c = hour.get("temp_c")
                        condition = hour.get("condition", {}).get("text", "")

                        # Format temperature based on user preference
                        if temp_f is not None and temp_c is not None:
                            temp_str = format_temperature(
                                temp_f,
                                unit_pref,
                                temperature_c=temp_c,
                                precision=get_temperature_precision(unit_pref),
                            )
                        else:
                            temp_str = "N/A"

                        text += f"  {formatted_time}: {temp_str}, {condition}\n"

                    text += "\n"

    # Add daily forecast
    for day in forecastdays:
        date = day.get("date", "Unknown")
        day_data = day.get("day", {})

        max_temp_f = day_data.get("maxtemp_f")
        max_temp_c = day_data.get("maxtemp_c")
        min_temp_f = day_data.get("mintemp_f")
        min_temp_c = day_data.get("mintemp_c")
        condition = day_data.get("condition", {}).get("text", "")

        # Format temperatures based on user preference
        if max_temp_f is not None and max_temp_c is not None:
            max_temp_str = format_temperature(
                max_temp_f,
                unit_pref,
                temperature_c=max_temp_c,
                precision=get_temperature_precision(unit_pref),
            )
        else:
            max_temp_str = "N/A"

        if min_temp_f is not None and min_temp_c is not None:
            min_temp_str = format_temperature(
                min_temp_f,
                unit_pref,
                temperature_c=min_temp_c,
                precision=get_temperature_precision(unit_pref),
            )
        else:
            min_temp_str = "N/A"

        text += f"{date}: High {max_temp_str}, Low {min_temp_str}\n{condition}\n\n"

    return text.strip()


def display_hourly_forecast(frame, hourly_data):
    """Display hourly forecast data in the UI.

    Args:
        frame: The main WeatherApp frame instance
        hourly_data: Dictionary with hourly forecast data
    """
    # This method is not currently used directly in the UI
    # The hourly forecast data is incorporated into the main forecast display
    pass
