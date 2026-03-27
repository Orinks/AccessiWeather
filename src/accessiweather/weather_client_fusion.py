"""Data fusion engine for merging weather data from multiple sources."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import fields, replace
from typing import Any

from accessiweather.config.source_priority import SourcePriorityConfig
from accessiweather.models.weather import (
    CurrentConditions,
    DataConflict,
    Forecast,
    HourlyForecast,
    Location,
    SourceAttribution,
    SourceData,
)

logger = logging.getLogger(__name__)

KM_PER_MILE = 1.609344
MB_PER_INHG = 33.8639
MM_PER_INCH = 25.4
CM_PER_INCH = 2.54
METERS_PER_FOOT = 0.3048


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

        # For US locations, only trust NWS for snow depth. Both Open-Meteo (ERA5/GFS)
        # and Visual Crossing likely source snowpack from SNODAS or similar gridded
        # analysis products rather than direct station observations — can be badly wrong.
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
        pair = self._build_value_pair(current.temperature_f, current.temperature_c, "temperature")
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

    def _build_dewpoint_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned dewpoint values from a single source."""
        return self._build_value_pair(current.dewpoint_f, current.dewpoint_c, "dewpoint")

    def _build_feels_like_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned feels-like values from a single source."""
        return self._build_value_pair(current.feels_like_f, current.feels_like_c, "feels_like")

    def _build_wind_chill_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned wind chill values from a single source."""
        return self._build_value_pair(current.wind_chill_f, current.wind_chill_c, "wind_chill")

    def _build_heat_index_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned heat index values from a single source."""
        return self._build_value_pair(current.heat_index_f, current.heat_index_c, "heat_index")

    def _build_speed_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned wind speed values from a single source."""
        pair = self._build_speed_pair(current.wind_speed_mph, current.wind_speed_kph, "wind_speed")
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

    def _discard_gust_if_below_wind_speed(
        self,
        merged_values: dict[str, Any],
        attribution: SourceAttribution,
    ) -> None:
        """Drop wind gust when it is physically impossible (gust < sustained speed).

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

    def _build_wind_gust_values(self, current: CurrentConditions) -> dict[str, float | None]:
        """Build aligned wind gust values from a single source."""
        return self._build_speed_pair(current.wind_gust_mph, current.wind_gust_kph, "wind_gust")

    def _build_value_pair(
        self,
        value_a: float | None,
        value_b: float | None,
        base_name: str,
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

    def _build_speed_pair(
        self,
        value_mph: float | None,
        value_kph: float | None,
        base_name: str,
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

    def _build_pressure_values(self, current: CurrentConditions) -> dict[str, float | None]:
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

    def _build_precipitation_values(self, current: CurrentConditions) -> dict[str, float | None]:
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

    def _build_snow_depth_values(self, current: CurrentConditions) -> dict[str, float | None]:
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

    def _build_freezing_level_values(self, current: CurrentConditions) -> dict[str, float | None]:
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
        requested_days: int = 7,
    ) -> tuple[Forecast | None, dict[str, str]]:
        """
        Select forecast from a single source based on location.

        Unlike merging multiple sources, forecasts are selected from a single preferred
        source to avoid duplicate periods with different naming conventions:
        - US locations: Prefer NWS (most accurate for US)
        - International: Use Open-Meteo
        - Visual Crossing: Used when explicitly selected or as fallback

        Args:
            sources: List of source data containers
            location: The location for source selection
            requested_days: User-configured forecast day target

        Returns:
            Tuple of Forecast from single source and source attribution

        """
        is_us = self._is_us_location(location)
        field_sources: dict[str, str] = {}

        # Filter to successful sources with forecasts
        valid_sources = [s for s in sources if s.success and s.forecast is not None]

        if not valid_sources:
            return None, field_sources

        # Select single source based on location (no merging to avoid duplicates)
        # US: prefer NWS for 7-day, Open-Meteo for extended ranges; PW as fallback
        # International: prefer Open-Meteo > Pirate Weather > Visual Crossing
        if is_us:
            preferred_order = (
                ["openmeteo", "nws", "visualcrossing", "pirateweather"]
                if requested_days > 7
                else ["nws", "openmeteo", "visualcrossing", "pirateweather"]
            )
        else:
            preferred_order = ["openmeteo", "pirateweather", "visualcrossing"]

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
        pirate_weather_source = next(
            (s for s in valid_sources if s.source == "pirateweather"), None
        )
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
        self,
        sources: list[SourceData],
        location: Location,
    ) -> tuple[HourlyForecast | None, dict[str, str]]:
        """
        Select hourly forecast from a single source based on location.

        Unlike other data types, hourly forecasts are NOT merged from multiple sources
        because different sources use different timezone representations that cause
        display issues when combined. Instead, we select the best single source:
        - US locations: Prefer NWS (most accurate for US)
        - International: Use Open-Meteo

        Args:
            sources: List of source data containers
            location: The location for source selection

        Returns:
            Tuple of HourlyForecast from single source and source attribution

        """
        is_us = self._is_us_location(location)
        field_sources: dict[str, str] = {}

        # Filter to successful sources with hourly forecasts
        valid_sources = [s for s in sources if s.success and s.hourly_forecast is not None]

        if not valid_sources:
            return None, field_sources

        # Select single source based on location (no merging for hourly data)
        # US: prefer NWS > Open-Meteo > Visual Crossing > Pirate Weather
        # International: prefer Open-Meteo > Pirate Weather > Visual Crossing
        if is_us:
            preferred_order = ["nws", "openmeteo", "visualcrossing", "pirateweather"]
        else:
            preferred_order = ["openmeteo", "pirateweather", "visualcrossing"]

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
        pirate_weather_source = next(
            (s for s in valid_sources if s.source == "pirateweather"), None
        )
        pirate_summary = (
            pirate_weather_source.hourly_forecast.summary
            if pirate_weather_source and pirate_weather_source.hourly_forecast
            else None
        )
        if hourly_forecast and hourly_forecast.summary is None and pirate_summary:
            hourly_forecast = replace(hourly_forecast, summary=pirate_summary)

        # Track attribution
        field_sources["hourly_source"] = source_name
        if pirate_summary and hourly_forecast and hourly_forecast.summary == pirate_summary:
            field_sources["hourly_summary"] = "pirateweather"
        logger.debug(f"Using {source_name} for hourly forecast (location: {location.name})")

        return hourly_forecast, field_sources
