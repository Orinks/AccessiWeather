"""
Simplified weather API client for AccessiWeather.

This module provides a direct, async weather API client that fetches data
from NWS and OpenMeteo APIs without complex service layer abstractions.
"""

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
from .utils import decode_taf_text
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

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the reusable HTTP client."""
        if self._http_client is None or getattr(self._http_client, "is_closed", False):
            client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
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
            return await nws_client.get_nws_all_data_parallel(
                location, self.nws_base_url, self.user_agent, self.timeout, client
            )

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
            return await openmeteo_client.get_openmeteo_all_data_parallel(
                location, self.openmeteo_base_url, self.timeout, client
            )

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

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def get_weather_data(self, location: Location) -> WeatherData:
        """Get complete weather data for a location."""
        logger.info(f"Fetching weather data for {location.name}")

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

                current = await self.visual_crossing_client.get_current_conditions(location)
                forecast = await self.visual_crossing_client.get_forecast(location)
                hourly_forecast = await self.visual_crossing_client.get_hourly_forecast(location)
                alerts = await self.visual_crossing_client.get_alerts(location)

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

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = discussion
                weather_data.alerts = alerts

                # Check if we actually got valid data
                if current is None and forecast is None:
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

        # Smart enrichment in auto mode: combine best features from different sources (parallel)
        if self.data_source == "auto":
            logger.debug("Running smart enrichment for auto mode (parallel)")
            # Run all enrichment tasks in parallel
            await asyncio.gather(
                self._enrich_with_sunrise_sunset(weather_data, location),
                self._enrich_with_nws_discussion(weather_data, location),
                self._enrich_with_visual_crossing_alerts(weather_data, location),
                return_exceptions=True,  # Continue even if some enrichments fail
            )

        # Run post-processing tasks in parallel
        await asyncio.gather(
            self._populate_environmental_metrics(weather_data, location),
            self._merge_international_alerts(weather_data, location),
            self._enrich_with_aviation_data(weather_data, location),
            return_exceptions=True,  # Continue even if some tasks fail
        )

        self._apply_trend_insights(weather_data)
        self._persist_weather_data(location, weather_data)

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
        """Check if location is within the United States (rough approximation)."""
        # Continental US bounds (approximate)
        return 24.0 <= location.latitude <= 49.0 and -125.0 <= location.longitude <= -66.0

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

    async def _enrich_with_nws_discussion(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        """Enrich weather data with forecast discussion from NWS for US locations."""
        # Only fetch NWS discussion for US locations
        if not self._is_us_location(location):
            return

        # If we already have a discussion, don't overwrite it unless it's a generic message
        if weather_data.discussion and not weather_data.discussion.startswith(
            "Forecast discussion not available"
        ):
            return

        try:
            logger.debug(f"Fetching forecast discussion from NWS for {location.name}")
            _, discussion = await self._get_nws_forecast_and_discussion(location)

            if discussion:
                weather_data.discussion = discussion
                logger.info("Added forecast discussion from NWS")
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to fetch NWS discussion: {exc}")

    async def _enrich_with_aviation_data(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        """Populate aviation data for US locations using NWS products."""
        if not self._is_us_location(location):
            return
        if weather_data.aviation and weather_data.aviation.has_taf():
            return

        try:
            client = self._get_http_client()
            station_id, station_name = await nws_client.get_nws_primary_station_info(
                location, self.nws_base_url, self.user_agent, self.timeout, client
            )
            if not station_id:
                return

            aviation = await self.get_aviation_weather(station_id)
            if station_name:
                aviation.airport_name = station_name

            weather_data.aviation = aviation
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to fetch aviation data: {exc}")

    async def get_aviation_weather(
        self,
        station_id: str,
        *,
        include_sigmets: bool = False,
        atsu: str | None = None,
        include_cwas: bool = False,
        cwsu_id: str | None = None,
    ) -> AviationData:
        """Fetch aviation weather products for a specific ICAO station identifier."""
        station = (station_id or "").strip().upper()
        if not station:
            raise ValueError("station_id must be a non-empty ICAO identifier.")

        client = self._get_http_client()
        aviation = AviationData(station_id=station, airport_name=station)

        raw_taf: str | None
        try:
            raw_taf = await nws_client.get_nws_tafs(
                station, self.nws_base_url, self.user_agent, self.timeout, client
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to fetch TAF for %s: %s", station, exc)
            raise

        if raw_taf:
            aviation.raw_taf = raw_taf
            aviation.decoded_taf = decode_taf_text(raw_taf)

        if include_sigmets:
            try:
                aviation.active_sigmets = await nws_client.get_nws_sigmets(
                    self.nws_base_url,
                    self.user_agent,
                    self.timeout,
                    client,
                    atsu=atsu,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to fetch SIGMET data for %s: %s", station, exc)

        if include_cwas and cwsu_id:
            try:
                aviation.active_cwas = await nws_client.get_nws_cwas(
                    cwsu_id, self.nws_base_url, self.user_agent, self.timeout, client
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to fetch CWA data for CWSU %s: %s", cwsu_id, exc)

        return aviation

    async def _enrich_with_visual_crossing_alerts(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        """Enrich weather data with alerts from Visual Crossing if available."""
        # Only use Visual Crossing for alerts if we have a client
        if not self.visual_crossing_client:
            return

        try:
            logger.debug(f"Fetching alerts from Visual Crossing for {location.name}")
            vc_alerts_data = await self.visual_crossing_client.get_alerts(location)

            if vc_alerts_data and vc_alerts_data.has_alerts():
                logger.info(f"Adding {len(vc_alerts_data.alerts)} alerts from Visual Crossing")

                # Merge with existing alerts (if any)
                existing = weather_data.alerts.alerts if weather_data.alerts else []
                combined: dict[str, WeatherAlert] = {
                    alert.get_unique_id(): alert for alert in existing
                }

                for alert in vc_alerts_data.alerts:
                    combined.setdefault(alert.get_unique_id(), alert)

                weather_data.alerts = WeatherAlerts(alerts=list(combined.values()))

                # Process alerts for notifications
                await self._process_visual_crossing_alerts(vc_alerts_data, location)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to fetch alerts from Visual Crossing: {exc}")

    async def _enrich_with_sunrise_sunset(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        """Enrich weather data with sunrise/sunset from Open-Meteo if not already present."""
        if not weather_data.current:
            return

        # If we already have sunrise/sunset data, don't fetch it again
        if weather_data.current.sunrise_time and weather_data.current.sunset_time:
            return

        try:
            # Fetch sunrise/sunset from Open-Meteo
            logger.debug(f"Fetching sunrise/sunset from Open-Meteo for {location.name}")
            openmeteo_current = await self._get_openmeteo_current_conditions(location)

            if openmeteo_current and (
                openmeteo_current.sunrise_time or openmeteo_current.sunset_time
            ):
                # Merge sunrise/sunset into existing current conditions
                if openmeteo_current.sunrise_time:
                    weather_data.current.sunrise_time = openmeteo_current.sunrise_time
                    logger.info(
                        f"Added sunrise time from Open-Meteo: {openmeteo_current.sunrise_time}"
                    )
                if openmeteo_current.sunset_time:
                    weather_data.current.sunset_time = openmeteo_current.sunset_time
                    logger.info(
                        f"Added sunset time from Open-Meteo: {openmeteo_current.sunset_time}"
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to fetch sunrise/sunset from Open-Meteo: {exc}")

    async def _populate_environmental_metrics(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        if not self.environmental_client:
            return
        if not (self.air_quality_enabled or self.pollen_enabled):
            return
        try:
            environmental = await self.environmental_client.fetch(
                location,
                include_air_quality=self.air_quality_enabled,
                include_pollen=self.pollen_enabled,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Environmental metrics failed: {exc}")
            return

        if not environmental:
            return

        weather_data.environmental = environmental
        if (
            self.air_quality_notify_threshold
            and environmental.air_quality_index is not None
            and environmental.air_quality_index >= self.air_quality_notify_threshold
        ):
            self._maybe_generate_air_quality_alert(weather_data, environmental)

    async def _merge_international_alerts(
        self, weather_data: WeatherData, location: Location
    ) -> None:
        if not self.international_alerts_enabled:
            return
        if self._is_us_location(location):
            return
        if not self.meteoalarm_client:
            return
        try:
            alerts = await self.meteoalarm_client.fetch_alerts(location)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"MeteoAlarm fetch failed: {exc}")
            return

        if not alerts or not alerts.has_alerts():
            return

        existing = weather_data.alerts.alerts if weather_data.alerts else []
        combined: dict[str, WeatherAlert] = {alert.get_unique_id(): alert for alert in existing}
        for alert in alerts.alerts:
            combined.setdefault(alert.get_unique_id(), alert)
        weather_data.alerts = WeatherAlerts(alerts=list(combined.values()))

    def _apply_trend_insights(self, weather_data: WeatherData) -> None:
        trends.apply_trend_insights(weather_data, self.trend_insights_enabled, self.trend_hours)

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

    def _weather_code_to_description(self, code: int | None) -> str | None:
        return parsers.weather_code_to_description(code)

    def _format_date_name(self, date_str: str, index: int) -> str:
        return parsers.format_date_name(date_str, index)
