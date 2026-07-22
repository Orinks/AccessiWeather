"""Tests for current AirNow observations."""

from __future__ import annotations

import logging
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from accessiweather.models import Location
from accessiweather.services.airnow_client import AirNowClient


def _location(latitude: float = 39.9526, longitude: float = -75.1652) -> Location:
    return Location(name="Philadelphia", latitude=latitude, longitude=longitude, country_code="US")


def _async_client(payload, *, error: Exception | None = None) -> AsyncMock:
    def raise_for_status() -> None:
        if error is not None:
            raise error

    response = SimpleNamespace(json=lambda: payload, raise_for_status=raise_for_status)
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


def _observations() -> list[dict]:
    return [
        {
            "DateObserved": "2026-07-21",
            "HourObserved": 14,
            "LocalTimeZone": "EDT",
            "ReportingArea": "Philadelphia",
            "ParameterName": "O3",
            "AQI": 42,
            "Category": {"Number": 1, "Name": "Good"},
        },
        {
            "DateObserved": "2026-07-21",
            "HourObserved": "14",
            "LocalTimeZone": "EDT",
            "ReportingArea": "Philadelphia",
            "ParameterName": "PM2.5",
            "AQI": "87",
            "Category": {"Number": 2, "Name": "Moderate"},
        },
    ]


@pytest.mark.asyncio
async def test_fetch_uses_current_ziplatlong_endpoint_and_selects_highest_aqi():
    http_client = _async_client(_observations())
    client = AirNowClient("  secret-key  ", distance=25)

    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=http_client,
    ):
        result = await client.fetch_current_air_quality(_location())

    assert result is not None
    assert result.aqi == 87
    assert result.category == "Moderate"
    assert result.pollutant == "PM2.5"
    assert result.reporting_area == "Philadelphia"
    assert result.observed_at is not None
    assert result.observed_at.hour == 14
    assert result.observed_at.utcoffset() == timedelta(hours=-4)

    url = http_client.get.await_args.args[0]
    params = http_client.get.await_args.kwargs["params"]
    assert url == "https://www.airnowapi.org/aq/observation/current/ziplatlong/"
    assert params == {
        "format": "application/json",
        "latitude": 39.9526,
        "longitude": -75.1652,
        "distance": 25,
        "API_KEY": "secret-key",
    }


@pytest.mark.asyncio
async def test_fetch_parses_live_camelcase_nowcast_schema():
    # Captured from the live API on 2026-07-22: camelCase fields, nowcastAQI,
    # and "HH:MM" hourObserved instead of the documented PascalCase schema.
    payload = [
        {
            "dateObserved": "2026-07-22",
            "hourObserved": "09:00",
            "localTimeZone": "EDT",
            "reportingAreaName": "Riverline",
            "siteName": "TOR",
            "parameterName": "PM2.5",
            "nowcastAQI": 28,
            "aqiCategoryName": "Good",
            "reportingAgency": "Philadelphia Air Management Services",
        },
        {
            "dateObserved": "2026-07-22",
            "hourObserved": "09:00",
            "localTimeZone": "EDT",
            "reportingAreaName": "Riverline",
            "siteName": "Bristol",
            "parameterName": "OZONE",
            "nowcastAQI": 28,
            "aqiCategoryName": "Good",
        },
        {
            "dateObserved": "2026-07-22",
            "hourObserved": "09:00",
            "localTimeZone": "EDT",
            "reportingAreaName": "Riverline",
            "siteName": "NEW",
            "parameterName": "PM10",
            "nowcastAQI": 12,
            "aqiCategoryName": "Good",
        },
    ]

    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=_async_client(payload),
    ):
        result = await AirNowClient("key").fetch_current_air_quality(_location())

    assert result is not None
    assert result.aqi == 28
    assert result.category == "Good"
    # Ties keep the first (primary) pollutant, matching AirNow.gov's display.
    assert result.pollutant == "PM2.5"
    assert result.reporting_area == "Riverline"
    assert result.observed_at is not None
    assert result.observed_at.hour == 9
    assert result.observed_at.utcoffset() == timedelta(hours=-4)


@pytest.mark.asyncio
async def test_invalid_records_are_ignored_and_category_can_be_derived():
    payload = [
        {"ParameterName": "O3", "AQI": -1},
        {"ParameterName": "PM10", "AQI": None},
        {"ParameterName": "CO", "AQI": "not available"},
        {"ParameterName": "PM2.5", "AQI": 151, "Category": {}},
    ]
    client = AirNowClient("key")

    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=_async_client(payload),
    ):
        result = await client.fetch_current_air_quality(_location())

    assert result is not None
    assert result.aqi == 151
    assert result.category == "Unhealthy"
    assert result.pollutant == "PM2.5"


