import logging
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "AccessiWeatherBot/1.0 (contact: youremail@example.com)"}

# Rate limit: minimum seconds between requests to the same domain
MIN_REQUEST_INTERVAL = 10  # seconds
_last_request_time: dict[str, float] = {}


def _rate_limit(domain: str) -> None:
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
            return pre.get_text(strip=True)
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
        # The discussion is usually in a <pre> tag after "...DISCUSSION..."
        pre = soup.find("pre")
        if pre:
            # Try to extract only the discussion section if possible
            text = pre.get_text()
            if "...DISCUSSION..." in text:
                text = text.split("...DISCUSSION...")[1].strip()
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
