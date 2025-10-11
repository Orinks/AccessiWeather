"""
Point data and location operations for NWS API wrapper.

This module handles geographic point data retrieval, transformation,
and location type identification operations.
"""

import logging
from typing import Any, cast

from accessiweather.api_client import NoaaApiError
from accessiweather.weather_gov_api_client.api.default import point

logger = logging.getLogger(__name__)


class NwsPointLocation:
    """Handles NWS point data and location identification operations."""

    def __init__(self, wrapper_instance):
        """
        Initialize with reference to the main wrapper.

        Args:
        ----
            wrapper_instance: The main NwsApiWrapper instance

        """
        self.wrapper = wrapper_instance

    def get_point_data(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get metadata about a specific lat/lon point.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force refresh cached data

        Returns:
        -------
            Point data dictionary

        Raises:
        ------
            NoaaApiError: For API-related errors

        """
        endpoint = f"points/{lat},{lon}"
        cache_key = self.wrapper._generate_cache_key(endpoint, {})
        logger.info(f"Fetching point data for coordinates: ({lat}, {lon})")

        def fetch_data() -> dict[str, Any]:
            self.wrapper._rate_limit()
            try:
                point_str = f"{lat},{lon}"
                response = self.wrapper.core_client.make_api_request(point.sync, point=point_str)
                return self._transform_point_data(response)
            except NoaaApiError:
                raise
            except Exception as e:
                logger.error(f"Error getting point data for {lat},{lon}: {str(e)}")
                url = f"{self.wrapper.core_client.BASE_URL}/{endpoint}"
                error_msg = f"Unexpected error getting point data: {e}"
                raise NoaaApiError(
                    message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                ) from e

        return cast(
            dict[str, Any], self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
        )

    def _transform_point_data(self, point_data: Any) -> dict[str, Any]:
        """
        Transform point data from the generated client format.

        Args:
        ----
            point_data: Raw point data from the API

        Returns:
        -------
            Transformed point data dictionary

        """
        # Extract and transform the data to match the format expected by the application
        if isinstance(point_data, dict):
            properties = point_data.get("properties", {})
            transformed = {
                "properties": {
                    "forecast": properties.get("forecast"),
                    "forecastHourly": properties.get("forecastHourly"),
                    "forecastGridData": properties.get("forecastGridData"),
                    "observationStations": properties.get("observationStations"),
                    "county": properties.get("county"),
                    "fireWeatherZone": properties.get("fireWeatherZone"),
                    "timeZone": properties.get("timeZone"),
                    "radarStation": properties.get("radarStation"),
                }
            }
        else:
            # Handle object with properties attribute
            properties_obj = getattr(point_data, "properties", None)
            if properties_obj:
                if hasattr(properties_obj, "additional_properties"):
                    properties = properties_obj.additional_properties
                else:
                    properties = {}
                    for attr in [
                        "forecast",
                        "forecast_hourly",
                        "forecast_grid_data",
                        "observation_stations",
                        "county",
                        "fire_weather_zone",
                        "time_zone",
                        "radar_station",
                    ]:
                        if hasattr(properties_obj, attr):
                            properties[attr] = getattr(properties_obj, attr)

                transformed = {
                    "properties": {
                        "forecast": properties.get("forecast"),
                        "forecastHourly": properties.get("forecastHourly")
                        or properties.get("forecast_hourly"),
                        "forecastGridData": properties.get("forecastGridData")
                        or properties.get("forecast_grid_data"),
                        "observationStations": properties.get("observationStations")
                        or properties.get("observation_stations"),
                        "county": properties.get("county"),
                        "fireWeatherZone": properties.get("fireWeatherZone")
                        or properties.get("fire_weather_zone"),
                        "timeZone": properties.get("timeZone") or properties.get("time_zone"),
                        "radarStation": properties.get("radarStation")
                        or properties.get("radar_station"),
                    }
                }
            else:
                transformed = {"properties": {}}

        return transformed

    def identify_location_type(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> tuple[str | None, str | None]:
        """
        Identify the type of location (county, state, etc.) for the given coordinates.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force refresh cached data

        Returns:
        -------
            Tuple of (location_type, location_id) or (None, None) if unable to identify

        """
        try:
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)
            properties = point_data.get("properties", {})

            # Check for county zone
            county_url = properties.get("county")
            if county_url and isinstance(county_url, str) and "/county/" in county_url:
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
                forecast_id = forecast_zone_url.split("/forecast/")[1]
                logger.info(f"Identified location as forecast zone: {forecast_id}")
                return "forecast", forecast_id

            # Check for fire weather zone
            fire_zone_url = properties.get("fireWeatherZone")
            if fire_zone_url and isinstance(fire_zone_url, str) and "/fire/" in fire_zone_url:
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
