"""Main weather fetch orchestration helpers for WeatherClient."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .alert_lifecycle import diff_alerts
from .models import (
    Location,
    SourceAttribution,
    WeatherAlerts,
    WeatherData,
)
from .pirate_weather_client import PirateWeatherApiError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class WeatherClientFetchMixin:
    async def _fetch_weather_data_with_dedup(
        self, location: Location, force_refresh: bool, skip_notifications: bool = False
    ) -> WeatherData:
        """
        Fetch weather data with deduplication tracking.

        This method prevents multiple concurrent requests for the same location.
        """
        location_key = self._location_key(location)

        # Check if there's already an in-flight request for this location
        if not force_refresh and location_key in self._in_flight_requests:
            # Wait for the existing request to complete
            logger.debug(f"Request for {location.name} already in flight, waiting for result")
            return await self._in_flight_requests[location_key]

        # Create a new task for this request
        if not force_refresh:
            task = asyncio.create_task(self._do_fetch_weather_data(location, skip_notifications))
            self._in_flight_requests[location_key] = task

            try:
                return await task
            finally:
                # Clean up completed request from tracking
                self._in_flight_requests.pop(location_key, None)
        else:
            # Force refresh bypasses deduplication
            return await self._do_fetch_weather_data(location, skip_notifications)

    async def _do_fetch_weather_data(
        self, location: Location, skip_notifications: bool = False
    ) -> WeatherData:
        """
        Perform the actual weather data fetch.

        This is the core fetch logic separated for deduplication purposes.
        """
        # Check if we should use smart auto source (parallel multi-source fetch)
        if self.data_source == "auto":
            return await self._fetch_smart_auto_source(location, skip_notifications)

        # Determine which API to use based on data source and location
        logger.debug("Determining API choice")
        api_choice = self._determine_api_choice(location)
        api_name = {
            "nws": "NWS",
            "openmeteo": "Open-Meteo",
            "pirateweather": "Pirate Weather",
        }.get(api_choice, "NWS")
        logger.info(f"Using {api_name} API for {location.name} (data_source: {self.data_source})")

        logger.debug("Creating WeatherData object")
        weather_data = WeatherData(location=location)

        if api_choice == "pirateweather":
            # Use Pirate Weather API
            try:
                pirate_weather_client = self._pirate_weather_client_for_location(location)
                if not pirate_weather_client:
                    raise PirateWeatherApiError("Pirate Weather API key not configured")

                # Parallelize API calls for better performance
                current, forecast, hourly_forecast, alerts = await asyncio.gather(
                    pirate_weather_client.get_current_conditions(location),
                    pirate_weather_client.get_forecast(
                        location,
                        days=self._get_forecast_days_for_source(location, source="pirateweather"),
                    ),
                    pirate_weather_client.get_hourly_forecast(location),
                    pirate_weather_client.get_alerts(location),
                )

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = "Forecast discussion not available from Pirate Weather."
                weather_data.discussion_issuance_time = None
                weather_data.alerts = alerts

                # Compute alert lifecycle diff
                _pw_loc_key = self._location_key(location)
                _pw_prev = self._previous_alerts.get(_pw_loc_key)
                weather_data.alert_lifecycle_diff = diff_alerts(_pw_prev, alerts)
                if alerts is not None:
                    self._previous_alerts[_pw_loc_key] = alerts

                # Set source attribution
                weather_data.source_attribution = SourceAttribution(
                    contributing_sources={"pirateweather"},
                )

                logger.info(f"Successfully fetched Pirate Weather data for {location.name}")

            except PirateWeatherApiError as e:
                logger.error(f"Pirate Weather API failed for {location.name}: {e}")
                self._set_empty_weather_data(weather_data)

        elif api_choice == "openmeteo":
            # Use Open-Meteo API only (user explicitly selected this source)
            try:
                current, forecast, hourly_forecast = await self._fetch_openmeteo_data(location)

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = "Forecast discussion not available from Open-Meteo."
                weather_data.discussion_issuance_time = None
                weather_data.alerts = WeatherAlerts(alerts=[])  # Open-Meteo doesn't provide alerts

                # Set source attribution for single-source mode
                weather_data.source_attribution = SourceAttribution(
                    contributing_sources={"openmeteo"},
                )

                logger.info(f"Successfully fetched Open-Meteo data for {location.name}")

            except Exception as e:
                logger.error(f"Open-Meteo API failed for {location.name}: {e}")
                self._set_empty_weather_data(weather_data)
        else:
            # Use NWS API only (user explicitly selected this source)
            try:
                use_openmeteo_forecast = self._should_use_openmeteo_for_extended_forecast(
                    location, source="nws"
                )

                if use_openmeteo_forecast:
                    current_task = asyncio.create_task(self._get_nws_current_conditions(location))
                    forecast_task = asyncio.create_task(self._get_openmeteo_forecast(location))
                    discussion_task = asyncio.create_task(self._get_nws_discussion_only(location))
                    alerts_task = asyncio.create_task(self._get_nws_alerts(location))
                    hourly_task = asyncio.create_task(self._get_nws_hourly_forecast(location))

                    current = await current_task
                    forecast = await forecast_task
                    discussion, discussion_issuance_time = await discussion_task
                    alerts = await alerts_task
                    hourly_forecast = await hourly_task
                else:
                    (
                        current,
                        forecast,
                        discussion,
                        discussion_issuance_time,
                        alerts,
                        hourly_forecast,
                    ) = await self._fetch_nws_data(location)

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = discussion
                weather_data.discussion_issuance_time = discussion_issuance_time
                weather_data.alerts = alerts

                # Compute alert lifecycle diff for NWS single-source path
                _nws_loc_key = self._location_key(location)
                _nws_prev = self._previous_alerts.get(_nws_loc_key)
                _cancel_refs = await self._fetch_nws_cancel_references()
                weather_data.alert_lifecycle_diff = diff_alerts(
                    _nws_prev, alerts, confirmed_cancel_ids=_cancel_refs
                )
                if alerts is not None:
                    self._previous_alerts[_nws_loc_key] = alerts

                # Set source attribution for single-source mode
                weather_data.source_attribution = SourceAttribution(
                    field_sources={
                        "forecast_source": "openmeteo" if use_openmeteo_forecast else "nws",
                        "hourly_source": "nws",
                    },
                    contributing_sources={"nws", "openmeteo"}
                    if use_openmeteo_forecast
                    else {"nws"},
                )

                if (current is None or not current.has_data()) and forecast is None:
                    logger.warning(f"NWS returned empty data for {location.name}")
                else:
                    logger.info(f"Successfully fetched NWS data for {location.name}")

            except Exception as e:
                logger.error(f"NWS API failed for {location.name}: {e}")
                self._set_empty_weather_data(weather_data)

        if weather_data.has_any_data():
            # Launch enrichment tasks in parallel
            enrichment_tasks = self._launch_enrichment_tasks(
                weather_data, location, skip_notifications
            )
            # Await enrichment completion (which includes persisting to cache)
            await self._await_enrichments(enrichment_tasks, weather_data)

        if not weather_data.has_any_data() and self.offline_cache:
            cached = self.offline_cache.load(location)
            if cached:
                logger.info(f"Using cached weather data for {location.name}")
                self._remember_weather_data(cached)
                return cached

        self._remember_weather_data(weather_data)
        return weather_data
