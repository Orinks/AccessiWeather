"""Tests for NationalDiscussionService."""

import sys
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
    NWS_API_BASE,
    NationalDiscussionService,
)


@pytest.fixture
def service():
    """Create a service with no delays for testing."""
    return NationalDiscussionService(request_delay=0, max_retries=0, timeout=5)


def _mock_product_list(product_type, products):
    """Create a mock product list response."""
    return httpx.Response(
        200,
        json={"@graph": products},
        request=httpx.Request("GET", f"{NWS_API_BASE}/products/types/{product_type}"),
    )


def _mock_product_text(product_id, text):
    """Create a mock product text response."""
    return httpx.Response(
        200,
        json={"productText": text},
        request=httpx.Request("GET", f"{NWS_API_BASE}/products/{product_id}"),
    )


def _mock_error_response(url, status_code=500):
    """Create an error response."""
    return httpx.Response(
        status_code,
        json={"error": "Server error"},
        request=httpx.Request("GET", url),
    )


class TestNationalDiscussionServiceInit:
    """Tests for service initialization."""

    def test_default_init(self):
        svc = NationalDiscussionService()
        assert svc.request_delay == 1.0
        assert svc.max_retries == 3
        assert svc.timeout == 10
        assert "User-Agent" in svc.headers

    def test_custom_init(self):
        svc = NationalDiscussionService(
            request_delay=2.0, max_retries=5, retry_backoff=2.0, timeout=30
        )
        assert svc.request_delay == 2.0
        assert svc.max_retries == 5
        assert svc.retry_backoff == 2.0
        assert svc.timeout == 30


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limit_enforced(self):
        svc = NationalDiscussionService(request_delay=0.1, max_retries=0)
        svc._last_request_time = 0.0
        # Should not raise
        svc._rate_limit()
        assert svc._last_request_time > 0


class TestMakeRequest:
    """Tests for _make_request."""

    def test_successful_request(self, service):
        mock_response = httpx.Response(
            200,
            json={"key": "value"},
            request=httpx.Request("GET", "https://example.com"),
        )
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            result = service._make_request("https://example.com")
            assert result["success"] is True
            assert result["data"] == {"key": "value"}

    def test_timeout_error(self, service):
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            result = service._make_request("https://example.com")
            assert result["success"] is False
            assert "timed out" in result["error"]

    def test_connection_error(self, service):
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.ConnectError("connection failed")
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            result = service._make_request("https://example.com")
            assert result["success"] is False
            assert "Connection error" in result["error"]

    def test_http_status_error(self, service):
        mock_response = httpx.Response(
            500,
            request=httpx.Request("GET", "https://example.com"),
        )
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "Server Error", request=mock_response.request, response=mock_response
                )
            )
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            result = service._make_request("https://example.com")
            assert result["success"] is False
            assert "HTTP error" in result["error"]


