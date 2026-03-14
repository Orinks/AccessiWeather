"""Tests for WeatherClient.pre_warm_batch() batch cache warming."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestPreWarmBatch:
    """Tests for batch pre-warming multiple locations."""

    def _make_client(self, vc_client=None):
        """Create a minimal WeatherClient with mocked internals."""
        from accessiweather.weather_client_base import WeatherClient

        client = WeatherClient.__new__(WeatherClient)
        client._visual_crossing_client = vc_client
        client._visual_crossing_api_key = ""
        client.user_agent = "test/1.0"
        return client

    @pytest.mark.asyncio
    async def test_empty_locations_returns_zero(self):
        """Empty locations list should return 0 immediately."""
        client = self._make_client()
        result = await client.pre_warm_batch([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_with_vc_client_calls_batch_then_individual(self):
        """With VC client and >1 locations, calls get_forecast_batch."""
        mock_vc = AsyncMock()
        mock_vc.get_forecast_batch.return_value = {
            "a": MagicMock(),
            "b": MagicMock(),
        }
        client = self._make_client(vc_client=mock_vc)

        locs = [MagicMock(name="Loc1"), MagicMock(name="Loc2")]
        client.pre_warm_cache = AsyncMock(return_value=True)

        result = await client.pre_warm_batch(locs)

        mock_vc.get_forecast_batch.assert_awaited_once_with(locs)
        assert client.pre_warm_cache.await_count == 2
        assert result == 2

    @pytest.mark.asyncio
    async def test_without_vc_client_only_individual(self):
        """Without VC client, only calls individual pre_warm_cache."""
        client = self._make_client(vc_client=None)

        locs = [MagicMock(name="Loc1")]
        client.pre_warm_cache = AsyncMock(return_value=True)

        result = await client.pre_warm_batch(locs)

        assert client.pre_warm_cache.await_count == 1
        assert result == 1

    @pytest.mark.asyncio
    async def test_batch_failure_falls_back_to_individual(self):
        """If get_forecast_batch raises, still does individual pre-warm."""
        mock_vc = AsyncMock()
        mock_vc.get_forecast_batch.side_effect = Exception("batch fail")
        client = self._make_client(vc_client=mock_vc)

        locs = [MagicMock(name="L1"), MagicMock(name="L2")]
        client.pre_warm_cache = AsyncMock(return_value=False)

        result = await client.pre_warm_batch(locs)

        assert client.pre_warm_cache.await_count == 2
        assert result == 0

    @pytest.mark.asyncio
    async def test_single_location_skips_batch(self):
        """Single location should skip batch even with VC client."""
        mock_vc = AsyncMock()
        client = self._make_client(vc_client=mock_vc)

        locs = [MagicMock(name="Loc1")]
        client.pre_warm_cache = AsyncMock(return_value=True)

        result = await client.pre_warm_batch(locs)

        mock_vc.get_forecast_batch.assert_not_awaited()
        assert result == 1
