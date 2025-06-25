"""Temperature utility functions for AccessiWeather Simple.

This module provides utility functions for temperature conversion and formatting,
copied from the wx version for consistency.
"""

import logging
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
    """Convert Celsius to Fahrenheit.

    Args:
        celsius: Temperature in Celsius

    Returns:
        Temperature in Fahrenheit
    """
    return (celsius * 9 / 5) + 32


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius.

    Args:
        fahrenheit: Temperature in Fahrenheit

    Returns:
        Temperature in Celsius
    """
    return (fahrenheit - 32) * 5 / 9


def format_temperature(
    temperature: int | float | None,
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
    temperature_c: int | float | None = None,
    precision: int = 1,
    smart_precision: bool = True,
) -> str:
    """Format temperature for display based on user preference.

    Args:
        temperature: Temperature value (assumed to be in Fahrenheit if temperature_c is None)
        unit: Temperature unit preference
        temperature_c: Temperature in Celsius (if available)
        precision: Number of decimal places to display
        smart_precision: If True, use 0 decimals for whole numbers

    Returns:
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
    elif unit == TemperatureUnit.CELSIUS:
        return f"{temperature_c:.{c_precision}f}°{TEMP_UNIT_CELSIUS}"
    else:  # BOTH
        return f"{temperature:.{f_precision}f}°{TEMP_UNIT_FAHRENHEIT} ({temperature_c:.{c_precision}f}°{TEMP_UNIT_CELSIUS})"


def get_temperature_values(
    temperature: int | float | None, temperature_c: int | float | None = None
) -> tuple[float | None, float | None]:
    """Get both Fahrenheit and Celsius values from available temperature data.

    Args:
        temperature: Temperature value (assumed to be in Fahrenheit if temperature_c is None)
        temperature_c: Temperature in Celsius (if available)

    Returns:
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
