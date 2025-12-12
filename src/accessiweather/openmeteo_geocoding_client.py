"""
Open-Meteo Geocoding API client for AccessiWeather.

This module provides a client for the Open-Meteo Geocoding API, which offers
free geocoding without requiring an API key.

API Documentation: https://open-meteo.com/en/docs/geocoding-api
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OpenMeteoGeocodingError(Exception):
    """Base exception for Open-Meteo Geocoding API errors."""


class OpenMeteoGeocodingApiError(OpenMeteoGeocodingError):
    """Exception raised for API errors (4xx, 5xx responses)."""


class OpenMeteoGeocodingNetworkError(OpenMeteoGeocodingError):
    """Exception raised for network-related errors (timeout, connection)."""


@dataclass
class GeocodingResult:
    """Structured result from geocoding API."""

    name: str
    latitude: float
    longitude: float
    country: str
    country_code: str
    timezone: str
    admin1: str | None = None  # State/Province
    admin2: str | None = None  # County
    admin3: str | None = None  # City district
    elevation: float | None = None
    population: int | None = None

    @property
    def display_name(self) -> str:
        """Generate human-readable display name."""
        parts = [self.name]
        if self.admin1:
            parts.append(self.admin1)
        parts.append(self.country)
        return ", ".join(parts)


class OpenMeteoGeocodingClient:
    """
    Client for the Open-Meteo Geocoding API.

    Open-Meteo Geocoding provides free geocoding without requiring an API key.
    It returns location data including coordinates, timezone, country, and elevation.
    """

    BASE_URL = "https://geocoding-api.open-meteo.com/v1"

    def __init__(
        self,
        user_agent: str = "AccessiWeather",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """
        Initialize the Open-Meteo Geocoding API client.

        Args:
            user_agent: User agent string for API requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds

        """
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Create HTTP client
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    def __del__(self) -> None:
        """Clean up the HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    def _make_request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Make a request to the Open-Meteo Geocoding API.

        Args:
            endpoint: API endpoint (e.g., "search")
            params: Query parameters

        Returns:
            JSON response as a dictionary

        Raises:
            OpenMeteoGeocodingApiError: If the API returns an error
            OpenMeteoGeocodingNetworkError: If there's a network error

        """
        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Making geocoding request to {url} with params: {params}")
                response = self.client.get(url, params=params)

                # Check for HTTP errors
                if response.status_code == 400:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get("reason", "Bad request")
                    raise OpenMeteoGeocodingApiError(f"API error: {error_msg}")
                if response.status_code == 429:
                    raise OpenMeteoGeocodingApiError("Rate limit exceeded")
                if response.status_code >= 500:
                    raise OpenMeteoGeocodingApiError(f"Server error: {response.status_code}")

                response.raise_for_status()

                # Parse JSON response
                data: dict[str, Any] = response.json()
                logger.debug(f"Received geocoding response with keys: {list(data.keys())}")
                return data

            except httpx.TimeoutException as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Geocoding request timeout, retrying in {self.retry_delay}s "
                        f"(attempt {attempt + 1})"
                    )
                    time.sleep(self.retry_delay)
                    continue
                raise OpenMeteoGeocodingNetworkError(
                    f"Request timeout after {self.max_retries} retries: {e!s}"
                ) from e

            except httpx.NetworkError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Geocoding network error, retrying in {self.retry_delay}s "
                        f"(attempt {attempt + 1})"
                    )
                    time.sleep(self.retry_delay)
                    continue
                raise OpenMeteoGeocodingNetworkError(
                    f"Network error after {self.max_retries} retries: {e!s}"
                ) from e

            except Exception as e:
                if isinstance(e, OpenMeteoGeocodingApiError | OpenMeteoGeocodingNetworkError):
                    raise
                raise OpenMeteoGeocodingApiError(f"Unexpected error: {e!s}") from e

        # This should never be reached due to the exception handling above
        raise OpenMeteoGeocodingApiError("Request failed after all retries")

    def search(
        self,
        name: str,
        count: int = 10,
        language: str = "en",
    ) -> list[GeocodingResult]:
        """
        Search for locations by name.

        Args:
            name: Location name to search for
            count: Maximum number of results to return (1-100)
            language: Language for result names (ISO 639-1 code)

        Returns:
            List of GeocodingResult objects matching the search query

        """
        params = {
            "name": name,
            "count": min(count, 100),  # API max is 100
            "language": language,
            "format": "json",
        }

        data = self._make_request("search", params)
        return self._parse_results(data)

    def _parse_results(self, data: dict[str, Any]) -> list[GeocodingResult]:
        """
        Parse API response into GeocodingResult objects.

        Args:
            data: Raw API response dictionary

        Returns:
            List of GeocodingResult objects

        """
        results: list[GeocodingResult] = []
        raw_results = data.get("results", [])

        for item in raw_results:
            try:
                result = GeocodingResult(
                    name=item["name"],
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                    country=item.get("country", ""),
                    country_code=item.get("country_code", ""),
                    timezone=item.get("timezone", ""),
                    admin1=item.get("admin1"),
                    admin2=item.get("admin2"),
                    admin3=item.get("admin3"),
                    elevation=item.get("elevation"),
                    population=item.get("population"),
                )
                results.append(result)
            except KeyError as e:
                logger.warning(f"Skipping geocoding result with missing required field: {e}")
                continue

        return results

    def close(self) -> None:
        """Close the HTTP client."""
        if hasattr(self, "client"):
            self.client.close()
