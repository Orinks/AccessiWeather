"""Geocoding service for AccessiWeather

This module provides geocoding functionality to convert addresses and zip codes to coordinates.
"""

import logging
import re
from typing import List, Optional, Tuple

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding addresses and zip codes"""

    # Regular expression for US ZIP codes (both 5-digit and ZIP+4 formats)
    ZIP_CODE_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")
    # Allowed country codes (primarily US, potentially add territories later if needed)
    # Nominatim often returns 'us' even for territories like PR, GU.
    ALLOWED_COUNTRY_CODES = ["us"]

    def __init__(self, user_agent: str = "AccessiWeather", timeout: int = 10):
        """Initialize the geocoding service

        Args:
            user_agent: User agent string for API requests
            timeout: Timeout in seconds for geocoding requests
        """
        self.geolocator = Nominatim(user_agent=user_agent, timeout=timeout)

    def is_zip_code(self, text: str) -> bool:
        """Check if the given text is a valid US ZIP code

        Args:
            text: Text to check

        Returns:
            True if the text is a valid US ZIP code, False otherwise
        """
        return bool(self.ZIP_CODE_PATTERN.match(text))

    def format_zip_code(self, zip_code: str) -> str:
        """Format a ZIP code for geocoding

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

    def geocode_address(self, address: str) -> Optional[Tuple[float, float, str]]:
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

            # --- Filter for US NWS Coverage Area ---
            if hasattr(location, "raw") and isinstance(location.raw, dict):
                address_details = location.raw.get("address", {})
                country_code = address_details.get("country_code")

                if country_code and country_code.lower() in self.ALLOWED_COUNTRY_CODES:
                    logger.info(
                        f"Successfully geocoded '{original_query}' to: {location.address} (country_code: {country_code})"
                    )
                    return location.latitude, location.longitude, location.address
                else:
                    logger.warning(
                        f"Location '{location.address}' found for query '{original_query}', "
                        f"but filtered out due to unsupported country_code: '{country_code}'. "
                        f"Only {self.ALLOWED_COUNTRY_CODES} are supported."
                    )
                    return None  # Location outside coverage area
            else:
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

    def validate_coordinates(self, lat: float, lon: float) -> bool:
        """Validate if coordinates are within the US NWS coverage area.

        This method performs a reverse geocoding lookup to determine if the
        given coordinates are within the US.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            True if coordinates are within the US NWS coverage area, False otherwise
        """
        try:
            logger.debug(f"Validating coordinates: ({lat}, {lon})")
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
                else:
                    logger.warning(
                        f"Coordinates ({lat}, {lon}) are outside the US NWS coverage area "
                        f"(country_code: '{country_code}'). Only {self.ALLOWED_COUNTRY_CODES} are supported."
                    )
                    return False
            else:
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

    def suggest_locations(self, query: str, limit: int = 5) -> List[str]:
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

            # Filter for US locations only
            us_locations = []
            for location in locations:
                if hasattr(location, "raw") and isinstance(location.raw, dict):
                    address_details = location.raw.get("address", {})
                    country_code = address_details.get("country_code", "").lower()

                    if country_code in self.ALLOWED_COUNTRY_CODES:
                        us_locations.append(location)
                        if len(us_locations) >= limit:
                            break

            if us_locations:
                # Extract the display names from US locations only
                suggestions = [location.address for location in us_locations]
                logger.debug(f"Found {len(suggestions)} US location suggestions")
                return suggestions
            else:
                logger.debug(f"No US location suggestions found for query: {query}")
                return []

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Location suggestion error for '{query}': {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected location suggestion error for '{query}': {str(e)}")
            return []
