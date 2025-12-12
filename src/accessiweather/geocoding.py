"""
Geocoding service for AccessiWeather.

This module provides geocoding functionality to convert addresses and zip codes to coordinates.
Uses Open-Meteo Geocoding API for location lookups.
"""

from __future__ import annotations

import logging
import re

from .openmeteo_geocoding_client import (
    GeocodingResult,
    OpenMeteoGeocodingClient,
    OpenMeteoGeocodingError,
)

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding addresses and zip codes."""

    # Regular expression for US ZIP codes (both 5-digit and ZIP+4 formats)
    ZIP_CODE_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")
    # Allowed country codes (primarily US, potentially add territories later if needed)
    ALLOWED_COUNTRY_CODES = ["US"]

    def __init__(
        self, user_agent: str = "AccessiWeather", timeout: int = 10, data_source: str = "nws"
    ) -> None:
        """
        Initialize the geocoding service.

        Args:
            user_agent: User agent string for API requests
            timeout: Timeout in seconds for geocoding requests
            data_source: The data source to use ('nws' or 'auto')

        """
        self.client = OpenMeteoGeocodingClient(
            user_agent=user_agent,
            timeout=float(timeout),
        )
        self.data_source = data_source

    def is_zip_code(self, text: str) -> bool:
        """
        Check if the given text is a valid US ZIP code.

        Args:
            text: Text to check

        Returns:
            True if the text is a valid US ZIP code, False otherwise

        """
        return bool(self.ZIP_CODE_PATTERN.match(text))

    def format_zip_code(self, zip_code: str) -> str:
        """
        Format a ZIP code for geocoding.

        Args:
            zip_code: ZIP code to format

        Returns:
            Formatted ZIP code string for geocoding

        """
        # Remove the dash for ZIP+4 codes to get just the 5-digit base
        if "-" in zip_code:
            zip_code = zip_code.split("-")[0]

        # Add USA to improve geocoding accuracy
        return f"{zip_code}, USA"

    def _filter_results_by_country(self, results: list[GeocodingResult]) -> list[GeocodingResult]:
        """
        Filter geocoding results based on data source.

        Args:
            results: List of GeocodingResult objects

        Returns:
            Filtered list based on data_source setting

        """
        if self.data_source == "nws":
            # Filter for US locations only when using NWS
            return [r for r in results if r.country_code in self.ALLOWED_COUNTRY_CODES]
        # For WeatherAPI or Automatic, allow any location worldwide
        return results

    def geocode_address(self, address: str) -> tuple[float, float, str] | None:
        """
        Convert an address or zip code to coordinates, filtering for US locations.

        Args:
            address: Address or zip code to geocode

        Returns:
            Tuple of (latitude, longitude, display_name) if successful and within
            the US NWS coverage area (when using NWS), None otherwise

        """
        try:
            # Clean up the address string
            address = address.strip()
            original_query = address  # Keep original for logging

            # Check if it's a US zip code (5-digit or ZIP+4 format)
            if self.is_zip_code(address):
                logger.info(f"Detected ZIP code format: {address}")
                address = self.format_zip_code(address)
                logger.info(f"Formatted for geocoding as: {address}")

            # Attempt geocoding
            logger.debug(f"Geocoding address: {address}")
            results = self.client.search(address, count=5)

            if not results:
                logger.warning(f"No results found for address: {original_query}")
                return None

            # Filter results based on data source
            filtered_results = self._filter_results_by_country(results)

            if not filtered_results:
                if self.data_source == "nws":
                    logger.warning(
                        f"Location found for query '{original_query}', "
                        f"but filtered out due to unsupported country. "
                        f"Only {self.ALLOWED_COUNTRY_CODES} are supported with NWS data source."
                    )
                return None

            # Return the first matching result
            location = filtered_results[0]
            logger.info(
                f"Successfully geocoded '{original_query}' to: {location.display_name} "
                f"(country_code: {location.country_code})"
            )
            return location.latitude, location.longitude, location.display_name

        except OpenMeteoGeocodingError as e:
            logger.error(f"Geocoding error for '{original_query}': {e!s}")
            return None
        except Exception as e:
            logger.error(f"Unexpected geocoding error for '{original_query}': {e!s}")
            return None

    def validate_coordinates(self, lat: float, lon: float, us_only: bool | None = None) -> bool:
        """
        Validate if coordinates are within valid range and optionally within US.

        This method validates that coordinates are within valid global bounds.
        When us_only=True, it uses a simple bounding box check for US territory
        rather than reverse geocoding.

        If us_only is None, the method will use the data_source to determine whether
        to restrict validation to US locations (True for 'nws', False for others).

        Args:
            lat: Latitude
            lon: Longitude
            us_only: Whether to restrict validation to US locations only
                     If None, uses data_source to determine (default: None)

        Returns:
            True if coordinates are valid according to the criteria, False otherwise

        """
        # If us_only is not specified, determine based on data source
        if us_only is None:
            us_only = self.data_source == "nws"

        # Basic validation for all cases
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            logger.warning(
                f"Coordinates ({lat}, {lon}) are outside valid range "
                f"(latitude: -90 to 90, longitude: -180 to 180)"
            )
            return False

        # If not US-only, we've already validated the basic range
        if not us_only:
            logger.debug(f"Coordinates ({lat}, {lon}) are within valid global range")
            return True

        # For US-only validation, use a simple bounding box check
        # This covers continental US, Alaska, Hawaii, and territories
        # Continental US: roughly 24-50°N, 66-125°W
        # Alaska: roughly 51-72°N, 130-173°W (and some east of 180°)
        # Hawaii: roughly 18-23°N, 154-161°W
        # Puerto Rico/Virgin Islands: roughly 17-19°N, 64-68°W
        # Guam: roughly 13-14°N, 144-145°E

        us_bounds = [
            # Continental US
            (24.0, 50.0, -125.0, -66.0),
            # Alaska (main)
            (51.0, 72.0, -180.0, -130.0),
            # Alaska (Aleutians crossing dateline)
            (51.0, 55.0, 172.0, 180.0),
            # Hawaii
            (18.0, 23.0, -161.0, -154.0),
            # Puerto Rico / Virgin Islands
            (17.0, 19.0, -68.0, -64.0),
            # Guam
            (13.0, 14.0, 144.0, 146.0),
        ]

        for min_lat, max_lat, min_lon, max_lon in us_bounds:
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                logger.info(f"Coordinates ({lat}, {lon}) validated as within US bounds")
                return True

        logger.warning(
            f"Coordinates ({lat}, {lon}) are outside the US NWS coverage area bounds. "
            f"Only US locations are supported with NWS data source."
        )
        return False

    def suggest_locations(self, query: str, limit: int = 5) -> list[str]:
        """
        Suggest location completions based on partial input.

        Args:
            query: Partial address or location name
            limit: Maximum number of suggestions to return

        Returns:
            List of suggested location strings (filtered by data_source)

        """
        try:
            # Clean up the query string
            query = query.strip()

            if not query or len(query) < 2:
                return []

            # Check if it's a ZIP code and format appropriately
            if self.is_zip_code(query):
                logger.info(f"Detected ZIP code in suggestions: {query}")
                query = self.format_zip_code(query)
                logger.info(f"Formatted for suggestions as: {query}")

            # Use geocoder to get suggestions
            logger.debug(f"Getting location suggestions for: {query}")
            # Request more results than needed to allow for filtering
            results = self.client.search(query, count=limit * 2)

            if not results:
                logger.debug(f"No suggestions found for query: {query}")
                return []

            # Filter results based on data source
            filtered_results = self._filter_results_by_country(results)

            # Limit to requested number
            filtered_results = filtered_results[:limit]

            # Extract display names
            suggestions = [r.display_name for r in filtered_results]

            if self.data_source == "nws":
                logger.debug(
                    f"Found {len(suggestions)} US location suggestions for NWS data source"
                )
            else:
                logger.debug(
                    f"Found {len(suggestions)} worldwide location suggestions for non-NWS data source"
                )

            return suggestions

        except OpenMeteoGeocodingError as e:
            logger.error(f"Location suggestion error for '{query}': {e!s}")
            return []
        except Exception as e:
            logger.error(f"Unexpected location suggestion error for '{query}': {e!s}")
            return []
