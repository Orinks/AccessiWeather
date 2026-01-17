"""Builders for forecast-related presentation objects."""

from __future__ import annotations

from collections.abc import Iterable

from ...models import AppSettings, Forecast, HourlyForecast, Location
from ...utils import TemperatureUnit
from ..weather_presenter import (
    ForecastPeriodPresentation,
    ForecastPresentation,
    HourlyPeriodPresentation,
)
from .formatters import (
    format_display_time,
    format_forecast_temperature,
    format_hourly_wind,
    format_period_temperature,
    format_period_wind,
    format_timestamp,
    get_temperature_precision,
    get_uv_description,
    wrap_text,
)


def build_forecast(
    forecast: Forecast,
    hourly_forecast: HourlyForecast | None,
    location: Location,
    unit_pref: TemperatureUnit,
    settings: AppSettings | None = None,
) -> ForecastPresentation:
    """Create a structured forecast including optional hourly highlights."""
    title = f"Forecast for {location.name}"
    precision = get_temperature_precision(unit_pref)

    periods: list[ForecastPeriodPresentation] = []
    fallback_lines = [f"Forecast for {location.name}:\n"]

    if hourly_forecast and hourly_forecast.has_data():
        hourly = build_hourly_summary(hourly_forecast, unit_pref, settings=settings)
    else:
        hourly = []

    # Extract time display preferences and verbosity from settings
    if settings:
        time_display_mode = getattr(settings, "time_display_mode", "local")
        time_format_12hour = getattr(settings, "time_format_12hour", True)
        show_timezone_suffix = getattr(settings, "show_timezone_suffix", False)
        verbosity_level = getattr(settings, "verbosity_level", "standard")
    else:
        time_display_mode = "local"
        time_format_12hour = True
        show_timezone_suffix = False
        verbosity_level = "standard"

    # Determine which fields to include based on verbosity level
    # minimal: temperature, conditions only
    # standard: temperature, conditions, wind, precipitation
    # detailed: all available fields
    include_wind = verbosity_level in ("standard", "detailed")
    include_precipitation = verbosity_level in ("standard", "detailed")
    include_uv = verbosity_level == "detailed"
    include_snowfall = verbosity_level == "detailed"
    include_details = verbosity_level == "detailed"

    for period in forecast.periods[:14]:
        temp_pair = format_forecast_temperature(period, unit_pref, precision)
        wind_value = format_period_wind(period) if include_wind else None
        details = (
            period.detailed_forecast
            if include_details
            and period.detailed_forecast
            and period.detailed_forecast != period.short_forecast
            else None
        )

        # Format extended fields based on verbosity
        precip_prob = (
            f"{int(period.precipitation_probability)}%"
            if include_precipitation and period.precipitation_probability is not None
            else None
        )
        snowfall_val = (
            f"{period.snowfall:.1f} in"
            if include_snowfall and period.snowfall is not None and period.snowfall > 0
            else None
        )
        uv_val = (
            f"{period.uv_index:.0f} ({get_uv_description(period.uv_index)})"
            if include_uv and period.uv_index is not None
            else None
        )

        periods.append(
            ForecastPeriodPresentation(
                name=period.name or "Unknown",
                temperature=temp_pair,
                conditions=period.short_forecast,
                wind=wind_value,
                details=details,
                precipitation_probability=precip_prob,
                snowfall=snowfall_val,
                uv_index=uv_val,
            )
        )

        fallback_lines.append(f"{period.name or 'Unknown'}: {temp_pair or 'N/A'}")
        if period.short_forecast:
            fallback_lines.append(f"  Conditions: {period.short_forecast}")
        if wind_value:
            fallback_lines.append(f"  Wind: {wind_value}")
        if precip_prob:
            fallback_lines.append(f"  Precipitation: {precip_prob}")
        if snowfall_val:
            fallback_lines.append(f"  Snowfall: {snowfall_val}")
        if uv_val:
            fallback_lines.append(f"  UV Index: {uv_val}")
        if details:
            fallback_lines.append(f"  Details: {wrap_text(details, 80)}")

    generated_at = (
        format_timestamp(
            forecast.generated_at,
            time_display_mode=time_display_mode,
            use_12hour=time_format_12hour,
            show_timezone=show_timezone_suffix,
        )
        if forecast.generated_at
        else None
    )
    if generated_at:
        fallback_lines.append(f"\nForecast generated: {generated_at}")

    if hourly:
        fallback_lines.insert(1, render_hourly_fallback(hourly))

    fallback_text = "\n".join(fallback_lines).rstrip()

    return ForecastPresentation(
        title=title,
        periods=periods,
        hourly_periods=hourly,
        generated_at=generated_at,
        fallback_text=fallback_text,
    )


def build_hourly_summary(
    hourly_forecast: HourlyForecast,
    unit_pref: TemperatureUnit,
    settings: AppSettings | None = None,
) -> list[HourlyPeriodPresentation]:
    """Generate the next six hours of simplified forecast data."""
    precision = get_temperature_precision(unit_pref)
    summary: list[HourlyPeriodPresentation] = []

    # Extract time display preferences and verbosity from settings
    if settings:
        time_display_mode = getattr(settings, "time_display_mode", "local")
        time_format_12hour = getattr(settings, "time_format_12hour", True)
        show_timezone_suffix = getattr(settings, "show_timezone_suffix", False)
        verbosity_level = getattr(settings, "verbosity_level", "standard")
    else:
        time_display_mode = "local"
        time_format_12hour = True
        show_timezone_suffix = False
        verbosity_level = "standard"

    # Determine which fields to include based on verbosity level
    # minimal: temperature, conditions only
    # standard: temperature, conditions, wind, precipitation
    # detailed: all available fields
    include_wind = verbosity_level in ("standard", "detailed")
    include_precipitation = verbosity_level in ("standard", "detailed")
    include_uv = verbosity_level == "detailed"
    include_snowfall = verbosity_level == "detailed"

    for period in hourly_forecast.get_next_hours(6):
        if not period.has_data():
            continue
        temperature = format_period_temperature(period, unit_pref, precision)
        wind = format_hourly_wind(period) if include_wind else None

        # Use enhanced time formatter with user preferences
        time_str = format_display_time(
            period.start_time,
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
        snowfall_val = (
            f"{period.snowfall:.1f} in"
            if include_snowfall and period.snowfall is not None and period.snowfall > 0
            else None
        )
        uv_val = (
            f"{period.uv_index:.0f} ({get_uv_description(period.uv_index)})"
            if include_uv and period.uv_index is not None
            else None
        )

        summary.append(
            HourlyPeriodPresentation(
                time=time_str,
                temperature=temperature,
                conditions=period.short_forecast,
                wind=wind,
                precipitation_probability=precip_prob,
                snowfall=snowfall_val,
                uv_index=uv_val,
            )
        )
    return summary


def render_hourly_fallback(hourly: Iterable[HourlyPeriodPresentation]) -> str:
    """Render hourly periods into fallback text."""
    lines = ["Next 6 Hours:"]
    for period in hourly:
        parts = [period.time]
        if period.temperature:
            parts.append(period.temperature)
        if period.conditions:
            parts.append(period.conditions)
        if period.wind:
            parts.append(f"Wind {period.wind}")
        if period.precipitation_probability:
            parts.append(f"Precip {period.precipitation_probability}")
        if period.snowfall:
            parts.append(f"Snow {period.snowfall}")
        if period.uv_index:
            parts.append(f"UV {period.uv_index}")
        lines.append("  " + " - ".join(parts))
    return "\n".join(lines)
