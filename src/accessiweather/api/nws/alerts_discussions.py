"""
Alerts and discussions operations for NWS API wrapper.

This module handles weather alerts, forecast discussions, and national
weather products from various centers.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.weather_gov_api_client.api.default import alerts_active, alerts_active_zone

logger = logging.getLogger(__name__)


class NwsAlertsDiscussions:
    """Handles NWS alerts and discussions operations."""

    def __init__(self, wrapper_instance):
        """
        Initialize with reference to the main wrapper.

        Args:
        ----
            wrapper_instance: The main NwsApiWrapper instance

        """
        self.wrapper = wrapper_instance
        # Conditional GET state for alert polling
        self._alert_etag: str | None = None
        self._alert_last_modified: str | None = None
        self._cached_alert_response: dict[str, Any] | None = None

    def reset_conditional_cache(self) -> None:
        """Reset conditional GET cache state (e.g. when location changes)."""
        self._alert_etag = None
        self._alert_last_modified = None
        self._cached_alert_response = None

    def _fetch_alerts_conditional(self, url: str) -> dict[str, Any]:
        """
        Fetch alerts using HTTP conditional GET (ETag / Last-Modified).

        On 304 Not Modified, returns the previously cached response.
        On 200, stores new ETag/Last-Modified headers and caches the response.
        Gracefully degrades when the server omits caching headers.
        """
        self.wrapper._rate_limit()

        headers = {"User-Agent": f"{self.wrapper.user_agent} ({self.wrapper.contact_info})"}
        if self._alert_etag:
            headers["If-None-Match"] = self._alert_etag
        if self._alert_last_modified:
            headers["If-Modified-Since"] = self._alert_last_modified

        with httpx.Client(timeout=httpx.Timeout(10.0), follow_redirects=True) as client:
            response = client.get(url, headers=headers)

            if response.status_code == 304 and self._cached_alert_response is not None:
                logger.debug("Alerts not modified (304), returning cached data")
                return self._cached_alert_response

            response.raise_for_status()

            # Store conditional GET headers for next request
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            if etag:
                self._alert_etag = etag
            if last_modified:
                self._alert_last_modified = last_modified

            data = response.json()
            self._cached_alert_response = data
            return data

    def get_alerts(
        self,
        lat: float,
        lon: float,
        radius: float = 50,
        precise_location: bool = True,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Get alerts for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            radius: Search radius in miles
            precise_location: Whether to use precise location-based alerts
            force_refresh: Whether to force refresh cached data

        Returns:
        -------
            Alerts data dictionary

        Raises:
        ------
            ApiClientError: For client-related errors

        """
        try:
            logger.info(
                f"Getting alerts for coordinates: ({lat}, {lon}) with radius {radius} miles, precise_location={precise_location}"
            )

            if precise_location:
                # Use point-based alerts for precise location (no radius parameter needed)
                logger.info(f"Using point-based alerts for precise location: ({lat}, {lon})")
                cache_key = self.wrapper._generate_cache_key(
                    "alerts_point", {"lat": lat, "lon": lon}
                )

                def fetch_data() -> dict[str, Any]:
                    try:
                        url = f"{self.wrapper.core_client.BASE_URL}/alerts/active?point={lat},{lon}"
                        response = self._fetch_alerts_conditional(url)
                        return self._transform_alerts_data(response)
                    except Exception as e:
                        logger.error(f"Error getting alerts for point ({lat}, {lon}): {str(e)}")
                        error_msg = f"Unexpected error getting alerts for point: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        ) from e

                return cast(
                    dict[str, Any],
                    self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
                )

            # For non-precise location, use zone-based alerts
            # Identify the location type
            location_type, location_id = self.wrapper.point_location.identify_location_type(
                lat, lon, force_refresh=force_refresh
            )

            if location_type in ("county", "forecast", "fire") and location_id:
                # Get alerts for the specific zone
                logger.info(f"Fetching alerts for {location_type} zone: {location_id}")
                cache_key = self.wrapper._generate_cache_key(
                    "alerts_zone", {"zone_id": location_id}
                )

                def fetch_data() -> dict[str, Any]:
                    self.wrapper._rate_limit()
                    try:
                        response = self.wrapper.core_client.make_api_request(
                            alerts_active_zone.sync, zone_id=location_id
                        )
                        return self._transform_alerts_data(response)
                    except NoaaApiError:
                        raise
                    except Exception as e:
                        logger.error(f"Error getting alerts for zone {location_id}: {str(e)}")
                        url = (
                            f"{self.wrapper.core_client.BASE_URL}/alerts/active/zone/{location_id}"
                        )
                        error_msg = f"Unexpected error getting alerts for zone: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        ) from e

                return cast(
                    dict[str, Any],
                    self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
                )

            # If we have a state but not precise location, get state alerts
            if not precise_location and location_type == "state" and location_id:
                logger.info(f"Fetching alerts for state: {location_id}")
                cache_key = self.wrapper._generate_cache_key("alerts_state", {"state": location_id})

                def fetch_data() -> dict[str, Any]:
                    try:
                        url = (
                            f"{self.wrapper.core_client.BASE_URL}/alerts/active?area={location_id}"
                        )
                        response = self._fetch_alerts_conditional(url)
                        return self._transform_alerts_data(response)
                    except Exception as e:
                        logger.error(f"Error getting alerts for state {location_id}: {str(e)}")
                        error_msg = f"Unexpected error getting alerts for state: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        ) from e

                return cast(
                    dict[str, Any],
                    self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
                )

            # If we couldn't determine location or state, fall back to point-radius search
            if location_type is None or location_id is None:
                logger.info(
                    f"Using point-radius search for alerts since location could not be determined: ({lat}, {lon}) with radius {radius} miles"
                )
                cache_key = self.wrapper._generate_cache_key(
                    "alerts_point", {"lat": lat, "lon": lon, "radius": radius}
                )

                def fetch_data() -> dict[str, Any]:
                    try:
                        url = f"{self.wrapper.core_client.BASE_URL}/alerts/active?point={lat},{lon}&radius={radius}"
                        response = self._fetch_alerts_conditional(url)
                        return self._transform_alerts_data(response)
                    except Exception as e:
                        logger.error(f"Error getting alerts for point ({lat}, {lon}): {str(e)}")
                        error_msg = f"Unexpected error getting alerts for point: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        ) from e

                return cast(
                    dict[str, Any],
                    self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
                )

            # Final fallback: get all active alerts
            logger.info("Falling back to all active alerts")
            cache_key = self.wrapper._generate_cache_key("alerts_all", {})

            def fetch_data() -> dict[str, Any]:
                self.wrapper._rate_limit()
                try:
                    response = self.wrapper.core_client.make_api_request(alerts_active.sync)
                    return self._transform_alerts_data(response)
                except NoaaApiError:
                    raise
                except Exception as e:
                    logger.error(f"Error getting all alerts: {str(e)}")
                    url = f"{self.wrapper.core_client.BASE_URL}/alerts/active"
                    error_msg = f"Unexpected error getting all alerts: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                    ) from e

            return cast(
                dict[str, Any],
                self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            raise ApiClientError(f"Unable to retrieve alerts data: {str(e)}") from e

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> str | None:
        """
        Get forecast discussion for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force refresh cached data

        Returns:
        -------
            Discussion text or None if not available

        """
        try:
            logger.info(f"Getting forecast discussion for coordinates: ({lat}, {lon})")
            point_data = self.wrapper.point_location.get_point_data(
                lat, lon, force_refresh=force_refresh
            )
            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                logger.warning("No forecast URL found in point data")
                return None

            parts = forecast_url.split("/")
            office_id = parts[-3]
            cache_key = self.wrapper._generate_cache_key(
                f"products/types/AFD/locations/{office_id}", {}
            )

            def fetch_data() -> str | None:
                self.wrapper._rate_limit()
                try:
                    products_url = f"{self.wrapper.core_client.BASE_URL}/products/types/AFD/locations/{office_id}"
                    products_response = self.wrapper._fetch_url(products_url)

                    if not products_response.get("@graph") or not products_response["@graph"]:
                        logger.warning(f"No AFD products found for {office_id}")
                        return None

                    latest_product = products_response["@graph"][0]
                    latest_product_id = latest_product.get("id")

                    product_url = (
                        f"{self.wrapper.core_client.BASE_URL}/products/{latest_product_id}"
                    )
                    product_response = self.wrapper._get_cached_or_fetch(
                        f"products/{latest_product_id}",
                        lambda: self.wrapper._fetch_url(product_url),
                        force_refresh=False,
                    )

                    if not product_response.get("productText"):
                        logger.warning(f"No product text found for {latest_product_id}")
                        return None

                    return cast(str | None, product_response.get("productText"))
                except Exception as e:
                    logger.error(f"Error getting discussion for {office_id}: {str(e)}")
                    return None

            return cast(
                str | None, self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting discussion: {str(e)}")
            return None

    def get_national_product(
        self, product_type: str, location: str, force_refresh: bool = False
    ) -> str | None:
        """
        Get a national product from a specific center.

        Args:
        ----
            product_type: Type of product to retrieve
            location: Location identifier
            force_refresh: Whether to force refresh cached data

        Returns:
        -------
            Product text or None if not available

        """
        try:
            endpoint = f"products/types/{product_type}/locations/{location}"
            cache_key = self.wrapper._generate_cache_key(endpoint, {})

            def fetch_data() -> str | None:
                self.wrapper._rate_limit()
                try:
                    products_url = f"{self.wrapper.core_client.BASE_URL}/products/types/{product_type}/locations/{location}"
                    products_response = self.wrapper._fetch_url(products_url)

                    if not products_response.get("@graph") or not products_response["@graph"]:
                        logger.warning(f"No products found for {product_type}/{location}")
                        return None

                    latest_product = products_response["@graph"][0]
                    latest_product_id = latest_product.get("id")

                    product_url = (
                        f"{self.wrapper.core_client.BASE_URL}/products/{latest_product_id}"
                    )
                    product_response = self.wrapper._get_cached_or_fetch(
                        f"products/{latest_product_id}",
                        lambda: self.wrapper._fetch_url(product_url),
                        force_refresh=False,
                    )

                    if not product_response.get("productText"):
                        logger.warning(f"No product text found for {latest_product_id}")
                        return None

                    return cast(str | None, product_response.get("productText"))
                except Exception as e:
                    logger.error(
                        f"Error getting national product {product_type} from {location}: {str(e)}"
                    )
                    return None

            return cast(
                str | None, self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting national product {product_type} from {location}: {str(e)}")
            return None

    def get_national_forecast_data(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get national forecast data from various centers.

        Args:
        ----
            force_refresh: Whether to force refresh cached data

        Returns:
        -------
            Dictionary containing national forecast data from various centers

        """
        return {
            "wpc": {
                "short_range": self.get_national_product("FXUS01", "KWNH", force_refresh),
                "medium_range": self.get_national_product("FXUS06", "KWNH", force_refresh),
                "extended": self.get_national_product("FXUS07", "KWNH", force_refresh),
                "qpf": self.get_national_product("FXUS02", "KWNH", force_refresh),
            },
            "spc": {
                "day1": self.get_national_product("ACUS01", "KWNS", force_refresh),
                "day2": self.get_national_product("ACUS02", "KWNS", force_refresh),
            },
            "nhc": {
                "atlantic": self.get_national_product("MIATWOAT", "KNHC", force_refresh),
                "east_pacific": self.get_national_product("MIATWOEP", "KNHC", force_refresh),
            },
        }

    def _transform_alerts_data(self, alerts_data: Any) -> dict[str, Any]:
        """Transform alerts data from the generated client format."""
        if isinstance(alerts_data, dict):
            return alerts_data
        if hasattr(alerts_data, "to_dict"):
            return cast(dict[str, Any], alerts_data.to_dict())
        return cast(dict[str, Any], alerts_data)
