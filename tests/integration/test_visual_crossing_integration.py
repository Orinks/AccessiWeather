"""Integration tests for Visual Crossing weather provider API."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

from accessiweather.models import Location
from accessiweather.visual_crossing_client import VisualCrossingClient

# Skip integration tests unless explicitly requested
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS", "0") == "1"
skip_reason = "Set RUN_INTEGRATION_TESTS=1 to run integration tests with real API calls"

# Test location: Lumberton, NJ
TEST_LOCATION = Location(name="Lumberton, New Jersey", latitude=39.9643, longitude=-74.8099)

# Visual Crossing requires an API key
VC_API_KEY = os.getenv("VISUAL_CROSSING_API_KEY")
skip_no_key = "Set VISUAL_CROSSING_API_KEY environment variable to run Visual Crossing tests"


@pytest.fixture
def vc_client():
    """Create Visual Crossing client for tests."""
    if not VC_API_KEY:
        pytest.skip(skip_no_key)
    client = VisualCrossingClient(api_key=VC_API_KEY)
    client.timeout = 30.0  # Increase timeout for integration tests
    return client


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
async def test_visual_crossing_get_history_yesterday(vc_client):
    """Test fetching yesterday's weather data from Visual Crossing."""
    # Get yesterday's date
    yesterday = datetime.now() - timedelta(days=1)

    # Fetch history
    history = await vc_client.get_history(TEST_LOCATION, yesterday, yesterday)

    # Verify we got data back
    assert history is not None, "History should not be None"
    assert history.periods is not None, "History periods should not be None"
    assert len(history.periods) > 0, "Should have at least one period"

    # Verify the period has temperature data
    period = history.periods[0]
    assert period.temperature is not None, "Period should have temperature"
    assert period.temperature_unit is not None, "Period should have temperature unit"

    # Verify reasonable temperature range (sanity check)
    assert -100 <= period.temperature <= 150, f"Temperature {period.temperature} seems unreasonable"


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
async def test_visual_crossing_get_history_date_range(vc_client):
    """Test fetching a date range of historical weather data."""
    # Get last 3 days
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=2)

    # Fetch history
    history = await vc_client.get_history(TEST_LOCATION, start_date, end_date)

    # Verify we got data back
    assert history is not None, "History should not be None"
    assert history.periods is not None, "History periods should not be None"

    # Should have 3 days of data
    assert len(history.periods) >= 1, "Should have at least one period"
    assert len(history.periods) <= 3, "Should have at most 3 periods"

    # Verify each period has required data
    for period in history.periods:
        assert period.temperature is not None, f"Period {period.name} should have temperature"


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
async def test_visual_crossing_history_has_required_fields(vc_client):
    """Test that historical data includes all required fields for trend comparison."""
    yesterday = datetime.now() - timedelta(days=1)

    history = await vc_client.get_history(TEST_LOCATION, yesterday, yesterday)

    assert history is not None
    assert len(history.periods) > 0

    period = history.periods[0]

    # Required for daily trend comparison
    assert period.temperature is not None, "Must have temperature"
    assert period.temperature_unit is not None, "Must have temperature unit"

    # Nice to have for display
    assert period.name is not None or period.detailed_forecast is not None, (
        "Should have some description"
    )


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
async def test_visual_crossing_history_invalid_location(vc_client):
    """Test that invalid coordinates are handled gracefully."""
    invalid_location = Location(name="Invalid", latitude=999, longitude=999)
    yesterday = datetime.now() - timedelta(days=1)

    # Should raise an error or return None
    try:
        history = await vc_client.get_history(invalid_location, yesterday, yesterday)
        # If it doesn't raise, it should return None or empty
        if history is not None:
            assert len(history.periods) == 0, "Invalid location should return no periods"
    except Exception:
        # Expected - invalid coordinates should fail
        pass


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
async def test_visual_crossing_history_future_date_handling(vc_client):
    """Test that requesting future dates is handled appropriately."""
    # Try to get tomorrow's "history" (should fail or return empty)
    tomorrow = datetime.now() + timedelta(days=1)

    try:
        history = await vc_client.get_history(TEST_LOCATION, tomorrow, tomorrow)
        # If it doesn't raise, should return None or empty
        if history is not None:
            # Future dates might return empty or current data
            assert isinstance(history.periods, list), "Should return a list"
    except Exception:
        # Expected - future dates might not be supported
        pass


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
async def test_visual_crossing_history_temperature_units(vc_client):
    """Test that temperature units are correctly set in historical data."""
    yesterday = datetime.now() - timedelta(days=1)

    history = await vc_client.get_history(TEST_LOCATION, yesterday, yesterday)

    assert history is not None
    assert len(history.periods) > 0

    period = history.periods[0]

    # Visual Crossing uses US units by default
    assert period.temperature_unit in ["F", "C"], (
        f"Temperature unit should be F or C, got {period.temperature_unit}"
    )

    # For US location with default settings, should be Fahrenheit
    if TEST_LOCATION.latitude > 24 and TEST_LOCATION.latitude < 50:  # Continental US
        assert period.temperature_unit == "F", "US location should default to Fahrenheit"
