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
    ZIP_CODE_PATTERN = re.compile(r'^\d{5}(?:-\d{4})?$')

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
        if '-' in zip_code:
            zip_code = zip_code.split('-')[0]

        # Add USA to improve geocoding accuracy
        return f"{zip_code}, USA"

    def geocode_address(self, address: str) -> Optional[Tuple[float, float, str]]:
        """Convert an address or zip code to coordinates

        Args:
            address: Address or zip code to geocode

        Returns:
            Tuple of (latitude, longitude, display_name) if successful, None otherwise
        """
        try:
            # Clean up the address string
            address = address.strip()

            # Check if it's a US zip code (5-digit or ZIP+4 format)
            if self.is_zip_code(address):
                logger.info(f"Detected ZIP code format: {address}")
                address = self.format_zip_code(address)
                logger.info(f"Formatted for geocoding as: {address}")

            # Attempt geocoding with increased timeout
            logger.debug(f"Geocoding address: {address}")
            location = self.geolocator.geocode(address)

            if location:
                logger.info(f"Successfully geocoded to: {location.address}")
                return location.latitude, location.longitude, location.address

            logger.warning(f"No results found for address: {address}")
            return None
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Geocoding error for '{address}': {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected geocoding error for '{address}': {str(e)}")
            return None

    def suggest_locations(self, query: str, limit: int = 5) -> List[str]:
        """Suggest location completions based on partial input

        Args:
            query: Partial address or location name
            limit: Maximum number of suggestions to return

        Returns:
            List of suggested location strings
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
            # Note: Nominatim doesn't have native autocomplete, so we're simulating it
            # by using the geocode function with limit parameter
            logger.debug(f"Getting location suggestions for: {query}")
            locations = self.geolocator.geocode(query, exactly_one=False, limit=limit)

            if locations:
                # Extract the display names
                suggestions = [location.address for location in locations]
                logger.debug(f"Found {len(suggestions)} suggestions")
                return suggestions

            logger.debug(f"No suggestions found for query: {query}")
            return []
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Location suggestion error for '{query}': {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected location suggestion error for '{query}': {str(e)}")
            return []
