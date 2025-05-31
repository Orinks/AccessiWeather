"""Weather service for AccessiWeather.

This module provides a service layer for weather-related operations,
separating business logic from UI concerns.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union

from accessiweather.api_client import ApiClientError, NoaaApiClient, NoaaApiError
from accessiweather.api_wrapper import NoaaApiWrapper
from accessiweather.gui.settings_dialog import (
    DATA_SOURCE_AUTO,
    DATA_SOURCE_NWS,
    DATA_SOURCE_OPENMETEO,
)
from accessiweather.openmeteo_client import OpenMeteoApiClient, OpenMeteoError
from accessiweather.openmeteo_mapper import OpenMeteoMapper
from accessiweather.services.national_discussion_scraper import NationalDiscussionScraper

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""

    pass


class WeatherService:
    """Service for weather-related operations."""

    def __init__(
        self,
        nws_client: Union[NoaaApiClient, NoaaApiWrapper],
        openmeteo_client: Optional[OpenMeteoApiClient] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the weather service.

        Args:
            nws_client: The NWS API client to use for weather data retrieval.
            openmeteo_client: The Open-Meteo API client to use for international weather data.
            config: Configuration dictionary containing settings like data_source.
        """
        self.nws_client = nws_client
        self.openmeteo_client = openmeteo_client or OpenMeteoApiClient()
        self.openmeteo_mapper = OpenMeteoMapper()
        self.config = config or {}
        self.national_scraper = NationalDiscussionScraper(request_delay=1.0)
        self.national_data_cache: Optional[Dict[str, Dict[str, str]]] = None
        self.national_data_timestamp: float = 0.0
        self.cache_expiry = 3600  # 1 hour in seconds

    def _get_temperature_unit_preference(self) -> str:
        """Get the user's temperature unit preference for Open-Meteo API calls.

        Returns:
            str: "celsius" or "fahrenheit" for Open-Meteo API
        """
        from accessiweather.gui.settings_dialog import (
            DEFAULT_TEMPERATURE_UNIT,
            TEMPERATURE_UNIT_KEY,
        )
        from accessiweather.utils.temperature_utils import TemperatureUnit

        settings = self.config.get("settings", {})
        unit_pref = settings.get(TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT)

        # Convert to Open-Meteo API format
        if unit_pref == TemperatureUnit.CELSIUS.value:
            return "celsius"
        else:
            # Default to fahrenheit for both "fahrenheit" and "both" preferences
            return "fahrenheit"

    def get_national_forecast_data(self, force_refresh: bool = False) -> dict:
        """Get nationwide forecast data, including national discussion summaries.

        Args:
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dictionary containing national forecast data with structure:
            {
                "national_discussion_summaries": {
                    "wpc": {
                        "short_range_summary": str,
                        "short_range_full": str
                    },
                    "spc": {
                        "day1_summary": str,
                        "day1_full": str
                    },
                    "attribution": str
                }
            }

        Raises:
            ApiClientError: If there was an error retrieving the data
        """
        current_time = time.time()

        # Check if we have cached data that's still valid and not forcing refresh
        if (
            not force_refresh
            and self.national_data_cache
            and current_time - self.national_data_timestamp < self.cache_expiry
        ):
            logger.info("Using cached nationwide forecast data")
            return {"national_discussion_summaries": self.national_data_cache}

        try:
            logger.info("Getting nationwide forecast data from scraper")
            # Fetch fresh data from the scraper
            national_data = self.national_scraper.fetch_all_discussions()

            # Update cache
            self.national_data_cache = national_data
            self.national_data_timestamp = current_time

            return {"national_discussion_summaries": national_data}
        except Exception as e:
            logger.error(f"Error getting nationwide forecast data: {str(e)}")

            # If we have cached data, return it even if expired
            if self.national_data_cache:
                logger.info("Returning cached national data due to fetch error")
                return {"national_discussion_summaries": self.national_data_cache}

            # Otherwise, raise an error
            raise ApiClientError(f"Unable to retrieve nationwide forecast data: {str(e)}")

    def _get_data_source(self) -> str:
        """Get the configured data source.

        Returns:
            String indicating which data source to use ('nws', 'openmeteo', or 'auto')
        """
        data_source = self.config.get("settings", {}).get("data_source", DATA_SOURCE_NWS)
        logger.debug(
            f"_get_data_source: config={self.config.get('settings', {})}, data_source={data_source}"
        )
        return str(data_source)

    def _is_location_in_us(self, lat: float, lon: float) -> bool:
        """Check if a location is within the United States.

        This method uses the geocoding service to determine if the given coordinates
        are within the United States.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            True if the location is within the US, False otherwise
        """
        from accessiweather.geocoding import GeocodingService

        # Create a geocoding service instance with the correct data source
        # Using 'auto' as data source to ensure it doesn't filter based on data source
        # but only on the explicit us_only parameter
        geocoding_service = GeocodingService(
            user_agent="AccessiWeather-WeatherService", data_source="auto"
        )

        # Use the validate_coordinates method to check if the location is in the US
        # Explicitly set us_only=True to check for US location regardless of data source
        is_us = geocoding_service.validate_coordinates(lat, lon, us_only=True)
        logger.debug(f"Location ({lat}, {lon}) is {'in' if is_us else 'not in'} the US")
        return is_us

    def _should_use_openmeteo(self, lat: float, lon: float) -> bool:
        """Determine if Open-Meteo should be used for the given location.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location

        Returns:
            True if Open-Meteo should be used, False if NWS should be used
        """
        data_source = self._get_data_source()
        logger.debug(f"_should_use_openmeteo: data_source={data_source}, lat={lat}, lon={lon}")

        # If Open-Meteo is explicitly selected, always use it
        if data_source == DATA_SOURCE_OPENMETEO:
            logger.debug("_should_use_openmeteo: Open-Meteo explicitly selected")
            return True

        # If Automatic mode is selected, use Open-Meteo for non-US locations
        if data_source == DATA_SOURCE_AUTO:
            # Check if location is in the US
            is_us_location = self._is_location_in_us(lat, lon)
            logger.debug(f"_should_use_openmeteo: Automatic mode, is_us_location={is_us_location}")
            return not is_us_location

        # Default to NWS
        logger.debug("_should_use_openmeteo: Defaulting to NWS API")
        return False

    def _try_fallback_api(
        self, lat: float, lon: float, method_name: str, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
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
            if self._should_use_openmeteo(lat, lon):
                if self._is_location_in_us(lat, lon):
                    logger.info(f"Open-Meteo failed, trying NWS fallback for {method_name}")
                    method = getattr(self.nws_client, method_name, None)
                    if method:
                        return method(lat, lon, *args, **kwargs)
                    else:
                        logger.warning(f"NWS client does not have method {method_name}")
                        return None
                else:
                    logger.warning(
                        f"Open-Meteo failed for non-US location, no fallback available for {method_name}"
                    )
                    return None
            else:
                # If we were using NWS and it failed, try Open-Meteo as fallback
                logger.info(f"NWS failed, trying Open-Meteo fallback for {method_name}")
                if method_name == "get_forecast":
                    temp_unit = self._get_temperature_unit_preference()
                    openmeteo_data = self.openmeteo_client.get_forecast(
                        lat, lon, temperature_unit=temp_unit
                    )
                    return self.openmeteo_mapper.map_forecast(openmeteo_data)
                elif method_name == "get_hourly_forecast":
                    temp_unit = self._get_temperature_unit_preference()
                    openmeteo_data = self.openmeteo_client.get_hourly_forecast(
                        lat, lon, temperature_unit=temp_unit
                    )
                    return self.openmeteo_mapper.map_hourly_forecast(openmeteo_data)
                elif method_name == "get_current_conditions":
                    temp_unit = self._get_temperature_unit_preference()
                    openmeteo_data = self.openmeteo_client.get_current_weather(
                        lat, lon, temperature_unit=temp_unit
                    )
                    return self.openmeteo_mapper.map_current_conditions(openmeteo_data)
                else:
                    logger.warning(f"No Open-Meteo fallback available for {method_name}")
                    return None

        except Exception as e:
            logger.error(f"Fallback API also failed for {method_name}: {str(e)}")
            return None

    def get_forecast(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
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
            if self._should_use_openmeteo(lat, lon):
                logger.info("Using Open-Meteo API for forecast")
                try:
                    # Get user's temperature preference
                    temp_unit = self._get_temperature_unit_preference()
                    # Get forecast from Open-Meteo with user's preferred units
                    openmeteo_data = self.openmeteo_client.get_forecast(
                        lat, lon, temperature_unit=temp_unit
                    )
                    # Transform to NWS-compatible format
                    return self.openmeteo_mapper.map_forecast(openmeteo_data)
                except (OpenMeteoError, Exception) as e:
                    logger.warning(f"Open-Meteo API failed for forecast: {str(e)}")
                    # Try fallback to NWS if location is in US
                    fallback_result = self._try_fallback_api(
                        lat, lon, "get_forecast", force_refresh=force_refresh
                    )
                    if fallback_result:
                        return fallback_result
                    else:
                        raise ApiClientError(
                            f"Open-Meteo failed and no fallback available: {str(e)}"
                        )
            else:
                logger.info("Using NWS API for forecast")
                try:
                    return self.nws_client.get_forecast(lat, lon, force_refresh=force_refresh)
                except (NoaaApiError, Exception) as e:
                    logger.warning(f"NWS API failed for forecast: {str(e)}")
                    # Try fallback to Open-Meteo
                    fallback_result = self._try_fallback_api(lat, lon, "get_forecast")
                    if fallback_result:
                        return fallback_result
                    else:
                        # Re-raise the original NWS error
                        if isinstance(e, NoaaApiError):
                            raise
                        else:
                            raise ApiClientError(
                                f"NWS failed and Open-Meteo fallback failed: {str(e)}"
                            )

        except ApiClientError:
            # Re-raise API client errors directly
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast data: {str(e)}")

    def get_hourly_forecast(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
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
            if self._should_use_openmeteo(lat, lon):
                logger.info("Using Open-Meteo API for hourly forecast")
                try:
                    # Get user's temperature preference
                    temp_unit = self._get_temperature_unit_preference()
                    # Get hourly forecast from Open-Meteo with user's preferred units
                    openmeteo_data = self.openmeteo_client.get_hourly_forecast(
                        lat, lon, temperature_unit=temp_unit
                    )
                    # Transform to NWS-compatible format
                    return self.openmeteo_mapper.map_hourly_forecast(openmeteo_data)
                except (OpenMeteoError, Exception) as e:
                    logger.warning(f"Open-Meteo API failed for hourly forecast: {str(e)}")
                    # Try fallback to NWS if location is in US
                    fallback_result = self._try_fallback_api(
                        lat, lon, "get_hourly_forecast", force_refresh=force_refresh
                    )
                    if fallback_result:
                        return fallback_result
                    else:
                        raise ApiClientError(
                            f"Open-Meteo failed and no fallback available: {str(e)}"
                        )
            else:
                logger.info("Using NWS API for hourly forecast")
                try:
                    return self.nws_client.get_hourly_forecast(
                        lat, lon, force_refresh=force_refresh
                    )
                except (NoaaApiError, Exception) as e:
                    logger.warning(f"NWS API failed for hourly forecast: {str(e)}")
                    # Try fallback to Open-Meteo
                    fallback_result = self._try_fallback_api(lat, lon, "get_hourly_forecast")
                    if fallback_result:
                        return fallback_result
                    else:
                        # Re-raise the original NWS error
                        if isinstance(e, NoaaApiError):
                            raise
                        else:
                            raise ApiClientError(
                                f"NWS failed and Open-Meteo fallback failed: {str(e)}"
                            )

        except ApiClientError:
            # Re-raise API client errors directly
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting hourly forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve hourly forecast data: {str(e)}")

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
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
    ) -> Dict[str, Any]:
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
            if self._should_use_openmeteo(lat, lon):
                logger.info("Using Open-Meteo API for current conditions")
                try:
                    # Get user's temperature preference
                    temp_unit = self._get_temperature_unit_preference()
                    # Get current conditions from Open-Meteo with user's preferred units
                    openmeteo_data = self.openmeteo_client.get_current_weather(
                        lat, lon, temperature_unit=temp_unit
                    )
                    # Transform to NWS-compatible format
                    return self.openmeteo_mapper.map_current_conditions(openmeteo_data)
                except (OpenMeteoError, Exception) as e:
                    logger.warning(f"Open-Meteo API failed for current conditions: {str(e)}")
                    # Try fallback to NWS if location is in US
                    fallback_result = self._try_fallback_api(
                        lat, lon, "get_current_conditions", force_refresh=force_refresh
                    )
                    if fallback_result:
                        return fallback_result
                    else:
                        raise ApiClientError(
                            f"Open-Meteo failed and no fallback available: {str(e)}"
                        )
            else:
                logger.info("Using NWS API for current conditions")
                try:
                    return self.nws_client.get_current_conditions(
                        lat, lon, force_refresh=force_refresh
                    )
                except (NoaaApiError, Exception) as e:
                    logger.warning(f"NWS API failed for current conditions: {str(e)}")
                    # Try fallback to Open-Meteo
                    fallback_result = self._try_fallback_api(lat, lon, "get_current_conditions")
                    if fallback_result:
                        return fallback_result
                    else:
                        # Re-raise the original NWS error
                        if isinstance(e, NoaaApiError):
                            raise
                        else:
                            raise ApiClientError(
                                f"NWS failed and Open-Meteo fallback failed: {str(e)}"
                            )

        except ApiClientError:
            # Re-raise API client errors directly
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting current conditions: {str(e)}")
            raise ApiClientError(f"Unable to retrieve current conditions data: {str(e)}")

    def get_alerts(
        self,
        lat: float,
        lon: float,
        force_refresh: bool = False,
        include_forecast_alerts: bool = False,
    ) -> Dict[str, Any]:
        """Get weather alerts for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.
            include_forecast_alerts: Whether to include alerts from forecast data.

        Returns:
            Dictionary containing weather alerts.

        Raises:
            ApiClientError: If there was an error retrieving the alerts.
        """
        try:
            logger.info(f"Getting alerts for coordinates: ({lat}, {lon})")

            # Check if this location would use Open-Meteo
            if self._should_use_openmeteo(lat, lon):
                logger.info("Open-Meteo does not provide weather alerts - returning empty alerts")
                # Return empty alerts structure for Open-Meteo locations
                return {
                    "features": [],
                    "title": "No alerts available",
                    "updated": "N/A",
                    "generator": "Open-Meteo (alerts not supported)",
                    "generatorVersion": "1.0",
                    "type": "FeatureCollection",
                    "@context": {
                        "wx": "https://api.weather.gov/ontology#",
                        "@vocab": "https://api.weather.gov/ontology#",
                    },
                }
            else:
                logger.info("Using NWS API for alerts")
                return self.nws_client.get_alerts(lat, lon, force_refresh=force_refresh)

        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting alerts: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            raise ApiClientError(f"Unable to retrieve alerts data: {str(e)}")

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get forecast discussion for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing forecast discussion.

        Raises:
            ApiClientError: If there was an error retrieving the discussion.
        """
        try:
            logger.info(f"Getting forecast discussion for coordinates: ({lat}, {lon})")
            # Always use NWS API for now (Open-Meteo integration will be added later)
            return self.nws_client.get_discussion(lat, lon, force_refresh=force_refresh)
        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting discussion: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting forecast discussion: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast discussion data: {str(e)}")

    def process_alerts(self, alerts_data: Dict[str, Any]) -> tuple[List[Dict[str, Any]], int, int]:
        """Process alerts data and return processed alerts with counts.

        This method delegates to the WeatherNotifier for processing.

        Args:
            alerts_data: Raw alerts data from the API.

        Returns:
            Tuple containing:
            - List of processed alert objects
            - Number of new alerts
            - Number of updated alerts
        """
        # Import here to avoid circular imports
        # Create a temporary notifier for processing
        # Use the same config directory as the main app would use
        import tempfile

        from ..notifications import WeatherNotifier

        temp_dir = tempfile.gettempdir()
        notifier = WeatherNotifier(config_dir=temp_dir, enable_persistence=False)

        return notifier.process_alerts(alerts_data)
