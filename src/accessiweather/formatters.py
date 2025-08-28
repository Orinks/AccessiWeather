"""Weather data formatters for AccessiWeather.

This module provides simple text formatting for weather data display,
optimized for accessibility and screen reader compatibility.
"""

import logging

from .models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    Location,
    WeatherAlerts,
    WeatherData,
)

logger = logging.getLogger(__name__)


class WeatherFormatter:
    """Simple weather data formatter for display."""

    def __init__(self, settings: AppSettings):
        """Initialize the instance."""
        self.settings = settings

    def format_current_conditions(
        self, current: CurrentConditions | None, location: Location
    ) -> str:
        """Format current conditions for display."""
        if not current or not current.has_data():
            return f"Current conditions for {location.name}:\nNo current weather data available."

        lines = [f"Current conditions for {location.name}:"]

        # Temperature
        if current.temperature_f is not None or current.temperature_c is not None:
            temp_text = self._format_temperature(current.temperature_f, current.temperature_c)
            lines.append(f"Temperature: {temp_text}")

        # Feels like temperature
        if current.feels_like_f is not None or current.feels_like_c is not None:
            feels_like_text = self._format_temperature(current.feels_like_f, current.feels_like_c)
            lines.append(f"Feels like: {feels_like_text}")

        # Condition
        if current.condition:
            lines.append(f"Conditions: {current.condition}")

        # Humidity
        if current.humidity is not None:
            lines.append(f"Humidity: {current.humidity}%")

        # Wind
        wind_text = self._format_wind(
            current.wind_speed_mph, current.wind_speed_kph, current.wind_direction
        )
        if wind_text:
            lines.append(f"Wind: {wind_text}")

        # Pressure
        pressure_text = self._format_pressure(current.pressure_in, current.pressure_mb)
        if pressure_text:
            lines.append(f"Pressure: {pressure_text}")

        # Visibility
        if current.visibility_miles is not None:
            lines.append(f"Visibility: {current.visibility_miles} miles")

        # UV Index
        if current.uv_index is not None:
            uv_desc = self._get_uv_description(current.uv_index)
            lines.append(f"UV Index: {current.uv_index} ({uv_desc})")

        # Last updated
        if current.last_updated:
            time_str = current.last_updated.strftime("%I:%M %p")
            lines.append(f"Last updated: {time_str}")

        return "\n".join(lines)

    def format_forecast(self, forecast: Forecast | None, location: Location) -> str:
        """Format forecast for display."""
        if not forecast or not forecast.has_data():
            return f"Forecast for {location.name}:\nNo forecast data available."

        lines = [f"Forecast for {location.name}:"]

        for period in forecast.periods[:7]:  # Show up to 7 days
            period_lines = [f"\n{period.name}:"]

            # Temperature
            if period.temperature is not None:
                temp_unit = period.temperature_unit or "F"
                if temp_unit.upper() == "F":
                    temp_f = period.temperature
                    temp_c = (temp_f - 32) * 5 / 9 if temp_f is not None else None
                else:
                    temp_c = period.temperature
                    temp_f = (temp_c * 9 / 5) + 32 if temp_c is not None else None

                temp_text = self._format_temperature(temp_f, temp_c)
                period_lines.append(f"  Temperature: {temp_text}")

            # Conditions
            if period.short_forecast:
                period_lines.append(f"  Conditions: {period.short_forecast}")

            # Wind
            if period.wind_speed or period.wind_direction:
                wind_parts = []
                if period.wind_direction:
                    wind_parts.append(period.wind_direction)
                if period.wind_speed:
                    wind_parts.append(period.wind_speed)
                wind_text = " ".join(wind_parts)
                period_lines.append(f"  Wind: {wind_text}")

            # Detailed forecast (if enabled and available)
            if (
                self.settings.show_detailed_forecast
                and period.detailed_forecast
                and period.detailed_forecast != period.short_forecast
            ):
                # Wrap long detailed forecasts
                detailed = self._wrap_text(period.detailed_forecast, 80)
                period_lines.append(f"  Details: {detailed}")

            lines.extend(period_lines)

        # Generation time
        if forecast.generated_at:
            time_str = forecast.generated_at.strftime("%I:%M %p")
            lines.append(f"\nForecast generated: {time_str}")

        return "\n".join(lines)

    def format_alerts(self, alerts: WeatherAlerts | None, location: Location) -> str:
        """Format weather alerts for display."""
        if not alerts or not alerts.has_alerts():
            return f"Weather alerts for {location.name}:\nNo active weather alerts."

        active_alerts = alerts.get_active_alerts()
        if not active_alerts:
            return f"Weather alerts for {location.name}:\nNo active weather alerts."

        lines = [f"Weather alerts for {location.name}:"]

        for i, alert in enumerate(active_alerts, 1):
            lines.append(f"\nAlert {i}: {alert.title}")

            # Severity and urgency
            if alert.severity != "Unknown" or alert.urgency != "Unknown":
                severity_parts = []
                if alert.severity != "Unknown":
                    severity_parts.append(f"Severity: {alert.severity}")
                if alert.urgency != "Unknown":
                    severity_parts.append(f"Urgency: {alert.urgency}")
                lines.append(f"  {', '.join(severity_parts)}")

            # Event type
            if alert.event:
                lines.append(f"  Event: {alert.event}")

            # Areas
            if alert.areas:
                areas_text = ", ".join(alert.areas[:3])  # Limit to first 3 areas
                if len(alert.areas) > 3:
                    areas_text += f" and {len(alert.areas) - 3} more"
                lines.append(f"  Areas: {areas_text}")

            # Expiration
            if alert.expires:
                expires_str = alert.expires.strftime("%m/%d %I:%M %p")
                lines.append(f"  Expires: {expires_str}")

            # Description (truncated for readability)
            if alert.description:
                description = self._wrap_text(alert.description[:200], 80)
                if len(alert.description) > 200:
                    description += "..."
                lines.append(f"  Description: {description}")

            # Instructions
            if alert.instruction:
                instruction = self._wrap_text(alert.instruction[:150], 80)
                if len(alert.instruction) > 150:
                    instruction += "..."
                lines.append(f"  Instructions: {instruction}")

        return "\n".join(lines)

    def format_weather_summary(self, weather_data: WeatherData) -> str:
        """Format a brief weather summary for notifications or status."""
        if not weather_data.has_any_data():
            return f"No weather data available for {weather_data.location.name}"

        parts = [weather_data.location.name]

        # Current temperature and conditions
        if weather_data.current and weather_data.current.has_data():
            current = weather_data.current

            # Temperature
            if current.temperature_f is not None:
                temp_text = self._format_temperature(current.temperature_f, current.temperature_c)
                parts.append(temp_text)

            # Conditions
            if current.condition:
                parts.append(current.condition)

        # Active alerts count
        if weather_data.alerts and weather_data.alerts.has_alerts():
            active_count = len(weather_data.alerts.get_active_alerts())
            if active_count > 0:
                parts.append(f"{active_count} alert{'s' if active_count != 1 else ''}")

        return " - ".join(parts)

    def _format_temperature(self, temp_f: float | None, temp_c: float | None) -> str:
        """Format temperature based on user preferences."""
        if temp_f is None and temp_c is None:
            return "Unknown"

        # Calculate missing temperature if needed
        if temp_f is None and temp_c is not None:
            temp_f = (temp_c * 9 / 5) + 32
        elif temp_c is None and temp_f is not None:
            temp_c = (temp_f - 32) * 5 / 9

        # Format based on user preference
        if self.settings.temperature_unit == "f":
            return f"{temp_f:.0f}°F"
        if self.settings.temperature_unit == "c":
            return f"{temp_c:.0f}°C"
        # both
        return f"{temp_f:.0f}°F ({temp_c:.0f}°C)"

    def _format_wind(
        self, speed_mph: float | None, speed_kph: float | None, direction: str | None
    ) -> str:
        """Format wind information."""
        if speed_mph is None and speed_kph is None and not direction:
            return ""

        parts = []

        # Direction - handle both string and numeric directions
        if direction is not None:
            if isinstance(direction, int | float):
                # Convert numeric degrees to cardinal direction
                direction_str = self._degrees_to_cardinal(direction)
                if direction_str:
                    parts.append(direction_str)
            else:
                parts.append(str(direction))

        # Speed
        if speed_mph is not None:
            parts.append(f"{speed_mph:.0f} mph")
        elif speed_kph is not None:
            parts.append(f"{speed_kph:.0f} kph")

        return " ".join(parts) if parts else ""

    def _format_pressure(self, pressure_in: float | None, pressure_mb: float | None) -> str:
        """Format pressure information."""
        if pressure_in is not None:
            return f"{pressure_in:.2f} in"
        if pressure_mb is not None:
            return f"{pressure_mb:.0f} mb"
        return ""

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

    def _degrees_to_cardinal(self, degrees: float) -> str | None:
        """Convert wind direction degrees to cardinal direction."""
        if degrees is None:
            return None

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
        index = round(degrees / 22.5) % 16
        return directions[index]

    def _wrap_text(self, text: str, width: int) -> str:
        """Wrap text for better readability."""
        if len(text) <= width:
            return text

        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(" ".join(current_line))

        return "\n    ".join(lines)  # Indent continuation lines
