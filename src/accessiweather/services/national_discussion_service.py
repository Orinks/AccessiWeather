"""
National Discussion Service for AccessiWeather.

Provide functionality to fetch national weather discussions from the NWS API
(api.weather.gov/products/types/) and scrape NHC tropical outlooks and CPC outlooks.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

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

# NHC tropical outlook URLs
NHC_ATLANTIC_OUTLOOK_URL = "https://www.nhc.noaa.gov/gtwo.php?basin=atlc"
NHC_EAST_PACIFIC_OUTLOOK_URL = "https://www.nhc.noaa.gov/gtwo.php?basin=epac"

# CPC outlook URLs
CPC_6_10_URL = "https://www.cpc.ncep.noaa.gov/products/predictions/610day/fxus06.html"
# 8-14 day discussion is in the same document as 6-10 day
CPC_8_14_URL = CPC_6_10_URL

# Default cache TTL (1 hour)
DEFAULT_CACHE_TTL = 3600


class NationalDiscussionService:
    """
    Service for fetching national weather discussions via the NWS API and web scraping.

    Fetch WPC discussions (PMD), SPC convective outlooks (SWO), QPF discussions,
    NHC tropical weather outlooks, and CPC extended outlooks. Include rate limiting,
    retry logic, and caching.
    """

    def __init__(
        self,
        request_delay: float = MIN_REQUEST_INTERVAL,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
        timeout: int = 10,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        """
        Initialize the service.

        Args:
            request_delay: Minimum delay between requests in seconds.
            max_retries: Maximum number of retry attempts for failed requests.
            retry_backoff: Multiplier for increasing delay between retries.
            timeout: Request timeout in seconds.
            cache_ttl: Cache time-to-live in seconds (default 3600 = 1 hour).

        """
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.timeout = timeout
        self._last_request_time: float = 0.0
        self.headers = HEADERS.copy()

        # Caching
        self.cache_ttl = cache_ttl
        self._cache: dict[str, Any] | None = None
        self._cache_timestamp: float = 0.0

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
        Make an HTTP GET request expecting JSON with retry logic.

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

    def _make_html_request(self, url: str) -> dict[str, Any]:
        """
        Make an HTTP GET request expecting HTML with retry logic.

        Args:
            url: The URL to request.

        Returns:
            Dict with 'success' bool and either 'html' or 'error' string.

        """
        last_error = ""
        for attempt in range(self.max_retries + 1):
            self._rate_limit()
            try:
                logger.debug(f"Requesting HTML {url} (attempt {attempt + 1})")
                with httpx.Client() as client:
                    response = client.get(
                        url,
                        headers={"User-Agent": "AccessiWeather/1.0 (AccessiWeather)"},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                return {"success": True, "html": response.text}
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

    def _classify_pmd_discussion(self, text: str) -> str | None:
        """
        Classify a PMD product into short_range, medium_range, or extended.

        Classifies by WMO header codes in the product text (e.g., PMDSPD,
        PMDEPD) since the API productName is always generic.

        Args:
            text: The product text content or header string.

        Returns:
            Classification key or None if not a target discussion.

        """
        text_upper = text.upper() if text else ""
        # WMO header codes (most reliable)
        if "PMDSPD" in text_upper:
            return "short_range"
        if "PMDEPD" in text_upper:
            return "medium_range"
        if "PMDET" in text_upper:
            return "extended"
        # Fallback to keyword matching
        text_lower = text.lower() if text else ""
        if "short range" in text_lower:
            return "short_range"
        if "medium range" in text_lower or "3-7 day" in text_lower:
            return "medium_range"
        if "extended" in text_lower and ("8-10" in text_lower or "day 8" in text_lower):
            return "extended"
        return None

    def _classify_swo_outlook(self, text: str) -> str | None:
        """
        Classify a SWO product into day1, day2, or day3.

        Classifies by WMO header codes in product text (e.g., SWODY1).

        Args:
            text: The product text content or header string.

        Returns:
            Classification key or None if not a target outlook.

        """
        text_upper = text.upper() if text else ""
        # WMO header codes
        if "SWODY1" in text_upper:
            return "day1"
        if "SWODY2" in text_upper:
            return "day2"
        if "SWODY3" in text_upper:
            return "day3"
        # Fallback to keyword matching
        text_lower = text.lower() if text else ""
        if "day 1" in text_lower:
            return "day1"
        if "day 2" in text_lower:
            return "day2"
        if "day 3" in text_lower:
            return "day3"
        return None

    def fetch_wpc_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch WPC prognostic meteorological discussions (PMD).

        Returns:
            Dict with keys 'short_range', 'medium_range', 'extended'.
            Each value is a dict with 'title' and 'text' keys.

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
        fetched: set[str] = set()
        for product in products:
            product_id = product.get("id", "")
            if not product_id:
                at_id = product.get("@id", "")
                if at_id:
                    product_id = at_id.rsplit("/", 1)[-1]

            # Fetch text first, then classify by content (API name is generic)
            text_result = self._fetch_product_text(product_id)
            if not text_result["success"]:
                continue

            classification = self._classify_pmd_discussion(text_result["text"])
            if classification and classification not in fetched:
                result[classification]["text"] = text_result["text"]
                fetched.add(classification)

            if len(fetched) == 3:
                break

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
            product_id = product.get("id", "")
            if not product_id:
                at_id = product.get("@id", "")
                if at_id:
                    product_id = at_id.rsplit("/", 1)[-1]

            # Fetch text first, then classify by content
            text_result = self._fetch_product_text(product_id)
            if not text_result["success"]:
                continue

            classification = self._classify_swo_outlook(text_result["text"])
            if classification and classification not in fetched:
                result[classification]["text"] = text_result["text"]
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
            Dict with key 'qpf'. Value is a dict with 'title' and 'text' keys.

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

    @staticmethod
    def _extract_nhc_outlook_text(html: str) -> str:
        """
        Extract tropical weather outlook text from NHC HTML page.

        Args:
            html: Raw HTML from NHC outlook page.

        Returns:
            Extracted outlook text or error message.

        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            pre = soup.find("pre")
            if pre:
                return pre.get_text().strip()

            div = soup.find("div", id=lambda i: i and "outlook" in i.lower())
            if div:
                return div.get_text().strip()

            el = soup.find(class_=lambda c: c and "outlook" in str(c).lower())
            if el:
                return el.get_text().strip()

            return "Unable to parse NHC outlook text from page"
        except Exception as e:
            return f"Error parsing NHC outlook: {e}"

    @staticmethod
    def is_hurricane_season() -> bool:
        """
        Check if the current date falls within Atlantic hurricane season.

        Returns:
            True if current month is June through November, False otherwise.

        """
        return datetime.now(timezone.utc).month in (6, 7, 8, 9, 10, 11)

    def fetch_nhc_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch NHC tropical weather outlooks by scraping nhc.noaa.gov.

        Returns:
            Dict with keys 'atlantic_outlook' and 'east_pacific_outlook'.
            Each value is a dict with 'title' and 'text' keys.

        """
        result: dict[str, dict[str, str]] = {
            "atlantic_outlook": {
                "title": "Atlantic Tropical Weather Outlook",
                "text": "",
            },
            "east_pacific_outlook": {
                "title": "East Pacific Tropical Weather Outlook",
                "text": "",
            },
        }

        atlantic_result = self._make_html_request(NHC_ATLANTIC_OUTLOOK_URL)
        if atlantic_result["success"]:
            result["atlantic_outlook"]["text"] = self._extract_nhc_outlook_text(
                atlantic_result["html"]
            )
        else:
            result["atlantic_outlook"]["text"] = (
                f"Error fetching Atlantic outlook: {atlantic_result['error']}"
            )

        epac_result = self._make_html_request(NHC_EAST_PACIFIC_OUTLOOK_URL)
        if epac_result["success"]:
            result["east_pacific_outlook"]["text"] = self._extract_nhc_outlook_text(
                epac_result["html"]
            )
        else:
            result["east_pacific_outlook"]["text"] = (
                f"Error fetching East Pacific outlook: {epac_result['error']}"
            )

        return result

    @staticmethod
    def _extract_cpc_outlook_text(html: str, label: str) -> str | None:
        """
        Extract outlook text from a CPC outlook HTML page.

        Args:
            html: Raw HTML content.
            label: Human-readable label for logging.

        Returns:
            Extracted text, or None if extraction failed.

        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            pre = soup.find("pre")
            if pre:
                text = pre.get_text().strip()
                if text:
                    return text

            for selector in [
                {"class_": "contentArea"},
                {"class_": "mainContent"},
                {"id": "content"},
            ]:
                div = soup.find("div", **selector)
                if div:
                    text = div.get_text().strip()
                    if text:
                        return text

            body = soup.find("body")
            if body:
                texts = [
                    p.get_text().strip()
                    for p in body.find_all(["p", "div"])
                    if p.get_text().strip()
                ]
                if texts:
                    longest = max(texts, key=len)
                    if len(longest) > 100:
                        return longest

            logger.error(f"Could not extract CPC {label} outlook text")
            return None
        except Exception as e:
            logger.error(f"Error parsing CPC {label} outlook HTML: {e}")
            return None

    def fetch_cpc_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch CPC 6-10 Day and 8-14 Day extended outlooks via scraping.

        Returns:
            Dict with keys 'outlook_6_10' and 'outlook_8_14'.
            Each value is a dict with 'title' and 'text' keys.

        """
        result: dict[str, dict[str, str]] = {
            "outlook_6_10": {"title": "CPC 6-10 Day Outlook", "text": ""},
            "outlook_8_14": {"title": "CPC 8-14 Day Outlook", "text": ""},
        }

        for key, url, label in [
            ("outlook_6_10", CPC_6_10_URL, "6-10 Day"),
            ("outlook_8_14", CPC_8_14_URL, "8-14 Day"),
        ]:
            html_result = self._make_html_request(url)
            if html_result["success"]:
                text = self._extract_cpc_outlook_text(html_result["html"], label)
                if text:
                    result[key]["text"] = text
                else:
                    result[key]["text"] = f"CPC {label} Outlook is currently unavailable."
            else:
                result[key]["text"] = f"Error fetching CPC {label} outlook: {html_result['error']}"

        return result

    def fetch_all_discussions(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Fetch all national discussions with caching.

        Returns a unified dict with keys: wpc, spc, qpf, nhc, cpc.
        NHC data is only fetched during hurricane season (June-November).

        Args:
            force_refresh: If True, bypass cache and fetch fresh data.

        Returns:
            Unified dict with all discussion data.

        """
        now = time.time()

        # Return cached data if valid and not forcing refresh
        if (
            not force_refresh
            and self._cache is not None
            and now - self._cache_timestamp < self.cache_ttl
        ):
            logger.info("Returning cached discussion data")
            return self._cache

        logger.info("Fetching all national discussions")

        result: dict[str, Any] = {
            "wpc": self.fetch_wpc_discussions(),
            "spc": self.fetch_spc_discussions(),
            "qpf": self.fetch_qpf_discussion(),
            "nhc": {},
            "cpc": self.fetch_cpc_discussions(),
        }

        # Only fetch NHC during hurricane season
        if self.is_hurricane_season():
            result["nhc"] = self.fetch_nhc_discussions()
        else:
            result["nhc"] = {
                "atlantic_outlook": {
                    "title": "Atlantic Tropical Weather Outlook",
                    "text": "NHC tropical outlooks are available during hurricane season (June-November).",
                },
                "east_pacific_outlook": {
                    "title": "East Pacific Tropical Weather Outlook",
                    "text": "NHC tropical outlooks are available during hurricane season (June-November).",
                },
            }

        # Update cache
        self._cache = result
        self._cache_timestamp = time.time()

        return result
