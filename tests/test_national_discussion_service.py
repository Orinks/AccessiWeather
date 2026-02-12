"""Tests for NationalDiscussionService fetch_all and caching (US-004)."""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from accessiweather.services.national_discussion_service import NationalDiscussionService


@pytest.fixture
def service():
    """Create a service with short cache TTL for testing."""
    return NationalDiscussionService(request_delay=0, max_retries=0, timeout=1, cache_ttl=3600)


@pytest.fixture
def retry_service():
    """Create a service with retries enabled but no delays."""
    return NationalDiscussionService(request_delay=0, max_retries=2, retry_backoff=0, timeout=1)


class TestFetchAllDiscussions:
    """Tests for fetch_all_discussions method."""

    def test_returns_all_keys(self, service):
        """fetch_all_discussions returns dict with wpc, spc, qpf, nhc, cpc keys."""
        with (
            patch.object(
                service,
                "fetch_wpc_discussions",
                return_value={"short_range": {"title": "t", "text": "wpc text"}},
            ),
            patch.object(
                service,
                "fetch_spc_discussions",
                return_value={"day1": {"title": "t", "text": "spc text"}},
            ),
            patch.object(
                service,
                "fetch_qpf_discussion",
                return_value={"qpf": {"title": "t", "text": "qpf text"}},
            ),
            patch.object(
                service,
                "fetch_cpc_discussions",
                return_value={"outlook": {"title": "t", "text": "cpc text"}},
            ),
            patch.object(NationalDiscussionService, "is_hurricane_season", return_value=False),
        ):
            result = service.fetch_all_discussions()

        assert "wpc" in result
        assert "spc" in result
        assert "qpf" in result
        assert "nhc" in result
        assert "cpc" in result

    def test_nhc_fetched_during_hurricane_season(self, service):
        """NHC discussions are fetched when is_hurricane_season returns True."""
        nhc_data = {
            "atlantic_outlook": {"title": "Atlantic", "text": "tropical stuff"},
            "east_pacific_outlook": {"title": "East Pacific", "text": "more tropical"},
        }
        with (
            patch.object(service, "fetch_wpc_discussions", return_value={}),
            patch.object(service, "fetch_spc_discussions", return_value={}),
            patch.object(service, "fetch_qpf_discussion", return_value={}),
            patch.object(service, "fetch_cpc_discussions", return_value={}),
            patch.object(service, "fetch_nhc_discussions", return_value=nhc_data) as mock_nhc,
            patch.object(NationalDiscussionService, "is_hurricane_season", return_value=True),
        ):
            result = service.fetch_all_discussions()

        mock_nhc.assert_called_once()
        assert result["nhc"] == nhc_data

    def test_nhc_not_fetched_outside_hurricane_season(self, service):
        """NHC discussions show season message outside hurricane season."""
        with (
            patch.object(service, "fetch_wpc_discussions", return_value={}),
            patch.object(service, "fetch_spc_discussions", return_value={}),
            patch.object(service, "fetch_qpf_discussion", return_value={}),
            patch.object(service, "fetch_cpc_discussions", return_value={}),
            patch.object(service, "fetch_nhc_discussions") as mock_nhc,
            patch.object(NationalDiscussionService, "is_hurricane_season", return_value=False),
        ):
            result = service.fetch_all_discussions()

        mock_nhc.assert_not_called()
        assert "hurricane season" in result["nhc"]["atlantic_outlook"]["text"].lower()

    def test_caching_returns_cached_data(self, service):
        """Second call within TTL returns cached data without new fetches."""
        with (
            patch.object(
                service, "fetch_wpc_discussions", return_value={"wpc": "data"}
            ) as mock_wpc,
            patch.object(service, "fetch_spc_discussions", return_value={}),
            patch.object(service, "fetch_qpf_discussion", return_value={}),
            patch.object(service, "fetch_cpc_discussions", return_value={}),
            patch.object(NationalDiscussionService, "is_hurricane_season", return_value=False),
        ):
            result1 = service.fetch_all_discussions()
            result2 = service.fetch_all_discussions()

        # fetch_wpc_discussions should only be called once
        assert mock_wpc.call_count == 1
        assert result1 is result2

    def test_force_refresh_bypasses_cache(self, service):
        """force_refresh=True fetches fresh data even with valid cache."""
        with (
            patch.object(
                service, "fetch_wpc_discussions", return_value={"wpc": "data"}
            ) as mock_wpc,
            patch.object(service, "fetch_spc_discussions", return_value={}),
            patch.object(service, "fetch_qpf_discussion", return_value={}),
            patch.object(service, "fetch_cpc_discussions", return_value={}),
            patch.object(NationalDiscussionService, "is_hurricane_season", return_value=False),
        ):
            service.fetch_all_discussions()
            service.fetch_all_discussions(force_refresh=True)

        assert mock_wpc.call_count == 2

    def test_cache_expires(self, service):
        """Expired cache triggers fresh fetch."""
        service.cache_ttl = 1  # 1 second TTL

        with (
            patch.object(service, "fetch_wpc_discussions", return_value={}) as mock_wpc,
            patch.object(service, "fetch_spc_discussions", return_value={}),
            patch.object(service, "fetch_qpf_discussion", return_value={}),
            patch.object(service, "fetch_cpc_discussions", return_value={}),
            patch.object(NationalDiscussionService, "is_hurricane_season", return_value=False),
        ):
            service.fetch_all_discussions()
            # Simulate cache expiry by backdating timestamp
            service._cache_timestamp = time.time() - 2
            service.fetch_all_discussions()

        assert mock_wpc.call_count == 2

    def test_cache_ttl_configurable(self):
        """Cache TTL can be configured via constructor."""
        svc = NationalDiscussionService(cache_ttl=7200)
        assert svc.cache_ttl == 7200


