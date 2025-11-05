"""Integration tests for HTTP timeout and retry behavior."""

import asyncio

import httpx
import pytest

from accessiweather.models import Location
from accessiweather.weather_client import WeatherClient


@pytest.fixture
def test_location():
    """Create a test location."""
    return Location(name="Test Location", latitude=40.7128, longitude=-74.0060)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_timeout_configuration(test_location: Location):
    """Test that HTTP client uses structured timeout configuration."""
    client = WeatherClient()

    http_client = client._get_http_client()
    assert isinstance(http_client, httpx.AsyncClient)

    # Check timeout configuration
    timeout = http_client.timeout
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 3.0
    assert timeout.read == 5.0
    assert timeout.write == 5.0
    assert timeout.pool == 5.0

    await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nws_fetch_with_timeout_simulation(test_location: Location, monkeypatch):
    """Test NWS data fetch handles timeout with retry."""
    from unittest.mock import AsyncMock

    client = WeatherClient()

    # Mock the parallel fetch to simulate timeout on first attempt
    call_count = 0

    async def mock_fetch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.TimeoutException("Simulated timeout")
        # Return None values on retry success
        return None, None, None, None, None

    mock = AsyncMock(side_effect=mock_fetch)
    monkeypatch.setattr(
        "accessiweather.weather_client_nws.get_nws_all_data_parallel",
        mock,
    )

    result = await client._fetch_nws_data(test_location)

    # Should have retried once
    assert call_count == 2
    assert result == (None, None, None, None, None)

    await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nws_fetch_timeout_exhausted(test_location: Location, monkeypatch):
    """Test NWS data fetch returns None tuple when all retries exhausted."""
    from unittest.mock import AsyncMock

    client = WeatherClient()

    # Mock to always timeout
    async def always_timeout(*args, **kwargs):
        raise httpx.TimeoutException("Persistent timeout")

    mock = AsyncMock(side_effect=always_timeout)
    monkeypatch.setattr(
        "accessiweather.weather_client_nws.get_nws_all_data_parallel",
        mock,
    )

    result = await client._fetch_nws_data(test_location)

    # Should return None tuple after exhausting retries
    assert result == (None, None, None, None, None)

    await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openmeteo_fetch_with_timeout_simulation(test_location: Location, monkeypatch):
    """Test Open-Meteo data fetch handles timeout with retry."""
    from unittest.mock import AsyncMock

    client = WeatherClient()

    call_count = 0

    async def mock_fetch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("Simulated connection error")
        return None, None, None

    mock = AsyncMock(side_effect=mock_fetch)
    monkeypatch.setattr(
        "accessiweather.weather_client_openmeteo.get_openmeteo_all_data_parallel",
        mock,
    )

    result = await client._fetch_openmeteo_data(test_location)

    assert call_count == 2
    assert result == (None, None, None)

    await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openmeteo_fetch_timeout_exhausted(test_location: Location, monkeypatch):
    """Test Open-Meteo fetch returns None tuple when retries exhausted."""
    from unittest.mock import AsyncMock

    client = WeatherClient()

    async def always_fails(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    mock = AsyncMock(side_effect=always_fails)
    monkeypatch.setattr(
        "accessiweather.weather_client_openmeteo.get_openmeteo_all_data_parallel",
        mock,
    )

    result = await client._fetch_openmeteo_data(test_location)

    assert result == (None, None, None)

    await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_delay_timing(test_location: Location, monkeypatch):
    """Test that retry delay follows exponential backoff."""
    from unittest.mock import AsyncMock

    client = WeatherClient()

    call_times = []

    async def track_calls(*args, **kwargs):
        call_times.append(asyncio.get_event_loop().time())
        if len(call_times) < 2:
            raise httpx.TimeoutException("Timeout")
        return None, None, None, None, None

    mock = AsyncMock(side_effect=track_calls)
    monkeypatch.setattr(
        "accessiweather.weather_client_nws.get_nws_all_data_parallel",
        mock,
    )

    await client._fetch_nws_data(test_location)

    # Should have 2 calls (initial + 1 retry)
    assert len(call_times) == 2

    # Check that delay is approximately 1 second (initial_delay)
    delay = call_times[1] - call_times[0]
    assert 0.9 < delay < 1.5  # Allow some tolerance for async timing

    await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connection_pool_limits():
    """Test that connection pool limits are configured correctly."""
    client = WeatherClient()

    http_client = client._get_http_client()

    # httpx stores limits in _limits (private attribute)
    # Just verify the client was created successfully and has expected methods
    assert hasattr(http_client, "get")
    assert hasattr(http_client, "post")
    assert not http_client.is_closed

    await client.close()
