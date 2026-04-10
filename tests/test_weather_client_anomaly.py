"""Tests for WeatherClient anomaly callout enrichment."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import CurrentConditions, Location, WeatherData
from accessiweather.weather_anomaly import AnomalyCallout
from accessiweather.weather_client import WeatherClient


def _make_location() -> Location:
    return Location(name="Test City", latitude=40.0, longitude=-74.0)


def _make_weather_data(temp_f: float | None = 72.0) -> WeatherData:
    current = CurrentConditions()
    current.temperature_f = temp_f
    return WeatherData(location=_make_location(), current=current)


def _make_callout(anomaly: float = 5.0) -> AnomalyCallout:
    return AnomalyCallout(
        temp_anomaly=anomaly,
        temp_anomaly_description=f"Currently {abs(anomaly):.1f} F warmer than average.",
        precip_anomaly_description=None,
        severity="significant",
    )


async def _cancel_tasks(tasks: dict[str, asyncio.Task]) -> None:
    for task in tasks.values():
        task.cancel()
    await asyncio.gather(*tasks.values(), return_exceptions=True)


class TestEnrichWithAnomalyCallout:
    @pytest.fixture()
    def client(self) -> WeatherClient:
        weather_client = WeatherClient()
        weather_client._test_mode = False
        weather_client.openmeteo_archive_client = MagicMock()
        return weather_client

    @pytest.mark.asyncio
    async def test_sets_anomaly_callout_on_success(self, client: WeatherClient) -> None:
        expected = _make_callout(5.0)
        weather_data = _make_weather_data(72.0)
        location = _make_location()

        with patch("accessiweather.weather_anomaly.compute_anomaly", return_value=expected):
            await client._enrich_with_anomaly_callout(weather_data, location)

        assert weather_data.anomaly_callout is expected

    @pytest.mark.asyncio
    async def test_leaves_callout_unset_when_anomaly_has_insufficient_history(
        self, client: WeatherClient
    ) -> None:
        weather_data = _make_weather_data(72.0)
        location = _make_location()

        with patch("accessiweather.weather_anomaly.compute_anomaly", return_value=None):
            await client._enrich_with_anomaly_callout(weather_data, location)

        assert weather_data.anomaly_callout is None

    @pytest.mark.asyncio
    async def test_skips_when_temperature_is_missing(self, client: WeatherClient) -> None:
        weather_data = _make_weather_data(temp_f=None)
        location = _make_location()

        with patch("accessiweather.weather_anomaly.compute_anomaly") as mock_compute:
            await client._enrich_with_anomaly_callout(weather_data, location)

        mock_compute.assert_not_called()
        assert weather_data.anomaly_callout is None

    @pytest.mark.asyncio
    async def test_skips_when_current_conditions_are_missing(self, client: WeatherClient) -> None:
        weather_data = WeatherData(location=_make_location())
        location = _make_location()

        with patch("accessiweather.weather_anomaly.compute_anomaly") as mock_compute:
            await client._enrich_with_anomaly_callout(weather_data, location)

        mock_compute.assert_not_called()
        assert weather_data.anomaly_callout is None

    @pytest.mark.asyncio
    async def test_archive_errors_do_not_abort_weather_update(self, client: WeatherClient) -> None:
        weather_data = _make_weather_data(72.0)
        location = _make_location()

        with patch(
            "accessiweather.weather_anomaly.compute_anomaly",
            side_effect=RuntimeError("archive unavailable"),
        ):
            await client._enrich_with_anomaly_callout(weather_data, location)

        assert weather_data.anomaly_callout is None


class TestOpenMeteoArchiveClientProperty:
    def test_lazy_creation_reuses_archive_client(self) -> None:
        client = WeatherClient()

        assert client._openmeteo_archive_client is None

        archive_client = client.openmeteo_archive_client

        assert archive_client is not None
        assert client.openmeteo_archive_client is archive_client

    def test_setter_allows_tests_to_inject_archive_client(self) -> None:
        client = WeatherClient()
        archive_client = MagicMock()

        client.openmeteo_archive_client = archive_client

        assert client.openmeteo_archive_client is archive_client


class TestLaunchEnrichmentTasksAnomaly:
    @pytest.mark.asyncio
    async def test_anomaly_task_skipped_in_test_mode(self) -> None:
        client = WeatherClient(data_source="openmeteo")
        client.trend_insights_enabled = False
        assert client._test_mode is True
        weather_data = _make_weather_data(72.0)

        with (
            patch(
                "accessiweather.weather_client_enrichment.populate_environmental_metrics",
                new=AsyncMock(),
            ),
            patch(
                "accessiweather.weather_client_enrichment.enrich_with_aviation_data",
                new=AsyncMock(),
            ),
        ):
            tasks = client._launch_enrichment_tasks(weather_data, _make_location())

        try:
            assert "anomaly_callout" not in tasks
        finally:
            await _cancel_tasks(tasks)

    @pytest.mark.asyncio
    async def test_anomaly_task_created_when_not_test_mode_and_temperature_exists(self) -> None:
        client = WeatherClient(data_source="openmeteo")
        client._test_mode = False
        client.trend_insights_enabled = False
        client._enrich_with_anomaly_callout = AsyncMock()
        weather_data = _make_weather_data(72.0)

        with (
            patch(
                "accessiweather.weather_client_enrichment.populate_environmental_metrics",
                new=AsyncMock(),
            ),
            patch(
                "accessiweather.weather_client_enrichment.enrich_with_aviation_data",
                new=AsyncMock(),
            ),
        ):
            tasks = client._launch_enrichment_tasks(weather_data, _make_location())

        try:
            assert "anomaly_callout" in tasks
        finally:
            await _cancel_tasks(tasks)

    @pytest.mark.asyncio
    async def test_anomaly_task_not_created_when_temperature_is_missing(self) -> None:
        client = WeatherClient(data_source="openmeteo")
        client._test_mode = False
        client.trend_insights_enabled = False
        client._enrich_with_anomaly_callout = AsyncMock()
        weather_data = _make_weather_data(temp_f=None)

        with (
            patch(
                "accessiweather.weather_client_enrichment.populate_environmental_metrics",
                new=AsyncMock(),
            ),
            patch(
                "accessiweather.weather_client_enrichment.enrich_with_aviation_data",
                new=AsyncMock(),
            ),
        ):
            tasks = client._launch_enrichment_tasks(weather_data, _make_location())

        try:
            assert "anomaly_callout" not in tasks
        finally:
            await _cancel_tasks(tasks)
