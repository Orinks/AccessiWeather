"""
Alerts and national products functionality for NOAA API client.

This module provides methods for weather alerts, location identification,
and national weather products retrieval.
"""

import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)


class AlertsAndProductsMixin:
    """
    Mixin class providing alerts and national products functionality.

    This mixin expects the following methods to be provided by the implementing class:
    - _make_request(endpoint_or_url, params=None, use_full_url=False, force_refresh=False)
    - identify_location_type(lat, lon, force_refresh=False) -> Tuple[Optional[str], Optional[str]]
    - get_point_data(lat, lon, force_refresh=False) -> Dict[str, Any]

    And the following attributes:
    - BASE_URL: str
    """

    # These methods must be implemented by the class that uses this mixin
    def _make_request(
        self,
        endpoint_or_url: str,
        params: dict[str, Any] | None = None,
        use_full_url: bool = False,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Make a request to the API. Must be implemented by the using class."""
        raise NotImplementedError("_make_request must be implemented by the using class")

    def identify_location_type(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> tuple[str | None, str | None]:
        """Identify location type. Must be implemented by the using class."""
        raise NotImplementedError("identify_location_type must be implemented by the using class")

    def get_point_data(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """Get point data. Must be implemented by the using class."""
        raise NotImplementedError("get_point_data must be implemented by the using class")

    @property
    def BASE_URL(self) -> str:
        """Base URL for the API. Must be implemented by the using class."""
        raise NotImplementedError("BASE_URL must be implemented by the using class")

    def get_alerts(
        self,
        lat: float,
        lon: float,
        radius: float = 50,
        precise_location: bool = True,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Get active weather alerts for the given coordinates.

        Uses point-based queries as the primary method for precise_location=True,
        which provides accurate polygon intersection for county-based alerts
        (tornado warnings, severe thunderstorm warnings, flash floods, etc.).

        Args:
        ----
            lat: Latitude of the location
            lon: Longitude of the location
            radius: Radius in miles to search for alerts (unused with point query,
                    kept for API compatibility)
            precise_location: Whether to get alerts for the precise location (point query)
                             or for the entire state (area query)
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
        -------
            Dictionary containing alert data

        """
        logger.info(
            f"Getting alerts for coordinates: ({lat}, {lon}), "
            f"precise_location={precise_location}"
        )

        if precise_location:
            # Use point query for precise location - this provides accurate
            # polygon intersection for county-based alerts (tornado warnings,
            # severe thunderstorm warnings, flash floods, etc.)
            logger.info(f"Fetching alerts using point query: ({lat}, {lon})")
            return self._make_request(
                "alerts/active",
                params={"point": f"{lat},{lon}"},
                force_refresh=force_refresh,
            )

        # For non-precise location, get alerts for the entire state
        # First, identify the location to get state info
        location_type, location_id = self.identify_location_type(
            lat, lon, force_refresh=force_refresh
        )

        # Extract state code from location info
        state = None
        if location_type == "state":
            state = location_id
        elif location_id and len(location_id) >= 2:
            # Extract state from zone code (first two characters, e.g., "NJ" from "NJC005")
            state = location_id[:2]

        if state:
            logger.info(f"Fetching alerts for state: {state}")
            return self._make_request(
                "alerts/active",
                params={"area": state},
                force_refresh=force_refresh,
            )

        # Fallback: if we couldn't determine state, use point query anyway
        logger.warning(
            f"Could not determine state for ({lat}, {lon}), falling back to point query"
        )
        return self._make_request(
            "alerts/active",
            params={"point": f"{lat},{lon}"},
            force_refresh=force_refresh,
        )

    def get_alerts_direct(self, url: str, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get active weather alerts directly from a provided URL.

        Args:
        ----
            url: Full URL to the alerts endpoint
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
        -------
            Dictionary containing alert data

        """
        logging.info(f"Fetching alerts directly from URL: {url}")
        return self._make_request(url, use_full_url=True, force_refresh=force_refresh)

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> str | None:
        """
        Get the forecast discussion for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
        -------
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

    def get_national_product(
        self, product_type: str, location: str, force_refresh: bool = False
    ) -> str | None:
        """
        Get a national product from a specific center.

        Args:
        ----
            product_type: Product type code (e.g., "FXUS01")
            location: Location code (e.g., "KWNH")
            force_refresh: Whether to force a refresh of the data

        Returns:
        -------
            Text of the product or None if not available

        """
        try:
            endpoint = f"products/types/{product_type}/locations/{location}"
            logger.debug(
                f"Requesting national product: type={product_type}, "
                f"location={location}, endpoint={endpoint}"
            )
            products = self._make_request(endpoint, force_refresh=force_refresh)
            logger.debug(f"Raw product list response for {product_type}/{location}: {products}")

            if "@graph" not in products or not products["@graph"]:
                logger.warning(
                    f"No '@graph' key or empty product list for {product_type}/{location}"
                )
                return None

            # Get the latest product
            latest_product = products["@graph"][0]
            latest_product_id = latest_product["id"]
            logger.debug(f"Latest product id for {product_type}/{location}: {latest_product_id}")

            # Get the product text
            product_endpoint = f"products/{latest_product_id}"
            product = self._make_request(product_endpoint, force_refresh=force_refresh)
            logger.debug(f"Raw product text response for {product_type}/{location}: {product}")

            if "productText" not in product:
                logger.warning(f"No 'productText' in product for {product_type}/{location}")
                return None

            return product.get("productText")
        except Exception as e:
            logger.error(f"Error getting national product {product_type} from {location}: {str(e)}")
            return None

    def get_national_forecast_data(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get national forecast data from various centers.

        Returns
        -------
            Dictionary containing national forecast data

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
            "cpc": {
                "6_10_day": self.get_national_product("FXUS05", "KWNC", force_refresh),
                "8_14_day": self.get_national_product("FXUS07", "KWNC", force_refresh),
            },
        }

    def get_national_discussion_summary(self, force_refresh: bool = False) -> dict:
        """
        Fetch and summarize the latest WPC Short Range and SPC Day 1 discussions.

        Returns
        -------
            dict: Summary of WPC and SPC discussions

        """

        def summarize(text, lines=10):
            if not text:
                return "No discussion available."
            # Split into lines and join the first N non-empty lines
            summary_lines = [line for line in text.splitlines() if line.strip()][:lines]
            return "\n".join(summary_lines)

        wpc_short = self.get_national_product("FXUS01", "KWNH", force_refresh)
        spc_day1 = self.get_national_product("ACUS01", "KWNS", force_refresh)
        return {
            "wpc": {"short_range_summary": summarize(wpc_short)},
            "spc": {"day1_summary": summarize(spc_day1)},
        }
