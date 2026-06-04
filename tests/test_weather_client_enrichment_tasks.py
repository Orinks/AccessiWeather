"""Tests for WeatherClient enrichment task scheduling."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

import accessiweather.weather_client_enrichment as enrichment
from accessiweather.models import Location, WeatherData
from accessiweather.weather_client import WeatherClient
from accessiweather.weather_client_auto import AUTO_NO_NWS_DISCUSSION_TEXT


async def _noop(*args, **kwargs) -> None:
    return None


async def _launch_enrichment_tasks(client: WeatherClient, weather_data: WeatherData):
    location = weather_data.location
    with (
        patch.object(enrichment, "enrich_with_sunrise_sunset", side_effect=_noop),
        patch.object(enrichment, "enrich_with_nws_discussion", side_effect=_noop),
        patch.object(enrichment, "populate_environmental_metrics", side_effect=_noop),
        patch.object(enrichment, "enrich_with_aviation_data", side_effect=_noop),
        patch.object(enrichment, "enrich_with_marine_data", side_effect=_noop),
    ):
        tasks = client._launch_enrichment_tasks(weather_data, location)
        for task in tasks.values():
            task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
    return tasks


@pytest.fixture
def nyc_location() -> Location:
    return Location(name="NYC", latitude=40.7128, longitude=-74.0060)


@pytest.mark.asyncio
async def test_auto_mode_creates_missing_smart_enrichment_tasks(nyc_location):
    """Auto mode fills shared enrichment and missing NWS-specific context."""
    client = WeatherClient(data_source="auto")
    weather_data = WeatherData(location=nyc_location)

    tasks = await _launch_enrichment_tasks(client, weather_data)

    assert "sunrise_sunset" in tasks
    assert "nws_discussion" in tasks
    assert "environmental" in tasks
    assert "aviation" in tasks
    assert "marine" in tasks


@pytest.mark.asyncio
async def test_auto_mode_reuses_existing_nws_discussion(nyc_location):
    """Auto mode should not refetch an NWS discussion already fetched upstream."""
    client = WeatherClient(data_source="auto")
    weather_data = WeatherData(location=nyc_location, discussion="AFD text")

    tasks = await _launch_enrichment_tasks(client, weather_data)

    assert "sunrise_sunset" in tasks
    assert "nws_discussion" not in tasks
    assert "environmental" in tasks


@pytest.mark.asyncio
async def test_auto_mode_respects_disabled_nws_discussion_source(nyc_location):
    """Auto mode should not refetch NWS discussion when NWS was intentionally skipped."""
    client = WeatherClient(data_source="auto")
    weather_data = WeatherData(location=nyc_location, discussion=AUTO_NO_NWS_DISCUSSION_TEXT)

    tasks = await _launch_enrichment_tasks(client, weather_data)

    assert "nws_discussion" not in tasks


@pytest.mark.asyncio
async def test_non_auto_mode_skips_smart_enrichment_tasks(nyc_location):
    """Explicit providers only launch shared enrichment tasks."""
    client = WeatherClient(data_source="nws")
    weather_data = WeatherData(location=nyc_location)

    tasks = await _launch_enrichment_tasks(client, weather_data)

    assert "sunrise_sunset" not in tasks
    assert "nws_discussion" not in tasks
    assert "environmental" in tasks
    assert "aviation" in tasks
    assert "marine" in tasks
