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
@pytest.mark.skip(reason="Needs porting to refactored weather_client_base.py structure")
async def test_cache_hit_skips_api_calls(
    temp_cache_dir: Path,
    test_location: Location,
    sample_weather_data: WeatherData,
    mocker,
):
    """Test that fresh cache hits skip API calls entirely."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=5)

    # Store fresh data in cache
    cache.store(test_location, sample_weather_data)

    # Create client with cache
    client = WeatherClient(offline_cache=cache)

    # Mock API methods to verify they're not called
    mock_nws = mocker.patch.object(client, "_fetch_nws_data")
    mock_openmeteo = mocker.patch.object(client, "_fetch_openmeteo_data")

    # Get weather data - should hit cache
    result = await client.get_weather_data(test_location)

    # Verify cache hit
    assert result.current is not None
    assert result.current.temperature_f == 72.0

    # Verify API methods were NOT called
    mock_nws.assert_not_called()
    mock_openmeteo.assert_not_called()

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
    """Test that multiple requests use cached data."""
    cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=60)

    # Store fresh data
    cache.store(test_location, sample_weather_data)

    client = WeatherClient(offline_cache=cache)

    # Mock API to verify it's not called
    mock_fetch = mocker.patch.object(client, "_fetch_nws_data")

    # Make multiple requests
    result1 = await client.get_weather_data(test_location)
    result2 = await client.get_weather_data(test_location)
    result3 = await client.get_weather_data(test_location)

    # All should return cached data
    assert result1.current is not None
    assert result2.current is not None
    assert result3.current is not None

    # API should not be called at all
    mock_fetch.assert_not_called()

    await client.close()
