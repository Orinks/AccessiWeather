"""Integration tests for Open-Meteo Archive API (historical weather data)."""

from __future__ import annotations

import time
from datetime import date, timedelta

import pytest

from accessiweather.openmeteo_client import OpenMeteoApiClient
from tests.integration.conftest import (
    LIVE_WEATHER_TESTS,
    get_vcr_config,
    skip_if_cassette_missing,
)

try:
    import vcr

    HAS_VCR = True
except ImportError:
    HAS_VCR = False

# Test location: New York City (well-documented location with reliable historical data)
TEST_LAT = 40.7128
TEST_LON = -74.0060

# Rate limiting courtesy
DELAY_BETWEEN_REQUESTS = 1.0
REQUEST_TIMEOUT = 30.0

# Fixed dates for cassette tests (at least 14 days in past for ERA5 availability)
FIXED_ARCHIVE_DATE = date(2024, 12, 1)
FIXED_RANGE_END_DATE = date(2024, 11, 24)
FIXED_RANGE_START_DATE = date(2024, 11, 18)  # 7 days total


def get_archive_date() -> date:
    """Get archive date - fixed for cassettes, dynamic for live mode."""
    if LIVE_WEATHER_TESTS:
        return date.today() - timedelta(days=14)
    return FIXED_ARCHIVE_DATE


def get_range_dates() -> tuple[date, date]:
    """Get date range - fixed for cassettes, dynamic for live mode."""
    if LIVE_WEATHER_TESTS:
        end_date = date.today() - timedelta(days=21)
        start_date = end_date - timedelta(days=6)
        return start_date, end_date
    return FIXED_RANGE_START_DATE, FIXED_RANGE_END_DATE


@pytest.fixture
def openmeteo_client():
    """Create Open-Meteo API client for tests."""
    return OpenMeteoApiClient(timeout=REQUEST_TIMEOUT, max_retries=2, retry_delay=2.0)


def _run_with_cassette(cassette_name: str, test_fn):
    """Run a test function with VCR cassette or in live mode."""
    # Skip if cassette doesn't exist and not in live mode
    skip_if_cassette_missing(cassette_name)

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette(cassette_name):  # type: ignore[attr-defined]
            test_fn()
    else:
        if not LIVE_WEATHER_TESTS:
            pytest.skip("VCR not installed and not in live mode")
        test_fn()


@pytest.mark.integration
@pytest.mark.network
def test_archive_endpoint_returns_historical_data(openmeteo_client):
    """
    Test that the archive API endpoint returns historical weather data.

    Uses a fixed date for cassette replay or 14 days ago for live mode.
    """

    def run_test():
        target_date = get_archive_date()

        params = {
            "latitude": TEST_LAT,
            "longitude": TEST_LON,
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "temperature_2m_mean",
                "wind_speed_10m_max",
            ],
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
        }

        response = openmeteo_client._make_request("archive", params, use_archive=True)

        # Contract: response structure
        assert response is not None, "Archive API should return data"
        assert "daily" in response, "Response should contain daily data"

        daily = response["daily"]
        assert "time" in daily, "Daily data should contain time array"
        assert "temperature_2m_max" in daily, "Daily data should contain temperature_2m_max"
        assert "temperature_2m_min" in daily, "Daily data should contain temperature_2m_min"

        # Contract: should return exactly 1 day of data
        times = daily["time"]
        assert len(times) == 1, f"Should have exactly 1 day of data, got {len(times)}"

        # Contract: temperature values are reasonable (not null, within plausible range)
        temp_max = daily["temperature_2m_max"][0]
        temp_min = daily["temperature_2m_min"][0]

        assert temp_max is not None, "Max temperature should not be None"
        assert temp_min is not None, "Min temperature should not be None"

        # Fahrenheit range check: -40°F to 130°F covers all Earth locations
        assert -40 <= temp_max <= 130, f"Max temp {temp_max}°F outside plausible range"
        assert -40 <= temp_min <= 130, f"Min temp {temp_min}°F outside plausible range"
        assert temp_min <= temp_max, "Min temp should be <= max temp"

        if LIVE_WEATHER_TESTS:
            time.sleep(DELAY_BETWEEN_REQUESTS)

    _run_with_cassette("openmeteo/archive_historical_data.yaml", run_test)


@pytest.mark.integration
@pytest.mark.network
def test_archive_endpoint_different_from_forecast(openmeteo_client):
    """
    Verify archive endpoint uses different base URL than forecast endpoint.

    This test confirms the fix works by checking that:
    1. Archive requests go to archive-api.open-meteo.com
    2. Forecast requests go to api.open-meteo.com
    """

    def run_test():
        # Contract: client should have both URLs configured
        assert openmeteo_client.BASE_URL == "https://api.open-meteo.com/v1"
        assert openmeteo_client.ARCHIVE_BASE_URL == "https://archive-api.open-meteo.com/v1"

        # Fetch from forecast endpoint (current weather)
        forecast_response = openmeteo_client.get_current_weather(
            latitude=TEST_LAT,
            longitude=TEST_LON,
            temperature_unit="fahrenheit",
        )

        assert forecast_response is not None, "Forecast endpoint should work"
        assert "current" in forecast_response, "Forecast should have current data"

        if LIVE_WEATHER_TESTS:
            time.sleep(DELAY_BETWEEN_REQUESTS)

        # Fetch from archive endpoint
        target_date = get_archive_date()
        params = {
            "latitude": TEST_LAT,
            "longitude": TEST_LON,
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
        }

        archive_response = openmeteo_client._make_request("archive", params, use_archive=True)

        assert archive_response is not None, "Archive endpoint should work"
        assert "daily" in archive_response, "Archive should have daily data"

        if LIVE_WEATHER_TESTS:
            time.sleep(DELAY_BETWEEN_REQUESTS)

    _run_with_cassette("openmeteo/archive_vs_forecast.yaml", run_test)


@pytest.mark.integration
@pytest.mark.network
def test_archive_date_range_query(openmeteo_client):
    """Test fetching a range of historical dates from archive API."""

    def run_test():
        start_date, end_date = get_range_dates()

        params = {
            "latitude": TEST_LAT,
            "longitude": TEST_LON,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "weather_code",
            ],
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
        }

        response = openmeteo_client._make_request("archive", params, use_archive=True)

        # Contract: response structure
        assert response is not None
        assert "daily" in response

        daily = response["daily"]
        times = daily["time"]

        # Contract: should have 7 days of data
        assert len(times) == 7, f"Expected 7 days, got {len(times)}"

        # Contract: all temperature arrays should have 7 values
        assert len(daily["temperature_2m_max"]) == 7
        assert len(daily["temperature_2m_min"]) == 7
        assert len(daily["weather_code"]) == 7

        # Contract: temperatures should be in valid range
        for i in range(7):
            temp_max = daily["temperature_2m_max"][i]
            temp_min = daily["temperature_2m_min"][i]
            if temp_max is not None and temp_min is not None:
                assert -40 <= temp_max <= 130, f"Day {i}: Max temp {temp_max}°F outside range"
                assert -40 <= temp_min <= 130, f"Day {i}: Min temp {temp_min}°F outside range"
                assert temp_min <= temp_max, f"Day {i}: Min temp should be <= max temp"

        if LIVE_WEATHER_TESTS:
            time.sleep(DELAY_BETWEEN_REQUESTS)

    _run_with_cassette("openmeteo/archive_date_range.yaml", run_test)
