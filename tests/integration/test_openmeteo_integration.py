"""Integration tests for Open-Meteo weather provider API."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

import pytest

from accessiweather.models import Location
from accessiweather.openmeteo_client import OpenMeteoApiClient
from accessiweather.openmeteo_mapper import OpenMeteoMapper

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
def openmeteo_client():
    """Create Open-Meteo API client for tests."""
    return OpenMeteoApiClient(timeout=REQUEST_TIMEOUT)


@pytest.fixture
def mapper():
    """Create Open-Meteo mapper for tests."""
    return OpenMeteoMapper()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.flaky(reruns=2, reruns_delay=5)
def test_openmeteo_current_conditions_sunrise_sunset(openmeteo_client, mapper):
    """Test Open-Meteo current conditions returns valid sunrise/sunset times."""
    # Fetch raw data from API
    raw_data = openmeteo_client.get_current_weather(
        latitude=TEST_LOCATION.latitude,
        longitude=TEST_LOCATION.longitude,
        temperature_unit="fahrenheit",
    )

    assert raw_data is not None, "Open-Meteo should return data"
    assert "daily" in raw_data, "Response should include daily data with sunrise/sunset"

    # Map to internal format
    mapped_data = mapper.map_current_conditions(raw_data)

    # Extract sunrise/sunset from mapped data
    props = mapped_data["properties"]
    sunrise_str = props["sunrise"]
    sunset_str = props["sunset"]

    assert sunrise_str is not None, "Sunrise time should be present"
    assert sunset_str is not None, "Sunset time should be present"

    # Parse the datetime strings (they should be naive local time strings)
    sunrise = datetime.fromisoformat(sunrise_str)
    sunset = datetime.fromisoformat(sunset_str)

    # Note: After our fix, sunrise/sunset are naive datetimes in local time
    # They should NOT have timezone info
    assert sunrise.tzinfo is None, "Sunrise should be naive (local time)"
    assert sunset.tzinfo is None, "Sunset should be naive (local time)"

    # Sunrise should be before sunset
    assert sunrise < sunset, "Sunrise should occur before sunset"

    # Sunrise/sunset should not be epoch (1970)
    assert sunrise.year > 2000, f"Sunrise year {sunrise.year} is invalid"
    assert sunset.year > 2000, f"Sunset year {sunset.year} is invalid"

    # Sunrise should be in reasonable morning hours (4 AM - 9 AM typically)
    assert 4 <= sunrise.hour <= 9, f"Sunrise hour {sunrise.hour} seems unreasonable"

    # Sunset should be in reasonable evening hours (4 PM - 8 PM typically)
    assert 16 <= sunset.hour <= 20, f"Sunset hour {sunset.hour} seems unreasonable"

    time.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_openmeteo_current_conditions_last_updated(openmeteo_client, mapper):
    """Test Open-Meteo current conditions has valid last_updated timestamp."""
    # Fetch raw data
    raw_data = openmeteo_client.get_current_weather(
        latitude=TEST_LOCATION.latitude,
        longitude=TEST_LOCATION.longitude,
        temperature_unit="fahrenheit",
    )

    # Map to internal format
    mapped_data = mapper.map_current_conditions(raw_data)
    timestamp_str = mapped_data["properties"]["timestamp"]

    assert timestamp_str is not None, "Timestamp should be present"

    # Parse the timestamp (should be in UTC)
    last_updated = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    assert isinstance(last_updated, datetime), "Last updated should be a datetime"
    assert last_updated.tzinfo is not None, "Timestamp should be timezone-aware (UTC)"

    # Last updated should be recent (within 7 days) and not in the future
    now_utc = datetime.now(UTC)
    age = now_utc - last_updated

    assert age.total_seconds() >= 0, "Last updated should not be in the future"
    assert age.total_seconds() < timedelta(days=7).total_seconds(), (
        f"Last updated {last_updated} is too old (age: {age})"
    )

    # Year sanity check (not epoch)
    assert last_updated.year > 2000, "Last updated year is invalid"

    time.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_openmeteo_forecast_contains_sunrise_sunset(openmeteo_client):
    """Test Open-Meteo forecast includes sunrise/sunset data in raw response."""
    # Fetch raw forecast data
    data = openmeteo_client.get_forecast(
        latitude=TEST_LOCATION.latitude,
        longitude=TEST_LOCATION.longitude,
        temperature_unit="fahrenheit",
        days=7,
    )

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

    # Parse ISO datetime strings (Open-Meteo with timezone=auto returns naive local times)
    sunrise_dt = datetime.fromisoformat(first_sunrise)
    sunset_dt = datetime.fromisoformat(first_sunset)

    # Should be naive datetimes in local time
    assert sunrise_dt.tzinfo is None, "Sunrise should be naive (local time)"
    assert sunset_dt.tzinfo is None, "Sunset should be naive (local time)"

    # Sunrise before sunset
    assert sunrise_dt < sunset_dt, "Sunrise should be before sunset"

    # Reasonable hours check
    assert 4 <= sunrise_dt.hour <= 9, f"Sunrise hour {sunrise_dt.hour} seems unreasonable"
    assert 16 <= sunset_dt.hour <= 20, f"Sunset hour {sunset_dt.hour} seems unreasonable"

    time.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_openmeteo_hourly_forecast_timezone_converted(openmeteo_client, mapper):
    """Test Open-Meteo hourly forecast timestamps are converted to UTC."""
    # Fetch raw hourly data
    raw_data = openmeteo_client.get_hourly_forecast(
        latitude=TEST_LOCATION.latitude,
        longitude=TEST_LOCATION.longitude,
        temperature_unit="fahrenheit",
        hours=48,
    )

    # Map to internal format
    mapped_data = mapper.map_hourly_forecast(raw_data)
    periods = mapped_data["properties"]["periods"]

    assert len(periods) > 0, "Hourly forecast should have periods"

    # Check first few periods have valid start times
    for i, period in enumerate(periods[:5]):
        start_time_str = period.get("startTime")
        if start_time_str:  # May be None if parsing failed
            # Parse the timestamp
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

            assert isinstance(start_time, datetime), f"Period {i} start_time should be datetime"

            # Should be timezone-aware (UTC)
            assert start_time.tzinfo is not None, f"Period {i} should be timezone-aware"

            # Check it's a recent hour (not epoch)
            assert start_time.year > 2000, f"Period {i} start_time year is invalid"

    time.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_openmeteo_client_fetches_all_data_types(openmeteo_client, mapper):
    """Test Open-Meteo client can fetch current, forecast, and hourly data."""
    # Fetch current weather
    current_raw = openmeteo_client.get_current_weather(
        latitude=TEST_LOCATION.latitude,
        longitude=TEST_LOCATION.longitude,
        temperature_unit="fahrenheit",
    )
    current_mapped = mapper.map_current_conditions(current_raw)

    # Fetch daily forecast
    forecast_raw = openmeteo_client.get_forecast(
        latitude=TEST_LOCATION.latitude,
        longitude=TEST_LOCATION.longitude,
        temperature_unit="fahrenheit",
        days=7,
    )
    forecast_mapped = mapper.map_forecast(forecast_raw)

    # Fetch hourly forecast
    hourly_raw = openmeteo_client.get_hourly_forecast(
        latitude=TEST_LOCATION.latitude,
        longitude=TEST_LOCATION.longitude,
        temperature_unit="fahrenheit",
        hours=48,
    )
    hourly_mapped = mapper.map_hourly_forecast(hourly_raw)

    # All three should return successfully
    assert current_mapped is not None, "Current conditions should be present"
    assert forecast_mapped is not None, "Forecast should be present"
    assert hourly_mapped is not None, "Hourly forecast should be present"

    # Verify current has sunrise/sunset
    assert current_mapped["properties"]["sunrise"] is not None, "Current should have sunrise"
    assert current_mapped["properties"]["sunset"] is not None, "Current should have sunset"

    # Verify forecast has periods
    assert len(forecast_mapped["properties"]["periods"]) > 0, "Forecast should have periods"

    # Verify hourly has periods
    assert len(hourly_mapped["properties"]["periods"]) > 0, "Hourly forecast should have periods"

    time.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_openmeteo_raw_response_timezone_field(openmeteo_client):
    """Test Open-Meteo API response includes timezone information."""
    data = openmeteo_client.get_current_weather(
        latitude=TEST_LOCATION.latitude,
        longitude=TEST_LOCATION.longitude,
        temperature_unit="fahrenheit",
    )

    # Check timezone field is present
    assert "timezone" in data, "Response should include timezone"
    assert "timezone_abbreviation" in data, "Response should include timezone abbreviation"
    assert "utc_offset_seconds" in data, "Response should include UTC offset"

    timezone = data["timezone"]
    assert isinstance(timezone, str), "Timezone should be a string"
    assert len(timezone) > 0, "Timezone should not be empty"

    # Should be an IANA timezone (e.g., "America/New_York")
    assert "/" in timezone or timezone == "GMT", (
        f"Timezone '{timezone}' should be IANA format or GMT"
    )

    # UTC offset should be an integer (seconds)
    utc_offset = data["utc_offset_seconds"]
    assert isinstance(utc_offset, int), "UTC offset should be an integer"

    time.sleep(DELAY_BETWEEN_REQUESTS)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_openmeteo_mapper_handles_sunrise_sunset(mapper):
    """Test Open-Meteo mapper correctly extracts sunrise/sunset from API response."""
    # Create a sample response matching Open-Meteo API structure with timezone=auto
    # (returns naive datetime strings in local time)
    sample_response = {
        "latitude": 39.9663,
        "longitude": -74.8103,
        "utc_offset_seconds": -18000,  # EST
        "timezone": "America/New_York",
        "current": {
            "time": "2025-11-11T12:00",  # Naive local time
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
            "sunrise": ["2025-11-11T06:30"],  # Naive local time
            "sunset": ["2025-11-11T17:15"],  # Naive local time
            "uv_index_max": [4.2],
        },
    }

    # Map with the actual mapper
    mapped_data = mapper.map_current_conditions(sample_response)
    props = mapped_data["properties"]

    # Verify sunrise/sunset were extracted
    assert props["sunrise"] is not None, "Mapper should extract sunrise"
    assert props["sunset"] is not None, "Mapper should extract sunset"

    # Parse the datetime strings
    sunrise = datetime.fromisoformat(props["sunrise"])
    sunset = datetime.fromisoformat(props["sunset"])

    # They should be naive datetimes (local time, NOT converted to UTC)
    assert sunrise.tzinfo is None, "Sunrise should be naive (local time)"
    assert sunset.tzinfo is None, "Sunset should be naive (local time)"

    # Verify reasonable values
    assert sunrise < sunset, "Sunrise should be before sunset"
    assert sunrise.year == 2025
    assert sunset.year == 2025
    assert sunrise.hour == 6
    assert sunset.hour == 17


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
def test_openmeteo_mapper_handles_missing_sunrise_sunset(mapper):
    """Test mapper gracefully handles missing sunrise/sunset data."""
    # Response without daily sunrise/sunset
    sample_response = {
        "latitude": 39.9663,
        "longitude": -74.8103,
        "utc_offset_seconds": -18000,
        "current": {
            "time": "2025-11-11T12:00",
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

    mapped_data = mapper.map_current_conditions(sample_response)
    props = mapped_data["properties"]

    # Should map successfully without sunrise/sunset
    assert mapped_data is not None
    assert props["temperature"]["value"] == 55.0
    assert props["sunrise"] is None
    assert props["sunset"] is None
