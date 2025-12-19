"""Integration tests for Open-Meteo environmental data provider."""

from __future__ import annotations

import pytest

from accessiweather.models import Location
from accessiweather.services.environmental_client import EnvironmentalDataClient
from tests.integration.conftest import (
    get_vcr_config,
    skip_if_cassette_missing,
)

try:
    import vcr

    HAS_VCR = True
except ImportError:
    HAS_VCR = False

# Test location: Lumberton, NJ
TEST_LOCATION = Location(name="Lumberton, New Jersey", latitude=39.9643, longitude=-74.8099)


@pytest.fixture
def env_client():
    """Create EnvironmentalDataClient for tests."""
    return EnvironmentalDataClient(timeout=30.0)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_fetch_air_quality_integration(env_client):
    """Test fetching air quality data from live API."""
    cassette_name = "environmental/test_fetch_air_quality.yaml"
    skip_if_cassette_missing(cassette_name)

    async def run_test():
        data = await env_client.fetch(
            TEST_LOCATION,
            include_air_quality=True,
            include_pollen=False,
            include_hourly_air_quality=False,
        )

        assert data is not None
        assert data.has_data()
        assert data.air_quality_index is not None
        assert isinstance(data.air_quality_index, (int, float))
        assert data.air_quality_category is not None
        assert isinstance(data.air_quality_category, str)
        assert "Open-Meteo Air Quality" in data.sources

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette("environmental/test_fetch_air_quality.yaml"):  # type: ignore[attr-defined]
            await run_test()
    else:
        await run_test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_fetch_pollen_integration(env_client):
    """Test fetching pollen data from live API."""
    cassette_name = "environmental/test_fetch_pollen.yaml"
    skip_if_cassette_missing(cassette_name)

    async def run_test():
        # We include air quality to ensure valid data is returned even if pollen is 0/None (winter)
        data = await env_client.fetch(
            TEST_LOCATION,
            include_air_quality=True,
            include_pollen=True,
            include_hourly_air_quality=False,
        )

        assert data is not None
        assert data.has_data()

        # If pollen data exists (in season), verify it
        if "Open-Meteo Pollen" in data.sources and data.pollen_index is not None:
            assert isinstance(data.pollen_index, (int, float))
            assert data.pollen_category is not None
            assert isinstance(data.pollen_category, str)

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette("environmental/test_fetch_pollen.yaml"):  # type: ignore[attr-defined]
            await run_test()
    else:
        await run_test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_fetch_hourly_air_quality_integration(env_client):
    """Test fetching hourly air quality data from live API."""
    cassette_name = "environmental/test_fetch_hourly_air_quality.yaml"
    skip_if_cassette_missing(cassette_name)

    async def run_test():
        hourly = await env_client.fetch_hourly_air_quality(TEST_LOCATION, hours=24)

        assert hourly is not None
        assert len(hourly) > 0

        first = hourly[0]
        assert "aqi" in first
        assert isinstance(first["aqi"], (int, float, type(None)))
        assert "timestamp" in first
        assert first["timestamp"].tzinfo is not None  # Should be aware

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette("environmental/test_fetch_hourly_air_quality.yaml"):  # type: ignore[attr-defined]
            await run_test()
    else:
        await run_test()
