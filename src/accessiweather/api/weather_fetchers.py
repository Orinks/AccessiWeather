"""Weather data fetchers for NOAA API wrapper.

This module handles fetching weather-related data including forecasts and current conditions.
"""

import logging
from typing import Any, Dict, cast

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.weather_gov_api_client.api.default import station_observation_latest

logger = logging.getLogger(__name__)


class ApiWeatherFetchers:
    """Handles weather data fetching operations."""

    def __init__(
        self,
        request_manager: Any,
        data_transformers: Any,
        location_services: Any,
        base_url: str,
    ):
        """Initialize weather fetchers.

        Args:
            request_manager: Request manager instance
            data_transformers: Data transformers instance
            location_services: Location services instance
            base_url: Base URL for API requests
        """
        self.request_manager = request_manager
        self.data_transformers = data_transformers
        self.location_services = location_services
        self.base_url = base_url

    def get_forecast(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get forecast for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing forecast data
        """
        # First get the forecast URL from the point data
        try:
            logger.info(f"Getting forecast for coordinates: ({lat}, {lon})")
            point_data = self.location_services.get_point_data(
                lat, lon, force_refresh=force_refresh
            )

            # Debug log the point data structure
            logger.debug(f"Point data structure keys: {list(point_data.keys())}")

            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find forecast URL in point data. " f"Available properties: {props}"
                )
                # Keep this specific ValueError for this context
                raise ValueError("Could not find forecast URL in point data")

            # Extract the forecast office ID and grid coordinates from the URL
            # Example URL: https://api.weather.gov/gridpoints/PHI/31,70/forecast
            parts = forecast_url.split("/")
            office_id = parts[-3]
            grid_x, grid_y = parts[-2].split(",")

            # Generate cache key for the forecast
            cache_key = self.request_manager.generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast"
            )

            def fetch_data() -> Dict[str, Any]:
                self.request_manager.rate_limit()
                try:
                    # Use direct URL fetch instead of gridpoint.sync to get formatted forecast data
                    response = self.request_manager.fetch_url(forecast_url)
                    # Transform the response to match the format expected by the application
                    return self.data_transformers.transform_forecast_data(response)
                except NoaaApiError:
                    # Re-raise NoaaApiErrors directly
                    raise
                except Exception as e:
                    # For any other exceptions, wrap them in a NoaaApiError
                    logger.error(f"Error getting forecast for {lat},{lon}: {str(e)}")
                    error_msg = f"Unexpected error getting forecast: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=forecast_url
                    )

            return cast(
                Dict[str, Any],
                self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except NoaaApiError:
            # Re-raise NoaaApiErrors directly
            raise
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast data: {str(e)}")

    def get_hourly_forecast(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get hourly forecast for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing hourly forecast data
        """
        # First get the forecast URL from the point data
        try:
            logger.info(f"Getting hourly forecast for coordinates: ({lat}, {lon})")
            point_data = self.location_services.get_point_data(
                lat, lon, force_refresh=force_refresh
            )

            forecast_hourly_url = point_data.get("properties", {}).get("forecastHourly")

            if not forecast_hourly_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find hourly forecast URL in point data. "
                    f"Available properties: {props}"
                )
                raise ValueError("Could not find hourly forecast URL in point data")

            # Extract the forecast office ID and grid coordinates from the URL
            # Example URL: https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly
            parts = forecast_hourly_url.split("/")
            office_id = parts[-4]
            grid_x, grid_y = parts[-3].split(",")

            # Generate cache key for the hourly forecast
            cache_key = self.request_manager.generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast/hourly"
            )

            def fetch_data() -> Dict[str, Any]:
                self.request_manager.rate_limit()
                try:
                    # Use direct URL fetch instead of gridpoint.sync to get formatted hourly forecast data
                    response = self.request_manager.fetch_url(forecast_hourly_url)
                    # Transform the response to match the format expected by the application
                    return self.data_transformers.transform_forecast_data(response)
                except NoaaApiError:
                    # Re-raise NoaaApiErrors directly
                    raise
                except Exception as e:
                    # For any other exceptions, wrap them in a NoaaApiError
                    logger.error(f"Error getting hourly forecast for {lat},{lon}: {str(e)}")
                    error_msg = f"Unexpected error getting hourly forecast: {e}"
                    raise NoaaApiError(
                        message=error_msg,
                        error_type=NoaaApiError.UNKNOWN_ERROR,
                        url=forecast_hourly_url,
                    )

            return cast(
                Dict[str, Any],
                self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting hourly forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve hourly forecast data: {str(e)}")

    def get_current_conditions(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get current weather conditions for a location from the nearest observation station.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing current weather conditions
        """
        try:
            logger.info(f"Getting current conditions for coordinates: ({lat}, {lon})")

            # Get the observation stations
            stations_data = self.location_services.get_stations(
                lat, lon, force_refresh=force_refresh
            )

            if "features" not in stations_data or not stations_data["features"]:
                logger.error("No observation stations found")
                raise ValueError("No observation stations found")

            # Get the first station (nearest)
            station = stations_data["features"][0]
            station_id = station["properties"]["stationIdentifier"]

            logger.info(f"Using station {station_id} for current conditions")

            # Generate cache key for the current conditions
            cache_key = self.request_manager.generate_cache_key(
                f"stations/{station_id}/observations/latest"
            )

            def fetch_data() -> Dict[str, Any]:
                self.request_manager.rate_limit()
                try:
                    # Use the new make_api_request method to handle errors consistently
                    response = self.request_manager.make_api_request(
                        station_observation_latest.sync, station_id=station_id
                    )
                    # Transform the response to match the format expected by the application
                    return self.data_transformers.transform_observation_data(response)
                except NoaaApiError:
                    # Re-raise NoaaApiErrors directly
                    raise
                except Exception as e:
                    # For any other exceptions, wrap them in a NoaaApiError
                    logger.error(
                        f"Error getting current conditions for station {station_id}: {str(e)}"
                    )
                    url = f"{self.base_url}/stations/{station_id}/observations/latest"
                    error_msg = f"Unexpected error getting current conditions: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                    )

            return cast(
                Dict[str, Any],
                self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting current conditions: {str(e)}")
            raise ApiClientError(f"Unable to retrieve current conditions data: {str(e)}")