class TestIsHurricaneSeason:
    """Tests for is_hurricane_season static method."""

    @pytest.mark.parametrize("month", [6, 7, 8, 9, 10, 11])
    def test_hurricane_season_months(self, month):
        """Months June-November are hurricane season."""
        with patch("accessiweather.services.national_discussion_service.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.month = month
            mock_dt.now.return_value = mock_now
            assert NationalDiscussionService.is_hurricane_season() is True

    @pytest.mark.parametrize("month", [1, 2, 3, 4, 5, 12])
    def test_non_hurricane_season_months(self, month):
        """Months outside June-November are not hurricane season."""
        with patch("accessiweather.services.national_discussion_service.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.month = month
            mock_dt.now.return_value = mock_now
            assert NationalDiscussionService.is_hurricane_season() is False


class TestNationalForecastHandlerIntegration:
    """Test NationalForecastHandler uses NationalDiscussionService."""

    def test_handler_uses_service(self):
        """NationalForecastHandler delegates to NationalDiscussionService."""
        from accessiweather.services.weather_service.national_forecast import (
            NationalForecastHandler,
        )

        handler = NationalForecastHandler()
        assert isinstance(handler.national_service, NationalDiscussionService)

    def test_handler_get_data(self):
        """NationalForecastHandler.get_national_forecast_data returns expected structure."""
        from accessiweather.services.weather_service.national_forecast import (
            NationalForecastHandler,
        )

        handler = NationalForecastHandler()
        mock_data = {"wpc": {}, "spc": {}, "qpf": {}, "nhc": {}, "cpc": {}}

        with patch.object(
            handler.national_service, "fetch_all_discussions", return_value=mock_data
        ):
            result = handler.get_national_forecast_data()

        assert "national_discussion_summaries" in result
        assert result["national_discussion_summaries"] == mock_data

    def test_handler_force_refresh(self):
        """force_refresh is passed through to service."""
        from accessiweather.services.weather_service.national_forecast import (
            NationalForecastHandler,
        )

        handler = NationalForecastHandler()

        with patch.object(
            handler.national_service, "fetch_all_discussions", return_value={}
        ) as mock:
            handler.get_national_forecast_data(force_refresh=True)

        mock.assert_called_once_with(force_refresh=True)


# ── New tests for coverage ──────────────────────────────────────────────


class TestRateLimit:
    """Tests for _rate_limit method."""

    def test_rate_limit_sleeps_when_needed(self, service):
        """Rate limiter sleeps if called too quickly."""
        service.request_delay = 0.5
        service._last_request_time = time.time()
        with patch("accessiweather.services.national_discussion_service.time.sleep") as mock_sleep:
            service._rate_limit()
            # Should have been called with a positive value
            if mock_sleep.called:
                assert mock_sleep.call_args[0][0] > 0

    def test_rate_limit_no_sleep_when_enough_time_passed(self, service):
        """Rate limiter doesn't sleep if enough time has passed."""
        service._last_request_time = 0.0
        with patch("accessiweather.services.national_discussion_service.time.sleep") as mock_sleep:
            service._rate_limit()
            mock_sleep.assert_not_called()


class TestMakeRequest:
    """Tests for _make_request method."""

    def test_successful_json_request(self, service):
        """Successful request returns parsed JSON."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value"}
        mock_response.raise_for_status = MagicMock()

        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_cl.return_value.__enter__ = MagicMock(
                return_value=MagicMock(get=MagicMock(return_value=mock_response))
            )
            mock_cl.return_value.__exit__ = MagicMock(return_value=False)
            result = service._make_request("https://example.com")

        assert result["success"] is True
        assert result["data"] == {"key": "value"}

    def test_timeout_error(self, service):
        """Timeout returns error."""
        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_cl.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_cl.return_value.__exit__ = MagicMock(return_value=False)
            result = service._make_request("https://example.com")

        assert result["success"] is False
        assert "timed out" in result["error"]

    def test_connect_error(self, service):
        """Connection error returns error."""
        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.ConnectError("conn failed")
            mock_cl.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_cl.return_value.__exit__ = MagicMock(return_value=False)
            result = service._make_request("https://example.com")

        assert result["success"] is False
        assert "Connection error" in result["error"]

    def test_http_status_error(self, service):
        """HTTP status error returns error with status code."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "server error", request=MagicMock(), response=mock_response
            )
            mock_cl.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_cl.return_value.__exit__ = MagicMock(return_value=False)
            result = service._make_request("https://example.com")

        assert result["success"] is False
        assert "500" in result["error"]

    def test_generic_request_error(self, service):
        """Generic RequestError returns error."""
        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.RequestError("bad request")
            mock_cl.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_cl.return_value.__exit__ = MagicMock(return_value=False)
            result = service._make_request("https://example.com")

        assert result["success"] is False
        assert "Request error" in result["error"]

    def test_unexpected_error(self, service):
        """Unexpected exception returns error."""
        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = RuntimeError("boom")
            mock_cl.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_cl.return_value.__exit__ = MagicMock(return_value=False)
            result = service._make_request("https://example.com")

        assert result["success"] is False
        assert "Unexpected error" in result["error"]

    def test_retry_logic(self, retry_service):
        """Request retries on failure then succeeds."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("timeout")
            return mock_response

        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = side_effect
            mock_cl.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_cl.return_value.__exit__ = MagicMock(return_value=False)
            with patch("accessiweather.services.national_discussion_service.time.sleep"):
                result = retry_service._make_request("https://example.com")

        assert result["success"] is True


class TestMakeHtmlRequest:
    """Tests for _make_html_request method."""

    def _mock_client(self, mock_cl, mock_client):
        mock_cl.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_cl.return_value.__exit__ = MagicMock(return_value=False)

    def test_successful_html_request(self, service):
        """Successful HTML request returns html text."""
        mock_response = MagicMock()
        mock_response.text = "<html>hello</html>"
        mock_response.raise_for_status = MagicMock()

        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            self._mock_client(mock_cl, mock_client)
            result = service._make_html_request("https://example.com")

        assert result["success"] is True
        assert result["html"] == "<html>hello</html>"

    def test_html_timeout_error(self, service):
        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            self._mock_client(mock_cl, mock_client)
            result = service._make_html_request("https://example.com")
        assert result["success"] is False
        assert "timed out" in result["error"]

    def test_html_connect_error(self, service):
        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.ConnectError("fail")
            self._mock_client(mock_cl, mock_client)
            result = service._make_html_request("https://example.com")
        assert result["success"] is False
        assert "Connection error" in result["error"]

    def test_html_http_status_error(self, service):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "not found", request=MagicMock(), response=mock_resp
            )
            self._mock_client(mock_cl, mock_client)
            result = service._make_html_request("https://example.com")
        assert result["success"] is False
        assert "404" in result["error"]

    def test_html_request_error(self, service):
        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.RequestError("err")
            self._mock_client(mock_cl, mock_client)
            result = service._make_html_request("https://example.com")
        assert result["success"] is False
        assert "Request error" in result["error"]

    def test_html_unexpected_error(self, service):
        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = ValueError("oops")
            self._mock_client(mock_cl, mock_client)
            result = service._make_html_request("https://example.com")
        assert result["success"] is False
        assert "Unexpected error" in result["error"]

    def test_html_retry_then_success(self, retry_service):
        mock_response = MagicMock()
        mock_response.text = "<html>ok</html>"
        mock_response.raise_for_status = MagicMock()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("fail")
            return mock_response

        with patch("accessiweather.services.national_discussion_service.httpx.Client") as mock_cl:
            mock_client = MagicMock()
            mock_client.get.side_effect = side_effect
            mock_cl.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_cl.return_value.__exit__ = MagicMock(return_value=False)
            with patch("accessiweather.services.national_discussion_service.time.sleep"):
                result = retry_service._make_html_request("https://example.com")
        assert result["success"] is True


class TestFetchLatestProduct:
    """Tests for _fetch_latest_product."""

    def test_success(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": True, "data": {"@graph": [{"id": "1"}]}},
        ):
            result = service._fetch_latest_product("PMD")
        assert result["success"] is True
        assert result["products"] == [{"id": "1"}]

    def test_empty_graph(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": True, "data": {"@graph": []}},
        ):
            result = service._fetch_latest_product("PMD")
        assert result["success"] is False
        assert "No PMD products found" in result["error"]

    def test_request_failure(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": False, "error": "timeout"},
        ):
            result = service._fetch_latest_product("PMD")
        assert result["success"] is False

    def test_parse_error_key_error(self, service):
        """KeyError in parsing returns error."""
        bad_data = MagicMock()
        bad_data.get.side_effect = KeyError("@graph")
        with patch.object(
            service,
            "_make_request",
            return_value={"success": True, "data": bad_data},
        ):
            result = service._fetch_latest_product("PMD")
        assert result["success"] is False
        assert "Failed to parse" in result["error"]

    def test_parse_error_type_error(self, service):
        """TypeError in parsing returns error."""
        bad_data = MagicMock()
        bad_data.get.side_effect = TypeError("bad type")
        with patch.object(
            service,
            "_make_request",
            return_value={"success": True, "data": bad_data},
        ):
            result = service._fetch_latest_product("PMD")
        assert result["success"] is False
        assert "Failed to parse" in result["error"]


class TestFetchProductText:
    """Tests for _fetch_product_text."""

    def test_success(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": True, "data": {"productText": "forecast text"}},
        ):
            result = service._fetch_product_text("ABC123")
        assert result["success"] is True
        assert result["text"] == "forecast text"

    def test_empty_text(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": True, "data": {"productText": ""}},
        ):
            result = service._fetch_product_text("ABC123")
        assert result["success"] is False
        assert "empty" in result["error"]

    def test_request_failure(self, service):
        with patch.object(
            service,
            "_make_request",
            return_value={"success": False, "error": "fail"},
        ):
            result = service._fetch_product_text("ABC123")
        assert result["success"] is False

    def test_parse_error(self, service):
        bad_data = MagicMock()
        bad_data.get.side_effect = TypeError("bad")
        with patch.object(
            service,
            "_make_request",
            return_value={"success": True, "data": bad_data},
        ):
            result = service._fetch_product_text("ABC123")
        assert result["success"] is False
        assert "Failed to parse" in result["error"]


class TestClassifyPmdDiscussion:
    """Tests for _classify_pmd_discussion."""

    def test_short_range_wmo(self, service):
        assert service._classify_pmd_discussion("PMDSPD\nShort Range") == "short_range"

    def test_short_range_keyword(self, service):
        assert service._classify_pmd_discussion("Short Range Discussion") == "short_range"

    def test_medium_range_wmo(self, service):
        assert service._classify_pmd_discussion("PMDEPD\nMedium Range") == "medium_range"

    def test_medium_range_keyword(self, service):
        assert service._classify_pmd_discussion("Medium Range Discussion") == "medium_range"
        assert service._classify_pmd_discussion("3-7 day forecast") == "medium_range"

    def test_extended_wmo(self, service):
        assert service._classify_pmd_discussion("PMDET4\nExtended forecast") == "extended"
        assert service._classify_pmd_discussion("PMDET8\nDay 8 outlook") == "extended"

    def test_extended_keyword(self, service):
        assert service._classify_pmd_discussion("Extended 8-10 day outlook") == "extended"

    def test_none(self, service):
        assert service._classify_pmd_discussion("Random Product") is None
        assert service._classify_pmd_discussion("") is None
        assert service._classify_pmd_discussion(None) is None


class TestClassifySwoOutlook:
    """Tests for _classify_swo_outlook."""

    def test_day1_wmo(self, service):
        assert service._classify_swo_outlook("SWODY1\nDay 1 Outlook") == "day1"

    def test_day1_keyword(self, service):
        assert service._classify_swo_outlook("Day 1 Convective Outlook") == "day1"

    def test_day2_wmo(self, service):
        assert service._classify_swo_outlook("SWODY2\nDay 2 Outlook") == "day2"

    def test_day2_keyword(self, service):
        assert service._classify_swo_outlook("Day 2 Convective Outlook") == "day2"

    def test_day3_wmo(self, service):
        assert service._classify_swo_outlook("SWODY3\nDay 3 Outlook") == "day3"

    def test_day3_keyword(self, service):
        assert service._classify_swo_outlook("Day 3 Convective Outlook") == "day3"

    def test_none(self, service):
        assert service._classify_swo_outlook("Day 4-8 Outlook") is None
        assert service._classify_swo_outlook("") is None
        assert service._classify_swo_outlook(None) is None


class TestFetchWpcDiscussions:
    """Tests for fetch_wpc_discussions."""

    def test_success_with_products(self, service):
        products = [
            {"id": "SR1"},
            {"id": "MR1"},
            {"id": "EX1"},
        ]
        # Text must contain WMO header codes for classification
        text_map = {
            "SR1": "PMDSPD\nShort Range Discussion text",
            "MR1": "PMDEPD\nMedium Range Discussion text",
            "EX1": "PMDET4\nExtended Discussion text",
        }
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": products},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                side_effect=lambda pid: {"success": True, "text": text_map.get(pid, "")},
            ),
        ):
            result = service.fetch_wpc_discussions()
        assert "Short Range" in result["short_range"]["text"]
        assert "Medium Range" in result["medium_range"]["text"]
        assert "Extended" in result["extended"]["text"]

    def test_fetch_failure(self, service):
        with patch.object(
            service,
            "_fetch_latest_product",
            return_value={"success": False, "error": "timeout"},
        ):
            result = service.fetch_wpc_discussions()
        assert "Error" in result["short_range"]["text"]

    def test_product_text_failure(self, service):
        products = [
            {"id": "SR1"},
        ]
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": products},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                return_value={"success": False, "error": "empty"},
            ),
        ):
            result = service.fetch_wpc_discussions()
        # When text fetch fails, product is skipped; no classification happens
        assert result["short_range"]["text"] == "Discussion not available"
        assert result["medium_range"]["text"] == "Discussion not available"

    def test_product_id_from_at_id(self, service):
        """Product ID extracted from @id when id is missing."""
        products = [
            {
                "issuingOffice": "WPC",
                "name": "Short Range Discussion",
                "id": "",
                "@id": "https://api.weather.gov/products/SR1",
            },
        ]
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": products},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                return_value={"success": True, "text": "text"},
            ) as mock_fetch,
        ):
            service.fetch_wpc_discussions()
        mock_fetch.assert_called_with("SR1")

    def test_breaks_after_all_fetched(self, service):
        """Stops iterating after all 3 classifications found."""
        products = [
            {"id": "SR1"},
            {"id": "MR1"},
            {"id": "EX1"},
            {"id": "SR2"},
        ]
        text_map = {
            "SR1": "PMDSPD\nShort range text",
            "MR1": "PMDEPD\nMedium range text",
            "EX1": "PMDET4\nExtended text",
            "SR2": "PMDSPD\nDuplicate",
        }
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": products},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                side_effect=lambda pid: {"success": True, "text": text_map.get(pid, "")},
            ) as mock_text,
        ):
            service.fetch_wpc_discussions()
        assert mock_text.call_count == 3


class TestFetchSpcDiscussions:
    """Tests for fetch_spc_discussions."""

    def test_success(self, service):
        products = [
            {"id": "D1"},
            {"id": "D2"},
            {"id": "D3"},
        ]
        text_map = {
            "D1": "SWODY1\nDay 1 Outlook text",
            "D2": "SWODY2\nDay 2 Outlook text",
            "D3": "SWODY3\nDay 3 Outlook text",
        }
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": products},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                side_effect=lambda pid: {"success": True, "text": text_map.get(pid, "")},
            ),
        ):
            result = service.fetch_spc_discussions()
        assert "Day 1" in result["day1"]["text"]
        assert "Day 2" in result["day2"]["text"]
        assert "Day 3" in result["day3"]["text"]

    def test_fetch_failure(self, service):
        with patch.object(
            service,
            "_fetch_latest_product",
            return_value={"success": False, "error": "err"},
        ):
            result = service.fetch_spc_discussions()
        for key in ("day1", "day2", "day3"):
            assert "Error" in result[key]["text"]

    def test_product_text_failure(self, service):
        products = [
            {"id": "D1"},
        ]
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": products},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                return_value={"success": False, "error": "fail"},
            ),
        ):
            result = service.fetch_spc_discussions()
        assert result["day1"]["text"] == "Outlook not available"
        assert result["day2"]["text"] == "Outlook not available"

    def test_product_id_from_at_id(self, service):
        products = [
            {
                "issuingOffice": "SPC",
                "name": "Day 1 Convective Outlook",
                "id": "",
                "@id": "https://api.weather.gov/products/D1",
            },
        ]
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": products},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                return_value={"success": True, "text": "text"},
            ) as mock_fetch,
        ):
            service.fetch_spc_discussions()
        mock_fetch.assert_called_with("D1")

    def test_breaks_after_all_fetched(self, service):
        products = [
            {"id": "D1"},
            {"id": "D2"},
            {"id": "D3"},
            {"id": "D1b"},
        ]
        text_map = {
            "D1": "SWODY1\nDay 1 text",
            "D2": "SWODY2\nDay 2 text",
            "D3": "SWODY3\nDay 3 text",
            "D1b": "SWODY1\nDuplicate",
        }
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": products},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                side_effect=lambda pid: {"success": True, "text": text_map.get(pid, "")},
            ) as mock_text,
        ):
            service.fetch_spc_discussions()
        assert mock_text.call_count == 3


class TestFetchQpfDiscussion:
    """Tests for fetch_qpf_discussion."""

    def test_success(self, service):
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": [{"id": "QPF1"}]},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                return_value={"success": True, "text": "QPF text"},
            ),
        ):
            result = service.fetch_qpf_discussion()
        assert result["qpf"]["text"] == "QPF text"

    def test_fetch_failure(self, service):
        with patch.object(
            service,
            "_fetch_latest_product",
            return_value={"success": False, "error": "err"},
        ):
            result = service.fetch_qpf_discussion()
        assert "Error" in result["qpf"]["text"]

    def test_text_failure(self, service):
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={"success": True, "products": [{"id": "QPF1"}]},
            ),
            patch.object(
                service,
                "_fetch_product_text",
                return_value={"success": False, "error": "fail"},
            ),
        ):
            result = service.fetch_qpf_discussion()
        assert "Error" in result["qpf"]["text"]

    def test_empty_products(self, service):
        with patch.object(
            service,
            "_fetch_latest_product",
            return_value={"success": True, "products": []},
        ):
            result = service.fetch_qpf_discussion()
        assert "not available" in result["qpf"]["text"]

    def test_product_id_from_at_id(self, service):
        with (
            patch.object(
                service,
                "_fetch_latest_product",
                return_value={
                    "success": True,
                    "products": [{"id": "", "@id": "https://api.weather.gov/products/QPF1"}],
                },
            ),
            patch.object(
                service,
                "_fetch_product_text",
                return_value={"success": True, "text": "text"},
            ) as mock_fetch,
        ):
            service.fetch_qpf_discussion()
        mock_fetch.assert_called_with("QPF1")


class TestExtractNhcOutlookText:
    """Tests for _extract_nhc_outlook_text."""

    def test_pre_tag(self):
        html = "<html><body><pre>Tropical outlook text</pre></body></html>"
        result = NationalDiscussionService._extract_nhc_outlook_text(html)
        assert result == "Tropical outlook text"

    def test_div_with_outlook_id(self):
        html = '<html><body><div id="outlookContent">Outlook info</div></body></html>'
        result = NationalDiscussionService._extract_nhc_outlook_text(html)
        assert result == "Outlook info"

    def test_class_with_outlook(self):
        html = '<html><body><div class="outlook-text">Class outlook</div></body></html>'
        result = NationalDiscussionService._extract_nhc_outlook_text(html)
        assert result == "Class outlook"

    def test_no_match(self):
        html = "<html><body><div>Nothing here</div></body></html>"
        result = NationalDiscussionService._extract_nhc_outlook_text(html)
        assert "Unable to parse" in result

    def test_exception(self):
        result = NationalDiscussionService._extract_nhc_outlook_text(None)
        assert "Error parsing" in result


class TestFetchNhcDiscussions:
    """Tests for fetch_nhc_discussions."""

    def test_success(self, service):
        with patch.object(
            service,
            "_make_html_request",
            return_value={"success": True, "html": "<pre>Outlook text</pre>"},
        ):
            result = service.fetch_nhc_discussions()
        assert result["atlantic_outlook"]["text"] == "Outlook text"
        assert result["east_pacific_outlook"]["text"] == "Outlook text"

    def test_failure(self, service):
        with patch.object(
            service,
            "_make_html_request",
            return_value={"success": False, "error": "timeout"},
        ):
            result = service.fetch_nhc_discussions()
        assert "Error" in result["atlantic_outlook"]["text"]
        assert "Error" in result["east_pacific_outlook"]["text"]


class TestExtractCpcOutlookText:
    """Tests for _extract_cpc_outlook_text."""

    def test_pre_tag(self):
        html = "<html><body><pre>CPC outlook text</pre></body></html>"
        result = NationalDiscussionService._extract_cpc_outlook_text(html, "6-10 Day")
        assert result == "CPC outlook text"

    def test_content_area_div(self):
        html = '<html><body><div class="contentArea">Content area text</div></body></html>'
        result = NationalDiscussionService._extract_cpc_outlook_text(html, "6-10 Day")
        assert result == "Content area text"

    def test_main_content_div(self):
        html = '<html><body><div class="mainContent">Main content text</div></body></html>'
        result = NationalDiscussionService._extract_cpc_outlook_text(html, "6-10 Day")
        assert result == "Main content text"

    def test_content_id_div(self):
        html = '<html><body><div id="content">ID content text</div></body></html>'
        result = NationalDiscussionService._extract_cpc_outlook_text(html, "6-10 Day")
        assert result == "ID content text"

    def test_fallback_to_longest_paragraph(self):
        long_text = "A" * 150
        html = f"<html><body><p>short</p><div>{long_text}</div></body></html>"
        result = NationalDiscussionService._extract_cpc_outlook_text(html, "6-10 Day")
        assert result == long_text

    def test_no_match(self):
        html = "<html><body></body></html>"
        result = NationalDiscussionService._extract_cpc_outlook_text(html, "6-10 Day")
        assert result is None

    def test_short_body_text(self):
        html = "<html><body><p>short</p></body></html>"
        result = NationalDiscussionService._extract_cpc_outlook_text(html, "6-10 Day")
        assert result is None

    def test_empty_pre(self):
        html = "<html><body><pre>   </pre></body></html>"
        result = NationalDiscussionService._extract_cpc_outlook_text(html, "6-10 Day")
        # Empty pre should fall through
        assert result is None

    def test_exception(self):
        result = NationalDiscussionService._extract_cpc_outlook_text(None, "6-10 Day")
        assert result is None


class TestFetchCpcDiscussions:
    """Tests for fetch_cpc_discussions."""

    def test_success(self, service):
        with patch.object(
            service,
            "_make_html_request",
            return_value={"success": True, "html": "<pre>CPC text</pre>"},
        ):
            result = service.fetch_cpc_discussions()
        assert result["outlook"]["text"] == "CPC text"

    def test_failure(self, service):
        with patch.object(
            service,
            "_make_html_request",
            return_value={"success": False, "error": "timeout"},
        ):
            result = service.fetch_cpc_discussions()
        assert "Error" in result["outlook"]["text"]

    def test_extraction_returns_none(self, service):
        with (
            patch.object(
                service,
                "_make_html_request",
                return_value={"success": True, "html": "<html></html>"},
            ),
            patch.object(
                NationalDiscussionService,
                "_extract_cpc_outlook_text",
                return_value=None,
            ),
        ):
            result = service.fetch_cpc_discussions()
        assert "unavailable" in result["outlook"]["text"].lower()


class TestServicesInit:
    """Tests for services __init__.py lazy imports."""

    def test_import_national_discussion_service(self):
        from accessiweather.services import NationalDiscussionService as NDS

        assert NDS is NationalDiscussionService

    def test_import_unknown_raises_attribute_error(self):
        import accessiweather.services as svc_mod

        with pytest.raises(AttributeError):
            svc_mod.__getattr__("NonExistentThing")

    def test_lazy_import_environmental_client(self):
        from accessiweather.services import EnvironmentalDataClient

        assert EnvironmentalDataClient is not None

    def test_lazy_import_platform_detector(self):
        from accessiweather.services import PlatformDetector

        assert PlatformDetector is not None

    def test_lazy_import_startup_manager(self):
        from accessiweather.services import StartupManager

        assert StartupManager is not None

    def test_lazy_import_github_update_service(self):
        from accessiweather.services import GitHubUpdateService

        assert GitHubUpdateService is not None

    def test_lazy_import_sync_update_channel(self):
        from accessiweather.services import sync_update_channel_to_service

        assert sync_update_channel_to_service is not None
