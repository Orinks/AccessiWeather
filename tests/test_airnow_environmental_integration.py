"""Integration tests for AirNow in environmental enrichment and runtime settings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.app_lifecycle import AppLifecycleMixin
from accessiweather.cache_serialization import (
    _deserialize_environmental,
    _serialize_environmental,
)
from accessiweather.models import HourlyAirQuality, Location, WeatherData
from accessiweather.models.weather_conditions import EnvironmentalConditions
from accessiweather.services.airnow_client import AirNowObservation
from accessiweather.services.environmental_client import EnvironmentalDataClient
from accessiweather.weather_client import WeatherClient
from accessiweather.weather_client_enrichment import populate_environmental_metrics


def _location(*, country_code: str | None = "US") -> Location:
    if country_code == "GB":
        name, latitude, longitude = "London", 51.5074, -0.1278
    elif country_code == "MX":
        name, latitude, longitude = "Tijuana", 32.5149, -117.0382
    else:
        # Missing/blank codes deliberately use U.S. coordinates to prove that
        # coordinates alone cannot opt a location into AirNow.
        name, latitude, longitude = "Philadelphia", 39.9526, -75.1652
    return Location(
        name=name,
        latitude=latitude,
        longitude=longitude,
        country_code=country_code,
    )


class _FakeAirNowProvider:
    def __init__(self, observation: AirNowObservation | None) -> None:
        self.fetch_mock = AsyncMock(return_value=observation)

    async def fetch_current_air_quality(self, location: Location) -> AirNowObservation | None:
        return await self.fetch_mock(location)


@pytest.mark.asyncio
async def test_airnow_supplies_current_aqi_while_openmeteo_supplies_hourly_forecast():
    observed_at = datetime(2026, 7, 21, 14, tzinfo=timezone(timedelta(hours=-4)))
    airnow = _FakeAirNowProvider(
        AirNowObservation(
            aqi=87,
            category="Moderate",
            pollutant="PM2.5",
            observed_at=observed_at,
            reporting_area="Philadelphia",
        )
    )
    client = EnvironmentalDataClient(airnow_client=airnow)
    hourly = [
        {
            "timestamp": observed_at,
            "aqi": 55,
            "category": "Moderate",
            "pm2_5": 16.2,
        }
    ]

    with (
        patch.object(client, "_populate_air_quality", new_callable=AsyncMock) as fallback,
        patch.object(
            client,
            "fetch_hourly_air_quality",
            new_callable=AsyncMock,
            return_value=hourly,
        ),
    ):
        result = await client.fetch(
            _location(),
            include_air_quality=True,
            include_pollen=False,
            include_hourly_air_quality=True,
            include_hourly_uv=False,
            prefer_airnow=True,
        )

    assert result is not None
    assert result.air_quality_index == 87
    assert result.air_quality_category == "Moderate"
    assert result.air_quality_pollutant == "PM2.5"
    assert result.air_quality_updated_at == observed_at
    assert result.air_quality_reporting_area == "Philadelphia"
    assert result.air_quality_source == "EPA AirNow and participating agencies"
    assert result.hourly_air_quality == [
        HourlyAirQuality(
            timestamp=observed_at,
            aqi=55,
            category="Moderate",
            pm2_5=16.2,
        )
    ]
    assert result.sources == [
        "EPA AirNow and participating agencies",
        "Open-Meteo Air Quality",
    ]
    fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_airnow_failure_falls_back_to_openmeteo_current_aqi():
    airnow = _FakeAirNowProvider(None)
    client = EnvironmentalDataClient(airnow_client=airnow)
    observed_at = datetime(2026, 7, 21, 18, tzinfo=UTC)

    async def populate_fallback(_http_client, _params, environmental):
        environmental.air_quality_index = 44
        environmental.air_quality_category = "Good"
        environmental.air_quality_pollutant = "PM2_5"
        environmental.air_quality_updated_at = observed_at
        environmental.air_quality_source = "Open-Meteo Air Quality"
        environmental.sources.append("Open-Meteo Air Quality")

    async_context = AsyncMock()
    async_context.__aenter__ = AsyncMock(return_value=AsyncMock())
    async_context.__aexit__ = AsyncMock(return_value=None)
    with (
        patch(
            "accessiweather.services.environmental_client.httpx.AsyncClient",
            return_value=async_context,
        ),
        patch.object(
            client,
            "_populate_air_quality",
            new_callable=AsyncMock,
            side_effect=populate_fallback,
        ) as fallback,
    ):
        result = await client.fetch(
            _location(),
            include_air_quality=True,
            include_pollen=False,
            include_hourly_air_quality=False,
            include_hourly_uv=False,
            prefer_airnow=True,
        )

    assert result is not None
    assert result.air_quality_index == 44
    assert result.air_quality_source == "Open-Meteo Air Quality"
    assert "EPA AirNow and participating agencies" not in result.sources
    fallback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("country_code", "prefer_airnow"),
    [("US", True), ("us", True), ("GB", False), ("MX", False), ("", False), (None, False)],
)
async def test_weather_enrichment_requires_confirmed_us_country_code_for_airnow(
    country_code, prefer_airnow
):
    environmental = EnvironmentalConditions(air_quality_index=25)
    environmental_client = SimpleNamespace(fetch=AsyncMock(return_value=environmental))
    client = WeatherClient(environmental_client=environmental_client)
    client.air_quality_enabled = True
    client.pollen_enabled = False
    location = _location(country_code=country_code)
    weather_data = WeatherData(location=location)

    await populate_environmental_metrics(client, weather_data, location)

    assert weather_data.environmental is environmental
    assert environmental_client.fetch.await_args.kwargs["prefer_airnow"] is prefer_airnow
    assert environmental_client.fetch.await_args.kwargs["include_hourly_air_quality"] is True


def test_air_quality_provenance_round_trips_through_weather_cache():
    observed_at = datetime(2026, 7, 21, 14, tzinfo=timezone(timedelta(hours=-4)))
    environmental = EnvironmentalConditions(
        air_quality_index=87,
        air_quality_category="Moderate",
        air_quality_pollutant="PM2.5",
        air_quality_updated_at=observed_at,
        air_quality_reporting_area="Philadelphia",
        air_quality_source="EPA AirNow and participating agencies",
        sources=["EPA AirNow and participating agencies"],
    )

    restored = _deserialize_environmental(_serialize_environmental(environmental))

    assert restored is not None
    assert restored.air_quality_updated_at == observed_at
    assert restored.air_quality_reporting_area == "Philadelphia"
    assert restored.air_quality_source == "EPA AirNow and participating agencies"


def test_runtime_settings_replace_airnow_client_without_restart():
    settings = SimpleNamespace(
        data_source="auto",
        enable_alerts=True,
        air_quality_enabled=True,
        pollen_enabled=False,
        airnow_api_key="new-airnow-key",
    )
    environmental_client = MagicMock()
    weather_client = SimpleNamespace(
        settings=None,
        data_source="auto",
        alerts_enabled=True,
        air_quality_enabled=True,
        pollen_enabled=False,
        _pirate_weather_api_key="",
        _pirate_weather_client=None,
        _avwx_api_key="",
        _airnow_api_key="old-airnow-key",
        environmental_client=environmental_client,
        user_agent="AccessiWeather/2.0",
        timeout=10.0,
    )
    app = SimpleNamespace(
        config_manager=SimpleNamespace(get_settings=lambda: settings),
        weather_client=weather_client,
        presenter=None,
        _notifier=None,
        alert_notification_system=None,
        taskbar_icon_updater=None,
        _start_auto_update_checks=MagicMock(),
        _start_background_updates=MagicMock(),
    )

    AppLifecycleMixin.refresh_runtime_settings(app)

    assert weather_client._airnow_api_key == "new-airnow-key"
    environmental_client.set_airnow_api_key.assert_called_once_with("new-airnow-key")
