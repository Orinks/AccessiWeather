"""
Unit utility functions for AccessiWeather Simple.

This module provides utility functions for formatting wind speed, pressure, and other units,
copied from the wx version for consistency.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .temperature_utils import TemperatureUnit

if TYPE_CHECKING:
    from ..units import DisplayUnitSystem

logger = logging.getLogger(__name__)


def _normalize_unit_system(unit_system: DisplayUnitSystem | str | None) -> str | None:
    """Normalize optional unit-system hints."""
    value = getattr(unit_system, "value", unit_system)
    if not isinstance(value, str):
        return None

    normalized = value.strip().lower()
    if normalized == "uk2":
        normalized = "uk"
    if normalized in {"us", "uk", "ca", "si"}:
        return normalized
    return None


def format_wind_speed(
    wind_speed_mph: int | float | None,
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    wind_speed_kph: int | float | None = None,
    precision: int = 1,
    unit_system: DisplayUnitSystem | str | None = None,
) -> str:
    """
    Format wind speed for display based on user preference.

    Args:
    ----
        wind_speed_mph: Wind speed in miles per hour
        unit: Temperature unit preference (used to determine display format)
        wind_speed_kph: Wind speed in kilometers per hour (if available)
        precision: Number of decimal places to display
        unit_system: Optional explicit unit-system override for auto-per-location display

    Returns:
    -------
        Formatted wind speed string

    """
    if wind_speed_mph is None and wind_speed_kph is None:
        return "N/A"

    # Calculate missing wind speed value if needed
    if wind_speed_mph is None and wind_speed_kph is not None:
        wind_speed_mph = wind_speed_kph * 0.621371
    elif wind_speed_mph is not None and wind_speed_kph is None:
        wind_speed_kph = wind_speed_mph * 1.60934
    assert wind_speed_mph is not None
    assert wind_speed_kph is not None

    normalized_system = _normalize_unit_system(unit_system)
    if normalized_system == "us":
        return f"{wind_speed_mph:.{precision}f} mph"
    if normalized_system == "uk":
        return f"{wind_speed_mph:.{precision}f} mph"
    if normalized_system == "ca":
        return f"{wind_speed_kph:.{precision}f} km/h"
    if normalized_system == "si":
        wind_speed_mps = wind_speed_kph / 3.6
        return f"{wind_speed_mps:.{precision}f} m/s"

    # Format based on user preference
    if unit == TemperatureUnit.FAHRENHEIT:
        return f"{wind_speed_mph:.{precision}f} mph"
    if unit == TemperatureUnit.CELSIUS:
        return f"{wind_speed_kph:.{precision}f} km/h"
    # BOTH
    return f"{wind_speed_mph:.{precision}f} mph ({wind_speed_kph:.{precision}f} km/h)"


def format_pressure(
    pressure_inhg: int | float | None,
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    pressure_mb: int | float | None = None,
    precision: int = 2,
    unit_system: DisplayUnitSystem | str | None = None,
) -> str:
    """
    Format pressure for display based on user preference.

    Args:
    ----
        pressure_inhg: Pressure in inches of mercury
        unit: Temperature unit preference (used to determine display format)
        pressure_mb: Pressure in millibars/hPa (if available)
        precision: Number of decimal places to display
        unit_system: Optional explicit unit-system override for auto-per-location display

    Returns:
    -------
        Formatted pressure string

    """
    if pressure_inhg is None and pressure_mb is None:
        return "N/A"

    # Calculate missing pressure value if needed
    if pressure_inhg is None and pressure_mb is not None:
        pressure_inhg = pressure_mb / 33.8639
    elif pressure_inhg is not None and pressure_mb is None:
        pressure_mb = pressure_inhg * 33.8639

    normalized_system = _normalize_unit_system(unit_system)
    if normalized_system == "us":
        return f"{pressure_inhg:.{precision}f} inHg"
    if normalized_system == "ca":
        return f"{pressure_mb / 10:.{precision}f} kPa"
    if normalized_system in {"uk", "si"}:
        return f"{pressure_mb:.{precision}f} hPa"

    # Format based on user preference
    if unit == TemperatureUnit.FAHRENHEIT:
        return f"{pressure_inhg:.{precision}f} inHg"
    if unit == TemperatureUnit.CELSIUS:
        return f"{pressure_mb:.{precision}f} hPa"
    # BOTH
    return f"{pressure_inhg:.{precision}f} inHg ({pressure_mb:.{precision}f} hPa)"


def format_visibility(
    visibility_miles: int | float | None,
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    visibility_km: int | float | None = None,
    precision: int = 1,
    unit_system: DisplayUnitSystem | str | None = None,
) -> str:
    """
    Format visibility for display based on user preference.

    Args:
    ----
        visibility_miles: Visibility in miles
        unit: Temperature unit preference (used to determine display format)
        visibility_km: Visibility in kilometers (if available)
        precision: Number of decimal places to display
        unit_system: Optional explicit unit-system override for auto-per-location display

    Returns:
    -------
        Formatted visibility string

    """
    if visibility_miles is None and visibility_km is None:
        return "N/A"

    # Calculate missing visibility value if needed
    if visibility_miles is None and visibility_km is not None:
        visibility_miles = visibility_km * 0.621371
    elif visibility_miles is not None and visibility_km is None:
        visibility_km = visibility_miles * 1.60934

    normalized_system = _normalize_unit_system(unit_system)
    if normalized_system in {"us", "uk"}:
        return f"{visibility_miles:.{precision}f} mi"
    if normalized_system in {"ca", "si"}:
        return f"{visibility_km:.{precision}f} km"

    # Format based on user preference
    if unit == TemperatureUnit.FAHRENHEIT:
        return f"{visibility_miles:.{precision}f} mi"
    if unit == TemperatureUnit.CELSIUS:
        return f"{visibility_km:.{precision}f} km"
    # BOTH
    return f"{visibility_miles:.{precision}f} mi ({visibility_km:.{precision}f} km)"


def format_precipitation(
    precipitation_inches: int | float | None,
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    precipitation_mm: int | float | None = None,
    precision: int = 2,
    unit_system: DisplayUnitSystem | str | None = None,
) -> str:
    """
    Format precipitation for display based on user preference.

    Args:
    ----
        precipitation_inches: Precipitation in inches
        unit: Temperature unit preference (used to determine display format)
        precipitation_mm: Precipitation in millimeters (if available)
        precision: Number of decimal places to display
        unit_system: Optional explicit unit-system override for auto-per-location display

    Returns:
    -------
        Formatted precipitation string

    """
    if precipitation_inches is None and precipitation_mm is None:
        return "N/A"

    # Calculate missing precipitation value if needed
    if precipitation_inches is None and precipitation_mm is not None:
        precipitation_inches = precipitation_mm / 25.4
    elif precipitation_inches is not None and precipitation_mm is None:
        precipitation_mm = precipitation_inches * 25.4

    normalized_system = _normalize_unit_system(unit_system)
    if normalized_system == "us":
        return f"{precipitation_inches:.{precision}f} in"
    if normalized_system in {"uk", "ca", "si"}:
        return f"{precipitation_mm:.{precision}f} mm"

    # Format based on user preference
    if unit == TemperatureUnit.FAHRENHEIT:
        return f"{precipitation_inches:.{precision}f} in"
    if unit == TemperatureUnit.CELSIUS:
        return f"{precipitation_mm:.{precision}f} mm"
    # BOTH
    return f"{precipitation_inches:.{precision}f} in ({precipitation_mm:.{precision}f} mm)"


def convert_wind_direction_to_cardinal(degrees: float | None) -> str:
    """
    Convert wind direction from degrees to cardinal direction.

    Args:
    ----
        degrees: Wind direction in degrees (0-360)

    Returns:
    -------
        Cardinal direction (N, NE, E, SE, S, SW, W, NW)

    """
    if degrees is None:
        return "N/A"

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


def format_combined_wind(
    wind_speed: float | None, wind_direction: float | str | None, speed_unit: str = "mph"
) -> str:
    """
    Format combined wind speed and direction for display.

    Args:
    ----
        wind_speed: Wind speed value
        wind_direction: Wind direction (degrees or cardinal)
        speed_unit: Unit for wind speed display

    Returns:
    -------
        Formatted wind string (e.g., "15 mph NW")

    """
    if wind_speed is None:
        return "N/A"

    try:
        speed_val = float(wind_speed)

        if speed_val == 0:
            return "Calm"

        # Format speed to whole number
        speed_str = f"{int(round(speed_val))} {speed_unit}"

        # Handle direction
        if isinstance(wind_direction, int | float):
            direction = convert_wind_direction_to_cardinal(wind_direction)
        else:
            direction = str(wind_direction) if wind_direction else ""

        if direction and direction != "N/A":
            return f"{speed_str} {direction}"
        return speed_str

    except (ValueError, TypeError):
        return "N/A"
