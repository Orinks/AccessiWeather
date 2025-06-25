"""Weather data formatter specifically designed for Toga UI components.

This module provides formatting functionality for weather data to be displayed
in Toga text widgets with proper accessibility support and temperature formatting.
"""

import logging

from accessiweather.utils.temperature_utils import TemperatureUnit, format_temperature
from accessiweather.utils.unit_utils import format_pressure, format_wind_speed

logger = logging.getLogger(__name__)


class TogaWeatherFormatter:
    """Weather data formatter specifically designed for Toga UI components."""

    def __init__(self, config):
        """Initialize the formatter with configuration.

        Args:
            config: Application configuration dictionary

        """
        self.config = config or {}

    def _get_temperature_unit_preference(self):
        """Get the user's temperature unit preference from config."""
        settings = self.config.get("settings", {})
        unit_pref = settings.get("temperature_unit", "fahrenheit")

        # Convert string to enum
        if unit_pref == "celsius":
            return TemperatureUnit.CELSIUS
        if unit_pref == "both":
            return TemperatureUnit.BOTH
        return TemperatureUnit.FAHRENHEIT

    def _get_temperature_precision(self, unit_pref: TemperatureUnit) -> int:
        """Get the appropriate precision for temperature formatting."""
        return 0 if unit_pref == TemperatureUnit.BOTH else 1

    def format_current_conditions(self, conditions_data, location_name):
        """Format current conditions data for Toga display."""
        if not conditions_data:
            return f"Current conditions for {location_name}\n\nNo current conditions data available"

        try:
            unit_pref = self._get_temperature_unit_preference()
            precision = self._get_temperature_precision(unit_pref)

            # Extract data from conditions
            temperature = conditions_data.get("temperature")
            temperature_c = conditions_data.get("temperature_c")
            condition = conditions_data.get("condition", "Unknown")
            humidity = conditions_data.get("humidity")
            wind_speed = conditions_data.get("wind_speed")
            wind_speed_kph = conditions_data.get("wind_speed_kph")
            wind_direction = conditions_data.get("wind_direction", "")
            pressure = conditions_data.get("pressure")
            pressure_mb = conditions_data.get("pressure_mb")
            feelslike = conditions_data.get("feelslike")
            feelslike_c = conditions_data.get("feelslike_c")

            # Format temperature
            if temperature is not None:
                temperature_str = format_temperature(
                    temperature, unit_pref, temperature_c=temperature_c, precision=precision
                )
            else:
                temperature_str = "N/A"

            # Format feels like temperature
            if feelslike is not None:
                feelslike_str = format_temperature(
                    feelslike, unit_pref, temperature_c=feelslike_c, precision=precision
                )
            else:
                feelslike_str = "N/A"

            # Format wind
            if wind_speed is not None:
                wind_speed_str = format_wind_speed(
                    wind_speed, unit_pref, wind_speed_kph=wind_speed_kph, precision=1
                )
            else:
                wind_speed_str = "N/A"

            # Format pressure
            if pressure is not None:
                pressure_str = format_pressure(
                    pressure, unit_pref, pressure_mb=pressure_mb, precision=0
                )
            else:
                pressure_str = "N/A"

            # Format humidity
            humidity_str = f"{humidity}%" if humidity is not None else "N/A"

            # Build the formatted text with accessibility-friendly flow
            text = f"Current conditions for {location_name}\n\n"
            text += f"Temperature: {temperature_str}, {condition}\n"
            text += f"Feels like: {feelslike_str}\n"
            text += f"Humidity: {humidity_str}\n"
            text += f"Wind: {wind_direction} at {wind_speed_str}\n"
            text += f"Pressure: {pressure_str}"

            return text

        except Exception as e:
            logger.error(f"Error formatting current conditions: {e}")
            return f"Current conditions for {location_name}\n\nError formatting weather data: {e}"

    def format_forecast(self, forecast_data, location_name):
        """Format forecast data for Toga display."""
        if not forecast_data:
            return f"Forecast for {location_name}\n\nNo forecast data available"

        try:
            unit_pref = self._get_temperature_unit_preference()
            precision = self._get_temperature_precision(unit_pref)

            text = f"Forecast for {location_name}\n\n"

            # Handle different forecast data structures
            periods = forecast_data.get("periods", [])
            if not periods:
                # Try alternative structure
                forecast_list = forecast_data.get("forecast", [])
                if forecast_list:
                    periods = forecast_list

            if not periods:
                return f"Forecast for {location_name}\n\nNo forecast periods available"

            # Format each forecast period
            for period in periods[:7]:  # Limit to 7 periods for readability
                name = period.get("name", "Unknown")
                temperature = period.get("temperature")
                temperature_unit = period.get("temperatureUnit", "F")
                short_forecast = period.get("shortForecast", "")

                # Convert temperature if needed
                if temperature is not None:
                    if temperature_unit == "F":
                        temp_f = temperature
                        temp_c = (temperature - 32) * 5 / 9
                    else:
                        temp_c = temperature
                        temp_f = (temperature * 9 / 5) + 32

                    temp_str = format_temperature(
                        temp_f, unit_pref, temperature_c=temp_c, precision=precision
                    )
                else:
                    temp_str = "N/A"

                text += f"{name}: {temp_str}, {short_forecast}\n"

            return text

        except Exception as e:
            logger.error(f"Error formatting forecast: {e}")
            return f"Forecast for {location_name}\n\nError formatting forecast data: {e}"

    def format_alerts(self, alerts_data, location_name):
        """Format alerts data for Toga Table display.

        Returns:
            tuple: (table_data, location_name) where table_data is a list of tuples
                   for the Table widget, or ([], location_name) if no alerts

        """
        if not alerts_data:
            return ([], location_name)

        try:
            # Handle different alert data structures
            alerts = alerts_data
            if isinstance(alerts_data, dict):
                alerts = alerts_data.get("alerts", [])

            if not alerts:
                return ([], location_name)

            # Format each alert as a tuple for the table
            table_data = []
            for alert in alerts[:10]:  # Limit to 10 alerts for performance
                event = alert.get("event", "Weather Alert")
                severity = alert.get("severity", "Unknown")
                headline = alert.get("headline", "No headline available")

                # Truncate headline if too long for table display
                if len(headline) > 80:
                    headline = headline[:77] + "..."

                table_data.append((event, severity, headline))

            return (table_data, location_name)

        except Exception as e:
            logger.error(f"Error formatting alerts: {e}")
            return ([], location_name)

    def get_alert_details(self, alerts_data, alert_index):
        """Get detailed information for a specific alert.

        Args:
            alerts_data: The original alerts data
            alert_index: Index of the alert to get details for

        Returns:
            dict: Alert details or None if not found

        """
        try:
            # Handle different alert data structures
            alerts = alerts_data
            if isinstance(alerts_data, dict):
                alerts = alerts_data.get("alerts", [])

            if not alerts or alert_index >= len(alerts):
                return None

            return alerts[alert_index]

        except Exception as e:
            logger.error(f"Error getting alert details: {e}")
            return None
