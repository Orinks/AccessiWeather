"""Open-Meteo current-condition parsing helpers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from .models import CurrentConditions
from .utils.temperature_utils import TemperatureUnit, calculate_dewpoint
from .weather_client_parsers import (
    convert_f_to_c,
    convert_wind_speed_to_mph_and_kph,
    normalize_pressure,
    normalize_temperature,
    weather_code_to_description,
)

logger = logging.getLogger(__name__)

SNOW_WEATHER_CODES = {71, 73, 75, 77, 85, 86}
RAIN_WEATHER_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
ACTIVE_PRECIP_EPSILON_IN = 0.001
NEAR_ZERO_SNOW_EPSILON_IN = 0.0005
VISIBILITY_CAP_M = 16093.4


def pick_precipitation_type(rain_in: float, snow_in: float) -> list[str] | None:
    """Infer precipitation type from rain/snow rates with conservative thresholds."""
    has_rain = rain_in > ACTIVE_PRECIP_EPSILON_IN
    has_snow = snow_in > ACTIVE_PRECIP_EPSILON_IN
    if has_rain and has_snow:
        return ["rain", "snow"]
    if has_rain:
        return ["rain"]
    if has_snow:
        return ["snow"]
    return None


def resolve_current_condition_description(current: dict[str, Any]) -> str | None:
    """Resolve current condition text using weather_code plus rain/snow rates."""
    weather_code = current.get("weather_code")
    base = weather_code_to_description(weather_code)

    try:
        code = int(weather_code) if weather_code is not None else None
    except (TypeError, ValueError):
        code = None

    rain = float(current.get("rain") or 0.0) + float(current.get("showers") or 0.0)
    snow = float(current.get("snowfall") or 0.0)

    if rain <= ACTIVE_PRECIP_EPSILON_IN and snow <= ACTIVE_PRECIP_EPSILON_IN:
        return base

    if rain > ACTIVE_PRECIP_EPSILON_IN and snow <= NEAR_ZERO_SNOW_EPSILON_IN:
        if code in SNOW_WEATHER_CODES:
            return "Light drizzle" if rain < 0.02 else "Slight rain"
        return base

    if snow > (rain * 1.5):
        if code in RAIN_WEATHER_CODES:
            return "Mixed rain and snow"
        return base

    if rain > ACTIVE_PRECIP_EPSILON_IN and snow > ACTIVE_PRECIP_EPSILON_IN:
        return "Mixed rain and snow"

    return base


def parse_iso_datetime(value: str | None, utc_offset_seconds: int | None = None) -> datetime | None:
    """Parse an ISO 8601 datetime string, converting to the location timezone."""
    if not value:
        return None

    candidates = [value]
    if value.endswith("Z"):
        candidates.append(value[:-1] + "+00:00")

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            local_tz = (
                timezone(timedelta(seconds=utc_offset_seconds))
                if utc_offset_seconds is not None
                else None
            )

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=local_tz) if local_tz else dt.replace(tzinfo=UTC)
            elif local_tz and (
                dt.tzinfo == UTC or (dt.utcoffset() and dt.utcoffset().total_seconds() == 0)
            ):
                dt = dt.astimezone(local_tz)

            return dt
        except ValueError:
            continue

    logger.debug("Failed to parse ISO datetime value: %s", value)
    return None


def _parse_uv_index(current: dict[str, Any], daily: dict[str, Any]) -> float | None:
    raw_current_uv = current.get("uv_index")
    if raw_current_uv is not None:
        try:
            return float(raw_current_uv)
        except (TypeError, ValueError):
            return None

    uv_values = daily.get("uv_index_max") or []
    if uv_values:
        try:
            return float(uv_values[0]) if uv_values[0] is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _normalize_snow_depth(
    value: float | None,
    unit: str,
) -> tuple[float | None, float | None]:
    if value is None:
        return None, None
    if "ft" in unit or "feet" in unit:
        return value * 12, value * 30.48
    if "m" in unit and "mm" not in unit:
        return value * 39.3701, value * 100
    return value * 39.3701, value * 100


def parse_openmeteo_current_conditions(data: dict) -> CurrentConditions:
    """Parse Open-Meteo current condition payload into a CurrentConditions model."""
    current = data.get("current", {})
    units = data.get("current_units", {})
    daily = data.get("daily", {})
    utc_offset_seconds = data.get("utc_offset_seconds")

    temp_f, temp_c = normalize_temperature(
        current.get("temperature_2m"), units.get("temperature_2m")
    )

    humidity = current.get("relative_humidity_2m")
    humidity = round(humidity) if humidity is not None else None

    dewpoint_f = None
    dewpoint_c = None
    if temp_f is not None and humidity is not None:
        dewpoint_f = calculate_dewpoint(temp_f, humidity, unit=TemperatureUnit.FAHRENHEIT)
        if dewpoint_f is not None:
            dewpoint_c = convert_f_to_c(dewpoint_f)

    wind_speed_mph, wind_speed_kph = convert_wind_speed_to_mph_and_kph(
        current.get("wind_speed_10m"), units.get("wind_speed_10m")
    )

    pressure_in, pressure_mb = normalize_pressure(
        current.get("pressure_msl"), units.get("pressure_msl")
    )

    feels_like_f, feels_like_c = normalize_temperature(
        current.get("apparent_temperature"), units.get("apparent_temperature")
    )

    sunrise_time = None
    sunset_time = None
    if daily:
        sunrise_list = daily.get("sunrise", [])
        sunset_list = daily.get("sunset", [])
        if sunrise_list and len(sunrise_list) > 0:
            sunrise_time = parse_iso_datetime(sunrise_list[0], utc_offset_seconds)
        if sunset_list and len(sunset_list) > 0:
            sunset_time = parse_iso_datetime(sunset_list[0], utc_offset_seconds)

    uv_index = _parse_uv_index(current, daily)

    snowfall_rate = current.get("snowfall")
    rain_rate_in = float(current.get("rain") or 0.0) + float(current.get("showers") or 0.0)
    snow_rate_in = float(snowfall_rate or 0.0)
    precipitation_type = pick_precipitation_type(rain_rate_in, snow_rate_in)

    snow_depth_in, snow_depth_cm = _normalize_snow_depth(
        current.get("snow_depth"),
        units.get("snow_depth", "").lower(),
    )

    visibility_m = current.get("visibility")
    if visibility_m is not None:
        visibility_m = min(visibility_m, VISIBILITY_CAP_M)
    visibility_miles = visibility_m / 1609.344 if visibility_m is not None else None
    visibility_km = visibility_m / 1000 if visibility_m is not None else None

    wind_chill_f = None
    wind_chill_c = None
    heat_index_f = None
    heat_index_c = None
    if feels_like_f is not None and temp_f is not None:
        if feels_like_f < temp_f:
            wind_chill_f = feels_like_f
            wind_chill_c = feels_like_c
        elif feels_like_f > temp_f:
            heat_index_f = feels_like_f
            heat_index_c = feels_like_c

    return CurrentConditions(
        temperature_f=temp_f,
        temperature_c=temp_c,
        condition=resolve_current_condition_description(current),
        humidity=humidity,
        dewpoint_f=dewpoint_f,
        dewpoint_c=dewpoint_c,
        wind_speed_mph=wind_speed_mph,
        wind_speed_kph=wind_speed_kph,
        wind_direction=current.get("wind_direction_10m"),
        pressure_in=pressure_in,
        pressure_mb=pressure_mb,
        feels_like_f=feels_like_f,
        feels_like_c=feels_like_c,
        visibility_miles=visibility_miles,
        visibility_km=visibility_km,
        sunrise_time=sunrise_time,
        sunset_time=sunset_time,
        uv_index=uv_index,
        snowfall_rate_in=snowfall_rate,
        snow_depth_in=snow_depth_in,
        snow_depth_cm=snow_depth_cm,
        wind_chill_f=wind_chill_f,
        wind_chill_c=wind_chill_c,
        heat_index_f=heat_index_f,
        heat_index_c=heat_index_c,
        precipitation_type=precipitation_type,
    )
