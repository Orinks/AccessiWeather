"""Unit utility functions for AccessiWeather.

This module provides utility functions for unit conversion and formatting.
"""

import logging
from typing import Optional, Union

from accessiweather.utils.temperature_utils import TemperatureUnit

logger = logging.getLogger(__name__)


def format_wind_speed(
    wind_speed_mph: Optional[Union[int, float]],
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    wind_speed_kph: Optional[Union[int, float]] = None,
    precision: int = 1,
) -> str:
    """Format wind speed for display based on user preference.

    Args:
        wind_speed_mph: Wind speed in miles per hour
        unit: Temperature unit preference (used to determine display format)
        wind_speed_kph: Wind speed in kilometers per hour (if available)
        precision: Number of decimal places to display

    Returns:
        Formatted wind speed string
    """
    if wind_speed_mph is None and wind_speed_kph is None:
        return "N/A"

    # Calculate missing wind speed value if needed
    if wind_speed_mph is None and wind_speed_kph is not None:
        wind_speed_mph = wind_speed_kph * 0.621371
    elif wind_speed_mph is not None and wind_speed_kph is None:
        wind_speed_kph = wind_speed_mph * 1.60934

    # Format based on user preference
    if unit == TemperatureUnit.FAHRENHEIT:
        return f"{wind_speed_mph:.{precision}f} mph"
    elif unit == TemperatureUnit.CELSIUS:
        return f"{wind_speed_kph:.{precision}f} km/h"
    else:  # BOTH
        return f"{wind_speed_mph:.{precision}f} mph ({wind_speed_kph:.{precision}f} km/h)"


def format_pressure(
    pressure_inhg: Optional[Union[int, float]],
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    pressure_mb: Optional[Union[int, float]] = None,
    precision: int = 2,
) -> str:
    """Format pressure for display based on user preference.

    Args:
        pressure_inhg: Pressure in inches of mercury
        unit: Temperature unit preference (used to determine display format)
        pressure_mb: Pressure in millibars/hPa (if available)
        precision: Number of decimal places to display

    Returns:
        Formatted pressure string
    """
    if pressure_inhg is None and pressure_mb is None:
        return "N/A"

    # Calculate missing pressure value if needed
    if pressure_inhg is None and pressure_mb is not None:
        pressure_inhg = pressure_mb / 33.8639
    elif pressure_inhg is not None and pressure_mb is None:
        pressure_mb = pressure_inhg * 33.8639

    # Format based on user preference
    if unit == TemperatureUnit.FAHRENHEIT:
        return f"{pressure_inhg:.{precision}f} inHg"
    elif unit == TemperatureUnit.CELSIUS:
        return f"{pressure_mb:.{precision}f} hPa"
    else:  # BOTH
        return f"{pressure_inhg:.{precision}f} inHg ({pressure_mb:.{precision}f} hPa)"


def format_visibility(
    visibility_miles: Optional[Union[int, float]],
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    visibility_km: Optional[Union[int, float]] = None,
    precision: int = 1,
) -> str:
    """Format visibility for display based on user preference.

    Args:
        visibility_miles: Visibility in miles
        unit: Temperature unit preference (used to determine display format)
        visibility_km: Visibility in kilometers (if available)
        precision: Number of decimal places to display

    Returns:
        Formatted visibility string
    """
    if visibility_miles is None and visibility_km is None:
        return "N/A"

    # Calculate missing visibility value if needed
    if visibility_miles is None and visibility_km is not None:
        visibility_miles = visibility_km * 0.621371
    elif visibility_miles is not None and visibility_km is None:
        visibility_km = visibility_miles * 1.60934

    # Format based on user preference
    if unit == TemperatureUnit.FAHRENHEIT:
        return f"{visibility_miles:.{precision}f} mi"
    elif unit == TemperatureUnit.CELSIUS:
        return f"{visibility_km:.{precision}f} km"
    else:  # BOTH
        return f"{visibility_miles:.{precision}f} mi ({visibility_km:.{precision}f} km)"


def format_precipitation(
    precip_in: Optional[Union[int, float]],
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    precip_mm: Optional[Union[int, float]] = None,
    precision: int = 2,
) -> str:
    """Format precipitation for display based on user preference.

    Args:
        precip_in: Precipitation in inches
        unit: Temperature unit preference (used to determine display format)
        precip_mm: Precipitation in millimeters (if available)
        precision: Number of decimal places to display

    Returns:
        Formatted precipitation string
    """
    if precip_in is None and precip_mm is None:
        return "N/A"

    # Calculate missing precipitation value if needed
    if precip_in is None and precip_mm is not None:
        precip_in = precip_mm / 25.4
    elif precip_in is not None and precip_mm is None:
        precip_mm = precip_in * 25.4

    # Format based on user preference
    if unit == TemperatureUnit.FAHRENHEIT:
        return f"{precip_in:.{precision}f} in"
    elif unit == TemperatureUnit.CELSIUS:
        return f"{precip_mm:.{precision}f} mm"
    else:  # BOTH
        return f"{precip_in:.{precision}f} in ({precip_mm:.{precision}f} mm)"
