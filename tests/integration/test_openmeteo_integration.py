"""Integration tests for Open-Meteo weather provider API."""

from __future__ import annotations

from datetime import datetime

import pytest

from accessiweather.models import Location
from accessiweather.openmeteo_client import OpenMeteoApiClient
from accessiweather.openmeteo_mapper import OpenMeteoMapper
from tests.integration.conftest import (
    LIVE_WEATHER_TESTS,
    conditional_sleep,
    get_vcr_config,
    skip_if_cassette_missing,
)

try:
    import vcr

    HAS_VCR = True
except ImportError:
    HAS_VCR = False

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


def _run_with_cassette(cassette_name: str, test_fn):
    """Run a test function with VCR cassette or in live mode."""
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
def test_openmeteo_current_conditions_sunrise_sunset(openmeteo_client, mapper):
    """Test Open-Meteo current conditions returns valid sunrise/sunset times."""

    def run_test():
        raw_data = openmeteo_client.get_current_weather(
            latitude=TEST_LOCATION.latitude,
            longitude=TEST_LOCATION.longitude,
            temperature_unit="fahrenheit",
        )

        assert raw_data is not None, "Open-Meteo should return data"
        assert "daily" in raw_data, "Response should include daily data with sunrise/sunset"

        mapped_data = mapper.map_current_conditions(raw_data)

        props = mapped_data["properties"]
        sunrise_str = props["sunrise"]
        sunset_str = props["sunset"]

        assert sunrise_str is not None, "Sunrise time should be present"
        assert sunset_str is not None, "Sunset time should be present"

        sunrise = datetime.fromisoformat(sunrise_str)
        sunset = datetime.fromisoformat(sunset_str)

        assert sunrise.tzinfo is None, "Sunrise should be naive (local time)"
        assert sunset.tzinfo is None, "Sunset should be naive (local time)"

        # Contract-based assertions: sunrise before sunset, valid years
        assert sunrise < sunset, "Sunrise should occur before sunset"
        assert sunrise.year > 2000, f"Sunrise year {sunrise.year} is invalid"
        assert sunset.year > 2000, f"Sunset year {sunset.year} is invalid"

        # Relaxed hour checks for cassette replay (any reasonable hour)
        assert 0 <= sunrise.hour <= 12, f"Sunrise hour {sunrise.hour} should be AM"
        assert 12 <= sunset.hour <= 23, f"Sunset hour {sunset.hour} should be PM"

        conditional_sleep(DELAY_BETWEEN_REQUESTS)

    _run_with_cassette("openmeteo/test_current_sunrise_sunset.yaml", run_test)


@pytest.mark.integration
@pytest.mark.network
def test_openmeteo_forecast_contains_sunrise_sunset(openmeteo_client):
    """Test Open-Meteo forecast includes sunrise/sunset data in raw response."""

    def run_test():
        data = openmeteo_client.get_forecast(
            latitude=TEST_LOCATION.latitude,
            longitude=TEST_LOCATION.longitude,
            temperature_unit="fahrenheit",
            days=7,
        )

        assert "daily" in data, "Response should contain daily data"
        daily = data["daily"]

        assert "sunrise" in daily, "Daily data should contain sunrise"
        assert "sunset" in daily, "Daily data should contain sunset"
        assert "time" in daily, "Daily data should contain time (dates)"

        sunrise_list = daily["sunrise"]
        sunset_list = daily["sunset"]
        dates = daily["time"]

        assert len(sunrise_list) > 0, "Sunrise array should have data"
        assert len(sunset_list) > 0, "Sunset array should have data"
        assert len(dates) > 0, "Dates array should have data"
        assert len(sunrise_list) == len(sunset_list) == len(dates), (
            "Arrays should have equal length"
        )

        first_sunrise = sunrise_list[0]
        first_sunset = sunset_list[0]

        assert first_sunrise is not None, "First sunrise should not be None"
        assert first_sunset is not None, "First sunset should not be None"

        sunrise_dt = datetime.fromisoformat(first_sunrise)
        sunset_dt = datetime.fromisoformat(first_sunset)

        assert sunrise_dt.tzinfo is None, "Sunrise should be naive (local time)"
        assert sunset_dt.tzinfo is None, "Sunset should be naive (local time)"

        # Contract-based assertions
        assert sunrise_dt < sunset_dt, "Sunrise should be before sunset"
        assert sunrise_dt.year > 2000, f"Sunrise year {sunrise_dt.year} is invalid"
        assert sunset_dt.year > 2000, f"Sunset year {sunset_dt.year} is invalid"

        # Relaxed hour checks for cassette replay
        assert 0 <= sunrise_dt.hour <= 12, f"Sunrise hour {sunrise_dt.hour} should be AM"
        assert 12 <= sunset_dt.hour <= 23, f"Sunset hour {sunset_dt.hour} should be PM"

        conditional_sleep(DELAY_BETWEEN_REQUESTS)

    _run_with_cassette("openmeteo/test_forecast_sunrise_sunset.yaml", run_test)


