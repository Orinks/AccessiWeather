"""Forecast source-selection helpers for weather data fusion."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from accessiweather.models.weather import Forecast, HourlyForecast, Location, SourceData

logger = logging.getLogger(__name__)


def merge_forecasts(
    engine: Any, sources: list[SourceData], location: Location, requested_days: int = 7
) -> tuple[Forecast | None, dict[str, str]]:
    """
    Select forecast from a single source based on location.

    Unlike merging multiple sources, forecasts are selected from a single preferred
    source to avoid duplicate periods with different naming conventions:
    - US locations: Prefer NWS (most accurate for US)
    - International: Use Open-Meteo
    - Pirate Weather: Used as a fallback when primary forecasts are unavailable

    Args:
        engine: Fusion engine used for location and priority helpers.
        sources: List of source data containers
        location: The location for source selection
        requested_days: User-configured forecast day target

    Returns:
        Tuple of Forecast from single source and source attribution

    """
    is_us = engine._is_us_location(location)
    field_sources: dict[str, str] = {}

    # Filter to successful sources with forecasts
    valid_sources = [s for s in sources if s.success and s.forecast is not None]

    if not valid_sources:
        return None, field_sources

    # Select single source based on location (no merging to avoid duplicates)
    # US: prefer NWS for 7-day, Open-Meteo for extended ranges; PW as fallback
    # International: prefer Open-Meteo > Pirate Weather
    if is_us:
        preferred_order = (
            ["openmeteo", "nws", "pirateweather"]
            if requested_days > 7
            else ["nws", "openmeteo", "pirateweather"]
        )
    else:
        preferred_order = ["openmeteo", "pirateweather"]

    # Find the first available source in preferred order
    selected_source = None
    for source_name in preferred_order:
        for source in valid_sources:
            if source.source == source_name:
                selected_source = source
                break
        if selected_source:
            break

    # Fallback to first available if none matched preferred order
    if not selected_source:
        selected_source = valid_sources[0]

    # Use the selected source's forecast directly, while preserving Pirate Weather's
    # block summary when another source wins the main forecast selection.
    forecast = selected_source.forecast
    source_name = selected_source.source
    pirate_weather_source = next((s for s in valid_sources if s.source == "pirateweather"), None)
    pirate_summary = (
        pirate_weather_source.forecast.summary
        if pirate_weather_source and pirate_weather_source.forecast
        else None
    )
    if forecast and forecast.summary is None and pirate_summary:
        forecast = replace(forecast, summary=pirate_summary)

    # Track attribution
    field_sources["forecast_source"] = source_name
    if pirate_summary and forecast and forecast.summary == pirate_summary:
        field_sources["forecast_summary"] = "pirateweather"
    logger.debug(f"Using {source_name} for forecast (location: {location.name})")

    return forecast, field_sources


def merge_hourly_forecasts(
    engine: Any, sources: list[SourceData], location: Location
) -> tuple[HourlyForecast | None, dict[str, str]]:
    """
    Select hourly forecast from a single source based on location.

    Unlike other data types, hourly forecasts are NOT merged from multiple sources
    because different sources use different timezone representations that cause
    display issues when combined. Instead, we select the best single source:
    - US locations: Prefer NWS (most accurate for US)
    - International: Use Open-Meteo

    Args:
        engine: Fusion engine used for location and priority helpers.
        sources: List of source data containers
        location: The location for source selection

    Returns:
        Tuple of HourlyForecast from single source and source attribution

    """
    is_us = engine._is_us_location(location)
    field_sources: dict[str, str] = {}

    # Filter to successful sources with hourly forecasts
    valid_sources = [s for s in sources if s.success and s.hourly_forecast is not None]

    if not valid_sources:
        return None, field_sources

    # Select single source based on location (no merging for hourly data)
    # US: prefer NWS > Open-Meteo > Pirate Weather
    # International: prefer Open-Meteo > Pirate Weather
    if is_us:
        preferred_order = ["nws", "openmeteo", "pirateweather"]
    else:
        preferred_order = ["openmeteo", "pirateweather"]

    # Find the first available source in preferred order
    selected_source = None
    for source_name in preferred_order:
        for source in valid_sources:
            if source.source == source_name:
                selected_source = source
                break
        if selected_source:
            break

    # Fallback to first available if none matched preferred order
    if not selected_source:
        selected_source = valid_sources[0]

    # Use the selected source's hourly forecast directly, while preserving Pirate Weather's
    # block summary when another source wins the hourly selection.
    hourly_forecast = selected_source.hourly_forecast
    source_name = selected_source.source
    pirate_weather_source = next((s for s in valid_sources if s.source == "pirateweather"), None)
    pirate_summary = (
        pirate_weather_source.hourly_forecast.summary
        if pirate_weather_source and pirate_weather_source.hourly_forecast
        else None
    )
    if hourly_forecast and hourly_forecast.summary is None and pirate_summary:
        hourly_forecast = replace(hourly_forecast, summary=pirate_summary)

    pressure_source = select_hourly_pressure_source(engine, valid_sources, selected_source)
    if (
        hourly_forecast
        and pressure_source
        and pressure_source.hourly_forecast
        and pressure_source.source != source_name
    ):
        overlaid_hourly = overlay_hourly_pressure(
            hourly_forecast,
            pressure_source.hourly_forecast,
        )
        if overlaid_hourly is not hourly_forecast:
            hourly_forecast = overlaid_hourly
            field_sources["hourly_pressure_source"] = pressure_source.source

    # Track attribution
    field_sources["hourly_source"] = source_name
    if pirate_summary and hourly_forecast and hourly_forecast.summary == pirate_summary:
        field_sources["hourly_summary"] = "pirateweather"
    logger.debug(f"Using {source_name} for hourly forecast (location: {location.name})")

    return hourly_forecast, field_sources


def select_hourly_pressure_source(
    engine: Any, valid_sources: list[SourceData], selected_source: SourceData
) -> SourceData | None:
    """Return the selected hourly source or best alternate source with pressure data."""
    if hourly_has_pressure(selected_source.hourly_forecast):
        return selected_source

    pressure_priority = ["openmeteo", "pirateweather"]
    pressure_sources = [s for s in valid_sources if hourly_has_pressure(s.hourly_forecast)]
    if not pressure_sources:
        return None

    pressure_sources.sort(
        key=lambda source: engine._source_priority_index(source.source, pressure_priority)
    )
    return pressure_sources[0]


def hourly_has_pressure(hourly: HourlyForecast | None) -> bool:
    """Return True when any hourly period includes pressure."""
    if hourly is None:
        return False
    return any(p.pressure_in is not None or p.pressure_mb is not None for p in hourly.periods)


def overlay_hourly_pressure(
    display_hourly: HourlyForecast, pressure_hourly: HourlyForecast
) -> HourlyForecast:
    """Copy pressure-only fields from a pressure-capable hourly source by nearest time."""
    pressure_periods = [
        period
        for period in pressure_hourly.periods
        if period.pressure_in is not None or period.pressure_mb is not None
    ]
    if not pressure_periods:
        return display_hourly

    overlaid_periods = []
    changed = False
    for display_period in display_hourly.periods:
        if display_period.pressure_in is not None or display_period.pressure_mb is not None:
            overlaid_periods.append(display_period)
            continue

        pressure_period = nearest_hourly_pressure_period(
            display_period.start_time,
            pressure_periods,
        )
        if pressure_period is None:
            overlaid_periods.append(display_period)
            continue

        overlaid_periods.append(
            replace(
                display_period,
                pressure_in=pressure_period.pressure_in,
                pressure_mb=pressure_period.pressure_mb,
            )
        )
        changed = True

    if not changed:
        return display_hourly
    return replace(display_hourly, periods=overlaid_periods)


def nearest_hourly_pressure_period(target: datetime, pressure_periods: list):
    """Find a pressure period close enough to the target display hour."""
    target_ts = datetime_timestamp(target)
    if target_ts is None:
        return None

    closest = None
    best_delta = None
    for period in pressure_periods:
        period_ts = datetime_timestamp(period.start_time)
        if period_ts is None:
            continue
        delta = abs(period_ts - target_ts)
        if best_delta is None or delta < best_delta:
            closest = period
            best_delta = delta

    if best_delta is None or best_delta > 90 * 60:
        return None
    return closest


def datetime_timestamp(value: datetime | None) -> float | None:
    """Normalize aware and naive datetimes to comparable timestamps."""
    if value is None:
        return None
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.timestamp()
