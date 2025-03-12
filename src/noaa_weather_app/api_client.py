"""NOAA Weather API Client

This module provides access to NOAA weather data through their public APIs.
"""

import requests
import json
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class NoaaApiClient:
    """Client for interacting with NOAA Weather API"""
    
    # NOAA Weather API base URL
    BASE_URL = "https://api.weather.gov"
    
    def __init__(self, user_agent: str = "NOAA Weather App"):
        """Initialize the NOAA API client
        
        Args:
            user_agent: User agent string for API requests
        """
        self.user_agent = user_agent
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/geo+json"
        }
    
    def get_point_data(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get metadata about a specific lat/lon point
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Dict containing point metadata
        """
        endpoint = f"{self.BASE_URL}/points/{lat},{lon}"
        return self._make_request(endpoint)
    
    def get_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get forecast for a location
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Dict containing forecast data
        """
        # First get the forecast URL from the point data
        point_data = self.get_point_data(lat, lon)
        forecast_url = point_data.get("properties", {}).get("forecast")
        
        if not forecast_url:
            raise ValueError("Could not find forecast URL in point data")
            
        return self._make_request(forecast_url)
    
    def get_alerts(self, lat: float, lon: float, radius: int = 25) -> Dict[str, Any]:
        """Get active alerts for a location
        
        Args:
            lat: Latitude
            lon: Longitude
            radius: Radius in miles to search for alerts (default: 25)
            
        Returns:
            Dict containing alert data
        """
        endpoint = f"{self.BASE_URL}/alerts/active"
        params = {"point": f"{lat},{lon}", "radius": radius}
        return self._make_request(endpoint, params=params)
    
    def get_discussion(self, lat: float, lon: float) -> Optional[str]:
        """Get the forecast discussion for a location
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Text of the forecast discussion or None if not available
        """
        point_data = self.get_point_data(lat, lon)
        office_id = point_data.get("properties", {}).get("gridId")
        
        if not office_id:
            raise ValueError("Could not find office ID in point data")
            
        # Get the forecast discussion product
        endpoint = f"{self.BASE_URL}/products/types/AFD/locations/{office_id}"
        products = self._make_request(endpoint)
        
        # Get the latest discussion
        try:
            latest_product_id = products.get("@graph", [])[0].get("id")
            product = self._make_request(f"{self.BASE_URL}/products/{latest_product_id}")
            return product.get("productText")
        except (IndexError, KeyError):
            logger.warning(f"Could not find forecast discussion for {office_id}")
            return None
    
    def _make_request(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a request to the NOAA API
        
        Args:
            url: The URL to request
            params: Query parameters
            
        Returns:
            Dict containing response data
        """
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise ConnectionError(f"Failed to connect to NOAA API: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in API request: {str(e)}")
            raise ConnectionError(f"Failed to connect to NOAA API: {str(e)}")
