"""Tests for ParallelFetchCoordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from accessiweather.models.weather import (
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
)
from accessiweather.weather_client_parallel import ParallelFetchCoordinator


@pytest.fixture
def coordinator():
    return ParallelFetchCoordinator(timeout=2.0)


@pytest.fixture
def location():
    return Location(name="Test City", latitude=40.0, longitude=-75.0)


@pytest.fixture
def mock_current():
    return MagicMock(spec=CurrentConditions)


@pytest.fixture
def mock_forecast():
    return MagicMock(spec=Forecast)


@pytest.fixture
def mock_hourly():
    return MagicMock(spec=HourlyForecast)


class TestParallelFetchCoordinator:
    """Tests for ParallelFetchCoordinator."""

    @pytest.mark.asyncio
    async def test_fetch_all_no_sources(self, coordinator, location):
        """Returns empty list when no sources provided."""
        results = await coordinator.fetch_all(location)
        assert results == []

    @pytest.mark.asyncio
    async def test_fetch_all_single_source_success(
        self, coordinator, location, mock_current, mock_forecast, mock_hourly
    ):
        """Single source returning data works."""

        async def fake_nws():
            return (mock_current, mock_forecast, mock_hourly, None)

        results = await coordinator.fetch_all(location, fetch_nws=fake_nws())
        assert len(results) == 1
        assert results[0].source == "nws"
        assert results[0].success is True
        assert results[0].current is mock_current
        assert results[0].forecast is mock_forecast
        assert results[0].hourly_forecast is mock_hourly
        assert results[0].alerts is None
        assert results[0].error is None

    @pytest.mark.asyncio
    async def test_fetch_all_multiple_sources(
        self, coordinator, location, mock_current, mock_forecast, mock_hourly
    ):
        """Multiple sources fetched in parallel."""

        async def fake_nws():
            return (mock_current, mock_forecast, mock_hourly, None)

        async def fake_openmeteo():
            return (mock_current, mock_forecast, mock_hourly)

        results = await coordinator.fetch_all(
            location,
            fetch_nws=fake_nws(),
            fetch_openmeteo=fake_openmeteo(),
        )
        assert len(results) == 2
        sources = {r.source for r in results}
        assert sources == {"nws", "openmeteo"}
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_fetch_all_with_visualcrossing(
        self, coordinator, location, mock_current, mock_forecast, mock_hourly
    ):
        """Visual Crossing source works."""

        async def fake_vc():
            return (mock_current, mock_forecast, mock_hourly, None)

        results = await coordinator.fetch_all(location, fetch_visualcrossing=fake_vc())
        assert len(results) == 1
        assert results[0].source == "visualcrossing"
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_fetch_all_source_exception(self, coordinator, location):
        """Source that raises exception produces failure SourceData."""

        async def failing_nws():
            raise ConnectionError("Network unreachable")

        results = await coordinator.fetch_all(location, fetch_nws=failing_nws())
        assert len(results) == 1
        assert results[0].source == "nws"
        assert results[0].success is False
        assert "Network unreachable" in results[0].error

    @pytest.mark.asyncio
    async def test_fetch_all_source_timeout(self, location):
        """Source that times out produces failure SourceData."""
        coordinator = ParallelFetchCoordinator(timeout=0.1)

        async def slow_nws():
            await asyncio.sleep(5)
            return (None, None, None, None)

        results = await coordinator.fetch_all(location, fetch_nws=slow_nws())
        assert len(results) == 1
        assert results[0].source == "nws"
        assert results[0].success is False
        assert "timed out" in results[0].error

    @pytest.mark.asyncio
    async def test_fetch_all_mixed_success_failure(
        self, coordinator, location, mock_current, mock_forecast, mock_hourly
    ):
        """One source succeeds, another fails."""

        async def good_openmeteo():
            return (mock_current, mock_forecast, mock_hourly)

        async def bad_nws():
            raise ValueError("Bad data")

        results = await coordinator.fetch_all(
            location,
            fetch_nws=bad_nws(),
            fetch_openmeteo=good_openmeteo(),
        )
        assert len(results) == 2
        nws_result = next(r for r in results if r.source == "nws")
        om_result = next(r for r in results if r.source == "openmeteo")
        assert nws_result.success is False
        assert om_result.success is True

    @pytest.mark.asyncio
    async def test_fetch_all_all_three_sources(
        self, coordinator, location, mock_current, mock_forecast, mock_hourly
    ):
        """All three sources fetched."""

        async def fake_nws():
            return (mock_current, mock_forecast, mock_hourly, None)

        async def fake_om():
            return (mock_current, mock_forecast, mock_hourly)

        async def fake_vc():
            return (mock_current, mock_forecast, mock_hourly, None)

        results = await coordinator.fetch_all(
            location,
            fetch_nws=fake_nws(),
            fetch_openmeteo=fake_om(),
            fetch_visualcrossing=fake_vc(),
        )
        assert len(results) == 3
        sources = {r.source for r in results}
        assert sources == {"nws", "openmeteo", "visualcrossing"}

    @pytest.mark.asyncio
    async def test_create_source_data_short_tuple(self, coordinator):
        """_create_source_data handles tuples shorter than 4."""
        result = coordinator._create_source_data("test", (None,))
        assert result.source == "test"
        assert result.current is None
        assert result.forecast is None
        assert result.hourly_forecast is None
        assert result.alerts is None
        assert result.success is True

    @pytest.mark.asyncio
    async def test_create_source_data_empty_tuple(self, coordinator):
        """_create_source_data handles empty tuple."""
        result = coordinator._create_source_data("test", ())
        assert result.current is None
        assert result.forecast is None

    @pytest.mark.asyncio
    async def test_handle_source_failure(self, coordinator):
        """_handle_source_failure creates correct SourceData."""
        error = RuntimeError("something broke")
        result = coordinator._handle_source_failure("nws", error)
        assert result.source == "nws"
        assert result.success is False
        assert "something broke" in result.error

    @pytest.mark.asyncio
    async def test_default_timeout(self):
        """Default timeout is 5.0."""
        coordinator = ParallelFetchCoordinator()
        assert coordinator.timeout == 5.0

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Custom timeout is respected."""
        coordinator = ParallelFetchCoordinator(timeout=10.0)
        assert coordinator.timeout == 10.0
