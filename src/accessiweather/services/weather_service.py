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
)
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
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the weather service.

        Args:
            nws_client: The NWS API client to use for weather data retrieval.
            config: Configuration dictionary containing settings like data_source.
        """
        self.nws_client = nws_client
        self.config = config or {}
        self.national_scraper = NationalDiscussionScraper(request_delay=1.0)
        self.national_data_cache: Optional[Dict[str, Dict[str, str]]] = None
        self.national_data_timestamp: float = 0.0
        self.cache_expiry = 3600  # 1 hour in seconds

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
            String indicating which data source to use ('nws' or 'auto')
        """
        data_source = self.config.get("settings", {}).get("data_source", DATA_SOURCE_NWS)
        logger.debug(
            f"_get_data_source: config={self.config.get('settings', {})}, data_source={data_source}"
        )
        return str(data_source)

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
            # Always use NWS API for now (Open-Meteo integration will be added later)
            return self.nws_client.get_forecast(lat, lon, force_refresh=force_refresh)
        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting forecast: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
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
            # Always use NWS API for now (Open-Meteo integration will be added later)
            return self.nws_client.get_hourly_forecast(lat, lon, force_refresh=force_refresh)
        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting hourly forecast: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting hourly forecast: {str(e)}")
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
            # Always use NWS API for now (Open-Meteo integration will be added later)
            return self.nws_client.get_current_conditions(lat, lon, force_refresh=force_refresh)
        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting current conditions: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting current conditions: {str(e)}")
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
            # Always use NWS API for now (Open-Meteo integration will be added later)
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
