"""
National Discussion Service for AccessiWeather.

This module provides functionality to fetch national weather discussions
from the NWS API (api.weather.gov/products/types/), including WPC discussions
(PMD), SPC convective outlooks (SWO), and QPF discussions.
"""

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# NWS API base URL
NWS_API_BASE = "https://api.weather.gov"

# Required User-Agent header for NWS API
HEADERS = {
    "User-Agent": "AccessiWeather/1.0 (AccessiWeather)",
    "Accept": "application/geo+json",
}

# Rate limit: minimum seconds between requests
MIN_REQUEST_INTERVAL = 1.0

# Product type codes
PRODUCT_TYPE_PMD = "PMD"  # Prognostic Meteorological Discussion (WPC)
PRODUCT_TYPE_SWO = "SWO"  # Severe Weather Outlook (SPC)
PRODUCT_TYPE_QPF = "QPF"  # Quantitative Precipitation Forecast


class NationalDiscussionService:
    """
    Service for fetching national weather discussions via the NWS API.

    Fetches WPC discussions (PMD), SPC convective outlooks (SWO), and QPF
    discussions using the api.weather.gov/products/types/ endpoint.
    Includes rate limiting and retry logic.
    """

    def __init__(
        self,
        request_delay: float = MIN_REQUEST_INTERVAL,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
        timeout: int = 10,
    ):
        """
        Initialize the service.

        Args:
            request_delay: Minimum delay between requests in seconds.
            max_retries: Maximum number of retry attempts for failed requests.
            retry_backoff: Multiplier for increasing delay between retries.
            timeout: Request timeout in seconds.

        """
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.timeout = timeout
        self._last_request_time: float = 0.0
        self.headers = HEADERS.copy()

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = time.time()
        wait = self.request_delay - (now - self._last_request_time)
        if wait > 0:
            logger.debug(f"Rate limiting: sleeping {wait:.2f}s")
            time.sleep(wait)
        self._last_request_time = time.time()

    def _make_request(self, url: str) -> dict[str, Any]:
        """
        Make an HTTP GET request with retry logic.

        Args:
            url: The URL to request.

        Returns:
            Dict with 'success' bool and either 'data' (parsed JSON) or 'error' string.

        """
        last_error = ""
        for attempt in range(self.max_retries + 1):
            self._rate_limit()
            try:
                logger.debug(f"Requesting {url} (attempt {attempt + 1})")
                with httpx.Client() as client:
                    response = client.get(url, headers=self.headers, timeout=self.timeout)
                    response.raise_for_status()
                return {"success": True, "data": response.json()}
            except httpx.TimeoutException:
                last_error = "Request timed out"
            except httpx.ConnectError:
                last_error = "Connection error"
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP error: {e.response.status_code}"
            except httpx.RequestError as e:
                last_error = f"Request error: {e}"
            except Exception as e:
                last_error = f"Unexpected error: {e}"

            if attempt < self.max_retries:
                delay = self.request_delay * (self.retry_backoff**attempt)
                logger.info(f"Retrying in {delay:.1f}s after: {last_error}")
                time.sleep(delay)

        logger.error(f"All attempts failed for {url}: {last_error}")
        return {"success": False, "error": last_error}

    def _fetch_latest_product(self, product_type: str) -> dict[str, Any]:
        """
        Fetch the latest product of a given type from the NWS API.

        Args:
            product_type: NWS product type code (e.g. 'PMD', 'SWO', 'QPF').

        Returns:
            Dict with 'success' and either 'products' list or 'error'.

        """
        url = f"{NWS_API_BASE}/products/types/{product_type}"
        result = self._make_request(url)
        if not result["success"]:
            return result

        try:
            graphs = result["data"].get("@graph", [])
            if not graphs:
                return {"success": False, "error": f"No {product_type} products found"}
            return {"success": True, "products": graphs}
        except (KeyError, TypeError) as e:
            return {"success": False, "error": f"Failed to parse product list: {e}"}

    def _fetch_product_text(self, product_id: str) -> dict[str, Any]:
        """
        Fetch the full text of a specific product by ID.

        Args:
            product_id: The NWS product ID.

        Returns:
            Dict with 'success' and either 'text' or 'error'.

        """
        url = f"{NWS_API_BASE}/products/{product_id}"
        result = self._make_request(url)
        if not result["success"]:
            return result

        try:
            text = result["data"].get("productText", "")
            if not text:
                return {"success": False, "error": "Product text is empty"}
            return {"success": True, "text": text}
        except (KeyError, TypeError) as e:
            return {"success": False, "error": f"Failed to parse product text: {e}"}

    def _classify_pmd_discussion(self, product_name: str) -> str | None:
        """
        Classify a PMD product into short_range, medium_range, or extended.

        Args:
            product_name: The product name/issuance text.

        Returns:
            Classification key or None if not a target discussion.

        """
        name_lower = product_name.lower() if product_name else ""
        if "short range" in name_lower or "day 1" in name_lower or "spd" in name_lower:
            return "short_range"
        if (
            "medium range" in name_lower
            or "3-7" in name_lower
            or "epd" in name_lower
            or "extended" in name_lower
        ):
            # Check for extended first since it might also contain 'extended'
            if "8-10" in name_lower or "day 8" in name_lower:
                return "extended"
            return "medium_range"
        if "8-10" in name_lower or "day 8" in name_lower:
            return "extended"
        return None

    def _classify_swo_outlook(self, product_name: str) -> str | None:
        """
        Classify a SWO product into day1, day2, or day3.

        Args:
            product_name: The product name/issuance text.

        Returns:
            Classification key or None if not a target outlook.

        """
        name_lower = product_name.lower() if product_name else ""
        if "day 1" in name_lower:
            return "day1"
        if "day 2" in name_lower:
            return "day2"
        if "day 3" in name_lower:
            return "day3"
        return None

    def fetch_wpc_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch WPC prognostic meteorological discussions (PMD).

        Returns:
            Dict with keys 'short_range', 'medium_range', 'extended'.
            Each value is a dict with 'title' and 'text' keys.
            On error, 'text' contains the error message.

        """
        result: dict[str, dict[str, str]] = {
            "short_range": {"title": "Short Range Forecast (Days 1-3)", "text": ""},
            "medium_range": {"title": "Medium Range Forecast (Days 3-7)", "text": ""},
            "extended": {"title": "Extended Forecast (Days 8-10)", "text": ""},
        }

        products_result = self._fetch_latest_product(PRODUCT_TYPE_PMD)
        if not products_result["success"]:
            error_msg = f"Error fetching WPC discussions: {products_result['error']}"
            for key in result:
                result[key]["text"] = error_msg
            return result

        products = products_result["products"]

        # Try to find and fetch each discussion type
        fetched: set[str] = set()
        for product in products:
            product_name = product.get("issuingOffice", "") + " " + product.get("name", "")
            product_id = product.get("id", "")
            if not product_id:
                # Try extracting from @id URL
                at_id = product.get("@id", "")
                if at_id:
                    product_id = at_id.rsplit("/", 1)[-1]

            classification = self._classify_pmd_discussion(product_name)
            if classification and classification not in fetched:
                text_result = self._fetch_product_text(product_id)
                if text_result["success"]:
                    result[classification]["text"] = text_result["text"]
                else:
                    result[classification]["text"] = f"Error: {text_result['error']}"
                fetched.add(classification)

            if len(fetched) == 3:
                break

        # Fill in any missing discussions
        for key in result:
            if not result[key]["text"]:
                result[key]["text"] = "Discussion not available"

        return result

    def fetch_spc_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch SPC convective outlook discussions (SWO).

        Returns:
            Dict with keys 'day1', 'day2', 'day3'.
            Each value is a dict with 'title' and 'text' keys.
            On error, 'text' contains the error message.

        """
        result: dict[str, dict[str, str]] = {
            "day1": {"title": "Day 1 Convective Outlook", "text": ""},
            "day2": {"title": "Day 2 Convective Outlook", "text": ""},
            "day3": {"title": "Day 3 Convective Outlook", "text": ""},
        }

        products_result = self._fetch_latest_product(PRODUCT_TYPE_SWO)
        if not products_result["success"]:
            error_msg = f"Error fetching SPC discussions: {products_result['error']}"
            for key in result:
                result[key]["text"] = error_msg
            return result

        products = products_result["products"]

        fetched: set[str] = set()
        for product in products:
            product_name = product.get("issuingOffice", "") + " " + product.get("name", "")
            product_id = product.get("id", "")
            if not product_id:
                at_id = product.get("@id", "")
                if at_id:
                    product_id = at_id.rsplit("/", 1)[-1]

            classification = self._classify_swo_outlook(product_name)
            if classification and classification not in fetched:
                text_result = self._fetch_product_text(product_id)
                if text_result["success"]:
                    result[classification]["text"] = text_result["text"]
                else:
                    result[classification]["text"] = f"Error: {text_result['error']}"
                fetched.add(classification)

            if len(fetched) == 3:
                break

        for key in result:
            if not result[key]["text"]:
                result[key]["text"] = "Outlook not available"

        return result

    def fetch_qpf_discussion(self) -> dict[str, dict[str, str]]:
        """
        Fetch QPF (Quantitative Precipitation Forecast) discussion.

        Returns:
            Dict with key 'qpf'.
            Value is a dict with 'title' and 'text' keys.
            On error, 'text' contains the error message.

        """
        result: dict[str, dict[str, str]] = {
            "qpf": {"title": "Quantitative Precipitation Forecast Discussion", "text": ""},
        }

        products_result = self._fetch_latest_product(PRODUCT_TYPE_QPF)
        if not products_result["success"]:
            result["qpf"]["text"] = f"Error fetching QPF discussion: {products_result['error']}"
            return result

        products = products_result["products"]
        if products:
            product = products[0]
            product_id = product.get("id", "")
            if not product_id:
                at_id = product.get("@id", "")
                if at_id:
                    product_id = at_id.rsplit("/", 1)[-1]

            text_result = self._fetch_product_text(product_id)
            if text_result["success"]:
                result["qpf"]["text"] = text_result["text"]
            else:
                result["qpf"]["text"] = f"Error: {text_result['error']}"
        else:
            result["qpf"]["text"] = "QPF discussion not available"

        return result