class TestFetchWPCDiscussions:
    """Tests for fetch_wpc_discussions."""

    def test_successful_fetch(self, service):
        products = [
            {"id": "pmd-sr-001", "name": "Short Range Forecast Discussion", "issuingOffice": "WPC"},
            {
                "id": "pmd-mr-001",
                "name": "Medium Range Forecast Discussion",
                "issuingOffice": "WPC",
            },
            {"id": "pmd-ext-001", "name": "Days 8-10 Extended Forecast", "issuingOffice": "WPC"},
        ]

        def mock_make_request(url):
            if "/products/types/PMD" in url:
                return {"success": True, "data": {"@graph": products}}
            if "pmd-sr-001" in url:
                return {"success": True, "data": {"productText": "Short range discussion text"}}
            if "pmd-mr-001" in url:
                return {"success": True, "data": {"productText": "Medium range discussion text"}}
            if "pmd-ext-001" in url:
                return {"success": True, "data": {"productText": "Extended discussion text"}}
            return {"success": False, "error": "Not found"}

        with patch.object(service, "_make_request", side_effect=mock_make_request):
            result = service.fetch_wpc_discussions()

        assert "short_range" in result
        assert "medium_range" in result
        assert "extended" in result
        assert result["short_range"]["text"] == "Short range discussion text"
        assert result["medium_range"]["text"] == "Medium range discussion text"
        assert result["extended"]["text"] == "Extended discussion text"
        assert result["short_range"]["title"] == "Short Range Forecast (Days 1-3)"

    def test_api_error(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": False, "error": "Connection error"},
        ):
            result = service.fetch_wpc_discussions()

        for key in ["short_range", "medium_range", "extended"]:
            assert "Error" in result[key]["text"]

    def test_missing_discussions(self, service):
        """Test that missing discussions show 'not available'."""
        products = [
            {"id": "pmd-sr-001", "name": "Short Range Forecast Discussion", "issuingOffice": "WPC"},
        ]

        def mock_make_request(url):
            if "/products/types/PMD" in url:
                return {"success": True, "data": {"@graph": products}}
            if "pmd-sr-001" in url:
                return {"success": True, "data": {"productText": "Short range text"}}
            return {"success": False, "error": "Not found"}

        with patch.object(service, "_make_request", side_effect=mock_make_request):
            result = service.fetch_wpc_discussions()

        assert result["short_range"]["text"] == "Short range text"
        assert result["medium_range"]["text"] == "Discussion not available"
        assert result["extended"]["text"] == "Discussion not available"

    def test_product_id_from_at_id(self, service):
        """Test extracting product ID from @id URL."""
        products = [
            {
                "@id": "https://api.weather.gov/products/pmd-sr-from-url",
                "name": "Short Range Forecast Discussion",
                "issuingOffice": "WPC",
            },
        ]

        def mock_make_request(url):
            if "/products/types/PMD" in url:
                return {"success": True, "data": {"@graph": products}}
            if "pmd-sr-from-url" in url:
                return {"success": True, "data": {"productText": "From URL text"}}
            return {"success": False, "error": "Not found"}

        with patch.object(service, "_make_request", side_effect=mock_make_request):
            result = service.fetch_wpc_discussions()

        assert result["short_range"]["text"] == "From URL text"


class TestFetchSPCDiscussions:
    """Tests for fetch_spc_discussions."""

    def test_successful_fetch(self, service):
        products = [
            {"id": "swo-d1-001", "name": "Day 1 Convective Outlook", "issuingOffice": "SPC"},
            {"id": "swo-d2-001", "name": "Day 2 Convective Outlook", "issuingOffice": "SPC"},
            {"id": "swo-d3-001", "name": "Day 3 Convective Outlook", "issuingOffice": "SPC"},
        ]

        def mock_make_request(url):
            if "/products/types/SWO" in url:
                return {"success": True, "data": {"@graph": products}}
            if "swo-d1-001" in url:
                return {"success": True, "data": {"productText": "Day 1 outlook text"}}
            if "swo-d2-001" in url:
                return {"success": True, "data": {"productText": "Day 2 outlook text"}}
            if "swo-d3-001" in url:
                return {"success": True, "data": {"productText": "Day 3 outlook text"}}
            return {"success": False, "error": "Not found"}

        with patch.object(service, "_make_request", side_effect=mock_make_request):
            result = service.fetch_spc_discussions()

        assert result["day1"]["text"] == "Day 1 outlook text"
        assert result["day2"]["text"] == "Day 2 outlook text"
        assert result["day3"]["text"] == "Day 3 outlook text"
        assert result["day1"]["title"] == "Day 1 Convective Outlook"

    def test_api_error(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": False, "error": "Timeout"},
        ):
            result = service.fetch_spc_discussions()

        for key in ["day1", "day2", "day3"]:
            assert "Error" in result[key]["text"]

    def test_partial_results(self, service):
        products = [
            {"id": "swo-d1-001", "name": "Day 1 Convective Outlook", "issuingOffice": "SPC"},
        ]

        def mock_make_request(url):
            if "/products/types/SWO" in url:
                return {"success": True, "data": {"@graph": products}}
            if "swo-d1-001" in url:
                return {"success": True, "data": {"productText": "Day 1 text"}}
            return {"success": False, "error": "Not found"}

        with patch.object(service, "_make_request", side_effect=mock_make_request):
            result = service.fetch_spc_discussions()

        assert result["day1"]["text"] == "Day 1 text"
        assert result["day2"]["text"] == "Outlook not available"
        assert result["day3"]["text"] == "Outlook not available"


