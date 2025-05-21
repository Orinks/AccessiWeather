"""WeatherAPI.com client implementation.

This module provides a client for the WeatherAPI.com API.
"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class WeatherApiClient:
    """Client for the WeatherAPI.com API."""

    BASE_URL = "https://api.weatherapi.com/v1"

    def __init__(
        self,
        api_key: str,
        user_agent: str = "AccessiWeather",
        timeout: float = 10.0,
    ):
        """Initialize the WeatherAPI.com client.

        Args:
            api_key: WeatherAPI.com API key
            user_agent: User agent string for API requests
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.user_agent = user_agent
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests.

        Returns:
            Dict containing headers for API requests
        """
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def _get_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get parameters for API requests.

        Args:
            params: Additional parameters for the request

        Returns:
            Dict containing parameters for API requests
        """
        # Start with the API key
        request_params = {"key": self.api_key}

        # Add additional parameters if provided
        if params:
            request_params.update(params)

        return request_params

    async def _request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the WeatherAPI.com API.

        Args:
            endpoint: API endpoint (e.g., "current.json")
            params: Additional parameters for the request

        Returns:
            Dict containing the response data

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        headers = self._get_headers()
        request_params = self._get_params(params)

        logger.debug(f"Making request to {url} with params: {request_params}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers, params=request_params)
            response.raise_for_status()
            result = response.json()
            return result if result else {}

    def _request_sync(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a synchronous request to the WeatherAPI.com API.

        Args:
            endpoint: API endpoint (e.g., "current.json")
            params: Additional parameters for the request

        Returns:
            Dict containing the response data

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        headers = self._get_headers()
        request_params = self._get_params(params)

        logger.debug(f"Making request to {url} with params: {request_params}")

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=headers, params=request_params)
            response.raise_for_status()
            result = response.json()
            return result if result else {}

    async def get_current(self, location: str) -> Dict[str, Any]:
        """Get current weather for a location.

        Args:
            location: Location to get weather for (city name, lat/lon, etc.)

        Returns:
            Dict containing current weather data
        """
        return await self._request("current.json", {"q": location})

    def get_current_sync(self, location: str) -> Dict[str, Any]:
        """Get current weather for a location (synchronous).

        Args:
            location: Location to get weather for (city name, lat/lon, etc.)

        Returns:
            Dict containing current weather data
        """
        return self._request_sync("current.json", {"q": location})

    async def get_forecast(
        self, location: str, days: int = 1, aqi: bool = False, alerts: bool = False
    ) -> Dict[str, Any]:
        """Get weather forecast for a location.

        Args:
            location: Location to get weather for (city name, lat/lon, etc.)
            days: Number of days of forecast (1-14)
            aqi: Include air quality data
            alerts: Include weather alerts

        Returns:
            Dict containing forecast weather data
        """
        params = {
            "q": location,
            "days": days,
            "aqi": "yes" if aqi else "no",
            "alerts": "yes" if alerts else "no",
        }
        return await self._request("forecast.json", params)

    def get_forecast_sync(
        self, location: str, days: int = 1, aqi: bool = False, alerts: bool = False
    ) -> Dict[str, Any]:
        """Get weather forecast for a location (synchronous).

        Args:
            location: Location to get weather for (city name, lat/lon, etc.)
            days: Number of days of forecast (1-14)
            aqi: Include air quality data
            alerts: Include weather alerts

        Returns:
            Dict containing forecast weather data
        """
        params = {
            "q": location,
            "days": days,
            "aqi": "yes" if aqi else "no",
            "alerts": "yes" if alerts else "no",
        }
        return self._request_sync("forecast.json", params)

    async def search(self, query: str) -> Dict[str, Any]:
        """Search for locations.

        Args:
            query: Search query

        Returns:
            Dict containing search results
        """
        return await self._request("search.json", {"q": query})

    def search_sync(self, query: str) -> Dict[str, Any]:
        """Search for locations (synchronous).

        Args:
            query: Search query

        Returns:
            Dict containing search results
        """
        return self._request_sync("search.json", {"q": query})
