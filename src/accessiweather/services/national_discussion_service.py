"""
National Discussion Service for AccessiWeather.

Provide functionality to fetch national weather discussions from IEM's
plain-text NWS text product endpoint.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from accessiweather.iem_client import IemProductFetchError, fetch_iem_afos_text_sync
from accessiweather.services.national_discussion_classification import (
    classify_pmd_discussion,
    classify_swo_outlook,
)
from accessiweather.services.national_discussion_http import (
    make_html_request,
    make_json_request,
    rate_limit,
)
from accessiweather.services.national_discussion_parsing import (
    extract_cpc_outlook_text,
    extract_nhc_outlook_text,
)

logger = logging.getLogger(__name__)

# NWS API base URL retained for legacy helper compatibility.
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

# Default cache TTL (1 hour)
DEFAULT_CACHE_TTL = 3600

IEM_NATIONAL_PRODUCTS = {
    "wpc": {
        "short_range": ("PMDSPD", "Short Range Forecast (Days 1-3)"),
        "medium_range": ("PMDEPD", "Medium Range Forecast (Days 3-7)"),
        "extended": ("PMDET4", "Extended Forecast (Days 8-10)"),
    },
    "spc": {
        "day1": ("SWODY1", "Day 1 Convective Outlook"),
        "day2": ("SWODY2", "Day 2 Convective Outlook"),
        "day3": ("SWODY3", "Day 3 Convective Outlook"),
    },
    "qpf": {
        "qpf": ("QPFPFD", "Quantitative Precipitation Forecast Discussion"),
    },
    "nhc": {
        "atlantic_outlook": ("TWOAT", "Atlantic Tropical Weather Outlook"),
        "east_pacific_outlook": ("TWOEP", "East Pacific Tropical Weather Outlook"),
    },
    "cpc": {
        "outlook": ("PMDMRD", "CPC 6-10 & 8-14 Day Outlook"),
    },
}


class NationalDiscussionService:
    """Fetch national weather discussions via IEM AFOS plain-text products."""

    def __init__(
        self,
        request_delay: float = MIN_REQUEST_INTERVAL,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
        timeout: int = 10,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        """Initialize the service with request, retry, timeout, and cache settings."""
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
        rate_limit(self, time_module=time, logger=logger)

    def _make_request(self, url: str) -> dict[str, Any]:
        """Make an HTTP GET request expecting JSON with retry logic."""
        return make_json_request(
            self,
            url,
            httpx_module=httpx,
            client_factory=httpx.Client,
            time_module=time,
            logger=logger,
        )

    def _make_html_request(self, url: str) -> dict[str, Any]:
        """Make an HTTP GET request expecting HTML with retry logic."""
        return make_html_request(
            self,
            url,
            httpx_module=httpx,
            client_factory=httpx.Client,
            time_module=time,
            logger=logger,
        )

    def _fetch_iem_text_product(self, pil: str) -> dict[str, Any]:
        """Fetch a plain-text national product from IEM's AFOS endpoint."""
        self._rate_limit()
        try:
            product = fetch_iem_afos_text_sync(
                pil, timeout=self.timeout, user_agent=HEADERS["User-Agent"]
            )
        except IemProductFetchError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "text": product.product_text}

    def _fetch_iem_product_group(
        self,
        group: str,
        unavailable_text: str,
    ) -> dict[str, dict[str, str]]:
        """Fetch a configured group of national AFOS products."""
        result: dict[str, dict[str, str]] = {}
        for key, (pil, title) in IEM_NATIONAL_PRODUCTS[group].items():
            product_result = self._fetch_iem_text_product(pil)
            if product_result["success"]:
                text = product_result["text"]
            else:
                text = f"Error fetching {title}: {product_result['error']}"
            result[key] = {"title": title, "text": text or unavailable_text}
        return result

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
        return classify_pmd_discussion(text)

    def _classify_swo_outlook(self, text: str) -> str | None:
        """
        Classify a SWO product into day1, day2, or day3.

        Classifies by WMO header codes in product text (e.g., SWODY1).

        Args:
            text: The product text content or header string.

        Returns:
            Classification key or None if not a target outlook.

        """
        return classify_swo_outlook(text)

    def fetch_wpc_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch WPC prognostic meteorological discussions (PMD).

        Returns:
            Dict with keys 'short_range', 'medium_range', 'extended'.
            Each value is a dict with 'title' and 'text' keys.

        """
        return self._fetch_iem_product_group("wpc", "Discussion not available")

    def fetch_spc_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch SPC convective outlook discussions (SWO).

        Returns:
            Dict with keys 'day1', 'day2', 'day3'.
            Each value is a dict with 'title' and 'text' keys.

        """
        return self._fetch_iem_product_group("spc", "Outlook not available")

    def fetch_qpf_discussion(self) -> dict[str, dict[str, str]]:
        """
        Fetch QPF (Quantitative Precipitation Forecast) discussion.

        Returns:
            Dict with key 'qpf'. Value is a dict with 'title' and 'text' keys.

        """
        return self._fetch_iem_product_group("qpf", "QPF discussion not available")

    @staticmethod
    def _extract_nhc_outlook_text(html: str) -> str:
        """Extract tropical weather outlook text from legacy HTML fixtures."""
        return extract_nhc_outlook_text(html)

    @staticmethod
    def is_hurricane_season() -> bool:
        """
        Check if the current date falls within Atlantic hurricane season.

        Returns:
            True if current month is June through November, False otherwise.

        """
        return datetime.now(UTC).month in (6, 7, 8, 9, 10, 11)

    def fetch_nhc_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch NHC tropical weather outlooks via IEM AFOS products.

        Returns:
            Dict with keys 'atlantic_outlook' and 'east_pacific_outlook'.
            Each value is a dict with 'title' and 'text' keys.

        """
        return self._fetch_iem_product_group("nhc", "Tropical outlook not available")

    @staticmethod
    def _extract_cpc_outlook_text(html: str, label: str) -> str | None:
        """Extract CPC outlook text from legacy HTML fixtures."""
        return extract_cpc_outlook_text(html, label)

    def fetch_cpc_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch CPC 6-10 and 8-14 Day prognostic discussion via IEM AFOS.

        Returns:
            Dict with key 'outlook'. Value is a dict with 'title' and 'text'.
            The single discussion document covers both 6-10 and 8-14 day periods.

        """
        return self._fetch_iem_product_group(
            "cpc",
            "CPC outlook discussion is currently unavailable.",
        )

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
