"""Integration tests for Open-Meteo environmental data provider."""

from __future__ import annotations

import os

import pytest

from accessiweather.models import Location
from accessiweather.services.environmental_client import EnvironmentalDataClient

# Skip integration tests unless explicitly requested
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS", "0") == "1"
skip_reason = "Set RUN_INTEGRATION_TESTS=1 to run integration tests with real API calls"

# Test location: Lumberton, NJ
TEST_LOCATION = Location(name="Lumberton, New Jersey", latitude=39.9643, longitude=-74.8099)


@pytest.fixture
def env_client():
    """Create EnvironmentalDataClient for tests."""
    import inspect

    print(f"DEBUG: EnvironmentalDataClient file: {inspect.getfile(EnvironmentalDataClient)}")
    return EnvironmentalDataClient(timeout=30.0)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
async def test_fetch_air_quality_integration(env_client):
    """Test fetching air quality data from live API."""
    data = await env_client.fetch(
        TEST_LOCATION,
        include_air_quality=True,
        include_pollen=False,
        include_hourly_air_quality=False,
    )

    assert data is not None
    assert data.has_data()
    assert data.air_quality_index is not None
    assert data.air_quality_category is not None
    assert "Open-Meteo Air Quality" in data.sources


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
async def test_fetch_pollen_integration(env_client):
    """Test fetching pollen data from live API."""
    # We include air quality to ensure valid data is returned even if pollen is 0/None (winter)
    data = await env_client.fetch(
        TEST_LOCATION,
        include_air_quality=True,  # Changed to True
        include_pollen=True,
        include_hourly_air_quality=False,
    )

    assert data is not None

    # If pollen data exists (in season), verify it
    if "Open-Meteo Pollen" in data.sources and data.pollen_index is not None:
        assert data.pollen_category is not None


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
async def test_fetch_hourly_air_quality_integration(env_client):
    """Test fetching hourly air quality data from live API."""
    hourly = await env_client.fetch_hourly_air_quality(TEST_LOCATION, hours=24)

    assert hourly is not None
    assert len(hourly) > 0

    first = hourly[0]
    assert "aqi" in first
    assert "timestamp" in first
    assert first["timestamp"].tzinfo is not None  # Should be aware