class TestFetchQPFDiscussion:
    """Tests for fetch_qpf_discussion."""

    def test_successful_fetch(self, service):
        products = [
            {"id": "qpf-001", "name": "QPF Discussion", "issuingOffice": "WPC"},
        ]

        def mock_make_request(url):
            if "/products/types/QPF" in url:
                return {"success": True, "data": {"@graph": products}}
            if "qpf-001" in url:
                return {"success": True, "data": {"productText": "QPF discussion text here"}}
            return {"success": False, "error": "Not found"}

        with patch.object(service, "_make_request", side_effect=mock_make_request):
            result = service.fetch_qpf_discussion()

        assert "qpf" in result
        assert result["qpf"]["text"] == "QPF discussion text here"
        assert result["qpf"]["title"] == "Quantitative Precipitation Forecast Discussion"

    def test_api_error(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": False, "error": "Server down"},
        ):
            result = service.fetch_qpf_discussion()

        assert "Error" in result["qpf"]["text"]

    def test_empty_product_list(self, service):
        def mock_make_request(url):
            if "/products/types/QPF" in url:
                return {"success": True, "data": {"@graph": []}}
            return {"success": False, "error": "Not found"}

        with patch.object(service, "_make_request", side_effect=mock_make_request):
            result = service.fetch_qpf_discussion()

        assert "Error" in result["qpf"]["text"] or "not available" in result["qpf"]["text"]

    def test_product_text_fetch_error(self, service):
        products = [
            {"id": "qpf-001", "name": "QPF Discussion", "issuingOffice": "WPC"},
        ]

        def mock_make_request(url):
            if "/products/types/QPF" in url:
                return {"success": True, "data": {"@graph": products}}
            return {"success": False, "error": "Product fetch failed"}

        with patch.object(service, "_make_request", side_effect=mock_make_request):
            result = service.fetch_qpf_discussion()

        assert "Error" in result["qpf"]["text"]


class TestClassifyMethods:
    """Tests for classification helper methods."""

    def test_classify_pmd_short_range(self, service):
        assert service._classify_pmd_discussion("Short Range Forecast") == "short_range"
        assert service._classify_pmd_discussion("Day 1 SPD Discussion") == "short_range"

    def test_classify_pmd_medium_range(self, service):
        assert service._classify_pmd_discussion("Medium Range Forecast 3-7 Day") == "medium_range"
        assert service._classify_pmd_discussion("EPD Discussion") == "medium_range"

    def test_classify_pmd_extended(self, service):
        assert service._classify_pmd_discussion("Days 8-10 Outlook") == "extended"
        assert service._classify_pmd_discussion("Day 8 Extended") == "extended"

    def test_classify_pmd_unknown(self, service):
        assert service._classify_pmd_discussion("Random Product") is None
        assert service._classify_pmd_discussion("") is None
        assert service._classify_pmd_discussion(None) is None

    def test_classify_swo_days(self, service):
        assert service._classify_swo_outlook("Day 1 Convective") == "day1"
        assert service._classify_swo_outlook("Day 2 Outlook") == "day2"
        assert service._classify_swo_outlook("Day 3 Severe") == "day3"

    def test_classify_swo_unknown(self, service):
        assert service._classify_swo_outlook("Random") is None
        assert service._classify_swo_outlook("") is None
        assert service._classify_swo_outlook(None) is None


class TestFetchProductText:
    """Tests for _fetch_product_text."""

    def test_empty_product_text(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": True, "data": {"productText": ""}},
        ):
            result = service._fetch_product_text("test-id")
            assert result["success"] is False
            assert "empty" in result["error"]

    def test_successful_product_text(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": True, "data": {"productText": "Some text"}},
        ):
            result = service._fetch_product_text("test-id")
            assert result["success"] is True
            assert result["text"] == "Some text"


class TestRetryLogic:
    """Tests for retry behavior."""

    def test_retries_on_failure(self):
        svc = NationalDiscussionService(request_delay=0, max_retries=2, timeout=1)
        call_count = 0

        def mock_make_request_counting(url):
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("timeout")

        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)

            result = svc._make_request("https://example.com")

        assert result["success"] is False
        # Should have been called max_retries + 1 times
        assert mock_client.get.call_count == 3
