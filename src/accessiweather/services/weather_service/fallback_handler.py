"""Fallback API handling for WeatherService.

This module handles API fallback logic when the primary API fails,
providing resilient weather data retrieval.
"""

import logging
from typing import Any, cast

from accessiweather.api_client import NoaaApiClient
from accessiweather.api_wrapper import NoaaApiWrapper
from accessiweather.openmeteo_client import OpenMeteoApiClient
from accessiweather.openmeteo_mapper import OpenMeteoMapper

logger = logging.getLogger(__name__)


class FallbackHandler:
    """Handles API fallback logic for weather services."""

    def __init__(
        self,
        nws_client: NoaaApiClient | NoaaApiWrapper,
        openmeteo_client: OpenMeteoApiClient,
        openmeteo_mapper: OpenMeteoMapper,
        api_client_manager,  # Type hint would create circular import
    ):
        """Initialize the fallback handler.

        Args:
            nws_client: The NWS API client
            openmeteo_client: The Open-Meteo API client
            openmeteo_mapper: The Open-Meteo data mapper
            api_client_manager: The API client manager instance

        """
        self.nws_client = nws_client
        self.openmeteo_client = openmeteo_client
        self.openmeteo_mapper = openmeteo_mapper
        self.api_client_manager = api_client_manager

    def try_fallback_api(
        self, lat: float, lon: float, method_name: str, *args, **kwargs
    ) -> dict[str, Any] | None:
        """Try fallback API when the primary API fails.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location
            method_name: Name of the method to call on the fallback API
            *args: Additional arguments to pass to the method
            **kwargs: Additional keyword arguments to pass to the method

        Returns:
            Dictionary containing the fallback API response, or None if fallback fails

        """
        try:
            # If we were using Open-Meteo and it failed, try NWS if location is in US
            if self.api_client_manager._should_use_openmeteo(lat, lon):
                if self.api_client_manager._is_location_in_us(lat, lon):
                    logger.info(f"Open-Meteo failed, trying NWS fallback for {method_name}")
                    method = getattr(self.nws_client, method_name, None)
                    if method:
                        result = method(lat, lon, *args, **kwargs)
                        return cast(dict[str, Any], result)
                    logger.warning(f"NWS client does not have method {method_name}")
                    return None
                logger.warning(
                    f"Open-Meteo failed for non-US location, no fallback available for {method_name}"
                )
                return None
            # If we were using NWS and it failed, try Open-Meteo as fallback
            logger.info(f"NWS failed, trying Open-Meteo fallback for {method_name}")
            if method_name == "get_forecast":
                temp_unit = self.api_client_manager._get_temperature_unit_preference()
                openmeteo_data = self.openmeteo_client.get_forecast(
                    lat, lon, temperature_unit=temp_unit
                )
                return self.openmeteo_mapper.map_forecast(openmeteo_data)
            if method_name == "get_hourly_forecast":
                temp_unit = self.api_client_manager._get_temperature_unit_preference()
                openmeteo_data = self.openmeteo_client.get_hourly_forecast(
                    lat, lon, temperature_unit=temp_unit
                )
                return self.openmeteo_mapper.map_hourly_forecast(openmeteo_data)
            if method_name == "get_current_conditions":
                temp_unit = self.api_client_manager._get_temperature_unit_preference()
                openmeteo_data = self.openmeteo_client.get_current_weather(
                    lat, lon, temperature_unit=temp_unit
                )
                return self.openmeteo_mapper.map_current_conditions(openmeteo_data)
            logger.warning(f"No Open-Meteo fallback available for {method_name}")
            return None

        except Exception as e:
            logger.error(f"Fallback API also failed for {method_name}: {str(e)}")
            return None
