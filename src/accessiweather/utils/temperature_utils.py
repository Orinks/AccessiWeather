"""
Temperature utility functions for AccessiWeather Simple.

This module provides utility functions for temperature conversion and formatting,
copied from the wx version for consistency.
"""

import logging
import math
from enum import Enum

logger = logging.getLogger(__name__)


class TemperatureUnit(str, Enum):
    """Temperature unit enum."""

    FAHRENHEIT = "fahrenheit"
    CELSIUS = "celsius"
    BOTH = "both"

    def __str__(self) -> str:
        return str(self.value)


# Constants for temperature unit display
TEMP_UNIT_FAHRENHEIT = "F"
TEMP_UNIT_CELSIUS = "C"


def celsius_to_fahrenheit(celsius: float) -> float:
    """
    Convert Celsius to Fahrenheit.

    Args:
    ----
        celsius: Temperature in Celsius

    Returns:
    -------
        Temperature in Fahrenheit

    """
    return (celsius * 9 / 5) + 32


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """
    Convert Fahrenheit to Celsius.

    Args:
    ----
        fahrenheit: Temperature in Fahrenheit

    Returns:
    -------
        Temperature in Celsius

    """
    return (fahrenheit - 32) * 5 / 9


def _normalize_dewpoint_unit(unit: TemperatureUnit | str | None) -> TemperatureUnit:
    """Normalize a dewpoint unit preference to a supported enum value."""
    if isinstance(unit, TemperatureUnit):
        return (
            TemperatureUnit.CELSIUS
            if unit == TemperatureUnit.CELSIUS
            else TemperatureUnit.FAHRENHEIT
        )

    if isinstance(unit, str):
        normalized = unit.strip().lower()
        if normalized in {"c", "celsius", "°c", "degc", "wmounit:degc"}:
            return TemperatureUnit.CELSIUS
        if normalized in {"f", "fahrenheit", "°f", "degf", "wmounit:degf"}:
            return TemperatureUnit.FAHRENHEIT

    return TemperatureUnit.FAHRENHEIT


def calculate_dewpoint(
    temperature: int | float | None,
    humidity: int | float | None,
    *,
    unit: TemperatureUnit | str = TemperatureUnit.FAHRENHEIT,
) -> float | None:
    """
    Calculate dewpoint temperature using the Magnus approximation.

    Args:
    ----
        temperature: Temperature measurement corresponding to the provided unit.
        humidity: Relative humidity percentage (0-100).
        unit: Unit of the provided temperature measurement.

    Returns:
    -------
        Dewpoint in the same unit family as requested, or None when inputs are invalid.

    """
    if temperature is None or humidity is None:
        return None

    try:
        temperature_value = float(temperature)
        humidity_value = float(humidity)
    except (TypeError, ValueError):
        logger.debug("Unable to calculate dewpoint due to non-numeric inputs", exc_info=True)
        return None

    if humidity_value <= 0:
        # Zero humidity leads to -inf dewpoint; treat as unavailable
        return None

    # Clamp humidity to [0.1, 100] to avoid math domain errors while preserving extremes
    humidity_ratio = min(max(humidity_value, 0.1), 100.0) / 100.0
    normalized_unit = _normalize_dewpoint_unit(unit)

    # Always perform Magnus formula in Celsius space
    temp_c = (
        temperature_value
        if normalized_unit == TemperatureUnit.CELSIUS
        else fahrenheit_to_celsius(temperature_value)
    )

    a = 17.27
    b = 237.7

    try:
        alpha = (a * temp_c) / (b + temp_c) + math.log(humidity_ratio)
    except ValueError:
        return None

    dewpoint_c = (b * alpha) / (a - alpha)

    if normalized_unit == TemperatureUnit.CELSIUS:
        return dewpoint_c

    return celsius_to_fahrenheit(dewpoint_c)


def format_temperature(
    temperature: int | float | None,
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    temperature_c: int | float | None = None,
    precision: int = 1,
    smart_precision: bool = True,
) -> str:
    """
    Format temperature for display based on user preference.

    Args:
    ----
        temperature: Temperature value (assumed to be in Fahrenheit if temperature_c is None)
        unit: Temperature unit preference
        temperature_c: Temperature in Celsius (if available)
        precision: Number of decimal places to display
        smart_precision: If True, use 0 decimals for whole numbers

    Returns:
    -------
        Formatted temperature string

    """
    if temperature is None and temperature_c is None:
        return "N/A"

    # Calculate missing temperature value if needed
    if temperature is None and temperature_c is not None:
        temperature = celsius_to_fahrenheit(temperature_c)
    elif temperature is not None and temperature_c is None:
        temperature_c = fahrenheit_to_celsius(temperature)

    # Determine precision for each temperature
    if smart_precision:
        f_precision = (
            0 if temperature is not None and temperature == int(temperature) else precision
        )
        c_precision = (
            0 if temperature_c is not None and temperature_c == int(temperature_c) else precision
        )
    else:
        f_precision = precision
        c_precision = precision

    # Format based on user preference
    if unit == TemperatureUnit.FAHRENHEIT:
        return f"{temperature:.{f_precision}f}°{TEMP_UNIT_FAHRENHEIT}"
    if unit == TemperatureUnit.CELSIUS:
        return f"{temperature_c:.{c_precision}f}°{TEMP_UNIT_CELSIUS}"
    # BOTH
    return f"{temperature:.{f_precision}f}°{TEMP_UNIT_FAHRENHEIT} ({temperature_c:.{c_precision}f}°{TEMP_UNIT_CELSIUS})"


def get_temperature_values(
    temperature: int | float | None, temperature_c: int | float | None = None
) -> tuple[float | None, float | None]:
    """
    Get both Fahrenheit and Celsius values from available temperature data.

    Args:
    ----
        temperature: Temperature value (assumed to be in Fahrenheit if temperature_c is None)
        temperature_c: Temperature in Celsius (if available)

    Returns:
    -------
        Tuple of (fahrenheit, celsius) values

    """
    if temperature is None and temperature_c is None:
        return None, None

    # Calculate missing temperature value if needed
    if temperature is None and temperature_c is not None:
        temperature = celsius_to_fahrenheit(temperature_c)
    elif temperature is not None and temperature_c is None:
        temperature_c = fahrenheit_to_celsius(temperature)

    return temperature, temperature_c
