"""Tests for request deduplication in WeatherClient."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest

from accessiweather.cache import WeatherDataCache
from accessiweather.models import CurrentConditions, Location, WeatherData
from accessiweather.models.config import AppSettings
from accessiweather.weather_client import WeatherClient

if TYPE_CHECKING:
    pass


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings():
    """Create test app settings."""
    return AppSettings(
        temperature_unit="F",
        data_source="auto",
    )


@pytest.fixture
async def weather_client(temp_cache_dir: Path, test_settings: AppSettings):
    """Create a WeatherClient for testing."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=180)
    client = WeatherClient(settings=test_settings, offline_cache=cache)
    yield client
    # Cleanup
    await client.close()


@pytest.fixture
def sample_location() -> Location:
    """Create a sample location for testing."""
    return Location(name="Test City", latitude=40.7128, longitude=-74.0060)


@pytest.fixture
def sample_weather_data(sample_location: Location) -> WeatherData:
    """Create sample weather data for testing."""
    return WeatherData(
        location=sample_location,
        last_updated=datetime.now(),
        current=CurrentConditions(
            temperature=72.0,
            condition="Partly Cloudy",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
        ),
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_concurrent_requests_deduplicated(
    weather_client: WeatherClient,
    sample_location: Location,
    sample_weather_data: WeatherData,
) -> None:
    """Test that concurrent requests for the same location are deduplicated."""
    # Mock the actual fetch to track call count
    fetch_count = 0

    async def mock_fetch(*args, **kwargs):
        nonlocal fetch_count
        fetch_count += 1
        await asyncio.sleep(0.1)  # Simulate API delay
        return sample_weather_data

    with patch.object(
        weather_client, "_do_fetch_weather_data", side_effect=mock_fetch
    ) as mock_do_fetch:
        # Launch 5 concurrent requests for the same location
        tasks = [
            asyncio.create_task(weather_client.get_weather_data(sample_location)) for _ in range(5)
        ]

        # Wait for all requests to complete
        results = await asyncio.gather(*tasks)

        # All results should be identical
        assert len(results) == 5
        assert all(r.location == sample_location for r in results)

        # But the actual fetch should only happen once (deduplication)
        assert fetch_count == 1
        assert mock_do_fetch.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_sequential_requests_not_deduplicated(
    weather_client: WeatherClient,
    sample_location: Location,
    sample_weather_data: WeatherData,
) -> None:
    """Test that sequential requests are not deduplicated."""
    fetch_count = 0

    async def mock_fetch(*args, **kwargs):
        nonlocal fetch_count
        fetch_count += 1
        return sample_weather_data

    with patch.object(
        weather_client, "_do_fetch_weather_data", side_effect=mock_fetch
    ) as mock_do_fetch:
        # Make 3 sequential requests
        for _ in range(3):
            await weather_client.get_weather_data(sample_location)

        # Each sequential request should result in a new fetch
        assert fetch_count == 3
        assert mock_do_fetch.call_count == 3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_different_locations_not_deduplicated(
    weather_client: WeatherClient, sample_weather_data: WeatherData
) -> None:
    """Test that requests for different locations are not deduplicated."""
    location1 = Location(name="City A", latitude=40.0, longitude=-74.0)
    location2 = Location(name="City B", latitude=41.0, longitude=-73.0)

    fetch_count = 0

    async def mock_fetch(*args, **kwargs):
        nonlocal fetch_count
        fetch_count += 1
        await asyncio.sleep(0.05)
        return sample_weather_data

    with patch.object(
        weather_client, "_do_fetch_weather_data", side_effect=mock_fetch
    ) as mock_do_fetch:
        # Launch concurrent requests for different locations
        tasks = [
            asyncio.create_task(weather_client.get_weather_data(location1)),
            asyncio.create_task(weather_client.get_weather_data(location2)),
        ]

        results = await asyncio.gather(*tasks)

        # Should get results for both locations
        assert len(results) == 2

        # Should fetch twice (once per location)
        assert fetch_count == 2
        assert mock_do_fetch.call_count == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_force_refresh_bypasses_deduplication(
    weather_client: WeatherClient,
    sample_location: Location,
    sample_weather_data: WeatherData,
) -> None:
    """Test that force_refresh bypasses deduplication."""
    fetch_count = 0

    async def mock_fetch(*args, **kwargs):
        nonlocal fetch_count
        fetch_count += 1
        await asyncio.sleep(0.05)
        return sample_weather_data

    with patch.object(
        weather_client, "_do_fetch_weather_data", side_effect=mock_fetch
    ) as mock_do_fetch:
        # Start a normal request
        task1 = asyncio.create_task(weather_client.get_weather_data(sample_location))

        # While first is in-flight, start a force_refresh request
        await asyncio.sleep(0.01)  # Let first request start
        task2 = asyncio.create_task(
            weather_client.get_weather_data(sample_location, force_refresh=True)
        )

        results = await asyncio.gather(task1, task2)

        # Should get both results
        assert len(results) == 2

        # Should fetch twice (force_refresh bypasses deduplication)
        assert fetch_count == 2
        assert mock_do_fetch.call_count == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_failed_request_cleanup(
    weather_client: WeatherClient,
    sample_location: Location,
) -> None:
    """Test that failed requests are cleaned up from in-flight tracking."""
    call_count = 0

    async def mock_fetch_fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        if call_count == 1:
            raise RuntimeError("API failure")
        # Second call succeeds
        return WeatherData(location=sample_location, last_updated=datetime.now())

    with patch.object(weather_client, "_do_fetch_weather_data", side_effect=mock_fetch_fail):
        # First request should fail
        with pytest.raises(RuntimeError):
            await weather_client.get_weather_data(sample_location)

        # Location key should be cleaned up after failure
        location_key = weather_client._location_key(sample_location)
        assert location_key not in weather_client._in_flight_requests

        # Second request should succeed (retry)
        result = await weather_client.get_weather_data(sample_location)
        assert result is not None
        assert result.location == sample_location

        # Should have been called twice (first fail, second success)
        assert call_count == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_location_key_uniqueness(weather_client: WeatherClient) -> None:
    """Test that location keys are unique and consistent."""
    # Same location should produce same key
    loc1a = Location(name="City", latitude=40.1234, longitude=-74.5678)
    loc1b = Location(name="City", latitude=40.1234, longitude=-74.5678)

    key1a = weather_client._location_key(loc1a)
    key1b = weather_client._location_key(loc1b)
    assert key1a == key1b

    # Different coordinates should produce different keys
    loc2 = Location(name="City", latitude=40.1235, longitude=-74.5678)
    key2 = weather_client._location_key(loc2)
    assert key1a != key2

    # Different names should produce different keys
    loc3 = Location(name="Other City", latitude=40.1234, longitude=-74.5678)
    key3 = weather_client._location_key(loc3)
    assert key1a != key3  # Different names = different keys


@pytest.mark.asyncio
@pytest.mark.unit
async def test_concurrent_requests_with_cache_hit(
    weather_client: WeatherClient,
    sample_location: Location,
    sample_weather_data: WeatherData,
) -> None:
    """Test that concurrent requests still fetch new data even with cached data."""
    # Mock cache to return fresh data
    if weather_client.offline_cache:
        weather_client.offline_cache.load = Mock(return_value=sample_weather_data)
        sample_weather_data.stale = False

        fetch_mock = AsyncMock(return_value=sample_weather_data)

        with patch.object(weather_client, "_do_fetch_weather_data", side_effect=fetch_mock):
            # Launch concurrent requests with cache enabled
            tasks = [
                asyncio.create_task(weather_client.get_weather_data(sample_location))
                for _ in range(3)
            ]

            results = await asyncio.gather(*tasks)

            # All should return data
            assert len(results) == 3

            # Fetch should be called once (deduplication of concurrent requests)
            assert fetch_mock.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deduplication_with_second_request_joining_inflight(
    weather_client: WeatherClient,
    sample_location: Location,
    sample_weather_data: WeatherData,
) -> None:
    """Test that second request joins in-flight request instead of creating new one."""
    fetch_started = asyncio.Event()
    fetch_can_complete = asyncio.Event()

    async def mock_fetch(*args, **kwargs):
        fetch_started.set()
        await fetch_can_complete.wait()
        return sample_weather_data

    with patch.object(weather_client, "_do_fetch_weather_data", side_effect=mock_fetch):
        # Start first request
        task1 = asyncio.create_task(weather_client.get_weather_data(sample_location))

        # Wait for fetch to start
        await fetch_started.wait()

        # Verify request is tracked
        location_key = weather_client._location_key(sample_location)
        assert location_key in weather_client._in_flight_requests

        # Start second request (should join in-flight)
        task2 = asyncio.create_task(weather_client.get_weather_data(sample_location))

        # Small delay to let second request check in-flight
        await asyncio.sleep(0.01)

        # Allow fetch to complete
        fetch_can_complete.set()

        # Both should complete successfully
        result1, result2 = await asyncio.gather(task1, task2)

        assert result1.location == sample_location
        assert result2.location == sample_location

        # In-flight should be cleaned up
        assert location_key not in weather_client._in_flight_requests
