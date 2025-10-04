"""Builders for forecast-related presentation objects."""

from __future__ import annotations

from collections.abc import Iterable

from ...models import Forecast, HourlyForecast, Location
from ...utils import TemperatureUnit
from ..weather_presenter import (
    ForecastPeriodPresentation,
    ForecastPresentation,
    HourlyPeriodPresentation,
)
from .formatters import (
    format_forecast_temperature,
    format_hour_time,
    format_hourly_wind,
    format_period_temperature,
    format_period_wind,
    format_timestamp,
    get_temperature_precision,
    wrap_text,
)


def build_forecast(
    forecast: Forecast,
    hourly_forecast: HourlyForecast | None,
    location: Location,
    unit_pref: TemperatureUnit,
) -> ForecastPresentation:
    """Create a structured forecast including optional hourly highlights."""
    title = f"Forecast for {location.name}"
    precision = get_temperature_precision(unit_pref)

    periods: list[ForecastPeriodPresentation] = []
    fallback_lines = [f"Forecast for {location.name}:\n"]

    if hourly_forecast and hourly_forecast.has_data():
        hourly = build_hourly_summary(hourly_forecast, unit_pref)
    else:
        hourly = []

    for period in forecast.periods[:14]:
        temp_pair = format_forecast_temperature(period, unit_pref, precision)
        wind_value = format_period_wind(period)
        details = (
            period.detailed_forecast
            if period.detailed_forecast and period.detailed_forecast != period.short_forecast
            else None
        )
        periods.append(
            ForecastPeriodPresentation(
                name=period.name or "Unknown",
                temperature=temp_pair,
                conditions=period.short_forecast,
                wind=wind_value,
                details=details,
            )
        )

        fallback_lines.append(f"{period.name or 'Unknown'}: {temp_pair or 'N/A'}")
        if period.short_forecast:
            fallback_lines.append(f"  Conditions: {period.short_forecast}")
        if wind_value:
            fallback_lines.append(f"  Wind: {wind_value}")
        if details:
            fallback_lines.append(f"  Details: {wrap_text(details, 80)}")

    generated_at = format_timestamp(forecast.generated_at) if forecast.generated_at else None
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
) -> list[HourlyPeriodPresentation]:
    """Generate the next six hours of simplified forecast data."""
    precision = get_temperature_precision(unit_pref)
    summary: list[HourlyPeriodPresentation] = []
    for period in hourly_forecast.get_next_hours(6):
        if not period.has_data():
            continue
        temperature = format_period_temperature(period, unit_pref, precision)
        wind = format_hourly_wind(period)
        summary.append(
            HourlyPeriodPresentation(
                time=format_hour_time(period.start_time),
                temperature=temperature,
                conditions=period.short_forecast,
                wind=wind,
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
        lines.append("  " + " - ".join(parts))
    return "\n".join(lines)
