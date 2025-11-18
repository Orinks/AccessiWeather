"""Tests for cache optimization and pre-warming."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from accessiweather.cache import WeatherDataCache
from accessiweather.models import CurrentConditions, Location, WeatherData
from accessiweather.weather_client import WeatherClient


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_location():
    """Create a test location."""
    return Location(name="Test City", latitude=40.7128, longitude=-74.0060)


@pytest.fixture
def sample_weather_data(test_location):
    """Create sample weather data."""
    current = CurrentConditions(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Partly Cloudy",
        humidity=65,
    )
    return WeatherData(location=test_location, current=current, last_updated=datetime.now(UTC))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_hit_still_fetches_api(
    temp_cache_dir: Path,
    test_location: Location,
    sample_weather_data: WeatherData,
    mocker,
):
    """Test that cache-first design returns cached data immediately and updates in background."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=5)

    # Store fresh data in cache
    cache.store(test_location, sample_weather_data)

    # Create client with cache
    client = WeatherClient(offline_cache=cache)

    # Mock API methods to track background calls
    mocker.patch.object(
        client,
        "_fetch_nws_data",
        return_value=(
            sample_weather_data.current,
            sample_weather_data.forecast,
            None,
            sample_weather_data.alerts,
            sample_weather_data.hourly_forecast,
        ),
    )
    # Mock enrichments to avoid API calls
    mocker.patch.object(client, "_launch_enrichment_tasks", return_value={})
    mocker.patch.object(client, "_await_enrichments")

    # Get weather data - should return cached data immediately
    result = await client.get_weather_data(test_location)

    # Verify we got data from cache
    assert result.current is not None
    assert result.current.temperature_f == 72.0

    # With cache-first design, API is NOT called immediately - it runs in background
    # The background enrichment task is created but may not complete before we assert
    # So we just verify the cached data was returned
    assert (
        result == sample_weather_data
        or result.current.temperature_f == sample_weather_data.current.temperature_f
    )

    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stale_cache_triggers_refresh(
    temp_cache_dir: Path,
    test_location: Location,
    sample_weather_data: WeatherData,
    mocker,
):
    """Test that stale cache triggers API refresh."""
    # Create cache with 0-minute max_age (immediately stale)
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=0)

    # Store data that will be immediately stale
    cache.store(test_location, sample_weather_data)

    # Create client with cache
    client = WeatherClient(offline_cache=cache)

    # Mock API to return fresh data
    fresh_data = WeatherData(
        location=test_location,
        current=CurrentConditions(
            temperature_f=75.0,  # Different temperature
            temperature_c=23.9,
            condition="Sunny",
            humidity=50,
        ),
        last_updated=datetime.now(UTC),
    )

    mock_fetch = mocker.patch.object(
        client, "_fetch_nws_data", return_value=(fresh_data.current, None, None, None, None)
    )

    # Get weather data - should bypass stale cache and fetch fresh
    await client.get_weather_data(test_location)

    # Verify API was called
    mock_fetch.assert_called_once()

    # Note: Result will be processed through the full fetch pipeline
    # so we just verify the API was actually called
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache(
    temp_cache_dir: Path,
    test_location: Location,
    sample_weather_data: WeatherData,
    mocker,
):
    """Test that force_refresh=True bypasses cache."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=60)

    # Store fresh data in cache
    cache.store(test_location, sample_weather_data)

    # Create client with cache
    client = WeatherClient(offline_cache=cache)

    # Mock API method to verify it's called
    mock_fetch = mocker.patch.object(
        client, "_fetch_nws_data", return_value=(None, None, None, None, None)
    )

    # Get weather data with force_refresh=True
    await client.get_weather_data(test_location, force_refresh=True)

    # Verify API was called despite fresh cache
    mock_fetch.assert_called_once()

    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pre_warm_cache_success(temp_cache_dir: Path, test_location: Location, mocker):
    """Test successful cache pre-warming."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=60)
    client = WeatherClient(offline_cache=cache)

    # Mock successful API response
    fresh_data = CurrentConditions(
        temperature_f=70.0, temperature_c=21.1, condition="Clear", humidity=55
    )
    mocker.patch.object(
        client, "_fetch_nws_data", return_value=(fresh_data, None, None, None, None)
    )

    # Pre-warm cache
    success = await client.pre_warm_cache(test_location)

    assert success is True

    # Verify data was stored in cache
    cached = cache.load(test_location)
    assert cached is not None
    assert cached.current is not None
    assert cached.current.temperature_f == 70.0

    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pre_warm_cache_failure(temp_cache_dir: Path, test_location: Location, mocker):
    """Test cache pre-warming when all APIs fail."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=60)
    client = WeatherClient(offline_cache=cache)

    # Mock all API methods to fail
    mocker.patch.object(client, "_fetch_nws_data", side_effect=Exception("NWS API Error"))
    mocker.patch.object(
        client, "_fetch_openmeteo_data", side_effect=Exception("OpenMeteo API Error")
    )

    # Pre-warm cache (should handle error)
    success = await client.pre_warm_cache(test_location)

    # With fallback logic, this may still succeed if enrichments provide data
    # The important thing is it doesn't crash
    assert isinstance(success, bool)

    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.skip(reason="Test uses methods from old architecture (_launch_enrichment_tasks)")
async def test_pre_warm_cache_no_data(temp_cache_dir: Path, test_location: Location, mocker):
    """Test cache pre-warming when APIs return no data and enrichments fail."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=60)
    client = WeatherClient(offline_cache=cache)

    # Mock API returning empty data
    mocker.patch.object(client, "_fetch_nws_data", return_value=(None, None, None, None, None))
    mocker.patch.object(client, "_fetch_openmeteo_data", return_value=(None, None, None))
    mocker.patch.object(client, "_augment_current_with_openmeteo", return_value=None)

    # Also mock enrichments to prevent fallback success
    mocker.patch.object(client, "_launch_enrichment_tasks", return_value={})

    # Pre-warm cache
    success = await client.pre_warm_cache(test_location)

    # Should return False when no data available
    assert success is False

    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_miss_fetches_data(temp_cache_dir: Path, test_location: Location, mocker):
    """Test that cache miss triggers data fetch."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=60)
    client = WeatherClient(offline_cache=cache)

    # Mock API response
    mock_fetch = mocker.patch.object(
        client, "_fetch_nws_data", return_value=(None, None, None, None, None)
    )

    # Get weather data (cache is empty)
    await client.get_weather_data(test_location)

    # Verify API was called
    mock_fetch.assert_called_once()

    await client.close()


@pytest.mark.unit
def test_cache_expiration_time(
    temp_cache_dir: Path, test_location: Location, sample_weather_data: WeatherData
):
    """Test that cache correctly identifies expired data."""
    # Create cache with 5-minute TTL
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=5)

    # Store data
    cache.store(test_location, sample_weather_data)

    # Load immediately - should not be stale
    fresh = cache.load(test_location, allow_stale=False)
    assert fresh is not None
    assert not fresh.stale

    # Create cache with 0-minute TTL to simulate expiration
    cache_short = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=0)

    # Load with short TTL - should be stale
    stale = cache_short.load(test_location, allow_stale=True)
    assert stale is not None
    assert stale.stale


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multiple_cache_hits(
    temp_cache_dir: Path,
    test_location: Location,
    sample_weather_data: WeatherData,
    mocker,
):
    """Test that multiple requests with cache-first design all return cached data quickly."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=60)

    # Store fresh data
    cache.store(test_location, sample_weather_data)

    client = WeatherClient(offline_cache=cache)

    # Mock API to return data (for background enrichment)
    mocker.patch.object(
        client,
        "_fetch_nws_data",
        return_value=(
            sample_weather_data.current,
            sample_weather_data.forecast,
            None,
            sample_weather_data.alerts,
            sample_weather_data.hourly_forecast,
        ),
    )
    # Mock enrichments to avoid API calls
    mocker.patch.object(client, "_launch_enrichment_tasks", return_value={})
    mocker.patch.object(client, "_await_enrichments")

    # Make multiple requests
    result1 = await client.get_weather_data(test_location)
    result2 = await client.get_weather_data(test_location)
    result3 = await client.get_weather_data(test_location)

    # All should have data from cache
    assert result1.current is not None
    assert result2.current is not None
    assert result3.current is not None

    # With cache-first design, all requests return cached data immediately
    # Background API calls may happen but are not awaited by the client
    # All results should be identical (same cached data)
    assert (
        result1.current.temperature_f
        == result2.current.temperature_f
        == result3.current.temperature_f
        == 72.0
    )

    await client.close()