@pytest.mark.parametrize(
    ("aqi", "category"),
    [
        (0, "Good"),
        (50, "Good"),
        (51, "Moderate"),
        (100, "Moderate"),
        (101, "Unhealthy for Sensitive Groups"),
        (150, "Unhealthy for Sensitive Groups"),
        (151, "Unhealthy"),
        (200, "Unhealthy"),
        (201, "Very Unhealthy"),
        (300, "Very Unhealthy"),
        (301, "Hazardous"),
    ],
)
def test_category_boundaries(aqi: int, category: str):
    assert AirNowClient._air_quality_category(aqi) == category


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {}, [], ["bad"], [{"AQI": None}]])
async def test_empty_or_malformed_payload_returns_none(payload):
    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=_async_client(payload),
    ):
        result = await AirNowClient("key").fetch_current_air_quality(_location())

    assert result is None


@pytest.mark.asyncio
async def test_http_failure_does_not_log_api_key(caplog):
    request = httpx.Request(
        "GET",
        "https://www.airnowapi.org/aq/observation/current/ziplatlong/?API_KEY=secret-key",
    )
    response = httpx.Response(401, request=request)
    error = httpx.HTTPStatusError("bad key at secret-key", request=request, response=response)

    with (
        caplog.at_level(logging.WARNING),
        patch(
            "accessiweather.services.airnow_client.httpx.AsyncClient",
            return_value=_async_client([], error=error),
        ),
    ):
        result = await AirNowClient("secret-key").fetch_current_air_quality(_location())

    assert result is None
    assert "secret-key" not in caplog.text
    assert "HTTPStatusError" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(91, 0), (-91, 0), (0, 181), (0, -181), (float("nan"), 0)],
)
async def test_invalid_coordinates_are_rejected_before_request(latitude, longitude):
    client = AirNowClient("key")
    with (
        patch("accessiweather.services.airnow_client.httpx.AsyncClient") as async_client,
        pytest.raises(ValueError),
    ):
        await client.fetch_current_air_quality(_location(latitude, longitude))
    async_client.assert_not_called()


@pytest.mark.asyncio
async def test_observation_is_cached_for_one_hour_per_location():
    http_client = _async_client(_observations())
    client = AirNowClient("key")

    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=http_client,
    ):
        first = await client.fetch_current_air_quality(_location())
        second = await client.fetch_current_air_quality(_location())

    assert first == second
    assert client._cache.default_ttl == 3600
    http_client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_successful_empty_response_is_cached_for_one_hour():
    http_client = _async_client([])
    client = AirNowClient("key")

    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=http_client,
    ):
        first = await client.fetch_current_air_quality(_location())
        second = await client.fetch_current_air_quality(_location())

    assert first is None
    assert second is None
    http_client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_key_skips_request():
    with patch("accessiweather.services.airnow_client.httpx.AsyncClient") as async_client:
        result = await AirNowClient(" ").fetch_current_air_quality(_location())

    assert result is None
    async_client.assert_not_called()


def _validation_client(status_code=200, payload=None, *, error: Exception | None = None):
    response = SimpleNamespace(status_code=status_code, json=lambda: payload)
    client = AsyncMock()
    client.get = AsyncMock(return_value=response, side_effect=error)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_validate_api_key_accepts_successful_list_response():
    http_client = _validation_client(payload=[])
    client = AirNowClient("  secret-key  ")

    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=http_client,
    ):
        valid, error = await client.validate_api_key()

    assert valid is True
    assert error is None
    params = http_client.get.await_args.kwargs["params"]
    assert params["API_KEY"] == "secret-key"
    assert (params["latitude"], params["longitude"]) == AirNowClient.VALIDATION_COORDINATES


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_validate_api_key_reports_invalid_key(status_code):
    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=_validation_client(status_code=status_code),
    ):
        valid, error = await AirNowClient("bad-key").validate_api_key()

    assert valid is False
    assert error == "Invalid API key"


@pytest.mark.asyncio
async def test_validate_api_key_reports_rate_limit_as_probably_valid():
    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=_validation_client(status_code=429),
    ):
        valid, error = await AirNowClient("key").validate_api_key()

    assert valid is False
    assert "key appears valid" in error


@pytest.mark.asyncio
async def test_validate_api_key_treats_error_body_with_ok_status_as_invalid():
    payload = {"WebServiceError": [{"Message": "Invalid API key"}]}
    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=_validation_client(payload=payload),
    ):
        valid, error = await AirNowClient("bad-key").validate_api_key()

    assert valid is False
    assert error == "Invalid API key"


@pytest.mark.asyncio
async def test_validate_api_key_network_error_does_not_leak_key():
    request = httpx.Request(
        "GET",
        "https://www.airnowapi.org/aq/observation/current/ziplatlong/?API_KEY=secret-key",
    )
    error = httpx.ConnectTimeout("timed out at secret-key", request=request)

    with patch(
        "accessiweather.services.airnow_client.httpx.AsyncClient",
        return_value=_validation_client(error=error),
    ):
        valid, message = await AirNowClient("secret-key").validate_api_key()

    assert valid is False
    assert "secret-key" not in message
    assert "ConnectTimeout" in message


@pytest.mark.asyncio
async def test_validate_api_key_requires_key():
    with patch("accessiweather.services.airnow_client.httpx.AsyncClient") as async_client:
        valid, error = await AirNowClient("").validate_api_key()

    assert valid is False
    assert error == "No API key provided"
    async_client.assert_not_called()
