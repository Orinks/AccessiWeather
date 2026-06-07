"""Provider-neutral normalization helpers for weather API adapters."""

from __future__ import annotations

from dataclasses import dataclass

from .utils.temperature_utils import TemperatureUnit, calculate_dewpoint
from .weather_client_parsers import (
    convert_f_to_c,
    convert_wind_speed_to_mph_and_kph,
    normalize_pressure,
    normalize_temperature,
)

KM_PER_MILE = 1.609344
MB_PER_INHG = 33.8639


@dataclass(frozen=True)
class TemperaturePair:
    """A temperature represented in both AccessiWeather display units."""

    fahrenheit: float | None
    celsius: float | None


@dataclass(frozen=True)
class SpeedPair:
    """A speed represented in both AccessiWeather display units."""

    mph: float | None
    kph: float | None


@dataclass(frozen=True)
class PressurePair:
    """A pressure represented in both AccessiWeather display units."""

    inches: float | None
    millibars: float | None


@dataclass(frozen=True)
class VisibilityPair:
    """A visibility distance represented in both AccessiWeather display units."""

    miles: float | None
    kilometers: float | None


@dataclass(frozen=True)
class ApparentTemperatureClassification:
    """Feels-like temperature split into chill/index fields."""

    wind_chill_f: float | None = None
    wind_chill_c: float | None = None
    heat_index_f: float | None = None
    heat_index_c: float | None = None


def as_float(value: object) -> float | None:
    """Return ``value`` as a float, treating missing or invalid values as absent."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_humidity_percent(value: object, *, fraction: bool = False) -> int | None:
    """Normalize humidity to a rounded 0-100 percentage."""
    numeric = as_float(value)
    if numeric is None:
        return None
    if fraction:
        numeric *= 100
    return round(numeric)


def normalize_temperature_pair(value: object, unit: str | None) -> TemperaturePair:
    """Normalize a provider temperature value to Fahrenheit and Celsius."""
    numeric = as_float(value)
    if numeric is None:
        return TemperaturePair(None, None)
    temp_f, temp_c = normalize_temperature(numeric, unit)
    return TemperaturePair(temp_f, temp_c)


def normalize_dewpoint_pair(
    dewpoint_value: object,
    dewpoint_unit: str | None,
    *,
    fallback_temperature_f: float | None,
    humidity_percent: int | None,
) -> TemperaturePair:
    """Normalize dewpoint, calculating it from temperature and humidity when absent."""
    dewpoint = normalize_temperature_pair(dewpoint_value, dewpoint_unit)
    if dewpoint.fahrenheit is not None or dewpoint.celsius is not None:
        return dewpoint

    if fallback_temperature_f is None or humidity_percent is None:
        return TemperaturePair(None, None)

    dewpoint_f = calculate_dewpoint(
        fallback_temperature_f,
        humidity_percent,
        unit=TemperatureUnit.FAHRENHEIT,
    )
    return TemperaturePair(dewpoint_f, convert_f_to_c(dewpoint_f))


def normalize_pressure_pair(value: object, unit: str | None) -> PressurePair:
    """Normalize pressure to inches of mercury and millibars."""
    numeric = as_float(value)
    if numeric is None:
        return PressurePair(None, None)
    pressure_in, pressure_mb = normalize_pressure(numeric, unit)
    return PressurePair(pressure_in, pressure_mb)


def normalize_pressure_to_pascals(value: object, unit: str | None) -> float | None:
    """Normalize a pressure value to Pascals for NWS-compatible mapped payloads."""
    numeric = as_float(value)
    if numeric is None:
        return None

    unit_text = (unit or "").strip().lower()
    if "hpa" in unit_text or "mb" in unit_text:
        return numeric * 100
    if "pa" in unit_text:
        return numeric
    if "inch" in unit_text or unit_text in {"in", "inhg"}:
        return numeric * 3386.39
    return numeric * 100


def normalize_millibars(value: object) -> PressurePair:
    """Normalize provider values that are already millibars/hectopascals."""
    numeric = as_float(value)
    if numeric is None:
        return PressurePair(None, None)
    return PressurePair(numeric / MB_PER_INHG, numeric)


def _canonical_wind_unit(unit: str | None) -> str | None:
    unit_text = (unit or "").strip().lower()
    if unit_text in {"m/s", "meter/s", "meters/s", "metre/s", "metres/s"}:
        return "wmoUnit:m_s-1"
    if unit_text in {"km/h", "kmh", "kph"}:
        return "wmoUnit:km_h-1"
    if unit_text in {"mph", "mi/h"}:
        return "wmoUnit:mi_h-1"
    if unit_text in {"kn", "kt", "knot", "knots"}:
        return "wmoUnit:kn"
    return unit


def normalize_speed_pair(value: object, unit: str | None) -> SpeedPair:
    """Normalize wind speed to miles per hour and kilometers per hour."""
    numeric = as_float(value)
    if numeric is None:
        return SpeedPair(None, None)
    mph, kph = convert_wind_speed_to_mph_and_kph(numeric, _canonical_wind_unit(unit))
    return SpeedPair(mph, kph)


def format_speed(value: object, unit_label: str) -> str | None:
    """Format provider-native speed for text forecast fields."""
    numeric = as_float(value)
    if numeric is None:
        return None
    return f"{round(numeric)} {unit_label}"


def normalize_visibility_pair(
    value: object,
    unit: str | None,
    *,
    cap_miles: float | None = None,
) -> VisibilityPair:
    """Normalize visibility to miles and kilometers."""
    numeric = as_float(value)
    if numeric is None:
        return VisibilityPair(None, None)

    unit_text = (unit or "").strip().lower().replace(" ", "_")
    if "ft" in unit_text or "feet" in unit_text:
        miles = numeric / 5280
    elif "km" in unit_text or "kilometer" in unit_text or "kilometre" in unit_text:
        miles = numeric / KM_PER_MILE
    elif unit_text in {"mi", "mile", "miles"}:
        miles = numeric
    else:
        miles = numeric / 1609.344

    if cap_miles is not None:
        miles = min(miles, cap_miles)
    return VisibilityPair(miles, miles * KM_PER_MILE)


def classify_apparent_temperature(
    temperature_f: float | None,
    apparent_f: float | None,
    apparent_c: float | None,
) -> ApparentTemperatureClassification:
    """Classify a feels-like value as wind chill or heat index when it differs."""
    if apparent_f is None or temperature_f is None:
        return ApparentTemperatureClassification()
    if apparent_f < temperature_f:
        return ApparentTemperatureClassification(wind_chill_f=apparent_f, wind_chill_c=apparent_c)
    if apparent_f > temperature_f:
        return ApparentTemperatureClassification(heat_index_f=apparent_f, heat_index_c=apparent_c)
    return ApparentTemperatureClassification()


def pirate_temperature_unit(units: str) -> str:
    """Return the temperature unit used by a Pirate Weather unit group."""
    return "F" if units == "us" else "C"


def pirate_wind_unit(units: str) -> str:
    """Return the wind-speed unit used by a Pirate Weather unit group."""
    if units in {"us", "uk2"}:
        return "mph"
    if units == "ca":
        return "km/h"
    return "m/s"


def pirate_visibility_unit(units: str) -> str:
    """Return the visibility unit used by a Pirate Weather unit group."""
    return "mi" if units in {"us", "uk2"} else "km"
