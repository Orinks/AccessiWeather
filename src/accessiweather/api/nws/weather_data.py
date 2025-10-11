"""
Weather data operations for NWS API wrapper.

This module handles weather data retrieval including current conditions,
forecasts, hourly forecasts, and observation stations.
"""

import logging
from typing import Any, cast

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.weather_gov_api_client.api.default import station_observation_latest

logger = logging.getLogger(__name__)


class NwsWeatherData:
    """Handles NWS weather data operations."""

    def __init__(self, wrapper_instance):
        """
        Initialize with reference to the main wrapper.

        Args:
        ----
            wrapper_instance: The main NwsApiWrapper instance

        """
        self.wrapper = wrapper_instance

    def get_current_conditions(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """
        Get current weather conditions for a location from the nearest observation station.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments including force_refresh

        Returns:
        -------
            Current conditions data dictionary

        Raises:
        ------
            ApiClientError: For client-related errors

        """
        force_refresh = kwargs.get("force_refresh", False)

        try:
            logger.info(f"Getting current conditions for coordinates: ({lat}, {lon})")

            # Get the observation stations
            stations_data = self.get_stations(lat, lon, force_refresh=force_refresh)

            if "features" not in stations_data or not stations_data["features"]:
                logger.error("No observation stations found")
                raise ValueError("No observation stations found")

            # Get the first station (nearest)
            station = stations_data["features"][0]
            station_id = station["properties"]["stationIdentifier"]

            logger.info(f"Using station {station_id} for current conditions")

            # Generate cache key for the current conditions
            cache_key = self.wrapper._generate_cache_key(
                f"stations/{station_id}/observations/latest", {}
            )

            def fetch_data() -> dict[str, Any]:
                self.wrapper._rate_limit()
                try:
                    response = self.wrapper.core_client.make_api_request(
                        station_observation_latest.sync, station_id=station_id
                    )
                    return self._transform_observation_data(response)
                except NoaaApiError:
                    raise
                except Exception as e:
                    logger.error(
                        f"Error getting current conditions for station {station_id}: {str(e)}"
                    )
                    url = f"{self.wrapper.core_client.BASE_URL}/stations/{station_id}/observations/latest"
                    error_msg = f"Unexpected error getting current conditions: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                    ) from e

            return cast(
                dict[str, Any],
                self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting current conditions: {str(e)}")
            raise ApiClientError(f"Unable to retrieve current conditions data: {str(e)}") from e

    def get_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """
        Get forecast for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments including force_refresh

        Returns:
        -------
            Forecast data dictionary

        Raises:
        ------
            ApiClientError: For client-related errors
            NoaaApiError: For API-related errors

        """
        force_refresh = kwargs.get("force_refresh", False)

        try:
            logger.info(f"Getting forecast for coordinates: ({lat}, {lon})")
            point_data = self.wrapper.point_location.get_point_data(
                lat, lon, force_refresh=force_refresh
            )

            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    f"Could not find forecast URL in point data. Available properties: {props}"
                )
                raise ValueError("Could not find forecast URL in point data")

            # Extract the forecast office ID and grid coordinates from the URL
            parts = forecast_url.split("/")
            office_id = parts[-3]
            grid_x, grid_y = parts[-2].split(",")

            # Generate cache key for the forecast
            cache_key = self.wrapper._generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast", {}
            )

            def fetch_data() -> dict[str, Any]:
                self.wrapper._rate_limit()
                try:
                    response = self.wrapper._fetch_url(forecast_url)
                    return self._transform_forecast_data(response)
                except NoaaApiError:
                    raise
                except Exception as e:
                    logger.error(f"Error getting forecast for {lat},{lon}: {str(e)}")
                    error_msg = f"Unexpected error getting forecast: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=forecast_url
                    ) from e

            return cast(
                dict[str, Any],
                self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except NoaaApiError:
            raise
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast data: {str(e)}") from e

    def get_hourly_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """
        Get hourly forecast for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments including force_refresh

        Returns:
        -------
            Hourly forecast data dictionary

        Raises:
        ------
            ApiClientError: For client-related errors

        """
        force_refresh = kwargs.get("force_refresh", False)

        try:
            logger.info(f"Getting hourly forecast for coordinates: ({lat}, {lon})")
            point_data = self.wrapper.point_location.get_point_data(
                lat, lon, force_refresh=force_refresh
            )

            forecast_hourly_url = point_data.get("properties", {}).get("forecastHourly")

            if not forecast_hourly_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    f"Could not find hourly forecast URL in point data. Available properties: {props}"
                )
                raise ValueError("Could not find hourly forecast URL in point data")

            # Extract the forecast office ID and grid coordinates from the URL
            parts = forecast_hourly_url.split("/")
            office_id = parts[-4]
            grid_x, grid_y = parts[-3].split(",")

            # Generate cache key for the hourly forecast
            cache_key = self.wrapper._generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast/hourly", {}
            )

            def fetch_data() -> dict[str, Any]:
                self.wrapper._rate_limit()
                try:
                    response = self.wrapper._fetch_url(forecast_hourly_url)
                    return self._transform_forecast_data(response)
                except NoaaApiError:
                    raise
                except Exception as e:
                    logger.error(f"Error getting hourly forecast for {lat},{lon}: {str(e)}")
                    error_msg = f"Unexpected error getting hourly forecast: {e}"
                    raise NoaaApiError(
                        message=error_msg,
                        error_type=NoaaApiError.UNKNOWN_ERROR,
                        url=forecast_hourly_url,
                    ) from e

            return cast(
                dict[str, Any],
                self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting hourly forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve hourly forecast data: {str(e)}") from e

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get observation stations for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force refresh cached data

        Returns:
        -------
            Stations data dictionary

        Raises:
        ------
            ApiClientError: For client-related errors

        """
        try:
            logger.info(f"Getting observation stations for coordinates: ({lat}, {lon})")
            point_data = self.wrapper.point_location.get_point_data(
                lat, lon, force_refresh=force_refresh
            )

            stations_url = point_data.get("properties", {}).get("observationStations")

            if not stations_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    f"Could not find observation stations URL in point data. Available properties: {props}"
                )
                raise ValueError("Could not find observation stations URL in point data")

            # Generate cache key for the stations
            cache_key = self.wrapper._generate_cache_key(stations_url, {})

            def fetch_data() -> dict[str, Any]:
                self.wrapper._rate_limit()
                try:
                    response = self.wrapper._fetch_url(stations_url)
                    return self._transform_stations_data(response)
                except Exception as e:
                    logger.error(f"Error getting stations for {lat},{lon}: {str(e)}")
                    raise NoaaApiError(
                        message=f"Error getting stations: {e}",
                        error_type=NoaaApiError.UNKNOWN_ERROR,
                        url=stations_url,
                    ) from e

            logger.info(f"Retrieved observation stations URL: {stations_url}")
            return cast(
                dict[str, Any],
                self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting observation stations: {str(e)}")
            raise ApiClientError(f"Unable to retrieve observation stations data: {str(e)}") from e

    def _transform_observation_data(self, observation_data: Any) -> dict[str, Any]:
        """Transform observation data from the generated client format."""
        if isinstance(observation_data, dict):
            return observation_data
        if hasattr(observation_data, "to_dict"):
            return cast(dict[str, Any], observation_data.to_dict())
        return cast(dict[str, Any], observation_data)

    def _transform_forecast_data(self, forecast_data: Any) -> dict[str, Any]:
        """Transform forecast data from the generated client format."""
        if hasattr(forecast_data, "to_dict"):
            return cast(dict[str, Any], forecast_data.to_dict())
        return cast(dict[str, Any], forecast_data)

    def _transform_stations_data(self, stations_data: Any) -> dict[str, Any]:
        """Transform stations data from the generated client format."""
        if isinstance(stations_data, dict):
            return stations_data
        if hasattr(stations_data, "to_dict"):
            return cast(dict[str, Any], stations_data.to_dict())
        return cast(dict[str, Any], stations_data)
