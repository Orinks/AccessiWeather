"""Core WeatherClient implementation with enrichment delegation."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import httpx

from . import (
    weather_client_nws as nws_client,
    weather_client_openmeteo as openmeteo_client,
)
from .cache import WeatherDataCache
from .models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    WeatherAlerts,
    WeatherData,
)
from .pirate_weather_client import PirateWeatherClient
from .services import EnvironmentalDataClient
from .utils.retry import APITimeoutError, retry_with_backoff
from .weather_client_auto import WeatherClientAutoMixin
from .weather_client_fetch import WeatherClientFetchMixin
from .weather_client_notification import WeatherClientNotificationMixin
from .weather_client_sources import WeatherClientSourcesMixin

logger = logging.getLogger(__name__)

MINUTELY_FAST_POLL_INTERVAL = timedelta(minutes=5)
MINUTELY_RECOMMENDED_MIN_POLL_INTERVAL = timedelta(minutes=15)
MINUTELY_ADAPTIVE_PRECIP_PROBABILITY_THRESHOLD = 30
MINUTELY_ADAPTIVE_LOOKAHEAD_HOURS = 6


def _is_unittest_mock(value: object) -> bool:
    """Return whether value is a unittest mock without importing unittest at app startup."""
    try:
        from unittest.mock import Mock
    except ImportError:  # pragma: no cover - standard library availability guard
        return False
    return isinstance(value, Mock)


class WeatherClient(
    WeatherClientSourcesMixin,
    WeatherClientAutoMixin,
    WeatherClientFetchMixin,
    WeatherClientNotificationMixin,
):
    """Simple async weather API client."""

    def __init__(
        self,
        user_agent: str = "AccessiWeather/1.0",
        data_source: str = "auto",
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
        self.data_source = data_source  # "auto", "nws", "openmeteo", "pirateweather"
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
        # Note: pirate_weather_api_key may be a LazySecureStorage object that defers
        # keyring access until first use. We avoid checking truthiness here to prevent
        # triggering the lazy load during initialization.
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
        self._latest_weather_by_location: dict[str, WeatherData] = {}
        self._last_minutely_poll_by_location: dict[str, datetime] = {}

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
        return f"{location.latitude:.4f},{location.longitude:.4f}"

    def _utcnow(self) -> datetime:
        """Return the current UTC time for poll-throttling decisions."""
        return datetime.now(UTC)

    def _remember_weather_data(self, weather_data: WeatherData) -> None:
        """Store the latest full-weather snapshot for adaptive polling decisions."""
        self._latest_weather_by_location[self._location_key(weather_data.location)] = weather_data

    def _get_latest_weather_data(self, location: Location) -> WeatherData | None:
        """Return the freshest known weather data for a location."""
        latest = self._latest_weather_by_location.get(self._location_key(location))
        if latest is not None:
            return latest
        return self.get_cached_weather(location)

    def _should_use_fast_minutely_poll(self, location: Location) -> bool:
        """Return True when the next few forecast hours suggest likely precipitation."""
        weather_data = self._get_latest_weather_data(location)
        hourly = weather_data.hourly_forecast if weather_data else None
        if not hourly or not hourly.has_data():
            return False

        now = self._utcnow()
        lookahead_deadline = now + timedelta(hours=MINUTELY_ADAPTIVE_LOOKAHEAD_HOURS)
        for period in hourly.get_next_hours(MINUTELY_ADAPTIVE_LOOKAHEAD_HOURS):
            probability = getattr(period, "precipitation_probability", None)
            start_time = getattr(period, "start_time", None)
            if probability is None or probability < MINUTELY_ADAPTIVE_PRECIP_PROBABILITY_THRESHOLD:
                continue
            if start_time is None:
                return True
            aware_start = (
                start_time.replace(tzinfo=UTC)
                if start_time.tzinfo is None
                else start_time.astimezone(UTC)
            )
            if aware_start <= lookahead_deadline:
                return True
        return False

    def _should_fetch_minutely_precipitation(self, location: Location) -> bool:
        """Throttle Pirate Weather minutely polling based on forecast precipitation risk."""
        normal_interval = timedelta(
            minutes=max(1, int(getattr(self.settings, "update_interval_minutes", 10)))
        )
        fast_polling = bool(getattr(self.settings, "minutely_precipitation_fast_polling", False))
        target_interval = max(normal_interval, MINUTELY_RECOMMENDED_MIN_POLL_INTERVAL)
        if fast_polling and self._should_use_fast_minutely_poll(location):
            target_interval = min(normal_interval, MINUTELY_FAST_POLL_INTERVAL)

        last_poll = self._last_minutely_poll_by_location.get(self._location_key(location))
        if last_poll is None:
            return True
        return self._utcnow() - last_poll >= target_interval

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
            if self._test_mode and _is_unittest_mock(client):
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
            if self._test_mode and _is_unittest_mock(current):
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
                requested_hours = self._get_hourly_hours_for_pressure_outlook()
                return await retry_with_backoff(
                    openmeteo_client.get_openmeteo_all_data_parallel,
                    location,
                    self.openmeteo_base_url,
                    self.timeout,
                    client,
                    forecast_days,
                    "best_match",
                    requested_hours,
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
        """
        Use Open-Meteo for full-range forecasts only in auto mode when forecast exceeds 7 days.

        When the user explicitly selects a specific source (e.g. 'nws'), Open-Meteo must not
        silently contribute data or appear in the attribution.  The fallback is only allowed
        in 'auto' mode where multi-source blending is expected.
        """
        normalized_source = (source or self.data_source).strip().lower()
        if normalized_source != "auto":
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
        Pre-warm forecast cache for multiple locations.

        Returns the number of locations successfully warmed.
        """
        if not locations:
            return 0

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

    def _persist_weather_data(self, location: Location, weather_data: WeatherData) -> None:
        self._remember_weather_data(weather_data)
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
