"""
Taskbar icon text updater for dynamic weather display.

This module provides the TaskbarIconUpdater class which handles formatting and
updating the system tray icon tooltip text based on current weather conditions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .format_string_parser import FormatStringParser

if TYPE_CHECKING:
    from .models import WeatherData

logger = logging.getLogger(__name__)

DEFAULT_TOOLTIP_TEXT = "AccessiWeather"
TOOLTIP_MAX_LENGTH = 127
PLACEHOLDER_NA = "N/A"


class TaskbarIconUpdater:
    """
    Manages taskbar/system tray icon text updates based on weather data.

    This class handles:
    - Format string parsing and variable substitution
    - Dynamic format selection based on weather conditions
    - Error handling for missing/invalid data
    - Tooltip text truncation for platform limits
    """

    def __init__(
        self,
        text_enabled: bool = False,
        dynamic_enabled: bool = True,
        format_string: str = "{temp} {condition}",
        temperature_unit: str = "both",
        verbosity_level: str = "standard",
    ):
        """
        Initialize the TaskbarIconUpdater.

        Args:
            text_enabled: Whether taskbar icon text updates are enabled
            dynamic_enabled: Whether dynamic format selection is enabled
            format_string: The format string to use for the tooltip
            temperature_unit: Temperature unit preference (fahrenheit, celsius, both)
            verbosity_level: Information verbosity level (minimal, standard, detailed)

        """
        self.text_enabled = text_enabled
        self.dynamic_enabled = dynamic_enabled
        self.format_string = format_string
        self.temperature_unit = temperature_unit
        self.verbosity_level = verbosity_level
        self.parser = FormatStringParser()
        self._last_format_error: str | None = None

    def update_settings(
        self,
        text_enabled: bool | None = None,
        dynamic_enabled: bool | None = None,
        format_string: str | None = None,
        temperature_unit: str | None = None,
        verbosity_level: str | None = None,
    ) -> None:
        """
        Update taskbar icon settings.

        Args:
            text_enabled: Whether taskbar icon text updates are enabled
            dynamic_enabled: Whether dynamic format selection is enabled
            format_string: The format string to use for the tooltip
            temperature_unit: Temperature unit preference
            verbosity_level: Information verbosity level (minimal, standard, detailed)

        """
        if text_enabled is not None:
            self.text_enabled = text_enabled
        if dynamic_enabled is not None:
            self.dynamic_enabled = dynamic_enabled
        if format_string is not None:
            self.format_string = format_string
        if temperature_unit is not None:
            self.temperature_unit = temperature_unit
        if verbosity_level is not None:
            self.verbosity_level = verbosity_level

    def format_tooltip(
        self,
        weather_data: WeatherData | None,
        location_name: str | None = None,
    ) -> str:
        """
        Format the tooltip text based on weather data and settings.

        The output varies based on verbosity_level:
        - minimal: Location + temperature only
        - standard: Location + temperature + condition (default behavior)
        - detailed: Location + temperature + condition + feels like + humidity + wind

        Args:
            weather_data: Current weather data, or None if unavailable
            location_name: Name of the current location

        Returns:
            Formatted tooltip text, or default text if formatting fails

        """
        if not self.text_enabled:
            return DEFAULT_TOOLTIP_TEXT

        if weather_data is None:
            return DEFAULT_TOOLTIP_TEXT

        if not self.dynamic_enabled:
            return DEFAULT_TOOLTIP_TEXT

        current = getattr(weather_data, "current_conditions", None)
        if current is None or not current.has_data():
            return DEFAULT_TOOLTIP_TEXT

        try:
            data = self._extract_weather_variables(current, location_name)
            tooltip = self._format_by_verbosity(data)

            if location_name and tooltip and not tooltip.startswith(location_name):
                tooltip = f"{location_name}: {tooltip}"

            return self._truncate_tooltip(tooltip)
        except Exception as exc:
            logger.debug("Failed to format tooltip: %s", exc)
            return DEFAULT_TOOLTIP_TEXT

    def _format_by_verbosity(self, data: dict[str, str]) -> str:
        """
        Format tooltip content based on verbosity level.

        Args:
            data: Dictionary of weather variable values

        Returns:
            Formatted tooltip string appropriate to verbosity level

        """
        if self.verbosity_level == "minimal":
            # Minimal: just temperature
            return data.get("temp", PLACEHOLDER_NA)

        if self.verbosity_level == "detailed":
            # Detailed: temp + condition + feels_like + humidity + wind
            parts = [data.get("temp", PLACEHOLDER_NA)]

            condition = data.get("condition")
            if condition and condition != PLACEHOLDER_NA:
                parts.append(condition)

            feels_like = data.get("feels_like")
            if feels_like and feels_like != PLACEHOLDER_NA:
                parts.append(f"Feels {feels_like}")

            humidity = data.get("humidity")
            if humidity and humidity != PLACEHOLDER_NA:
                parts.append(f"Humidity {humidity}")

            wind = data.get("wind")
            if wind and wind != PLACEHOLDER_NA:
                parts.append(f"Wind {wind}")

            return " | ".join(parts)

        # Standard (default): temp + condition
        format_string = self.format_string
        return self._format_with_fallback(format_string, data)

    def _extract_weather_variables(
        self,
        current: Any,
        location_name: str | None = None,
    ) -> dict[str, str]:
        """
        Extract weather variables from current conditions for substitution.

        Args:
            current: Current conditions object
            location_name: Name of the current location

        Returns:
            Dictionary of variable names to string values

        """
        data: dict[str, str] = {}

        data["location"] = location_name or PLACEHOLDER_NA
        data["temp"] = self._format_temperature(current)
        data["temp_f"] = self._format_temp_value(getattr(current, "temperature_f", None), "F")
        data["temp_c"] = self._format_temp_value(getattr(current, "temperature_c", None), "C")
        data["condition"] = getattr(current, "condition", None) or PLACEHOLDER_NA
        # Try both humidity field names (model uses 'humidity', some code uses 'relative_humidity')
        humidity = getattr(current, "humidity", None) or getattr(current, "relative_humidity", None)
        data["humidity"] = self._format_numeric(humidity, "%")
        data["wind"] = self._format_wind(current)
        data["wind_speed"] = self._format_numeric(getattr(current, "wind_speed", None), " mph")
        # wind_direction can be str ("NW") or int (270 degrees) - ensure it's a string
        wind_dir = getattr(current, "wind_direction", None)
        data["wind_dir"] = str(wind_dir) if wind_dir is not None else PLACEHOLDER_NA
        data["pressure"] = self._format_numeric(getattr(current, "pressure", None), " inHg")
        data["feels_like"] = self._format_feels_like(current)
        data["uv"] = self._format_numeric(getattr(current, "uv_index", None), "")
        data["visibility"] = self._format_numeric(getattr(current, "visibility", None), " mi")
        data["high"] = PLACEHOLDER_NA
        data["low"] = PLACEHOLDER_NA
        data["precip"] = self._format_numeric(getattr(current, "precipitation", None), " in")
        data["precip_chance"] = self._format_numeric(
            getattr(current, "precipitation_probability", None), ""
        )

        return data

    def _format_temperature(self, current: Any) -> str:
        """Format temperature according to user preference."""
        temp_f = getattr(current, "temperature_f", None)
        temp_c = getattr(current, "temperature_c", None)

        if temp_f is None and temp_c is None:
            return PLACEHOLDER_NA

        if self.temperature_unit in ("fahrenheit", "f"):
            return self._format_temp_value(temp_f, "F")
        if self.temperature_unit in ("celsius", "c"):
            if temp_c is not None:
                return self._format_temp_value(temp_c, "C")
            return PLACEHOLDER_NA
        if temp_f is not None and temp_c is not None:
            return f"{temp_f:.0f}F/{temp_c:.0f}C"
        if temp_f is not None:
            return f"{temp_f:.0f}F"
        if temp_c is not None:
            return f"{temp_c:.0f}C"
        return PLACEHOLDER_NA

    def _format_feels_like(self, current: Any) -> str:
        """Format feels-like temperature."""
        feels_f = getattr(current, "feels_like_f", None)
        feels_c = getattr(current, "feels_like_c", None)

        if feels_f is None and feels_c is None:
            return PLACEHOLDER_NA

        if self.temperature_unit in ("fahrenheit", "f"):
            return self._format_temp_value(feels_f, "F")
        if self.temperature_unit in ("celsius", "c"):
            if feels_c is not None:
                return self._format_temp_value(feels_c, "C")
            return PLACEHOLDER_NA
        if feels_f is not None and feels_c is not None:
            return f"{feels_f:.0f}F/{feels_c:.0f}C"
        if feels_f is not None:
            return f"{feels_f:.0f}F"
        if feels_c is not None:
            return f"{feels_c:.0f}C"
        return PLACEHOLDER_NA

    def _format_temp_value(self, value: float | None, suffix: str) -> str:
        """Format a single temperature value."""
        if value is None:
            return PLACEHOLDER_NA
        return f"{value:.0f}{suffix}"

    def _format_numeric(self, value: float | int | None, suffix: str) -> str:
        """Format a numeric value with optional suffix."""
        if value is None:
            return PLACEHOLDER_NA
        if isinstance(value, float):
            if value == int(value):
                return f"{int(value)}{suffix}"
            return f"{value:.1f}{suffix}"
        return f"{value}{suffix}"

    def _format_wind(self, current: Any) -> str:
        """Format wind direction and speed."""
        direction = getattr(current, "wind_direction", None)
        speed = getattr(current, "wind_speed", None)

        if direction is None and speed is None:
            return PLACEHOLDER_NA

        parts = []
        if direction is not None:
            # Convert to string - direction can be str ("NW") or int (270 degrees)
            parts.append(str(direction))
        if speed is not None:
            parts.append(f"at {speed:.0f} mph")

        return " ".join(parts) if parts else PLACEHOLDER_NA

    def _format_with_fallback(self, format_string: str, data: dict[str, str]) -> str:
        """
        Format the string with fallback for invalid format strings.

        Args:
            format_string: The format string to use
            data: Dictionary of variable values

        Returns:
            Formatted string, or default if format is invalid

        """
        is_valid, error = self.parser.validate_format_string(format_string)
        if not is_valid:
            if error != self._last_format_error:
                logger.warning("Invalid format string: %s", error)
                self._last_format_error = error
            format_string = "{temp} {condition}"

        result = self.parser.format_string(format_string, data)

        if "Error" in result:
            logger.warning("Format error: %s", result)
            return DEFAULT_TOOLTIP_TEXT

        return result.strip()

    def _truncate_tooltip(self, text: str) -> str:
        """
        Truncate tooltip text to platform-dependent limits.

        Args:
            text: The tooltip text to truncate

        Returns:
            Truncated text with ellipsis if needed

        """
        if not text:
            return DEFAULT_TOOLTIP_TEXT

        if len(text) <= TOOLTIP_MAX_LENGTH:
            return text

        return text[: TOOLTIP_MAX_LENGTH - 3] + "..."

    def validate_format_string(self, format_string: str) -> tuple[bool, str | None]:
        """
        Validate a format string.

        Args:
            format_string: The format string to validate

        Returns:
            Tuple of (is_valid, error_message)

        """
        return self.parser.validate_format_string(format_string)

    def get_available_variables(self) -> dict[str, str]:
        """
        Get all available variables for format strings.

        Returns:
            Dictionary of variable names to descriptions

        """
        return self.parser.SUPPORTED_PLACEHOLDERS.copy()
