"""Tests for NationalDiscussionService fetch_all and caching (US-004)."""

import time
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.services.national_discussion_service import NationalDiscussionService


@pytest.fixture
def service():
    """Create a service with short cache TTL for testing."""
    return NationalDiscussionService(request_delay=0, max_retries=0, timeout=1, cache_ttl=3600)


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
                return_value={"outlook_6_10": {"title": "t", "text": "cpc text"}},
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
