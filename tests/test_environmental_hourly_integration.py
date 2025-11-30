"""Tests for hourly air quality integration with EnvironmentalConditions."""

from __future__ import annotations

import pytest

from accessiweather.models import Location
from accessiweather.services.environmental_client import EnvironmentalDataClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fetch_includes_hourly_air_quality():
    """Test that main fetch method includes hourly air quality data."""
    client = EnvironmentalDataClient()
    location = Location(name="Denver", latitude=39.7392, longitude=-104.9903)

    result = await client.fetch(
        location,
        include_air_quality=True,
        include_pollen=False,
        include_hourly_air_quality=True,
        hourly_hours=24,
    )

    assert result is not None
    assert len(result.hourly_air_quality) > 0
    assert len(result.hourly_air_quality) <= 24

    # Check structure
    first_hour = result.hourly_air_quality[0]
    assert first_hour.timestamp is not None
    assert first_hour.aqi >= 0
    assert first_hour.category in [
        "Good",
        "Moderate",
        "Unhealthy for Sensitive Groups",
        "Unhealthy",
        "Very Unhealthy",
        "Hazardous",
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fetch_can_disable_hourly_air_quality():
    """Test that hourly air quality can be disabled."""
    client = EnvironmentalDataClient()
    location = Location(name="Seattle", latitude=47.6062, longitude=-122.3321)

    result = await client.fetch(
        location,
        include_air_quality=True,
        include_pollen=False,
        include_hourly_air_quality=False,
    )

    assert result is not None
    assert len(result.hourly_air_quality) == 0
    # Should still have current air quality
    assert result.air_quality_index is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hourly_air_quality_includes_pollutant_details():
    """Test that hourly forecast includes individual pollutant measurements."""
    client = EnvironmentalDataClient()
    location = Location(name="Phoenix", latitude=33.4484, longitude=-112.0740)

    result = await client.fetch(
        location,
        include_air_quality=False,
        include_pollen=False,
        include_hourly_air_quality=True,
        hourly_hours=12,
    )

    assert result is not None
    assert len(result.hourly_air_quality) > 0

    # Check that at least some pollutant data exists
    has_pollutants = any(
        hour.pm2_5 is not None
        or hour.pm10 is not None
        or hour.ozone is not None
        or hour.nitrogen_dioxide is not None
        for hour in result.hourly_air_quality
    )
    assert has_pollutants


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hourly_air_quality_timestamps_are_ordered():
    """Test that hourly timestamps are in chronological order."""
    client = EnvironmentalDataClient()
    location = Location(name="Boston", latitude=42.3601, longitude=-71.0589)

    result = await client.fetch(
        location,
        include_air_quality=False,
        include_pollen=False,
        include_hourly_air_quality=True,
        hourly_hours=24,
    )

    assert result is not None
    assert len(result.hourly_air_quality) > 1

    # Verify timestamps are in order
    for i in range(len(result.hourly_air_quality) - 1):
        current = result.hourly_air_quality[i].timestamp
        next_hour = result.hourly_air_quality[i + 1].timestamp
        assert current < next_hour
