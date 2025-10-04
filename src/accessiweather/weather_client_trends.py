"""Trend insight computation for weather data analysis in AccessiWeather."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta

from .models import HourlyForecastPeriod, TrendInsight, WeatherData

logger = logging.getLogger(__name__)


def apply_trend_insights(
    weather_data: WeatherData,
    trend_insights_enabled: bool,
    trend_hours: int,
) -> None:
    """Populate trend insights on the provided WeatherData instance."""
    if not trend_insights_enabled:
        logger.debug("Trend insights disabled; clearing insights")
        weather_data.trend_insights = []
        return

    insights: list[TrendInsight] = []

    temp_insight = compute_temperature_trend(weather_data, trend_hours)
    if temp_insight:
        insights.append(temp_insight)

    pressure_insight = compute_pressure_trend(weather_data, trend_hours)
    if pressure_insight:
        insights.append(pressure_insight)

    weather_data.trend_insights = insights


def compute_temperature_trend(
    weather_data: WeatherData,
    trend_hours: int,
) -> TrendInsight | None:
    """Compute the projected temperature trend over the configured number of hours."""
    current = weather_data.current
    hourly = weather_data.hourly_forecast.periods if weather_data.hourly_forecast else []
    if current is None or not hourly:
        logger.debug("Insufficient data for temperature trend calculation")
        return None

    base = current.temperature_f
    unit = "°F"
    if base is None:
        base = current.temperature_c
        unit = "°C"
    if base is None:
        logger.debug("Missing base temperature for trend calculation")
        return None

    target_period = period_for_hours_ahead(hourly, trend_hours)
    if not target_period or target_period.temperature is None:
        logger.debug("Target period missing temperature for trend calculation")
        return None

    change = target_period.temperature - base
    direction, sparkline = trend_descriptor(
        change,
        minor=1.0 if unit == "°F" else 0.5,
        strong=3.0 if unit == "°F" else 1.5,
    )
    summary = f"Temperature {direction} {change:+.1f}{unit} over {trend_hours}h"
    return TrendInsight(
        metric="temperature",
        direction=direction,
        change=round(change, 1),
        unit=unit,
        timeframe_hours=trend_hours,
        summary=summary,
        sparkline=sparkline,
    )


def compute_pressure_trend(
    weather_data: WeatherData,
    trend_hours: int,
) -> TrendInsight | None:
    """Compute the projected pressure trend over the configured number of hours."""
    current = weather_data.current
    hourly = weather_data.hourly_forecast.periods if weather_data.hourly_forecast else []
    if current is None or not hourly:
        logger.debug("Insufficient data for pressure trend calculation")
        return None

    base_mb = current.pressure_mb
    base_in = current.pressure_in
    target_period = period_for_hours_ahead(hourly, trend_hours)
    if not target_period:
        logger.debug("No target period available for pressure trend calculation")
        return None

    future_mb = target_period.pressure_mb
    future_in = target_period.pressure_in

    value_pairs: list[tuple[float, float, str]] = []
    if base_mb is not None and future_mb is not None:
        value_pairs.append((base_mb, future_mb, "mb"))
    if base_in is not None and future_in is not None:
        value_pairs.append((base_in, future_in, "inHg"))
    if not value_pairs:
        logger.debug("No comparable pressure values available for trend")
        return None

    base, future, unit = value_pairs[0]
    change = future - base
    direction, sparkline = trend_descriptor(
        change,
        minor=0.5 if unit == "mb" else 0.02,
        strong=1.5 if unit == "mb" else 0.05,
    )
    summary = f"Pressure {direction} {change:+.2f}{unit} over {trend_hours}h"
    return TrendInsight(
        metric="pressure",
        direction=direction,
        change=round(change, 2),
        unit=unit,
        timeframe_hours=trend_hours,
        summary=summary,
        sparkline=sparkline,
    )


def trend_descriptor(change: float, *, minor: float, strong: float) -> tuple[str, str]:
    """Return the directional descriptor and sparkline for the given change magnitude."""
    if change >= strong:
        return "rising", "↑↑"
    if change >= minor:
        return "rising", "↑"
    if change <= -strong:
        return "falling", "↓↓"
    if change <= -minor:
        return "falling", "↓"
    return "steady", "→"


def period_for_hours_ahead(
    periods: Sequence[HourlyForecastPeriod],
    hours_ahead: int,
) -> HourlyForecastPeriod | None:
    """Return the forecast period closest to the target number of hours ahead."""
    if not periods:
        return None

    target = normalize_datetime(datetime.now()) + timedelta(hours=hours_ahead)
    closest = None
    best_delta = None
    for period in periods:
        start = normalize_datetime(period.start_time)
        if start is None:
            continue
        delta = abs((start - target).total_seconds())
        if best_delta is None or delta < best_delta:
            closest = period
            best_delta = delta
    return closest


def normalize_datetime(value: datetime | None) -> datetime | None:
    """Normalize datetimes by removing timezone information when present."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone().replace(tzinfo=None)
