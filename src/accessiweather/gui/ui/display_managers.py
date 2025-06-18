"""Display Managers for AccessiWeather UI.

This module provides classes for managing the display of weather data
in various UI components.
"""

import logging

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.utils.temperature_utils import format_temperature
from accessiweather.utils.unit_utils import format_pressure, format_wind_speed

from .alerts_manager import AlertsDisplayManager
from .data_extractors import WeatherDataExtractor
from .data_formatters import WeatherDataFormatter
from .ui_utils import is_weatherapi_data

logger = logging.getLogger(__name__)


class WeatherDisplayManager:
    """Manages the display of weather data in UI components."""

    def __init__(self, frame):
        """Initialize the display manager.

        Args:
            frame: The main WeatherApp frame instance.
        """
        self.frame = frame
        self.formatter = WeatherDataFormatter(frame)
        self.extractor = WeatherDataExtractor(frame)
        self.alerts_manager = AlertsDisplayManager(frame)

    def display_loading_state(self, location_name=None, is_nationwide=False):
        """Display loading state in the UI.

        Args:
            location_name: Optional location name for status text
            is_nationwide: Whether this is a nationwide forecast
        """
        # Disable refresh button
        self.frame.refresh_btn.Disable()

        # Set loading text based on type
        loading_text = "Loading nationwide forecast..." if is_nationwide else "Loading forecast..."
        self.frame.forecast_text.SetValue(loading_text)

        # Set loading text for current conditions
        if not is_nationwide:
            self.frame.current_conditions_text.SetValue("Loading current conditions...")
        else:
            self.frame.current_conditions_text.SetValue(
                "Current conditions not available for nationwide view"
            )

        # Clear and set loading text in alerts list
        self.frame.alerts_list.DeleteAllItems()
        self.frame.alerts_list.InsertItem(0, "Loading alerts...")

        # Set status text
        if location_name:
            status = f"Updating weather data for {location_name}..."
            if is_nationwide:
                status = "Updating nationwide weather data..."
        else:
            status = "Updating weather data..."
        self.frame.SetStatusText(status)

    def display_ready_state(self):
        """Display ready state in the UI."""
        self.frame.refresh_btn.Enable()
        self.frame.SetStatusText("Ready")

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

    def display_forecast_error(self, error):
        """Display forecast error in the UI.

        Args:
            error: Error message or exception object
        """
        error_msg = self._format_error_message(error)
        self.frame.forecast_text.SetValue(f"Error fetching forecast: {error_msg}")
        self.frame.current_conditions_text.SetValue("Error fetching current conditions")

    def display_alerts_error(self, error):
        """Display alerts error in the UI.

        Args:
            error: Error message or exception object
        """
        # Clear alerts list
        self.frame.alerts_list.DeleteAllItems()

        # Format the error message
        error_msg = self._format_error_message(error)

        # Add error message to alerts list
        index = self.frame.alerts_list.InsertItem(0, "Error")
        self.frame.alerts_list.SetItem(index, 1, "")  # Empty severity
        self.frame.alerts_list.SetItem(index, 2, f"Error fetching alerts: {error_msg}")

        # Disable the alert button since there are no valid alerts
        if hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Disable()

    def _format_error_message(self, error):
        """Format an error message based on the error type.

        Args:
            error: Error message or exception object

        Returns:
            Formatted error message string
        """
        # If it's already a string, just return it
        if isinstance(error, str):
            return error

        # Handle NOAA API specific errors
        elif isinstance(error, NoaaApiError):
            if error.error_type == NoaaApiError.RATE_LIMIT_ERROR:
                return "NWS API rate limit exceeded. Please try again later."
            elif error.error_type == NoaaApiError.TIMEOUT_ERROR:
                return "NWS API request timed out. Please try again later."
            elif error.error_type == NoaaApiError.CONNECTION_ERROR:
                return "Connection error. Please check your internet connection."
            else:
                return f"NWS API error: {str(error)}"

        # Handle generic API client errors
        elif isinstance(error, ApiClientError):
            return f"API error: {str(error)}"

        # For any other exception, just convert to string
        return str(error)

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
