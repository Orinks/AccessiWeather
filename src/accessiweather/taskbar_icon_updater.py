"""
Taskbar icon text updater for dynamic weather display.

This module provides the TaskbarIconUpdater class which handles formatting and
updating the system tray icon tooltip text based on current weather conditions.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from .format_string_parser import FormatStringParser
from .utils.temperature_utils import (
    TemperatureUnit,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
)
from .utils.unit_utils import (
    format_precipitation,
    format_pressure,
    format_visibility,
    format_wind_speed,
)

if TYPE_CHECKING:
    from .models import WeatherData

logger = logging.getLogger(__name__)

DEFAULT_TOOLTIP_TEXT = "AccessiWeather"
DEFAULT_TOOLTIP_FORMAT = "{temp} {condition}"
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
        format_string: str = DEFAULT_TOOLTIP_FORMAT,
        temperature_unit: str = "both",
        verbosity_level: str = "standard",
        round_values: bool = False,
    ):
        """
        Initialize the TaskbarIconUpdater.

        Args:
            text_enabled: Whether taskbar icon text updates are enabled
            dynamic_enabled: Whether dynamic format selection is enabled
            format_string: The format string to use for the tooltip
            temperature_unit: Temperature unit preference (fahrenheit, celsius, both)
            verbosity_level: Information verbosity level (minimal, standard, detailed)
            round_values: Whether to round numeric values to whole numbers

        """
        self.text_enabled = text_enabled
        self.dynamic_enabled = dynamic_enabled
        self.format_string = format_string
        self.temperature_unit = temperature_unit
        self.verbosity_level = verbosity_level
        self.round_values = round_values
        self.parser = FormatStringParser()
        self._last_format_error: str | None = None

    def update_settings(
        self,
        text_enabled: bool | None = None,
        dynamic_enabled: bool | None = None,
        format_string: str | None = None,
        temperature_unit: str | None = None,
        verbosity_level: str | None = None,
        round_values: bool | None = None,
    ) -> None:
        """
        Update taskbar icon settings.

        Args:
            text_enabled: Whether taskbar icon text updates are enabled
            dynamic_enabled: Whether dynamic format selection is enabled
            format_string: The format string to use for the tooltip
            temperature_unit: Temperature unit preference
            verbosity_level: Information verbosity level (minimal, standard, detailed)
            round_values: Whether to round numeric values to whole numbers

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
        if round_values is not None:
            self.round_values = round_values

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

        current = getattr(weather_data, "current_conditions", None)
        if current is None or not current.has_data():
            return DEFAULT_TOOLTIP_TEXT

        try:
            data = self._extract_weather_variables(
                current,
                location_name,
                weather_data=weather_data,
            )
            return self.format_text(data)
        except Exception as exc:
            logger.debug("Failed to format tooltip: %s", exc)
            return DEFAULT_TOOLTIP_TEXT

    def format_text(
        self,
        data: dict[str, str],
        format_string: str | None = None,
    ) -> str:
        """Format tray text from already-extracted placeholder data."""
        result = self._format_with_fallback(format_string or self.format_string, data)
        return self._truncate_tooltip(result)

    def build_preview(
        self,
        format_string: str,
        weather_data: WeatherData | None = None,
        location_name: str | None = None,
    ) -> str:
        """Build preview text using live weather data when available, else safe sample values."""
        current = getattr(weather_data, "current_conditions", None) if weather_data else None
        if current is not None and current.has_data():
            data = self._extract_weather_variables(
                current,
                location_name,
                weather_data=weather_data,
            )
        else:
            preview_weather = self._build_preview_weather_data()
            data = self._extract_weather_variables(
                preview_weather.current_conditions,
                location_name or "Sample Location",
                weather_data=preview_weather,
            )

        return self.format_text(data, format_string=format_string)

    def _extract_weather_variables(
        self,
        current: Any,
        location_name: str | None = None,
        *,
        weather_data: WeatherData | Any | None = None,
    ) -> dict[str, str]:
        """
        Extract weather variables from current conditions for substitution.

        Args:
            current: Current conditions object
            location_name: Name of the current location
            weather_data: Optional weather payload used for forecast-derived placeholders
                like high and low.

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
        data["wind_speed"] = self._format_wind_speed(current)
        # wind_direction can be str ("NW") or int (270 degrees) - ensure it's a string
        wind_dir = getattr(current, "wind_direction", None)
        data["wind_dir"] = str(wind_dir) if wind_dir is not None else PLACEHOLDER_NA
        data["pressure"] = self._format_pressure(current)
        data["feels_like"] = self._format_feels_like(current)
        data["uv"] = self._format_numeric(getattr(current, "uv_index", None), "")
        data["visibility"] = self._format_visibility(current)
        data["high"], data["low"] = self._format_forecast_temperatures(weather_data)
        data["precip"] = self._format_precipitation(current)
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

    def _normalize_temperature_unit(self) -> TemperatureUnit:
        """Normalize legacy short forms to the shared temperature unit enum."""
        normalized = (self.temperature_unit or "both").strip().lower()
        if normalized in {"fahrenheit", "f"}:
            return TemperatureUnit.FAHRENHEIT
        if normalized in {"celsius", "c"}:
            return TemperatureUnit.CELSIUS
        return TemperatureUnit.BOTH

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

    def _format_wind_speed(self, current: Any) -> str:
        """Format wind speed using the selected unit preference."""
        precision = 0 if self.round_values else 1
        return format_wind_speed(
            getattr(current, "wind_speed_mph", None),
            unit=self._normalize_temperature_unit(),
            wind_speed_kph=getattr(current, "wind_speed_kph", None),
            precision=precision,
        )

    def _format_pressure(self, current: Any) -> str:
        """Format pressure using the selected unit preference."""
        precision = 0 if self.round_values else 2
        return format_pressure(
            getattr(current, "pressure_in", None),
            unit=self._normalize_temperature_unit(),
            pressure_mb=getattr(current, "pressure_mb", None),
            precision=precision,
        )

    def _format_visibility(self, current: Any) -> str:
        """Format visibility using the selected unit preference."""
        precision = 0 if self.round_values else 1
        return format_visibility(
            getattr(current, "visibility_miles", None),
            unit=self._normalize_temperature_unit(),
            visibility_km=getattr(current, "visibility_km", None),
            precision=precision,
        )

    def _format_precipitation(self, current: Any) -> str:
        """Format precipitation using the selected unit preference when source data exists."""
        precip_in = getattr(current, "precipitation_in", None)
        if precip_in is None:
            precip_in = getattr(current, "precipitation_inches", None)
        if precip_in is None:
            precip_in = getattr(current, "precipitation", None)

        precision = 0 if self.round_values else 2
        return format_precipitation(
            precip_in,
            unit=self._normalize_temperature_unit(),
            precipitation_mm=getattr(current, "precipitation_mm", None),
            precision=precision,
        )

    def _format_forecast_temperatures(
        self, weather_data: WeatherData | Any | None
    ) -> tuple[str, str]:
        """Return high/low placeholders from forecast data when it exists."""
        forecast = getattr(weather_data, "forecast", None) if weather_data is not None else None
        periods = getattr(forecast, "periods", None) or []
        if not periods:
            return PLACEHOLDER_NA, PLACEHOLDER_NA

        high_period = next((period for period in periods if self._is_day_period(period)), None)
        low_period = next((period for period in periods if self._is_night_period(period)), None)

        if high_period is None:
            high_period = next(
                (period for period in periods if getattr(period, "temperature", None) is not None),
                None,
            )

        high = self._format_forecast_temperature(
            getattr(high_period, "temperature", None) if high_period is not None else None,
            getattr(high_period, "temperature_unit", "F") if high_period is not None else "F",
        )

        low_value = None
        low_unit = "F"
        if low_period is not None:
            low_value = getattr(low_period, "temperature_low", None)
            if low_value is None:
                low_value = getattr(low_period, "temperature", None)
            low_unit = getattr(low_period, "temperature_unit", "F")
        else:
            for period in periods:
                low_value = getattr(period, "temperature_low", None)
                if low_value is not None:
                    low_unit = getattr(period, "temperature_unit", "F")
                    break

        return high, self._format_forecast_temperature(low_value, low_unit)

    def _format_forecast_temperature(self, value: float | None, unit_code: str | None) -> str:
        """Format a forecast temperature according to the selected unit preference."""
        if value is None:
            return PLACEHOLDER_NA

        normalized_unit = (unit_code or "F").strip().upper()
        temp_f = value if normalized_unit == "F" else celsius_to_fahrenheit(value)
        temp_c = value if normalized_unit == "C" else fahrenheit_to_celsius(value)

        if self.temperature_unit in ("fahrenheit", "f"):
            return self._format_temp_value(temp_f, "F")
        if self.temperature_unit in ("celsius", "c"):
            return self._format_temp_value(temp_c, "C")
        return f"{temp_f:.0f}F/{temp_c:.0f}C"

    def _is_day_period(self, period: Any) -> bool:
        """Best-effort detection for daytime forecast periods."""
        name = str(getattr(period, "name", "") or "").lower()
        return "night" not in name and "tonight" not in name and "overnight" not in name

    def _is_night_period(self, period: Any) -> bool:
        """Best-effort detection for nighttime forecast periods."""
        name = str(getattr(period, "name", "") or "").lower()
        return any(token in name for token in ("night", "tonight", "overnight"))

    def _build_preview_weather_data(self) -> Any:
        """Create sample weather data so preview formatting matches live formatting rules."""
        current = SimpleNamespace(
            temperature_f=72.0,
            temperature_c=22.0,
            condition="Partly Cloudy",
            humidity=55,
            wind_speed=8.0,
            wind_speed_mph=8.0,
            wind_speed_kph=12.9,
            wind_direction="NW",
            pressure=30.1,
            pressure_in=30.1,
            pressure_mb=1019.3,
            feels_like_f=74.0,
            feels_like_c=23.0,
            uv_index=5,
            visibility_miles=10.0,
            visibility_km=16.1,
            precipitation=0.0,
            precipitation_mm=0.0,
            precipitation_probability=20,
            has_data=lambda: True,
        )
        forecast = SimpleNamespace(
            periods=[
                SimpleNamespace(name="Today", temperature=78.0, temperature_unit="F"),
                SimpleNamespace(name="Tonight", temperature=61.0, temperature_unit="F"),
            ]
        )
        return SimpleNamespace(current_conditions=current, forecast=forecast)

    def _format_with_fallback(self, format_string: str, data: dict[str, str]) -> str:
        """
        Format the string with fallback for invalid format strings.

        Unknown placeholders (e.g. ``{foo}``) are left as literal text in the
        output — they do NOT trigger a full format-string fallback.  Only
        genuinely malformed input (unbalanced braces) causes a fallback to
        ``DEFAULT_TOOLTIP_TEXT``.

        Args:
            format_string: The format string to use
            data: Dictionary of variable values

        Returns:
            Formatted string, or default if format is genuinely invalid

        """
        # Detect unbalanced braces before handing off to the parser.
        # Unknown placeholder names are handled safely by FormatStringParser.format_string
        # which leaves them as literal "{key}" text, so we no longer reject them here.
        if format_string.count("{") != format_string.count("}"):
            error = "Unbalanced braces in format string"
            if error != self._last_format_error:
                logger.warning("Invalid format string: %s", error)
                self._last_format_error = error
            return DEFAULT_TOOLTIP_TEXT

        result = self.parser.format_string(format_string, data)

        if "Error" in result:
            logger.warning("Format error: %s", result)
            return DEFAULT_TOOLTIP_TEXT

        result = result.strip()
        return result or DEFAULT_TOOLTIP_TEXT

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
