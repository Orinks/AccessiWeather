"""Trend helpers for current conditions presentation."""

from __future__ import annotations

from collections.abc import Iterable

from ...models import CurrentConditions, HourlyForecast, HourlyForecastPeriod, TrendInsight
from ...utils import TemperatureUnit


def _adapt_temperature_trend_summary(trend: TrendInsight, unit_pref: TemperatureUnit) -> str:
    """Return a temperature-trend summary adapted to the user's unit preference."""
    if trend.change is None or trend.unit not in {"°F", "°C"}:
        return trend.summary or describe_trend(trend)

    src_unit = trend.unit
    direction = trend.direction or "steady"
    hours = trend.timeframe_hours or 24

    if src_unit == "°F":
        change_f = trend.change
        change_c = change_f * 5.0 / 9.0
        if unit_pref == TemperatureUnit.CELSIUS:
            return f"Temperature {direction} {change_c:+.1f}°C over {hours}h"
        if unit_pref == TemperatureUnit.BOTH:
            return f"Temperature {direction} {change_f:+.1f}°F ({change_c:+.1f}°C) over {hours}h"
        return trend.summary or describe_trend(trend)

    change_c = trend.change
    change_f = change_c * 9.0 / 5.0
    if unit_pref == TemperatureUnit.FAHRENHEIT:
        return f"Temperature {direction} {change_f:+.1f}°F over {hours}h"
    if unit_pref == TemperatureUnit.BOTH:
        return f"Temperature {direction} {change_f:+.1f}°F ({change_c:+.1f}°C) over {hours}h"
    return trend.summary or describe_trend(trend)


def format_trend_lines(
    trends: Iterable[TrendInsight] | None,
    *,
    current: CurrentConditions | None = None,
    hourly_forecast: HourlyForecast | None = None,
    include_pressure: bool = True,
    unit_pref: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
) -> list[str]:
    """Generate human readable summaries for trend insights."""
    lines: list[str] = []
    pressure_present = False

    if trends:
        for trend in trends:
            metric_name = getattr(trend, "metric", "")
            if isinstance(metric_name, str) and metric_name.lower() == "daily_trend":
                continue
            is_pressure = isinstance(metric_name, str) and metric_name.lower() == "pressure"
            if is_pressure and not include_pressure:
                continue

            is_temperature = isinstance(metric_name, str) and metric_name.lower() == "temperature"
            if is_temperature:
                summary = _adapt_temperature_trend_summary(trend, unit_pref)
            else:
                summary = trend.summary or describe_trend(trend)

            if trend.sparkline:
                summary = f"{summary} {trend.sparkline}".strip()
            if summary:
                lines.append(summary)
            if is_pressure:
                pressure_present = True

    if include_pressure and (not pressure_present) and current and hourly_forecast:
        legacy_pressure = compute_pressure_trend_from_hourly(current, hourly_forecast)
        if legacy_pressure:
            summary = legacy_pressure["summary"]
            if summary and summary not in lines:
                lines.append(summary)

    return lines


def describe_trend(trend: TrendInsight) -> str:
    """Describe a trend insight when it lacks a canned summary."""
    direction = (trend.direction or "steady").capitalize()
    timeframe = trend.timeframe_hours or 24
    change_text = ""
    if trend.change is not None:
        if trend.unit in {"°F", "°C"}:
            change_text = f"{trend.change:+.1f}{trend.unit}"
        elif trend.unit:
            change_text = f"{trend.change:+.2f}{trend.unit}"
        else:
            change_text = f"{trend.change:+.1f}"
    pieces = [direction]
    if change_text:
        pieces.append(change_text)
    pieces.append(f"over {timeframe}h")
    return " ".join(pieces)


def compute_pressure_trend_from_hourly(
    current: CurrentConditions,
    hourly_forecast: HourlyForecast | None,
) -> dict[str, str] | None:
    """Approximate a pressure trend using upcoming hourly data."""
    if not hourly_forecast or not hourly_forecast.has_data():
        return None

    next_hours = hourly_forecast.get_next_hours(6)
    if not next_hours:
        return None

    target: HourlyForecastPeriod | None = None
    for period in reversed(next_hours):
        if not period:
            continue
        if period.pressure_in is not None or period.pressure_mb is not None:
            target = period
            break

    if target is None:
        return None

    base_in = current.pressure_in
    base_mb = current.pressure_mb
    future_in = target.pressure_in
    future_mb = target.pressure_mb

    descriptor: str | None = None
    magnitude: str | None = None
    change: float | None = None

    if base_in is not None and future_in is not None:
        change = future_in - base_in
        descriptor = direction_descriptor(change, minor=0.02, strong=0.05)
        magnitude = f"{change:+.2f} inHg"
    elif base_mb is not None and future_mb is not None:
        change = future_mb - base_mb
        descriptor = direction_descriptor(change, minor=0.5, strong=1.5)
        magnitude = f"{change:+.1f} mb"

    if descriptor is None or magnitude is None or change is None:
        return None

    direction_word, arrow = split_direction_descriptor(descriptor)
    window_hours = 6
    arrow_part = f" {arrow}" if arrow else ""
    value = f"{direction_word.title()}{arrow_part} {magnitude} over next {window_hours}h".strip()
    summary = f"Pressure {descriptor} {magnitude} over next {window_hours}h".strip()

    return {"summary": summary, "value": value}


def direction_descriptor(change: float, *, minor: float, strong: float) -> str:
    """Classify change magnitude into rising/falling/steady buckets with arrows."""
    if change >= strong:
        return "rising ⬆⬆"
    if change >= minor:
        return "rising ⬆"
    if change <= -strong:
        return "falling ⬇⬇"
    if change <= -minor:
        return "falling ⬇"
    return "steady →"


def split_direction_descriptor(descriptor: str) -> tuple[str, str]:
    """Return the textual direction and accompanying arrow glyphs."""
    if not descriptor:
        return "steady", ""
    if " " in descriptor:
        direction, arrow = descriptor.split(" ", 1)
        return direction, arrow.strip()
    return descriptor, ""