@pytest.mark.integration
@pytest.mark.network
def test_openmeteo_hourly_forecast_timezone_converted(openmeteo_client, mapper):
    """Test Open-Meteo hourly forecast timestamps are converted to UTC."""

    def run_test():
        raw_data = openmeteo_client.get_hourly_forecast(
            latitude=TEST_LOCATION.latitude,
            longitude=TEST_LOCATION.longitude,
            temperature_unit="fahrenheit",
            hours=48,
        )

        mapped_data = mapper.map_hourly_forecast(raw_data)
        periods = mapped_data["properties"]["periods"]

        assert len(periods) > 0, "Hourly forecast should have periods"

        for i, period in enumerate(periods[:5]):
            start_time_str = period.get("startTime")
            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

                assert isinstance(start_time, datetime), f"Period {i} start_time should be datetime"
                assert start_time.tzinfo is not None, f"Period {i} should be timezone-aware"
                assert start_time.year > 2000, f"Period {i} start_time year is invalid"

        conditional_sleep(DELAY_BETWEEN_REQUESTS)

    _run_with_cassette("openmeteo/test_hourly_timezone.yaml", run_test)


@pytest.mark.integration
@pytest.mark.network
def test_openmeteo_client_fetches_all_data_types(openmeteo_client, mapper):
    """Test Open-Meteo client can fetch current, forecast, and hourly data."""

    def run_test():
        current_raw = openmeteo_client.get_current_weather(
            latitude=TEST_LOCATION.latitude,
            longitude=TEST_LOCATION.longitude,
            temperature_unit="fahrenheit",
        )
        current_mapped = mapper.map_current_conditions(current_raw)

        forecast_raw = openmeteo_client.get_forecast(
            latitude=TEST_LOCATION.latitude,
            longitude=TEST_LOCATION.longitude,
            temperature_unit="fahrenheit",
            days=7,
        )
        forecast_mapped = mapper.map_forecast(forecast_raw)

        hourly_raw = openmeteo_client.get_hourly_forecast(
            latitude=TEST_LOCATION.latitude,
            longitude=TEST_LOCATION.longitude,
            temperature_unit="fahrenheit",
            hours=48,
        )
        hourly_mapped = mapper.map_hourly_forecast(hourly_raw)

        assert current_mapped is not None, "Current conditions should be present"
        assert forecast_mapped is not None, "Forecast should be present"
        assert hourly_mapped is not None, "Hourly forecast should be present"

        assert current_mapped["properties"]["sunrise"] is not None, "Current should have sunrise"
        assert current_mapped["properties"]["sunset"] is not None, "Current should have sunset"
        assert len(forecast_mapped["properties"]["periods"]) > 0, "Forecast should have periods"
        assert len(hourly_mapped["properties"]["periods"]) > 0, (
            "Hourly forecast should have periods"
        )

        conditional_sleep(DELAY_BETWEEN_REQUESTS)

    _run_with_cassette("openmeteo/test_all_data_types.yaml", run_test)


@pytest.mark.integration
@pytest.mark.network
def test_openmeteo_raw_response_timezone_field(openmeteo_client):
    """Test Open-Meteo API response includes timezone information."""

    def run_test():
        data = openmeteo_client.get_current_weather(
            latitude=TEST_LOCATION.latitude,
            longitude=TEST_LOCATION.longitude,
            temperature_unit="fahrenheit",
        )

        assert "timezone" in data, "Response should include timezone"
        assert "timezone_abbreviation" in data, "Response should include timezone abbreviation"
        assert "utc_offset_seconds" in data, "Response should include UTC offset"

        timezone = data["timezone"]
        assert isinstance(timezone, str), "Timezone should be a string"
        assert len(timezone) > 0, "Timezone should not be empty"

        assert "/" in timezone or timezone == "GMT", (
            f"Timezone '{timezone}' should be IANA format or GMT"
        )

        utc_offset = data["utc_offset_seconds"]
        assert isinstance(utc_offset, int), "UTC offset should be an integer"

        conditional_sleep(DELAY_BETWEEN_REQUESTS)

    _run_with_cassette("openmeteo/test_timezone_field.yaml", run_test)


# Unit tests using sample data - no cassettes needed
@pytest.mark.integration
@pytest.mark.network
def test_openmeteo_mapper_handles_sunrise_sunset(mapper):
    """Test Open-Meteo mapper correctly extracts sunrise/sunset from API response."""
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

    mapped_data = mapper.map_current_conditions(sample_response)
    props = mapped_data["properties"]

    assert props["sunrise"] is not None, "Mapper should extract sunrise"
    assert props["sunset"] is not None, "Mapper should extract sunset"

    sunrise = datetime.fromisoformat(props["sunrise"])
    sunset = datetime.fromisoformat(props["sunset"])

    assert sunrise.tzinfo is None, "Sunrise should be naive (local time)"
    assert sunset.tzinfo is None, "Sunset should be naive (local time)"

    assert sunrise < sunset, "Sunrise should be before sunset"
    assert sunrise.year == 2025
    assert sunset.year == 2025
    assert sunrise.hour == 6
    assert sunset.hour == 17


@pytest.mark.integration
@pytest.mark.network
def test_openmeteo_mapper_handles_missing_sunrise_sunset(mapper):
    """Test mapper gracefully handles missing sunrise/sunset data."""
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

    assert mapped_data is not None
    assert props["temperature"]["value"] == 55.0
    assert props["sunrise"] is None
    assert props["sunset"] is None
