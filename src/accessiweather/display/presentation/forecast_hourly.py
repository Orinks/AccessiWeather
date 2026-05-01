"""Hourly forecast presentation builders."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import tzinfo

from ...models import AppSettings, HourlyForecast
from ...utils import TemperatureUnit, calculate_dewpoint, format_temperature
from ...utils.unit_utils import format_precipitation, format_wind_speed
from .forecast_time import _resolve_forecast_display_time
from .formatters import (
    format_display_time,
    format_hourly_wind,
    format_period_temperature,
    get_temperature_precision,
    get_uv_description,
)
from .models import HourlyPeriodPresentation


def build_hourly_summary(
    hourly_forecast: HourlyForecast,
    unit_pref: TemperatureUnit,
    settings: AppSettings | None = None,
    *,
    location_timezone: tzinfo | None = None,
) -> list[HourlyPeriodPresentation]:
    """Generate the next six hours of simplified forecast data."""
    round_values = getattr(settings, "round_values", False) if settings else False
    precision = 0 if round_values else get_temperature_precision(unit_pref)
    summary: list[HourlyPeriodPresentation] = []

    # Extract time display preferences and verbosity from settings
    if settings:
        time_display_mode = getattr(settings, "time_display_mode", "local")
        time_format_12hour = getattr(settings, "time_format_12hour", True)
        show_timezone_suffix = getattr(settings, "show_timezone_suffix", False)
        forecast_time_reference = getattr(settings, "forecast_time_reference", "location")
        verbosity_level = getattr(settings, "verbosity_level", "standard")
    else:
        time_display_mode = "local"
        time_format_12hour = True
        show_timezone_suffix = False
        forecast_time_reference = "location"
        verbosity_level = "standard"

    # Determine which fields to include based on verbosity level
    # minimal: temperature, conditions only
    # standard: temperature, conditions, wind, precipitation
    # detailed: all available fields
    include_wind = verbosity_level in ("standard", "detailed")
    include_precipitation = verbosity_level in ("standard", "detailed")
    include_humidity = verbosity_level in ("standard", "detailed")
    include_dewpoint = verbosity_level in ("standard", "detailed")
    include_uv = verbosity_level == "detailed"
    include_snowfall = verbosity_level == "detailed"
    include_cloud_cover = verbosity_level == "detailed"
    include_wind_gust = verbosity_level == "detailed"

    hourly_hours = getattr(settings, "hourly_forecast_hours", 6) if settings else 6
    hourly_hours = max(1, min(hourly_hours, 168))
    for period in hourly_forecast.get_next_hours(hourly_hours):
        if not period.has_data():
            continue
        temperature = format_period_temperature(period, unit_pref, precision)
        wind = format_hourly_wind(period, unit_pref) if include_wind else None

        # Use enhanced time formatter with user preferences
        display_time = _resolve_forecast_display_time(
            period.start_time,
            forecast_time_reference=forecast_time_reference,
            location_timezone=location_timezone,
        )
        time_str = format_display_time(
            display_time,
            time_display_mode=time_display_mode,
            use_12hour=time_format_12hour,
            show_timezone=show_timezone_suffix,
        )

        # Format extended fields based on verbosity
        precip_prob = (
            f"{int(period.precipitation_probability)}%"
            if include_precipitation and period.precipitation_probability is not None
            else None
        )
        humidity_val = (
            f"{period.humidity:.0f}%" if include_humidity and period.humidity is not None else None
        )
        dewpoint_val = (
            _format_hourly_dewpoint(period, unit_pref, precision) if include_dewpoint else None
        )
        snowfall_val = (
            f"{period.snowfall:.{precision}f} in"
            if include_snowfall and period.snowfall is not None and period.snowfall > 0
            else None
        )
        uv_val = (
            f"{period.uv_index:.0f} ({get_uv_description(period.uv_index)})"
            if include_uv and period.uv_index is not None
            else None
        )
        cloud_val = (
            f"{period.cloud_cover:.0f}%"
            if include_cloud_cover and period.cloud_cover is not None
            else None
        )
        gust_val = (
            format_wind_speed(period.wind_gust_mph, unit_pref, precision=0)
            if include_wind_gust and period.wind_gust_mph is not None
            else None
        )
        precip_amt = (
            format_precipitation(
                period.precipitation_amount,
                unit_pref,
                precipitation_mm=period.precipitation_amount * 25.4,
                precision=precision,
            )
            if include_precipitation
            and period.precipitation_amount is not None
            and period.precipitation_amount > 0
            else None
        )

        summary.append(
            HourlyPeriodPresentation(
                time=time_str,
                temperature=temperature,
                conditions=period.short_forecast,
                wind=wind,
                humidity=humidity_val,
                dewpoint=dewpoint_val,
                precipitation_probability=precip_prob,
                snowfall=snowfall_val,
                uv_index=uv_val,
                cloud_cover=cloud_val,
                wind_gust=gust_val,
                precipitation_amount=precip_amt,
            )
        )
    return summary


def render_hourly_fallback(hourly: Iterable[HourlyPeriodPresentation], hours: int = 6) -> str:
    """Render hourly periods into fallback text."""
    lines = [f"Next {hours} Hours:"]
    for period in hourly:
        parts = [period.time]
        if period.temperature:
            parts.append(period.temperature)
        if period.conditions:
            parts.append(period.conditions)
        # Bug 5: compact wind – combine speed and gust on one line
        if period.wind and period.wind_gust:
            parts.append(f"Wind {period.wind}, gusting to {period.wind_gust}")
        elif period.wind:
            parts.append(f"Wind {period.wind}")
        elif period.wind_gust:
            parts.append(f"Gusts {period.wind_gust}")
        if period.humidity:
            parts.append(f"Humidity {period.humidity}")
        if period.dewpoint:
            parts.append(f"Dewpoint {period.dewpoint}")
        # Bug 6: compact precip – combine amount and chance on one line
        precip_parts: list[str] = []
        if period.precipitation_amount:
            precip_parts.append(period.precipitation_amount)
        if period.precipitation_probability:
            precip_parts.append(f"{period.precipitation_probability} chance")
        if precip_parts:
            parts.append(f"Precip {', '.join(precip_parts)}")
        if period.snowfall:
            parts.append(f"Snow {period.snowfall}")
        if period.cloud_cover:
            parts.append(f"Clouds {period.cloud_cover}")
        if period.uv_index:
            parts.append(f"UV {period.uv_index}")
        lines.append("  " + " - ".join(parts))
    return "\n".join(lines)


def build_hourly_section_text(
    hourly: Iterable[HourlyPeriodPresentation],
    *,
    hours: int,
    summary_line: str | None = None,
) -> str:
    """Render hourly forecast as a separate accessibility section."""
    hourly_periods = list(hourly)
    if not hourly_periods and not summary_line:
        return ""

    lines = ["Hourly forecast:"]
    if summary_line:
        lines.append(summary_line)

    rendered = render_hourly_fallback(hourly_periods, hours=hours)
    if rendered:
        lines.append(rendered)

    return "\n".join(lines).rstrip()


def _format_hourly_dewpoint(
    period,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    dewpoint_f = period.dewpoint_f
    dewpoint_c = period.dewpoint_c

    if dewpoint_f is None and dewpoint_c is None:
        if period.temperature is None or period.humidity is None:
            return None
        unit = (period.temperature_unit or "F").upper()
        temp_f = period.temperature if unit == "F" else (period.temperature * 9 / 5) + 32
        dewpoint_f = calculate_dewpoint(
            temp_f,
            period.humidity,
            unit=TemperatureUnit.FAHRENHEIT,
        )
        dewpoint_c = (dewpoint_f - 32) * 5 / 9 if dewpoint_f is not None else None

    return format_temperature(
        dewpoint_f,
        unit_pref,
        temperature_c=dewpoint_c,
        precision=precision,
    )
