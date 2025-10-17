"""Shared parsing and utility functions for weather data processing in AccessiWeather."""

from __future__ import annotations

import logging
from datetime import datetime

__all__ = [
    "convert_mps_to_mph",
    "convert_wind_speed_to_mph",
    "convert_wind_speed_to_kph",
    "convert_wind_speed_to_mph_and_kph",
    "convert_pa_to_inches",
    "convert_pa_to_mb",
    "normalize_temperature",
    "normalize_pressure",
    "convert_f_to_c",
    "degrees_to_cardinal",
    "weather_code_to_description",
    "format_date_name",
]

logger = logging.getLogger(__name__)

OPEN_METEO_WEATHER_CODE_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def convert_mps_to_mph(mps: float | None) -> float | None:
    """Convert meters per second to miles per hour."""
    return mps * 2.237 if mps is not None else None


def convert_wind_speed_to_mph(value: float | None, unit_code: str | None) -> float | None:
    """Normalize WMO wind speed units to miles per hour."""
    if value is None:
        return None
    if not unit_code:
        return value
    unit_code = unit_code.lower()
    if unit_code.endswith(("m_s-1", "mps")):
        return value * 2.237
    if unit_code.endswith(("km_h-1", "kmh", "km/h")):
        return value * 0.621371
    if unit_code.endswith(("mi_h-1", "mph", "mp/h")):
        return value
    if unit_code.endswith(("kn", "kt")):
        return value * 1.15078
    return value


def convert_wind_speed_to_kph(value: float | None, unit_code: str | None) -> float | None:
    """Normalize WMO wind speed units to kilometers per hour."""
    if value is None:
        return None
    if not unit_code:
        return value
    unit_code = unit_code.lower()
    if unit_code.endswith(("m_s-1", "mps")):
        return value * 3.6
    if unit_code.endswith(("km_h-1", "kmh", "km/h")):
        return value
    if unit_code.endswith(("mi_h-1", "mph", "mp/h")):
        return value * 1.60934
    if unit_code.endswith(("kn", "kt")):
        return value * 1.852
    return value


def convert_wind_speed_to_mph_and_kph(
    value: float | None, unit_code: str | None
) -> tuple[float | None, float | None]:
    """Return wind speed converted to both miles per hour and kilometers per hour."""
    return (
        convert_wind_speed_to_mph(value, unit_code),
        convert_wind_speed_to_kph(value, unit_code),
    )


def convert_pa_to_inches(pa: float | None) -> float | None:
    """Convert pressure from pascals to inches of mercury."""
    return pa * 0.0002953 if pa is not None else None


def convert_pa_to_mb(pa: float | None) -> float | None:
    """Convert pressure from pascals to millibars (hectopascals)."""
    return pa / 100 if pa is not None else None


def normalize_temperature(
    value: float | None, unit: str | None
) -> tuple[float | None, float | None]:
    """Return temperature normalized to both Fahrenheit and Celsius."""
    if value is None:
        return None, None

    unit_lower = (unit or "").lower()
    if "f" in unit_lower:
        temp_f = value
        temp_c = convert_f_to_c(temp_f)
    elif "c" in unit_lower:
        temp_c = value
        temp_f = (temp_c * 9 / 5) + 32
    else:
        temp_f = value
        temp_c = convert_f_to_c(temp_f)
    return temp_f, temp_c


def normalize_pressure(value: float | None, unit: str | None) -> tuple[float | None, float | None]:
    """Return pressure normalized to both inches of mercury and millibars."""
    if value is None:
        return None, None

    unit_lower = (unit or "").lower()
    if "hpa" in unit_lower or "mb" in unit_lower:
        pressure_mb = value
        pressure_in = value * 0.0295299830714
    elif "pa" in unit_lower:
        pressure_mb = value / 100
        pressure_in = convert_pa_to_inches(value)
    elif "inch" in unit_lower or unit_lower.endswith("in"):
        pressure_in = value
        pressure_mb = value * 33.8639
    else:
        pressure_mb = value
        pressure_in = None
    return pressure_in, pressure_mb


def convert_f_to_c(fahrenheit: float | None) -> float | None:
    """Convert Fahrenheit to Celsius."""
    return (fahrenheit - 32) * 5 / 9 if fahrenheit is not None else None


def degrees_to_cardinal(degrees: float | None) -> str | None:
    """Convert wind direction in degrees to its cardinal direction."""
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


def weather_code_to_description(code: int | None) -> str | None:
    """Convert an Open-Meteo weather code to a human-readable description."""
    if code is None:
        return None

    return OPEN_METEO_WEATHER_CODE_DESCRIPTIONS.get(code, f"Weather code {code}")


def format_date_name(date_str: str, index: int) -> str:
    """Format a date string into a friendly name such as Today, Tomorrow, or weekday."""
    if index == 0:
        return "Today"
    if index == 1:
        return "Tomorrow"
    try:
        date_obj = datetime.fromisoformat(date_str)
        return date_obj.strftime("%A")
    except (ValueError, TypeError):
        logger.debug("Failed to format date '%s' at index %s", date_str, index)
        return f"Day {index + 1}"
