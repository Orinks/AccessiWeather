"""Builders for current conditions presentation objects."""

from __future__ import annotations

from collections.abc import Iterable

from ...models import (
    CurrentConditions,
    EnvironmentalConditions,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
)
from ...utils import TemperatureUnit
from ..weather_presenter import CurrentConditionsPresentation, Metric
from .formatters import (
    format_dewpoint,
    format_pressure_value,
    format_temperature_pair,
    format_timestamp,
    format_visibility_value,
    format_wind,
    get_temperature_precision,
    get_uv_description,
)


def build_current_conditions(
    current: CurrentConditions,
    location: Location,
    unit_pref: TemperatureUnit,
    *,
    environmental: EnvironmentalConditions | None = None,
    trends: Iterable[TrendInsight] | None = None,
    hourly_forecast: HourlyForecast | None = None,
) -> CurrentConditionsPresentation:
    """Create a structured presentation for the current weather."""
    title = f"Current conditions for {location.name}"
    description = current.condition or "Unknown"
    precision = get_temperature_precision(unit_pref)

    temperature_str = format_temperature_pair(
        current.temperature_f, current.temperature_c, unit_pref, precision
    )
    temperature_value = temperature_str if temperature_str is not None else "N/A"
    metrics: list[Metric] = [Metric("Temperature", temperature_value)]

    if current.feels_like_f is not None or current.feels_like_c is not None:
        feels_like = format_temperature_pair(
            current.feels_like_f, current.feels_like_c, unit_pref, precision
        )
        if feels_like:
            metrics.append(Metric("Feels like", feels_like))

    if current.humidity is not None:
        metrics.append(Metric("Humidity", f"{current.humidity:.0f}%"))

    wind_value = format_wind(current, unit_pref)
    if wind_value:
        metrics.append(Metric("Wind", wind_value))

    dewpoint_value = format_dewpoint(current, unit_pref, precision)
    if dewpoint_value:
        metrics.append(Metric("Dewpoint", dewpoint_value))

    pressure_value = format_pressure_value(current, unit_pref)
    if pressure_value:
        metrics.append(Metric("Pressure", pressure_value))

    visibility_value = format_visibility_value(current, unit_pref)
    if visibility_value:
        metrics.append(Metric("Visibility", visibility_value))

    if current.uv_index is not None:
        uv_desc = get_uv_description(current.uv_index)
        metrics.append(Metric("UV Index", f"{current.uv_index} ({uv_desc})"))

    if current.last_updated:
        metrics.append(Metric("Last updated", format_timestamp(current.last_updated)))

    if environmental:
        if environmental.air_quality_index is not None:
            aq_label = (
                f"{environmental.air_quality_index:.0f}"
                if environmental.air_quality_index is not None
                else ""
            )
            if environmental.air_quality_category:
                aq_label = (
                    f"{aq_label} ({environmental.air_quality_category})"
                    if aq_label
                    else environmental.air_quality_category
                )
            if environmental.air_quality_pollutant:
                pollutant = environmental.air_quality_pollutant
                aq_label = f"{aq_label} – {pollutant}" if aq_label else pollutant
            metrics.append(Metric("Air Quality", aq_label or "Data unavailable"))
        if environmental.pollen_index is not None or environmental.pollen_primary_allergen:
            pollen_value = (
                f"{environmental.pollen_index:.0f}"
                if environmental.pollen_index is not None
                else ""
            )
            if environmental.pollen_category:
                pollen_value = (
                    f"{pollen_value} ({environmental.pollen_category})"
                    if pollen_value
                    else environmental.pollen_category
                )
            if environmental.pollen_primary_allergen:
                pollen_value = (
                    f"{pollen_value} – {environmental.pollen_primary_allergen}"
                    if pollen_value
                    else environmental.pollen_primary_allergen
                )
            metrics.append(Metric("Pollen", pollen_value or "Data unavailable"))

    pressure_trend_present = False
    if trends:
        for trend in trends:
            summary = trend.summary or describe_trend(trend)
            if trend.sparkline:
                summary = f"{summary} {trend.sparkline}".strip()
            metrics.append(Metric(f"{trend.metric.title()} trend", summary))
            metric_name = getattr(trend, "metric", "")
            if isinstance(metric_name, str) and metric_name.lower() == "pressure":
                pressure_trend_present = True

    if not pressure_trend_present:
        legacy_pressure_trend = compute_pressure_trend_from_hourly(current, hourly_forecast)
        if legacy_pressure_trend:
            metrics.append(Metric("Pressure trend", legacy_pressure_trend["value"]))

    fallback_lines = [f"Current Conditions: {description}"]
    fallback_lines.append(f"Temperature: {temperature_value}")
    for metric in metrics[1:]:  # already added temperature
        fallback_lines.append(f"{metric.label}: {metric.value}")
    fallback_text = "\n".join(fallback_lines)

    trend_lines = format_trend_lines(
        trends,
        current=current,
        hourly_forecast=hourly_forecast,
    )

    return CurrentConditionsPresentation(
        title=title,
        description=description,
        metrics=metrics,
        fallback_text=fallback_text,
        trends=trend_lines,
    )


def format_trend_lines(
    trends: Iterable[TrendInsight] | None,
    *,
    current: CurrentConditions | None = None,
    hourly_forecast: HourlyForecast | None = None,
) -> list[str]:
    """Generate human readable summaries for trend insights."""
    lines: list[str] = []
    pressure_present = False

    if trends:
        for trend in trends:
            summary = trend.summary or describe_trend(trend)
            if trend.sparkline:
                summary = f"{summary} {trend.sparkline}".strip()
            if summary:
                lines.append(summary)
            metric_name = getattr(trend, "metric", "")
            if isinstance(metric_name, str) and metric_name.lower() == "pressure":
                pressure_present = True

    if (not pressure_present) and current and hourly_forecast:
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
