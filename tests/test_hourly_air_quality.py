"""Tests for hourly air quality forecast functionality."""

from __future__ import annotations

from datetime import datetime

import pytest

from accessiweather.models import Location
from accessiweather.services.environmental_client import EnvironmentalDataClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fetch_hourly_air_quality_returns_forecast():
    """Test that hourly AQI forecast is fetched from Open-Meteo."""
    client = EnvironmentalDataClient()
    location = Location(name="New York", latitude=40.7128, longitude=-74.0060)

    result = await client.fetch_hourly_air_quality(location, hours=24)

    assert result is not None
    assert len(result) > 0
    assert len(result) <= 24

    # Check first entry structure
    first_entry = result[0]
    assert "timestamp" in first_entry
    assert "aqi" in first_entry
    assert isinstance(first_entry["timestamp"], datetime)
    assert isinstance(first_entry["aqi"], (int, float))
    assert first_entry["aqi"] >= 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_hourly_air_quality_includes_pollutants():
    """Test that hourly forecast includes individual pollutant data."""
    client = EnvironmentalDataClient()
    location = Location(name="Los Angeles", latitude=34.0522, longitude=-118.2437)

    result = await client.fetch_hourly_air_quality(location, hours=12)

    assert result is not None
    assert len(result) > 0

    # Check that pollutant data is included
    first_entry = result[0]
    assert "pm2_5" in first_entry or "pm10" in first_entry or "ozone" in first_entry


@pytest.mark.asyncio
@pytest.mark.unit
async def test_hourly_air_quality_handles_api_error():
    """Test that API errors are handled gracefully."""
    client = EnvironmentalDataClient()
    # Invalid coordinates
    location = Location(name="Invalid", latitude=999, longitude=999)

    result = await client.fetch_hourly_air_quality(location, hours=24)

    # Should return None or empty list on error
    assert result is None or result == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_hourly_air_quality_respects_hours_parameter():
    """Test that the hours parameter limits the forecast length."""
    client = EnvironmentalDataClient()
    location = Location(name="Chicago", latitude=41.8781, longitude=-87.6298)

    result = await client.fetch_hourly_air_quality(location, hours=6)

    assert result is not None
    assert len(result) <= 6


@pytest.mark.unit
def test_air_quality_category_from_aqi():
    """Test AQI value to category conversion."""
    client = EnvironmentalDataClient()

    assert client._air_quality_category(25) == "Good"
    assert client._air_quality_category(75) == "Moderate"
    assert client._air_quality_category(125) == "Unhealthy for Sensitive Groups"
    assert client._air_quality_category(175) == "Unhealthy"
    assert client._air_quality_category(225) == "Very Unhealthy"
    assert client._air_quality_category(350) == "Hazardous"
