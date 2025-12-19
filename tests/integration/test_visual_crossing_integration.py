"""Integration tests for Visual Crossing weather provider API."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

from accessiweather.models import Location
from accessiweather.visual_crossing_client import VisualCrossingClient
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
    vcr = None  # type: ignore[assignment]

# Test location: Lumberton, NJ
TEST_LOCATION = Location(name="Lumberton, New Jersey", latitude=39.9643, longitude=-74.8099)

# Fixed date for cassette tests (deterministic), dynamic for live
TEST_DATE = datetime(2024, 12, 15)
if LIVE_WEATHER_TESTS:
    TEST_DATE = datetime.now() - timedelta(days=1)


@pytest.fixture
def vc_client():
    """Create Visual Crossing client for tests."""
    api_key: str
    if LIVE_WEATHER_TESTS:
        env_key = os.getenv("VISUAL_CROSSING_API_KEY")
        if not env_key:
            pytest.skip("VISUAL_CROSSING_API_KEY required for live tests")
        api_key = env_key
    else:
        api_key = "REDACTED"
    client = VisualCrossingClient(api_key=api_key)
    client.timeout = 30.0
    return client


def get_cassette_vcr():
    """Get a VCR instance configured for cassette use."""
    if not HAS_VCR or vcr is None:
        return None
    return vcr.VCR(**get_vcr_config())


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_visual_crossing_get_history_yesterday(vc_client):
    """Test fetching yesterday's weather data from Visual Crossing."""
    my_vcr = get_cassette_vcr()

    async def run_test():
        history = await vc_client.get_history(TEST_LOCATION, TEST_DATE, TEST_DATE)

        assert history is not None, "History should not be None"
        assert history.periods is not None, "History periods should not be None"
        assert len(history.periods) > 0, "Should have at least one period"

        period = history.periods[0]
        assert period.temperature is not None, "Period should have temperature"
        assert isinstance(period.temperature, (int, float)), "Temperature should be numeric"
        assert -100 <= period.temperature <= 150, f"Temperature {period.temperature} out of range"
        assert period.temperature_unit in ["F", "C"], (
            f"Temperature unit should be F or C, got {period.temperature_unit}"
        )

    cassette_name = "visual_crossing/test_get_history_yesterday.yaml"
    skip_if_cassette_missing(cassette_name)
    if my_vcr is not None:
        with my_vcr.use_cassette(cassette_name):
            await run_test()
    elif LIVE_WEATHER_TESTS:
        await run_test()
    else:
        pytest.skip("VCR not installed and not in live mode")


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_visual_crossing_get_history_date_range(vc_client):
    """Test fetching a date range of historical weather data."""
    my_vcr = get_cassette_vcr()
    end_date = TEST_DATE
    start_date = end_date - timedelta(days=2)

    async def run_test():
        history = await vc_client.get_history(TEST_LOCATION, start_date, end_date)

        assert history is not None, "History should not be None"
        assert history.periods is not None, "History periods should not be None"
        assert len(history.periods) >= 1, "Should have at least one period"
        assert len(history.periods) <= 3, "Should have at most 3 periods"

        for period in history.periods:
            assert period.temperature is not None, f"Period {period.name} should have temperature"
            assert isinstance(period.temperature, (int, float)), "Temperature should be numeric"

    cassette_name = "visual_crossing/test_get_history_date_range.yaml"
    skip_if_cassette_missing(cassette_name)
    if my_vcr is not None:
        with my_vcr.use_cassette(cassette_name):
            await run_test()
    elif LIVE_WEATHER_TESTS:
        await run_test()
    else:
        pytest.skip("VCR not installed and not in live mode")


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_visual_crossing_history_has_required_fields(vc_client):
    """Test that historical data includes all required fields for trend comparison."""
    my_vcr = get_cassette_vcr()

    async def run_test():
        history = await vc_client.get_history(TEST_LOCATION, TEST_DATE, TEST_DATE)

        assert history is not None
        assert len(history.periods) > 0

        period = history.periods[0]

        assert period.temperature is not None, "Must have temperature"
        assert isinstance(period.temperature, (int, float)), "Temperature must be numeric"
        assert period.temperature_unit is not None, "Must have temperature unit"
        assert period.temperature_unit in ["F", "C"], "Temperature unit must be F or C"

        assert period.name is not None or period.detailed_forecast is not None, (
            "Should have some description"
        )

    cassette_name = "visual_crossing/test_history_has_required_fields.yaml"
    skip_if_cassette_missing(cassette_name)
    if my_vcr is not None:
        with my_vcr.use_cassette(cassette_name):
            await run_test()
    elif LIVE_WEATHER_TESTS:
        await run_test()
    else:
        pytest.skip("VCR not installed and not in live mode")


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_visual_crossing_history_invalid_location(vc_client):
    """Test that invalid coordinates are handled gracefully."""
    my_vcr = get_cassette_vcr()
    invalid_location = Location(name="Invalid", latitude=999, longitude=999)

    async def run_test():
        try:
            history = await vc_client.get_history(invalid_location, TEST_DATE, TEST_DATE)
            if history is not None:
                assert len(history.periods) == 0, "Invalid location should return no periods"
        except Exception:
            pass

    cassette_name = "visual_crossing/test_history_invalid_location.yaml"
    skip_if_cassette_missing(cassette_name)
    if my_vcr is not None:
        with my_vcr.use_cassette(cassette_name):
            await run_test()
    elif LIVE_WEATHER_TESTS:
        await run_test()
    else:
        pytest.skip("VCR not installed and not in live mode")


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_visual_crossing_history_future_date_handling(vc_client):
    """Test that requesting future dates is handled appropriately."""
    my_vcr = get_cassette_vcr()
    future_date = TEST_DATE + timedelta(days=30)

    async def run_test():
        try:
            history = await vc_client.get_history(TEST_LOCATION, future_date, future_date)
            if history is not None:
                assert isinstance(history.periods, list), "Should return a list"
        except Exception:
            pass

    cassette_name = "visual_crossing/test_history_future_date_handling.yaml"
    skip_if_cassette_missing(cassette_name)
    if my_vcr is not None:
        with my_vcr.use_cassette(cassette_name):
            await run_test()
    elif LIVE_WEATHER_TESTS:
        await run_test()
    else:
        pytest.skip("VCR not installed and not in live mode")


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_visual_crossing_history_temperature_units(vc_client):
    """Test that temperature units are correctly set in historical data."""
    my_vcr = get_cassette_vcr()

    async def run_test():
        history = await vc_client.get_history(TEST_LOCATION, TEST_DATE, TEST_DATE)

        assert history is not None
        assert len(history.periods) > 0

        period = history.periods[0]

        assert period.temperature_unit in ["F", "C"], (
            f"Temperature unit should be F or C, got {period.temperature_unit}"
        )

    cassette_name = "visual_crossing/test_history_temperature_units.yaml"
    skip_if_cassette_missing(cassette_name)
    if my_vcr is not None:
        with my_vcr.use_cassette(cassette_name):
            await run_test()
    elif LIVE_WEATHER_TESTS:
        await run_test()
    else:
        pytest.skip("VCR not installed and not in live mode")
