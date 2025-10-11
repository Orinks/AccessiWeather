"""Reusable formatting helpers for weather presentation output."""

from __future__ import annotations

import textwrap
from datetime import datetime

from ...models import CurrentConditions, ForecastPeriod, HourlyForecastPeriod
from ...utils import (
    TemperatureUnit,
    calculate_dewpoint,
    convert_wind_direction_to_cardinal,
    format_pressure,
    format_temperature,
    format_visibility,
    format_wind_speed,
)


def format_temperature_pair(
    temp_f: float | None,
    temp_c: float | None,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Return a temperature string honoring the configured unit preference."""
    if temp_f is None and temp_c is None:
        return None
    return format_temperature(temp_f, unit_pref, temperature_c=temp_c, precision=precision)


def format_wind(current: CurrentConditions, unit_pref: TemperatureUnit) -> str | None:
    """Describe wind direction and speed or return calm when wind is negligible."""
    if (
        current.wind_speed_mph is None
        and current.wind_speed_kph is None
        and current.wind_direction is None
    ):
        return None

    speed_mph = current.wind_speed_mph
    if speed_mph is None and current.wind_speed_kph is not None:
        speed_mph = current.wind_speed_kph * 0.621371

    if speed_mph is not None and abs(speed_mph) < 0.5:
        return "Calm"

    direction = None
    if current.wind_direction is not None:
        if isinstance(current.wind_direction, (int, float)):
            direction = convert_wind_direction_to_cardinal(current.wind_direction)
        else:
            direction = str(current.wind_direction)

    speed = format_wind_speed(
        current.wind_speed_mph,
        unit_pref,
        wind_speed_kph=current.wind_speed_kph,
        precision=1,
    )
    if direction and speed:
        return f"{direction} at {speed}"
    if speed:
        return speed
    return direction


def format_dewpoint(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Calculate or reuse dewpoint and format it using the active preference."""
    dewpoint_f = current.dewpoint_f
    dewpoint_c = current.dewpoint_c

    if dewpoint_f is None and dewpoint_c is None:
        if current.temperature_f is None or current.humidity is None:
            return None
        dewpoint_f = calculate_dewpoint(
            current.temperature_f,
            current.humidity,
            unit=TemperatureUnit.FAHRENHEIT,
        )
        if dewpoint_f is None:
            return None
        dewpoint_c = (dewpoint_f - 32) * 5 / 9

    return format_temperature(
        dewpoint_f,
        unit_pref,
        temperature_c=dewpoint_c,
        precision=precision,
    )


def format_pressure_value(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
) -> str | None:
    """Format station pressure in the preferred unit, if available."""
    if current.pressure_in is None and current.pressure_mb is None:
        return None
    pressure_in = current.pressure_in
    pressure_mb = current.pressure_mb
    if pressure_in is None and pressure_mb is not None:
        pressure_in = pressure_mb / 33.8639
    return format_pressure(pressure_in, unit_pref, pressure_mb=pressure_mb, precision=0)


def format_visibility_value(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
) -> str | None:
    """Format horizontal visibility taking unit preference into account."""
    if current.visibility_miles is None and current.visibility_km is None:
        return None
    return format_visibility(
        current.visibility_miles,
        unit_pref,
        visibility_km=current.visibility_km,
        precision=1,
    )


def format_forecast_temperature(
    period: ForecastPeriod,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Format a forecast period temperature without mutating the period."""
    if period.temperature is None:
        return None
    temp = period.temperature
    unit = (period.temperature_unit or "F").upper()
    if unit == "F":
        temp_f = temp
        temp_c = (temp - 32) * 5 / 9
    else:
        temp_c = temp
        temp_f = (temp * 9 / 5) + 32
    return format_temperature(temp_f, unit_pref, temperature_c=temp_c, precision=precision)


def format_period_wind(period: ForecastPeriod) -> str | None:
    """Return a combined wind string for a forecast period, if available."""
    if not period.wind_speed and not period.wind_direction:
        return None
    parts: list[str] = []
    if period.wind_direction:
        parts.append(period.wind_direction)
    if period.wind_speed:
        parts.append(period.wind_speed)
    return " ".join(parts) if parts else None


def format_period_temperature(
    period: HourlyForecastPeriod,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Format an hourly forecast temperature with unit conversion."""
    if period.temperature is None:
        return None
    temp = period.temperature
    unit = (period.temperature_unit or "F").upper()
    if unit == "F":
        temp_f = temp
        temp_c = (temp - 32) * 5 / 9
    else:
        temp_c = temp
        temp_f = (temp * 9 / 5) + 32
    return format_temperature(temp_f, unit_pref, temperature_c=temp_c, precision=precision)


def format_hour_time(start_time: datetime | None) -> str:
    """Render an hour label for hourly forecast output."""
    if not start_time:
        return "Unknown"
    return start_time.strftime("%I:%M %p")


def format_timestamp(value: datetime) -> str:
    """Return a localised timestamp suitable for short metric labels."""
    timestamp = value
    if timestamp.tzinfo is not None:
        timestamp = timestamp.astimezone()
    return timestamp.strftime("%I:%M %p")


def get_uv_description(uv_index: float) -> str:
    """Describe a numeric UV index value."""
    if uv_index < 3:
        return "Low"
    if uv_index < 6:
        return "Moderate"
    if uv_index < 8:
        return "High"
    if uv_index < 11:
        return "Very High"
    return "Extreme"


def format_sun_time(sun_time: datetime | None) -> str | None:
    """
    Format sunrise or sunset time for display.

    Args:
    ----
        sun_time: Datetime object for sunrise or sunset

    Returns:
    -------
        Formatted time string (e.g., "6:32 AM") or None if time is not available

    """
    if sun_time is None:
        return None
    # Convert to local timezone if the datetime is timezone-aware
    local_time = sun_time
    if sun_time.tzinfo is not None:
        local_time = sun_time.astimezone()
    return local_time.strftime("%I:%M %p").lstrip("0")


def wrap_text(text: str, width: int) -> str:
    """Wrap long text blocks to make fallback text easier to read."""
    return textwrap.fill(text, width=width, break_long_words=False)


def truncate(text: str, max_length: int) -> str:
    """Trim text to a maximum length using an ellipsis when needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def get_temperature_precision(unit_pref: TemperatureUnit) -> int:
    """Return the decimal precision to use for temperature display."""
    return 0 if unit_pref == TemperatureUnit.BOTH else 1


def format_hourly_wind(period: HourlyForecastPeriod) -> str | None:
    """Return wind description for hourly periods when both pieces are present."""
    if not period.wind_direction or not period.wind_speed:
        return None
    return f"{period.wind_direction} at {period.wind_speed}"
