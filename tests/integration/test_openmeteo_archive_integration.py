"""Integration tests for Open-Meteo Archive API (historical weather data)."""

from __future__ import annotations

import os
import time
from datetime import date, timedelta

import pytest

from accessiweather.openmeteo_client import OpenMeteoApiClient

# Skip integration tests unless explicitly requested
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS", "0") == "1"
skip_reason = "Set RUN_INTEGRATION_TESTS=1 to run integration tests with real API calls"

# Test location: New York City (well-documented location with reliable historical data)
TEST_LAT = 40.7128
TEST_LON = -74.0060

# Rate limiting courtesy
DELAY_BETWEEN_REQUESTS = 1.0
REQUEST_TIMEOUT = 30.0


@pytest.fixture
def openmeteo_client():
    """Create Open-Meteo API client for tests."""
    return OpenMeteoApiClient(timeout=REQUEST_TIMEOUT, max_retries=2, retry_delay=2.0)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_archive_endpoint_returns_historical_data(openmeteo_client):
    """
    Test that the archive API endpoint returns historical weather data.

    Uses a date 14 days ago to ensure data availability (ERA5 has ~5 day lag).
    """
    # Use a date 14 days ago - well within ERA5 data availability window
    target_date = date.today() - timedelta(days=14)

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

    # This should hit https://archive-api.open-meteo.com/v1/archive
    response = openmeteo_client._make_request("archive", params, use_archive=True)

    # Verify response structure
    assert response is not None, "Archive API should return data"
    assert "daily" in response, "Response should contain daily data"

    daily = response["daily"]
    assert "time" in daily, "Daily data should contain time array"
    assert "temperature_2m_max" in daily, "Daily data should contain temperature_2m_max"
    assert "temperature_2m_min" in daily, "Daily data should contain temperature_2m_min"

    # Verify we got data for the requested date
    times = daily["time"]
    assert len(times) == 1, f"Should have exactly 1 day of data, got {len(times)}"
    assert times[0] == target_date.isoformat(), f"Date should match {target_date.isoformat()}"

    # Verify temperature values are reasonable (not null, within plausible range)
    temp_max = daily["temperature_2m_max"][0]
    temp_min = daily["temperature_2m_min"][0]

    assert temp_max is not None, "Max temperature should not be None"
    assert temp_min is not None, "Min temperature should not be None"

    # Fahrenheit range check: -40°F to 130°F covers all Earth locations
    assert -40 <= temp_max <= 130, f"Max temp {temp_max}°F outside plausible range"
    assert -40 <= temp_min <= 130, f"Min temp {temp_min}°F outside plausible range"
    assert temp_min <= temp_max, "Min temp should be <= max temp"

    time.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_archive_endpoint_different_from_forecast(openmeteo_client):
    """
    Verify archive endpoint uses different base URL than forecast endpoint.

    This test confirms the fix works by checking that:
    1. Archive requests go to archive-api.open-meteo.com
    2. Forecast requests go to api.open-meteo.com
    """
    # The client should have both URLs configured
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

    time.sleep(DELAY_BETWEEN_REQUESTS)

    # Fetch from archive endpoint (historical data from 14 days ago)
    target_date = date.today() - timedelta(days=14)
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

    time.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_archive_date_range_query(openmeteo_client):
    """Test fetching a range of historical dates from archive API."""
    # Fetch 7 days of data from 3 weeks ago (well within ERA5 availability)
    end_date = date.today() - timedelta(days=21)
    start_date = end_date - timedelta(days=6)  # 7 days total

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

    assert response is not None
    assert "daily" in response

    daily = response["daily"]
    times = daily["time"]

    # Should have 7 days of data
    assert len(times) == 7, f"Expected 7 days, got {len(times)}"

    # All temperature arrays should have 7 values
    assert len(daily["temperature_2m_max"]) == 7
    assert len(daily["temperature_2m_min"]) == 7
    assert len(daily["weather_code"]) == 7

    time.sleep(DELAY_BETWEEN_REQUESTS)
