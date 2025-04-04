"""Geocoding service for AccessiWeather.

This module provides geocoding functionality to convert addresses/zip codes
to coordinates.
"""

import logging
from typing import List, Optional, Tuple

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding addresses and zip codes."""

    def __init__(self, user_agent: str = "AccessiWeather"):
        """Initialize the geocoding service.

        Args:
            user_agent: User agent string for API requests
        """
        self.geolocator = Nominatim(user_agent=user_agent)

    def geocode_address(self, address: str) -> Optional[Tuple[float, float, str]]:
        """Convert an address or zip code to coordinates.

        Args:
            address: Address or zip code to geocode

        Returns:
            Tuple of (latitude, longitude, display_name) if successful,
            None otherwise
        """
        try:
            # Check if it's possibly a US zip code (5 digits)
            if address.isdigit() and len(address) == 5:
                # Add USA to improve geocoding accuracy for zip codes
                address = f"{address}, USA"

            location = self.geolocator.geocode(address)
            if location:
                return location.latitude, location.longitude, location.address
            return None
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Geocoding error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected geocoding error: {str(e)}")
            return None

    def suggest_locations(self, query: str, limit: int = 5) -> List[str]:
        """Suggest location completions based on partial input.

        Args:
            query: Partial address or location name
            limit: Maximum number of suggestions to return

        Returns:
            List of suggested location strings
        """
        try:
            if not query or len(query) < 2:
                return []

            # Use geocoder to get suggestions
            # Note: Nominatim doesn't have native autocomplete, so we simulate
            # it by using the geocode function with limit parameter
            locations = self.geolocator.geocode(query, exactly_one=False, limit=limit)

            if locations:
                # Extract the display names
                return [location.address for location in locations]
            return []
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Location suggestion error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected location suggestion error: {str(e)}")
            return []
