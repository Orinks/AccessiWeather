"""Data fusion engine for merging weather data from multiple sources."""

from __future__ import annotations

import logging
from dataclasses import fields
from datetime import datetime
from typing import Any

from accessiweather.config.source_priority import SourcePriorityConfig
from accessiweather.models.weather import (
    CurrentConditions,
    DataConflict,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    SourceAttribution,
    SourceData,
)

logger = logging.getLogger(__name__)


class DataFusionEngine:
    """Merges weather data from multiple sources using configurable priorities."""

    def __init__(self, config: SourcePriorityConfig | None = None):
        """
        Initialize the fusion engine.

        Args:
            config: Source priority configuration. Uses defaults if not provided.

        """
        self.config = config or SourcePriorityConfig()

    def _is_us_location(self, location: Location) -> bool:
        """Check if location is in the US."""
        if location.country_code:
            return location.country_code.upper() == "US"
        # Rough bounding box for continental US
        lat, lon = location.latitude, location.longitude
        return 24.0 <= lat <= 50.0 and -125.0 <= lon <= -66.0

    def _get_field_value(self, obj: Any, field_name: str) -> Any:
        """Get a field value from an object, returning None if not present."""
        return getattr(obj, field_name, None)

    def merge_current_conditions(
        self,
        sources: list[SourceData],
        location: Location,
    ) -> tuple[CurrentConditions | None, SourceAttribution]:
        """
        Merge current conditions from multiple sources.

        Args:
            sources: List of source data containers
            location: The location for priority determination

        Returns:
            Tuple of merged CurrentConditions and source attribution

        """
        attribution = SourceAttribution()
        is_us = self._is_us_location(location)

        # Filter to successful sources with current conditions
        valid_sources = [s for s in sources if s.success and s.current is not None]

        if not valid_sources:
            return None, attribution

        # Get priority order
        priority = self.config.get_priority("current_conditions", is_us)

        # Sort sources by priority
        def source_priority(s: SourceData) -> int:
            try:
                return priority.index(s.source)
            except ValueError:
                return len(priority)  # Unknown sources go last

        valid_sources.sort(key=source_priority)

        # Track contributing sources
        for s in valid_sources:
            attribution.contributing_sources.add(s.source)

        # Track failed sources
        for s in sources:
            if not s.success:
                attribution.failed_sources.add(s.source)

        # Get all field names from CurrentConditions
        condition_fields = [f.name for f in fields(CurrentConditions)]

        # Merge fields by priority
        merged_values: dict[str, Any] = {}
        for field_name in condition_fields:
            field_priority = self.config.get_priority(field_name, is_us)

            # Sort sources for this specific field
            field_sources = sorted(
                valid_sources,
                key=lambda s: (
                    field_priority.index(s.source)
                    if s.source in field_priority
                    else len(field_priority)
                ),
            )

            # Find first non-None value
            for source in field_sources:
                value = self._get_field_value(source.current, field_name)
                if value is not None:
                    merged_values[field_name] = value
                    attribution.field_sources[field_name] = source.source
                    break

        # Check for temperature conflicts
        self._check_temperature_conflicts(valid_sources, merged_values, attribution, is_us)

        # Create merged CurrentConditions
        merged = CurrentConditions(**merged_values)
        return merged, attribution

    def _check_temperature_conflicts(
        self,
        sources: list[SourceData],
        merged_values: dict[str, Any],
        attribution: SourceAttribution,
        is_us: bool,
    ) -> None:
        """
        Check for temperature conflicts and log them.

        Args:
            sources: List of valid source data
            merged_values: The merged values dict (may be modified)
            attribution: Attribution to record conflicts
            is_us: Whether location is in US

        """
        temp_fields = ["temperature", "temperature_f", "temperature_c"]
        threshold = self.config.temperature_conflict_threshold

        for temp_field in temp_fields:
            values: dict[str, float] = {}
            for source in sources:
                if source.current:
                    val = self._get_field_value(source.current, temp_field)
                    # Only include numeric values (skip mocks and other non-numeric types)
                    if val is not None and isinstance(val, (int, float)):
                        values[source.source] = val

            if len(values) < 2:
                continue

            # Check for conflicts
            val_list = list(values.values())
            max_diff = max(val_list) - min(val_list)

            if max_diff > threshold:
                # Get highest priority source for this field
                priority = self.config.get_priority(temp_field, is_us)
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

    def merge_forecasts(
        self,
        sources: list[SourceData],
        location: Location,
    ) -> tuple[Forecast | None, dict[str, str]]:
        """
        Merge forecast data from multiple sources.

        Combines forecast periods from all sources into a unified timeline,
        preferring higher temporal resolution for overlapping periods.

        Args:
            sources: List of source data containers
            location: The location for priority determination

        Returns:
            Tuple of merged Forecast and field-level source attribution

        """
        is_us = self._is_us_location(location)
        field_sources: dict[str, str] = {}

        # Filter to successful sources with forecasts
        valid_sources = [s for s in sources if s.success and s.forecast is not None]

        if not valid_sources:
            return None, field_sources

        # Get priority order
        priority = self.config.get_priority("forecast", is_us)

        # Sort sources by priority
        def source_priority(s: SourceData) -> int:
            try:
                return priority.index(s.source)
            except ValueError:
                return len(priority)

        valid_sources.sort(key=source_priority)

        # Collect all periods with their source
        all_periods: list[tuple[ForecastPeriod, str]] = []
        for source in valid_sources:
            if source.forecast and source.forecast.periods:
                for period in source.forecast.periods:
                    all_periods.append((period, source.source))

        if not all_periods:
            return None, field_sources

        # Deduplicate periods by time range, keeping highest priority
        merged_periods: list[ForecastPeriod] = []
        seen_times: set[tuple[str, str]] = set()

        for period, src in all_periods:
            # Create a key based on start/end time or name
            if period.start_time and period.end_time:
                key = (
                    period.start_time.isoformat(),
                    period.end_time.isoformat(),
                )
            else:
                key = (period.name, "")

            if key not in seen_times:
                seen_times.add(key)
                merged_periods.append(period)
                field_sources[f"period_{period.name}"] = src

        # Sort by start time if available, with fallback for periods without times
        # Use a tuple key: (has_time, time_or_name) to ensure consistent ordering
        # Periods with times come first (sorted by time), then periods without times (sorted by name)
        def sort_key(p: ForecastPeriod) -> tuple[int, datetime | str]:
            if p.start_time is not None:
                return (0, p.start_time)  # Periods with times first
            return (1, p.name)  # Periods without times second

        merged_periods.sort(key=sort_key)

        # Use the most recent generated_at time
        generated_at = None
        for source in valid_sources:
            if source.forecast and source.forecast.generated_at:
                src_generated_at = source.forecast.generated_at
                # Only compare if it's a datetime (skip mocks)
                if isinstance(src_generated_at, datetime) and (
                    generated_at is None or src_generated_at > generated_at
                ):
                    generated_at = src_generated_at

        return Forecast(periods=merged_periods, generated_at=generated_at), field_sources

    def merge_hourly_forecasts(
        self,
        sources: list[SourceData],
        location: Location,
    ) -> tuple[HourlyForecast | None, dict[str, str]]:
        """
        Merge hourly forecast data from multiple sources.

        Args:
            sources: List of source data containers
            location: The location for priority determination

        Returns:
            Tuple of merged HourlyForecast and field-level source attribution

        """
        is_us = self._is_us_location(location)
        field_sources: dict[str, str] = {}

        # Filter to successful sources with hourly forecasts
        valid_sources = [s for s in sources if s.success and s.hourly_forecast is not None]

        if not valid_sources:
            return None, field_sources

        # Get priority order
        priority = self.config.get_priority("hourly_forecast", is_us)

        # Sort sources by priority
        def source_priority(s: SourceData) -> int:
            try:
                return priority.index(s.source)
            except ValueError:
                return len(priority)

        valid_sources.sort(key=source_priority)

        # Collect all periods with their source, keyed by start time
        periods_by_time: dict[str, tuple[HourlyForecastPeriod, str]] = {}

        for source in valid_sources:
            if source.hourly_forecast and source.hourly_forecast.periods:
                for period in source.hourly_forecast.periods:
                    time_key = period.start_time.isoformat()
                    # Only add if not already present (first = highest priority)
                    if time_key not in periods_by_time:
                        periods_by_time[time_key] = (period, source.source)

        if not periods_by_time:
            return None, field_sources

        # Extract periods and sort by time
        merged_periods: list[HourlyForecastPeriod] = []
        for time_key, (period, src) in sorted(periods_by_time.items()):
            merged_periods.append(period)
            field_sources[f"hour_{time_key}"] = src

        # Use the most recent generated_at time
        generated_at = None
        for source in valid_sources:
            if source.hourly_forecast and source.hourly_forecast.generated_at:
                src_generated_at = source.hourly_forecast.generated_at
                # Only compare if it's a datetime (skip mocks)
                if isinstance(src_generated_at, datetime) and (
                    generated_at is None or src_generated_at > generated_at
                ):
                    generated_at = src_generated_at

        return (
            HourlyForecast(periods=merged_periods, generated_at=generated_at),
            field_sources,
        )
