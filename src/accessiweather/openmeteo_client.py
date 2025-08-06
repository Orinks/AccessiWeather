"""Open-Meteo API client for AccessiWeather.

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

logger = logging.getLogger(__name__)


class OpenMeteoError(Exception):
    """Base exception for Open-Meteo API errors."""


class OpenMeteoApiError(OpenMeteoError):
    """Exception raised for Open-Meteo API errors."""


class OpenMeteoNetworkError(OpenMeteoError):
    """Exception raised for network-related errors."""


class OpenMeteoApiClient:
    """Client for the Open-Meteo weather API.

    Open-Meteo provides free weather data without requiring an API key.
    It supports current conditions, hourly forecasts, and daily forecasts.
    """

    BASE_URL = "https://api.open-meteo.com/v1"

    def __init__(
        self,
        user_agent: str = "AccessiWeather",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize the Open-Meteo API client.

        Args:
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

    def _make_request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make a request to the Open-Meteo API.

        Args:
            endpoint: API endpoint (e.g., "forecast")
            params: Query parameters

        Returns:
            JSON response as a dictionary

        Raises:
            OpenMeteoApiError: If the API returns an error
            OpenMeteoNetworkError: If there's a network error

        """
        url = f"{self.BASE_URL}/{endpoint}"

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
                )

            except httpx.NetworkError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Network error, retrying in {self.retry_delay}s (attempt {attempt + 1})"
                    )
                    time.sleep(self.retry_delay)
                    continue
                raise OpenMeteoNetworkError(
                    f"Network error after {self.max_retries} retries: {str(e)}"
                )

            except Exception as e:
                if isinstance(e, OpenMeteoApiError | OpenMeteoNetworkError):
                    raise
                raise OpenMeteoApiError(f"Unexpected error: {str(e)}")

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
        """Get current weather conditions for a location.

        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
            temperature_unit: Temperature unit ("celsius" or "fahrenheit")
            wind_speed_unit: Wind speed unit ("kmh", "ms", "mph", "kn")
            precipitation_unit: Precipitation unit ("mm" or "inch")

        Returns:
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
            ],
            "temperature_unit": temperature_unit,
            "wind_speed_unit": wind_speed_unit,
            "precipitation_unit": precipitation_unit,
            "timezone": "auto",
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
        """Get daily forecast for a location.

        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
            days: Number of forecast days (1-16)
            temperature_unit: Temperature unit ("celsius" or "fahrenheit")
            wind_speed_unit: Wind speed unit ("kmh", "ms", "mph", "kn")
            precipitation_unit: Precipitation unit ("mm" or "inch")

        Returns:
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
        """Get hourly forecast for a location.

        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
            hours: Number of forecast hours (max 384 = 16 days)
            temperature_unit: Temperature unit ("celsius" or "fahrenheit")
            wind_speed_unit: Wind speed unit ("kmh", "ms", "mph", "kn")
            precipitation_unit: Precipitation unit ("mm" or "inch")

        Returns:
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
            ],
            "temperature_unit": temperature_unit,
            "wind_speed_unit": wind_speed_unit,
            "precipitation_unit": precipitation_unit,
            "timezone": "auto",
            "forecast_hours": min(hours, 384),  # API supports max 384 hours
        }

        return self._make_request("forecast", params)

    @staticmethod
    def get_weather_description(weather_code: int) -> str:
        """Get weather description from Open-Meteo weather code.

        Args:
            weather_code: Open-Meteo weather code

        Returns:
            Human-readable weather description

        """
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }

        return weather_codes.get(weather_code, f"Unknown weather code: {weather_code}")

    def close(self):
        """Close the HTTP client."""
        if hasattr(self, "client"):
            self.client.close()
