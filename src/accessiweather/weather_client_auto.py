"""Auto-mode source selection helpers for WeatherClient."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from . import (
    weather_client_enrichment as enrichment,
    weather_client_trends as trends,
)
from .alert_lifecycle import diff_alerts
from .config.source_priority import SourcePriorityConfig
from .forecast_confidence import calculate_forecast_confidence
from .models import (
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    SourceAttribution,
    SourceData,
    WeatherAlerts,
    WeatherData,
)
from .weather_client_alerts import AlertAggregator
from .weather_client_fusion import DataFusionEngine
from .weather_client_parallel import ParallelFetchCoordinator

logger = logging.getLogger(__name__)


class WeatherClientAutoMixin:
    def _get_auto_mode_api_budget(self) -> str:
        """Return the validated automatic-mode API budget setting."""
        budget = getattr(self.settings, "auto_mode_api_budget", "max_coverage")
        return budget if budget in {"economy", "balanced", "max_coverage"} else "max_coverage"

    @staticmethod
    def _source_has_core_section(
        section: CurrentConditions | Forecast | HourlyForecast | None,
    ) -> bool:
        """Return True when a current/forecast/hourly section is present and populated."""
        return bool(section is not None and section.has_data())

    def _source_has_complete_core_data(self, source_data: SourceData | None) -> bool:
        """Return True when a single-source result includes current, forecast, and hourly data."""
        if source_data is None:
            return False
        return all(
            self._source_has_core_section(section)
            for section in (source_data.current, source_data.forecast, source_data.hourly_forecast)
        )

    @staticmethod
    def _configured_sources_in_fetch_order(
        active_sources: Sequence[str],
        fetchers: dict[str, object],
        fetched_sources: set[str] | None = None,
    ) -> list[str]:
        """Return configured sources that are currently fetchable, preserving user order."""
        already_fetched = fetched_sources or set()
        return [
            source
            for source in active_sources
            if source in fetchers and source not in already_fetched
        ]

    async def _fetch_auto_mode_sources(
        self,
        location: Location,
        coordinator: ParallelFetchCoordinator,
        fetchers: dict[str, object],
        requested_sources: Sequence[str],
    ) -> list[SourceData]:
        """Fetch a selected subset of automatic-mode sources."""
        sources_to_fetch = [source for source in requested_sources if source in fetchers]
        if not sources_to_fetch:
            return []

        return await coordinator.fetch_all(
            location=location,
            fetch_nws=fetchers["nws"]() if "nws" in sources_to_fetch else None,
            fetch_openmeteo=fetchers["openmeteo"]() if "openmeteo" in sources_to_fetch else None,
            fetch_pirateweather=(
                fetchers["pirateweather"]() if "pirateweather" in sources_to_fetch else None
            ),
        )

    async def _fetch_smart_auto_source(
        self, location: Location, skip_notifications: bool = False
    ) -> WeatherData:
        """Fetch weather data using staged automatic-source decisions."""
        logger.info("Using smart auto source for %s", location.name)

        auto_sources_us = getattr(
            self.settings,
            "auto_sources_us",
            ["nws", "openmeteo", "pirateweather"],
        )
        auto_sources_international = getattr(
            self.settings,
            "auto_sources_international",
            ["openmeteo", "pirateweather"],
        )

        config = SourcePriorityConfig(
            us_default=auto_sources_us,
            international_default=auto_sources_international,
        )
        auto_budget = self._get_auto_mode_api_budget()
        parallel_timeout = getattr(self.settings, "parallel_fetch_timeout", 5.0)
        coordinator = ParallelFetchCoordinator(timeout=parallel_timeout)
        fusion_engine = DataFusionEngine(config)
        alert_aggregator = AlertAggregator()

        is_us = self._is_us_location(location)
        active_sources = list(auto_sources_us if is_us else auto_sources_international)

        async def fetch_openmeteo():
            current, forecast, hourly = await self._fetch_openmeteo_data(location)
            return (current, forecast, hourly)

        async def fetch_nws():
            (
                current,
                forecast,
                _discussion,
                _discussion_time,
                alerts,
                hourly,
            ) = await self._fetch_nws_data(location)
            return (current, forecast, hourly, alerts)

        async def fetch_pw():
            pirate_weather_client = self._pirate_weather_client_for_location(location)
            if not pirate_weather_client:
                return (None, None, None, None)
            current = await pirate_weather_client.get_current_conditions(location)
            forecast = await pirate_weather_client.get_forecast(
                location,
                days=self._get_forecast_days_for_source(location, source="pirateweather"),
            )
            hourly = await pirate_weather_client.get_hourly_forecast(location)
            alerts = await pirate_weather_client.get_alerts(location)
            return (current, forecast, hourly, alerts)

        fetchers: dict[str, object] = {}
        if "openmeteo" in active_sources:
            fetchers["openmeteo"] = fetch_openmeteo
        if is_us and "nws" in active_sources:
            fetchers["nws"] = fetch_nws
        if self._pirate_weather_client_for_location(location) and "pirateweather" in active_sources:
            fetchers["pirateweather"] = fetch_pw

        if auto_budget == "max_coverage":
            source_results = await self._fetch_auto_mode_sources(
                location, coordinator, fetchers, active_sources
            )
        else:
            configured_sources = self._configured_sources_in_fetch_order(active_sources, fetchers)
            primary_source = configured_sources[0] if configured_sources else None
            primary_sources = (
                [primary_source] if primary_source and primary_source in fetchers else []
            )
            source_results = await self._fetch_auto_mode_sources(
                location, coordinator, fetchers, primary_sources
            )

            fetched_sources = {source.source for source in source_results}
            primary_result = source_results[0] if source_results else None
            core_complete = self._source_has_complete_core_data(primary_result)
            needs_us_openmeteo = (
                is_us
                and "openmeteo" in fetchers
                and "openmeteo" not in fetched_sources
                and (
                    self._should_use_openmeteo_for_extended_forecast(location, source="auto")
                    or not core_complete
                )
            )
            needs_intl_alert_source = (
                not is_us
                and primary_source == "openmeteo"
                and "pirateweather" not in fetched_sources
            )
            needs_intl_core_fallback = not is_us and not core_complete

            remaining_sources = self._configured_sources_in_fetch_order(
                active_sources, fetchers, fetched_sources
            )

            def _pick_secondary_candidate(predicate) -> list[str]:
                for source in remaining_sources:
                    if predicate(source):
                        return [source]
                return []

            secondary_sources: list[str] = []
            if needs_us_openmeteo or (auto_budget == "balanced" and is_us and not core_complete):
                secondary_sources = _pick_secondary_candidate(lambda _source: True)
            elif needs_intl_alert_source:
                secondary_sources = _pick_secondary_candidate(
                    lambda source: source == "pirateweather"
                )
            elif needs_intl_core_fallback:
                secondary_sources = _pick_secondary_candidate(lambda _source: True)

            if secondary_sources:
                source_results.extend(
                    await self._fetch_auto_mode_sources(
                        location, coordinator, fetchers, secondary_sources
                    )
                )

        successful_sources = [s for s in source_results if s.success]
        if not successful_sources:
            logger.warning("All sources failed for %s, checking cache", location.name)
            return self._handle_all_sources_failed(location, source_results)

        merged_current, current_attribution = fusion_engine.merge_current_conditions(
            source_results, location
        )
        requested_days = getattr(self.settings, "forecast_duration_days", 7)
        merged_forecast, forecast_attribution = fusion_engine.merge_forecasts(
            source_results, location, requested_days=requested_days
        )
        merged_hourly, hourly_attribution = fusion_engine.merge_hourly_forecasts(
            source_results, location
        )

        _want_start = getattr(self.settings, "notify_minutely_precipitation_start", False)
        _want_stop = getattr(self.settings, "notify_minutely_precipitation_stop", False)
        _want_likelihood = getattr(self.settings, "notify_precipitation_likelihood", False)
        _pw_fetched = any(source.source == "pirateweather" for source in source_results)
        merged_minutely = None
        if self.pirate_weather_api_key and (
            _pw_fetched or _want_start or _want_stop or _want_likelihood
        ):
            merged_minutely = await self._get_pirate_weather_minutely(location)

        has_any_data = (
            self._source_has_core_section(merged_current)
            or self._source_has_core_section(merged_forecast)
            or self._source_has_core_section(merged_hourly)
        )
        if not has_any_data:
            logger.warning("All sources returned empty data for %s", location.name)
            return self._handle_all_sources_failed(location, source_results)

        nws_alerts = None
        pw_alerts_data = None
        for source in source_results:
            if source.source == "nws" and source.alerts:
                nws_alerts = source.alerts
            elif source.source == "pirateweather" and source.alerts:
                pw_alerts_data = source.alerts

        if is_us and nws_alerts is not None:
            merged_alerts = alert_aggregator.aggregate_alerts(nws_alerts, None)
        else:
            merged_alerts = alert_aggregator.aggregate_alerts(nws_alerts, pw_alerts_data)

        _loc_key = self._location_key(location)
        _prev_alerts = self._previous_alerts.get(_loc_key)
        _cancel_refs = (
            await self._fetch_nws_cancel_references() if nws_alerts is not None else set()
        )
        _alert_diff = diff_alerts(_prev_alerts, merged_alerts, confirmed_cancel_ids=_cancel_refs)
        self._previous_alerts[_loc_key] = merged_alerts

        failed_sources = {source.source for source in source_results if not source.success}
        contributing_sources = (
            current_attribution.contributing_sources
            | set(forecast_attribution.values())
            | set(hourly_attribution.values())
            | {source.source for source in source_results if source.alerts is not None}
        )
        attribution = SourceAttribution(
            field_sources={
                **current_attribution.field_sources,
                **forecast_attribution,
                **hourly_attribution,
            },
            conflicts=current_attribution.conflicts,
            contributing_sources=contributing_sources,
            failed_sources=current_attribution.failed_sources | failed_sources,
        )

        incomplete_sections: set[str] = set()
        if merged_current is None:
            incomplete_sections.add("current")
        if merged_forecast is None:
            incomplete_sections.add("forecast")
        if merged_hourly is None:
            incomplete_sections.add("hourly_forecast")

        if is_us and any(source.source == "nws" for source in source_results):
            discussion = "Forecast discussion available from NWS for US locations."
            discussion_issuance_time = None
        elif is_us:
            discussion = (
                "Forecast discussion is unavailable because Automatic mode did not use NWS."
            )
            discussion_issuance_time = None
        else:
            discussion = "Forecast discussion not available from Open-Meteo."
            discussion_issuance_time = None

        confidence = calculate_forecast_confidence(source_results)
        weather_data = WeatherData(
            location=location,
            current=merged_current,
            forecast=merged_forecast,
            hourly_forecast=merged_hourly,
            discussion=discussion,
            discussion_issuance_time=discussion_issuance_time,
            minutely_precipitation=merged_minutely,
            alerts=merged_alerts,
            source_attribution=attribution,
            incomplete_sections=incomplete_sections,
            forecast_confidence=confidence,
        )
        weather_data.alert_lifecycle_diff = _alert_diff

        if weather_data.has_any_data():
            enrichment_tasks = self._launch_enrichment_tasks(
                weather_data, location, skip_notifications
            )
            await self._await_enrichments(enrichment_tasks, weather_data)

        if weather_data.has_any_data() and self.offline_cache:
            self._persist_weather_data(location, weather_data)

        logger.info(
            "Smart auto source completed for %s: %d sources succeeded",
            location.name,
            len(successful_sources),
        )
        return weather_data

    def _handle_all_sources_failed(
        self, location: Location, source_results: list[SourceData]
    ) -> WeatherData:
        """
        Handle the case when all sources fail.

        Returns cached data if available, marked as stale.

        Args:
            location: The location that failed
            source_results: List of failed source results

        Returns:
            Cached WeatherData marked as stale, or empty WeatherData

        """
        # Try to return cached data
        if self.offline_cache:
            cached = self.offline_cache.load(location, allow_stale=True)
            if cached:
                cached.stale = True
                cached.stale_reason = "All weather sources failed"
                logger.info(f"Returning stale cached data for {location.name}")
                self._remember_weather_data(cached)
                return cached

        # No cache available, return empty data with attribution
        attribution = SourceAttribution()
        for source in source_results:
            attribution.failed_sources.add(source.source)

        # Return empty but non-None objects for backward compatibility
        return WeatherData(
            location=location,
            current=CurrentConditions(),
            forecast=Forecast(periods=[]),
            hourly_forecast=HourlyForecast(periods=[]),
            alerts=WeatherAlerts(alerts=[]),
            source_attribution=attribution,
            incomplete_sections={"current", "forecast", "hourly_forecast", "alerts"},
            stale=True,
            stale_reason="All weather sources failed and no cached data available",
        )

    def _launch_enrichment_tasks(
        self, weather_data: WeatherData, location: Location, skip_notifications: bool = False
    ) -> dict[str, asyncio.Task]:
        """
        Launch enrichment tasks that can run concurrently.

        Returns a dictionary of task names to asyncio.Task objects that can be
        awaited later for progressive updates.

        Args:
        ----
            weather_data: The WeatherData object to enrich
            location: The location for enrichment
            skip_notifications: If True, skip triggering alert notifications

        Returns:
        -------
            Dictionary mapping enrichment names to their tasks

        """
        tasks = {}

        # Smart enrichments for auto mode
        if self.data_source == "auto":
            tasks["sunrise_sunset"] = asyncio.create_task(
                enrichment.enrich_with_sunrise_sunset(self, weather_data, location)
            )
            tasks["nws_discussion"] = asyncio.create_task(
                enrichment.enrich_with_nws_discussion(self, weather_data, location)
            )

        # Post-processing enrichments (always run)
        tasks["environmental"] = asyncio.create_task(
            enrichment.populate_environmental_metrics(self, weather_data, location)
        )
        tasks["aviation"] = asyncio.create_task(
            enrichment.enrich_with_aviation_data(self, weather_data, location)
        )
        tasks["marine"] = asyncio.create_task(
            enrichment.enrich_with_marine_data(self, weather_data, location)
        )

        return tasks

    async def _await_enrichments(
        self, tasks: dict[str, asyncio.Task], weather_data: WeatherData
    ) -> None:
        """
        Await all enrichment tasks and apply final processing.

        Args:
        ----
            tasks: Dictionary of enrichment task names to Task objects
            weather_data: The WeatherData object being enriched

        """
        # Await all tasks, capturing exceptions
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # Log any errors from enrichments (non-fatal)
        for task_name, result in zip(tasks.keys(), results, strict=False):
            if isinstance(result, Exception):
                logger.debug(f"Enrichment '{task_name}' failed: {result}")

        # Apply final processing
        trends.apply_trend_insights(  # pragma: no cover
            weather_data,
            self.trend_insights_enabled,
            self.trend_hours,
            include_pressure=self.show_pressure_trend,
        )
        self._persist_weather_data(weather_data.location, weather_data)
