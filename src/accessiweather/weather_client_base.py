"""Core WeatherClient implementation with enrichment delegation."""

import asyncio
import logging
import os
from collections.abc import Sequence
from datetime import datetime

import httpx

try:  # pragma: no cover - standard library availability guard
    from unittest.mock import Mock
except ImportError:  # pragma: no cover
    Mock = None

from . import (
    weather_client_enrichment as enrichment,
    weather_client_nws as nws_client,
    weather_client_openmeteo as openmeteo_client,
    weather_client_parsers as parsers,
    weather_client_trends as trends,
    weather_client_visualcrossing as vc_alerts,
)
from .cache import WeatherDataCache
from .models import (
    AppSettings,
    AviationData,
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)
from .services import EnvironmentalDataClient, MeteoAlarmClient
from .utils.retry import APITimeoutError, retry_with_backoff
from .visual_crossing_client import VisualCrossingApiError, VisualCrossingClient

logger = logging.getLogger(__name__)


class WeatherClient:
    """Simple async weather API client."""

    def __init__(
        self,
        user_agent: str = "AccessiWeather/1.0",
        data_source: str = "auto",
        visual_crossing_api_key: str = "",
        settings: AppSettings | None = None,
        *,
        meteoalarm_client: MeteoAlarmClient | None = None,
        environmental_client: EnvironmentalDataClient | None = None,
        offline_cache: WeatherDataCache | None = None,
    ):
        """Initialize the instance."""
        self.user_agent = user_agent
        self.nws_base_url = "https://api.weather.gov"
        self.openmeteo_base_url = "https://api.open-meteo.com/v1"
        self.timeout = 10.0
        self.data_source = data_source  # "auto", "nws", "openmeteo", "visualcrossing"
        self.visual_crossing_api_key = visual_crossing_api_key
        self.settings = settings or AppSettings()
        self._test_mode = bool(os.environ.get("PYTEST_CURRENT_TEST"))
        self.alerts_enabled = bool(self.settings.enable_alerts)
        self.international_alerts_enabled = bool(self.settings.international_alerts_enabled)
        if self._test_mode and meteoalarm_client is None:
            self.international_alerts_enabled = False
        self.international_alerts_provider = (
            (self.settings.international_alerts_provider or "meteosalarm").strip().lower()
        )
        self.trend_insights_enabled = bool(self.settings.trend_insights_enabled)
        self.trend_hours = max(1, int(self.settings.trend_hours or 24))
        self.show_pressure_trend = bool(getattr(self.settings, "show_pressure_trend", True))
        self.air_quality_enabled = bool(self.settings.air_quality_enabled)
        self.pollen_enabled = bool(self.settings.pollen_enabled)
        if self._test_mode:
            self.air_quality_enabled = False
            self.pollen_enabled = False
        self.air_quality_notify_threshold = int(self.settings.air_quality_notify_threshold or 0)
        self.offline_cache = offline_cache
        if self.offline_cache:
            try:
                self.offline_cache.purge_expired()
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Weather cache purge failed: {exc}")

        # Initialize Visual Crossing client if API key is provided
        self.visual_crossing_client = None
        if visual_crossing_api_key:
            self.visual_crossing_client = VisualCrossingClient(visual_crossing_api_key, user_agent)

        # Secondary data providers
        self.meteoalarm_client = meteoalarm_client
        if (
            self.international_alerts_enabled
            and self.meteoalarm_client is None
            and self.international_alerts_provider == "meteosalarm"
        ):
            self.meteoalarm_client = MeteoAlarmClient(user_agent=user_agent, timeout=self.timeout)

        self.environmental_client = environmental_client
        if (self.air_quality_enabled or self.pollen_enabled) and self.environmental_client is None:
            self.environmental_client = EnvironmentalDataClient(
                user_agent=user_agent, timeout=self.timeout
            )

        # Reusable HTTP client for performance
        self._http_client: httpx.AsyncClient | None = None

        # Track in-flight requests to deduplicate concurrent calls
        self._in_flight_requests: dict[str, asyncio.Task[WeatherData]] = {}

    def _location_key(self, location: Location) -> str:
        """Generate a unique key for a location to track in-flight requests."""
        return f"{location.name}:{location.latitude:.4f},{location.longitude:.4f}"

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the reusable HTTP client with optimized connection pooling."""
        if self._http_client is None or getattr(self._http_client, "is_closed", False):
            # Optimized connection pool for concurrent requests:
            # - max_connections=30: Allows multiple concurrent API calls
            # - max_keepalive_connections=15: Reuses connections for performance
            # - timeout with connect=3.0: Fast connection timeout
            timeout_config = httpx.Timeout(connect=3.0, read=5.0, write=5.0, pool=5.0)
            client = httpx.AsyncClient(
                timeout=timeout_config,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=15, max_connections=30),
            )
            if Mock is not None and isinstance(client, Mock):
                enter = getattr(client, "__aenter__", None)
                if enter is not None:
                    entered = getattr(enter, "return_value", None)
                    if entered is not None:
                        client = entered  # type: ignore[assignment]
            self._http_client = client  # type: ignore[assignment]
        return self._http_client

    def _methods_overridden(self, method_names: Sequence[str]) -> bool:
        """Detect if any of the named methods have been monkeypatched or mocked."""
        for name in method_names:
            current = getattr(self, name, None)
            original = getattr(self.__class__, name, None)

            if current is None or original is None:
                continue

            if Mock is not None and isinstance(current, Mock):
                return True

            current_callable = getattr(current, "__func__", current)
            original_callable = getattr(original, "__func__", original)

            if current_callable is not original_callable:
                return True

        return False

    async def _fetch_nws_data(
        self, location: Location
    ) -> tuple[
        CurrentConditions | None,
        Forecast | None,
        str | None,
        WeatherAlerts | None,
        HourlyForecast | None,
    ]:
        """Fetch NWS data, respecting test overrides while using optimized parallel path."""
        method_names = [
            "_get_nws_current_conditions",
            "_get_nws_forecast_and_discussion",
            "_get_nws_alerts",
            "_get_nws_hourly_forecast",
        ]

        client = self._get_http_client()
        client_is_mock = Mock is not None and isinstance(client, Mock)

        if not self._methods_overridden(method_names) and not client_is_mock:
            # Use retry wrapper for the parallel fetch
            try:
                return await retry_with_backoff(
                    nws_client.get_nws_all_data_parallel,
                    location,
                    self.nws_base_url,
                    self.user_agent,
                    self.timeout,
                    client,
                    max_retries=1,
                    initial_delay=1.0,
                )
            except APITimeoutError as exc:
                logger.error(f"NWS API timeout after retries: {exc}")
                return None, None, None, None, None

        current, forecast_result, alerts, hourly_forecast = await asyncio.gather(
            self._get_nws_current_conditions(location),
            self._get_nws_forecast_and_discussion(location),
            self._get_nws_alerts(location),
            self._get_nws_hourly_forecast(location),
        )

        forecast: Forecast | None
        discussion: str | None
        if isinstance(forecast_result, tuple):
            forecast, discussion = forecast_result
        else:
            forecast, discussion = (None, None)

        return current, forecast, discussion, alerts, hourly_forecast

    async def _fetch_openmeteo_data(
        self, location: Location
    ) -> tuple[CurrentConditions | None, Forecast | None, HourlyForecast | None]:
        """Fetch Open-Meteo data, respecting test overrides while using optimized parallel path."""
        method_names = [
            "_get_openmeteo_current_conditions",
            "_get_openmeteo_forecast",
            "_get_openmeteo_hourly_forecast",
        ]

        client = self._get_http_client()
        client_is_mock = Mock is not None and isinstance(client, Mock)

        if not self._methods_overridden(method_names) and not client_is_mock:
            # Use retry wrapper for the parallel fetch
            try:
                return await retry_with_backoff(
                    openmeteo_client.get_openmeteo_all_data_parallel,
                    location,
                    self.openmeteo_base_url,
                    self.timeout,
                    client,
                    max_retries=1,
                    initial_delay=1.0,
                )
            except APITimeoutError as exc:
                logger.error(f"Open-Meteo API timeout after retries: {exc}")
                return None, None, None

        return await asyncio.gather(
            self._get_openmeteo_current_conditions(location),
            self._get_openmeteo_forecast(location),
            self._get_openmeteo_hourly_forecast(location),
        )

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Async context manager exit."""
        await self.close()

    async def pre_warm_cache(self, location: Location) -> bool:
        """
        Pre-warm the cache for a location by fetching and storing weather data.

        This method is useful for reducing first-load latency by populating the cache
        before the user requests data.

        Args:
        ----
            location: The location to pre-warm cache for

        Returns:
        -------
            True if cache was successfully warmed, False otherwise

        """
        logger.info(f"Pre-warming cache for {location.name}")
        try:
            # Fetch fresh data (bypassing cache)
            weather_data = await self.get_weather_data(location, force_refresh=True)

            if weather_data.has_any_data():
                logger.info(f"✓ Cache pre-warmed successfully for {location.name}")
                return True

            logger.warning(f"Cache pre-warm failed: no data returned for {location.name}")
            return False

        except Exception as exc:
            logger.error(f"Cache pre-warm failed for {location.name}: {exc}")
            return False

    def get_cached_weather(self, location: Location) -> WeatherData | None:
        """
        Retrieve cached weather data for a location without triggering a network fetch.

        Args:
        ----
            location: The location to retrieve cached data for.

        Returns:
        -------
            The cached WeatherData or None if not found.

        """
        if not self.offline_cache:
            return None
        # Load with allow_stale=True so we can show something immediately
        # The calling code can check .stale property if it cares
        return self.offline_cache.load(location, allow_stale=True)

    async def get_weather_data(
        self, location: Location, force_refresh: bool = False
    ) -> WeatherData:
        """
        Get complete weather data for a location.

        Args:
            location: Location to fetch weather for
            force_refresh: If True, bypass cache and force fresh API call

        """
        logger.info(f"Fetching weather data for {location.name}")

        # Handle force_refresh by temporarily clearing cache for this location
        if force_refresh and self.offline_cache:
            logger.debug(f"Force refresh requested, clearing cache for {location.name}")
            self.offline_cache.invalidate(location)

        # Use deduplication for concurrent requests
        return await self._fetch_weather_data_with_dedup(location, force_refresh)

    async def _fetch_weather_data_with_dedup(
        self, location: Location, force_refresh: bool
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
            task = asyncio.create_task(self._do_fetch_weather_data(location))
            self._in_flight_requests[location_key] = task

            try:
                return await task
            finally:
                # Clean up completed request from tracking
                self._in_flight_requests.pop(location_key, None)
        else:
            # Force refresh bypasses deduplication
            return await self._do_fetch_weather_data(location)

    async def _do_fetch_weather_data(self, location: Location) -> WeatherData:
        """
        Perform the actual weather data fetch.

        This is the core fetch logic separated for deduplication purposes.
        """
        # Determine which API to use based on data source and location
        logger.debug("Determining API choice")
        api_choice = self._determine_api_choice(location)
        api_name = {
            "nws": "NWS",
            "openmeteo": "Open-Meteo",
            "visualcrossing": "Visual Crossing",
        }.get(api_choice, "NWS")
        logger.info(f"Using {api_name} API for {location.name} (data_source: {self.data_source})")

        logger.debug("Creating WeatherData object")
        weather_data = WeatherData(location=location, last_updated=datetime.now())

        if api_choice == "visualcrossing":
            # Use Visual Crossing API
            try:
                if not self.visual_crossing_client:
                    raise VisualCrossingApiError("Visual Crossing API key not configured")

                # Parallelize API calls for better performance
                current, forecast, hourly_forecast, alerts = await asyncio.gather(
                    self.visual_crossing_client.get_current_conditions(location),
                    self.visual_crossing_client.get_forecast(location),
                    self.visual_crossing_client.get_hourly_forecast(location),
                    self.visual_crossing_client.get_alerts(location),
                )

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = "Forecast discussion not available from Visual Crossing."
                weather_data.alerts = alerts

                # Process alerts for notifications if we have any
                if alerts and alerts.has_alerts():
                    logger.info(
                        f"Processing {len(alerts.alerts)} Visual Crossing alerts for notifications"
                    )
                    await self._process_visual_crossing_alerts(alerts, location)

                logger.info(f"Successfully fetched Visual Crossing data for {location.name}")

            except VisualCrossingApiError as e:
                logger.warning(f"Visual Crossing API failed for {location.name}: {e}")

                # Try fallback based on location
                if self._is_us_location(location):
                    logger.info(f"Trying NWS fallback for US location: {location.name}")
                    try:
                        (
                            current,
                            forecast,
                            discussion,
                            alerts,
                            hourly_forecast,
                        ) = await self._fetch_nws_data(location)

                        current = await self._augment_current_with_openmeteo(current, location)
                        weather_data.current = current
                        weather_data.forecast = forecast
                        weather_data.hourly_forecast = hourly_forecast
                        weather_data.discussion = discussion
                        weather_data.alerts = alerts

                        logger.info(f"Successfully fetched NWS fallback data for {location.name}")
                    except Exception as e2:
                        logger.error(
                            f"Both Visual Crossing and NWS failed for {location.name}: "
                            f"VC={e}, NWS={e2}"
                        )
                        self._set_empty_weather_data(weather_data)
                else:
                    logger.info(
                        f"Trying Open-Meteo fallback for international location: {location.name}"
                    )
                    try:
                        current, forecast, hourly_forecast = await self._fetch_openmeteo_data(
                            location
                        )

                        weather_data.current = current
                        weather_data.forecast = forecast
                        weather_data.hourly_forecast = hourly_forecast
                        weather_data.discussion = (
                            "Forecast discussion not available from Open-Meteo."
                        )
                        weather_data.alerts = WeatherAlerts(alerts=[])

                        logger.info(
                            f"Successfully fetched Open-Meteo fallback data for {location.name}"
                        )
                    except Exception as e2:
                        logger.error(
                            f"Both Visual Crossing and Open-Meteo failed for "
                            f"{location.name}: VC={e}, OM={e2}"
                        )
                        self._set_empty_weather_data(weather_data)

        elif api_choice == "openmeteo":
            # Use Open-Meteo API with parallel fetching
            try:
                current, forecast, hourly_forecast = await self._fetch_openmeteo_data(location)

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = "Forecast discussion not available from Open-Meteo."
                weather_data.alerts = WeatherAlerts(alerts=[])  # Open-Meteo doesn't provide alerts

                logger.info(f"Successfully fetched Open-Meteo data for {location.name}")

            except Exception as e:
                logger.warning(f"Open-Meteo API failed for {location.name}: {e}")

                # Try NWS as fallback if location is in US
                if self._is_us_location(location):
                    logger.info(f"Trying NWS fallback for US location: {location.name}")
                    try:
                        (
                            current,
                            forecast,
                            discussion,
                            alerts,
                            hourly_forecast,
                        ) = await self._fetch_nws_data(location)

                        current = await self._augment_current_with_openmeteo(current, location)
                        weather_data.current = current
                        weather_data.forecast = forecast
                        weather_data.hourly_forecast = hourly_forecast
                        weather_data.discussion = discussion
                        weather_data.alerts = alerts

                        logger.info(f"Successfully fetched NWS fallback data for {location.name}")
                    except Exception as e2:
                        logger.error(
                            f"Both Open-Meteo and NWS failed for {location.name}: "
                            f"OpenMeteo={e}, NWS={e2}"
                        )
                        self._set_empty_weather_data(weather_data)
                else:
                    logger.error(
                        f"Open-Meteo failed for international location {location.name}: {e}"
                    )
                    self._set_empty_weather_data(weather_data)
        else:
            # Use NWS API with parallel fetching
            try:
                (
                    current,
                    forecast,
                    discussion,
                    alerts,
                    hourly_forecast,
                ) = await self._fetch_nws_data(location)

                current = await self._augment_current_with_openmeteo(current, location)
                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = discussion
                weather_data.alerts = alerts

                # Check if we actually got valid data
                if (current is None or not current.has_data()) and forecast is None:
                    # If essential data is missing, try Open-Meteo fallback
                    logger.info(
                        f"NWS returned empty data for {location.name}, trying Open-Meteo fallback"
                    )
                    try:
                        current, forecast, hourly_forecast = await self._fetch_openmeteo_data(
                            location
                        )

                        weather_data.current = current
                        weather_data.forecast = forecast
                        weather_data.hourly_forecast = hourly_forecast
                        weather_data.discussion = (
                            "Forecast discussion not available from Open-Meteo."
                        )
                        weather_data.alerts = WeatherAlerts(alerts=[])

                        # Check if Open-Meteo returned valid data
                        if current is None and forecast is None:
                            logger.error(f"Open-Meteo also returned empty data for {location.name}")
                            self._set_empty_weather_data(weather_data)
                        else:
                            logger.info(
                                f"Successfully fetched Open-Meteo fallback data for {location.name}"
                            )
                    except Exception as e2:
                        logger.error(f"Both NWS and Open-Meteo failed for {location.name}: {e2}")
                        self._set_empty_weather_data(weather_data)
                else:
                    logger.info(f"Successfully fetched NWS data for {location.name}")

            except Exception as e:
                logger.warning(f"NWS API failed for {location.name}: {e}")

                # Try Open-Meteo as fallback
                logger.info(f"Trying Open-Meteo fallback for {location.name}")
                try:
                    current, forecast, hourly_forecast = await self._fetch_openmeteo_data(location)

                    weather_data.current = current
                    weather_data.forecast = forecast
                    weather_data.hourly_forecast = hourly_forecast
                    weather_data.discussion = "Forecast discussion not available from Open-Meteo."
                    weather_data.alerts = WeatherAlerts(
                        alerts=[]
                    )  # Open-Meteo doesn't provide alerts

                    logger.info(
                        f"Successfully fetched Open-Meteo fallback data for {location.name}"
                    )
                except Exception as e2:
                    logger.error(
                        f"Both NWS and Open-Meteo failed for {location.name}: "
                        f"NWS={e}, OpenMeteo={e2}"
                    )
                    self._set_empty_weather_data(weather_data)

        if weather_data.has_any_data():
            # Launch enrichment tasks in parallel
            enrichment_tasks = self._launch_enrichment_tasks(weather_data, location)
            # Await enrichment completion (which includes persisting to cache)
            await self._await_enrichments(enrichment_tasks, weather_data)

        if not weather_data.has_any_data() and self.offline_cache:
            cached = self.offline_cache.load(location)
            if cached:
                logger.info(f"Using cached weather data for {location.name}")
                return cached

        return weather_data

    async def _process_visual_crossing_alerts(
        self, alerts: WeatherAlerts, location: Location
    ) -> None:
        """Delegate Visual Crossing alert processing to the dedicated module."""
        await vc_alerts.process_visual_crossing_alerts(alerts, location)

    def _launch_enrichment_tasks(
        self, weather_data: WeatherData, location: Location
    ) -> dict[str, asyncio.Task]:
        """
        Launch enrichment tasks that can run concurrently.

        Returns a dictionary of task names to asyncio.Task objects that can be
        awaited later for progressive updates.

        Args:
        ----
            weather_data: The WeatherData object to enrich
            location: The location for enrichment

        Returns:
        -------
            Dictionary mapping enrichment names to their tasks

        """
        tasks = {}

        # Smart enrichments for auto mode
        if self.data_source == "auto":
            tasks["sunrise_sunset"] = asyncio.create_task(
                self._enrich_with_sunrise_sunset(weather_data, location)
            )
            tasks["nws_discussion"] = asyncio.create_task(
                self._enrich_with_nws_discussion(weather_data, location)
            )
            tasks["vc_alerts"] = asyncio.create_task(
                self._enrich_with_visual_crossing_alerts(weather_data, location)
            )
            tasks["vc_moon_data"] = asyncio.create_task(
                self._enrich_with_visual_crossing_moon_data(weather_data, location)
            )

        # Post-processing enrichments (always run)
        tasks["environmental"] = asyncio.create_task(
            self._populate_environmental_metrics(weather_data, location)
        )
        tasks["international_alerts"] = asyncio.create_task(
            self._merge_international_alerts(weather_data, location)
        )
        tasks["aviation"] = asyncio.create_task(
            self._enrich_with_aviation_data(weather_data, location)
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
        self._apply_trend_insights(weather_data)
        self._persist_weather_data(weather_data.location, weather_data)

    def _determine_api_choice(self, location: Location) -> str:
        """Determine which API to use for the given location."""
        # Validate data source
        valid_sources = ["auto", "nws", "openmeteo", "visualcrossing"]
        if self.data_source not in valid_sources:
            logger.warning(f"Invalid data source '{self.data_source}', defaulting to 'auto'")
            self.data_source = "auto"

        if self.data_source == "visualcrossing":
            # Check if Visual Crossing client is available
            if not self.visual_crossing_client:
                logger.warning(
                    "Visual Crossing selected but no API key provided, falling back to auto"
                )
                return "nws" if self._is_us_location(location) else "openmeteo"
            return "visualcrossing"
        if self.data_source == "openmeteo":
            return "openmeteo"
        if self.data_source == "nws":
            return "nws"
        if self.data_source == "auto":
            # Use NWS for US locations, Open-Meteo for international locations
            return "nws" if self._is_us_location(location) else "openmeteo"
        # Fallback for any unexpected cases
        logger.warning(f"Unexpected data source '{self.data_source}', defaulting to auto")
        return "nws" if self._is_us_location(location) else "openmeteo"

    def _is_us_location(self, location: Location) -> bool:
        """
        Check if location is within the United States.

        Uses country_code when available for accurate detection. Falls back to
        coordinate bounds for legacy locations, but logs a warning since this
        can misclassify Canadian border cities like Toronto.
        """
        country_code = getattr(location, "country_code", None)
        if country_code:
            return country_code.upper() == "US"

        lat = location.latitude
        lon = location.longitude

        # Without country_code, use coordinate bounds as fallback
        # Note: This can misclassify Canadian cities near the US border
        # (e.g., Toronto, Montreal, Ottawa) as US locations.

        # Continental US bounds (approximate)
        in_continental_bounds = 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0

        # Alaska bounds (51-71°N, 130-172°W)
        in_alaska_bounds = 51.0 <= lat <= 71.5 and -172.0 <= lon <= -130.0

        # Hawaii bounds (18-23°N, 154-161°W)
        in_hawaii_bounds = 18.0 <= lat <= 23.0 and -161.0 <= lon <= -154.0

        is_us = in_continental_bounds or in_alaska_bounds or in_hawaii_bounds

        if is_us and not country_code:
            # Log warning for locations without country_code in ambiguous regions
            # This helps identify locations that may need country_code to be set
            logger.debug(
                f"Location '{location.name}' ({lat:.2f}, {lon:.2f}) detected as US by "
                f"coordinates but has no country_code. If this is incorrect (e.g., Canadian "
                f"city), re-add the location to set country_code via geocoding."
            )

        return is_us

    def _set_empty_weather_data(self, weather_data: WeatherData) -> None:
        """Set empty weather data when all APIs fail."""
        weather_data.current = CurrentConditions()
        weather_data.forecast = Forecast(periods=[])
        weather_data.hourly_forecast = HourlyForecast(periods=[])
        weather_data.discussion = "Weather data not available."
        weather_data.alerts = WeatherAlerts(alerts=[])

    async def _get_nws_current_conditions(self, location: Location) -> CurrentConditions | None:
        """Delegate to the NWS client module."""
        return await nws_client.get_nws_current_conditions(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_nws_forecast_and_discussion(
        self, location: Location
    ) -> tuple[Forecast | None, str | None]:
        """Delegate to the NWS client module."""
        return await nws_client.get_nws_forecast_and_discussion(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_nws_alerts(self, location: Location) -> WeatherAlerts | None:
        """Delegate to the NWS client module."""
        return await nws_client.get_nws_alerts(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_nws_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Delegate to the NWS client module."""
        return await nws_client.get_nws_hourly_forecast(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_openmeteo_current_conditions(
        self, location: Location
    ) -> CurrentConditions | None:
        """Delegate to the Open-Meteo client module."""
        return await openmeteo_client.get_openmeteo_current_conditions(
            location, self.openmeteo_base_url, self.timeout, self._get_http_client()
        )

    async def _get_openmeteo_forecast(self, location: Location) -> Forecast | None:
        """Delegate to the Open-Meteo client module."""
        return await openmeteo_client.get_openmeteo_forecast(
            location, self.openmeteo_base_url, self.timeout, self._get_http_client()
        )

    async def _get_openmeteo_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Delegate to the Open-Meteo client module."""
        return await openmeteo_client.get_openmeteo_hourly_forecast(
            location, self.openmeteo_base_url, self.timeout, self._get_http_client()
        )

    def _parse_nws_current_conditions(self, data: dict) -> CurrentConditions:
        """Delegate to the NWS client module."""
        return nws_client.parse_nws_current_conditions(data)

    def _parse_nws_forecast(self, data: dict) -> Forecast:
        """Delegate to the NWS client module."""
        return nws_client.parse_nws_forecast(data)

    def _parse_nws_alerts(self, data: dict) -> WeatherAlerts:
        """Delegate to the NWS client module."""
        return nws_client.parse_nws_alerts(data)

    def _parse_nws_hourly_forecast(self, data: dict) -> HourlyForecast:
        """Delegate to the NWS client module."""
        return nws_client.parse_nws_hourly_forecast(data)

    def _parse_openmeteo_current_conditions(self, data: dict) -> CurrentConditions:
        """Delegate to the Open-Meteo client module."""
        return openmeteo_client.parse_openmeteo_current_conditions(data)

    def _parse_openmeteo_forecast(self, data: dict) -> Forecast:
        """Delegate to the Open-Meteo client module."""
        return openmeteo_client.parse_openmeteo_forecast(data)

    def _parse_openmeteo_hourly_forecast(self, data: dict) -> HourlyForecast:
        """Delegate to the Open-Meteo client module."""
        return openmeteo_client.parse_openmeteo_hourly_forecast(data)

    async def _augment_current_with_openmeteo(
        self,
        current: CurrentConditions | None,
        location: Location,
    ) -> CurrentConditions | None:
        """Fill missing current-condition fields using Open-Meteo data when available."""
        if current is not None and current.has_data():
            return current

        try:
            fallback = await self._get_openmeteo_current_conditions(location)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Open-Meteo current conditions fallback failed: %s", exc)
            return current

        if fallback is None:
            return current

        if current is None:
            logger.info(
                "Using Open-Meteo current conditions for %s due to missing NWS data", location.name
            )
            return fallback

        logger.info(
            "Supplementing NWS current conditions with Open-Meteo data for %s", location.name
        )
        return self._merge_current_conditions(current, fallback)

    def _merge_current_conditions(
        self,
        primary: CurrentConditions | None,
        fallback: CurrentConditions,
    ) -> CurrentConditions:
        """Merge missing fields from fallback conditions into the primary instance."""
        if primary is None:
            return fallback

        for field in [
            "temperature",
            "temperature_f",
            "temperature_c",
            "condition",
            "humidity",
            "dewpoint_f",
            "dewpoint_c",
            "wind_speed",
            "wind_speed_mph",
            "wind_speed_kph",
            "wind_direction",
            "pressure",
            "pressure_in",
            "pressure_mb",
            "feels_like_f",
            "feels_like_c",
            "visibility_miles",
            "visibility_km",
            "uv_index",
            "sunrise_time",
            "sunset_time",
            "moon_phase",
            "moonrise_time",
            "moonset_time",
            "last_updated",
        ]:
            value = getattr(primary, field, None)
            if value not in (None, ""):
                continue
            fallback_value = getattr(fallback, field, None)
            if fallback_value in (None, ""):
                continue
            setattr(primary, field, fallback_value)

        primary.__post_init__()
        return primary

    async def _enrich_with_nws_discussion(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        await enrichment.enrich_with_nws_discussion(self, weather_data, location)

    async def _enrich_with_aviation_data(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        await enrichment.enrich_with_aviation_data(self, weather_data, location)

    async def get_aviation_weather(
        self,
        station_id: str,
        *,
        include_sigmets: bool = False,
        atsu: str | None = None,
        include_cwas: bool = False,
        cwsu_id: str | None = None,
    ) -> AviationData:
        return await enrichment.get_aviation_weather(
            self,
            station_id,
            include_sigmets=include_sigmets,
            atsu=atsu,
            include_cwas=include_cwas,
            cwsu_id=cwsu_id,
        )

    async def _enrich_with_visual_crossing_alerts(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        await enrichment.enrich_with_visual_crossing_alerts(self, weather_data, location)

    async def _enrich_with_visual_crossing_moon_data(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        await enrichment.enrich_with_visual_crossing_moon_data(self, weather_data, location)

    async def _enrich_with_sunrise_sunset(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        await enrichment.enrich_with_sunrise_sunset(self, weather_data, location)

    async def _populate_environmental_metrics(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        await enrichment.populate_environmental_metrics(self, weather_data, location)

    async def _merge_international_alerts(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        await enrichment.merge_international_alerts(self, weather_data, location)

    def _apply_trend_insights(self, weather_data: WeatherData) -> None:
        trends.apply_trend_insights(
            weather_data,
            self.trend_insights_enabled,
            self.trend_hours,
            include_pressure=self.show_pressure_trend,
        )

    def _persist_weather_data(self, location: Location, weather_data: WeatherData) -> None:
        if not self.offline_cache:
            return
        if not weather_data.has_any_data():
            return
        if weather_data.stale:
            return
        try:
            self.offline_cache.store(location, weather_data)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to persist weather data cache: {exc}")

    def _maybe_generate_air_quality_alert(
        self, weather_data: WeatherData, environmental: EnvironmentalConditions
    ) -> None:
        if not self.alerts_enabled:
            return
        severity = self._air_quality_severity(environmental.air_quality_index or 0.0)
        description = (
            f"Air quality index is {environmental.air_quality_index:.0f}"
            if environmental.air_quality_index is not None
            else "Air quality threshold exceeded"
        )
        if environmental.air_quality_category:
            description += f" ({environmental.air_quality_category})"

        alert = WeatherAlert(
            title="Air Quality Alert",
            description=description,
            severity=severity,
            urgency="Expected",
            certainty="Observed",
            event="Air Quality Alert",
            headline=f"Air quality {environmental.air_quality_category or ''}".strip(),
            instruction="Consider limiting outdoor exposure and using air filtration indoors.",
            areas=[weather_data.location.name],
            source="AirQuality",
        )

        alerts = weather_data.alerts.alerts if weather_data.alerts else []
        combined: dict[str, WeatherAlert] = {alert.get_unique_id(): alert for alert in alerts}
        combined[alert.get_unique_id()] = alert
        weather_data.alerts = WeatherAlerts(alerts=list(combined.values()))

    def _air_quality_severity(self, value: float) -> str:
        if value >= 300:
            return "Extreme"
        if value >= 200:
            return "Severe"
        if value >= 150:
            return "Moderate"
        if value >= 100:
            return "Minor"
        return "Unknown"

    def _compute_temperature_trend(self, weather_data: WeatherData) -> TrendInsight | None:
        return trends.compute_temperature_trend(weather_data, self.trend_hours)

    def _compute_pressure_trend(self, weather_data: WeatherData) -> TrendInsight | None:
        return trends.compute_pressure_trend(weather_data, self.trend_hours)

    def _trend_descriptor(self, change: float, *, minor: float, strong: float) -> tuple[str, str]:
        return trends.trend_descriptor(change, minor=minor, strong=strong)

    def _period_for_hours_ahead(
        self, periods: list[HourlyForecastPeriod] | Sequence[HourlyForecastPeriod], hours_ahead: int
    ) -> HourlyForecastPeriod | None:
        return trends.period_for_hours_ahead(periods, hours_ahead)

    def _normalize_datetime(self, value: datetime | None) -> datetime | None:
        return trends.normalize_datetime(value)

    # Utility methods
    def _convert_mps_to_mph(self, mps: float | None) -> float | None:
        return parsers.convert_mps_to_mph(mps)

    def _convert_wind_speed_to_mph(
        self, value: float | None, unit_code: str | None
    ) -> float | None:
        return parsers.convert_wind_speed_to_mph(value, unit_code)

    def _convert_wind_speed_to_kph(
        self, value: float | None, unit_code: str | None
    ) -> float | None:
        return parsers.convert_wind_speed_to_kph(value, unit_code)

    def _convert_wind_speed_to_mph_and_kph(
        self, value: float | None, unit_code: str | None
    ) -> tuple[float | None, float | None]:
        return parsers.convert_wind_speed_to_mph_and_kph(value, unit_code)

    def _convert_pa_to_inches(self, pa: float | None) -> float | None:
        return parsers.convert_pa_to_inches(pa)

    def _convert_pa_to_mb(self, pa: float | None) -> float | None:
        return parsers.convert_pa_to_mb(pa)

    def _normalize_temperature(
        self, value: float | None, unit: str | None
    ) -> tuple[float | None, float | None]:
        return parsers.normalize_temperature(value, unit)

    def _normalize_pressure(
        self, value: float | None, unit: str | None
    ) -> tuple[float | None, float | None]:
        return parsers.normalize_pressure(value, unit)

    def _convert_f_to_c(self, fahrenheit: float | None) -> float | None:
        return parsers.convert_f_to_c(fahrenheit)

    def _degrees_to_cardinal(self, degrees: float | None) -> str | None:
        return parsers.degrees_to_cardinal(degrees)

    def _weather_code_to_description(self, code: int | str | None) -> str | None:
        return parsers.weather_code_to_description(code)

    def _format_date_name(self, date_str: str, index: int) -> str:
        return parsers.format_date_name(date_str, index)
