"""
Open-Meteo Geocoding API client for AccessiWeather.

This module provides a client for the Open-Meteo Geocoding API, which offers
free geocoding without requiring an API key.

API Documentation: https://open-meteo.com/en/docs/geocoding-api
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

import httpx

try:
    from unidecode import unidecode
except ImportError:  # pragma: no cover - exercised when the dependency is unavailable locally
    FALLBACK_TRANSLITERATION_MAP = str.maketrans(
        {
            "á": "a",
            "à": "a",
            "â": "a",
            "ã": "a",
            "ä": "a",
            "å": "a",
            "ç": "c",
            "é": "e",
            "è": "e",
            "ê": "e",
            "ë": "e",
            "í": "i",
            "ì": "i",
            "î": "i",
            "ï": "i",
            "ñ": "n",
            "ó": "o",
            "ò": "o",
            "ô": "o",
            "õ": "o",
            "ö": "o",
            "ø": "o",
            "ß": "ss",
            "ú": "u",
            "ù": "u",
            "û": "u",
            "ü": "u",
            "ý": "y",
            "ÿ": "y",
            "Á": "A",
            "À": "A",
            "Â": "A",
            "Ã": "A",
            "Ä": "A",
            "Å": "A",
            "Ç": "C",
            "É": "E",
            "È": "E",
            "Ê": "E",
            "Ë": "E",
            "Í": "I",
            "Ì": "I",
            "Î": "I",
            "Ï": "I",
            "Ñ": "N",
            "Ó": "O",
            "Ò": "O",
            "Ô": "O",
            "Õ": "O",
            "Ö": "O",
            "Ø": "O",
            "Ú": "U",
            "Ù": "U",
            "Û": "U",
            "Ü": "U",
            "Ý": "Y",
        }
    )

    def unidecode(value: str) -> str:
        """Best-effort ASCII transliteration when Unidecode is unavailable."""
        normalized = value.translate(FALLBACK_TRANSLITERATION_MAP)
        return unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")


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
    UNICODE_SUBSTITUTIONS: dict[str, tuple[str, ...]] = {
        "a": ("á", "à", "â", "ã", "ä", "å"),
        "c": ("ç",),
        "e": ("é", "è", "ê", "ë"),
        "i": ("í", "ì", "î", "ï"),
        "n": ("ñ",),
        "o": ("ó", "ò", "ô", "õ", "ö", "ø"),
        "s": ("ß",),
        "u": ("ú", "ù", "û", "ü"),
        "y": ("ý", "ÿ"),
    }
    COUNTRY_HINTS: dict[str, tuple[str, ...]] = {
        "alesund": ("Norway",),
        "goteborg": ("Sweden",),
        "malmo": ("Sweden",),
        "munchen": ("Germany",),
        "reykjavik": ("Iceland",),
        "tromso": ("Norway",),
        "zurich": ("Switzerland",),
    }

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
        search_name = name.strip()
        params = {
            "count": min(count, 100),  # API max is 100
            "language": language,
            "format": "json",
        }

        direct_results = self._search_once(search_name, params)
        if direct_results:
            return direct_results

        for fallback_query in self._build_fallback_queries(search_name):
            fallback_results = self._search_once(fallback_query, params)
            matched_results = self._filter_matching_results(search_name, fallback_results)
            if matched_results:
                logger.info(
                    "Geocoding fallback matched '%s' using retry query '%s'",
                    search_name,
                    fallback_query,
                )
                return matched_results

        return []

    def _search_once(
        self,
        name: str,
        base_params: dict[str, Any],
    ) -> list[GeocodingResult]:
        """Run a single geocoding search request."""
        params = {
            **base_params,
            "name": name,
        }
        data = self._make_request("search", params)
        return self._parse_results(data)

    def _build_fallback_queries(self, name: str) -> list[str]:
        """Build retry queries for ASCII-only location searches."""
        fallback_queries: list[str] = []
        seen: set[str] = {name.casefold()}

        for variant in self._generate_unicode_variants(name):
            self._append_unique_query(fallback_queries, seen, variant)

        if len(name.split()) == 1:
            normalized_name = self._normalize_text(name)
            for country_name in self.COUNTRY_HINTS.get(normalized_name, ()):
                self._append_unique_query(fallback_queries, seen, f"{name}, {country_name}")
                for variant in self._generate_unicode_variants(name):
                    self._append_unique_query(
                        fallback_queries,
                        seen,
                        f"{variant}, {country_name}",
                    )

        return fallback_queries

    def _append_unique_query(
        self,
        queries: list[str],
        seen: set[str],
        query: str,
    ) -> None:
        """Add a fallback query once, preserving insertion order."""
        normalized_query = query.casefold()
        if normalized_query in seen:
            return

        seen.add(normalized_query)
        queries.append(query)

    def _generate_unicode_variants(self, name: str, max_variants: int = 32) -> list[str]:
        """Generate likely Unicode spelling variants for an ASCII query."""
        variants: list[str] = []
        seen: set[str] = {name.casefold()}
        frontier = [name]

        for _ in range(2):
            next_frontier: list[str] = []
            for candidate in frontier:
                for index, char in enumerate(candidate):
                    for replacement in self.UNICODE_SUBSTITUTIONS.get(char.casefold(), ()):
                        variant = candidate[:index] + replacement + candidate[index + 1 :]
                        normalized_variant = variant.casefold()
                        if normalized_variant in seen:
                            continue

                        seen.add(normalized_variant)
                        variants.append(variant)
                        next_frontier.append(variant)

                        if len(variants) >= max_variants:
                            return variants

            if not next_frontier:
                break

            frontier = next_frontier

        return variants

    def _filter_matching_results(
        self,
        original_query: str,
        results: list[GeocodingResult],
    ) -> list[GeocodingResult]:
        """Keep fallback results that still match the user's original query."""
        normalized_query = self._normalize_text(original_query)
        scored_results: list[tuple[int, GeocodingResult]] = []

        for result in results:
            if not self._result_matches_query(normalized_query, result):
                continue

            scored_results.append((self._score_result_match(normalized_query, result), result))

        scored_results.sort(
            key=lambda item: (
                item[0],
                -(item[1].population or 0),
                item[1].display_name.casefold(),
            )
        )
        return [result for _, result in scored_results]

    def _result_matches_query(self, normalized_query: str, result: GeocodingResult) -> bool:
        """Check whether a fallback result matches the original ASCII query."""
        result_name = self._normalize_text(result.name)
        display_name = self._normalize_text(result.display_name)

        return (
            result_name == normalized_query
            or display_name == normalized_query
            or result_name.startswith(f"{normalized_query} ")
            or display_name.startswith(f"{normalized_query} ")
            or f" {normalized_query} " in f" {display_name} "
        )

    def _score_result_match(self, normalized_query: str, result: GeocodingResult) -> int:
        """Rank more exact fallback matches ahead of looser matches."""
        result_name = self._normalize_text(result.name)
        display_name = self._normalize_text(result.display_name)

        if result_name == normalized_query:
            return 0
        if display_name == normalized_query:
            return 1
        if result_name.startswith(f"{normalized_query} "):
            return 2
        if display_name.startswith(f"{normalized_query} "):
            return 3
        return 4

    def _normalize_text(self, text: str) -> str:
        """Normalize text for accent-insensitive comparisons."""
        ascii_text = unidecode(text).casefold()
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_text)).strip()

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
