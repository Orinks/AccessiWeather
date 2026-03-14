"""Tests for VC air quality fallback in populate_environmental_metrics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from accessiweather.models import (
    EnvironmentalConditions,
    Location,
    WeatherData,
)
from accessiweather.weather_client_enrichment import populate_environmental_metrics


class TestPopulateEnvironmentalMetricsVcFallback:
    """Tests for VC AQ fallback when Open-Meteo AQ data is unavailable."""

    @pytest.mark.asyncio
    async def test_vc_aq_fallback_called_when_aq_index_none(self):
        """When AQ index is None and VC client exists, call get_air_quality."""
        loc = Location(name="Test", latitude=40.0, longitude=-74.0)
        weather_data = WeatherData(location=loc)

        env = EnvironmentalConditions(air_quality_index=None)
        mock_env_client = AsyncMock()
        mock_env_client.fetch.return_value = env
        mock_env_client.populate_from_visual_crossing = MagicMock()

        mock_vc_client = AsyncMock()
        mock_vc_client.get_air_quality.return_value = {"aqius": 42}

        mock_client = MagicMock()
        mock_client.environmental_client = mock_env_client
        mock_client.air_quality_enabled = True
        mock_client.pollen_enabled = False
        mock_client.visual_crossing_client = mock_vc_client

        await populate_environmental_metrics(mock_client, weather_data, loc)

        mock_vc_client.get_air_quality.assert_awaited_once_with(loc)
        mock_env_client.populate_from_visual_crossing.assert_called_once_with({"aqius": 42}, env)

    @pytest.mark.asyncio
    async def test_vc_aq_fallback_failure_does_not_crash(self):
        """When VC AQ fallback fails, it logs and continues."""
        loc = Location(name="Test", latitude=40.0, longitude=-74.0)
        weather_data = WeatherData(location=loc)

        env = EnvironmentalConditions(air_quality_index=None)
        mock_env_client = AsyncMock()
        mock_env_client.fetch.return_value = env

        mock_vc_client = AsyncMock()
        mock_vc_client.get_air_quality.side_effect = Exception("VC down")

        mock_client = MagicMock()
        mock_client.environmental_client = mock_env_client
        mock_client.air_quality_enabled = True
        mock_client.pollen_enabled = False
        mock_client.visual_crossing_client = mock_vc_client

        await populate_environmental_metrics(mock_client, weather_data, loc)

        assert weather_data.environmental is env

    @pytest.mark.asyncio
    async def test_no_vc_fallback_when_aq_index_present(self):
        """When AQ index is present, VC fallback should not be called."""
        loc = Location(name="Test", latitude=40.0, longitude=-74.0)
        weather_data = WeatherData(location=loc)

        env = EnvironmentalConditions(air_quality_index=42.0)
        mock_env_client = AsyncMock()
        mock_env_client.fetch.return_value = env

        mock_vc_client = AsyncMock()

        mock_client = MagicMock()
        mock_client.environmental_client = mock_env_client
        mock_client.air_quality_enabled = True
        mock_client.pollen_enabled = False
        mock_client.visual_crossing_client = mock_vc_client

        await populate_environmental_metrics(mock_client, weather_data, loc)

        mock_vc_client.get_air_quality.assert_not_awaited()
