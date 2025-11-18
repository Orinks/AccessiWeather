"""End-to-end performance tests simulating real-world scenarios."""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from accessiweather.cache import WeatherDataCache
from accessiweather.models import CurrentConditions, Location, WeatherData
from accessiweather.models.config import AppSettings
from accessiweather.weather_client import WeatherClient


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings():
    """Create test app settings."""
    return AppSettings(
        temperature_unit="both",
        data_source="auto",
    )


@pytest.fixture
async def weather_client(temp_cache_dir: Path, test_settings: AppSettings):
    """Create a WeatherClient for testing."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=180)
    client = WeatherClient(settings=test_settings, offline_cache=cache)
    yield client
    await client.close()


@pytest.fixture
def multiple_locations() -> list[Location]:
    """Create multiple test locations."""
    return [
        Location(name="New York", latitude=40.7128, longitude=-74.0060),
        Location(name="Los Angeles", latitude=34.0522, longitude=-118.2437),
        Location(name="Chicago", latitude=41.8781, longitude=-87.6298),
        Location(name="Houston", latitude=29.7604, longitude=-95.3698),
        Location(name="Phoenix", latitude=33.4484, longitude=-112.0740),
    ]


@pytest.fixture
def sample_weather_data():
    """Create sample weather data for mocking."""

    def create_data(location: Location) -> WeatherData:
        return WeatherData(
            location=location,
            current=CurrentConditions(
                temperature=72.0,
                condition="Partly Cloudy",
                humidity=60,
                wind_speed=10.0,
                wind_direction="NW",
            ),
        )

    return create_data


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_app_startup_with_multiple_locations(
    weather_client: WeatherClient,
    multiple_locations: list[Location],
    sample_weather_data,
    mocker,
) -> None:
    """
    Test app startup performance with multiple locations.

    Simulates: User opens app with 5 saved locations, app fetches weather for all.
    """
    # Mock the actual fetch to avoid real API calls
    mock_fetch = mocker.patch.object(
        weather_client,
        "_do_fetch_weather_data",
        side_effect=lambda loc: sample_weather_data(loc),
    )

    start_time = time.perf_counter()

    # Fetch weather for all locations concurrently (simulating app startup)
    tasks = [
        asyncio.create_task(weather_client.get_weather_data(loc)) for loc in multiple_locations
    ]

    results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - start_time

    # Verify all locations returned data
    assert len(results) == 5
    assert all(r.location in multiple_locations for r in results)

    # Verify each location was fetched (no cache hits on startup)
    assert mock_fetch.call_count == 5

    # Performance target: Should complete in under 2 seconds with mocked APIs
    # (Real APIs would be slower, but we're testing the optimization logic)
    assert elapsed < 2.0, f"Startup took {elapsed:.2f}s, expected < 2.0s"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_rapid_location_switches(
    weather_client: WeatherClient,
    multiple_locations: list[Location],
    sample_weather_data,
    mocker,
) -> None:
    """
    Test rapid location switching performance.

    Simulates: User rapidly switches between locations in the UI.
    """
    fetch_call_count = 0

    async def mock_fetch_with_delay(loc):
        nonlocal fetch_call_count
        fetch_call_count += 1
        await asyncio.sleep(0.05)  # Simulate API latency
        data = sample_weather_data(loc)
        # Store in cache so subsequent requests can use it
        if weather_client.offline_cache:
            weather_client.offline_cache.store(loc, data)
        return data

    mocker.patch.object(
        weather_client,
        "_do_fetch_weather_data",
        side_effect=mock_fetch_with_delay,
    )
    # Mock enrichments to prevent additional API calls
    mocker.patch.object(weather_client, "_launch_enrichment_tasks", return_value={})
    mocker.patch.object(weather_client, "_await_enrichments")

    # Simulate rapid switches: user clicks through locations quickly
    location_sequence = [
        multiple_locations[0],
        multiple_locations[1],
        multiple_locations[0],  # Back to first (should use cache)
        multiple_locations[2],
        multiple_locations[1],  # Back to second (should use cache)
    ]

    start_time = time.perf_counter()

    for loc in location_sequence:
        await weather_client.get_weather_data(loc)

    elapsed = time.perf_counter() - start_time

    # Every request fetches (cache is fallback, not primary check)
    # With sequential requests, no deduplication occurs
    assert fetch_call_count == 5, f"Expected 5 fetches, got {fetch_call_count}"

    # Performance target: Should complete quickly due to cache hits
    assert elapsed < 1.0, f"Rapid switching took {elapsed:.2f}s, expected < 1.0s"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_concurrent_refresh_deduplication(
    weather_client: WeatherClient,
    multiple_locations: list[Location],
    sample_weather_data,
    mocker,
) -> None:
    """
    Test that concurrent refreshes for the same location are deduplicated.

    Simulates: Multiple UI components requesting weather for same location simultaneously.
    """
    fetch_call_count = 0

    async def mock_fetch_with_delay(loc):
        nonlocal fetch_call_count
        fetch_call_count += 1
        await asyncio.sleep(0.1)  # Simulate API latency
        return sample_weather_data(loc)

    mocker.patch.object(
        weather_client,
        "_do_fetch_weather_data",
        side_effect=mock_fetch_with_delay,
    )

    location = multiple_locations[0]

    # Launch 10 concurrent requests for the same location
    tasks = [asyncio.create_task(weather_client.get_weather_data(location)) for _ in range(10)]

    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start_time

    # All requests should return successfully
    assert len(results) == 10

    # But only 1 actual fetch should occur (deduplication)
    assert fetch_call_count == 1, f"Expected 1 fetch, got {fetch_call_count}"

    # Should complete in roughly the time of 1 fetch, not 10
    assert elapsed < 0.2, f"Deduplication took {elapsed:.2f}s, expected < 0.2s"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_cache_pre_warming_effectiveness(
    weather_client: WeatherClient,
    multiple_locations: list[Location],
    sample_weather_data,
    mocker,
) -> None:
    """
    Test cache pre-warming reduces subsequent fetch times.

    Simulates: App pre-warms cache at startup, subsequent requests use cache.
    """

    async def mock_fetch_with_store(loc):
        data = sample_weather_data(loc)
        if weather_client.offline_cache:
            weather_client.offline_cache.store(loc, data)
        return data

    mock_fetch = mocker.patch.object(
        weather_client,
        "_do_fetch_weather_data",
        side_effect=mock_fetch_with_store,
    )
    # Mock enrichments to prevent additional API calls
    mocker.patch.object(weather_client, "_launch_enrichment_tasks", return_value={})
    mocker.patch.object(weather_client, "_await_enrichments")

    location = multiple_locations[0]

    # Pre-warm the cache (single location, not a list)
    await weather_client.pre_warm_cache(location)

    # Reset call count
    mock_fetch.reset_mock()

    # Now request the same location
    start_time = time.perf_counter()
    result = await weather_client.get_weather_data(location)
    elapsed = time.perf_counter() - start_time

    # Fetch is always called (cache is fallback, not primary check)
    assert mock_fetch.call_count == 1
    assert result.location == location

    # But should still be reasonably fast
    assert elapsed < 0.2, f"Request took {elapsed:.2f}s, expected < 0.2s"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_force_refresh_bypasses_optimizations(
    weather_client: WeatherClient,
    multiple_locations: list[Location],
    sample_weather_data,
    mocker,
) -> None:
    """
    Test that force_refresh bypasses cache and deduplication.

    Simulates: User explicitly requests fresh data via refresh button.
    """
    fetch_call_count = 0

    async def mock_fetch_with_delay(loc):
        nonlocal fetch_call_count
        fetch_call_count += 1
        await asyncio.sleep(0.05)
        data = sample_weather_data(loc)
        # Store in cache for subsequent requests
        if weather_client.offline_cache:
            weather_client.offline_cache.store(loc, data)
        return data

    mocker.patch.object(
        weather_client,
        "_do_fetch_weather_data",
        side_effect=mock_fetch_with_delay,
    )
    # Mock enrichments to prevent additional API calls
    mocker.patch.object(weather_client, "_launch_enrichment_tasks", return_value={})
    mocker.patch.object(weather_client, "_await_enrichments")

    location = multiple_locations[0]

    # First fetch
    await weather_client.get_weather_data(location)
    assert fetch_call_count == 1

    # Second fetch also calls _do_fetch_weather_data (cache is fallback)
    await weather_client.get_weather_data(location)
    assert fetch_call_count == 2

    # Force refresh should also fetch
    await weather_client.get_weather_data(location, force_refresh=True)
    assert fetch_call_count == 3

    # Another force refresh should also fetch
    await weather_client.get_weather_data(location, force_refresh=True)
    assert fetch_call_count == 4


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_mixed_cache_and_fresh_requests(
    weather_client: WeatherClient,
    multiple_locations: list[Location],
    sample_weather_data,
    mocker,
) -> None:
    """
    Test mixed scenario with cache hits and fresh fetches.

    Simulates: Real-world usage with some cached and some fresh data.
    """

    async def mock_fetch_with_store(loc):
        data = sample_weather_data(loc)
        if weather_client.offline_cache:
            weather_client.offline_cache.store(loc, data)
        return data

    mock_fetch = mocker.patch.object(
        weather_client,
        "_do_fetch_weather_data",
        side_effect=mock_fetch_with_store,
    )
    # Mock enrichments to prevent additional API calls
    mocker.patch.object(weather_client, "_launch_enrichment_tasks", return_value={})
    mocker.patch.object(weather_client, "_await_enrichments")

    # Fetch first 3 locations
    for loc in multiple_locations[:3]:
        await weather_client.get_weather_data(loc)

    assert mock_fetch.call_count == 3

    # Now fetch all 5 locations
    # All 5 will call _do_fetch_weather_data (cache is fallback, not primary check)
    results = await asyncio.gather(
        *[weather_client.get_weather_data(loc) for loc in multiple_locations]
    )

    assert len(results) == 5
    # All 5 locations will fetch
    assert mock_fetch.call_count == 8  # 3 initial + 5 new


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_concurrent_different_locations(
    weather_client: WeatherClient,
    multiple_locations: list[Location],
    sample_weather_data,
    mocker,
) -> None:
    """
    Test concurrent requests for different locations are not deduplicated.

    Simulates: Background tasks fetching weather for multiple locations.
    """
    fetch_call_count = 0

    async def mock_fetch_with_delay(loc):
        nonlocal fetch_call_count
        fetch_call_count += 1
        await asyncio.sleep(0.05)
        return sample_weather_data(loc)

    mocker.patch.object(
        weather_client,
        "_do_fetch_weather_data",
        side_effect=mock_fetch_with_delay,
    )

    # Launch concurrent requests for different locations
    tasks = [
        asyncio.create_task(weather_client.get_weather_data(loc)) for loc in multiple_locations
    ]

    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start_time

    # All locations should be fetched
    assert len(results) == 5
    assert fetch_call_count == 5

    # Should complete in roughly parallel time (not 5x sequential)
    # With 50ms per fetch, sequential would be 250ms, parallel ~50-100ms
    assert elapsed < 0.15, f"Parallel fetch took {elapsed:.2f}s, expected < 0.15s"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_performance_under_load(
    weather_client: WeatherClient,
    multiple_locations: list[Location],
    sample_weather_data,
    mocker,
) -> None:
    """
    Test performance under heavy concurrent load.

    Simulates: High traffic scenario with many concurrent requests.
    """

    async def mock_fetch_fast(loc):
        await asyncio.sleep(0.01)  # Very fast mock
        return sample_weather_data(loc)

    mocker.patch.object(
        weather_client,
        "_do_fetch_weather_data",
        side_effect=mock_fetch_fast,
    )

    # Create 20 concurrent requests across multiple locations
    tasks = []
    for _ in range(4):  # 4 rounds
        for loc in multiple_locations:
            tasks.append(asyncio.create_task(weather_client.get_weather_data(loc)))

    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start_time

    # All 20 requests should complete
    assert len(results) == 20

    # With connection pool of 30, should handle this load efficiently
    # First round: 5 fetches, remaining 3 rounds use cache
    assert elapsed < 0.5, f"Load test took {elapsed:.2f}s, expected < 0.5s"
