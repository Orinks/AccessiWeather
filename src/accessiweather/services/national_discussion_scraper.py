"""National Discussion Scraper for AccessiWeather.

This module provides functionality to scrape and parse national weather discussions
from NOAA websites, including the Weather Prediction Center (WPC) and Storm Prediction
Center (SPC). It includes rate limiting to avoid overloading the servers.
"""

import logging
import time
from typing import Dict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "AccessiWeatherBot/1.0 (contact: youremail@example.com)"}

# Rate limit: minimum seconds between requests to the same domain
MIN_REQUEST_INTERVAL = 10  # seconds
_last_request_time: dict[str, float] = {}


class NationalDiscussionScraper:
    """Service for scraping text-based discussions from WPC/SPC websites with rate limiting.

    This class provides methods to fetch and parse weather discussions from the
    Weather Prediction Center (WPC) and Storm Prediction Center (SPC) websites.
    It includes built-in rate limiting to avoid overloading the servers and
    caching to improve performance.
    """

    def __init__(self, request_delay: float = 1.0):
        """Initialize the scraper with rate limiting.

        Args:
            request_delay: Delay between requests in seconds
        """
        self.request_delay = request_delay  # Delay between requests in seconds
        self.last_request_time: Dict[str, float] = {}
        self.headers = HEADERS  # Use the same headers as the legacy functions

    def _rate_limit(self, domain: str) -> None:
        """Enforce rate limiting between requests to the same domain.

        Args:
            domain: The domain being requested
        """
        current_time = time.time()
        last = self.last_request_time.get(domain, 0)
        wait = self.request_delay - (current_time - last)

        if wait > 0:
            logger.info(
                f"Rate limiting: sleeping for {wait:.1f} seconds before next request to {domain}"
            )
            time.sleep(wait)

        self.last_request_time[domain] = time.time()

    def fetch_wpc_discussion(self) -> Dict[str, str]:
        """Fetch the Weather Prediction Center (WPC) discussion.

        Returns:
            Dictionary containing summary and full text of the discussion
        """
        domain = "wpc.ncep.noaa.gov"
        url = "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd"
        self._rate_limit(domain)

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            # Find the pre tag containing the discussion text
            discussion_element = soup.find("pre")

            if not discussion_element:
                logger.error("Could not find WPC discussion text")
                return {"summary": "WPC discussion unavailable", "full": ""}

            # Get text without strip=True to preserve internal whitespace and newlines
            full_text = discussion_element.get_text()
            if full_text:
                # Only strip leading/trailing whitespace from the whole block
                full_text = full_text.strip()

            # Extract a summary (first 150 chars of the stripped full text)
            summary = full_text[:150] + "..." if len(full_text) > 150 else full_text

            return {"summary": summary, "full": full_text}

        except Exception as e:
            logger.error(f"Error fetching WPC discussion: {str(e)}")
            return {"summary": f"Error: {str(e)}", "full": ""}

    def fetch_spc_discussion(self) -> Dict[str, str]:
        """Fetch the Storm Prediction Center (SPC) discussion.

        Returns:
            Dictionary containing summary and full text of the discussion
        """
        domain = "spc.noaa.gov"
        url = "https://www.spc.noaa.gov/products/outlook/day1otlk.html"
        self._rate_limit(domain)

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            # Find the pre tag containing the discussion text
            discussion_element = soup.find("pre")

            if not discussion_element:
                logger.error("Could not find SPC discussion text")
                return {"summary": "SPC discussion unavailable", "full": ""}

            full_text = discussion_element.get_text()

            # Try to extract the discussion section, which now follows "...SUMMARY..."
            if "...SUMMARY..." in full_text:
                # Take everything after the first occurrence of "...SUMMARY..."
                full_text = full_text.split("...SUMMARY...", 1)[1].strip()

            # Extract a summary (first 150 chars)
            summary = full_text[:150] + "..." if len(full_text) > 150 else full_text

            return {"summary": summary, "full": full_text}

        except Exception as e:
            logger.error(f"Error fetching SPC discussion: {str(e)}")
            return {"summary": f"Error: {str(e)}", "full": ""}

    def fetch_all_discussions(self) -> Dict[str, Dict[str, str]]:
        """Fetch all national discussions.

        Returns:
            Dictionary containing all discussions with structure:
            {
                "wpc": {
                    "summary": str,
                    "full": str
                },
                "spc": {
                    "summary": str,
                    "full": str
                }
            }
        """
        wpc_data = self.fetch_wpc_discussion()
        spc_data = self.fetch_spc_discussion()

        return {"wpc": wpc_data, "spc": spc_data}


