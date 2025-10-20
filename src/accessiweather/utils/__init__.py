"""
Utility modules for AccessiWeather Simple.

This package provides utility functions for temperature conversion, unit formatting,
and other common operations, copied from the wx version for consistency.
"""

from .temperature_utils import (
    TemperatureUnit,
    calculate_dewpoint,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    format_temperature,
    get_temperature_values,
)
from .taf_decoder import decode_taf_text
from .unit_utils import (
    convert_wind_direction_to_cardinal,
    format_combined_wind,
    format_precipitation,
    format_pressure,
    format_visibility,
    format_wind_speed,
)

__all__ = [
    # Temperature utilities
    "TemperatureUnit",
    "calculate_dewpoint",
    "celsius_to_fahrenheit",
    "fahrenheit_to_celsius",
    "format_temperature",
    "get_temperature_values",
    # Aviation decoding
    "decode_taf_text",
    # Unit utilities
    "format_wind_speed",
    "format_pressure",
    "format_visibility",
    "format_precipitation",
    "convert_wind_direction_to_cardinal",
    "format_combined_wind",
]
