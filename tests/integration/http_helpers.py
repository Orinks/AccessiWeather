"""
HTTP test helpers with provider-specific rate limiting and resilience.

Provides rate limiters, resilient HTTP client wrapper, and contract assertion
helpers for integration tests against weather API providers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for controlling request frequency."""

    def __init__(self, requests_per_minute: int):
        """Initialize rate limiter with requests per minute limit."""
        self.requests_per_minute = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self.request_times: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait if needed to stay under rate limit."""
        async with self._lock:
            now = time.monotonic()
            cutoff = now - 60.0
            self.request_times = [t for t in self.request_times if t > cutoff]

            if len(self.request_times) >= self.requests_per_minute:
                oldest = self.request_times[0]
                wait_time = oldest + 60.0 - now
                if wait_time > 0:
                    logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    now = time.monotonic()
                    cutoff = now - 60.0
                    self.request_times = [t for t in self.request_times if t > cutoff]

            self.request_times.append(now)

    def reset(self) -> None:
        """Reset the rate limiter state."""
        self.request_times.clear()


NWS_LIMITER = RateLimiter(requests_per_minute=10)
OPENMETEO_LIMITER = RateLimiter(requests_per_minute=500)
VC_LIMITER = RateLimiter(requests_per_minute=1)

_PROVIDER_LIMITERS: dict[str, RateLimiter] = {
    "nws": NWS_LIMITER,
    "openmeteo": OPENMETEO_LIMITER,
    "visual_crossing": VC_LIMITER,
}


class RateLimitExceeded(Exception):
    """Raised when provider returns 429 and retry is not appropriate."""


class TransientError(Exception):
    """Raised when a transient error occurs after max retries."""


async def resilient_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    provider: str = "default",
    timeout: float = 30.0,
    max_retries: int = 3,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make an HTTP request with rate limiting and retry logic.

    Args:
        client: The httpx async client to use.
        method: HTTP method (GET, POST, etc.).
        url: The URL to request.
        provider: Provider name for rate limiting ("nws", "openmeteo", "visual_crossing").
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts for transient failures.
        **kwargs: Additional arguments passed to client.request().

    Returns:
        The HTTP response.

    Raises:
        RateLimitExceeded: If provider returns 429 and retry is not appropriate.
        TransientError: If transient errors persist after max retries.
        httpx.HTTPError: For other HTTP errors.

    """
    limiter = _PROVIDER_LIMITERS.get(provider)
    if limiter:
        await limiter.acquire()

    kwargs.setdefault("timeout", timeout)
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = await client.request(method, url, **kwargs)

            if response.status_code == 429:
                if provider == "visual_crossing":
                    raise RateLimitExceeded(f"Visual Crossing rate limit exceeded (429) for {url}")
                if provider == "nws":
                    retry_after = response.headers.get("Retry-After", "5")
                    try:
                        wait_time = float(retry_after)
                    except ValueError:
                        wait_time = 5.0
                    logger.warning(f"NWS 429: waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                if provider == "openmeteo":
                    if attempt < 1:
                        wait_time = 2.0 * (attempt + 1)
                        logger.warning(f"Open-Meteo 429: backing off {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    raise RateLimitExceeded(f"Open-Meteo rate limit exceeded after retry for {url}")
                await asyncio.sleep(1.0)
                continue

            if 500 <= response.status_code < 600:
                if attempt < max_retries:
                    wait_time = 1.0 * (2**attempt)
                    logger.warning(
                        f"Server error {response.status_code}: retry {attempt + 1}/{max_retries} after {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise TransientError(
                    f"Server error {response.status_code} after {max_retries} retries for {url}"
                )

            return response

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
            last_error = e
            if attempt < max_retries:
                wait_time = 1.0 * (2**attempt)
                logger.warning(
                    f"Connection error: retry {attempt + 1}/{max_retries} after {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)
                continue
            raise TransientError(
                f"Connection error after {max_retries} retries for {url}: {e}"
            ) from e

    raise TransientError(f"Request failed after {max_retries} retries: {last_error}")


def create_nws_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """Create an httpx client configured for NWS API."""
    return httpx.AsyncClient(
        headers={
            "User-Agent": "(AccessiWeather Integration Tests, https://github.com/Orinks/AccessiWeather)",
            "Accept": "application/geo+json",
        },
        timeout=timeout,
        follow_redirects=True,
    )


def create_openmeteo_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """Create an httpx client configured for Open-Meteo API."""
    return httpx.AsyncClient(
        headers={
            "Accept": "application/json",
        },
        timeout=timeout,
        follow_redirects=True,
    )


def create_vc_client(api_key: str, timeout: float = 30.0) -> httpx.AsyncClient:
    """Create an httpx client configured for Visual Crossing API."""
    return httpx.AsyncClient(
        headers={
            "Accept": "application/json",
        },
        params={"key": api_key},
        timeout=timeout,
        follow_redirects=True,
    )


def assert_valid_temperature(value: float | None, unit: str = "F") -> None:
    """
    Assert temperature is in valid range.

    Args:
        value: Temperature value (can be None for missing data).
        unit: Temperature unit ("F" or "C").

    Raises:
        AssertionError: If temperature is outside valid range.

    """
    if value is None:
        return

    if unit.upper() == "F":
        min_temp, max_temp = -130.0, 140.0
    elif unit.upper() == "C":
        min_temp, max_temp = -90.0, 60.0
    else:
        raise ValueError(f"Unknown temperature unit: {unit}")

    assert min_temp <= value <= max_temp, (
        f"Temperature {value}°{unit} outside valid range [{min_temp}, {max_temp}]"
    )


def assert_valid_humidity(value: float | None) -> None:
    """
    Assert humidity is in valid range (0-100%).

    Args:
        value: Humidity percentage (can be None for missing data).

    Raises:
        AssertionError: If humidity is outside 0-100%.

    """
    if value is None:
        return

    assert 0.0 <= value <= 100.0, f"Humidity {value}% outside valid range [0, 100]"


def assert_valid_wind_speed(value: float | None, unit: str = "mph") -> None:
    """
    Assert wind speed is non-negative and in reasonable range.

    Args:
        value: Wind speed value (can be None for missing data).
        unit: Wind speed unit ("mph", "kph", "m/s", "knots").

    Raises:
        AssertionError: If wind speed is negative or unreasonably high.

    """
    if value is None:
        return

    max_speeds = {
        "mph": 320.0,
        "kph": 515.0,
        "m/s": 143.0,
        "knots": 278.0,
    }
    max_speed = max_speeds.get(unit.lower(), 500.0)

    assert value >= 0.0, f"Wind speed {value} {unit} is negative"
    assert value <= max_speed, f"Wind speed {value} {unit} exceeds reasonable maximum {max_speed}"


def assert_valid_timestamp(dt: datetime | str | None) -> None:
    """
    Assert timestamp is valid and reasonable.

    Args:
        dt: Datetime object or ISO format string (can be None for missing data).

    Raises:
        AssertionError: If timestamp is invalid or before year 2000.
        ValueError: If string cannot be parsed as datetime.

    """
    if dt is None:
        return

    if isinstance(dt, str):
        try:
            if dt.endswith("Z"):
                dt = dt[:-1] + "+00:00"
            parsed = datetime.fromisoformat(dt)
        except ValueError as e:
            raise ValueError(f"Cannot parse timestamp '{dt}': {e}") from e
    else:
        parsed = dt

    assert parsed.year >= 2000, f"Timestamp year {parsed.year} is before 2000"
    assert parsed.year <= 2100, f"Timestamp year {parsed.year} is after 2100"


def assert_schema_matches(data: dict[str, Any], required_fields: list[str]) -> None:
    """
    Assert all required fields are present in data.

    Args:
        data: Dictionary to check.
        required_fields: List of required field names (supports dot notation for nested).

    Raises:
        AssertionError: If any required field is missing.

    """
    missing = []
    for field in required_fields:
        parts = field.split(".")
        current = data
        for _i, part in enumerate(parts):
            if not isinstance(current, dict):
                missing.append(field)
                break
            if part not in current:
                missing.append(field)
                break
            current = current[part]

    assert not missing, f"Missing required fields: {missing}"


def assert_valid_coordinates(lat: float | None, lon: float | None) -> None:
    """
    Assert coordinates are in valid range.

    Args:
        lat: Latitude value (-90 to 90).
        lon: Longitude value (-180 to 180).

    Raises:
        AssertionError: If coordinates are outside valid range.

    """
    if lat is not None:
        assert -90.0 <= lat <= 90.0, f"Latitude {lat} outside valid range [-90, 90]"
    if lon is not None:
        assert -180.0 <= lon <= 180.0, f"Longitude {lon} outside valid range [-180, 180]"


def assert_valid_pressure(value: float | None, unit: str = "mb") -> None:
    """
    Assert pressure is in valid range.

    Args:
        value: Pressure value (can be None for missing data).
        unit: Pressure unit ("mb", "hPa", "inHg").

    Raises:
        AssertionError: If pressure is outside valid range.

    """
    if value is None:
        return

    ranges = {
        "mb": (870.0, 1085.0),
        "hpa": (870.0, 1085.0),
        "inhg": (25.7, 32.0),
    }
    min_val, max_val = ranges.get(unit.lower(), (0.0, 2000.0))

    assert min_val <= value <= max_val, (
        f"Pressure {value} {unit} outside valid range [{min_val}, {max_val}]"
    )
