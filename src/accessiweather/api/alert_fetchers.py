"""Alert fetchers for NOAA API wrapper.

This module handles fetching weather alert data.
"""

import logging
from typing import Any, Dict, cast

from accessiweather.api.exceptions import ApiClientError, NoaaApiError
from accessiweather.weather_gov_api_client.api.default import alerts_active, alerts_active_zone

logger = logging.getLogger(__name__)


class ApiAlertFetchers:
    """Handles alert data fetching operations."""

    def __init__(
        self,
        request_manager: Any,
        data_transformers: Any,
        location_services: Any,
        base_url: str,
    ):
        """Initialize alert fetchers.

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
            lat: Latitude
            lon: Longitude
            radius: Radius in miles to search for alerts
            precise_location: Whether to get alerts for the precise location (county/zone)
                             or for the entire state
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dictionary containing alert data
        """
        try:
            logger.info(
                f"Getting alerts for coordinates: ({lat}, {lon}) with radius {radius} miles, "
                f"precise_location={precise_location}, force_refresh={force_refresh}"
            )

            # Identify the location type
            location_type, location_id = self.location_services.identify_location_type(
                lat, lon, force_refresh=force_refresh
            )

            if precise_location and location_type in ("county", "forecast", "fire") and location_id:
                # Get alerts for the specific zone
                logger.info(f"Fetching alerts for {location_type} zone: {location_id}")
                cache_key = self.request_manager.generate_cache_key(
                    "alerts_zone", {"zone_id": location_id}
                )

                def fetch_data() -> Dict[str, Any]:
                    self.request_manager.rate_limit()
                    try:
                        # Use the new make_api_request method to handle errors consistently
                        response = self.request_manager.make_api_request(
                            alerts_active_zone.sync, zone_id=location_id
                        )
                        # Transform the response to match the format expected by the application
                        return self.data_transformers.transform_alerts_data(response)
                    except NoaaApiError:
                        # Re-raise NoaaApiErrors directly
                        raise
                    except Exception as e:
                        # For any other exceptions, wrap them in a NoaaApiError
                        logger.error(f"Error getting alerts for zone {location_id}: {str(e)}")
                        url = f"{self.base_url}/alerts/active/zone/{location_id}"
                        error_msg = f"Unexpected error getting alerts for zone: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        )

                return cast(
                    Dict[str, Any],
                    self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
                )

            # If we have a state but not precise location, get state alerts
            if not precise_location and location_type == "state" and location_id:
                logger.info(f"Fetching alerts for state: {location_id}")
                cache_key = self.request_manager.generate_cache_key(
                    "alerts_state", {"state": location_id}
                )

                def fetch_data() -> Dict[str, Any]:
                    self.request_manager.rate_limit()
                    try:
                        # Use fetch_url for state-based alerts
                        url = f"{self.base_url}/alerts/active?area={location_id}"
                        response = self.request_manager.fetch_url(url)
                        return self.data_transformers.transform_alerts_data(response)
                    except Exception as e:
                        logger.error(f"Error getting alerts for state {location_id}: {str(e)}")
                        error_msg = f"Unexpected error getting alerts for state: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        )

                return cast(
                    Dict[str, Any],
                    self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
                )

            # If we couldn't determine location or state, fall back to point-radius search
            if location_type is None or location_id is None:
                logger.info(
                    "Using point-radius search for alerts since location could not "
                    f"be determined: ({lat}, {lon}) with radius {radius} miles"
                )
                cache_key = self.request_manager.generate_cache_key(
                    "alerts_point", {"lat": lat, "lon": lon, "radius": radius}
                )

                def fetch_data() -> Dict[str, Any]:
                    self.request_manager.rate_limit()
                    try:
                        # Use fetch_url for point-radius alerts
                        url = f"{self.base_url}/alerts/active?point={lat},{lon}&radius={radius}"
                        response = self.request_manager.fetch_url(url)
                        return self.data_transformers.transform_alerts_data(response)
                    except Exception as e:
                        logger.error(f"Error getting alerts for point ({lat}, {lon}): {str(e)}")
                        error_msg = f"Unexpected error getting alerts for point: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        )

                return cast(
                    Dict[str, Any],
                    self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
                )

            # Final fallback: get all active alerts
            logger.info("Falling back to all active alerts")
            cache_key = self.request_manager.generate_cache_key("alerts_all", {})

            def fetch_data() -> Dict[str, Any]:
                self.request_manager.rate_limit()
                try:
                    # Use the new make_api_request method to handle errors consistently
                    response = self.request_manager.make_api_request(alerts_active.sync)
                    # Transform the response to match the format expected by the application
                    return self.data_transformers.transform_alerts_data(response)
                except NoaaApiError:
                    # Re-raise NoaaApiErrors directly
                    raise
                except Exception as e:
                    # For any other exceptions, wrap them in a NoaaApiError
                    logger.error(f"Error getting all alerts: {str(e)}")
                    url = f"{self.base_url}/alerts/active"
                    error_msg = f"Unexpected error getting all alerts: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                    )

            return cast(
                Dict[str, Any],
                self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            raise ApiClientError(f"Unable to retrieve alerts data: {str(e)}")

    def get_alerts_direct(self, url: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Get active weather alerts directly from a provided URL.

        Args:
            url: Full URL to the alerts endpoint
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dictionary containing alert data
        """
        try:
            logger.info(f"Fetching alerts directly from URL: {url}")

            # Generate cache key for the URL
            cache_key = self.request_manager.generate_cache_key("alerts_direct", {"url": url})

            def fetch_data() -> Dict[str, Any]:
                self.request_manager.rate_limit()
                try:
                    # Use fetch_url for direct URL access
                    response = self.request_manager.fetch_url(url)
                    # Transform the response to match the format expected by the application
                    return self.data_transformers.transform_alerts_data(response)
                except Exception as e:
                    # For any exceptions, wrap them in a NoaaApiError
                    logger.error(f"Error getting alerts from URL {url}: {str(e)}")
                    error_msg = f"Unexpected error getting alerts from URL: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                    )

            return cast(
                Dict[str, Any],
                self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting alerts from URL: {str(e)}")
            raise ApiClientError(f"Unable to retrieve alerts from URL: {str(e)}")
