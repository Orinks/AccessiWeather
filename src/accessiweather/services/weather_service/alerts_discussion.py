"""
Alerts and discussion functionality for WeatherService.

This module handles weather alerts and forecast discussion retrieval,
including alert processing delegation.
"""

import logging
import tempfile
from typing import Any

from accessiweather.api_client import ApiClientError, NoaaApiClient, NoaaApiError
from accessiweather.api_wrapper import NoaaApiWrapper

logger = logging.getLogger(__name__)


class AlertsDiscussionHandler:
    """Handles weather alerts and forecast discussion operations."""

    def __init__(
        self,
        nws_client: NoaaApiClient | NoaaApiWrapper,
        api_client_manager,  # Type hint would create circular import
    ):
        """
        Initialize the alerts and discussion handler.

        Args:
        ----
            nws_client: The NWS API client
            api_client_manager: The API client manager instance

        """
        self.nws_client = nws_client
        self.api_client_manager = api_client_manager

    def get_alerts(
        self,
        lat: float,
        lon: float,
        force_refresh: bool = False,
        include_forecast_alerts: bool = False,
        radius: float = 50,
        precise_location: bool = True,
    ) -> dict[str, Any]:
        """
        Get weather alerts for a location.

        Args:
        ----
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.
            include_forecast_alerts: Whether to include alerts from forecast data.
            radius: Radius in miles to search for alerts (used for point-radius search).
            precise_location: Whether to get alerts for the precise location (county/zone)
                             or for the entire state.

        Returns:
        -------
            Dictionary containing weather alerts.

        Raises:
        ------
            ApiClientError: If there was an error retrieving the alerts.

        """
        try:
            logger.info(f"Getting alerts for coordinates: ({lat}, {lon})")

            # Check if this location would use Open-Meteo
            if self.api_client_manager._should_use_openmeteo(lat, lon):
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
            logger.info("Using NWS API for alerts")
            return self.nws_client.get_alerts(
                lat,
                lon,
                radius=radius,
                precise_location=precise_location,
                force_refresh=force_refresh,
            )

        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting alerts: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            raise ApiClientError(f"Unable to retrieve alerts data: {str(e)}") from e

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> str | None:
        """
        Get forecast discussion for a location.

        Args:
        ----
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
        -------
            String containing forecast discussion text, or None if not available.

        Raises:
        ------
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
            raise ApiClientError(f"Unable to retrieve forecast discussion data: {str(e)}") from e

    def process_alerts(self, alerts_data: dict[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
        """
        Process alerts data and return processed alerts with counts.

        This method delegates to the WeatherNotifier for processing.

        Args:
        ----
            alerts_data: Raw alerts data from the API.

        Returns:
        -------
            Tuple containing:
            - List of processed alert objects
            - Number of new alerts
            - Number of updated alerts

        """
        # Import here to avoid circular imports
        # Create a temporary notifier for processing
        # Use the same config directory as the main app would use
        from ...notifications import WeatherNotifier

        temp_dir = tempfile.gettempdir()
        notifier = WeatherNotifier(config_dir=temp_dir, enable_persistence=False)

        return notifier.process_alerts(alerts_data)
