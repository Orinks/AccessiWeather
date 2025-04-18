"""Weather service for AccessiWeather.

This module provides a service layer for weather-related operations,
separating business logic from UI concerns.
"""

import logging
from typing import Any, Dict, List, Optional

from accessiweather.api_client import ApiClientError, NoaaApiClient

logger = logging.getLogger(__name__)


class WeatherService:
    """Service for weather-related operations."""

    def get_national_discussion_summary(self, force_refresh: bool = False) -> dict:
        """
        Fetch and summarize the latest WPC Short Range and SPC Day 1 discussions for nationwide view.
        Returns:
            dict: {"wpc": {"short_range_summary": str}, "spc": {"day1_summary": str}}
        """
        return self.api_client.get_national_discussion_summary(force_refresh=force_refresh)

    def __init__(self, api_client: NoaaApiClient):
        """Initialize the weather service.

        Args:
            api_client: The API client to use for weather data retrieval.
        """
        self.api_client = api_client

    def get_national_forecast_data(self, force_refresh: bool = False) -> dict:
        """Get nationwide forecast data, including national discussion summaries."""
        try:
            logger.info("Getting nationwide forecast data (with scraper summaries)")
            from accessiweather.services import national_discussion_scraper
            summaries = national_discussion_scraper.get_national_discussion_summaries()
            return {
                "national_discussion_summaries": summaries
            }
        except Exception as e:
            logger.error(f"Error getting nationwide forecast data: {str(e)}")
            raise ApiClientError(f"Unable to retrieve nationwide forecast data: {str(e)}")

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
            return self.api_client.get_forecast(lat, lon, force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast data: {str(e)}")

    def get_alerts(
        self,
        lat: float,
        lon: float,
        radius: float = 50,
        precise_location: bool = True,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Get alerts for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            radius: Radius in miles to search for alerts.
            precise_location: Whether to get alerts for the precise location (county/zone)
                             or for the entire state.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing alert data.

        Raises:
            ApiClientError: If there was an error retrieving the alerts.
        """
        try:
            logger.info(
                f"Getting alerts for coordinates: ({lat}, {lon}) with radius {radius} miles, "
                f"precise_location={precise_location}, force_refresh={force_refresh}"
            )
            return self.api_client.get_alerts(
                lat,
                lon,
                radius=radius,
                precise_location=precise_location,
                force_refresh=force_refresh,
            )
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            raise ApiClientError(f"Unable to retrieve alerts data: {str(e)}")

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Optional[str]:
        """Get forecast discussion for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Text of the forecast discussion or None if not available.

        Raises:
            ApiClientError: If there was an error retrieving the discussion.
        """
        try:
            logger.info(f"Getting forecast discussion for coordinates: ({lat}, {lon})")
            discussion = self.api_client.get_discussion(lat, lon, force_refresh=force_refresh)
            if not discussion:
                logger.warning("No discussion available")
                return None
            return discussion
        except Exception as e:
            logger.error(f"Error getting discussion: {str(e)}")
            raise ApiClientError(f"Unable to retrieve discussion data: {str(e)}")

    def process_alerts(self, alerts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process alerts data into a list of alert objects.

        Args:
            alerts_data: Raw alerts data from the API.

        Returns:
            List of processed alert objects.
        """
        processed_alerts = []
        features = alerts_data.get("features", [])

        for feature in features:
            properties = feature.get("properties", {})

            # Extract relevant alert information
            alert = {
                "id": feature.get("id", ""),
                "headline": properties.get("headline", "Unknown Alert"),
                "description": properties.get("description", "No description available"),
                "instruction": properties.get("instruction", ""),
                "severity": properties.get("severity", "Unknown"),
                "event": properties.get("event", "Unknown Event"),
                "effective": properties.get("effective", ""),
                "expires": properties.get("expires", ""),
                "status": properties.get("status", ""),
                "messageType": properties.get("messageType", ""),
                "areaDesc": properties.get("areaDesc", "Unknown Area"),
            }

            processed_alerts.append(alert)

        return processed_alerts
