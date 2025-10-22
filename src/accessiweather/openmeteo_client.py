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
from datetime import date as _date
from typing import Any

import httpx

from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.api.default import (
    get_archive,
    get_forecast,
)
from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.client import (
    Client as GeneratedOpenMeteoClient,
)
from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.get_archive_temperature_unit import (
    GetArchiveTemperatureUnit,
)
from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.get_forecast_precipitation_unit import (
    GetForecastPrecipitationUnit,
)
from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.get_forecast_temperature_unit import (
    GetForecastTemperatureUnit,
)
from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.get_forecast_wind_speed_unit import (
    GetForecastWindSpeedUnit,
)
from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.open_meteo_error import (
    OpenMeteoError as GeneratedOpenMeteoError,
)
from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.types import (
    UNSET,
)
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

    def __init__(
        self,
        user_agent: str = "AccessiWeather",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        use_generated_models: bool = False,
    ):
        """
        Initialize the Open-Meteo API client.

        Args:
        ----
            user_agent: User agent string for API requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds
            use_generated_models: When True, normalise responses using the generated
                OpenAPI models before handing them to parsers

        """
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_generated_models = use_generated_models

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
        """
        Make a request to the Open-Meteo API.

        Args:
        ----
            endpoint: API endpoint (e.g., "forecast")
            params: Query parameters

        Returns:
        -------
            JSON response as a dictionary

        Raises:
        ------
            OpenMeteoApiError: If the API returns an error
            OpenMeteoNetworkError: If there's a network error

        """
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug("Calling Open-Meteo %s with params: %s", endpoint, params)
                if endpoint == "forecast":
                    data = self._request_forecast(params)
                elif endpoint == "archive":
                    data = self._request_archive(params)
                else:
                    raise OpenMeteoApiError(f"Unsupported Open-Meteo endpoint: {endpoint}")

                logger.debug(
                    "Received Open-Meteo %s response keys: %s", endpoint, list(data.keys())
                )
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

    @staticmethod
    def _csv_or_unset(value: Any) -> Any:
        if value is None:
            return UNSET
        if isinstance(value, list | tuple):
            filtered = [str(item) for item in value if item is not None]
            return UNSET if not filtered else ",".join(filtered)
        return value

    @staticmethod
    def _map_temperature_unit(value: Any):
        if value is None:
            return UNSET
        try:
            return GetForecastTemperatureUnit(str(value))
        except ValueError:
            logger.debug("Unsupported temperature unit: %s", value)
            return UNSET

    @staticmethod
    def _map_wind_speed_unit(value: Any):
        if value is None:
            return UNSET
        try:
            return GetForecastWindSpeedUnit(str(value))
        except ValueError:
            logger.debug("Unsupported wind speed unit: %s", value)
            return UNSET

    @staticmethod
    def _map_precipitation_unit(value: Any):
        if value is None:
            return UNSET
        try:
            return GetForecastPrecipitationUnit(str(value))
        except ValueError:
            logger.debug("Unsupported precipitation unit: %s", value)
            return UNSET

    def _request_forecast(self, params: dict[str, Any]) -> dict[str, Any]:
        with GeneratedOpenMeteoClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        ) as client:
            result = get_forecast.sync(
                client=client,
                latitude=float(params["latitude"]),
                longitude=float(params["longitude"]),
                current=self._csv_or_unset(params.get("current")),
                hourly=self._csv_or_unset(params.get("hourly")),
                daily=self._csv_or_unset(params.get("daily")),
                temperature_unit=self._map_temperature_unit(params.get("temperature_unit")),
                wind_speed_unit=self._map_wind_speed_unit(params.get("wind_speed_unit")),
                precipitation_unit=self._map_precipitation_unit(params.get("precipitation_unit")),
                timezone=params.get("timezone", UNSET) or UNSET,
                forecast_days=params.get("forecast_days", UNSET),
                forecast_hours=params.get("forecast_hours", UNSET),
            )

        if result is None:
            raise OpenMeteoApiError("Empty response from Open-Meteo forecast endpoint")
        if isinstance(result, GeneratedOpenMeteoError):
            reason = result.reason or result.error or "Unknown Open-Meteo error"
            raise OpenMeteoApiError(reason)

        return result.to_dict()

    def _request_archive(self, params: dict[str, Any]) -> dict[str, Any]:
        start_date = _date.fromisoformat(params["start_date"])
        end_date = _date.fromisoformat(params["end_date"])

        daily_values = params.get("daily")
        daily = self._csv_or_unset(daily_values)

        temperature_unit = params.get("temperature_unit")
        temp_enum = UNSET
        if temperature_unit is not None:
            try:
                temp_enum = GetArchiveTemperatureUnit(str(temperature_unit))
            except ValueError:
                logger.debug("Unsupported archive temperature unit: %s", temperature_unit)
                temp_enum = UNSET

        with GeneratedOpenMeteoClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        ) as client:
            result = get_archive.sync(
                client=client,
                latitude=float(params["latitude"]),
                longitude=float(params["longitude"]),
                start_date=start_date,
                end_date=end_date,
                daily=daily,
                temperature_unit=temp_enum,
                timezone=params.get("timezone", UNSET) or UNSET,
            )

        if result is None:
            raise OpenMeteoApiError("Empty response from Open-Meteo archive endpoint")
        if isinstance(result, GeneratedOpenMeteoError):
            reason = result.reason or result.error or "Unknown Open-Meteo error"
            raise OpenMeteoApiError(reason)

        return result.to_dict()

    def _coerce_with_generated_model(
        self, endpoint: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalise payloads using the generated models (retained for compatibility)."""
        try:
            if endpoint == "forecast":
                from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.forecast_response import (
                    ForecastResponse,
                )

                return ForecastResponse.from_dict(payload).to_dict()

            if endpoint == "archive":
                from .open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.archive_response import (
                    ArchiveResponse,
                )

                return ArchiveResponse.from_dict(payload).to_dict()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to normalise Open-Meteo %s payload: %s", endpoint, exc)
        return payload

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
            ],
            "daily": [
                "sunrise",
                "sunset",
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
