"""Data fusion engine for merging weather data from multiple sources."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import fields
from datetime import datetime
from typing import Any

from accessiweather.config.source_priority import SourcePriorityConfig
from accessiweather.models.weather import (
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    SourceAttribution,
    SourceData,
)
from accessiweather.weather_client_fusion_forecasts import (
    datetime_timestamp,
    hourly_has_pressure,
    merge_forecasts as select_forecast,
    merge_hourly_forecasts as select_hourly_forecast,
    nearest_hourly_pressure_period,
    overlay_hourly_pressure,
    select_hourly_pressure_source,
)
from accessiweather.weather_client_fusion_values import (
    build_dewpoint_values,
    build_feels_like_values,
    build_freezing_level_values,
    build_heat_index_values,
    build_precipitation_values,
    build_pressure_values,
    build_snow_depth_values,
    build_speed_pair,
    build_speed_values,
    build_temperature_values,
    build_value_pair,
    build_wind_chill_values,
    build_wind_gust_values,
    check_temperature_conflicts,
    discard_gust_if_below_wind_speed,
)

logger = logging.getLogger(__name__)

KM_PER_MILE = 1.609344


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

    def _source_priority_index(
        self,
        source_name: str,
        priority: list[str],
    ) -> int:
        """Return a stable priority index for sorting sources."""
        try:
            return priority.index(source_name)
        except ValueError:
            return len(priority)

    def _source_has_any_field(
        self,
        source: SourceData,
        field_names: tuple[str, ...],
    ) -> bool:
        """Check whether a source reports any field in a semantic group."""
        if source.current is None:
            return False
        return any(
            self._get_field_value(source.current, field_name) is not None
            for field_name in field_names
        )

    def _select_semantic_group_source(
        self,
        valid_sources: list[SourceData],
        *,
        field_names: tuple[str, ...],
        priority_field: str,
        is_us: bool,
    ) -> SourceData | None:
        """Pick the highest-priority source that has any value in the semantic group."""
        field_priority = self.config.get_priority(priority_field, is_us)
        field_sources = sorted(
            valid_sources,
            key=lambda source: self._source_priority_index(source.source, field_priority),
        )
        for source in field_sources:
            if self._source_has_any_field(source, field_names):
                return source
        return None

    def _set_group_values(
        self,
        values: dict[str, Any],
        merged_values: dict[str, Any],
        attribution: SourceAttribution,
        source_name: str,
    ) -> None:
        """Apply a semantic group selection and keep attribution aligned."""
        for field_name, value in values.items():
            if value is not None:
                merged_values[field_name] = value
                attribution.field_sources[field_name] = source_name
            else:
                merged_values.pop(field_name, None)
                attribution.field_sources.pop(field_name, None)

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
        valid_sources.sort(key=lambda source: self._source_priority_index(source.source, priority))

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

        self._apply_semantic_group_selections(valid_sources, merged_values, attribution, is_us)

        # Check for temperature conflicts
        self._check_temperature_conflicts(valid_sources, merged_values, attribution, is_us)

        # For US locations, only trust NWS for snow depth. Open-Meteo (ERA5/GFS)
        # likely sources snowpack from model or gridded analysis data rather than
        # direct station observations, which can be badly wrong.
        if is_us:
            snow_source = attribution.field_sources.get("snow_depth_in")
            if snow_source and snow_source != "nws":
                merged_values.pop("snow_depth_in", None)
                merged_values.pop("snow_depth_cm", None)
                attribution.field_sources.pop("snow_depth_in", None)
                attribution.field_sources.pop("snow_depth_cm", None)

        # Create merged CurrentConditions
        merged = CurrentConditions(**merged_values)
        return merged, attribution

    def _apply_semantic_group_selections(
        self,
        valid_sources: list[SourceData],
        merged_values: dict[str, Any],
        attribution: SourceAttribution,
        is_us: bool,
    ) -> None:
        """Align related measurements so one semantic reading comes from one source."""
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="temperature",
            field_names=("temperature", "temperature_f", "temperature_c"),
            value_builder=self._build_temperature_values,
        )
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="dewpoint_f",
            field_names=("dewpoint_f", "dewpoint_c"),
            value_builder=self._build_dewpoint_values,
        )
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="wind_speed",
            field_names=("wind_speed", "wind_speed_mph", "wind_speed_kph"),
            value_builder=self._build_speed_values,
        )
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="pressure",
            field_names=("pressure", "pressure_in", "pressure_mb"),
            value_builder=self._build_pressure_values,
        )
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="feels_like_f",
            field_names=("feels_like_f", "feels_like_c"),
            value_builder=self._build_feels_like_values,
        )
        self._apply_visibility_selection(valid_sources, merged_values, attribution)
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="wind_gust_mph",
            field_names=("wind_gust_mph", "wind_gust_kph"),
            value_builder=self._build_wind_gust_values,
        )
        # Sanity-check: a gust must be >= sustained wind speed.  When the gust
        # came from a different source than the wind speed (cross-source fusion),
        # the two values may be in inconsistent units or just stale data.  Drop
        # the gust if it is physically impossible (gust < speed).
        self._discard_gust_if_below_wind_speed(merged_values, attribution)
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="precipitation_in",
            field_names=("precipitation_in", "precipitation_mm"),
            value_builder=self._build_precipitation_values,
        )
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="snow_depth_in",
            field_names=("snow_depth_in", "snow_depth_cm"),
            value_builder=self._build_snow_depth_values,
        )
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="wind_chill_f",
            field_names=("wind_chill_f", "wind_chill_c"),
            value_builder=self._build_wind_chill_values,
        )
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="freezing_level_ft",
            field_names=("freezing_level_ft", "freezing_level_m"),
            value_builder=self._build_freezing_level_values,
        )
        self._apply_priority_group_selection(
            valid_sources,
            merged_values,
            attribution,
            is_us=is_us,
            priority_field="heat_index_f",
            field_names=("heat_index_f", "heat_index_c"),
            value_builder=self._build_heat_index_values,
        )

    def _apply_priority_group_selection(
        self,
        valid_sources: list[SourceData],
        merged_values: dict[str, Any],
        attribution: SourceAttribution,
        *,
        is_us: bool,
        priority_field: str,
        field_names: tuple[str, ...],
        value_builder: Callable[[CurrentConditions], dict[str, float | None]],
    ) -> None:
        """Select one source for a semantic field group and normalize missing units."""
        source = self._select_semantic_group_source(
            valid_sources,
            field_names=field_names,
            priority_field=priority_field,
            is_us=is_us,
        )
        if source is None or source.current is None:
            return

        values = value_builder(source.current)
        self._set_group_values(values, merged_values, attribution, source.source)

    def _apply_visibility_selection(
        self,
        valid_sources: list[SourceData],
        merged_values: dict[str, Any],
        attribution: SourceAttribution,
    ) -> None:
        """Select visibility once and keep both units aligned to the winning source."""
        visibility = self._select_visibility(valid_sources)
        if visibility is None:
            return

        visibility_miles, visibility_km, source_name = visibility
        if visibility_miles is not None:
            merged_values["visibility_miles"] = visibility_miles
            attribution.field_sources["visibility_miles"] = source_name
        else:
            merged_values.pop("visibility_miles", None)
            attribution.field_sources.pop("visibility_miles", None)

        if visibility_km is not None:
            merged_values["visibility_km"] = visibility_km
            attribution.field_sources["visibility_km"] = source_name
        else:
            merged_values.pop("visibility_km", None)
            attribution.field_sources.pop("visibility_km", None)

    def _select_visibility(
        self,
        valid_sources: list[SourceData],
    ) -> tuple[float | None, float | None, str] | None:
        """
        Select visibility from the highest-priority source that has data.

        Visibility is treated as one semantic field with two unit representations.
        We use the highest-priority source's value directly rather than trying
        to pick the "most conservative" — the API returns what it returns.
        """
        best_source: SourceData | None = None

        for source in valid_sources:
            if source.current is None:
                continue

            miles = self._visibility_miles(source.current)
            if miles is None:
                continue

            # Take first source with data (valid_sources is already priority-ordered)
            best_source = source
            break

        if best_source is None or best_source.current is None:
            return None

        visibility_miles = best_source.current.visibility_miles
        visibility_km = best_source.current.visibility_km

        if visibility_miles is None and visibility_km is not None:
            visibility_miles = visibility_km / KM_PER_MILE
        if visibility_km is None and visibility_miles is not None:
            visibility_km = visibility_miles * KM_PER_MILE

        return visibility_miles, visibility_km, best_source.source

    def _visibility_miles(self, current: CurrentConditions) -> float | None:
        """Normalize visibility to miles for comparison."""
        if current.visibility_miles is not None:
            return current.visibility_miles
        if current.visibility_km is not None:
            return current.visibility_km / KM_PER_MILE
        return None

    def _build_temperature_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned temperature values from a single source."""
        return build_temperature_values(current)

    def _build_dewpoint_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned dewpoint values from a single source."""
        return build_dewpoint_values(current)

    def _build_feels_like_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned feels-like values from a single source."""
        return build_feels_like_values(current)

    def _build_wind_chill_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned wind chill values from a single source."""
        return build_wind_chill_values(current)

    def _build_heat_index_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned heat index values from a single source."""
        return build_heat_index_values(current)

    def _build_speed_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned wind speed values from a single source."""
        return build_speed_values(current)

    def _discard_gust_if_below_wind_speed(
        self,
        merged_values: dict[str, Any],
        attribution: SourceAttribution,
    ) -> None:
        """Drop wind gust when it is physically impossible."""
        discard_gust_if_below_wind_speed(merged_values, attribution)

    def _build_wind_gust_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned wind gust values from a single source."""
        return build_wind_gust_values(current)

    def _build_value_pair(
        self,
        value_a: float | None,
        value_b: float | None,
        base_name: str,
    ) -> dict[str, float | None]:
        """Build aligned Fahrenheit/Celsius-style value pairs from a single source."""
        return build_value_pair(value_a, value_b, base_name)

    def _build_speed_pair(
        self,
        value_mph: float | None,
        value_kph: float | None,
        base_name: str,
    ) -> dict[str, float | None]:
        """Build aligned mph/kph value pairs from a single source."""
        return build_speed_pair(value_mph, value_kph, base_name)

    def _build_pressure_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned pressure values from a single source."""
        return build_pressure_values(current)

    def _build_precipitation_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned precipitation totals from a single source."""
        return build_precipitation_values(current)

    def _build_snow_depth_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned snow depth values from a single source."""
        return build_snow_depth_values(current)

    def _build_freezing_level_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned freezing level values from a single source."""
        return build_freezing_level_values(current)

    def _check_temperature_conflicts(
        self,
        sources: list[SourceData],
        merged_values: dict[str, Any],
        attribution: SourceAttribution,
        is_us: bool,
    ) -> None:
        """Check for temperature conflicts and log them."""
        check_temperature_conflicts(self, sources, merged_values, attribution, is_us)

    def merge_forecasts(
        self,
        sources: list[SourceData],
        location: Location,
        requested_days: int = 7,
    ) -> tuple[Forecast | None, dict[str, str]]:
        """Select forecast from a single source based on location."""
        return select_forecast(self, sources, location, requested_days=requested_days)

    def merge_hourly_forecasts(
        self,
        sources: list[SourceData],
        location: Location,
    ) -> tuple[HourlyForecast | None, dict[str, str]]:
        """Select hourly forecast from a single source based on location."""
        return select_hourly_forecast(self, sources, location)

    def _select_hourly_pressure_source(
        self,
        valid_sources: list[SourceData],
        selected_source: SourceData,
    ) -> SourceData | None:
        """Return the selected hourly source or best alternate source with pressure data."""
        return select_hourly_pressure_source(self, valid_sources, selected_source)

    def _hourly_has_pressure(self, hourly: HourlyForecast | None) -> bool:
        """Return True when any hourly period includes pressure."""
        return hourly_has_pressure(hourly)

    def _overlay_hourly_pressure(
        self,
        display_hourly: HourlyForecast,
        pressure_hourly: HourlyForecast,
    ) -> HourlyForecast:
        """Copy pressure-only fields from a pressure-capable hourly source by nearest time."""
        return overlay_hourly_pressure(display_hourly, pressure_hourly)

    def _nearest_hourly_pressure_period(
        self,
        target: datetime,
        pressure_periods: list,
    ):
        """Find a pressure period close enough to the target display hour."""
        return nearest_hourly_pressure_period(target, pressure_periods)

    def _datetime_timestamp(self, value: datetime | None) -> float | None:
        """Normalize aware and naive datetimes to comparable timestamps."""
        return datetime_timestamp(value)
