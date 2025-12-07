"""
Open-Meteo API client for AccessiWeather.

This module provides a client for the Open-Meteo weather API, which offers
free weather data without requiring an API key.

LIMITATIONS:
- Open-Meteo does not provide weather alerts/warnings
- For international locations using Open-Meteo, no alert data will be available
- Only current conditions, forecasts, and historical data are supported
"""

import logging
import time
from typing import Any

import httpx

from .weather_client_parsers import weather_code_to_description

logger = logging.getLogger(__name__)


class OpenMeteoError(Exception):
    """Base exception for Open-Meteo API errors."""


class OpenMeteoApiError(OpenMeteoError):
    """Exception raised for Open-Meteo API errors."""


class OpenMeteoNetworkError(OpenMeteoError):
    """Exception raised for network-related errors."""


class OpenMeteoApiClient:
    """
    Client for the Open-Meteo weather API.

    Open-Meteo provides free weather data without requiring an API key.
    It supports current conditions, hourly forecasts, and daily forecasts.
    """

    BASE_URL = "https://api.open-meteo.com/v1"
    ARCHIVE_BASE_URL = "https://archive-api.open-meteo.com/v1"

    def __init__(
        self,
        user_agent: str = "AccessiWeather",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the Open-Meteo API client.

        Args:
        ----
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

    def __del__(self):
        """Clean up the HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    def _make_request(
        self, endpoint: str, params: dict[str, Any], use_archive: bool = False
    ) -> dict[str, Any]:
        """
        Make a request to the Open-Meteo API.

        Args:
        ----
            endpoint: API endpoint (e.g., "forecast", "archive")
            params: Query parameters
            use_archive: If True, use the archive API base URL for historical data

        Returns:
        -------
            JSON response as a dictionary

        Raises:
        ------
            OpenMeteoApiError: If the API returns an error
            OpenMeteoNetworkError: If there's a network error

        """
        base_url = self.ARCHIVE_BASE_URL if use_archive else self.BASE_URL
        url = f"{base_url}/{endpoint}"

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Making request to {url} with params: {params}")
                response = self.client.get(url, params=params)

                # Check for HTTP errors
                if response.status_code == 400:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get("reason", "Bad request")
                    raise OpenMeteoApiError(f"API error: {error_msg}")
                if response.status_code == 429:
                    raise OpenMeteoApiError("Rate limit exceeded")
                if response.status_code >= 500:
                    raise OpenMeteoApiError(f"Server error: {response.status_code}")

                response.raise_for_status()

                # Parse JSON response
                data: dict[str, Any] = response.json()
                logger.debug(f"Received response with keys: {list(data.keys())}")
                return data

            except httpx.TimeoutException as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Request timeout, retrying in {self.retry_delay}s (attempt {attempt + 1})"
                    )
                    time.sleep(self.retry_delay)
                    continue
                raise OpenMeteoNetworkError(
                    f"Request timeout after {self.max_retries} retries: {str(e)}"
                ) from e

            except httpx.NetworkError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Network error, retrying in {self.retry_delay}s (attempt {attempt + 1})"
                    )
                    time.sleep(self.retry_delay)
                    continue
                raise OpenMeteoNetworkError(
                    f"Network error after {self.max_retries} retries: {str(e)}"
                ) from e

            except Exception as e:
                if isinstance(e, OpenMeteoApiError | OpenMeteoNetworkError):
                    raise
                raise OpenMeteoApiError(f"Unexpected error: {str(e)}") from e

        # This should never be reached due to the exception handling above
        raise OpenMeteoApiError("Request failed after all retries")

    def get_current_weather(
        self,
        latitude: float,
        longitude: float,
        temperature_unit: str = "fahrenheit",
        wind_speed_unit: str = "mph",
        precipitation_unit: str = "inch",
    ) -> dict[str, Any]:
        """
        Get current weather conditions for a location.

        Args:
        ----
            latitude: Latitude of the location
            longitude: Longitude of the location
            temperature_unit: Temperature unit ("celsius" or "fahrenheit")
            wind_speed_unit: Wind speed unit ("kmh", "ms", "mph", "kn")
            precipitation_unit: Precipitation unit ("mm" or "inch")

        Returns:
        -------
            Dictionary containing current weather data

        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "is_day",
                "precipitation",
                "weather_code",
                "cloud_cover",
                "pressure_msl",
                "surface_pressure",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "uv_index",
                # Seasonal fields
                "snowfall",
                "snow_depth",
                "visibility",
            ],
            "daily": [
                "sunrise",
                "sunset",
                "uv_index_max",
            ],
            "temperature_unit": temperature_unit,
            "wind_speed_unit": wind_speed_unit,
            "precipitation_unit": precipitation_unit,
            "timezone": "auto",
            "forecast_days": 1,
        }

        return self._make_request("forecast", params)

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = 7,
        temperature_unit: str = "fahrenheit",
        wind_speed_unit: str = "mph",
        precipitation_unit: str = "inch",
    ) -> dict[str, Any]:
        """
        Get daily forecast for a location.

        Args:
        ----
            latitude: Latitude of the location
            longitude: Longitude of the location
            days: Number of forecast days (1-16)
            temperature_unit: Temperature unit ("celsius" or "fahrenheit")
            wind_speed_unit: Wind speed unit ("kmh", "ms", "mph", "kn")
            precipitation_unit: Precipitation unit ("mm" or "inch")

        Returns:
        -------
            Dictionary containing daily forecast data

        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "apparent_temperature_max",
                "apparent_temperature_min",
                "sunrise",
                "sunset",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
                "wind_direction_10m_dominant",
                "uv_index_max",
                "snowfall_sum",
            ],
            "temperature_unit": temperature_unit,
            "wind_speed_unit": wind_speed_unit,
            "precipitation_unit": precipitation_unit,
            "timezone": "auto",
            "forecast_days": min(days, 16),  # API supports max 16 days
        }

        return self._make_request("forecast", params)

    def get_hourly_forecast(
        self,
        latitude: float,
        longitude: float,
        hours: int = 48,
        temperature_unit: str = "fahrenheit",
        wind_speed_unit: str = "mph",
        precipitation_unit: str = "inch",
    ) -> dict[str, Any]:
        """
        Get hourly forecast for a location.

        Args:
        ----
            latitude: Latitude of the location
            longitude: Longitude of the location
            hours: Number of forecast hours (max 384 = 16 days)
            temperature_unit: Temperature unit ("celsius" or "fahrenheit")
            wind_speed_unit: Wind speed unit ("kmh", "ms", "mph", "kn")
            precipitation_unit: Precipitation unit ("mm" or "inch")

        Returns:
        -------
            Dictionary containing hourly forecast data

        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "weather_code",
                "pressure_msl",
                "surface_pressure",
                "cloud_cover",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "is_day",
                "snowfall",
                "uv_index",
                # Seasonal fields
                "snow_depth",
                "freezing_level_height",
                "visibility",
            ],
            "temperature_unit": temperature_unit,
            "wind_speed_unit": wind_speed_unit,
            "precipitation_unit": precipitation_unit,
            "timezone": "auto",
            "forecast_hours": min(hours, 384),  # API supports max 384 hours
        }

        return self._make_request("forecast", params)

    @staticmethod
    def get_weather_description(weather_code: int | str) -> str:
        """
        Get weather description from Open-Meteo weather code.

        Args:
        ----
            weather_code: Open-Meteo weather code

        Returns:
        -------
            Human-readable weather description

        """
        description = weather_code_to_description(weather_code)
        if description is None:
            return "Unknown weather code: None"

        if description.startswith("Weather code "):
            suffix = description.split("Weather code ", 1)[1]
            return f"Unknown weather code: {suffix}"

        return description

    def close(self):
        """Close the HTTP client."""
        if hasattr(self, "client"):
            self.client.close()
