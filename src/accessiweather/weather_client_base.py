"""Core WeatherClient implementation with enrichment delegation."""

from __future__ import annotations

import asyncio
import inspect
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
from .alert_lifecycle import diff_alerts
from .cache import WeatherDataCache
from .config.source_priority import SourcePriorityConfig
from .forecast_confidence import calculate_forecast_confidence
from .models import (
    AppSettings,
    AviationData,
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    MinutelyPrecipitationForecast,
    SourceAttribution,
    SourceData,
    WeatherAlerts,
    WeatherData,
)
from .notifications.minutely_precipitation import parse_pirate_weather_minutely_block
from .pirate_weather_client import PirateWeatherApiError, PirateWeatherClient
from .services import EnvironmentalDataClient
from .units import resolve_auto_unit_system
from .utils.retry import APITimeoutError, retry_with_backoff
from .visual_crossing_client import VisualCrossingApiError, VisualCrossingClient
from .weather_client_alerts import AlertAggregator
from .weather_client_fusion import DataFusionEngine
from .weather_client_parallel import ParallelFetchCoordinator

logger = logging.getLogger(__name__)


class WeatherClient:
    """Simple async weather API client."""

    def __init__(
        self,
        user_agent: str = "AccessiWeather/1.0",
        data_source: str = "auto",
        visual_crossing_api_key: str = "",
        pirate_weather_api_key: str = "",
        avwx_api_key: str = "",
        settings: AppSettings | None = None,
        *,
        environmental_client: EnvironmentalDataClient | None = None,
        offline_cache: WeatherDataCache | None = None,
    ):
        """Initialize the instance."""
        self.user_agent = user_agent
        self.nws_base_url = "https://api.weather.gov"
        self.openmeteo_base_url = "https://api.open-meteo.com/v1"
        self.timeout = 10.0
        self.data_source = data_source  # "auto", "nws", "openmeteo", "visualcrossing"
        self.settings = settings or AppSettings()
        self._test_mode = bool(os.environ.get("PYTEST_CURRENT_TEST"))
        self.alerts_enabled = bool(self.settings.enable_alerts)
        self.trend_insights_enabled = bool(self.settings.trend_insights_enabled)
        self.trend_hours = max(1, int(self.settings.trend_hours or 24))
        self.show_pressure_trend = bool(getattr(self.settings, "show_pressure_trend", True))
        self.air_quality_enabled = bool(self.settings.air_quality_enabled)
        self.pollen_enabled = bool(self.settings.pollen_enabled)
        if self._test_mode:
            self.air_quality_enabled = False
            self.pollen_enabled = False

        self.offline_cache = offline_cache
        self._cache_purge_pending = True

        # Store the API key reference for lazy client creation
        # Note: visual_crossing_api_key / pirate_weather_api_key may be LazySecureStorage
        # objects that defer keyring access until first use. We avoid checking truthiness
        # here to prevent triggering the lazy load during initialization.
        self._visual_crossing_api_key = visual_crossing_api_key
        self._visual_crossing_client: VisualCrossingClient | None = None
        self._pirate_weather_api_key = pirate_weather_api_key
        self._pirate_weather_client: PirateWeatherClient | None = None

        # AVWX API key for international aviation weather (stored as a plain string or
        # LazySecureStorage; resolved to str on first access via avwx_api_key property).
        self._avwx_api_key = avwx_api_key

        # Secondary data providers
        self.environmental_client = environmental_client
        if (self.air_quality_enabled or self.pollen_enabled) and self.environmental_client is None:
            self.environmental_client = EnvironmentalDataClient(
                user_agent=user_agent, timeout=self.timeout
            )

        # Reusable HTTP client for performance
        self._http_client: httpx.AsyncClient | None = None

        # Track in-flight requests to deduplicate concurrent calls
        self._in_flight_requests: dict[str, asyncio.Task[WeatherData]] = {}

        # Cache of previous alerts per location key (for lifecycle diff)
        self._previous_alerts: dict[str, WeatherAlerts] = {}

    @property
    def visual_crossing_api_key(self) -> str:
        """
        Get the Visual Crossing API key, resolving lazy accessor if needed.

        The API key may be a LazySecureStorage object that defers keyring access.
        This property resolves the value when accessed.
        """
        key = self._visual_crossing_api_key
        if key is None or key == "":
            return ""
        # Handle LazySecureStorage by converting to string (triggers lazy load)
        # Note: str() calls __str__ on LazySecureStorage which returns the value
        return str(key)

    @property
    def visual_crossing_client(self) -> VisualCrossingClient | None:
        """
        Get the Visual Crossing client, creating it lazily on first access.

        This defers keyring access for the API key until the client is actually needed,
        improving startup performance.
        """
        if self._visual_crossing_client is None:
            # Now we check the API key truthiness, which may trigger lazy keyring load
            api_key = self.visual_crossing_api_key
            if api_key:
                self._visual_crossing_client = VisualCrossingClient(api_key, self.user_agent)
                logger.debug("Visual Crossing client created lazily")
        return self._visual_crossing_client

    @visual_crossing_client.setter
    def visual_crossing_client(self, value: VisualCrossingClient | None) -> None:
        """Allow direct assignment for backward compatibility and testing."""
        self._visual_crossing_client = value

    @property
    def pirate_weather_api_key(self) -> str:
        """Get the Pirate Weather API key, resolving lazy accessor if needed."""
        key = self._pirate_weather_api_key
        if key is None or key == "":
            return ""
        return str(key)

    @property
    def pirate_weather_client(self) -> PirateWeatherClient | None:
        """Get the Pirate Weather client, creating it lazily on first access."""
        if self._pirate_weather_client is None:
            api_key = self.pirate_weather_api_key
            if api_key:
                self._pirate_weather_client = PirateWeatherClient(api_key, self.user_agent)
                logger.debug("Pirate Weather client created lazily")
        return self._pirate_weather_client

    @pirate_weather_client.setter
    def pirate_weather_client(self, value: PirateWeatherClient | None) -> None:
        """Allow direct assignment for backward compatibility and testing."""
        self._pirate_weather_client = value

    @property
    def avwx_api_key(self) -> str:
        """Get the AVWX API key, resolving lazy accessor if needed."""
        key = self._avwx_api_key
        if key is None or key == "":
            return ""
        return str(key)

    def _location_key(self, location: Location) -> str:
        """Generate a unique key for a location to track in-flight requests."""
        return f"{location.name}:{location.latitude:.4f},{location.longitude:.4f}"

    async def _fetch_nws_cancel_references(self) -> set[str]:
        """Fetch recent NWS cancel references for verifying genuine cancellations."""
        return await nws_client.fetch_nws_cancel_references(
            self.nws_base_url,
            self.user_agent,
            self.timeout,
            lookback_minutes=15,
            client=self._get_http_client(),
        )

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
            # Use explicit test mode flag instead of brittle isinstance check
            # The _test_mode flag is set in __init__ based on PYTEST_CURRENT_TEST env var
            if self._test_mode and Mock is not None and isinstance(client, Mock):
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

            # Use explicit test mode flag instead of brittle isinstance check
            if self._test_mode and Mock is not None and isinstance(current, Mock):
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
        datetime | None,
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

        # Use explicit test mode flag instead of brittle isinstance check
        if not self._methods_overridden(method_names) and not self._test_mode:
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
                return None, None, None, None, None, None

        current, forecast_result, alerts, hourly_forecast = await asyncio.gather(
            self._get_nws_current_conditions(location),
            self._get_nws_forecast_and_discussion(location),
            self._get_nws_alerts(location),
            self._get_nws_hourly_forecast(location),
        )

        forecast: Forecast | None
        discussion: str | None
        if isinstance(forecast_result, tuple) and len(forecast_result) == 3:
            forecast, discussion, discussion_issuance_time = forecast_result
        else:
            forecast, discussion, discussion_issuance_time = (None, None, None)

        return current, forecast, discussion, discussion_issuance_time, alerts, hourly_forecast

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

        # Use explicit test mode flag instead of brittle isinstance check
        if not self._methods_overridden(method_names) and not self._test_mode:
            # Use retry wrapper for the parallel fetch
            try:
                forecast_days = self._get_forecast_days_for_source(location, source="openmeteo")
                return await retry_with_backoff(
                    openmeteo_client.get_openmeteo_all_data_parallel,
                    location,
                    self.openmeteo_base_url,
                    self.timeout,
                    client,
                    forecast_days,
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

    def _should_use_openmeteo_for_extended_forecast(
        self, location: Location, source: str | None = None
    ) -> bool:
        """Use Open-Meteo for full-range forecasts when NWS-style sources exceed 7 days."""
        normalized_source = (source or self.data_source).strip().lower()
        if normalized_source not in {"nws", "pw", "auto"}:
            return False
        if not self._is_us_location(location):
            return False
        return self._get_forecast_days_for_source(location, "openmeteo") > 7

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
            # Fetch fresh data (bypassing cache), skip notifications for non-selected locations
            weather_data = await self.get_weather_data(
                location, force_refresh=True, skip_notifications=True
            )

            if weather_data.has_any_data():
                logger.info(f"✓ Cache pre-warmed successfully for {location.name}")
                return True

            logger.warning(f"Cache pre-warm failed: no data returned for {location.name}")
            return False

        except Exception as exc:
            logger.error(f"Cache pre-warm failed for {location.name}: {exc}")
            return False

    async def pre_warm_batch(self, locations: list[Location]) -> int:
        """
        Pre-warm forecast cache for multiple locations using a single batch API call.

        Uses Visual Crossing batch endpoint when available, falls back to
        individual pre_warm_cache calls otherwise.

        Returns the number of locations successfully warmed.
        """
        if not locations:
            return 0

        # Try batch via VC if client is configured
        vc = self.visual_crossing_client
        if vc and len(locations) > 1:
            try:
                batch_results = await vc.get_forecast_batch(locations)
                if batch_results:
                    logger.info("Batch pre-warm: got %d forecasts from VC", len(batch_results))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Batch forecast failed, falling back to individual: %s", exc)

        # Still do full individual pre-warm for each location (current, alerts, etc.)
        warmed = 0
        for loc in locations:
            if await self.pre_warm_cache(loc):
                warmed += 1
        return warmed

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
        self, location: Location, force_refresh: bool = False, skip_notifications: bool = False
    ) -> WeatherData:
        """
        Get complete weather data for a location.

        Args:
            location: Location to fetch weather for
            force_refresh: If True, bypass cache and force fresh API call
            skip_notifications: If True, skip triggering alert notifications (used for pre-warming)

        """
        logger.info(f"Fetching weather data for {location.name}")

        # Lazy cache purge on first data fetch (deferred from __init__ for faster startup)
        if self._cache_purge_pending and self.offline_cache:
            self._cache_purge_pending = False
            try:
                self.offline_cache.purge_expired()
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Weather cache purge failed: {exc}")

        # Handle force_refresh by temporarily clearing cache for this location
        if force_refresh and self.offline_cache:
            logger.debug(f"Force refresh requested, clearing cache for {location.name}")
            self.offline_cache.invalidate(location)

        # Use deduplication for concurrent requests
        return await self._fetch_weather_data_with_dedup(
            location, force_refresh, skip_notifications
        )

    async def get_notification_event_data(self, location: Location) -> WeatherData:
        """Fetch only lightweight data needed for alert/discussion/risk notifications."""
        logger.info("Fetching notification event data for %s", location.name)
        weather_data = WeatherData(location=location)

        try:
            if self._is_us_location(location):
                # Use discussion-only fetch so a forecast API failure can never
                # silently suppress AFD update notifications.
                discussion_task = asyncio.create_task(self._get_nws_discussion_only(location))
                alerts_task = asyncio.create_task(self._get_nws_alerts(location))
                discussion, discussion_issuance_time = await discussion_task
                alerts = await alerts_task
                logger.debug(
                    "get_notification_event_data: discussion=%s issuance=%s alerts=%s",
                    "ok" if discussion else "None",
                    discussion_issuance_time,
                    len(alerts.alerts) if alerts and alerts.alerts else 0,
                )
                weather_data.discussion = discussion
                weather_data.discussion_issuance_time = discussion_issuance_time
                weather_data.alerts = alerts or WeatherAlerts(alerts=[])
            elif self.visual_crossing_client:
                current_task = asyncio.create_task(
                    self.visual_crossing_client.get_current_conditions(location)
                )
                alerts_task = asyncio.create_task(self.visual_crossing_client.get_alerts(location))
                weather_data.current = await current_task
                weather_data.alerts = await alerts_task or WeatherAlerts(alerts=[])
            elif self.pirate_weather_client:
                current_task = asyncio.create_task(
                    self.pirate_weather_client.get_current_conditions(location)
                )
                alerts_task = asyncio.create_task(self.pirate_weather_client.get_alerts(location))
                weather_data.current = await current_task
                weather_data.alerts = await alerts_task or WeatherAlerts(alerts=[])
            else:
                weather_data.alerts = WeatherAlerts(alerts=[])

            # Only fetch PW minutely in the lightweight poll if the user actually
            # wants precipitation start/stop notifications AND a PW client exists.
            # This avoids an extra API call every 60s for users who don't use it.
            if self.pirate_weather_client and self.settings:
                _want_start = getattr(self.settings, "notify_minutely_precipitation_start", False)
                _want_stop = getattr(self.settings, "notify_minutely_precipitation_stop", False)
                if _want_start or _want_stop:
                    weather_data.minutely_precipitation = await self._get_pirate_weather_minutely(
                        location
                    )

            loc_key = self._location_key(location)
            previous_alerts = self._previous_alerts.get(loc_key)
            _cancel_refs = await self._fetch_nws_cancel_references()
            weather_data.alert_lifecycle_diff = diff_alerts(
                previous_alerts, weather_data.alerts, confirmed_cancel_ids=_cancel_refs
            )
            if weather_data.alerts is not None:
                self._previous_alerts[loc_key] = weather_data.alerts
        except Exception as exc:
            logger.error("Failed to fetch notification event data for %s: %s", location.name, exc)
            weather_data.alerts = weather_data.alerts or WeatherAlerts(alerts=[])

        return weather_data

    async def _get_pirate_weather_minutely(
        self, location: Location
    ) -> MinutelyPrecipitationForecast | None:
        """Fetch Pirate Weather minutely precipitation when a client is configured."""
        client = getattr(self, "pirate_weather_client", None)
        if client is None:
            return None

        for method_name in ("get_minutely_forecast", "get_forecast"):
            method = getattr(client, method_name, None)
            if not callable(method):
                continue
            try:
                result = method(location)
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, dict):
                    return parse_pirate_weather_minutely_block(result)
            except TypeError:
                logger.debug(
                    "Pirate Weather client method %s has an unsupported signature", method_name
                )
            except Exception as exc:
                logger.debug("Pirate Weather minutely fetch via %s failed: %s", method_name, exc)
                return None

        return None

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
            "visualcrossing": "Visual Crossing",
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

        elif api_choice == "visualcrossing":
            # Use Visual Crossing API
            try:
                if not self.visual_crossing_client:
                    raise VisualCrossingApiError("Visual Crossing API key not configured")

                # Parallelize API calls for better performance
                current, forecast, hourly_forecast, alerts = await asyncio.gather(
                    self.visual_crossing_client.get_current_conditions(location),
                    self.visual_crossing_client.get_forecast(
                        location,
                        days=self._get_forecast_days_for_source(location, source="visualcrossing"),
                    ),
                    self.visual_crossing_client.get_hourly_forecast(location),
                    self.visual_crossing_client.get_alerts(location),
                )

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = "Forecast discussion not available from Visual Crossing."
                weather_data.discussion_issuance_time = None
                weather_data.alerts = alerts

                # Compute alert lifecycle diff for VC single-source path
                _vc_loc_key = self._location_key(location)
                _vc_prev = self._previous_alerts.get(_vc_loc_key)
                weather_data.alert_lifecycle_diff = diff_alerts(_vc_prev, alerts)
                if alerts is not None:
                    self._previous_alerts[_vc_loc_key] = alerts

                # Set source attribution for single-source mode
                weather_data.source_attribution = SourceAttribution(
                    contributing_sources={"visualcrossing"},
                )

                # Process alerts for notifications if we have any (unless skipped for pre-warming)
                if not skip_notifications and alerts and alerts.has_alerts():
                    logger.info(
                        f"Processing {len(alerts.alerts)} Visual Crossing alerts for notifications"
                    )
                    await self._process_visual_crossing_alerts(alerts, location)

                logger.info(f"Successfully fetched Visual Crossing data for {location.name}")

            except VisualCrossingApiError as e:
                logger.error(f"Visual Crossing API failed for {location.name}: {e}")
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
            enrichment_tasks = self._launch_enrichment_tasks(weather_data, location)
            # Await enrichment completion (which includes persisting to cache)
            await self._await_enrichments(enrichment_tasks, weather_data)

        if not weather_data.has_any_data() and self.offline_cache:
            cached = self.offline_cache.load(location)
            if cached:
                logger.info(f"Using cached weather data for {location.name}")
                return cached

        return weather_data

    async def _fetch_smart_auto_source(
        self, location: Location, skip_notifications: bool = False
    ) -> WeatherData:
        """
        Fetch weather data from all sources in parallel and merge results.

        This implements the smart auto source feature that:
        1. Fetches from all available sources concurrently
        2. Merges data using configurable priorities
        3. Deduplicates alerts from multiple sources
        4. Tracks source attribution for transparency

        Args:
            location: The location to fetch weather for
            skip_notifications: If True, skip triggering alert notifications

        Returns:
            Merged WeatherData from all successful sources

        """
        logger.info(f"Using smart auto source for {location.name}")

        # Initialize components with user's source priority settings
        us_priority = getattr(
            self.settings,
            "source_priority_us",
            ["nws", "openmeteo", "visualcrossing", "pirateweather"],
        )
        intl_priority = getattr(
            self.settings,
            "source_priority_international",
            ["openmeteo", "pirateweather", "visualcrossing"],
        )
        config = SourcePriorityConfig(us_default=us_priority, international_default=intl_priority)
        parallel_timeout = getattr(self.settings, "parallel_fetch_timeout", 5.0)
        coordinator = ParallelFetchCoordinator(timeout=parallel_timeout)
        fusion_engine = DataFusionEngine(config)
        alert_aggregator = AlertAggregator()

        # Prepare fetch coroutines for available sources
        is_us = self._is_us_location(location)

        # Always fetch from Open-Meteo (works globally)
        async def fetch_openmeteo():
            current, forecast, hourly = await self._fetch_openmeteo_data(location)
            return (current, forecast, hourly)

        # Fetch from NWS for US locations
        async def fetch_nws():
            (
                current,
                forecast,
                discussion,
                discussion_time,
                alerts,
                hourly,
            ) = await self._fetch_nws_data(location)
            return (current, forecast, hourly, alerts)

        # Fetch from Visual Crossing if configured
        async def fetch_vc():
            if not self.visual_crossing_client:
                return (None, None, None, None)
            current = await self.visual_crossing_client.get_current_conditions(location)
            forecast = await self.visual_crossing_client.get_forecast(
                location,
                days=self._get_forecast_days_for_source(location, source="visualcrossing"),
            )
            hourly = await self.visual_crossing_client.get_hourly_forecast(location)
            alerts = await self.visual_crossing_client.get_alerts(location)
            return (current, forecast, hourly, alerts)

        # Fetch from Pirate Weather if configured
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

        # Fetch from all sources in parallel
        source_results = await coordinator.fetch_all(
            location=location,
            fetch_nws=fetch_nws() if is_us else None,
            fetch_openmeteo=fetch_openmeteo(),
            fetch_visualcrossing=fetch_vc() if self.visual_crossing_client else None,
            fetch_pirateweather=fetch_pw() if self.pirate_weather_api_key else None,
        )

        # Check if all sources failed
        successful_sources = [s for s in source_results if s.success]
        if not successful_sources:
            logger.warning(f"All sources failed for {location.name}, checking cache")
            return self._handle_all_sources_failed(location, source_results)

        # Merge current conditions
        merged_current, current_attribution = fusion_engine.merge_current_conditions(
            source_results, location
        )

        # Merge forecasts
        requested_days = getattr(self.settings, "forecast_duration_days", 7)
        merged_forecast, forecast_attribution = fusion_engine.merge_forecasts(
            source_results, location, requested_days=requested_days
        )

        # Merge hourly forecasts
        merged_hourly, hourly_attribution = fusion_engine.merge_hourly_forecasts(
            source_results, location
        )

        merged_minutely = None
        if self.pirate_weather_api_key:
            merged_minutely = await self._get_pirate_weather_minutely(location)

        # Check if we got any actual data
        has_any_data = (
            (merged_current is not None and merged_current.has_data())
            or (merged_forecast is not None and merged_forecast.has_data())
            or (merged_hourly is not None and merged_hourly.has_data())
        )

        if not has_any_data:
            # All sources returned empty data, treat as failure
            logger.warning(f"All sources returned empty data for {location.name}")
            return self._handle_all_sources_failed(location, source_results)

        # Aggregate alerts - for US locations, use only NWS (authoritative source)
        # Visual Crossing mirrors NWS alerts but lacks severity/urgency metadata
        nws_alerts = None
        vc_alerts_data = None
        pw_alerts_data = None
        for source in source_results:
            if source.source == "nws" and source.alerts:
                nws_alerts = source.alerts
            elif source.source == "visualcrossing" and source.alerts:
                vc_alerts_data = source.alerts
            elif source.source == "pirateweather" and source.alerts:
                pw_alerts_data = source.alerts

        # For US locations, skip VC/PW alerts to avoid duplicates with missing metadata
        if is_us:
            merged_alerts = alert_aggregator.aggregate_alerts(nws_alerts, None)
        else:
            # Use whichever non-NWS source has alerts (PW preferred over VC when both present)
            non_nws_alerts = pw_alerts_data or vc_alerts_data
            merged_alerts = alert_aggregator.aggregate_alerts(nws_alerts, non_nws_alerts)

        # Compute alert lifecycle diff (compare against previous fetch for this location)
        _loc_key = self._location_key(location)
        _prev_alerts = self._previous_alerts.get(_loc_key)
        _cancel_refs = await self._fetch_nws_cancel_references()
        _alert_diff = diff_alerts(_prev_alerts, merged_alerts, confirmed_cancel_ids=_cancel_refs)
        self._previous_alerts[_loc_key] = merged_alerts

        # Build source attribution
        attribution = SourceAttribution(
            field_sources={
                **current_attribution.field_sources,
                **forecast_attribution,
                **hourly_attribution,
            },
            conflicts=current_attribution.conflicts,
            contributing_sources=(
                current_attribution.contributing_sources
                | set(forecast_attribution.values())
                | set(hourly_attribution.values())
            ),
            failed_sources=current_attribution.failed_sources,
        )

        # Track incomplete sections
        incomplete_sections: set[str] = set()
        if merged_current is None:
            incomplete_sections.add("current")
        if merged_forecast is None:
            incomplete_sections.add("forecast")
        if merged_hourly is None:
            incomplete_sections.add("hourly_forecast")

        # Set appropriate discussion message based on location
        if is_us:
            discussion = "Forecast discussion available from NWS for US locations."
            discussion_issuance_time = None  # Will be populated by enrichment
        else:
            discussion = "Forecast discussion not available from Open-Meteo."
            discussion_issuance_time = None

        # Compute cross-source forecast confidence
        confidence = calculate_forecast_confidence(source_results)

        # Create the merged WeatherData
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

        # Run enrichment tasks
        if weather_data.has_any_data():
            enrichment_tasks = self._launch_enrichment_tasks(
                weather_data, location, skip_notifications
            )
            await self._await_enrichments(enrichment_tasks, weather_data)

        # Cache the result
        if weather_data.has_any_data() and self.offline_cache:
            self._persist_weather_data(location, weather_data)

        logger.info(
            f"Smart auto source completed for {location.name}: "
            f"{len(successful_sources)} sources succeeded"
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

    async def _process_visual_crossing_alerts(
        self, alerts: WeatherAlerts, location: Location
    ) -> None:
        """Delegate Visual Crossing alert processing to the dedicated module."""
        await vc_alerts.process_visual_crossing_alerts(alerts, location)

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
            tasks["vc_alerts"] = asyncio.create_task(
                enrichment.enrich_with_visual_crossing_alerts(
                    self, weather_data, location, skip_notifications
                )
            )
            tasks["vc_moon_data"] = asyncio.create_task(
                enrichment.enrich_with_visual_crossing_moon_data(self, weather_data, location)
            )

        if self.trend_insights_enabled and not weather_data.daily_history:
            tasks["vc_history"] = asyncio.create_task(
                self._enrich_with_visual_crossing_history(weather_data, location)
            )

        # Post-processing enrichments (always run)
        tasks["environmental"] = asyncio.create_task(
            enrichment.populate_environmental_metrics(self, weather_data, location)
        )
        tasks["aviation"] = asyncio.create_task(
            enrichment.enrich_with_aviation_data(self, weather_data, location)
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

    def _determine_api_choice(self, location: Location) -> str:
        """Determine which API to use for the given location."""
        # Validate data source
        valid_sources = ["auto", "nws", "openmeteo", "visualcrossing", "pirateweather"]
        if self.data_source not in valid_sources:
            logger.warning(f"Invalid data source '{self.data_source}', defaulting to 'auto'")
            self.data_source = "auto"

        if self.data_source == "pirateweather":
            if not self.pirate_weather_client:
                logger.warning(
                    "Pirate Weather selected but no API key provided, falling back to auto"
                )
                return "nws" if self._is_us_location(location) else "openmeteo"
            return "pirateweather"
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

    @staticmethod
    def _location_key(location: Location) -> str:
        """Return a stable string key for a location (used for alert caching)."""
        return f"{location.latitude:.4f},{location.longitude:.4f}"

    def _resolve_pirate_weather_units(self, location: Location) -> str:
        """Resolve the Pirate Weather unit bundle for the given location."""
        preference = (getattr(self.settings, "temperature_unit", "both") or "both").strip().lower()
        if preference == "auto":
            unit_system = resolve_auto_unit_system(location)
            return "uk" if unit_system.value == "uk" else unit_system.value
        if preference in {"c", "celsius"}:
            return "ca"
        return "us"

    def _pirate_weather_client_for_location(self, location: Location) -> PirateWeatherClient | None:
        """Return a Pirate Weather client configured for the location's effective unit system."""
        api_key = self.pirate_weather_api_key
        if not api_key:
            return None

        units = self._resolve_pirate_weather_units(location)
        client = self._pirate_weather_client
        if client is None or client.units != units:
            client = PirateWeatherClient(api_key, self.user_agent, units=units)
            self._pirate_weather_client = client
        return client

    def _is_us_location(self, location: Location) -> bool:
        """
        Check if location is within the United States.

        Uses country_code when available for accurate detection. Falls back to
        coordinate bounds only for clear-cut cases. For ambiguous regions (near US-Canada
        border), requires country_code to be set - otherwise returns False to avoid
        misclassifying Canadian cities like Toronto, Montreal, Ottawa as US locations.
        """
        country_code = getattr(location, "country_code", None)
        if country_code:
            return country_code.upper() == "US"

        lat = location.latitude
        lon = location.longitude

        # Continental US bounds (approximate)
        in_continental_bounds = 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0

        # Alaska bounds (51-71°N, 130-172°W)
        in_alaska_bounds = 51.0 <= lat <= 71.5 and -172.0 <= lon <= -130.0

        # Hawaii bounds (18-23°N, 154-161°W)
        in_hawaii_bounds = 18.0 <= lat <= 23.0 and -161.0 <= lon <= -154.0

        # For clear-cut cases (far from borders), coordinate bounds are reliable
        # - Hawaii (obvious island)
        # - Alaska (far northwest, separated from Canada)
        # - Deep in continental US (away from Canadian/Mexican borders)
        if in_hawaii_bounds or in_alaska_bounds:
            return True

        # For continental US, use both lat/lon to identify clearly US vs ambiguous zones
        if in_continental_bounds:
            # Canadian border cities (Toronto ~43°N/-79°, Montreal ~45.5°N/-73°, Ottawa ~45.4°N/-75°)
            # are in the eastern half of the continent (east of ~-95° longitude)
            # US Pacific Northwest (Seattle ~47.6°N/-122°, Portland ~45.5°N/-122°) is further west
            # Use lon < -95 as a proxy for "eastern region where Canadian cities cluster"
            if lat >= 43.0 and lon > -95.0 and lon < -70.0:
                # Eastern region near Canadian border - require country_code for accurate detection
                # This catches Canadian cities while allowing US Pacific Northwest
                logger.debug(
                    f"Location '{location.name}' ({lat:.2f}, {lon:.2f}) is in eastern "
                    f"North America near Canadian border but has no country_code. "
                    f"To ensure correct detection, re-add the location to set country_code via geocoding."
                )
                return False
            return True

        # Outside all US bounds - definitely not US
        return False

    def _set_empty_weather_data(self, weather_data: WeatherData) -> None:
        """Set empty weather data when all APIs fail."""
        weather_data.current = CurrentConditions()
        weather_data.forecast = Forecast(periods=[])
        weather_data.hourly_forecast = HourlyForecast(periods=[])
        weather_data.discussion = "Weather data not available."
        weather_data.discussion_issuance_time = None
        weather_data.alerts = WeatherAlerts(alerts=[])

    async def _get_nws_current_conditions(self, location: Location) -> CurrentConditions | None:
        """Delegate to the NWS client module."""
        return await nws_client.get_nws_current_conditions(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_nws_forecast_and_discussion(
        self, location: Location
    ) -> tuple[Forecast | None, str | None, datetime | None]:
        """Delegate to the NWS client module."""
        return await nws_client.get_nws_forecast_and_discussion(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_nws_discussion_only(
        self, location: Location
    ) -> tuple[str | None, datetime | None]:
        """Fetch only the NWS AFD discussion (no forecast). Used by the notification path."""
        return await nws_client.get_nws_discussion_only(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_nws_alerts(self, location: Location) -> WeatherAlerts | None:
        """Delegate to the NWS client module."""
        alert_radius_type = getattr(self.settings, "alert_radius_type", "county")
        return await nws_client.get_nws_alerts(
            location,
            self.nws_base_url,
            self.user_agent,
            self.timeout,
            self._get_http_client(),
            alert_radius_type=alert_radius_type,
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
            location,
            self.openmeteo_base_url,
            self.timeout,
            self._get_http_client(),
            days=self._get_forecast_days_for_source(location, source="openmeteo"),
        )

    def _get_forecast_days_for_source(self, location: Location, source: str) -> int:
        """
        Return configured forecast days with location/source caps.

        US locations are capped at 7 days to align with NWS limitations.
        Other sources are capped by their API limits.
        """
        configured = getattr(self.settings, "forecast_duration_days", 7)
        if not isinstance(configured, int):
            configured = 7
        configured = max(3, min(configured, 16))

        source_limits = {
            "openmeteo": 16,
            "visualcrossing": 15,
            "pirateweather": 8,
            "nws": 7,
        }
        return min(configured, source_limits.get(source, 16))

    async def _get_openmeteo_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Delegate to the Open-Meteo client module."""
        return await openmeteo_client.get_openmeteo_hourly_forecast(
            location, self.openmeteo_base_url, self.timeout, self._get_http_client()
        )

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
            # Strip model-derived snow depth — Open-Meteo uses ERA5/GFS which is
            # notoriously inaccurate for snowpack. Only station observations are reliable.
            fallback.snow_depth_in = None  # pragma: no cover
            fallback.snow_depth_cm = None  # pragma: no cover
            return fallback

        logger.info(
            "Supplementing NWS current conditions with Open-Meteo data for %s", location.name
        )
        return parsers.merge_current_conditions(current, fallback)

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

    async def _enrich_with_visual_crossing_history(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        """Enrich weather data with historical weather from Visual Crossing for trends."""
        if not self.visual_crossing_client:
            return

        try:
            # We want yesterday's data to compare
            from datetime import timedelta

            end_date = datetime.now() - timedelta(days=1)
            start_date = end_date  # Just one day

            logger.debug("Fetching historical data from Visual Crossing for %s", location.name)
            history = await self.visual_crossing_client.get_history(location, start_date, end_date)

            if history and history.periods:
                weather_data.daily_history = history.periods
                logger.info(
                    "Updated weather history from Visual Crossing (fetched %d periods)",
                    len(history.periods),
                )

        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch history from Visual Crossing: %s", exc)

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
