"""Weather service for AccessiWeather.

This module provides a service layer for weather-related operations,
separating business logic from UI concerns.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from accessiweather.api_client import NoaaApiClient
from accessiweather.api_wrapper import NoaaApiWrapper
from accessiweather.openmeteo_client import OpenMeteoApiClient

from .alerts_discussion import AlertsDiscussionHandler
from .api_client_manager import ApiClientManager
from .fallback_handler import FallbackHandler
from .national_forecast import NationalForecastHandler
from .weather_data_retrieval import WeatherDataRetrieval

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
        self.config = config or {}

        # Initialize component handlers
        self.api_client_manager = ApiClientManager(nws_client, openmeteo_client, self.config)
        self.fallback_handler = FallbackHandler(
            nws_client,
            self.api_client_manager.openmeteo_client,
            self.api_client_manager.openmeteo_mapper,
            self.api_client_manager,
        )
        self.weather_data_retrieval = WeatherDataRetrieval(
            nws_client, self.api_client_manager, self.fallback_handler
        )
        self.national_forecast_handler = NationalForecastHandler()
        self.alerts_discussion_handler = AlertsDiscussionHandler(
            nws_client, self.api_client_manager
        )

    # Backward compatibility properties for tests and external code
    @property
    def openmeteo_client(self):
        """Backward compatibility property for openmeteo_client."""
        return self.api_client_manager.openmeteo_client

    @property
    def openmeteo_mapper(self):
        """Backward compatibility property for openmeteo_mapper."""
        return self.api_client_manager.openmeteo_mapper

    def _get_temperature_unit_preference(self) -> str:
        """Backward compatibility method for _get_temperature_unit_preference."""
        # Update the config in the API client manager to ensure it has the latest config
        self.api_client_manager.config = self.config
        return self.api_client_manager._get_temperature_unit_preference()

    def _should_use_openmeteo(self, lat: float, lon: float) -> bool:
        """Backward compatibility method for _should_use_openmeteo."""
        # Update the config in the API client manager to ensure it has the latest config
        self.api_client_manager.config = self.config
        return self.api_client_manager._should_use_openmeteo(lat, lon)

    def _get_data_source(self) -> str:
        """Backward compatibility method for _get_data_source."""
        # Update the config in the API client manager to ensure it has the latest config
        self.api_client_manager.config = self.config
        return self.api_client_manager._get_data_source()

    @property
    def national_scraper(self):
        """Backward compatibility property for national_scraper."""
        return self.national_forecast_handler.national_scraper

    @property
    def national_data_cache(self):
        """Backward compatibility property for national_data_cache."""
        return self.national_forecast_handler.national_data_cache

    @national_data_cache.setter
    def national_data_cache(self, value):
        """Backward compatibility setter for national_data_cache."""
        self.national_forecast_handler.national_data_cache = value

    @property
    def national_data_timestamp(self):
        """Backward compatibility property for national_data_timestamp."""
        return self.national_forecast_handler.national_data_timestamp

    @national_data_timestamp.setter
    def national_data_timestamp(self, value):
        """Backward compatibility setter for national_data_timestamp."""
        self.national_forecast_handler.national_data_timestamp = value

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
        return self.national_forecast_handler.get_national_forecast_data(force_refresh)

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
        return self.weather_data_retrieval.get_forecast(lat, lon, force_refresh)

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
        return self.weather_data_retrieval.get_hourly_forecast(lat, lon, force_refresh)

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
        return self.weather_data_retrieval.get_stations(lat, lon, force_refresh)

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
        return self.weather_data_retrieval.get_current_conditions(lat, lon, force_refresh)

    def get_alerts(
        self,
        lat: float,
        lon: float,
        force_refresh: bool = False,
        include_forecast_alerts: bool = False,
        radius: float = 50,
        precise_location: bool = True,
    ) -> Dict[str, Any]:
        """Get weather alerts for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.
            include_forecast_alerts: Whether to include alerts from forecast data.
            radius: Radius in miles to search for alerts (used for point-radius search).
            precise_location: Whether to get alerts for the precise location (county/zone)
                             or for the entire state.

        Returns:
            Dictionary containing weather alerts.

        Raises:
            ApiClientError: If there was an error retrieving the alerts.
        """
        return self.alerts_discussion_handler.get_alerts(
            lat, lon, force_refresh, include_forecast_alerts, radius, precise_location
        )

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Optional[str]:
        """Get forecast discussion for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            String containing forecast discussion text, or None if not available.

        Raises:
            ApiClientError: If there was an error retrieving the discussion.
        """
        return self.alerts_discussion_handler.get_discussion(lat, lon, force_refresh)

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
        return self.alerts_discussion_handler.process_alerts(alerts_data)
