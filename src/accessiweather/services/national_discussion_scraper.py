"""
National Discussion Scraper for AccessiWeather.

This module provides functionality to scrape and parse national weather discussions
from NOAA websites, including the Weather Prediction Center (WPC) and Storm Prediction
Center (SPC). It includes rate limiting to avoid overloading the servers, robust
error handling, and automatic retry mechanisms.
"""

import logging
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "AccessiWeather/1.0 (AccessiWeather)"}

# Rate limit: minimum seconds between requests to the same domain
MIN_REQUEST_INTERVAL = 10  # seconds
_last_request_time: dict[str, float] = {}


class NationalDiscussionScraper:
    """
    Service for scraping text-based discussions from WPC/SPC websites with rate limiting.

    This class provides methods to fetch and parse weather discussions from the
    Weather Prediction Center (WPC) and Storm Prediction Center (SPC) websites.
    It includes built-in rate limiting to avoid overloading the servers,
    automatic retry mechanisms, and robust error handling.
    """

    # Default URLs for discussions
    WPC_URL = "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd"
    SPC_URL = "https://www.spc.noaa.gov/products/outlook/day1otlk.html"

    # Alternative URLs in case primary ones fail
    WPC_ALT_URL = "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdepd"
    SPC_ALT_URL = "https://www.spc.noaa.gov/products/outlook/day1otlk_1300.html"

    def __init__(
        self,
        request_delay: float = 1.0,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
        timeout: int = 10,
    ):
        """
        Initialize the scraper with rate limiting and retry settings.

        Args:
        ----
            request_delay: Delay between requests in seconds
            max_retries: Maximum number of retry attempts for failed requests
            retry_backoff: Multiplier for increasing delay between retries
            timeout: Request timeout in seconds

        """
        self.request_delay = request_delay  # Delay between requests in seconds
        self.max_retries = max_retries  # Maximum number of retry attempts
        self.retry_backoff = retry_backoff  # Backoff multiplier for retries
        self.timeout = timeout  # Request timeout in seconds
        self.last_request_time: dict[str, float] = {}
        self.headers = HEADERS  # Use the same headers as the legacy functions

    def _rate_limit(self, domain: str) -> None:
        """
        Enforce rate limiting between requests to the same domain.

        Args:
        ----
            domain: The domain being requested

        """
        # For testing compatibility, we'll use the global _last_request_time
        # This allows the tests to mock time.time() correctly
        current_time = time.time()
        last = _last_request_time.get(domain, 0)
        wait = self.request_delay - (current_time - last)

        if wait > 0:
            logger.info(
                f"Rate limiting: sleeping for {wait:.1f} seconds before next request to {domain}"
            )
            time.sleep(wait)

        _last_request_time[domain] = time.time()

    def _make_request(self, url: str, domain: str, retry_count: int = 0) -> dict[str, Any]:
        """
        Make an HTTP request with retry logic and error handling.

        Args:
        ----
            url: URL to request
            domain: Domain for rate limiting
            retry_count: Current retry attempt number

        Returns:
        -------
            Dictionary with response text or error information

        """
        self._rate_limit(domain)

        try:
            logger.debug(
                f"Requesting URL: {url} (attempt {retry_count + 1}/{self.max_retries + 1})"
            )
            with httpx.Client() as client:
                response = client.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
            return {"success": True, "text": response.text, "status_code": response.status_code}
        except httpx.TimeoutException:
            logger.warning(f"Request timeout for {url}")
            return {"success": False, "error": "Request timed out", "error_type": "timeout"}
        except httpx.ConnectError:
            logger.warning(f"Connection error for {url}")
            return {"success": False, "error": "Connection error", "error_type": "connection"}
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error for {url}: {e}")
            return {
                "success": False,
                "error": f"HTTP error: {e}",
                "error_type": "http",
                "status_code": e.response.status_code if hasattr(e, "response") else None,
            }
        except httpx.RedirectError:
            logger.warning(f"Too many redirects for {url}")
            return {"success": False, "error": "Too many redirects", "error_type": "redirects"}
        except httpx.RequestError as e:
            logger.warning(f"Request exception for {url}: {e}")
            return {"success": False, "error": f"Request error: {e}", "error_type": "request"}

    def _extract_discussion_text(self, html_content: str, source: str) -> dict[str, Any]:
        """
        Extract discussion text from HTML content with robust parsing.

        Args:
        ----
            html_content: HTML content to parse
            source: Source identifier ('wpc' or 'spc')

        Returns:
        -------
            Dictionary with extracted text or error information

        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Try multiple selectors to find the discussion text
            discussion_element = None

            # First try the standard pre tag
            discussion_element = soup.find("pre")

            # If that fails, try other common containers
            if not discussion_element:
                # Try div with class containing 'discussion'
                discussion_element = soup.find(
                    "div", class_=lambda c: c and "discussion" in c.lower()
                )

            if not discussion_element:
                # Try div with id containing 'discussion'
                discussion_element = soup.find("div", id=lambda i: i and "discussion" in i.lower())

            if not discussion_element:
                # Try paragraphs with specific text patterns
                if source == "wpc":
                    # Look for paragraphs containing WPC-specific text
                    for p in soup.find_all("p"):
                        if p.text and any(
                            phrase in p.text
                            for phrase in [
                                "Short-Range Forecast Discussion",
                                "Weather Prediction Center",
                            ]
                        ):
                            discussion_element = p
                            break
                elif source == "spc":
                    # Look for paragraphs containing SPC-specific text
                    for p in soup.find_all("p"):
                        if p.text and any(
                            phrase in p.text
                            for phrase in ["Convective Outlook", "Storm Prediction Center"]
                        ):
                            discussion_element = p
                            break

            if not discussion_element:
                logger.error(f"Could not find {source.upper()} discussion text using any selector")
                return {"success": False, "error": f"{source.upper()} discussion unavailable"}

            # Get text without strip=True to preserve internal whitespace and newlines
            full_text = discussion_element.get_text()
            if not full_text:
                logger.error(f"Empty {source.upper()} discussion text")
                return {"success": False, "error": f"Empty {source.upper()} discussion"}

            # Only strip leading/trailing whitespace from the whole block
            full_text = full_text.strip()

            # For SPC, extract the discussion section after "...SUMMARY..."
            if source == "spc" and "...SUMMARY..." in full_text:
                try:
                    full_text = full_text.split("...SUMMARY...", 1)[1].strip()
                except Exception as e:
                    logger.warning(f"Error extracting SPC summary section: {e}")
                    # Continue with the full text if extraction fails

            return {"success": True, "full_text": full_text}

        except Exception as e:
            logger.error(f"Error parsing {source.upper()} discussion HTML: {str(e)}")
            return {
                "success": False,
                "error": f"Error parsing {source.upper()} discussion: {str(e)}",
            }

    def fetch_wpc_discussion(self) -> dict[str, str]:
        """
        Fetch the Weather Prediction Center (WPC) discussion with retry logic.

        Returns
        -------
            Dictionary containing summary and full text of the discussion

        """
        domain = "wpc.ncep.noaa.gov"
        urls = [self.WPC_URL, self.WPC_ALT_URL]  # Try primary URL first, then fallback

        for retry in range(self.max_retries + 1):
            # For first attempt, use primary URL; for subsequent retries, alternate between URLs
            url_index = 0 if retry == 0 else retry % len(urls)
            url = urls[url_index]

            # Calculate backoff delay (0 for first attempt)
            backoff_delay = (
                0 if retry == 0 else self.request_delay * (self.retry_backoff ** (retry - 1))
            )

            if retry > 0:
                logger.info(
                    f"Retrying WPC discussion fetch (attempt {retry + 1}/{self.max_retries + 1})"
                )
                if backoff_delay > 0:
                    logger.info(f"Backing off for {backoff_delay:.1f} seconds")
                    time.sleep(backoff_delay)

            # Make the request
            response = self._make_request(url, domain, retry)

            if response.get("success"):
                # Parse the HTML content
                parse_result = self._extract_discussion_text(response["text"], "wpc")

                if parse_result.get("success"):
                    full_text = parse_result["full_text"]
                    # Extract a summary (first 150 chars of the stripped full text)
                    summary = full_text[:150] + "..." if len(full_text) > 150 else full_text
                    logger.info(f"Successfully fetched WPC discussion from {url}")
                    return {"summary": summary, "full": full_text}

            # If we get here, the request or parsing failed
            error_msg = response.get("error", "Unknown error")
            logger.warning(f"WPC discussion fetch attempt {retry + 1} failed: {error_msg}")

        # If we've exhausted all retries, return an error
        logger.error(f"Failed to fetch WPC discussion after {self.max_retries + 1} attempts")
        return {"summary": "No discussion found. (WPC)", "full": ""}

    def fetch_spc_discussion(self) -> dict[str, str]:
        """
        Fetch the Storm Prediction Center (SPC) discussion with retry logic.

        Returns
        -------
            Dictionary containing summary and full text of the discussion

        """
        domain = "spc.noaa.gov"
        urls = [self.SPC_URL, self.SPC_ALT_URL]  # Try primary URL first, then fallback

        for retry in range(self.max_retries + 1):
            # For first attempt, use primary URL; for subsequent retries, alternate between URLs
            url_index = 0 if retry == 0 else retry % len(urls)
            url = urls[url_index]

            # Calculate backoff delay (0 for first attempt)
            backoff_delay = (
                0 if retry == 0 else self.request_delay * (self.retry_backoff ** (retry - 1))
            )

            if retry > 0:
                logger.info(
                    f"Retrying SPC discussion fetch (attempt {retry + 1}/{self.max_retries + 1})"
                )
                if backoff_delay > 0:
                    logger.info(f"Backing off for {backoff_delay:.1f} seconds")
                    time.sleep(backoff_delay)

            # Make the request
            response = self._make_request(url, domain, retry)

            if response.get("success"):
                # Parse the HTML content
                parse_result = self._extract_discussion_text(response["text"], "spc")

                if parse_result.get("success"):
                    full_text = parse_result["full_text"]
                    # Extract a summary (first 150 chars of the stripped full text)
                    summary = full_text[:150] + "..." if len(full_text) > 150 else full_text
                    logger.info(f"Successfully fetched SPC discussion from {url}")
                    return {"summary": summary, "full": full_text}

            # If we get here, the request or parsing failed
            error_msg = response.get("error", "Unknown error")
            logger.warning(f"SPC discussion fetch attempt {retry + 1} failed: {error_msg}")

        # If we've exhausted all retries, return an error
        logger.error(f"Failed to fetch SPC discussion after {self.max_retries + 1} attempts")
        return {"summary": "No discussion found. (SPC)", "full": ""}

    # CPC URLs for extended outlooks
    CPC_6_10_URL = "https://www.cpc.ncep.noaa.gov/products/predictions/610day/"
    CPC_8_14_URL = "https://www.cpc.ncep.noaa.gov/products/predictions/814day/"

    def fetch_cpc_discussions(self) -> dict[str, str]:
        """
        Fetch CPC 6-10 Day and 8-14 Day extended outlooks via scraping.

        CPC does not provide a public API, so we scrape the outlook pages.

        Returns
        -------
            Dictionary with keys 'outlook_6_10' and 'outlook_8_14',
            each containing the outlook text or an error message string.

        """
        domain = "cpc.ncep.noaa.gov"
        result: dict[str, str] = {}

        for key, url, label in [
            ("outlook_6_10", self.CPC_6_10_URL, "6-10 Day"),
            ("outlook_8_14", self.CPC_8_14_URL, "8-14 Day"),
        ]:
            text = self._fetch_cpc_outlook(url, domain, label)
            result[key] = text

        return result

    def _fetch_cpc_outlook(self, url: str, domain: str, label: str) -> str:
        """
        Fetch and parse a single CPC outlook page.

        Args:
        ----
            url: URL of the CPC outlook page
            domain: Domain for rate limiting
            label: Human-readable label for logging (e.g. '6-10 Day')

        Returns:
        -------
            The outlook text, or a descriptive error message string.

        """
        for retry in range(self.max_retries + 1):
            backoff_delay = (
                0 if retry == 0 else self.request_delay * (self.retry_backoff ** (retry - 1))
            )
            if retry > 0:
                logger.info(
                    f"Retrying CPC {label} outlook fetch "
                    f"(attempt {retry + 1}/{self.max_retries + 1})"
                )
                if backoff_delay > 0:
                    time.sleep(backoff_delay)

            response = self._make_request(url, domain, retry)

            if response.get("success"):
                text = self._extract_cpc_outlook_text(response["text"], label)
                if text:
                    logger.info(f"Successfully fetched CPC {label} outlook")
                    return text

            error_msg = response.get("error", "Unknown error")
            logger.warning(f"CPC {label} outlook fetch attempt {retry + 1} failed: {error_msg}")

        logger.error(f"Failed to fetch CPC {label} outlook after {self.max_retries + 1} attempts")
        return f"CPC {label} Outlook is currently unavailable."

    def _extract_cpc_outlook_text(self, html_content: str, label: str) -> str | None:
        """
        Extract outlook text from a CPC outlook HTML page.

        CPC outlook pages typically contain the discussion text in a <pre> tag
        or within the main content area.

        Args:
        ----
            html_content: Raw HTML content
            label: Human-readable label for logging

        Returns:
        -------
            Extracted text, or None if extraction failed.

        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # CPC outlook pages typically have the discussion in a <pre> tag
            pre = soup.find("pre")
            if pre:
                text = pre.get_text().strip()
                if text:
                    return text

            # Fallback: look for div with class 'contentArea' or similar
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

            # Last resort: try to find any substantial text block
            body = soup.find("body")
            if body:
                # Look for the longest text block
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

    def fetch_all_discussions(self) -> dict[str, dict[str, str]]:
        """
        Fetch all national discussions with parallel processing.

        Returns
        -------
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
        # Fetch both discussions
        wpc_data = self.fetch_wpc_discussion()
        spc_data = self.fetch_spc_discussion()

        # Log the results
        if wpc_data.get("full"):
            logger.info("Successfully fetched WPC discussion")
        else:
            logger.warning("Failed to fetch WPC discussion")

        if spc_data.get("full"):
            logger.info("Successfully fetched SPC discussion")
        else:
            logger.warning("Failed to fetch SPC discussion")

        # Return the combined data
        return {"wpc": wpc_data, "spc": spc_data}


# Create a singleton instance for use by other modules
# This is used by the legacy functions for backward compatibility
_scraper = NationalDiscussionScraper(
    request_delay=MIN_REQUEST_INTERVAL, max_retries=2, retry_backoff=1.5, timeout=10
)


# Legacy functions for backward compatibility


def _rate_limit(domain: str) -> None:
    """
    Legacy rate limiting function that uses the global _last_request_time dict.

    Args:
    ----
        domain: The domain being requested

    """
    # This function is only used for testing


def fetch_wpc_short_range():
    """
    Fetch the latest WPC Short Range Discussion (PMDSPD) from the WPC site.

    This function uses the improved NationalDiscussionScraper class internally
    for better reliability and error handling.

    Returns
    -------
        text (str): The discussion text, or a friendly error message.

    """
    try:
        # Use the singleton scraper instance
        result = _scraper.fetch_wpc_discussion()

        # Return the full text if available, otherwise return the error message
        if result.get("full"):
            return result["full"]
        return "No discussion found. (WPC)"
    except httpx.RequestError as e:
        # For test compatibility with the request error test
        logger.error(f"Request exception in fetch_wpc_short_range: {e}")
        return "Error fetching WPC discussion."


def fetch_spc_day1():
    """
    Fetch the latest SPC Day 1 Outlook Discussion from the SPC site.

    This function uses the improved NationalDiscussionScraper class internally
    for better reliability and error handling.

    Returns
    -------
        text (str): The discussion text, or a friendly error message.

    """
    try:
        # Use the singleton scraper instance
        result = _scraper.fetch_spc_discussion()

        # Return the full text if available, otherwise return the error message
        if result.get("full"):
            return result["full"]
        return "No discussion found. (SPC)"
    except httpx.RequestError as e:
        # For test compatibility with the request error test
        logger.error(f"Request exception in fetch_spc_day1: {e}")
        return "Error fetching SPC discussion."


def get_national_discussion_summaries():
    """
    Fetch and summarize the latest WPC and SPC national discussions.

    This function uses the improved NationalDiscussionScraper class internally
    for better reliability and error handling.

    Returns
    -------
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
    # Get the WPC and SPC discussions using the legacy functions
    # This allows the tests to mock these functions
    wpc_full = fetch_wpc_short_range()
    spc_full = fetch_spc_day1()

    def summarize(text: str, lines: int = 10) -> str:
        """Create a summary from the first few lines of text."""
        if not text:
            return "No discussion available."
        if text.startswith("Error fetching"):
            return text
        summary_lines = [line for line in text.splitlines() if line.strip()][:lines]
        return "\n".join(summary_lines)

    # Create the attribution text
    attribution = (
        "Data from NOAA/NWS/WPC and NOAA/NWS/SPC. "
        "See https://www.wpc.ncep.noaa.gov/ and https://www.spc.noaa.gov/ for full details."
    )

    # Return the formatted data
    return {
        "wpc": {"short_range_summary": summarize(wpc_full), "short_range_full": wpc_full},
        "spc": {"day1_summary": summarize(spc_full), "day1_full": spc_full},
        "attribution": attribution,
    }
