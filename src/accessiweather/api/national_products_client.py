"""National products functionality for NOAA API client."""

import logging
from typing import Any, Dict, Optional

from accessiweather.api.base_client import NoaaApiClient

logger = logging.getLogger(__name__)


class NationalProductsClient(NoaaApiClient):
    """Client for national products-related NOAA API operations."""

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
            "cpc": {
                "6_10_day": self.get_national_product("FXUS05", "KWNC", force_refresh),
                "8_14_day": self.get_national_product("FXUS07", "KWNC", force_refresh),
            },
        }
        return result

    def get_national_discussion_summary(self, force_refresh: bool = False) -> dict:
        """Fetch and summarize the latest WPC Short Range and SPC Day 1 discussions.

        Args:
            force_refresh: Whether to force a refresh of the data

        Returns:
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
