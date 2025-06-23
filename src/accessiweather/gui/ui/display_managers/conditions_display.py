"""Current conditions display management for AccessiWeather UI.

This module handles the display of current weather conditions data.
"""

import logging

from accessiweather.utils.temperature_utils import format_temperature
from accessiweather.utils.unit_utils import format_pressure, format_wind_speed

from ..ui_utils import is_weatherapi_data

logger = logging.getLogger(__name__)


class ConditionsDisplay:
    """Manages the display of current weather conditions."""

    def __init__(self, frame, formatter, extractor):
        """Initialize the conditions display manager.

        Args:
            frame: The main WeatherApp frame instance.
            formatter: WeatherDataFormatter instance for formatting data.
            extractor: WeatherDataExtractor instance for extracting data.

        """
        self.frame = frame
        self.formatter = formatter
        self.extractor = extractor

    def display_current_conditions(self, conditions_data):
        """Display current weather conditions in the UI.

        Args:
            conditions_data: Dictionary with current conditions data

        """
        logger.debug(f"display_current_conditions received: {conditions_data}")

        # Create a dictionary for taskbar icon data
        taskbar_data = {}

        # Check if this is WeatherAPI.com data
        if is_weatherapi_data(conditions_data):
            try:
                text = self.formatter._format_weatherapi_current_conditions(conditions_data)
                # Normalize line endings for consistent screen reader behavior
                if isinstance(text, str):
                    text = text.replace("\r\n", "\n").replace("\r", "\n")
                self.frame.current_conditions_text.SetValue(text)

                # Extract data for taskbar icon
                taskbar_data = self.extractor.extract_weatherapi_data_for_taskbar(conditions_data)

                # Update taskbar icon with weather data
                if hasattr(self.frame, "taskbar_icon") and self.frame.taskbar_icon:
                    self.frame.taskbar_icon.update_weather_data(taskbar_data)

                return
            except Exception as e:
                logger.exception("Error formatting WeatherAPI.com current conditions")
                self.frame.current_conditions_text.SetValue(
                    f"Error formatting current conditions: {e}"
                )
                return

        # Handle NWS API data
        self._display_nws_current_conditions(conditions_data)

    def _display_nws_current_conditions(self, conditions_data):
        """Display NWS API current conditions.

        Args:
            conditions_data: NWS current conditions data

        """
        if not conditions_data or "properties" not in conditions_data:
            self.frame.current_conditions_text.SetValue("No current conditions data available")
            return

        properties = conditions_data.get("properties", {})

        # Extract key weather data
        temperature = properties.get("temperature", {}).get("value")
        dewpoint = properties.get("dewpoint", {}).get("value")
        wind_speed = properties.get("windSpeed", {}).get("value")
        wind_direction = properties.get("windDirection", {}).get("value")
        barometric_pressure = properties.get("barometricPressure", {}).get("value")
        relative_humidity = properties.get("relativeHumidity", {}).get("value")
        description = properties.get("textDescription", "No description available")

        # Get user's temperature unit preference
        unit_pref = self.formatter._get_temperature_unit_preference()

        # Extract data for taskbar icon
        taskbar_data = self.extractor.extract_nws_data_for_taskbar(conditions_data)

        # Update taskbar icon with weather data
        if hasattr(self.frame, "taskbar_icon") and self.frame.taskbar_icon:
            self.frame.taskbar_icon.update_weather_data(taskbar_data)

        # Format the display text
        text = self._format_nws_conditions_text(
            properties,
            temperature,
            dewpoint,
            wind_speed,
            wind_direction,
            barometric_pressure,
            relative_humidity,
            description,
            unit_pref,
        )

        # Normalize line endings for consistent screen reader behavior
        if isinstance(text, str):
            text = text.replace("\r\n", "\n").replace("\r", "\n")

        self.frame.current_conditions_text.SetValue(text)

    def _format_nws_conditions_text(
        self,
        properties,
        temperature,
        dewpoint,
        wind_speed,
        wind_direction,
        barometric_pressure,
        relative_humidity,
        description,
        unit_pref,
    ):
        """Format NWS current conditions text for display.

        Args:
            properties: Properties from NWS data
            temperature: Temperature value
            dewpoint: Dewpoint value
            wind_speed: Wind speed value
            wind_direction: Wind direction value
            barometric_pressure: Pressure value
            relative_humidity: Humidity value
            description: Weather description
            unit_pref: Temperature unit preference

        Returns:
            str: Formatted conditions text

        """
        # Convert units and format temperature
        if temperature is not None:
            temp_unit_code = properties.get("temperature", {}).get("unitCode", "")
            if "degF" in temp_unit_code:
                temperature_f = temperature
                temperature_c = (temperature - 32) * 5 / 9
            else:
                temperature_f = (temperature * 9 / 5) + 32
                temperature_c = temperature

            temperature_str = format_temperature(
                temperature_f,
                unit_pref,
                temperature_c=temperature_c,
                precision=self.formatter._get_temperature_precision(unit_pref),
            )
        else:
            temperature_str = "N/A"

        # Format dewpoint
        if dewpoint is not None:
            dewpoint_unit_code = properties.get("dewpoint", {}).get("unitCode", "")
            if "degF" in dewpoint_unit_code:
                dewpoint_f = dewpoint
                dewpoint_c = (dewpoint - 32) * 5 / 9
            else:
                dewpoint_f = (dewpoint * 9 / 5) + 32
                dewpoint_c = dewpoint

            dewpoint_str = format_temperature(
                dewpoint_f,
                unit_pref,
                temperature_c=dewpoint_c,
                precision=self.formatter._get_temperature_precision(unit_pref),
            )
        else:
            dewpoint_str = "N/A"

        # Format wind
        if wind_speed is not None:
            wind_speed_mph = wind_speed * 0.621371
            wind_speed_str = format_wind_speed(
                wind_speed_mph, unit_pref, wind_speed_kph=wind_speed, precision=1
            )
        else:
            wind_speed_str = "N/A"

        # Format pressure
        if barometric_pressure is not None:
            pressure_inhg = barometric_pressure / 3386.39
            pressure_mb = barometric_pressure / 100
            pressure_str = format_pressure(
                pressure_inhg, unit_pref, pressure_mb=pressure_mb, precision=0
            )
        else:
            pressure_str = "N/A"

        # Format humidity
        if relative_humidity is not None:
            humidity_str = f"{relative_humidity:.0f}%"
        else:
            humidity_str = "N/A"

        # Format wind direction
        if wind_direction is not None:
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
            index = round(wind_direction / 22.5) % 16
            wind_dir_str = directions[index]
        else:
            wind_dir_str = "N/A"

        # Format the text
        text = f"Current Conditions: {description}\n"
        text += f"Temperature: {temperature_str}\n"
        text += f"Humidity: {humidity_str}\n"
        text += f"Wind: {wind_dir_str} at {wind_speed_str}\n"
        text += f"Dewpoint: {dewpoint_str}\n"
        text += f"Pressure: {pressure_str}"

        return text
