"""Weather data retrieval for WeatherService.

This module handles the main weather data retrieval methods including
forecast, hourly forecast, current conditions, and observation stations.
"""

import logging
from typing import Any

from accessiweather.api_client import ApiClientError, NoaaApiClient, NoaaApiError
from accessiweather.api_wrapper import NoaaApiWrapper
from accessiweather.openmeteo_client import OpenMeteoError

logger = logging.getLogger(__name__)


class WeatherDataRetrieval:
    """Handles weather data retrieval operations."""

    def __init__(
        self,
        nws_client: NoaaApiClient | NoaaApiWrapper,
        api_client_manager,  # Type hint would create circular import
        fallback_handler,  # Type hint would create circular import
    ):
        """Initialize the weather data retrieval handler.

        Args:
            nws_client: The NWS API client
            api_client_manager: The API client manager instance
            fallback_handler: The fallback handler instance

        """
        self.nws_client = nws_client
        self.api_client_manager = api_client_manager
        self.fallback_handler = fallback_handler

    def get_forecast(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """Get forecast data for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing forecast data.

        Raises:
            ApiClientError: If there was an error retrieving the forecast.

        """
        try:
            logger.info(f"Getting forecast for coordinates: ({lat}, {lon})")

            # Determine which API to use based on configuration and location
            if self.api_client_manager._should_use_openmeteo(lat, lon):
                logger.info("Using Open-Meteo API for forecast")
                try:
                    # Get user's temperature preference
                    temp_unit = self.api_client_manager._get_temperature_unit_preference()
                    # Get forecast from Open-Meteo with user's preferred units
                    openmeteo_data = self.api_client_manager.openmeteo_client.get_forecast(
                        lat, lon, temperature_unit=temp_unit
                    )
                    # Transform to NWS-compatible format
                    return self.api_client_manager.openmeteo_mapper.map_forecast(openmeteo_data)  # type: ignore[no-any-return]
                except (OpenMeteoError, Exception) as e:
                    logger.warning(f"Open-Meteo API failed for forecast: {str(e)}")
                    # Try fallback to NWS if location is in US
                    fallback_result = self.fallback_handler.try_fallback_api(
                        lat, lon, "get_forecast", force_refresh=force_refresh
                    )
                    if fallback_result:
                        return fallback_result  # type: ignore[no-any-return]
                    raise ApiClientError(f"Open-Meteo failed and no fallback available: {str(e)}")
            else:
                logger.info("Using NWS API for forecast")
                try:
                    return self.nws_client.get_forecast(lat, lon, force_refresh=force_refresh)
                except (NoaaApiError, Exception) as e:
                    logger.warning(f"NWS API failed for forecast: {str(e)}")
                    # Try fallback to Open-Meteo
                    fallback_result = self.fallback_handler.try_fallback_api(
                        lat, lon, "get_forecast"
                    )
                    if fallback_result:
                        return fallback_result  # type: ignore[no-any-return]
                    # Re-raise the original NWS error
                    if isinstance(e, NoaaApiError):
                        raise
                    raise ApiClientError(f"NWS failed and Open-Meteo fallback failed: {str(e)}")

        except ApiClientError:
            # Re-raise API client errors directly
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast data: {str(e)}")

    def get_hourly_forecast(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> dict[str, Any]:
        """Get hourly forecast data for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing hourly forecast data.

        Raises:
            ApiClientError: If there was an error retrieving the hourly forecast.

        """
        try:
            logger.info(f"Getting hourly forecast for coordinates: ({lat}, {lon})")

            # Determine which API to use based on configuration and location
            if self.api_client_manager._should_use_openmeteo(lat, lon):
                logger.info("Using Open-Meteo API for hourly forecast")
                try:
                    # Get user's temperature preference
                    temp_unit = self.api_client_manager._get_temperature_unit_preference()
                    # Get hourly forecast from Open-Meteo with user's preferred units
                    openmeteo_data = self.api_client_manager.openmeteo_client.get_hourly_forecast(
                        lat, lon, temperature_unit=temp_unit
                    )
                    # Transform to NWS-compatible format
                    return self.api_client_manager.openmeteo_mapper.map_hourly_forecast(  # type: ignore[no-any-return]
                        openmeteo_data
                    )
                except (OpenMeteoError, Exception) as e:
                    logger.warning(f"Open-Meteo API failed for hourly forecast: {str(e)}")
                    # Try fallback to NWS if location is in US
                    fallback_result = self.fallback_handler.try_fallback_api(
                        lat, lon, "get_hourly_forecast", force_refresh=force_refresh
                    )
                    if fallback_result:
                        return fallback_result  # type: ignore[no-any-return]
                    raise ApiClientError(f"Open-Meteo failed and no fallback available: {str(e)}")
            else:
                logger.info("Using NWS API for hourly forecast")
                try:
                    return self.nws_client.get_hourly_forecast(
                        lat, lon, force_refresh=force_refresh
                    )
                except (NoaaApiError, Exception) as e:
                    logger.warning(f"NWS API failed for hourly forecast: {str(e)}")
                    # Try fallback to Open-Meteo
                    fallback_result = self.fallback_handler.try_fallback_api(
                        lat, lon, "get_hourly_forecast"
                    )
                    if fallback_result:
                        return fallback_result  # type: ignore[no-any-return]
                    # Re-raise the original NWS error
                    if isinstance(e, NoaaApiError):
                        raise
                    raise ApiClientError(f"NWS failed and Open-Meteo fallback failed: {str(e)}")

        except ApiClientError:
            # Re-raise API client errors directly
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting hourly forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve hourly forecast data: {str(e)}")

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """Get observation stations for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing observation stations data.

        Raises:
            ApiClientError: If there was an error retrieving the stations.

        """
        try:
            logger.info(f"Getting observation stations for coordinates: ({lat}, {lon})")
            # Always use NWS for stations
            return self.nws_client.get_stations(lat, lon, force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error getting observation stations: {str(e)}")
            raise ApiClientError(f"Unable to retrieve observation stations data: {str(e)}")

    def get_current_conditions(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> dict[str, Any]:
        """Get current weather conditions for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing current weather conditions.

        Raises:
            ApiClientError: If there was an error retrieving the current conditions.

        """
        try:
            logger.info(f"Getting current conditions for coordinates: ({lat}, {lon})")

            # Determine which API to use based on configuration and location
            if self.api_client_manager._should_use_openmeteo(lat, lon):
                logger.info("Using Open-Meteo API for current conditions")
                try:
                    # Get user's temperature preference
                    temp_unit = self.api_client_manager._get_temperature_unit_preference()
                    # Get current conditions from Open-Meteo with user's preferred units
                    openmeteo_data = self.api_client_manager.openmeteo_client.get_current_weather(
                        lat, lon, temperature_unit=temp_unit
                    )
                    # Transform to NWS-compatible format
                    return self.api_client_manager.openmeteo_mapper.map_current_conditions(  # type: ignore[no-any-return]
                        openmeteo_data
                    )
                except (OpenMeteoError, Exception) as e:
                    logger.warning(f"Open-Meteo API failed for current conditions: {str(e)}")
                    # Try fallback to NWS if location is in US
                    fallback_result = self.fallback_handler.try_fallback_api(
                        lat, lon, "get_current_conditions", force_refresh=force_refresh
                    )
                    if fallback_result:
                        return fallback_result  # type: ignore[no-any-return]
                    raise ApiClientError(f"Open-Meteo failed and no fallback available: {str(e)}")
            else:
                logger.info("Using NWS API for current conditions")
                try:
                    return self.nws_client.get_current_conditions(
                        lat, lon, force_refresh=force_refresh
                    )
                except (NoaaApiError, Exception) as e:
                    logger.warning(f"NWS API failed for current conditions: {str(e)}")
                    # Try fallback to Open-Meteo
                    fallback_result = self.fallback_handler.try_fallback_api(
                        lat, lon, "get_current_conditions"
                    )
                    if fallback_result:
                        return fallback_result  # type: ignore[no-any-return]
                    # Re-raise the original NWS error
                    if isinstance(e, NoaaApiError):
                        raise
                    raise ApiClientError(f"NWS failed and Open-Meteo fallback failed: {str(e)}")

        except ApiClientError:
            # Re-raise API client errors directly
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting current conditions: {str(e)}")
            raise ApiClientError(f"Unable to retrieve current conditions data: {str(e)}")
