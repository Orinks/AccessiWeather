"""
Open-Meteo API wrapper for AccessiWeather.

This module provides the OpenMeteoApiWrapper class that handles Open-Meteo-specific
weather API operations, inheriting from BaseApiWrapper for shared functionality.
"""

import logging
from typing import Any, cast

from accessiweather.api_client import NoaaApiError
from accessiweather.openmeteo_client import (
    OpenMeteoApiClient,
    OpenMeteoApiError,
    OpenMeteoNetworkError,
)

from .base_wrapper import BaseApiWrapper

logger = logging.getLogger(__name__)


class OpenMeteoApiWrapper(BaseApiWrapper):
    """Open-Meteo-specific API wrapper that handles Open-Meteo weather operations."""

    def __init__(self, **kwargs):
        """
        Initialize the Open-Meteo API wrapper.

        Args:
        ----
            **kwargs: Arguments passed to BaseApiWrapper

        """
        super().__init__(**kwargs)

        # Initialize the Open-Meteo client
        self.openmeteo_client = OpenMeteoApiClient(
            user_agent=self.user_agent,
            timeout=30.0,
            max_retries=self.max_retries,
            retry_delay=1.0,
        )

        logger.info(f"Initialized Open-Meteo API wrapper with User-Agent: {self.user_agent}")

    def _map_openmeteo_error(self, error: Exception, lat: float, lon: float) -> NoaaApiError:
        """Map Open-Meteo errors to NoaaApiError for consistency."""
        if isinstance(error, OpenMeteoApiError):
            if "Rate limit" in str(error):
                return NoaaApiError(
                    message=str(error),
                    error_type=NoaaApiError.RATE_LIMIT_ERROR,
                    url=f"Open-Meteo API for {lat},{lon}",
                )
            return NoaaApiError(
                message=str(error),
                error_type=NoaaApiError.API_ERROR,
                url=f"Open-Meteo API for {lat},{lon}",
            )
        if isinstance(error, OpenMeteoNetworkError):
            return NoaaApiError(
                message=str(error),
                error_type=NoaaApiError.NETWORK_ERROR,
                url=f"Open-Meteo API for {lat},{lon}",
            )
        return NoaaApiError(
            message=f"Unexpected Open-Meteo error: {error}",
            error_type=NoaaApiError.UNKNOWN_ERROR,
            url=f"Open-Meteo API for {lat},{lon}",
        )

    # Implementation of abstract methods from BaseApiWrapper
    def get_current_conditions(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """Get current weather conditions for a location using Open-Meteo."""
        force_refresh = kwargs.get("force_refresh", False)
        temperature_unit = kwargs.get("temperature_unit", "fahrenheit")
        wind_speed_unit = kwargs.get("wind_speed_unit", "mph")
        precipitation_unit = kwargs.get("precipitation_unit", "inch")
        model = kwargs.get("model", "best_match")

        logger.info(f"Getting current conditions from Open-Meteo for coordinates: ({lat}, {lon})")

        cache_key = self._generate_cache_key(
            "openmeteo_current",
            {
                "lat": lat,
                "lon": lon,
                "temp_unit": temperature_unit,
                "wind_unit": wind_speed_unit,
                "precip_unit": precipitation_unit,
                "model": model,
            },
        )

        def fetch_data() -> dict[str, Any]:
            self._rate_limit()
            try:
                response = self.openmeteo_client.get_current_weather(
                    latitude=lat,
                    longitude=lon,
                    temperature_unit=temperature_unit,
                    wind_speed_unit=wind_speed_unit,
                    precipitation_unit=precipitation_unit,
                    model=model,
                )
                return self._transform_current_conditions(response)
            except Exception as e:
                logger.error(
                    f"Error getting current conditions from Open-Meteo for {lat},{lon}: {str(e)}"
                )
                raise self._map_openmeteo_error(e, lat, lon) from e

        return cast(dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh))

    def get_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """Get forecast for a location using Open-Meteo."""
        force_refresh = kwargs.get("force_refresh", False)
        days = kwargs.get("days", 7)
        temperature_unit = kwargs.get("temperature_unit", "fahrenheit")
        wind_speed_unit = kwargs.get("wind_speed_unit", "mph")
        precipitation_unit = kwargs.get("precipitation_unit", "inch")
        model = kwargs.get("model", "best_match")

        logger.info(f"Getting forecast from Open-Meteo for coordinates: ({lat}, {lon})")

        cache_key = self._generate_cache_key(
            "openmeteo_forecast",
            {
                "lat": lat,
                "lon": lon,
                "days": days,
                "temp_unit": temperature_unit,
                "wind_unit": wind_speed_unit,
                "precip_unit": precipitation_unit,
                "model": model,
            },
        )

        def fetch_data() -> dict[str, Any]:
            self._rate_limit()
            try:
                response = self.openmeteo_client.get_forecast(
                    latitude=lat,
                    longitude=lon,
                    days=days,
                    temperature_unit=temperature_unit,
                    wind_speed_unit=wind_speed_unit,
                    precipitation_unit=precipitation_unit,
                    model=model,
                )
                return self._transform_forecast(response)
            except Exception as e:
                logger.error(f"Error getting forecast from Open-Meteo for {lat},{lon}: {str(e)}")
                raise self._map_openmeteo_error(e, lat, lon) from e

        return cast(dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh))

    def get_hourly_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """Get hourly forecast for a location using Open-Meteo."""
        force_refresh = kwargs.get("force_refresh", False)
        hours = kwargs.get("hours", 48)
        temperature_unit = kwargs.get("temperature_unit", "fahrenheit")
        wind_speed_unit = kwargs.get("wind_speed_unit", "mph")
        precipitation_unit = kwargs.get("precipitation_unit", "inch")
        model = kwargs.get("model", "best_match")

        logger.info(f"Getting hourly forecast from Open-Meteo for coordinates: ({lat}, {lon})")

        cache_key = self._generate_cache_key(
            "openmeteo_hourly",
            {
                "lat": lat,
                "lon": lon,
                "hours": hours,
                "temp_unit": temperature_unit,
                "wind_unit": wind_speed_unit,
                "precip_unit": precipitation_unit,
                "model": model,
            },
        )

        def fetch_data() -> dict[str, Any]:
            self._rate_limit()
            try:
                response = self.openmeteo_client.get_hourly_forecast(
                    latitude=lat,
                    longitude=lon,
                    hours=hours,
                    temperature_unit=temperature_unit,
                    wind_speed_unit=wind_speed_unit,
                    precipitation_unit=precipitation_unit,
                    model=model,
                )
                return self._transform_hourly_forecast(response)
            except Exception as e:
                logger.error(
                    f"Error getting hourly forecast from Open-Meteo for {lat},{lon}: {str(e)}"
                )
                raise self._map_openmeteo_error(e, lat, lon) from e

        return cast(dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh))

    # Data transformation methods
    def _transform_current_conditions(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform Open-Meteo current conditions to standard format."""
        # Open-Meteo returns data in a specific format, transform it to match expected format
        return {
            "type": "openmeteo_current",
            "data": data,
            "current": data.get("current", {}),
            "current_units": data.get("current_units", {}),
        }

    def _transform_forecast(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform Open-Meteo forecast to standard format."""
        return {
            "type": "openmeteo_forecast",
            "data": data,
            "daily": data.get("daily", {}),
            "daily_units": data.get("daily_units", {}),
        }

    def _transform_hourly_forecast(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform Open-Meteo hourly forecast to standard format."""
        return {
            "type": "openmeteo_hourly",
            "data": data,
            "hourly": data.get("hourly", {}),
            "hourly_units": data.get("hourly_units", {}),
        }

    # Open-Meteo specific methods
    def get_weather_description(self, weather_code: int) -> str:
        """Get weather description from Open-Meteo weather code."""
        return self.openmeteo_client.get_weather_description(weather_code)

    def close(self):
        """Close the Open-Meteo client."""
        if hasattr(self, "openmeteo_client"):
            self.openmeteo_client.close()

    def __del__(self):
        """Clean up resources."""
        self.close()
