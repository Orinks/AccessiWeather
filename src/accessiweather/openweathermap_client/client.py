"""OpenWeatherMap API client.

This module provides a comprehensive client for the OpenWeatherMap One Call API 3.0
with support for current weather, forecasts, and weather alerts.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from .exceptions import (
    AuthenticationError,
    NotFoundError,
    OpenWeatherMapError,
    RateLimitError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class OpenWeatherMapClient:
    """Client for the OpenWeatherMap One Call API 3.0."""

    BASE_URL = "https://api.openweathermap.org"

    # API endpoints
    CURRENT_WEATHER_ENDPOINT = "/data/2.5/weather"
    ONE_CALL_ENDPOINT = "/data/3.0/onecall"

    # Supported units
    UNITS_METRIC = "metric"
    UNITS_IMPERIAL = "imperial"
    UNITS_STANDARD = "standard"

    # Supported languages (subset of commonly used ones)
    SUPPORTED_LANGUAGES = {"en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh_cn", "zh_tw"}

    def __init__(
        self,
        api_key: str,
        user_agent: str = "AccessiWeather",
        timeout: float = 10.0,
        units: str = UNITS_IMPERIAL,
        language: str = "en",
    ):
        """Initialize the OpenWeatherMap client.

        Args:
            api_key: OpenWeatherMap API key
            user_agent: User agent string for API requests
            timeout: Request timeout in seconds
            units: Units for temperature and other measurements
            language: Language for weather descriptions
        """
        self.api_key = api_key
        self.user_agent = user_agent
        self.timeout = timeout
        self.units = (
            units
            if units in [self.UNITS_METRIC, self.UNITS_IMPERIAL, self.UNITS_STANDARD]
            else self.UNITS_IMPERIAL
        )
        self.language = language if language in self.SUPPORTED_LANGUAGES else "en"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests.

        Returns:
            Dict containing headers for API requests
        """
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def _get_base_params(self) -> Dict[str, str]:
        """Get base parameters for API requests.

        Returns:
            Dict containing base parameters for API requests
        """
        return {
            "appid": self.api_key,
            "units": self.units,
            "lang": self.language,
        }

    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an HTTP request to the OpenWeatherMap API.

        Args:
            endpoint: API endpoint path
            params: Additional query parameters

        Returns:
            JSON response data

        Raises:
            OpenWeatherMapError: If the request fails
        """
        url = f"{self.BASE_URL}{endpoint}"

        # Combine base params with additional params
        request_params = self._get_base_params()
        if params:
            request_params.update(params)

        headers = self._get_headers()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                logger.debug(f"Making request to {url} with params: {request_params}")
                response = client.get(url, headers=headers, params=request_params)

                # Handle different HTTP status codes
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise AuthenticationError("Invalid API key", url=url)
                elif response.status_code == 404:
                    raise NotFoundError("Location not found", url=url)
                elif response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", url=url)
                elif response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", "Invalid request parameters")
                    except Exception:
                        error_msg = "Invalid request parameters"
                    raise ValidationError(error_msg, url=url)
                else:
                    # Handle other error status codes
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", f"HTTP {response.status_code}")
                    except Exception:
                        error_msg = f"HTTP {response.status_code}"

                    if 400 <= response.status_code < 500:
                        error_type = OpenWeatherMapError.CLIENT_ERROR
                    elif 500 <= response.status_code < 600:
                        error_type = OpenWeatherMapError.SERVER_ERROR
                    else:
                        error_type = OpenWeatherMapError.UNKNOWN_ERROR

                    raise OpenWeatherMapError(
                        message=error_msg,
                        status_code=response.status_code,
                        error_type=error_type,
                        url=url,
                    )

        except httpx.TimeoutException as e:
            logger.error(f"Timeout error for {url}: {str(e)}")
            raise OpenWeatherMapError(
                message=f"Request timeout: {str(e)}",
                error_type=OpenWeatherMapError.TIMEOUT_ERROR,
                url=url,
            ) from e
        except httpx.ConnectError as e:
            logger.error(f"Connection error for {url}: {str(e)}")
            raise OpenWeatherMapError(
                message=f"Connection error: {str(e)}",
                error_type=OpenWeatherMapError.CONNECTION_ERROR,
                url=url,
            ) from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {url}: {str(e)}")
            raise OpenWeatherMapError(
                message=f"HTTP error: {str(e)}",
                error_type=OpenWeatherMapError.NETWORK_ERROR,
                url=url,
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {str(e)}")
            raise OpenWeatherMapError(
                message=f"Unexpected error: {str(e)}",
                error_type=OpenWeatherMapError.UNKNOWN_ERROR,
                url=url,
            ) from e

    def get_current_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get current weather conditions for a location.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location

        Returns:
            Dictionary containing current weather data

        Raises:
            OpenWeatherMapError: If the request fails
        """
        params = {
            "lat": lat,
            "lon": lon,
        }

        logger.info(f"Getting current weather for coordinates: ({lat}, {lon})")
        return self._make_request(self.CURRENT_WEATHER_ENDPOINT, params)

    def get_one_call_data(
        self, lat: float, lon: float, exclude: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive weather data using One Call API 3.0.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location
            exclude: Comma-separated list of data blocks to exclude
                    (current, minutely, hourly, daily, alerts)

        Returns:
            Dictionary containing comprehensive weather data

        Raises:
            OpenWeatherMapError: If the request fails
        """
        params: Dict[str, Any] = {
            "lat": lat,
            "lon": lon,
        }

        if exclude:
            params["exclude"] = exclude

        logger.info(f"Getting One Call data for coordinates: ({lat}, {lon})")
        return self._make_request(self.ONE_CALL_ENDPOINT, params)
