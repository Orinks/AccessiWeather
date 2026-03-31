"""Tests for anomaly callout enrichment in WeatherClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.models import (
    CurrentConditions,
    Location,
    WeatherData,
)
from accessiweather.weather_anomaly import AnomalyCallout
from accessiweather.weather_client import WeatherClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_location() -> Location:
    return Location(name="Test City", latitude=40.0, longitude=-74.0)


def _make_weather_data(temp_f: float | None = 72.0) -> WeatherData:
    current = CurrentConditions()
    current.temperature_f = temp_f
    return WeatherData(location=_make_location(), current=current)


def _make_callout(anomaly: float = 5.0) -> AnomalyCallout:
    return AnomalyCallout(
        temp_anomaly=anomaly,
        temp_anomaly_description=f"Currently {abs(anomaly):.1f}°F warmer than average.",
        precip_anomaly_description=None,
        severity="significant",
    )


# ---------------------------------------------------------------------------
# _enrich_with_anomaly_callout
# ---------------------------------------------------------------------------


class TestEnrichWithAnomalyCallout:
    @pytest.fixture()
    def client(self):
        """WeatherClient NOT in test mode (so anomaly runs)."""
        c = WeatherClient()
        c._test_mode = False
        return c

    @pytest.mark.asyncio
    async def test_sets_anomaly_callout_on_success(self, client):
        """When compute_anomaly returns a callout it is stored on weather_data."""
        expected = _make_callout(5.0)
        weather_data = _make_weather_data(72.0)
        location = _make_location()

        with (
            patch(
                "accessiweather.weather_client_base.WeatherClient._enrich_with_anomaly_callout",
                wraps=client._enrich_with_anomaly_callout,
            ),
            patch("accessiweather.weather_anomaly.compute_anomaly", return_value=expected),
        ):
            await client._enrich_with_anomaly_callout(weather_data, location)

        assert weather_data.anomaly_callout is expected

    @pytest.mark.asyncio
    async def test_sets_none_when_compute_returns_none(self, client):
        """When compute_anomaly returns None (insufficient data), anomaly_callout stays None."""
        weather_data = _make_weather_data(72.0)
        location = _make_location()

        with patch("accessiweather.weather_anomaly.compute_anomaly", return_value=None):
            await client._enrich_with_anomaly_callout(weather_data, location)

        assert weather_data.anomaly_callout is None

    @pytest.mark.asyncio
    async def test_skips_when_no_temperature(self, client):
        """Enrichment is a no-op when current temperature_f is None."""
        weather_data = _make_weather_data(temp_f=None)
        location = _make_location()

        with patch("accessiweather.weather_anomaly.compute_anomaly") as mock_compute:
            await client._enrich_with_anomaly_callout(weather_data, location)
            mock_compute.assert_not_called()

        assert weather_data.anomaly_callout is None

    @pytest.mark.asyncio
    async def test_skips_when_no_current(self, client):
        """Enrichment is a no-op when current conditions are absent."""
        weather_data = WeatherData(location=_make_location())
        location = _make_location()

        with patch("accessiweather.weather_anomaly.compute_anomaly") as mock_compute:
            await client._enrich_with_anomaly_callout(weather_data, location)
            mock_compute.assert_not_called()

        assert weather_data.anomaly_callout is None

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, client):
        """A compute_anomaly exception must not propagate; anomaly_callout stays None."""
        weather_data = _make_weather_data(72.0)
        location = _make_location()

        with patch(
            "accessiweather.weather_anomaly.compute_anomaly",
            side_effect=RuntimeError("archive unavailable"),
        ):
            # Should not raise
            await client._enrich_with_anomaly_callout(weather_data, location)

        assert weather_data.anomaly_callout is None


# ---------------------------------------------------------------------------
# openmeteo_archive_client property
# ---------------------------------------------------------------------------


class TestOpenMeteoArchiveClientProperty:
    def test_lazy_creation(self):
        client = WeatherClient()
        assert client._openmeteo_archive_client is None
        archive = client.openmeteo_archive_client
        assert archive is not None
        # Second access returns same instance
        assert client.openmeteo_archive_client is archive

    def test_setter_for_testing(self):
        client = WeatherClient()
        mock_archive = MagicMock()
        client.openmeteo_archive_client = mock_archive
        assert client.openmeteo_archive_client is mock_archive


# ---------------------------------------------------------------------------
# _launch_enrichment_tasks — anomaly task inclusion
# ---------------------------------------------------------------------------


class TestLaunchEnrichmentTasksAnomaly:
    @pytest.mark.asyncio
    async def test_anomaly_task_skipped_in_test_mode(self):
        """In test mode the anomaly task must NOT be created."""
        client = WeatherClient()
        assert client._test_mode is True  # pytest sets PYTEST_CURRENT_TEST

        weather_data = _make_weather_data(72.0)
        location = _make_location()

        tasks = client._launch_enrichment_tasks(weather_data, location)
        assert "anomaly_callout" not in tasks
        for t in tasks.values():
            t.cancel()

    @pytest.mark.asyncio
    async def test_anomaly_task_created_when_not_test_mode(self):
        """Outside test mode, the anomaly task is created when temperature is available."""
        client = WeatherClient()
        client._test_mode = False

        weather_data = _make_weather_data(72.0)
        location = _make_location()

        tasks = client._launch_enrichment_tasks(weather_data, location)
        assert "anomaly_callout" in tasks
        for t in tasks.values():
            t.cancel()

    @pytest.mark.asyncio
    async def test_anomaly_task_not_created_when_no_temperature(self):
        """Without a temperature reading the anomaly task must not be created."""
        client = WeatherClient()
        client._test_mode = False

        weather_data = _make_weather_data(temp_f=None)
        location = _make_location()

        tasks = client._launch_enrichment_tasks(weather_data, location)
        assert "anomaly_callout" not in tasks
        for t in tasks.values():
            t.cancel()
