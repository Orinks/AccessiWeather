"""Tests for parallel weather data fetching optimization."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import Location, WeatherData
from accessiweather.weather_client import WeatherClient


@pytest.fixture
def mock_location():
    """Create a mock location for testing."""
    return Location(
        name="Test City", latitude=40.7128, longitude=-74.0060, timezone="America/New_York"
    )


@pytest.mark.asyncio
async def test_enrichments_launch_as_tasks(mock_location):
    """Test that enrichments are launched as asyncio.Tasks."""
    client = WeatherClient(data_source="auto")
    weather_data = WeatherData(location=mock_location)

    # Launch enrichment tasks
    tasks = client._launch_enrichment_tasks(weather_data, mock_location)

    # Verify tasks were created
    assert isinstance(tasks, dict)
    assert len(tasks) > 0

    # Verify all values are asyncio.Task instances
    for task_name, task in tasks.items():
        assert isinstance(task, asyncio.Task), f"{task_name} should be an asyncio.Task"

    # Clean up - cancel all tasks
    for task in tasks.values():
        task.cancel()

    # Wait for cancellation
    await asyncio.gather(*tasks.values(), return_exceptions=True)


@pytest.mark.asyncio
async def test_enrichments_run_concurrently(mock_location):
    """Test that enrichment tasks run in parallel using asyncio.gather."""
    client = WeatherClient(data_source="auto")
    weather_data = WeatherData(location=mock_location)

    # Use AsyncMock to mock the enrichment methods
    mock_sunrise = AsyncMock()
    mock_discussion = AsyncMock()
    mock_vc_alerts = AsyncMock()
    mock_vc_moon = AsyncMock()
    mock_environmental = AsyncMock()
    mock_intl_alerts = AsyncMock()
    mock_aviation = AsyncMock()
    mock_trends = MagicMock()  # Sync method
    mock_persist = MagicMock()  # Sync method

    with (
        patch.object(client, "_enrich_with_sunrise_sunset", mock_sunrise),
        patch.object(client, "_enrich_with_nws_discussion", mock_discussion),
        patch.object(client, "_enrich_with_visual_crossing_alerts", mock_vc_alerts),
        patch.object(client, "_enrich_with_visual_crossing_moon_data", mock_vc_moon),
        patch.object(client, "_populate_environmental_metrics", mock_environmental),
        patch.object(client, "_merge_international_alerts", mock_intl_alerts),
        patch.object(client, "_enrich_with_aviation_data", mock_aviation),
        patch.object(client, "_apply_trend_insights", mock_trends),
        patch.object(client, "_persist_weather_data", mock_persist),
    ):
        # Launch enrichment tasks
        tasks = client._launch_enrichment_tasks(weather_data, mock_location)

        # Verify tasks were created
        assert len(tasks) == 7  # 4 auto-mode + 3 post-processing

        # Await all enrichments
        await client._await_enrichments(tasks, weather_data)

    # Verify all enrichment methods were called
    mock_sunrise.assert_called_once()
    mock_discussion.assert_called_once()
    mock_vc_alerts.assert_called_once()
    mock_vc_moon.assert_called_once()
    mock_environmental.assert_called_once()
    mock_intl_alerts.assert_called_once()
    mock_aviation.assert_called_once()
    mock_trends.assert_called_once()
    mock_persist.assert_called_once()


@pytest.mark.asyncio
async def test_enrichment_errors_dont_crash_await(mock_location):
    """Test that errors in enrichment tasks don't crash the await process."""
    client = WeatherClient(data_source="auto")
    weather_data = WeatherData(location=mock_location)

    # Mock enrichment methods with one that raises an error
    with (
        patch.object(client, "_enrich_with_sunrise_sunset", side_effect=RuntimeError("Test error")),
        patch.object(client, "_enrich_with_nws_discussion", return_value=None),
        patch.object(client, "_enrich_with_visual_crossing_alerts", return_value=None),
        patch.object(client, "_populate_environmental_metrics", return_value=None),
        patch.object(client, "_merge_international_alerts", return_value=None),
        patch.object(client, "_enrich_with_aviation_data", return_value=None),
        patch.object(client, "_apply_trend_insights", return_value=None),
        patch.object(client, "_persist_weather_data", return_value=None),
    ):
        # Launch enrichment tasks
        tasks = client._launch_enrichment_tasks(weather_data, mock_location)

        # This should not raise an exception despite the error in sunrise_sunset
        await client._await_enrichments(tasks, weather_data)

        # Verify we completed without crashing
        assert True


@pytest.mark.asyncio
async def test_pending_enrichments_field_on_weather_data(mock_location):
    """Test that WeatherData can store pending enrichment tasks."""
    weather_data = WeatherData(location=mock_location)

    # Create some mock tasks
    async def dummy_task():
        await asyncio.sleep(0.001)
        return "done"

    task1 = asyncio.create_task(dummy_task())
    task2 = asyncio.create_task(dummy_task())

    # Store tasks in WeatherData
    weather_data.pending_enrichments = {
        "task1": task1,
        "task2": task2,
    }

    # Verify tasks are stored
    assert weather_data.pending_enrichments is not None
    assert len(weather_data.pending_enrichments) == 2

    # Clean up
    await asyncio.gather(task1, task2)
