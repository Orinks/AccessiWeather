"""Location services for NOAA API wrapper.

This module handles location identification and point data retrieval.
"""

import logging
from typing import Any, Dict, Optional, Tuple, cast

from accessiweather.api.exceptions import ApiClientError, NoaaApiError
from accessiweather.weather_gov_api_client.api.default import point

logger = logging.getLogger(__name__)


class ApiLocationServices:
    """Handles location-related API operations."""

    def __init__(self, request_manager: Any, data_transformers: Any, base_url: str):
        """Initialize location services.

        Args:
            request_manager: Request manager instance
            data_transformers: Data transformers instance
            base_url: Base URL for API requests
        """
        self.request_manager = request_manager
        self.data_transformers = data_transformers
        self.base_url = base_url

    def get_point_data(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get metadata about a specific lat/lon point.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing point metadata
        """
        endpoint = f"points/{lat},{lon}"
        cache_key = self.request_manager.generate_cache_key(endpoint)
        logger.info(f"Fetching point data for coordinates: ({lat}, {lon})")

        def fetch_data() -> Dict[str, Any]:
            self.request_manager.rate_limit()
            try:
                point_str = f"{lat},{lon}"
                # Use the new make_api_request method to handle errors consistently
                response = self.request_manager.make_api_request(point.sync, point=point_str)
                # Transform the response to match the format expected by the application
                return self.data_transformers.transform_point_data(response)
            except NoaaApiError:
                # Re-raise NoaaApiErrors directly
                raise
            except Exception as e:
                # For any other exceptions, wrap them in a NoaaApiError
                logger.error(f"Error getting point data for {lat},{lon}: {str(e)}")
                url = f"{self.base_url}/{endpoint}"
                error_msg = f"Unexpected error getting point data: {e}"
                raise NoaaApiError(
                    message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                )

        return cast(
            Dict[str, Any],
            self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
        )

    def identify_location_type(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Tuple[Optional[str], Optional[str]]:
        """Identify the type of location (county, state, etc.) for the given coordinates.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache

        Returns:
            Tuple of (location_type, location_id) where location_type is one of
            'county', 'forecast', 'fire', or None if the type cannot be determined.
            location_id is the UGC code for the location or None.
        """
        try:
            # Get point data for the coordinates
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)
            properties = point_data.get("properties", {})

            # Check for county zone
            county_url = properties.get("county")
            if county_url and isinstance(county_url, str) and "/county/" in county_url:
                # Extract county code (format: .../zones/county/XXC###)
                county_id = county_url.split("/county/")[1]
                logger.info(f"Identified location as county: {county_id}")
                return "county", county_id

            # Check for forecast zone
            forecast_zone_url = properties.get("forecastZone")
            if (
                forecast_zone_url
                and isinstance(forecast_zone_url, str)
                and "/forecast/" in forecast_zone_url
            ):
                # Extract forecast zone code (format: .../zones/forecast/XXZ###)
                forecast_id = forecast_zone_url.split("/forecast/")[1]
                logger.info(f"Identified location as forecast zone: {forecast_id}")
                return "forecast", forecast_id

            # Check for fire weather zone
            fire_zone_url = properties.get("fireWeatherZone")
            if fire_zone_url and isinstance(fire_zone_url, str) and "/fire/" in fire_zone_url:
                # Extract fire zone code (format: .../zones/fire/XXZ###)
                fire_id = fire_zone_url.split("/fire/")[1]
                logger.info(f"Identified location as fire zone: {fire_id}")
                return "fire", fire_id

            # If we can't determine a specific zone, try to get the state
            try:
                state = properties.get("relativeLocation", {}).get("properties", {}).get("state")
                if state:
                    logger.info(f"Could only identify location at state level: {state}")
                    return "state", state
            except (KeyError, TypeError):
                pass

            logger.warning(f"Could not identify location type for coordinates: ({lat}, {lon})")
            return None, None

        except Exception as e:
            logger.error(f"Error identifying location type: {str(e)}")
            return None, None

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get observation stations for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing observation stations data
        """
        try:
            logger.info(f"Getting observation stations for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            stations_url = point_data.get("properties", {}).get("observationStations")

            if not stations_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find observation stations URL in point data. "
                    f"Available properties: {props}"
                )
                raise ValueError("Could not find observation stations URL in point data")

            # Generate cache key for the stations
            cache_key = self.request_manager.generate_cache_key(stations_url)

            def fetch_data() -> Dict[str, Any]:
                self.request_manager.rate_limit()
                try:
                    # Use direct API call instead of the generated client
                    response = self.request_manager.fetch_url(stations_url)
                    # Transform the response to match the format expected by the application
                    return self.data_transformers.transform_stations_data(response)
                except Exception as e:
                    logger.error(f"Error getting stations for {lat},{lon}: {str(e)}")
                    raise self.request_manager.handle_client_error(e, stations_url)

            logger.info(f"Retrieved observation stations URL: {stations_url}")
            return cast(
                Dict[str, Any],
                self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting observation stations: {str(e)}")
            raise ApiClientError(f"Unable to retrieve observation stations data: {str(e)}")
