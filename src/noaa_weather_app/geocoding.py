"""Geocoding service for NOAA Weather App

This module provides geocoding functionality to convert addresses and zip codes to coordinates.
"""

import logging
from typing import Optional, Tuple, Dict, Any
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

logger = logging.getLogger(__name__)

class GeocodingService:
    """Service for geocoding addresses and zip codes"""
    
    def __init__(self, user_agent: str = "NOAA Weather App"):
        """Initialize the geocoding service
        
        Args:
            user_agent: User agent string for API requests
        """
        self.geolocator = Nominatim(user_agent=user_agent)
    
    def geocode_address(self, address: str) -> Optional[Tuple[float, float, str]]:
        """Convert an address or zip code to coordinates
        
        Args:
            address: Address or zip code to geocode
            
        Returns:
            Tuple of (latitude, longitude, display_name) if successful, None otherwise
        """
        try:
            # Check if it's possibly a US zip code (5 digits)
            if address.isdigit() and len(address) == 5:
                address = f"{address}, USA"  # Add USA to improve geocoding accuracy for zip codes
                
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
