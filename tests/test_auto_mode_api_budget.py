from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models.config import AppSettings
from accessiweather.models.weather import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    WeatherAlerts,
)
from accessiweather.ui.dialogs.settings_tabs.data_sources import DataSourcesTab
from accessiweather.weather_client import WeatherClient
from accessiweather.weather_client_parallel import ParallelFetchCoordinator


class _FakeChoice:
    def __init__(self, selection: int = 0):
        self.selection = selection
        self.name = None

    def SetSelection(self, selection: int) -> None:
        self.selection = selection

    def GetSelection(self) -> int:
        return self.selection

    def SetName(self, name: str) -> None:
        self.name = name


class _FakeTextCtrl:
    def __init__(self, value: str = ""):
        self.value = value
        self.name = None

    def SetValue(self, value: str) -> None:
        self.value = value

    def GetValue(self) -> str:
        return self.value

    def Bind(self, *_args, **_kwargs) -> None:
        return None

    def SetName(self, name: str) -> None:
        self.name = name


class _FakeDialog:
    def __init__(self):
        self._controls = {
            "data_source": _FakeChoice(),
            "vc_key": _FakeTextCtrl(),
            "pw_key": _FakeTextCtrl(),
            "source_settings_summary": _FakeTextCtrl(),
            "configure_source_settings": _FakeChoice(),
        }
        self._source_settings_states = DataSourcesTab._build_default_source_settings_states()
        self._original_vc_key = ""
        self._original_pw_key = ""
        self._vc_key_cleared = False
        self._pw_key_cleared = False
        self.api_visibility_updates = 0

    def _update_api_key_visibility(self) -> None:
        self.api_visibility_updates += 1

    def _update_auto_source_key_state(self) -> None:
        return None


@pytest.fixture
def us_location() -> Location:
    return Location(name="New York", latitude=40.7128, longitude=-74.0060, country_code="US")


@pytest.fixture
def intl_location() -> Location:
    return Location(name="London", latitude=51.5074, longitude=-0.1278, country_code="GB")


def _forecast(label: str = "Today") -> Forecast:
    return Forecast(periods=[ForecastPeriod(name=label, temperature=70)])


def _hourly() -> HourlyForecast:
    return HourlyForecast(
        periods=[HourlyForecastPeriod(start_time=datetime.now(UTC), temperature=70)]
    )


def _current() -> CurrentConditions:
    return CurrentConditions(temperature_f=70.0, condition="Sunny")


async def _execute_fetch_all(self, location, **kwargs):
    results = []
    for name, coro in kwargs.items():
        if coro is None:
            continue
        results.append(self._create_source_data(name.removeprefix("fetch_"), await coro))
    return results


def _stub_enrichments(client: WeatherClient) -> None:
    client._launch_enrichment_tasks = MagicMock(return_value={})
    client._await_enrichments = AsyncMock(return_value=None)
    client._fetch_nws_cancel_references = AsyncMock(return_value=set())


def test_auto_mode_api_budget_defaults_and_round_trips() -> None:
    settings = AppSettings()
    assert settings.auto_mode_api_budget == "economy"

    restored = AppSettings.from_dict(settings.to_dict())
    assert restored.auto_mode_api_budget == "economy"

    restored.auto_mode_api_budget = "nope"
    assert restored.validate_on_access("auto_mode_api_budget") is True
    assert restored.auto_mode_api_budget == "economy"


def test_data_sources_tab_budget_load_save_round_trip() -> None:
    dialog = _FakeDialog()
    tab = DataSourcesTab(dialog)
    settings = AppSettings(
        auto_mode_api_budget="balanced",
        data_source="auto",
        source_priority_us=["nws", "openmeteo"],
        source_priority_international=["openmeteo", "pirateweather"],
        auto_sources_us=["nws", "openmeteo"],
        auto_sources_international=["openmeteo", "pirateweather"],
        station_selection_strategy="major_airport_preferred",
    )

    tab.load(settings)
    saved = tab.save()

    assert dialog._source_settings_states["auto_mode_api_budget"] == 1
    assert saved["auto_mode_api_budget"] == "balanced"
    assert saved["auto_sources_us"] == ["nws", "openmeteo", "pirateweather"]
    assert saved["auto_sources_international"] == ["openmeteo", "pirateweather"]
    assert "Automatic mode budget: Balanced." in tab._get_source_settings_summary_text()


