"""Current-condition value helpers for weather data fusion."""

from __future__ import annotations

import logging
from typing import Any

from accessiweather.models.weather import (
    CurrentConditions,
    DataConflict,
    SourceAttribution,
    SourceData,
)

logger = logging.getLogger(__name__)

KM_PER_MILE = 1.609344
MB_PER_INHG = 33.8639
MM_PER_INCH = 25.4
CM_PER_INCH = 2.54
METERS_PER_FOOT = 0.3048


def build_temperature_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned temperature values from a single source."""
    pair = build_value_pair(current.temperature_f, current.temperature_c, "temperature")
    temperature_f = pair["temperature_f"]
    temperature_c = pair["temperature_c"]
    temperature = current.temperature
    if temperature is None:
        temperature = temperature_f if temperature_f is not None else temperature_c
    return {
        "temperature": temperature,
        "temperature_f": temperature_f,
        "temperature_c": temperature_c,
    }


def build_dewpoint_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned dewpoint values from a single source."""
    return build_value_pair(current.dewpoint_f, current.dewpoint_c, "dewpoint")


def build_feels_like_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned feels-like values from a single source."""
    return build_value_pair(current.feels_like_f, current.feels_like_c, "feels_like")


def build_wind_chill_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned wind chill values from a single source."""
    return build_value_pair(current.wind_chill_f, current.wind_chill_c, "wind_chill")


def build_heat_index_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned heat index values from a single source."""
    return build_value_pair(current.heat_index_f, current.heat_index_c, "heat_index")


def build_speed_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned wind speed values from a single source."""
    pair = build_speed_pair(current.wind_speed_mph, current.wind_speed_kph, "wind_speed")
    speed_mph = pair["wind_speed_mph"]
    speed_kph = pair["wind_speed_kph"]
    speed = current.wind_speed
    if speed is None:
        speed = speed_mph if speed_mph is not None else speed_kph
    return {
        "wind_speed": speed,
        "wind_speed_mph": speed_mph,
        "wind_speed_kph": speed_kph,
    }


def discard_gust_if_below_wind_speed(
    merged_values: dict[str, Any], attribution: SourceAttribution
) -> None:
    """
    Drop wind gust when it is physically impossible (gust < sustained speed).

    This can happen when wind_speed and wind_gust are selected from different
    sources during cross-source fusion, leaving the two values in inconsistent
    states.  Dropping the gust is safer than displaying an impossible reading.
    """
    speed_mph: float | None = merged_values.get("wind_speed_mph")
    gust_mph: float | None = merged_values.get("wind_gust_mph")
    if speed_mph is not None and gust_mph is not None and gust_mph < speed_mph:
        logger.debug(
            "Discarding wind gust (%.1f mph) that is lower than wind speed (%.1f mph) "
            "— likely a cross-source unit mismatch",
            gust_mph,
            speed_mph,
        )
        merged_values.pop("wind_gust_mph", None)
        merged_values.pop("wind_gust_kph", None)
        attribution.field_sources.pop("wind_gust_mph", None)
        attribution.field_sources.pop("wind_gust_kph", None)


def build_wind_gust_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned wind gust values from a single source."""
    return build_speed_pair(current.wind_gust_mph, current.wind_gust_kph, "wind_gust")


def build_value_pair(
    value_a: float | None, value_b: float | None, base_name: str
) -> dict[str, float | None]:
    """Build aligned Fahrenheit/Celsius-style value pairs from a single source."""
    if value_a is None and value_b is not None:
        value_a = (value_b * 9 / 5) + 32
    if value_b is None and value_a is not None:
        value_b = (value_a - 32) * 5 / 9
    return {
        f"{base_name}_f": value_a,
        f"{base_name}_c": value_b,
    }


def build_speed_pair(
    value_mph: float | None, value_kph: float | None, base_name: str
) -> dict[str, float | None]:
    """Build aligned mph/kph value pairs from a single source."""
    if value_mph is None and value_kph is not None:
        value_mph = value_kph / KM_PER_MILE
    if value_kph is None and value_mph is not None:
        value_kph = value_mph * KM_PER_MILE

    return {
        f"{base_name}_mph": value_mph,
        f"{base_name}_kph": value_kph,
    }


def build_pressure_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned pressure values from a single source."""
    pressure_in = current.pressure_in
    pressure_mb = current.pressure_mb
    if pressure_in is None and pressure_mb is not None:
        pressure_in = pressure_mb / MB_PER_INHG
    if pressure_mb is None and pressure_in is not None:
        pressure_mb = pressure_in * MB_PER_INHG

    pressure = current.pressure
    if pressure is None:
        pressure = pressure_in if pressure_in is not None else pressure_mb

    return {
        "pressure": pressure,
        "pressure_in": pressure_in,
        "pressure_mb": pressure_mb,
    }


