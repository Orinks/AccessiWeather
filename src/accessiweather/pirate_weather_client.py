"""
Pirate Weather API client for AccessiWeather.

This module provides a client for the Pirate Weather API
(https://pirateweather.net), which is an open-source Dark Sky API replacement.
It provides current conditions, hourly/daily forecasts, minutely precipitation,
and global WMO weather alerts.

API endpoint: https://api.pirateweather.net/forecast/{apikey}/{lat},{lon}
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from .models import (
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    WeatherAlerts,
)
from .pirate_weather_current import parse_current_conditions
from .pirate_weather_parsing import (
    _build_alert_id,  # noqa: F401 - compatibility re-export for tests/callers
    _icon_to_condition,  # noqa: F401 - compatibility re-export for tests/callers
    parse_alerts,
    parse_forecast,
    parse_hourly_forecast,
)
from .utils.retry_utils import async_retry_with_backoff

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.pirateweather.net/forecast"
_PIRATE_WEATHER_API_VERSION = "2"
_PW_MIN_INCLUDED_SEVERITIES = frozenset({"Severe", "Extreme"})


class PirateWeatherApiError(Exception):
    """Exception raised for Pirate Weather API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize the instance."""
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PirateWeatherClient:
    """Client for the Pirate Weather API."""

    def __init__(
        self,
        api_key: str,
        user_agent: str = "AccessiWeather/1.0",
        units: str = "us",
    ):
        """
        Initialize the Pirate Weather client.

        Args:
            api_key: Pirate Weather API key.
            user_agent: HTTP User-Agent header value.
            units: Unit system – "us" (°F, mph, in), "si" (°C, m/s, mm),
                   "ca" (°C, km/h, mm), or "uk"/"uk2" (°C, mph, mm).

        """
        self.api_key = api_key
        self.user_agent = user_agent
        self.units = "uk2" if units == "uk" else units
        self.timeout = 15.0
        self._recent_payload_ttl_seconds = 2.0
        self._rate_limit_cooldown_seconds = 300.0
        self._recent_payloads: dict[str, tuple[float, dict]] = {}
        self._in_flight_payloads: dict[str, asyncio.Task[dict | None]] = {}
        self._rate_limited_until: float = 0.0

    def _build_url(self, lat: float, lon: float) -> str:
        return f"{_BASE_URL}/{self.api_key}/{lat},{lon}"

    def _cache_key(self, location: Location) -> str:
        """Build a stable cache key for a location+unit combination."""
        return f"{location.latitude:.6f},{location.longitude:.6f}:{self.units}"

    def _get_cached_payload(self, cache_key: str) -> dict | None:
        """Return a recent payload if it is still fresh."""
        cached = self._recent_payloads.get(cache_key)
        if not cached:
            return None

        fetched_at, payload = cached
        if (time.monotonic() - fetched_at) > self._recent_payload_ttl_seconds:
            self._recent_payloads.pop(cache_key, None)
            return None
        return payload

    def _enforce_rate_limit_cooldown(self) -> None:
        """Short-circuit requests while a recent 429 cooldown is active."""
        if time.monotonic() < self._rate_limited_until:
            raise PirateWeatherApiError("API rate limit exceeded", 429)

    def _finalize_in_flight_payload(self, cache_key: str, task: asyncio.Task[dict | None]) -> None:
        """Clean up in-flight bookkeeping when a shared fetch task completes."""
        if self._in_flight_payloads.get(cache_key) is task:
            self._in_flight_payloads.pop(cache_key, None)

        if task.cancelled():
            return

        try:
            payload = task.result()
        except Exception:
            return

        if payload is not None:
            self._recent_payloads[cache_key] = (time.monotonic(), payload)

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
    async def _request_forecast_data(self, location: Location) -> dict | None:
        """Issue a single network request for the Pirate Weather payload."""
        url = self._build_url(location.latitude, location.longitude)
        params = {
            "units": self.units,
            "extend": "hourly",
            "version": _PIRATE_WEATHER_API_VERSION,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 400:
                    raise PirateWeatherApiError(
                        "Bad request – check API key and coordinates",
                        response.status_code,
                    )
                if response.status_code == 401:
                    raise PirateWeatherApiError("Invalid API key", response.status_code)
                if response.status_code == 429:
                    self._rate_limited_until = time.monotonic() + self._rate_limit_cooldown_seconds
                    raise PirateWeatherApiError("API rate limit exceeded", response.status_code)
                if response.status_code != 200:
                    raise PirateWeatherApiError(
                        f"API request failed: HTTP {response.status_code}",
                        response.status_code,
                    )

                return response.json()

        except httpx.TimeoutException:
            logger.error("Pirate Weather API request timed out")
            raise PirateWeatherApiError("Request timed out") from None
        except httpx.RequestError as e:
            logger.error(f"Pirate Weather API request failed: {e}")
            raise PirateWeatherApiError(f"Request failed: {e}") from e
        except PirateWeatherApiError:
            raise
        except Exception as e:
            logger.error(f"Unexpected Pirate Weather error: {e}")
            raise PirateWeatherApiError(f"Unexpected error: {e}") from e

    async def get_forecast_data(self, location: Location) -> dict | None:
        """
        Fetch the full forecast payload from Pirate Weather.

        Returns the raw API response dict (with ``currently``, ``hourly``,
        ``daily``, ``minutely``, ``alerts`` keys) or ``None`` on error.
        """
        self._enforce_rate_limit_cooldown()
        cache_key = self._cache_key(location)
        cached_payload = self._get_cached_payload(cache_key)
        if cached_payload is not None:
            return cached_payload

        existing_task = self._in_flight_payloads.get(cache_key)
        if existing_task is not None:
            return await asyncio.shield(existing_task)

        task = asyncio.create_task(self._request_forecast_data(location))
        self._in_flight_payloads[cache_key] = task
        task.add_done_callback(
            lambda done_task: self._finalize_in_flight_payload(cache_key, done_task)
        )
        return await asyncio.shield(task)

    async def get_current_conditions(self, location: Location) -> CurrentConditions | None:
        """Get current weather conditions."""
        data = await self.get_forecast_data(location)
        if data is None:
            return None
        return self._parse_current_conditions(data)

    async def get_forecast(self, location: Location, days: int = 7) -> Forecast | None:
        """Get daily weather forecast."""
        data = await self.get_forecast_data(location)
        if data is None:
            return None
        return self._parse_forecast(data, days=days)

    async def get_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Get hourly weather forecast."""
        data = await self.get_forecast_data(location)
        if data is None:
            return None
        return self._parse_hourly_forecast(data)

    async def get_minutely_forecast(self, location: Location) -> dict | None:
        """Return the raw payload for minutely precipitation consumers."""
        return await self.get_forecast_data(location)

    async def get_alerts(self, location: Location) -> WeatherAlerts:
        """Get weather alerts."""
        try:
            data = await self.get_forecast_data(location)
            if data is None:
                return WeatherAlerts(alerts=[])
            return self._parse_alerts(data)
        except Exception:
            logger.debug("Pirate Weather alerts request failed", exc_info=True)
            return WeatherAlerts(alerts=[])

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse Pirate Weather ``currently`` block into CurrentConditions."""
        return parse_current_conditions(self, data)

    def _parse_forecast(self, data: dict, days: int | None = None) -> Forecast | None:
        """Parse Pirate Weather ``daily`` block into a Forecast."""
        return parse_forecast(self, data, days=days)

    def _parse_hourly_forecast(self, data: dict) -> HourlyForecast:
        """Parse Pirate Weather ``hourly`` block into an HourlyForecast."""
        return parse_hourly_forecast(self, data)

    def _parse_alerts(self, data: dict) -> WeatherAlerts:
        """Parse Pirate Weather ``alerts`` list into WeatherAlerts."""
        return parse_alerts(self, data)

    def _map_severity(self, severity: str | None) -> str:
        """Map Pirate Weather severity string to standard levels."""
        if not severity:
            return "Unknown"
        mapping = {
            "extreme": "Extreme",
            "severe": "Severe",
            "moderate": "Moderate",
            "minor": "Minor",
            "advisory": "Minor",
            "watch": "Moderate",
            "warning": "Severe",
        }
        return mapping.get(severity.lower(), "Unknown")
