"""Weather data formatting for system tray icon."""

import logging
from typing import Any, Dict, List, Optional

from accessiweather.gui.settings_dialog import (
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


class SystemTrayFormatter:
    """Handles formatting of weather data for system tray display."""

    def __init__(self, format_parser, dynamic_format_manager):
        """Initialize the formatter.
        
        Args:
            format_parser: FormatStringParser instance
            dynamic_format_manager: DynamicFormatManager instance
        """
        self.format_parser = format_parser
        self.dynamic_format_manager = dynamic_format_manager

    def format_weather_data_for_tray(
        self,
        weather_data: Dict[str, Any],
        alerts_data: Optional[List[Dict[str, Any]]],
        settings: Dict[str, Any]
    ) -> Optional[str]:
        """Format weather data for system tray display.
        
        Args:
            weather_data: Current weather data
            alerts_data: Current alerts data
            settings: Application settings
            
        Returns:
            Formatted text for tray icon or None if formatting fails
        """
        if not weather_data:
            logger.debug("No weather data available for taskbar icon text")
            return None

        text_enabled = settings.get(TASKBAR_ICON_TEXT_ENABLED_KEY, False)
        if not text_enabled:
            return None

        # Get user preferences
        user_format_string = settings.get(
            TASKBAR_ICON_TEXT_FORMAT_KEY, "{location} {temp} {condition}"
        )
        dynamic_enabled = settings.get(TASKBAR_ICON_DYNAMIC_ENABLED_KEY, True)
        unit_pref_str = settings.get(TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT)

        # Convert string to enum
        unit_pref = self._get_temperature_unit(unit_pref_str)

        # Format the weather data
        formatted_data = self._format_weather_values(weather_data, unit_pref)

        try:
            # Determine which format string to use
            if dynamic_enabled:
                format_string = self.dynamic_format_manager.get_dynamic_format_string(
                    weather_data,
                    alerts_data,
                    user_format=user_format_string,
                )
            else:
                format_string = user_format_string

            # Add alert data if available
            if alerts_data:
                primary_alert = self._get_primary_alert(alerts_data)
                if primary_alert:
                    formatted_data.update({
                        "event": primary_alert.get("event", "Weather Alert"),
                        "severity": primary_alert.get("severity", "Unknown"),
                        "headline": primary_alert.get("headline", ""),
                    })

            # Format the string
            return self.format_parser.format_string(format_string, formatted_data)

        except Exception as e:
            logger.error(f"Error formatting taskbar icon text: {e}")
            return None

    def _get_temperature_unit(self, unit_pref_str: str) -> TemperatureUnit:
        """Convert temperature unit string to enum.
        
        Args:
            unit_pref_str: Temperature unit preference string
            
        Returns:
            TemperatureUnit enum value
        """
        if unit_pref_str == TemperatureUnit.FAHRENHEIT.value:
            return TemperatureUnit.FAHRENHEIT
        elif unit_pref_str == TemperatureUnit.CELSIUS.value:
            return TemperatureUnit.CELSIUS
        elif unit_pref_str == TemperatureUnit.BOTH.value:
            return TemperatureUnit.BOTH
        else:
            return TemperatureUnit.FAHRENHEIT

    def _format_weather_values(
        self, weather_data: Dict[str, Any], unit_pref: TemperatureUnit
    ) -> Dict[str, Any]:
        """Format weather values based on unit preference.
        
        Args:
            weather_data: Raw weather data
            unit_pref: Temperature unit preference
            
        Returns:
            Dictionary with formatted weather values
        """
        formatted_data = weather_data.copy()

        # Format temperature
        if "temp_f" in formatted_data and "temp_c" in formatted_data:
            temp_f = formatted_data.get("temp_f")
            temp_c = formatted_data.get("temp_c")
            if temp_f is not None:
                precision = 0 if unit_pref == TemperatureUnit.BOTH else 1
                formatted_data["temp"] = format_temperature(
                    temp_f,
                    unit_pref,
                    temperature_c=temp_c,
                    precision=precision,
                    smart_precision=True,
                )

        # Format feels like temperature
        if "feels_like_f" in formatted_data and "feels_like_c" in formatted_data:
            feels_like_f = formatted_data.get("feels_like_f")
            feels_like_c = formatted_data.get("feels_like_c")
            if feels_like_f is not None:
                precision = 0 if unit_pref == TemperatureUnit.BOTH else 1
                formatted_data["feels_like"] = format_temperature(
                    feels_like_f,
                    unit_pref,
                    temperature_c=feels_like_c,
                    precision=precision,
                    smart_precision=True,
                )

        # Format wind speed
        if "wind_speed" in formatted_data:
            wind_speed = formatted_data.get("wind_speed")
            wind_speed_kph = wind_speed * 1.60934 if wind_speed is not None else None
            formatted_data["wind_speed"] = format_wind_speed(
                wind_speed, unit_pref, wind_speed_kph=wind_speed_kph, precision=1
            )

        # Format pressure
        if "pressure" in formatted_data:
            pressure = formatted_data.get("pressure")
            pressure_mb = pressure * 33.8639 if pressure is not None else None
            formatted_data["pressure"] = format_pressure(
                pressure, unit_pref, pressure_mb=pressure_mb, precision=0
            )

        # Format visibility
        if "visibility" in formatted_data:
            visibility = formatted_data.get("visibility")
            visibility_km = visibility * 1.60934 if visibility is not None else None
            formatted_data["visibility"] = format_visibility(
                visibility, unit_pref, visibility_km=visibility_km, precision=1
            )

        # Format humidity
        if "humidity" in formatted_data:
            humidity = formatted_data.get("humidity")
            if humidity is not None:
                formatted_data["humidity"] = f"{humidity:.0f}"

        # Format UV index
        if "uv" in formatted_data:
            uv = formatted_data.get("uv")
            if uv is not None:
                formatted_data["uv"] = f"{uv:.0f}"

        # Format precipitation
        if "precip" in formatted_data:
            precip = formatted_data.get("precip")
            if precip is not None:
                formatted_data["precip"] = format_precipitation(precip, unit_pref, precision=1)

        # Format precipitation chance
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
