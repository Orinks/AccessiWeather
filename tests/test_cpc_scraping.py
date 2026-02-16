"""Tests for CPC outlook scraping in NationalDiscussionScraper."""

from unittest.mock import patch

import httpx
import pytest

from accessiweather.services.national_discussion_scraper import NationalDiscussionScraper

# Sample HTML resembling a CPC 6-10 Day outlook page
SAMPLE_CPC_6_10_HTML = """
<html>
<head><title>6-10 Day Outlook</title></head>
<body>
<pre>
6-10 DAY OUTLOOK FOR JAN 15 - 19, 2026

TEMPERATURE: ABOVE NORMAL TEMPS ARE EXPECTED ACROSS THE EASTERN US,
WHILE BELOW NORMAL TEMPS ARE LIKELY OVER THE WESTERN US AND ALASKA.

PRECIPITATION: ABOVE NORMAL PRECIP IS FAVORED ACROSS THE PACIFIC NORTHWEST
AND THE NORTHERN TIER OF THE COUNTRY. BELOW NORMAL PRECIP IS EXPECTED
ACROSS THE SOUTHERN US.
</pre>
</body>
</html>
"""

SAMPLE_CPC_8_14_HTML = """
<html>
<head><title>8-14 Day Outlook</title></head>
<body>
<pre>
8-14 DAY OUTLOOK FOR JAN 18 - 24, 2026

TEMPERATURE: THE EXTENDED RANGE OUTLOOK INDICATES ABOVE NORMAL TEMPS
ACROSS MUCH OF THE EASTERN TWO-THIRDS OF THE CONUS.

PRECIPITATION: ABOVE NORMAL PRECIP IS FAVORED ALONG THE WEST COAST
AND ACROSS THE NORTHERN PLAINS.
</pre>
</body>
</html>
"""

SAMPLE_CPC_NO_PRE_HTML = """
<html>
<body>
<div class="contentArea">
This is the CPC outlook content found in a div instead of a pre tag.
It contains enough text to be considered a valid outlook with more than one hundred characters of content for the extraction logic to work properly.
</div>
</body>
</html>
"""

SAMPLE_CPC_EMPTY_HTML = """
<html>
<body>
<p>Page under maintenance</p>
</body>
</html>
"""


@pytest.fixture
def scraper():
    """Create a scraper with fast settings for testing."""
    return NationalDiscussionScraper(request_delay=0, max_retries=0, retry_backoff=1.0, timeout=5)


class TestFetchCpcDiscussions:
    """Tests for fetch_cpc_discussions method."""

    def test_fetches_both_outlooks_successfully(self, scraper):
        """Both 6-10 and 8-14 day outlooks are fetched and returned."""
        responses = [
            httpx.Response(
                200, text=SAMPLE_CPC_6_10_HTML, request=httpx.Request("GET", "https://example.com")
            ),
            httpx.Response(
                200, text=SAMPLE_CPC_8_14_HTML, request=httpx.Request("GET", "https://example.com")
            ),
        ]
        call_count = 0

        def mock_get(self_client, url, **kwargs):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        with patch.object(httpx.Client, "get", mock_get):
            result = scraper.fetch_cpc_discussions()

        assert "outlook_6_10" in result
        assert "outlook_8_14" in result
        assert "6-10 DAY OUTLOOK" in result["outlook_6_10"]
        assert "8-14 DAY OUTLOOK" in result["outlook_8_14"]

    def test_returns_error_string_on_connection_failure(self, scraper):
        """Connection errors return descriptive error messages, not exceptions."""

        def mock_get(self_client, url, **kwargs):
            raise httpx.ConnectError("Connection refused")

        with patch.object(httpx.Client, "get", mock_get):
            result = scraper.fetch_cpc_discussions()

        assert "outlook_6_10" in result
        assert "outlook_8_14" in result
        assert "unavailable" in result["outlook_6_10"].lower()
        assert "unavailable" in result["outlook_8_14"].lower()

    def test_returns_error_string_on_http_error(self, scraper):
        """HTTP errors (e.g. 500) return descriptive error messages."""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(500, request=request)

        def mock_get(self_client, url, **kwargs):
            raise httpx.HTTPStatusError("Server Error", request=request, response=response)

        with patch.object(httpx.Client, "get", mock_get):
            result = scraper.fetch_cpc_discussions()

        assert "unavailable" in result["outlook_6_10"].lower()
        assert "unavailable" in result["outlook_8_14"].lower()

    def test_returns_error_string_on_timeout(self, scraper):
        """Timeout errors return descriptive error messages."""

        def mock_get(self_client, url, **kwargs):
            raise httpx.TimeoutException("Request timed out")

        with patch.object(httpx.Client, "get", mock_get):
            result = scraper.fetch_cpc_discussions()

        assert "unavailable" in result["outlook_6_10"].lower()
        assert "unavailable" in result["outlook_8_14"].lower()

    def test_partial_failure_returns_one_error_one_success(self, scraper):
        """If one outlook fails and one succeeds, both keys are present."""
        call_count = 0

        def mock_get(self_client, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("Connection refused")
            return httpx.Response(200, text=SAMPLE_CPC_8_14_HTML, request=httpx.Request("GET", url))

        with patch.object(httpx.Client, "get", mock_get):
            result = scraper.fetch_cpc_discussions()

        assert "unavailable" in result["outlook_6_10"].lower()
        assert "8-14 DAY OUTLOOK" in result["outlook_8_14"]

    def test_fallback_to_div_content(self, scraper):
        """When no <pre> tag exists, falls back to div extraction."""

        def mock_get(self_client, url, **kwargs):
            return httpx.Response(
                200, text=SAMPLE_CPC_NO_PRE_HTML, request=httpx.Request("GET", url)
            )

        with patch.object(httpx.Client, "get", mock_get):
            result = scraper.fetch_cpc_discussions()

        assert "CPC outlook content" in result["outlook_6_10"]

    def test_empty_page_returns_error(self, scraper):
        """A page with no extractable content returns an error message."""

        def mock_get(self_client, url, **kwargs):
            return httpx.Response(
                200, text=SAMPLE_CPC_EMPTY_HTML, request=httpx.Request("GET", url)
            )

        with patch.object(httpx.Client, "get", mock_get):
            result = scraper.fetch_cpc_discussions()

        assert "unavailable" in result["outlook_6_10"].lower()


class TestExtractCpcOutlookText:
    """Tests for _extract_cpc_outlook_text method."""

    def test_extracts_from_pre_tag(self, scraper):
        text = scraper._extract_cpc_outlook_text(SAMPLE_CPC_6_10_HTML, "6-10 Day")
        assert text is not None
        assert "6-10 DAY OUTLOOK" in text

    def test_extracts_from_content_div(self, scraper):
        text = scraper._extract_cpc_outlook_text(SAMPLE_CPC_NO_PRE_HTML, "6-10 Day")
        assert text is not None
        assert "CPC outlook content" in text

    def test_returns_none_for_empty_page(self, scraper):
        text = scraper._extract_cpc_outlook_text(SAMPLE_CPC_EMPTY_HTML, "6-10 Day")
        assert text is None

    def test_handles_malformed_html(self, scraper):
        text = scraper._extract_cpc_outlook_text("<html><body></body></html>", "6-10 Day")
        assert text is None
