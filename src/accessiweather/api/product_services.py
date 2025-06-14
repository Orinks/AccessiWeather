"""Product services for NOAA API wrapper.

This module handles fetching discussion and national product data.
"""

import logging
from typing import Any, Dict, Optional, cast

from accessiweather.api.exceptions import ApiClientError

logger = logging.getLogger(__name__)


class ApiProductServices:
    """Handles product data fetching operations."""

    def __init__(
        self,
        request_manager: Any,
        location_services: Any,
        base_url: str,
    ):
        """Initialize product services.

        Args:
            request_manager: Request manager instance
            location_services: Location services instance
            base_url: Base URL for API requests
        """
        self.request_manager = request_manager
        self.location_services = location_services
        self.base_url = base_url

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Optional[str]:
        """Get forecast discussion for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Text of the forecast discussion or None if not available
        """
        try:
            logger.info(f"Getting forecast discussion for coordinates: ({lat}, {lon})")

            # Get the point data to find the forecast office
            point_data = self.location_services.get_point_data(
                lat, lon, force_refresh=force_refresh
            )

            # Extract the forecast office ID from the forecast URL
            # Example URL: https://api.weather.gov/gridpoints/PHI/31,70/forecast
            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                logger.warning("No forecast URL found in point data")
                return None

            parts = forecast_url.split("/")
            office_id = parts[-3]

            # Generate cache key for the discussion
            cache_key = self.request_manager.generate_cache_key(
                f"products/types/AFD/locations/{office_id}"
            )

            def fetch_data() -> Optional[str]:
                self.request_manager.rate_limit()
                try:
                    # Get the list of products
                    # Since product_locations doesn't support these parameters, use a direct API call
                    products_url = f"{self.base_url}/products/types/AFD/locations/{office_id}"
                    products_response = self.request_manager.fetch_url(products_url)

                    # Check if the response has a @graph property
                    if not products_response.get("@graph") or not products_response["@graph"]:
                        logger.warning(f"No AFD products found for {office_id}")
                        return None

                    # Get the latest product
                    latest_product = products_response["@graph"][0]
                    latest_product_id = latest_product.get("id")

                    # Get the product text
                    # Since product module is not available, we'll use a direct API call
                    product_url = f"{self.base_url}/products/{latest_product_id}"
                    product_response = self.request_manager.get_cached_or_fetch(
                        f"products/{latest_product_id}",
                        lambda: self.request_manager.fetch_url(product_url),
                        force_refresh=False,
                    )

                    if not product_response.get("productText"):
                        logger.warning(f"No product text found for {latest_product_id}")
                        return None

                    return cast(Optional[str], product_response.get("productText"))
                except Exception as e:
                    logger.error(f"Error getting discussion for {office_id}: {str(e)}")
                    # Return None instead of raising an error for discussions
                    return None

            return cast(
                Optional[str],
                self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting discussion: {str(e)}")
            return None

    def get_national_product(
        self, product_type: str, location: str, force_refresh: bool = False
    ) -> Optional[str]:
        """Get a national product from a specific center.

        Args:
            product_type: Product type code (e.g., "FXUS01")
            location: Location code (e.g., "KWNH")
            force_refresh: Whether to force a refresh of the data

        Returns:
            Text of the product or None if not available
        """
        try:
            endpoint = f"products/types/{product_type}/locations/{location}"
            logger.debug(
                f"Requesting national product: type={product_type}, "
                f"location={location}, endpoint={endpoint}"
            )

            # Generate cache key for the product
            cache_key = self.request_manager.generate_cache_key(endpoint)

            def fetch_data() -> Optional[str]:
                self.request_manager.rate_limit()
                try:
                    # Get the list of products
                    # Since product_locations doesn't support these parameters, use a direct API call
                    products_url = (
                        f"{self.base_url}/products/types/{product_type}/locations/{location}"
                    )
                    products_response = self.request_manager.fetch_url(products_url)

                    # Check if the response has a @graph property
                    if not products_response.get("@graph") or not products_response["@graph"]:
                        logger.warning(f"No {product_type} products found for {location}")
                        return None

                    # Get the latest product
                    latest_product = products_response["@graph"][0]
                    latest_product_id = latest_product.get("id")

                    # Get the product text
                    product_url = f"{self.base_url}/products/{latest_product_id}"
                    product_response = self.request_manager.get_cached_or_fetch(
                        f"products/{latest_product_id}",
                        lambda: self.request_manager.fetch_url(product_url),
                        force_refresh=False,
                    )

                    if not product_response.get("productText"):
                        logger.warning(f"No product text found for {latest_product_id}")
                        return None

                    return cast(Optional[str], product_response.get("productText"))
                except Exception as e:
                    logger.error(
                        f"Error getting national product {product_type} from {location}: {str(e)}"
                    )
                    # Return None instead of raising an error for products
                    return None

            return cast(
                Optional[str],
                self.request_manager.get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting national product: {str(e)}")
            return None

    def get_national_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get national forecast data from various centers.

        Args:
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dictionary containing national forecast data
        """
        result = {
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
        return result
