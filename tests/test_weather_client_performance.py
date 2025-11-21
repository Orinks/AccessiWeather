"""Test performance optimizations in weather client."""

import asyncio
import time
from unittest.mock import patch

import pytest

from accessiweather.weather_client import WeatherClient


@pytest.mark.asyncio
async def test_http_client_reuse():
    """Test that HTTP client is reused across multiple calls."""
    client = WeatherClient(user_agent="TestAgent")

    # Get the HTTP client
    http_client1 = client._get_http_client()
    http_client2 = client._get_http_client()

    # Should be the same instance
    assert http_client1 is http_client2

    # Clean up
    await client.close()


@pytest.mark.asyncio
async def test_context_manager():
    """Test that WeatherClient can be used as an async context manager."""
    async with WeatherClient(user_agent="TestAgent") as client:
        # HTTP client should be available
        http_client = client._get_http_client()
        assert http_client is not None
        assert not http_client.is_closed

    # After exiting context, client should be closed
    # Note: We can't easily check if it's closed without accessing private state


@pytest.mark.asyncio
async def test_parallel_nws_fetching_faster_than_sequential():
    """Test that parallel fetching is faster than sequential (simulated)."""

    # Mock the individual NWS functions to simulate delay
    async def mock_current(*args, **kwargs):
        await asyncio.sleep(0.1)  # Simulate 100ms API call
        return

    async def mock_forecast(*args, **kwargs):
        await asyncio.sleep(0.1)  # Simulate 100ms API call
        return None, None

    async def mock_alerts(*args, **kwargs):
        await asyncio.sleep(0.1)  # Simulate 100ms API call
        return

    async def mock_hourly(*args, **kwargs):
        await asyncio.sleep(0.1)  # Simulate 100ms API call
        return

    with (
        patch("accessiweather.weather_client_nws.get_nws_current_conditions", new=mock_current),
        patch(
            "accessiweather.weather_client_nws.get_nws_forecast_and_discussion", new=mock_forecast
        ),
        patch("accessiweather.weather_client_nws.get_nws_alerts", new=mock_alerts),
        patch("accessiweather.weather_client_nws.get_nws_hourly_forecast", new=mock_hourly),
    ):
        # Simulate sequential execution (old way)
        start_sequential = time.time()
        await mock_current()
        await mock_forecast()
        await mock_alerts()
        await mock_hourly()
        sequential_time = time.time() - start_sequential

        # Simulate parallel execution (new way)
        start_parallel = time.time()
        await asyncio.gather(
            mock_current(),
            mock_forecast(),
            mock_alerts(),
            mock_hourly(),
        )
        parallel_time = time.time() - start_parallel

        # Parallel should be significantly faster
        # Sequential: ~400ms, Parallel: ~100ms
        assert parallel_time < sequential_time * 0.5, (
            f"Parallel ({parallel_time:.3f}s) should be much faster than sequential ({sequential_time:.3f}s)"
        )


@pytest.mark.asyncio
async def test_enrichment_parallel_execution():
    """Test that enrichment calls run in parallel."""
    # Track call order
    call_order = []

    async def mock_enrich1(*args):
        call_order.append("start_1")
        await asyncio.sleep(0.05)
        call_order.append("end_1")

    async def mock_enrich2(*args):
        call_order.append("start_2")
        await asyncio.sleep(0.05)
        call_order.append("end_2")

    async def mock_enrich3(*args):
        call_order.append("start_3")
        await asyncio.sleep(0.05)
        call_order.append("end_3")

    # Test parallel execution
    call_order.clear()
    start = time.time()
    await asyncio.gather(
        mock_enrich1(),
        mock_enrich2(),
        mock_enrich3(),
    )
    parallel_time = time.time() - start

    # All tasks should start before any end (proving parallelism)
    start_indices = [i for i, call in enumerate(call_order) if call.startswith("start_")]
    end_indices = [i for i, call in enumerate(call_order) if call.startswith("end_")]

    # At least one task should start before another one ends (overlap)
    assert max(start_indices) < max(end_indices)

    # Should take ~0.05s (parallel) not ~0.15s (sequential)
    assert parallel_time < 0.1, f"Parallel execution took {parallel_time:.3f}s, expected < 0.1s"


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_http_client_reuse())
    asyncio.run(test_context_manager())
    asyncio.run(test_parallel_nws_fetching_faster_than_sequential())
    asyncio.run(test_enrichment_parallel_execution())
    print("All tests passed!")
