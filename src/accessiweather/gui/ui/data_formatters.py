"""Data Formatters for AccessiWeather UI.

This module provides classes for formatting weather data for display
in the user interface.
"""

import logging
from datetime import datetime

from accessiweather.gui.settings.constants import DEFAULT_TEMPERATURE_UNIT, TEMPERATURE_UNIT_KEY
from accessiweather.utils.temperature_utils import TemperatureUnit, format_temperature

logger = logging.getLogger(__name__)


class WeatherDataFormatter:
    """Formats weather data for UI display."""

    def __init__(self, frame):
        """Initialize the formatter.

        Args:
            frame: The main WeatherApp frame instance for config access.
        """
        self.frame = frame

    def _get_temperature_unit_preference(self):
        """Get the user's temperature unit preference from config.

        Returns:
            TemperatureUnit: The user's temperature unit preference
        """
        if not hasattr(self.frame, "config"):
            return TemperatureUnit.FAHRENHEIT

        settings = self.frame.config.get("settings", {})
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

    def _get_temperature_precision(self, unit_pref: TemperatureUnit) -> int:
        """Get the appropriate precision for temperature formatting.

        Args:
            unit_pref: The temperature unit preference

        Returns:
            int: Precision (0 for whole numbers when 'both', 1 otherwise)
        """
        return 0 if unit_pref == TemperatureUnit.BOTH else 1

    def format_national_forecast(self, forecast_data):
        """Format national forecast data for display.

        Args:
            forecast_data: Dictionary containing national forecast data from scraper
                         with structure: {"national_discussion_summaries": {"wpc": {...}, "spc": {...}}}

        Returns:
            str: Formatted forecast text
        """
        if not forecast_data or "national_discussion_summaries" not in forecast_data:
            return "No national forecast data available"

        summaries = forecast_data["national_discussion_summaries"]
        text = "National Weather Overview\n\n"

        # Add WPC summary if available
        wpc_data = summaries.get("wpc", {})
        if wpc_data:
            text += "Weather Prediction Center (WPC) Summary:\n"
            # Check for both "summary" and "short_range_summary" keys
            wpc_summary = wpc_data.get("summary") or wpc_data.get("short_range_summary")
            text += (wpc_summary or "No WPC summary available") + "\n\n"

        # Add SPC summary if available
        spc_data = summaries.get("spc", {})
        if spc_data:
            text += "Storm Prediction Center (SPC) Summary:\n"
            # Check for both "summary" and "day1_summary" keys
            spc_summary = spc_data.get("summary") or spc_data.get("day1_summary")
            text += (spc_summary or "No SPC summary available") + "\n\n"

        # Add attribution
        attribution = summaries.get("attribution", "")
        if attribution:
            text += "\n" + attribution

        return text

    def format_weatherapi_forecast(self, forecast_data, hourly_forecast_data=None):
        """Format WeatherAPI.com forecast data for display.

        Args:
            forecast_data: Dictionary with WeatherAPI.com forecast data
            hourly_forecast_data: Optional dictionary with hourly forecast data

        Returns:
            str: Formatted forecast text
        """
        if not forecast_data:
            return "No forecast data available"

        # Get the forecast data
        forecast_days = forecast_data.get("forecast", [])
        if not forecast_days:
            return "No forecast periods available"

        # Format forecast text
        text = ""

        # Add location information if available
        location = forecast_data.get("location", {})
        if location:
            location_name = location.get("name", "")
            region = location.get("region", "")
            country = location.get("country", "")
            if location_name and country:
                if region:
                    text += f"Forecast for {location_name}, {region}, {country}\n\n"
                else:
                    text += f"Forecast for {location_name}, {country}\n\n"

        # Add hourly forecast if available
        hourly_data = forecast_data.get("hourly", []) or (hourly_forecast_data or {}).get(
            "hourly", []
        )
        if hourly_data:
            text += self._format_weatherapi_hourly(hourly_data)

        # Add daily forecast
        text += "Extended Forecast:\n"
        for day in forecast_days:
            text += self._format_weatherapi_daily(day)

        return text

    def _format_weatherapi_hourly(self, hourly_data):
        """Format WeatherAPI hourly data.

        Args:
            hourly_data: List of hourly forecast data

        Returns:
            str: Formatted hourly forecast text
        """
        text = "Next 6 Hours:\n"
        unit_pref = self._get_temperature_unit_preference()

        for hour in hourly_data[:6]:  # Show next 6 hours
            time_str = hour.get("time", "Unknown")
            # Format time string (e.g., "2023-01-01 12:00")
            try:
                # Extract just the time portion (HH:MM)
                time_parts = time_str.split(" ")
                if len(time_parts) > 1:
                    time_part = time_parts[1]
                    hour_val = int(time_part.split(":")[0])
                    am_pm = "AM" if hour_val < 12 else "PM"
                    if hour_val == 0:
                        hour_val = 12
                    elif hour_val > 12:
                        hour_val -= 12
                    formatted_time = f"{hour_val}:{time_part.split(':')[1]} {am_pm}"
                else:
                    formatted_time = time_str
            except (IndexError, ValueError):
                formatted_time = time_str

            temp_f = hour.get("temperature", hour.get("temp_f", "?"))
            temp_c = hour.get("temp_c", None)
            condition = hour.get("condition", "")
            if isinstance(condition, dict):
                condition = condition.get("text", "")

            # Format temperature based on user preference
            temp_str = format_temperature(
                temp_f,
                unit_pref,
                temperature_c=temp_c,
                precision=self._get_temperature_precision(unit_pref),
            )

            text += f"{formatted_time}: {temp_str}, {condition}\n"

        text += "\n"
        return text

    def _format_weatherapi_daily(self, day):
        """Format WeatherAPI daily forecast data.

        Args:
            day: Daily forecast data dictionary

        Returns:
            str: Formatted daily forecast text
        """
        date = day.get("date", "Unknown")
        high = day.get("high", day.get("maxtemp_f", "?"))
        low = day.get("low", day.get("mintemp_f", "?"))
        condition = day.get("condition", "")
        if isinstance(condition, dict):
            condition = condition.get("text", "")

        # Format date (e.g., "2023-01-01" to "Monday, January 1")
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%A, %B %d")
        except (ValueError, TypeError):
            formatted_date = date

        # Get high and low temperatures in both units if available
        high_f = high
        high_c = day.get("maxtemp_c", None)
        low_f = low
        low_c = day.get("mintemp_c", None)

        # Format temperatures based on user preference
        unit_pref = self._get_temperature_unit_preference()
        precision = self._get_temperature_precision(unit_pref)
        high_str = format_temperature(high_f, unit_pref, temperature_c=high_c, precision=precision)
        low_str = format_temperature(low_f, unit_pref, temperature_c=low_c, precision=precision)

        text = f"{formatted_date}: High {high_str}, Low {low_str}\n"
        text += f"{condition}\n"

        # Add precipitation chance if available
        precip_chance = day.get("precipitation_probability", day.get("daily_chance_of_rain", ""))
        if precip_chance:
            text += f"Chance of precipitation: {precip_chance}%\n"

        # Add wind information if available
        wind_speed = day.get("max_wind_speed", day.get("maxwind_mph", ""))
        if wind_speed:
            text += f"Wind: {wind_speed} mph\n"

        text += "\n"
        return text

    def _format_weatherapi_current_conditions(self, conditions_data):
        """Format WeatherAPI.com current conditions data for display.

        Args:
            conditions_data: Dictionary with WeatherAPI.com current conditions data

        Returns:
            str: Formatted current conditions text
        """
        from accessiweather.utils.unit_utils import format_pressure, format_wind_speed

        if not conditions_data:
            return "No current conditions data available"

        # Extract key weather data
        temperature = conditions_data.get("temperature")
        temperature_c = conditions_data.get("temperature_c")
        humidity = conditions_data.get("humidity")
        wind_speed = conditions_data.get("wind_speed")
        wind_speed_kph = conditions_data.get("wind_speed_kph")
        wind_direction = conditions_data.get("wind_direction")
        pressure = conditions_data.get("pressure")
        pressure_mb = conditions_data.get("pressure_mb")
        condition = conditions_data.get("condition", "")
        feelslike = conditions_data.get("feelslike")
        feelslike_c = conditions_data.get("feelslike_c")

        # Get user's temperature unit preference
        unit_pref = self._get_temperature_unit_preference()

        # Format temperature
        temperature_str = format_temperature(
            temperature,
            unit_pref,
            temperature_c=temperature_c,
            precision=self._get_temperature_precision(unit_pref),
        )

        # Format humidity
        humidity_str = f"{humidity}%" if humidity is not None else "N/A"

        # Format wind
        wind_speed_str = format_wind_speed(
            wind_speed, unit_pref, wind_speed_kph=wind_speed_kph, precision=1
        )

        # Format pressure
        pressure_str = format_pressure(pressure, unit_pref, pressure_mb=pressure_mb, precision=0)

        # Format feels like
        feelslike_str = format_temperature(
            feelslike,
            unit_pref,
            temperature_c=feelslike_c,
            precision=self._get_temperature_precision(unit_pref),
        )

        # Format the text
        text = f"Current Conditions: {condition}\n"
        text += f"Temperature: {temperature_str}\n"
        text += f"Feels Like: {feelslike_str}\n"
        text += f"Humidity: {humidity_str}\n"
        text += f"Wind: {wind_direction} at {wind_speed_str}\n"
        text += f"Pressure: {pressure_str}"

        return text
