"""Tests for weather display updates with embedded air quality context."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from accessiweather.display import WeatherPresenter
from accessiweather.handlers.weather_handlers import update_weather_displays
from accessiweather.models import (
    AppSettings,
    AviationData,
    CurrentConditions,
    EnvironmentalConditions,
    Location,
    WeatherData,
)

# Ensure Toga uses the dummy backend for tests interacting with UI widgets.
os.environ.setdefault("TOGA_BACKEND", "toga_dummy")


@dataclass(slots=True)
class DummyText:
    """Simple text widget substitute for tests."""

    value: str = ""


@dataclass(slots=True)
class DummyTable:
    """Simple table widget substitute for tests."""

    data: list = None

    def __post_init__(self):
        if self.data is None:
            self.data = []


@dataclass(slots=True)
class DummyButton:
    """Simple button widget substitute for tests."""

    enabled: bool = False


def _create_app():
    """Create a lightweight app stub with the fields used by update_weather_displays."""
    from unittest.mock import Mock

    settings = AppSettings()
    presenter = WeatherPresenter(settings)

    # Mock main_window to make the window appear "visible" for tests
    mock_window = Mock()
    mock_window.visible = True

    # Mock config_manager to provide settings
    mock_config_manager = Mock()
    mock_config = Mock()
    mock_config.settings = settings
    mock_config_manager.get_config.return_value = mock_config

    return SimpleNamespace(
        presenter=presenter,
        config_manager=mock_config_manager,
        current_conditions_display=DummyText(),
        forecast_display=DummyText(),
        aviation_display=DummyText(),
        alerts_table=DummyTable(),
        alert_details_button=DummyButton(),
        weather_history_service=None,
        alert_notification_system=None,
        refresh_button=None,
        current_alerts_data=None,
        _notifier=None,
        status_label=None,
        main_window=mock_window,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_weather_displays_embeds_air_quality_details():
    app = _create_app()
    assert not hasattr(app, "air_quality_display")
    location = Location(name="AQ Town", latitude=40.0, longitude=-74.0)
    environmental = EnvironmentalConditions(
        air_quality_index=135,
        air_quality_category="Unhealthy for Sensitive Groups",
        air_quality_pollutant="PM2_5",
        updated_at=datetime(2025, 1, 1, 15, 0, tzinfo=UTC),
        sources=["Open-Meteo Air Quality"],
    )

    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(condition="Clear", temperature_f=72.0),
        environmental=environmental,
    )

    await update_weather_displays(app, weather_data)

    current_text = app.current_conditions_display.value
    assert "Air Quality:" in current_text
    assert "AQI 135" in current_text
    assert "Unhealthy for Sensitive Groups" in current_text


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_weather_displays_handles_missing_air_quality():
    app = _create_app()
    assert not hasattr(app, "air_quality_display")
    location = Location(name="No AQ City", latitude=10.0, longitude=20.0)
    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(condition="Cloudy", temperature_f=65.0),
        environmental=EnvironmentalConditions(),  # No air quality data
    )

    await update_weather_displays(app, weather_data)

    assert "Air Quality:" not in app.current_conditions_display.value


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_weather_displays_populates_aviation_summary():
    app = _create_app()
    location = Location(name="Flight Town", latitude=39.8561, longitude=-104.6737)
    weather_data = WeatherData(
        location=location,
        aviation=AviationData(
            raw_taf="TAF KDEN 010000Z 0100/0206 34010KT P6SM FEW080",
            station_id="KDEN",
            airport_name="Denver International",
        ),
    )

    await update_weather_displays(app, weather_data)

    aviation_text = app.aviation_display.value
    assert "Aviation weather for" in aviation_text
    assert "Terminal Aerodrome Forecast" in aviation_text
    assert "KDEN" in aviation_text


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_weather_displays_omits_placeholders_when_sections_missing():
    app = _create_app()
    location = Location(name="Partial Town", latitude=35.0, longitude=-120.0)
    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(condition="Clear", temperature_f=70.0),
        forecast=None,
        alerts=None,
        aviation=None,
    )

    await update_weather_displays(app, weather_data)

    assert "No forecast data available" not in app.forecast_display.value
    assert app.forecast_display.value == ""
    assert "No aviation data available" not in app.aviation_display.value
    assert app.aviation_display.value == ""


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_weather_displays_clears_aviation_after_nil_response():
    app = _create_app()
    location = Location(name="Aviation City", latitude=33.6367, longitude=-84.4281)

    initial_weather = WeatherData(
        location=location,
        aviation=AviationData(
            raw_taf="TAF KATL 010000Z 0100/0206 20010KT P6SM SCT050",
            decoded_taf="Forecast for station KATL. Winds 200 at 10 knots.",
            station_id="KATL",
            airport_name="Hartsfield-Jackson Atlanta",
        ),
    )

    await update_weather_displays(app, initial_weather)
    assert app.aviation_display.value
    assert "Terminal Aerodrome Forecast" in app.aviation_display.value

    nil_weather = WeatherData(
        location=location,
        aviation=AviationData(station_id="KATL", airport_name="Hartsfield-Jackson Atlanta"),
    )

    await update_weather_displays(app, nil_weather)

    assert app.aviation_display.value == ""
