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
    presenter = WeatherPresenter(AppSettings())
    return SimpleNamespace(
        presenter=presenter,
        current_conditions_display=DummyText(),
        forecast_display=DummyText(),
        alerts_table=DummyTable(),
        alert_details_button=DummyButton(),
        weather_history_service=None,
        alert_notification_system=None,
        refresh_button=None,
        current_alerts_data=None,
        _notifier=None,
        status_label=None,
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
    assert "Advice:" in current_text


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