def build_precipitation_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned precipitation totals from a single source."""
    precipitation_in = current.precipitation_in
    precipitation_mm = current.precipitation_mm
    if precipitation_in is None and precipitation_mm is not None:
        precipitation_in = precipitation_mm / MM_PER_INCH
    if precipitation_mm is None and precipitation_in is not None:
        precipitation_mm = precipitation_in * MM_PER_INCH
    return {
        "precipitation_in": precipitation_in,
        "precipitation_mm": precipitation_mm,
    }


def build_snow_depth_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned snow depth values from a single source."""
    snow_depth_in = current.snow_depth_in
    snow_depth_cm = current.snow_depth_cm
    if snow_depth_in is None and snow_depth_cm is not None:
        snow_depth_in = snow_depth_cm / CM_PER_INCH
    if snow_depth_cm is None and snow_depth_in is not None:
        snow_depth_cm = snow_depth_in * CM_PER_INCH
    return {
        "snow_depth_in": snow_depth_in,
        "snow_depth_cm": snow_depth_cm,
    }


def build_freezing_level_values(current: CurrentConditions) -> dict[str, float | None]:
    """Build aligned freezing level values from a single source."""
    freezing_level_ft = current.freezing_level_ft
    freezing_level_m = current.freezing_level_m
    if freezing_level_ft is None and freezing_level_m is not None:
        freezing_level_ft = freezing_level_m / METERS_PER_FOOT
    if freezing_level_m is None and freezing_level_ft is not None:
        freezing_level_m = freezing_level_ft * METERS_PER_FOOT
    return {
        "freezing_level_ft": freezing_level_ft,
        "freezing_level_m": freezing_level_m,
    }


def check_temperature_conflicts(
    engine: Any,
    sources: list[SourceData],
    merged_values: dict[str, Any],
    attribution: SourceAttribution,
    is_us: bool,
) -> None:
    """
    Check for temperature conflicts and log them.

    Args:
        engine: Fusion engine used for configuration and value access.
        sources: List of valid source data
        merged_values: The merged values dict (may be modified)
        attribution: Attribution to record conflicts
        is_us: Whether location is in US

    """
    temp_fields = ["temperature", "temperature_f", "temperature_c"]
    threshold = engine.config.temperature_conflict_threshold

    for temp_field in temp_fields:
        values: dict[str, float] = {}
        for source in sources:
            if source.current:
                val = engine._get_field_value(source.current, temp_field)
                # Only include numeric values (skip mocks and other non-numeric types)
                if val is not None and isinstance(val, int | float):
                    values[source.source] = val

        if len(values) < 2:
            continue

        # Check for conflicts
        val_list = list(values.values())
        max_diff = max(val_list) - min(val_list)

        if max_diff > threshold:
            # Get highest priority source for this field
            priority = engine.config.get_priority(temp_field, is_us)
            selected_source = None
            selected_value = None

            for src_name in priority:
                if src_name in values:
                    selected_source = src_name
                    selected_value = values[src_name]
                    break

            if selected_source:
                conflict = DataConflict(
                    field_name=temp_field,
                    values=values,
                    selected_source=selected_source,
                    selected_value=selected_value,
                )
                attribution.conflicts.append(conflict)
                merged_values[temp_field] = selected_value
                attribution.field_sources[temp_field] = selected_source

                logger.debug(
                    f"Temperature conflict for {temp_field}: {values}, "
                    f"selected {selected_source}={selected_value}"
                )