# Create a singleton instance for use by other modules
# Note: This is currently unused but kept for potential future use
# and backward compatibility with legacy functions
_scraper = NationalDiscussionScraper(request_delay=MIN_REQUEST_INTERVAL)  # noqa: F841


# Legacy functions for backward compatibility


def _rate_limit(domain: str) -> None:
    """Legacy rate limiting function that uses the global _last_request_time dict.

    Args:
        domain: The domain being requested
    """
    now = time.time()
    last = _last_request_time.get(domain, 0)
    wait = MIN_REQUEST_INTERVAL - (now - last)
    if wait > 0:
        logger.info(
            f"Rate limiting: sleeping for {wait:.1f} seconds before next request to {domain}"
        )
        time.sleep(wait)
    _last_request_time[domain] = time.time()


def fetch_wpc_short_range():
    """
    Fetch the latest WPC Short Range Discussion (PMDSPD) from the WPC site.
    Returns:
        text (str): The discussion text, or a friendly error message.
    """
    url = "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd"
    _rate_limit("wpc.ncep.noaa.gov")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        pre = soup.find("pre")
        if pre:
            # Get text without strip=True to preserve internal whitespace and newlines
            text = pre.get_text()
            # Only strip leading/trailing whitespace from the whole block
            return text.strip() if text else "No discussion found. (WPC)"
        return "No discussion found. (WPC)"
    except Exception as e:
        logger.error(f"Error fetching WPC discussion: {e}")
        return "Error fetching WPC discussion."


def fetch_spc_day1():
    """
    Fetch the latest SPC Day 1 Outlook Discussion from the SPC site.
    Returns:
        text (str): The discussion text, or a friendly error message.
    """
    url = "https://www.spc.noaa.gov/products/outlook/day1otlk.html"
    _rate_limit("spc.noaa.gov")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # The discussion is usually in a <pre> tag after "...SUMMARY..."
        pre = soup.find("pre")
        if pre:
            # Try to extract the discussion section, which now follows "...SUMMARY..."
            text = pre.get_text()
            if "...SUMMARY..." in text:
                # Take everything after the first occurrence of "...SUMMARY..."
                text = text.split("...SUMMARY...", 1)[1].strip()
            return text.strip()
        return "No discussion found. (SPC)"
    except Exception as e:
        logger.error(f"Error fetching SPC discussion: {e}")
        return "Error fetching SPC discussion."


def get_national_discussion_summaries():
    """
    Fetch and summarize the latest WPC and SPC national discussions.
    Returns:
        dict: Contains both summaries and full text for national discussions:
            {
                "wpc": {
                    "short_range_summary": str,
                    "short_range_full": str
                },
                "spc": {
                    "day1_summary": str,
                    "day1_full": str
                },
                "attribution": str
            }
    """
    wpc = fetch_wpc_short_range()
    spc = fetch_spc_day1()

    def summarize(text: str, lines: int = 10) -> str:
        if not text:
            return "No discussion available."
        summary_lines = [line for line in text.splitlines() if line.strip()][:lines]
        return "\n".join(summary_lines)

    attribution = (
        "Data from NOAA/NWS/WPC and NOAA/NWS/SPC. "
        "See https://www.wpc.ncep.noaa.gov/ and https://www.spc.noaa.gov/ for full details."
    )
    return {
        "wpc": {"short_range_summary": summarize(wpc), "short_range_full": wpc},
        "spc": {"day1_summary": summarize(spc), "day1_full": spc},
        "attribution": attribution,
    }
