"""Forecast display management for AccessiWeather UI.

This module handles the display of weather forecast data in various formats.
"""

import logging

from accessiweather.utils.temperature_utils import format_temperature
from ..ui_utils import is_weatherapi_data

logger = logging.getLogger(__name__)


class ForecastDisplay:
    """Manages the display of weather forecast data."""

    def __init__(self, frame, formatter):
        """Initialize the forecast display manager.

        Args:
            frame: The main WeatherApp frame instance.
            formatter: WeatherDataFormatter instance for formatting data.
        """
        self.frame = frame
        self.formatter = formatter

    def display_forecast(self, forecast_data, hourly_forecast_data=None):
        """Display forecast data in the UI.

        Args:
            forecast_data: Dictionary with forecast data
            hourly_forecast_data: Optional dictionary with hourly forecast data
        """
        logger.debug(f"display_forecast received: {forecast_data}")

        # Detect nationwide data by presence of national_discussion_summaries key
        if "national_discussion_summaries" in forecast_data:
            try:
                formatted = self.formatter.format_national_forecast(forecast_data)
                self.frame.forecast_text.SetValue(formatted)
                # Clear current conditions for nationwide view
                self.frame.current_conditions_text.SetValue(
                    "Current conditions not available for nationwide view"
                )
            except Exception as e:
                logger.exception("Error formatting national forecast")
                self.frame.forecast_text.SetValue(f"Error formatting national forecast: {e}")
            return

        # Check if this is WeatherAPI.com data
        if is_weatherapi_data(forecast_data):
            try:
                formatted = self.formatter.format_weatherapi_forecast(
                    forecast_data, hourly_forecast_data
                )
                self.frame.forecast_text.SetValue(formatted)
                return
            except Exception as e:
                logger.exception("Error formatting WeatherAPI.com forecast")
                self.frame.forecast_text.SetValue(f"Error formatting forecast: {e}")
                return

        # Handle NWS API location forecast data
        self._display_nws_forecast(forecast_data, hourly_forecast_data)

    def _display_nws_forecast(self, forecast_data, hourly_forecast_data=None):
        """Display NWS API forecast data.

        Args:
            forecast_data: NWS forecast data
            hourly_forecast_data: Optional hourly forecast data
        """
        if not forecast_data or "properties" not in forecast_data:
            self.frame.forecast_text.SetValue("No forecast data available")
            return

        periods = forecast_data.get("properties", {}).get("periods", [])
        if not periods:
            self.frame.forecast_text.SetValue("No forecast periods available")
            return

        # Format forecast text
        text = ""

        # Add hourly forecast summary if available
        if hourly_forecast_data and "properties" in hourly_forecast_data:
            text += self._format_nws_hourly_summary(hourly_forecast_data)

        # Add daily forecast
        text += "Extended Forecast:\n"
        text += self._format_nws_daily_periods(periods)

        self.frame.forecast_text.SetValue(text)

    def _format_nws_hourly_summary(self, hourly_forecast_data):
        """Format NWS hourly forecast summary.

        Args:
            hourly_forecast_data: Hourly forecast data from NWS

        Returns:
            str: Formatted hourly summary text
        """
        hourly_periods = hourly_forecast_data.get("properties", {}).get("periods", [])
        if not hourly_periods:
            return ""

        text = "Next 6 Hours:\n"
        unit_pref = self.formatter._get_temperature_unit_preference()

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
            if unit == "F" and isinstance(temp, (int, float)):
                temp_f = temp
                temp_c = (temp - 32) * 5 / 9
            elif unit == "C" and isinstance(temp, (int, float)):
                temp_c = temp
                temp_f = (temp * 9 / 5) + 32
            else:
                temp_f = temp
                temp_c = None

            # Format temperature based on user preference
            temp_str = format_temperature(
                temp_f,
                unit_pref,
                temperature_c=temp_c,
                precision=self.formatter._get_temperature_precision(unit_pref),
            )

            text += f"{formatted_time}: {temp_str}, {short_forecast}\n"

        text += "\n"
        return text

    def _format_nws_daily_periods(self, periods):
        """Format NWS daily forecast periods.

        Args:
            periods: List of forecast periods

        Returns:
            str: Formatted daily periods text
        """
        text = ""
        unit_pref = self.formatter._get_temperature_unit_preference()

        for period in periods[:14]:  # Show up to 14 periods (7 days, day and night)
            name = period.get("name", "Unknown")
            temp = period.get("temperature", "?")
            unit = period.get("temperatureUnit", "F")
            details = period.get("detailedForecast", "No details available")

            # Convert temperature if needed
            if unit == "F" and isinstance(temp, (int, float)):
                temp_f = temp
                temp_c = (temp - 32) * 5 / 9
            elif unit == "C" and isinstance(temp, (int, float)):
                temp_c = temp
                temp_f = (temp * 9 / 5) + 32
            else:
                temp_f = temp
                temp_c = None

            # Format temperature based on user preference
            temp_str = format_temperature(
                temp_f,
                unit_pref,
                temperature_c=temp_c,
                precision=self.formatter._get_temperature_precision(unit_pref),
            )

            text += f"{name}: {temp_str}\n"
            text += f"{details}\n\n"

        return text
