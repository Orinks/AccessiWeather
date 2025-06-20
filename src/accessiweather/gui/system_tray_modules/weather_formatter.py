"""Weather data formatting for system tray display.

This module provides weather data formatting functionality including:
- Temperature, wind, pressure, and other weather data formatting
- Dynamic format management integration
- Alert data handling and prioritization
"""

import logging
from typing import Any, Dict, List, Optional

from accessiweather.dynamic_format_manager import DynamicFormatManager
from accessiweather.format_string_parser import FormatStringParser
from accessiweather.gui.settings.constants import (
    DEFAULT_TEMPERATURE_UNIT,
    TASKBAR_ICON_DYNAMIC_ENABLED_KEY,
    TASKBAR_ICON_TEXT_ENABLED_KEY,
    TASKBAR_ICON_TEXT_FORMAT_KEY,
    TEMPERATURE_UNIT_KEY,
)
from accessiweather.utils.temperature_utils import TemperatureUnit, format_temperature
from accessiweather.utils.unit_utils import (
    format_precipitation,
    format_pressure,
    format_visibility,
    format_wind_speed,
)

logger = logging.getLogger(__name__)


class WeatherDataFormatter:
    """Handles weather data formatting for system tray display.

    This mixin expects the following methods to be provided by the implementing class:
    - set_icon(tooltip_text=None)

    And the following attributes:
    - frame: The main application frame
    """

    # These methods must be implemented by the class that uses this mixin
    def set_icon(self, tooltip_text=None):
        """Set the taskbar icon. Must be implemented by the implementing class."""
        raise NotImplementedError("set_icon must be implemented by the implementing class")

    @property
    def frame(self):
        """The main application frame. Must be set by the implementing class."""
        if not hasattr(self, "_frame"):
            raise NotImplementedError("frame must be set by the implementing class")
        return self._frame

    @frame.setter
    def frame(self, value):
        """Set the main application frame."""
        self._frame = value

    def __init__(self):
        """Initialize the weather data formatter."""
        self.format_parser = FormatStringParser()
        self.dynamic_format_manager = DynamicFormatManager()
        self.current_weather_data = {}
        self.current_alerts_data: Optional[List[Dict[str, Any]]] = None

    def update_weather_data(self, weather_data: Dict[str, Any]):
        """Update the current weather data and refresh the taskbar icon text.

        Args:
            weather_data: Dictionary containing current weather data
        """
        self.current_weather_data = weather_data
        self.update_icon_text()

    def update_alerts_data(self, alerts_data: Optional[List[Dict[str, Any]]]):
        """Update the current alerts data and refresh the taskbar icon text.

        Args:
            alerts_data: List of current weather alerts or None
        """
        self.current_alerts_data = alerts_data
        self.update_icon_text()

    def update_icon_text(self):
        """Update the taskbar icon text based on current settings and weather data."""
        # Check if we have weather data
        if not self.current_weather_data:
            logger.debug("No weather data available for taskbar icon text")
            return

        # Get settings from the frame's config
        settings = self.frame.config.get("settings", {})
        text_enabled = settings.get(TASKBAR_ICON_TEXT_ENABLED_KEY, False)

        if not text_enabled:
            # If text is not enabled, just set the default icon
            self.set_icon()
            return

        # Get the user's base format string, dynamic setting, and temperature unit preference
        user_format_string = settings.get(
            TASKBAR_ICON_TEXT_FORMAT_KEY, "{location} {temp} {condition}"
        )
        dynamic_enabled = settings.get(TASKBAR_ICON_DYNAMIC_ENABLED_KEY, True)
        unit_pref_str = settings.get(TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT)

        # Convert string to enum
        if unit_pref_str == TemperatureUnit.FAHRENHEIT.value:
            unit_pref = TemperatureUnit.FAHRENHEIT
        elif unit_pref_str == TemperatureUnit.CELSIUS.value:
            unit_pref = TemperatureUnit.CELSIUS
        elif unit_pref_str == TemperatureUnit.BOTH.value:
            unit_pref = TemperatureUnit.BOTH
        else:
            unit_pref = TemperatureUnit.FAHRENHEIT

        # Create a copy of the weather data to format values based on unit preference
        formatted_data = self._format_weather_data(self.current_weather_data, unit_pref)

        try:
            # Determine which format string to use
            if dynamic_enabled:
                # Get dynamic format string based on current conditions
                format_string = self.dynamic_format_manager.get_dynamic_format_string(
                    self.current_weather_data,
                    self.current_alerts_data,
                    user_format=user_format_string,
                )
            else:
                # Use the user's static format string
                format_string = user_format_string

            # Add alert data to formatted_data if we have alerts
            if self.current_alerts_data:
                primary_alert = self._get_primary_alert(self.current_alerts_data)
                if primary_alert:
                    formatted_data.update(
                        {
                            "event": primary_alert.get("event", "Weather Alert"),
                            "severity": primary_alert.get("severity", "Unknown"),
                            "headline": primary_alert.get("headline", ""),
                        }
                    )

            # Format the string with formatted weather data
            formatted_text = self.format_parser.format_string(format_string, formatted_data)

            # Update the icon with the new text
            self.set_icon(formatted_text)
            logger.debug(f"Updated taskbar icon text: {formatted_text}")
        except Exception as e:
            logger.error(f"Error updating taskbar icon text: {e}")
            # Fall back to default icon
            self.set_icon()

    def _format_weather_data(
        self, weather_data: Dict[str, Any], unit_pref: TemperatureUnit
    ) -> Dict[str, Any]:
        """Format weather data values based on unit preference.

        Args:
            weather_data: Raw weather data dictionary
            unit_pref: Temperature unit preference

        Returns:
            Dictionary with formatted weather values
        """
        formatted_data = weather_data.copy()

        # Format temperature if available
        if "temp_f" in formatted_data and "temp_c" in formatted_data:
            temp_f = formatted_data.get("temp_f")
            temp_c = formatted_data.get("temp_c")
            if temp_f is not None:
                # Use whole numbers (precision=0) when unit preference is 'both'
                precision = 0 if unit_pref == TemperatureUnit.BOTH else 1
                formatted_data["temp"] = format_temperature(
                    temp_f,
                    unit_pref,
                    temperature_c=temp_c,
                    precision=precision,
                    smart_precision=True,
                )

        # Format wind speed if available
        if "wind_speed" in formatted_data:
            wind_speed = formatted_data.get("wind_speed")
            wind_speed_kph = wind_speed * 1.60934 if wind_speed is not None else None
            formatted_data["wind_speed"] = format_wind_speed(
                wind_speed, unit_pref, wind_speed_kph=wind_speed_kph, precision=1
            )

        # Format pressure if available
        if "pressure" in formatted_data:
            pressure = formatted_data.get("pressure")
            pressure_mb = pressure * 33.8639 if pressure is not None else None
            formatted_data["pressure"] = format_pressure(
                pressure, unit_pref, pressure_mb=pressure_mb, precision=0
            )

        # Format visibility if available
        if "visibility" in formatted_data:
            visibility = formatted_data.get("visibility")
            visibility_km = visibility * 1.60934 if visibility is not None else None
            formatted_data["visibility"] = format_visibility(
                visibility, unit_pref, visibility_km=visibility_km, precision=1
            )

        # Format humidity if available
        if "humidity" in formatted_data:
            humidity = formatted_data.get("humidity")
            if humidity is not None:
                formatted_data["humidity"] = f"{humidity:.0f}"

        # Format feels like temperature if available
        if "feels_like_f" in formatted_data and "feels_like_c" in formatted_data:
            feels_like_f = formatted_data.get("feels_like_f")
            feels_like_c = formatted_data.get("feels_like_c")
            if feels_like_f is not None:
                # Use whole numbers (precision=0) when unit preference is 'both'
                precision = 0 if unit_pref == TemperatureUnit.BOTH else 1
                formatted_data["feels_like"] = format_temperature(
                    feels_like_f,
                    unit_pref,
                    temperature_c=feels_like_c,
                    precision=precision,
                    smart_precision=True,
                )

        # Format UV index if available
        if "uv" in formatted_data:
            uv = formatted_data.get("uv")
            if uv is not None:
                formatted_data["uv"] = f"{uv:.0f}"

        # Format precipitation if available
        if "precip" in formatted_data:
            precip = formatted_data.get("precip")
            if precip is not None:
                # Use format_precipitation function to handle units based on user preference
                formatted_data["precip"] = format_precipitation(precip, unit_pref, precision=1)

        # Format precipitation chance if available
        if "precip_chance" in formatted_data:
            precip_chance = formatted_data.get("precip_chance")
            if precip_chance is not None:
                formatted_data["precip_chance"] = f"{precip_chance:.0f}"

        return formatted_data

    def _get_primary_alert(self, alerts_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Get the primary (highest severity) alert from alerts data.

        Args:
            alerts_data: List of alert dictionaries

        Returns:
            Primary alert dictionary or None if no alerts
        """
        if not alerts_data:
            return None

        # Priority mapping for alert severities
        severity_priority = {
            "Extreme": 4,
            "Severe": 3,
            "Moderate": 2,
            "Minor": 1,
            "Unknown": 0,
        }

        primary_alert = None
        max_priority = -1

        for alert in alerts_data:
            severity = alert.get("severity", "Unknown")
            priority = severity_priority.get(severity, 0)

            if priority > max_priority:
                max_priority = priority
                primary_alert = alert

        return primary_alert
