"""Tests for WeatherClient.pre_warm_batch() batch cache warming."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestPreWarmBatch:
    """Tests for batch pre-warming multiple locations."""

    def _make_client(self):
        """Create a minimal WeatherClient with mocked internals."""
        from accessiweather.weather_client_base import WeatherClient

        client = WeatherClient.__new__(WeatherClient)
        client.user_agent = "test/1.0"
        return client

    @pytest.mark.asyncio
    async def test_empty_locations_returns_zero(self):
        """Empty locations list should return 0 immediately."""
        client = self._make_client()
        result = await client.pre_warm_batch([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_locations_pre_warm_individually(self):
        """Locations are warmed through the normal per-location cache path."""
        client = self._make_client()

        locs = [MagicMock(name="L1"), MagicMock(name="L2")]
        client.pre_warm_cache = AsyncMock(return_value=True)

        result = await client.pre_warm_batch(locs)

        assert client.pre_warm_cache.await_count == 2
        assert result == 2

    @pytest.mark.asyncio
    async def test_failed_locations_are_not_counted(self):
        """Failed per-location warmups are excluded from the success count."""
        client = self._make_client()

        locs = [MagicMock(name="Loc1"), MagicMock(name="Loc2")]
        client.pre_warm_cache = AsyncMock(side_effect=[True, False])

        result = await client.pre_warm_batch(locs)

        assert result == 1
