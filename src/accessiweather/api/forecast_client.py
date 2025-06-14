"""Forecast-related functionality for NOAA API client."""

import json
import logging
import traceback
from typing import Any, Dict, Optional

from accessiweather.api.base_client import NoaaApiClient

logger = logging.getLogger(__name__)


class ForecastClient(NoaaApiClient):
    """Client for forecast-related NOAA API operations."""

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
        logger.info(f"Fetching point data for coordinates: ({lat}, {lon})")
        return self._make_request(endpoint, force_refresh=force_refresh)

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
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            # Debug log the point data structure
            logger.debug(f"Point data structure: {json.dumps(point_data, indent=2)}")

            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find forecast URL in point data. " f"Available properties: {props}"
                )
                # Keep this specific ValueError for this context
                raise ValueError("Could not find forecast URL in point data")

            logger.info(f"Retrieved forecast URL: {forecast_url}")
            return self._make_request(forecast_url, use_full_url=True, force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

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
        # First get the hourly forecast URL from the point data
        try:
            logger.info(f"Getting hourly forecast for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            # Debug log the point data structure
            logger.debug(f"Point data structure: {json.dumps(point_data, indent=2)}")

            hourly_forecast_url = point_data.get("properties", {}).get("forecastHourly")

            if not hourly_forecast_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find hourly forecast URL in point data. "
                    f"Available properties: {props}"
                )
                raise ValueError("Could not find hourly forecast URL in point data")

            logger.info(f"Retrieved hourly forecast URL: {hourly_forecast_url}")
            return self._make_request(
                hourly_forecast_url, use_full_url=True, force_refresh=force_refresh
            )
        except Exception as e:
            logger.error(f"Error getting hourly forecast: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

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

            # Debug log the point data structure
            logger.debug(f"Point data structure: {json.dumps(point_data, indent=2)}")

            stations_url = point_data.get("properties", {}).get("observationStations")

            if not stations_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find observation stations URL in point data. "
                    f"Available properties: {props}"
                )
                raise ValueError("Could not find observation stations URL in point data")

            logger.info(f"Retrieved observation stations URL: {stations_url}")
            return self._make_request(stations_url, use_full_url=True, force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error getting observation stations: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

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
            stations_data = self.get_stations(lat, lon, force_refresh=force_refresh)

            # Check if we have any stations
            if not stations_data.get("features") or len(stations_data["features"]) == 0:
                logger.error("No observation stations found for the given coordinates")
                raise ValueError("No observation stations found for the given coordinates")

            # Get the first station (nearest)
            station = stations_data["features"][0]
            station_id = station["properties"]["stationIdentifier"]

            logger.info(f"Using station {station_id} for current conditions")

            # Get the latest observation from this station
            from accessiweather.api.constants import BASE_URL
            observation_url = f"{BASE_URL}/stations/{station_id}/observations/latest"
            logger.info(f"Fetching current conditions from: {observation_url}")

            return self._make_request(
                observation_url, use_full_url=True, force_refresh=force_refresh
            )
        except Exception as e:
            logger.error(f"Error getting current conditions: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Optional[str]:
        """Get the forecast discussion for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Text of the forecast discussion or None if not available
        """
        try:
            logger.info(f"Getting forecast discussion for coordinates: ({lat}, {lon})")
            logger.debug("Calling get_point_data")
            point_data = self.get_point_data(lat, lon)
            logger.debug("Returned from get_point_data")
            logger.debug(f"Point data keys: {list(point_data.keys())}")
            logger.debug(
                f"Point data properties keys: {list(point_data.get('properties', {}).keys())}"
            )
            office_id = point_data.get("properties", {}).get("gridId")
            logger.debug(f"Office ID: {office_id}")

            if not office_id:
                logger.warning("Could not find office ID in point data")
                # Keep this specific ValueError for this context
                raise ValueError("Could not find office ID in point data")

            # Get the forecast discussion product
            endpoint = f"products/types/AFD/locations/{office_id}"
            logger.info(f"Fetching products for office: {office_id}")
            logger.debug(f"Making request to endpoint: {endpoint}")
            products = self._make_request(endpoint, force_refresh=force_refresh)
            logger.debug("Returned from _make_request for products")
            logger.debug(f"Products keys: {list(products.keys())}")

            # Get the latest discussion
            try:
                graph_data = products.get("@graph", [])
                logger.debug(f"Found {len(graph_data)} products in @graph")

                if not graph_data:
                    logger.warning("No products found in @graph")
                    return None

                latest_product = graph_data[0]
                logger.debug(f"Latest product keys: {list(latest_product.keys())}")
                latest_product_id = latest_product.get("id")
                if not latest_product_id:
                    logger.warning("No product ID found in latest product")
                    return None

                logger.info(f"Fetching product text for: {latest_product_id}")
                product_endpoint = f"products/{latest_product_id}"
                logger.debug(f"Making request to endpoint: {product_endpoint}")
                product = self._make_request(product_endpoint, force_refresh=force_refresh)
                logger.debug("Returned from _make_request for product text")
                logger.debug(f"Product keys: {list(product.keys())}")

                product_text = product.get("productText")
                if product_text:
                    logger.debug(
                        f"Successfully retrieved product text (length: {len(product_text)})"
                    )
                    # Log the first 100 characters of the product text
                    preview = product_text[:100].replace("\n", "\\n")
                    logger.debug(f"Product text preview: {preview}...")
                else:
                    logger.warning("Product text is empty or missing")

                logger.debug("Returning product_text from get_discussion")
                return str(product_text) if product_text else None
            except (IndexError, KeyError) as e:
                logger.warning(f"Could not find forecast discussion for {office_id}: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"Error getting discussion: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
