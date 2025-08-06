"""Geocoding service for AccessiWeather.

This module provides geocoding functionality to convert addresses and zip codes to coordinates.
"""

import logging
import re

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding addresses and zip codes."""

    # Regular expression for US ZIP codes (both 5-digit and ZIP+4 formats)
    ZIP_CODE_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")
    # Allowed country codes (primarily US, potentially add territories later if needed)
    # Nominatim often returns 'us' even for territories like PR, GU.
    ALLOWED_COUNTRY_CODES = ["us"]

    def __init__(
        self, user_agent: str = "AccessiWeather", timeout: int = 10, data_source: str = "nws"
    ):
        """Initialize the geocoding service.

        Args:
            user_agent: User agent string for API requests
            timeout: Timeout in seconds for geocoding requests
            data_source: The data source to use ('nws' or 'auto')

        """
        self.geolocator = Nominatim(user_agent=user_agent, timeout=timeout)
        self.data_source = data_source

    def is_zip_code(self, text: str) -> bool:
        """Check if the given text is a valid US ZIP code.

        Args:
            text: Text to check

        Returns:
            True if the text is a valid US ZIP code, False otherwise

        """
        return bool(self.ZIP_CODE_PATTERN.match(text))

    def format_zip_code(self, zip_code: str) -> str:
        """Format a ZIP code for geocoding.

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

    def geocode_address(self, address: str) -> tuple[float, float, str] | None:
        """Convert an address or zip code to coordinates, filtering for US locations.

        Args:
            address: Address or zip code to geocode

        Returns:
            Tuple of (latitude, longitude, display_name) if successful and within
            the US NWS coverage area, None otherwise

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

            # Attempt geocoding with increased timeout and address details
            logger.debug(f"Geocoding address: {address}")
            # Request addressdetails=True to get country_code
            location = self.geolocator.geocode(address, addressdetails=True)

            if not location:
                logger.warning(f"No results found for address: {original_query}")
                return None

            # --- Filter for US NWS Coverage Area if using NWS data source ---
            if hasattr(location, "raw") and isinstance(location.raw, dict):
                address_details = location.raw.get("address", {})
                country_code = address_details.get("country_code", "").lower()

                # Only filter for US locations if using NWS data source
                if self.data_source == "nws" and country_code not in self.ALLOWED_COUNTRY_CODES:
                    logger.warning(
                        f"Location '{location.address}' found for query '{original_query}', "
                        f"but filtered out due to unsupported country_code: '{country_code}'. "
                        f"Only {self.ALLOWED_COUNTRY_CODES} are supported with NWS data source."
                    )
                    return None  # Location outside coverage area

                # For WeatherAPI or Automatic, allow any location
                logger.info(
                    f"Successfully geocoded '{original_query}' to: {location.address} "
                    f"(country_code: {country_code})"
                )
                return location.latitude, location.longitude, location.address
            logger.warning(
                f"Geocoding result for '{original_query}' lacks detailed address information "
                f"to verify country code. Raw data: {getattr(location, 'raw', 'N/A')}"
            )
            # Cannot verify country, treat as unsupported for safety
            return None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Geocoding error for '{original_query}': {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected geocoding error for '{original_query}': {str(e)}")
            return None

    def validate_coordinates(self, lat: float, lon: float, us_only: bool | None = None) -> bool:
        """Validate if coordinates are within the US NWS coverage area or globally valid.

        This method performs a reverse geocoding lookup to determine if the
        given coordinates are within the US (when us_only=True) or are valid
        coordinates anywhere in the world (when us_only=False).

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

        try:
            logger.debug(f"Validating coordinates: ({lat}, {lon}) for US location")
            # Perform reverse geocoding with address details
            location = self.geolocator.reverse((lat, lon), addressdetails=True)

            if not location:
                logger.warning(f"No location found for coordinates: ({lat}, {lon})")
                return False

            # Check if the location is in the US
            if hasattr(location, "raw") and isinstance(location.raw, dict):
                address_details = location.raw.get("address", {})
                country_code = address_details.get("country_code", "").lower()

                if country_code in self.ALLOWED_COUNTRY_CODES:
                    logger.info(
                        f"Coordinates ({lat}, {lon}) validated as within US (country_code: {country_code})"
                    )
                    return True
                logger.warning(
                    f"Coordinates ({lat}, {lon}) are outside the US NWS coverage area "
                    f"(country_code: '{country_code}'). Only {self.ALLOWED_COUNTRY_CODES} are supported."
                )
                return False
            logger.warning(
                f"Reverse geocoding result for coordinates ({lat}, {lon}) lacks detailed "
                f"address information to verify country code. Raw data: {getattr(location, 'raw', 'N/A')}"
            )
            # Cannot verify country, treat as unsupported for safety
            return False

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Geocoding error validating coordinates ({lat}, {lon}): {str(e)}")
            # In case of service errors, we'll assume the coordinates are valid
            # to avoid removing potentially valid locations due to temporary service issues
            return True
        except Exception as e:
            logger.error(f"Unexpected error validating coordinates ({lat}, {lon}): {str(e)}")
            # Same as above, assume valid in case of unexpected errors
            return True

    def suggest_locations(self, query: str, limit: int = 5) -> list[str]:
        """Suggest location completions based on partial input, filtering for US locations.

        Args:
            query: Partial address or location name
            limit: Maximum number of suggestions to return

        Returns:
            List of suggested location strings (US locations only)

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

            # Use geocoder to get suggestions with address details
            # Note: Nominatim doesn't have native autocomplete, so we're simulating it
            # by using the geocode function with limit parameter
            logger.debug(f"Getting location suggestions for: {query}")
            # Request addressdetails=True to get country_code for filtering
            locations = self.geolocator.geocode(
                query, exactly_one=False, limit=limit * 2, addressdetails=True
            )

            if not locations:
                logger.debug(f"No suggestions found for query: {query}")
                return []

            # Filter locations based on data source
            filtered_locations = []

            if self.data_source == "nws":
                # Filter for US locations only when using NWS
                for location in locations:
                    if hasattr(location, "raw") and isinstance(location.raw, dict):
                        address_details = location.raw.get("address", {})
                        country_code = address_details.get("country_code", "").lower()

                        if country_code in self.ALLOWED_COUNTRY_CODES:
                            filtered_locations.append(location)
                            if len(filtered_locations) >= limit:
                                break

                if filtered_locations:
                    # Extract the display names from US locations only
                    suggestions = [location.address for location in filtered_locations]
                    logger.debug(
                        f"Found {len(suggestions)} US location suggestions for NWS data source"
                    )
                    return suggestions
                logger.debug(f"No US location suggestions found for query: {query}")
                return []
            # For WeatherAPI or Automatic, allow any location worldwide
            filtered_locations = locations[:limit]  # Just take the first 'limit' locations
            suggestions = [location.address for location in filtered_locations]
            logger.debug(
                f"Found {len(suggestions)} worldwide location suggestions for non-NWS data source"
            )
            return suggestions

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Location suggestion error for '{query}': {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected location suggestion error for '{query}': {str(e)}")
            return []
