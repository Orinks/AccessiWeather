"""Tests for NHC tropical outlook scraping in NationalDiscussionService."""

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Mock wx modules before any accessiweather imports
if "wx" not in sys.modules:
    _wx_mock = MagicMock()
    sys.modules["wx"] = _wx_mock
    sys.modules["wx.core"] = _wx_mock
    sys.modules["wx.adv"] = _wx_mock
    sys.modules["wx.lib"] = _wx_mock
    sys.modules["wx.lib.newevent"] = _wx_mock

import httpx
import pytest

from accessiweather.services.national_discussion_service import (
    NationalDiscussionService,
)


@pytest.fixture
def service():
    """Create a service with no delays for testing."""
    return NationalDiscussionService(request_delay=0, max_retries=0, timeout=5)


# Sample HTML responses
SAMPLE_NHC_HTML_PRE = """
<html><body>
<h1>Tropical Weather Outlook</h1>
<pre>
ZCZC MIATWOAT ALL
TTAA00 KNHC 111200

Tropical Weather Outlook
NWS National Hurricane Center Miami FL
800 AM EDT Wed Feb 11 2026

For the North Atlantic...Caribbean Sea and the Gulf of Mexico:

No tropical cyclone formation is expected during the next 7 days.

$$
Forecaster Smith
</pre>
</body></html>
"""

SAMPLE_NHC_HTML_DIV = """
<html><body>
<div id="outlook-text">
Atlantic Tropical Weather Outlook text here.
</div>
</body></html>
"""

SAMPLE_NHC_HTML_NO_CONTENT = """
<html><body>
<h1>Page with no outlook</h1>
<p>Nothing here</p>
</body></html>
"""


class TestFetchNhcDiscussions:
    """Test fetch_nhc_discussions method."""

    def test_successful_fetch_both_outlooks(self, service):
        """Test successful scraping of both Atlantic and East Pacific outlooks."""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_NHC_HTML_PRE
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(return_value=mock_response)

            result = service.fetch_nhc_discussions()

        assert "atlantic_outlook" in result
        assert "east_pacific_outlook" in result
        assert "Tropical Weather Outlook" in result["atlantic_outlook"]["text"]
        assert result["atlantic_outlook"]["title"] == "Atlantic Tropical Weather Outlook"
        assert result["east_pacific_outlook"]["title"] == "East Pacific Tropical Weather Outlook"

    def test_atlantic_fetch_error(self, service):
        """Test error handling when Atlantic outlook fetch fails."""
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(side_effect=httpx.ConnectError("Connection refused"))

            result = service.fetch_nhc_discussions()

        assert "Error fetching Atlantic outlook" in result["atlantic_outlook"]["text"]
        assert "Error fetching East Pacific outlook" in result["east_pacific_outlook"]["text"]

    def test_timeout_error(self, service):
        """Test timeout error handling."""
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(side_effect=httpx.TimeoutException("timeout"))

            result = service.fetch_nhc_discussions()

        assert "Error fetching Atlantic outlook" in result["atlantic_outlook"]["text"]
        assert "timed out" in result["atlantic_outlook"]["text"]

    def test_result_structure(self, service):
        """Test that result has correct keys and structure."""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_NHC_HTML_PRE
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(return_value=mock_response)

            result = service.fetch_nhc_discussions()

        for key in ("atlantic_outlook", "east_pacific_outlook"):
            assert "title" in result[key]
            assert "text" in result[key]
            assert isinstance(result[key]["title"], str)
            assert isinstance(result[key]["text"], str)


class TestExtractNhcOutlookText:
    """Test _extract_nhc_outlook_text static method."""

    def test_extract_from_pre_tag(self):
        """Test extraction from <pre> tag."""
        text = NationalDiscussionService._extract_nhc_outlook_text(SAMPLE_NHC_HTML_PRE)
        assert "Tropical Weather Outlook" in text
        assert "Forecaster Smith" in text

    def test_extract_from_div_with_outlook_id(self):
        """Test extraction from div with outlook-related id."""
        text = NationalDiscussionService._extract_nhc_outlook_text(SAMPLE_NHC_HTML_DIV)
        assert "Atlantic Tropical Weather Outlook" in text

    def test_no_content_found(self):
        """Test fallback message when no outlook content found."""
        text = NationalDiscussionService._extract_nhc_outlook_text(SAMPLE_NHC_HTML_NO_CONTENT)
        assert "Unable to parse" in text

    def test_empty_html(self):
        """Test handling of empty HTML."""
        text = NationalDiscussionService._extract_nhc_outlook_text("")
        assert "Unable to parse" in text

    def test_malformed_html(self):
        """Test handling of malformed HTML."""
        text = NationalDiscussionService._extract_nhc_outlook_text("<html><pre>Some text</pre>")
        assert text == "Some text"


class TestIsHurricaneSeason:
    """Test is_hurricane_season static method."""

    @pytest.mark.parametrize("month", [6, 7, 8, 9, 10, 11])
    def test_hurricane_season_months(self, month):
        """Test that June-November returns True."""
        with patch("accessiweather.services.national_discussion_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, month, 15, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert NationalDiscussionService.is_hurricane_season() is True

    @pytest.mark.parametrize("month", [1, 2, 3, 4, 5, 12])
    def test_non_hurricane_season_months(self, month):
        """Test that Jan-May and December returns False."""
        with patch("accessiweather.services.national_discussion_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, month, 15, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert NationalDiscussionService.is_hurricane_season() is False


class TestMakeHtmlRequest:
    """Test _make_html_request method."""

    def test_successful_request(self, service):
        """Test successful HTML request."""
        mock_response = MagicMock()
        mock_response.text = "<html>content</html>"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(return_value=mock_response)

            result = service._make_html_request("https://example.com")

        assert result["success"] is True
        assert result["html"] == "<html>content</html>"

    def test_connection_error(self, service):
        """Test connection error handling."""
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(side_effect=httpx.ConnectError("refused"))

            result = service._make_html_request("https://example.com")

        assert result["success"] is False
        assert "Connection error" in result["error"]

    def test_http_status_error(self, service):
        """Test HTTP status error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(side_effect=error)

            result = service._make_html_request("https://example.com")

        assert result["success"] is False
        assert "HTTP error" in result["error"]

    def test_retry_on_failure(self):
        """Test retry logic on failure."""
        svc = NationalDiscussionService(request_delay=0, max_retries=2, timeout=5)

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get = MagicMock(side_effect=httpx.TimeoutException("timeout"))

            result = svc._make_html_request("https://example.com")

        assert result["success"] is False
        assert mock_client.get.call_count == 3  # 1 initial + 2 retries
