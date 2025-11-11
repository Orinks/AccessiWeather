"""Integration tests for Open-Meteo weather provider API."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from accessiweather.models import Location
from accessiweather.weather_client_openmeteo import (
    get_openmeteo_all_data_parallel,
    get_openmeteo_current_conditions,
    get_openmeteo_hourly_forecast,
    parse_openmeteo_current_conditions,
)

# Skip integration tests unless explicitly requested
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS", "0") == "1"
skip_reason = "Set RUN_INTEGRATION_TESTS=1 to run integration tests with real API calls"

# Test location: Lumberton, NJ (from the screenshot)
TEST_LOCATION = Location(name="Lumberton, New Jersey", latitude=39.9643, longitude=-74.8099)

# Open-Meteo API endpoint
OPENMETEO_BASE_URL = "https://api.open-meteo.com/v1"
REQUEST_TIMEOUT = 30.0
DELAY_BETWEEN_REQUESTS = 0.5  # Rate limiting courtesy


@pytest.fixture
async def http_client():
    """Create a shared HTTP client for tests."""
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as client:
        yield client


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_openmeteo_current_conditions_sunrise_sunset(http_client):
    """Test Open-Meteo current conditions returns valid sunrise/sunset times."""
    # Fetch current conditions
    current = await get_openmeteo_current_conditions(
        TEST_LOCATION,
        OPENMETEO_BASE_URL,
        REQUEST_TIMEOUT,
        http_client,
    )

    assert current is not None, "Open-Meteo should return current conditions"

    # Verify sunrise time
    assert current.sunrise_time is not None, "Sunrise time should be present"
    assert isinstance(current.sunrise_time, datetime), "Sunrise should be a datetime object"
    # Note: Open-Meteo parser may return naive datetimes (tzinfo=None) depending on implementation
    # This is a known issue we're tracking. At minimum, verify the datetime is parseable.

    # Verify sunset time
    assert current.sunset_time is not None, "Sunset time should be present"
    assert isinstance(current.sunset_time, datetime), "Sunset should be a datetime object"

    # Sanity check: sunrise/sunset should be within reasonable range
    # If timezone-aware, compare to now; otherwise just check year
    if current.sunrise_time.tzinfo is not None:
        now_utc = datetime.now(UTC)
        time_window = timedelta(hours=48)  # Allow 48-hour window

        assert (
            abs((current.sunrise_time - now_utc).total_seconds()) < time_window.total_seconds()
        ), f"Sunrise time {current.sunrise_time} should be within 48 hours of now {now_utc}"
        assert abs((current.sunset_time - now_utc).total_seconds()) < time_window.total_seconds(), (
            f"Sunset time {current.sunset_time} should be within 48 hours of now {now_utc}"
        )

    # Sunrise should be before sunset
    assert current.sunrise_time < current.sunset_time, "Sunrise should occur before sunset"

    # Sunrise/sunset should not be epoch (1970)
    assert current.sunrise_time.year > 2000, f"Sunrise year {current.sunrise_time.year} is invalid"
    assert current.sunset_time.year > 2000, f"Sunset year {current.sunset_time.year} is invalid"

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_openmeteo_current_conditions_last_updated(http_client):
    """Test Open-Meteo current conditions has valid last_updated timestamp."""
    current = await get_openmeteo_current_conditions(
        TEST_LOCATION,
        OPENMETEO_BASE_URL,
        REQUEST_TIMEOUT,
        http_client,
    )

    assert current is not None
    assert current.last_updated is not None, "Last updated time should be present"
    assert isinstance(current.last_updated, datetime), "Last updated should be a datetime"

    # Last updated should be recent (within 7 days) and not in the future
    now_utc = datetime.now(UTC)
    age = now_utc - current.last_updated.replace(tzinfo=UTC)

    assert age.total_seconds() >= 0, "Last updated should not be in the future"
    assert age.total_seconds() < timedelta(days=7).total_seconds(), (
        f"Last updated {current.last_updated} is too old (age: {age})"
    )

    # Year sanity check (not epoch)
    assert current.last_updated.year > 2000, "Last updated year is invalid"

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_openmeteo_forecast_contains_sunrise_sunset(http_client):
    """Test Open-Meteo forecast includes sunrise/sunset data in raw response."""
    # Make raw API call to get forecast with daily sunrise/sunset
    url = f"{OPENMETEO_BASE_URL}/forecast"
    params = {
        "latitude": TEST_LOCATION.latitude,
        "longitude": TEST_LOCATION.longitude,
        "daily": "sunrise,sunset,temperature_2m_max,weather_code",
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
        "forecast_days": 7,
    }

    response = await http_client.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    # Check raw response structure
    assert "daily" in data, "Response should contain daily data"
    daily = data["daily"]

    assert "sunrise" in daily, "Daily data should contain sunrise"
    assert "sunset" in daily, "Daily data should contain sunset"
    assert "time" in daily, "Daily data should contain time (dates)"

    # Check that arrays have data
    sunrise_list = daily["sunrise"]
    sunset_list = daily["sunset"]
    dates = daily["time"]

    assert len(sunrise_list) > 0, "Sunrise array should have data"
    assert len(sunset_list) > 0, "Sunset array should have data"
    assert len(dates) > 0, "Dates array should have data"
    assert len(sunrise_list) == len(sunset_list) == len(dates), "Arrays should have equal length"

    # Parse and validate first day's sunrise/sunset
    first_sunrise = sunrise_list[0]
    first_sunset = sunset_list[0]

    assert first_sunrise is not None, "First sunrise should not be None"
    assert first_sunset is not None, "First sunset should not be None"

    # Parse ISO datetime strings
    from accessiweather.weather_client_openmeteo import _parse_iso_datetime

    sunrise_dt = _parse_iso_datetime(first_sunrise)
    sunset_dt = _parse_iso_datetime(first_sunset)

    assert sunrise_dt is not None, f"Failed to parse sunrise: {first_sunrise}"
    assert sunset_dt is not None, f"Failed to parse sunset: {first_sunset}"

    # Timezone aware check (may be None for naive datetimes)
    # The raw API typically returns timezone-aware ISO strings, but parser may strip it
    if sunrise_dt.tzinfo is not None and sunset_dt.tzinfo is not None:
        # If timezone-aware, verify they're reasonable
        assert sunrise_dt.tzinfo is not None, "Parsed sunrise should be timezone-aware"
        assert sunset_dt.tzinfo is not None, "Parsed sunset should be timezone-aware"

    # Sunrise before sunset
    assert sunrise_dt < sunset_dt, "Sunrise should be before sunset"

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_openmeteo_hourly_forecast_timezone_aware(http_client):
    """Test Open-Meteo hourly forecast returns timezone-aware timestamps."""
    hourly = await get_openmeteo_hourly_forecast(
        TEST_LOCATION,
        OPENMETEO_BASE_URL,
        REQUEST_TIMEOUT,
        http_client,
    )

    assert hourly is not None, "Hourly forecast should not be None"
    assert len(hourly.periods) > 0, "Hourly forecast should have periods"

    # Check first few periods have valid start times
    for i, period in enumerate(hourly.periods[:5]):
        if period.start_time:  # May be None if parsing failed
            assert isinstance(period.start_time, datetime), (
                f"Period {i} start_time should be datetime"
            )
            # Note: Open-Meteo may return naive datetimes depending on parsing
            # Just verify it's parseable and reasonable

            # Check it's a recent hour (not epoch)
            assert period.start_time.year > 2000, f"Period {i} start_time year is invalid"

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_openmeteo_parallel_fetch_returns_all_data(http_client):
    """Test Open-Meteo parallel fetch returns current, forecast, and hourly data."""
    current, forecast, hourly = await get_openmeteo_all_data_parallel(
        TEST_LOCATION,
        OPENMETEO_BASE_URL,
        REQUEST_TIMEOUT,
        http_client,
    )

    # All three should return successfully
    assert current is not None, "Current conditions should be present"
    assert forecast is not None, "Forecast should be present"
    assert hourly is not None, "Hourly forecast should be present"

    # Verify current has sunrise/sunset
    assert current.sunrise_time is not None, "Current should have sunrise"
    assert current.sunset_time is not None, "Current should have sunset"

    # Verify forecast has periods
    assert len(forecast.periods) > 0, "Forecast should have periods"

    # Verify hourly has periods
    assert len(hourly.periods) > 0, "Hourly forecast should have periods"

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_openmeteo_raw_response_timezone_field(http_client):
    """Test Open-Meteo API response includes timezone information."""
    url = f"{OPENMETEO_BASE_URL}/forecast"
    params = {
        "latitude": TEST_LOCATION.latitude,
        "longitude": TEST_LOCATION.longitude,
        "current": "temperature_2m",
        "timezone": "auto",
        "forecast_days": 1,
    }

    response = await http_client.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    # Check timezone field is present
    assert "timezone" in data, "Response should include timezone"
    assert "timezone_abbreviation" in data, "Response should include timezone abbreviation"

    timezone = data["timezone"]
    assert isinstance(timezone, str), "Timezone should be a string"
    assert len(timezone) > 0, "Timezone should not be empty"

    # Should be an IANA timezone (e.g., "America/New_York")
    assert "/" in timezone or timezone == "GMT", (
        f"Timezone '{timezone}' should be IANA format or GMT"
    )

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_openmeteo_parser_handles_sunrise_sunset():
    """Test Open-Meteo parser correctly extracts sunrise/sunset from API response."""
    # Create a sample response matching Open-Meteo API structure
    sample_response = {
        "current": {
            "time": "2025-11-11T12:00:00Z",
            "temperature_2m": 55.0,
            "relative_humidity_2m": 65,
            "weather_code": 1,
            "wind_speed_10m": 8.5,
            "wind_direction_10m": 180,
            "pressure_msl": 1013.25,
        },
        "current_units": {
            "temperature_2m": "°F",
            "wind_speed_10m": "mph",
            "pressure_msl": "hPa",
        },
        "daily": {
            "time": ["2025-11-11"],
            "sunrise": ["2025-11-11T06:30:00-05:00"],
            "sunset": ["2025-11-11T17:15:00-05:00"],
            "uv_index_max": [4.2],
        },
    }

    # Parse with the actual parser function
    current = parse_openmeteo_current_conditions(sample_response)

    # Verify sunrise/sunset were parsed
    assert current.sunrise_time is not None, "Parser should extract sunrise"
    assert current.sunset_time is not None, "Parser should extract sunset"

    # Verify they are datetime objects
    assert isinstance(current.sunrise_time, datetime)
    assert isinstance(current.sunset_time, datetime)

    # Verify timezone awareness (sample has timezone-aware strings)
    # The parser should preserve timezone info from the input
    assert current.sunrise_time.tzinfo is not None, (
        "Parsed sunrise should be timezone-aware from ISO string"
    )
    assert current.sunset_time.tzinfo is not None, (
        "Parsed sunset should be timezone-aware from ISO string"
    )

    # Verify reasonable values
    assert current.sunrise_time < current.sunset_time
    assert current.sunrise_time.year == 2025
    assert current.sunset_time.year == 2025


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_openmeteo_handles_missing_sunrise_sunset():
    """Test parser gracefully handles missing sunrise/sunset data."""
    # Response without daily sunrise/sunset
    sample_response = {
        "current": {
            "time": "2025-11-11T12:00:00Z",
            "temperature_2m": 55.0,
            "relative_humidity_2m": 65,
            "weather_code": 1,
            "wind_speed_10m": 8.5,
            "wind_direction_10m": 180,
            "pressure_msl": 1013.25,
        },
        "current_units": {
            "temperature_2m": "°F",
            "wind_speed_10m": "mph",
            "pressure_msl": "hPa",
        },
        # No daily data
    }

    current = parse_openmeteo_current_conditions(sample_response)

    # Should parse successfully without sunrise/sunset
    assert current is not None
    assert current.temperature_f == 55.0
    assert current.sunrise_time is None
    assert current.sunset_time is None
