"""
Tests for AFD notification failure isolation.

Covers:
- get_nws_forecast_and_discussion: forecast failure does not kill discussion
- get_nws_discussion_only: happy-path fetch and error handling
- get_notification_event_data: uses discussion-only path, returns issuance_time
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from accessiweather.models import Location, WeatherAlerts
from accessiweather.weather_client import WeatherClient
from accessiweather.weather_client_nws import (
    get_nws_discussion_only,
    get_nws_forecast_and_discussion,
)

NWS_BASE = "https://api.weather.gov"
US_LOCATION = Location(name="NYC", latitude=40.7128, longitude=-74.0060, country_code="US")

GRID_DATA = {
    "properties": {
        "forecast": f"{NWS_BASE}/gridpoints/OKX/36,38/forecast",
    }
}

PRODUCTS_LIST = {
    "@graph": [
        {
            "id": "test-afd-product-001",
            "issuanceTime": "2026-01-20T19:01:00+00:00",
        }
    ]
}

PRODUCT_TEXT = {"productText": "THIS IS A TEST AFD ISSUED 701 PM EST MON JAN 20 2026."}

FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Tonight",
                "temperature": 32,
                "temperatureUnit": "F",
                "windSpeed": "5 mph",
                "windDirection": "NW",
                "shortForecast": "Clear",
                "detailedForecast": "Clear skies.",
                "isDaytime": False,
                "startTime": "2026-01-20T18:00:00-05:00",
                "endTime": "2026-01-21T06:00:00-05:00",
            }
        ],
        "generatedAt": "2026-01-20T19:01:00+00:00",
    }
}


def _make_mock_response(json_data, status_code=200):
    """Build a synchronous mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _make_mock_response_error(status_code=503):
    """Build a mock response whose raise_for_status raises HTTPStatusError."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    error = httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=MagicMock(),
        response=resp,
    )
    resp.raise_for_status.side_effect = error
    return resp


def _build_client_for_discussion_happy(include_forecast_response=True):
    """
    Return a mock AsyncClient whose .get() returns appropriate responses.

    Covers the full forecast+discussion fetch path.
    """
    responses = {
        f"{NWS_BASE}/points/{US_LOCATION.latitude},{US_LOCATION.longitude}": _make_mock_response(
            GRID_DATA
        ),
        f"{NWS_BASE}/gridpoints/OKX/36,38/forecast": _make_mock_response(FORECAST_DATA),
        f"{NWS_BASE}/products/types/AFD/locations/OKX": _make_mock_response(PRODUCTS_LIST),
        f"{NWS_BASE}/products/test-afd-product-001": _make_mock_response(PRODUCT_TEXT),
    }

    def side_effect(url, **kwargs):
        return responses.get(url, _make_mock_response({}, status_code=404))

    client = MagicMock(spec=httpx.AsyncClient)
    client.get.side_effect = side_effect
    return client


def _build_client_forecast_fails():
    """
    Return a mock AsyncClient where the forecast endpoint returns 503.

    Discussion endpoints still work fine.
    """
    responses = {
        f"{NWS_BASE}/points/{US_LOCATION.latitude},{US_LOCATION.longitude}": _make_mock_response(
            GRID_DATA
        ),
        f"{NWS_BASE}/gridpoints/OKX/36,38/forecast": _make_mock_response_error(503),
        f"{NWS_BASE}/products/types/AFD/locations/OKX": _make_mock_response(PRODUCTS_LIST),
        f"{NWS_BASE}/products/test-afd-product-001": _make_mock_response(PRODUCT_TEXT),
    }

    def side_effect(url, **kwargs):
        return responses.get(url, _make_mock_response({}, status_code=404))

    client = MagicMock(spec=httpx.AsyncClient)
    client.get.side_effect = side_effect
    return client


class TestGetNwsForecastAndDiscussionIsolation:
    """Forecast failure must not suppress AFD discussion data."""

    @pytest.mark.asyncio
    async def test_forecast_failure_still_returns_discussion(self):
        """When forecast fetch raises a non-retryable HTTP error, discussion is still returned."""
        mock_client = _build_client_forecast_fails()

        forecast, discussion, issuance_time = await get_nws_forecast_and_discussion(
            location=US_LOCATION,
            nws_base_url=NWS_BASE,
            user_agent="Test/1.0",
            timeout=10.0,
            client=mock_client,
        )

        # Forecast should be None because it failed
        assert forecast is None, "Expected forecast to be None when HTTP 503 returned"

        # Discussion MUST still be populated — this is the core bug fix
        assert discussion is not None, "Discussion must not be None even when forecast fetch fails"
        assert "AFD" in discussion

        # issuance_time MUST be set for AFD update notifications to fire
        assert issuance_time is not None, (
            "issuance_time must not be None even when forecast fetch fails"
        )
        assert issuance_time == datetime(2026, 1, 20, 19, 1, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_forecast_and_discussion_both_succeed(self):
        """When everything works, both forecast and discussion are returned."""
        mock_client = _build_client_for_discussion_happy()

        forecast, discussion, issuance_time = await get_nws_forecast_and_discussion(
            location=US_LOCATION,
            nws_base_url=NWS_BASE,
            user_agent="Test/1.0",
            timeout=10.0,
            client=mock_client,
        )

        assert forecast is not None
        assert discussion is not None
        assert issuance_time is not None

    @pytest.mark.asyncio
    async def test_grid_data_failure_returns_all_none(self):
        """If the /points grid fetch fails (retryable), the function raises to let retry handle it."""
        # 503 on /points is a retryable HTTP error — the retry decorator will re-raise it
        error_response = _make_mock_response_error(503)
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = error_response

        # The retry decorator catches retryable errors and re-raises after max attempts.
        # After exhausting retries it should propagate the exception.
        with pytest.raises(httpx.HTTPStatusError):
            await get_nws_forecast_and_discussion(
                location=US_LOCATION,
                nws_base_url=NWS_BASE,
                user_agent="Test/1.0",
                timeout=10.0,
                client=mock_client,
            )


class TestGetNwsDiscussionOnly:
    """Tests for the lightweight discussion-only fetch."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_discussion_and_issuance_time(self):
        """Happy path: returns (discussion_text, issuance_time)."""
        responses = {
            f"{NWS_BASE}/points/{US_LOCATION.latitude},{US_LOCATION.longitude}": (
                _make_mock_response(GRID_DATA)
            ),
            f"{NWS_BASE}/products/types/AFD/locations/OKX": _make_mock_response(PRODUCTS_LIST),
            f"{NWS_BASE}/products/test-afd-product-001": _make_mock_response(PRODUCT_TEXT),
        }

        def side_effect(url, **kwargs):
            return responses.get(url, _make_mock_response({}, status_code=404))

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = side_effect

        discussion, issuance_time = await get_nws_discussion_only(
            location=US_LOCATION,
            nws_base_url=NWS_BASE,
            user_agent="Test/1.0",
            timeout=10.0,
            client=mock_client,
        )

        assert discussion is not None
        assert "AFD" in discussion
        assert issuance_time == datetime(2026, 1, 20, 19, 1, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_no_forecast_call_is_made(self):
        """Discussion-only fetch must never call the forecast endpoint."""
        responses = {
            f"{NWS_BASE}/points/{US_LOCATION.latitude},{US_LOCATION.longitude}": (
                _make_mock_response(GRID_DATA)
            ),
            f"{NWS_BASE}/products/types/AFD/locations/OKX": _make_mock_response(PRODUCTS_LIST),
            f"{NWS_BASE}/products/test-afd-product-001": _make_mock_response(PRODUCT_TEXT),
        }

        def side_effect(url, **kwargs):
            return responses.get(url, _make_mock_response({}, status_code=404))

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = side_effect

        await get_nws_discussion_only(
            location=US_LOCATION,
            nws_base_url=NWS_BASE,
            user_agent="Test/1.0",
            timeout=10.0,
            client=mock_client,
        )

        called_urls = [call.args[0] for call in mock_client.get.call_args_list]
        assert all("forecast" not in url.split("/")[-1] for url in called_urls), (
            f"Forecast endpoint must not be called by get_nws_discussion_only, "
            f"but called: {called_urls}"
        )

    @pytest.mark.asyncio
    async def test_unrecoverable_error_returns_none_none(self):
        """Non-retryable error on /points returns (None, None)."""
        # 404 is not in RETRYABLE_EXCEPTIONS so it should return (None, None)
        error_response = _make_mock_response_error(404)
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = error_response

        discussion, issuance_time = await get_nws_discussion_only(
            location=US_LOCATION,
            nws_base_url=NWS_BASE,
            user_agent="Test/1.0",
            timeout=10.0,
            client=mock_client,
        )

        assert discussion is None
        assert issuance_time is None


class TestGetNotificationEventDataDiscussionPath:
    """WeatherClient.get_notification_event_data must use the discussion-only path."""

    @pytest.fixture
    def client(self):
        return WeatherClient()

    @pytest.fixture
    def us_location(self):
        return US_LOCATION

    @pytest.mark.asyncio
    async def test_discussion_issuance_time_populated(self, client, us_location):
        """get_notification_event_data populates discussion_issuance_time for US locations."""
        issuance = datetime(2026, 1, 20, 19, 1, 0, tzinfo=timezone.utc)

        client._get_nws_discussion_only = AsyncMock(return_value=("AFD text", issuance))
        client._get_nws_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
        client._fetch_nws_cancel_references = AsyncMock(return_value=set())

        weather_data = await client.get_notification_event_data(us_location)

        assert weather_data.discussion_issuance_time == issuance
        assert weather_data.discussion == "AFD text"

    @pytest.mark.asyncio
    async def test_discussion_only_method_is_called_not_forecast_and_discussion(
        self, client, us_location
    ):
        """Notification path calls _get_nws_discussion_only, not _get_nws_forecast_and_discussion."""
        issuance = datetime(2026, 1, 20, 19, 1, 0, tzinfo=timezone.utc)

        client._get_nws_discussion_only = AsyncMock(return_value=("AFD text", issuance))
        client._get_nws_forecast_and_discussion = AsyncMock(
            return_value=(None, "should not be called", None)
        )
        client._get_nws_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
        client._fetch_nws_cancel_references = AsyncMock(return_value=set())

        await client.get_notification_event_data(us_location)

        client._get_nws_discussion_only.assert_called_once_with(us_location)
        client._get_nws_forecast_and_discussion.assert_not_called()

    @pytest.mark.asyncio
    async def test_discussion_fetch_failure_does_not_crash(self, client, us_location):
        """If discussion fetch returns (None, None), weather_data is returned without crashing."""
        client._get_nws_discussion_only = AsyncMock(return_value=(None, None))
        client._get_nws_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
        client._fetch_nws_cancel_references = AsyncMock(return_value=set())

        weather_data = await client.get_notification_event_data(us_location)

        assert weather_data is not None
        assert weather_data.discussion_issuance_time is None