@pytest.mark.asyncio
async def test_economy_us_fetches_nws_then_openmeteo_for_extended_forecast(
    us_location: Location,
) -> None:
    settings = AppSettings(
        auto_mode_api_budget="economy",
        forecast_duration_days=10,
    )
    client = WeatherClient(data_source="auto", settings=settings)
    _stub_enrichments(client)
    client._fetch_nws_data = AsyncMock(
        return_value=(_current(), _forecast("NWS"), None, None, WeatherAlerts(alerts=[]), _hourly())
    )
    client._fetch_openmeteo_data = AsyncMock(return_value=(_current(), _forecast("OM"), _hourly()))
    client._visual_crossing_client = MagicMock()
    client._visual_crossing_client.get_current_conditions = AsyncMock(return_value=_current())
    client._visual_crossing_client.get_forecast = AsyncMock(return_value=_forecast("VC"))
    client._visual_crossing_client.get_hourly_forecast = AsyncMock(return_value=_hourly())
    client._visual_crossing_client.get_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))

    calls: list[list[str]] = []

    async def _recording_fetch_all(self, location, **kwargs):
        calls.append(
            [name.removeprefix("fetch_") for name, coro in kwargs.items() if coro is not None]
        )
        return await _execute_fetch_all(self, location, **kwargs)

    with patch.object(ParallelFetchCoordinator, "fetch_all", new=_recording_fetch_all):
        result = await client._fetch_smart_auto_source(us_location)

    assert calls == [["nws"], ["openmeteo"]]
    assert client._fetch_nws_data.await_count == 1
    assert client._fetch_openmeteo_data.await_count == 1
    client._visual_crossing_client.get_current_conditions.assert_not_called()
    assert result.source_attribution is not None
    assert "nws" in result.source_attribution.contributing_sources
    assert "openmeteo" in result.source_attribution.contributing_sources


@pytest.mark.asyncio
async def test_economy_us_skips_pw_and_vc_when_nws_is_sufficient(us_location: Location) -> None:
    settings = AppSettings(auto_mode_api_budget="economy", forecast_duration_days=7)
    client = WeatherClient(data_source="auto", settings=settings)
    _stub_enrichments(client)
    client._fetch_nws_data = AsyncMock(
        return_value=(_current(), _forecast("NWS"), None, None, WeatherAlerts(alerts=[]), _hourly())
    )
    client._fetch_openmeteo_data = AsyncMock(return_value=(_current(), _forecast("OM"), _hourly()))

    vc_client = MagicMock()
    vc_client.get_current_conditions = AsyncMock(return_value=_current())
    vc_client.get_forecast = AsyncMock(return_value=_forecast("VC"))
    vc_client.get_hourly_forecast = AsyncMock(return_value=_hourly())
    vc_client.get_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
    client._visual_crossing_client = vc_client

    with patch.object(ParallelFetchCoordinator, "fetch_all", new=_execute_fetch_all):
        await client._fetch_smart_auto_source(us_location)

    client._fetch_openmeteo_data.assert_not_called()
    vc_client.get_current_conditions.assert_not_called()


@pytest.mark.asyncio
async def test_balanced_us_can_use_one_non_openmeteo_secondary_when_needed(
    us_location: Location,
) -> None:
    settings = AppSettings(
        auto_mode_api_budget="balanced",
        auto_sources_us=["nws", "visualcrossing"],
        forecast_duration_days=7,
    )
    client = WeatherClient(
        data_source="auto", settings=settings, visual_crossing_api_key="test-key"
    )
    _stub_enrichments(client)
    client._fetch_nws_data = AsyncMock(
        return_value=(None, _forecast("NWS"), None, None, WeatherAlerts(alerts=[]), None)
    )

    vc_client = MagicMock()
    vc_client.get_current_conditions = AsyncMock(return_value=_current())
    vc_client.get_forecast = AsyncMock(return_value=_forecast("VC"))
    vc_client.get_hourly_forecast = AsyncMock(return_value=_hourly())
    vc_client.get_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
    client._visual_crossing_client = vc_client

    calls: list[list[str]] = []

    async def _recording_fetch_all(self, location, **kwargs):
        calls.append(
            [name.removeprefix("fetch_") for name, coro in kwargs.items() if coro is not None]
        )
        return await _execute_fetch_all(self, location, **kwargs)

    with patch.object(ParallelFetchCoordinator, "fetch_all", new=_recording_fetch_all):
        result = await client._fetch_smart_auto_source(us_location)

    assert calls == [["nws"], ["visualcrossing"]]
    vc_client.get_current_conditions.assert_awaited_once()
    assert result.source_attribution is not None
    assert "visualcrossing" in result.source_attribution.contributing_sources


@pytest.mark.asyncio
async def test_notification_event_data_keeps_pirate_weather_minutely_path(
    intl_location: Location,
) -> None:
    settings = AppSettings(notify_minutely_precipitation_start=True)
    client = WeatherClient(data_source="auto", settings=settings, pirate_weather_api_key="test-key")

    vc_client = MagicMock()
    vc_client.get_current_conditions = AsyncMock(return_value=_current())
    vc_client.get_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
    client._visual_crossing_client = vc_client

    pw_client = MagicMock()
    client._pirate_weather_client = pw_client
    client._get_pirate_weather_minutely = AsyncMock(
        return_value=SimpleNamespace(summary="rain soon")
    )

    result = await client.get_notification_event_data(intl_location)

    vc_client.get_current_conditions.assert_awaited_once_with(intl_location)
    vc_client.get_alerts.assert_awaited_once_with(intl_location)
    client._get_pirate_weather_minutely.assert_awaited_once_with(intl_location)
    assert result.minutely_precipitation is not None
