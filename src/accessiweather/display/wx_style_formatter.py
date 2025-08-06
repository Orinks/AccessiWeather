"""WX-style weather data formatter for AccessiWeather Simple.

This module provides weather data formatting that exactly matches the wx version's
display output for consistency and familiarity.
"""

import logging
from datetime import datetime

from ..models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    WeatherAlerts,
)
from ..utils import (
    TemperatureUnit,
    convert_wind_direction_to_cardinal,
    format_pressure,
    format_temperature,
    format_wind_speed,
)

logger = logging.getLogger(__name__)


class WxStyleWeatherFormatter:
    """Weather data formatter that matches the wx version's output exactly."""

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def _get_temperature_unit_preference(self) -> TemperatureUnit:
        """Get the user's temperature unit preference from settings."""
        unit_pref = self.settings.temperature_unit.lower()

        if unit_pref == "fahrenheit" or unit_pref == "f":
            return TemperatureUnit.FAHRENHEIT
        if unit_pref == "celsius" or unit_pref == "c":
            return TemperatureUnit.CELSIUS
        if unit_pref == "both":
            return TemperatureUnit.BOTH
        return TemperatureUnit.BOTH  # Default to both like wx version

    def _get_temperature_precision(self, unit_pref: TemperatureUnit) -> int:
        """Get the appropriate precision for temperature formatting."""
        return 0 if unit_pref == TemperatureUnit.BOTH else 1

    def format_current_conditions(
        self, current: CurrentConditions | None, location: Location
    ) -> str:
        """Format current conditions exactly like the wx version."""
        if not current or not current.has_data():
            return f"Current conditions for {location.name}:\nNo current weather data available."

        unit_pref = self._get_temperature_unit_preference()
        precision = self._get_temperature_precision(unit_pref)

        # Extract and convert temperature data
        temperature_f = current.temperature_f
        temperature_c = current.temperature_c

        # Calculate missing temperature if needed
        if temperature_f is None and temperature_c is not None:
            temperature_f = (temperature_c * 9 / 5) + 32
        elif temperature_c is None and temperature_f is not None:
            temperature_c = (temperature_f - 32) * 5 / 9

        # Format temperature
        temperature_str = format_temperature(
            temperature_f, unit_pref, temperature_c=temperature_c, precision=precision
        )

        # Format feels like temperature
        feels_like_f = current.feels_like_f
        feels_like_c = current.feels_like_c
        if feels_like_f is None and feels_like_c is not None:
            feels_like_f = (feels_like_c * 9 / 5) + 32
        elif feels_like_c is None and feels_like_f is not None:
            feels_like_c = (feels_like_f - 32) * 5 / 9

        feels_like_str = "N/A"
        if feels_like_f is not None:
            feels_like_str = format_temperature(
                feels_like_f, unit_pref, temperature_c=feels_like_c, precision=precision
            )

        # Format humidity
        humidity_str = f"{current.humidity:.0f}%" if current.humidity is not None else "N/A"

        # Format wind
        wind_speed_str = "N/A"
        wind_dir_str = "N/A"

        if current.wind_speed_mph is not None:
            wind_speed_str = format_wind_speed(
                current.wind_speed_mph,
                unit_pref,
                wind_speed_kph=current.wind_speed_kph,
                precision=1,
            )

        if current.wind_direction is not None:
            if isinstance(current.wind_direction, int | float):
                wind_dir_str = convert_wind_direction_to_cardinal(current.wind_direction)
            else:
                wind_dir_str = str(current.wind_direction)

        # Format pressure
        pressure_str = "N/A"
        if current.pressure_in is not None:
            pressure_str = format_pressure(
                current.pressure_in, unit_pref, pressure_mb=current.pressure_mb, precision=0
            )
        elif current.pressure_mb is not None:
            # Convert mb to inHg
            pressure_in = current.pressure_mb / 33.8639
            pressure_str = format_pressure(
                pressure_in, unit_pref, pressure_mb=current.pressure_mb, precision=0
            )

        # Format visibility
        visibility_str = "N/A"
        if current.visibility_miles is not None:
            visibility_str = f"{current.visibility_miles:.1f} mi"
        elif current.visibility_km is not None:
            visibility_miles = current.visibility_km * 0.621371
            visibility_str = f"{visibility_miles:.1f} mi"

        # Build the formatted text exactly like wx version
        description = current.condition or "Unknown"
        text = f"Current Conditions: {description}\n"
        text += f"Temperature: {temperature_str}\n"

        # Only show feels like if it's different from actual temperature
        if feels_like_f is not None and temperature_f is not None:
            if abs(feels_like_f - temperature_f) > 2:  # Only show if significantly different
                text += f"Feels like: {feels_like_str}\n"

        text += f"Humidity: {humidity_str}\n"
        text += f"Wind: {wind_dir_str} at {wind_speed_str}\n"

        # Add dewpoint if available (calculated from temperature and humidity)
        if current.temperature_f is not None and current.humidity is not None:
            dewpoint_f = self._calculate_dewpoint(current.temperature_f, current.humidity)
            dewpoint_c = (dewpoint_f - 32) * 5 / 9
            dewpoint_str = format_temperature(
                dewpoint_f, unit_pref, temperature_c=dewpoint_c, precision=precision
            )
            text += f"Dewpoint: {dewpoint_str}\n"

        text += f"Pressure: {pressure_str}"

        # Add visibility if available
        if visibility_str != "N/A":
            text += f"\nVisibility: {visibility_str}"

        # Add UV index if available
        if current.uv_index is not None:
            uv_desc = self._get_uv_description(current.uv_index)
            text += f"\nUV Index: {current.uv_index} ({uv_desc})"

        return text

    def format_forecast(
        self,
        forecast: Forecast | None,
        location: Location,
        hourly_forecast: HourlyForecast | None = None,
    ) -> str:
        """Format forecast exactly like the wx version, including hourly forecast if available."""
        if not forecast or not forecast.has_data():
            return f"Forecast for {location.name}:\nNo forecast data available."

        unit_pref = self._get_temperature_unit_preference()
        precision = self._get_temperature_precision(unit_pref)

        text = f"Forecast for {location.name}:\n\n"

        # Add hourly forecast summary if available (matching wx version)
        if hourly_forecast and hourly_forecast.has_data():
            text += self._format_hourly_summary(hourly_forecast)
            text += "\n"

        # Add extended forecast header
        text += "Extended Forecast:\n"

        # Format each period exactly like wx version
        for period in forecast.periods[:14]:  # Show up to 14 periods (7 days, day and night)
            name = period.name or "Unknown"
            temp = period.temperature
            unit = period.temperature_unit or "F"
            details = period.detailed_forecast or "No details available"

            # Convert temperature if needed
            if unit == "F" and isinstance(temp, int | float):
                temp_f = temp
                temp_c = (temp - 32) * 5 / 9
            elif unit == "C" and isinstance(temp, int | float):
                temp_c = temp
                temp_f = (temp * 9 / 5) + 32
            else:
                temp_f = temp
                temp_c = None

            # Format temperature based on user preference
            if temp_f is not None:
                temp_str = format_temperature(
                    temp_f, unit_pref, temperature_c=temp_c, precision=precision
                )
            else:
                temp_str = "N/A"

            text += f"{name}: {temp_str}\n"
            text += f"{details}\n\n"

        return text.rstrip()  # Remove trailing newlines

    def format_alerts(self, alerts: WeatherAlerts | None, location: Location) -> str:
        """Format weather alerts exactly like the wx version."""
        if not alerts or not alerts.has_alerts():
            return f"Weather alerts for {location.name}:\nNo active weather alerts."

        active_alerts = alerts.get_active_alerts()
        if not active_alerts:
            return f"Weather alerts for {location.name}:\nNo active weather alerts."

        text = f"Weather alerts for {location.name}:\n\n"

        # Format each alert (limit to 5 for readability like wx version)
        for i, alert in enumerate(active_alerts[:5]):
            if i > 0:
                text += "\n"

            event = alert.event or "Weather Alert"
            severity = alert.severity or "Unknown"
            headline = alert.headline or ""
            description = alert.description or ""

            text += f"Alert {i + 1}: {event}\n"
            text += f"Severity: {severity}\n"

            if headline:
                text += f"Headline: {headline}\n"

            if description:
                # Truncate long descriptions for readability like wx version
                if len(description) > 200:
                    description = description[:200] + "..."
                text += f"Description: {description}\n"

            # Add expiration if available
            if alert.expires:
                expires_str = alert.expires.strftime("%m/%d %I:%M %p")
                text += f"Expires: {expires_str}\n"

        return text.rstrip()  # Remove trailing newlines

    def _calculate_dewpoint(self, temperature_f: float, humidity: float) -> float:
        """Calculate dewpoint from temperature and humidity."""
        # Convert to Celsius for calculation
        temp_c = (temperature_f - 32) * 5 / 9

        # Magnus formula approximation
        a = 17.27
        b = 237.7

        alpha = ((a * temp_c) / (b + temp_c)) + (humidity / 100.0)
        dewpoint_c = (b * alpha) / (a - alpha)

        # Convert back to Fahrenheit
        return (dewpoint_c * 9 / 5) + 32

    def _get_uv_description(self, uv_index: float) -> str:
        """Get UV index description."""
        if uv_index < 3:
            return "Low"
        if uv_index < 6:
            return "Moderate"
        if uv_index < 8:
            return "High"
        if uv_index < 11:
            return "Very High"
        return "Extreme"

    def _format_hourly_summary(self, hourly_forecast: HourlyForecast) -> str:
        """Format hourly forecast summary matching wx version."""
        if not hourly_forecast or not hourly_forecast.has_data():
            return ""

        text = "Next 6 Hours:\n"
        unit_pref = self._get_temperature_unit_preference()

        # Get next 6 hours of data
        next_hours = hourly_forecast.get_next_hours(6)

        for period in next_hours:
            if not period.has_data():
                continue

            # Format time (convert from ISO to readable format)
            formatted_time = self._format_hour_time(period.start_time)

            # Format temperature
            temp_text = self._format_hourly_temperature(
                period.temperature, period.temperature_unit, unit_pref
            )

            # Format conditions
            condition = period.short_forecast or "Unknown"

            # Format wind if available
            wind_text = ""
            if period.wind_speed and period.wind_direction:
                wind_text = f", {period.wind_direction} {period.wind_speed}"
            elif period.wind_speed:
                wind_text = f", {period.wind_speed}"

            # Combine into line
            text += f"{formatted_time}: {temp_text}, {condition}{wind_text}\n"

        return text

    def _format_hour_time(self, start_time: datetime) -> str:
        """Format hour time to match wx version (12:30 PM format)."""
        if not start_time:
            return "Unknown"

        try:
            # Convert to 12-hour format with AM/PM
            hour = start_time.hour
            minute = start_time.minute

            am_pm = "AM" if hour < 12 else "PM"
            if hour == 0:
                hour = 12
            elif hour > 12:
                hour -= 12

            return f"{hour}:{minute:02d} {am_pm}"
        except Exception:
            return "Unknown"

    def _format_hourly_temperature(
        self, temperature: float | None, temp_unit: str, unit_pref: TemperatureUnit
    ) -> str:
        """Format hourly temperature according to user preference."""
        if temperature is None:
            return "Unknown"

        # Convert to both units
        if temp_unit == "F":
            temp_f = temperature
            temp_c = (temperature - 32) * 5 / 9
        else:
            temp_c = temperature
            temp_f = (temperature * 9 / 5) + 32

        # Format according to preference
        if unit_pref == TemperatureUnit.FAHRENHEIT:
            return f"{temp_f:.0f}°F"
        if unit_pref == TemperatureUnit.CELSIUS:
            return f"{temp_c:.0f}°C"
        # Both
        return f"{temp_f:.0f}°F ({temp_c:.0f}°C)"
