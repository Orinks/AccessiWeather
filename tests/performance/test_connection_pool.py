"""Tests for HTTP connection pool optimization."""

from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import pytest

from accessiweather.cache import WeatherDataCache
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
    # Cleanup
    await client.close()


@pytest.mark.unit
def test_connection_pool_limits(weather_client: WeatherClient) -> None:
    """Test that HTTP client has optimized connection pool limits."""
    http_client = weather_client._get_http_client()

    assert isinstance(http_client, httpx.AsyncClient)

    # Access the connection pool through the transport
    pool = http_client._transport._pool
    assert pool._max_connections == 30
    assert pool._max_keepalive_connections == 15


@pytest.mark.unit
def test_connection_pool_timeout_config(weather_client: WeatherClient) -> None:
    """Test that HTTP client has proper timeout configuration."""
    http_client = weather_client._get_http_client()

    assert isinstance(http_client.timeout, httpx.Timeout)
    assert http_client.timeout.connect == 3.0
    # Total timeout should be 5.0 (read timeout defaults to total when not specified)
    assert http_client.timeout.read == 5.0 or http_client.timeout.pool == 5.0


@pytest.mark.unit
def test_http_client_reuse(weather_client: WeatherClient) -> None:
    """Test that HTTP client is reused across calls."""
    client1 = weather_client._get_http_client()
    client2 = weather_client._get_http_client()

    # Should return the same client instance
    assert client1 is client2


@pytest.mark.unit
def test_connection_pool_allows_concurrent_requests(weather_client: WeatherClient) -> None:
    """Test that connection pool size allows for concurrent API requests."""
    http_client = weather_client._get_http_client()

    # With max_connections=30, we can handle:
    # - NWS API: gridpoints, forecast, hourly, alerts, discussion, stations (6 concurrent)
    # - Open-Meteo: current, sunrise/sunset (2 concurrent)
    # - Visual Crossing: current, forecast, hourly, alerts (4 concurrent)
    # - Enrichments: environmental, aviation, international alerts (3 concurrent)
    # Total potential concurrent: ~15 requests
    # Our limit of 30 provides comfortable headroom

    pool = http_client._transport._pool
    assert pool._max_connections >= 30
    assert pool._max_keepalive_connections >= 15


@pytest.mark.unit
def test_connection_pool_keepalive_for_performance(weather_client: WeatherClient) -> None:
    """Test that keepalive connections are enabled for performance."""
    http_client = weather_client._get_http_client()

    # Keepalive connections reduce latency by reusing TCP connections
    # With 15 keepalive slots, we can maintain open connections to:
    # - api.weather.gov
    # - api.open-meteo.com
    # - api.visualcrossing.com
    # - aviationweather.gov
    # And other enrichment APIs

    pool = http_client._transport._pool
    assert pool._max_keepalive_connections > 0
    assert pool._max_keepalive_connections >= 15
    # Verify keepalive expiry is set (default 5 seconds)
    assert pool._keepalive_expiry > 0


@pytest.mark.unit
def test_http_client_follows_redirects(weather_client: WeatherClient) -> None:
    """Test that HTTP client is configured to follow redirects."""
    http_client = weather_client._get_http_client()

    # Some weather APIs return 301/302 redirects
    assert http_client.follow_redirects is True
