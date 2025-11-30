"""
Tests for hourly AQI UI integration.

The Current Conditions now displays a brief air quality summary.
Detailed hourly forecast is shown in the dedicated Air Quality Dialog.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock

import pytest

from accessiweather.handlers.weather_handlers import update_weather_displays
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    EnvironmentalConditions,
    HourlyAirQuality,
    Location,
    WeatherData,
)


def _create_mock_app():
    """Create a mock app with config_manager."""
    app = MagicMock()
    app.current_conditions_display = MagicMock()
    app.current_conditions_display.value = ""
    app.forecast_display = MagicMock()
    app.alerts_table = MagicMock()
    app.alert_details_button = MagicMock()
    app.alert_details_button.enabled = False
    app.current_alerts_data = None

    # Mock config_manager
    mock_config_manager = Mock()
    mock_config = Mock()
    mock_config.settings = AppSettings()
    mock_config_manager.get_config.return_value = mock_config
    app.config_manager = mock_config_manager

    # Mock the presenter
    app.presenter = MagicMock()
    mock_presentation = MagicMock()
    mock_presentation.current_conditions = MagicMock()
    mock_presentation.current_conditions.fallback_text = "Temperature: 70°F"
    mock_presentation.forecast = None
    mock_presentation.aviation = None
    mock_presentation.air_quality = MagicMock()
    mock_presentation.air_quality.summary = "AQI 50 (Good)"
    mock_presentation.air_quality.guidance = "Air quality is satisfactory"
    mock_presentation.air_quality.updated_at = None
    mock_presentation.air_quality.sources = []
    mock_presentation.status_messages = []
    app.presenter.present.return_value = mock_presentation

    return app


@pytest.mark.asyncio
@pytest.mark.unit
async def test_brief_aqi_displayed_in_current_conditions():
    """Test that brief AQI summary is displayed in current conditions."""
    app = _create_mock_app()

    location = Location(name="Test City", latitude=40.0, longitude=-74.0)
    now = datetime.now(UTC)

    hourly_data = [
        HourlyAirQuality(timestamp=now, aqi=50, category="Good"),
        HourlyAirQuality(timestamp=now + timedelta(hours=1), aqi=75, category="Moderate"),
        HourlyAirQuality(
            timestamp=now + timedelta(hours=2), aqi=125, category="Unhealthy for Sensitive Groups"
        ),
    ]

    environmental = EnvironmentalConditions(
        air_quality_index=50.0,
        air_quality_category="Good",
        hourly_air_quality=hourly_data,
    )

    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(temperature_f=70.0, condition="Clear"),
        environmental=environmental,
    )

    await update_weather_displays(app, weather_data)

    display_text = app.current_conditions_display.value
    assert "Air Quality:" in display_text
    assert "AQI: 50" in display_text
    assert "Good" in display_text


@pytest.mark.asyncio
@pytest.mark.unit
async def test_aqi_not_displayed_when_unavailable():
    """Test that air quality section is omitted when no data."""
    app = _create_mock_app()

    location = Location(name="Test City", latitude=40.0, longitude=-74.0)

    environmental = EnvironmentalConditions(
        air_quality_index=None,
        air_quality_category=None,
        hourly_air_quality=[],
    )

    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(temperature_f=70.0, condition="Clear"),
        environmental=environmental,
    )

    await update_weather_displays(app, weather_data)

    display_text = app.current_conditions_display.value
    assert "Air Quality:" not in display_text


@pytest.mark.asyncio
@pytest.mark.unit
async def test_brief_aqi_shows_trend():
    """Test that brief AQI shows trend indicator from hourly data."""
    app = _create_mock_app()

    location = Location(name="Test City", latitude=40.0, longitude=-74.0)
    now = datetime.now(UTC)

    hourly_data = [
        HourlyAirQuality(timestamp=now, aqi=50, category="Good"),
        HourlyAirQuality(timestamp=now + timedelta(hours=1), aqi=75, category="Moderate"),
        HourlyAirQuality(timestamp=now + timedelta(hours=2), aqi=150, category="Unhealthy"),
    ]

    environmental = EnvironmentalConditions(
        air_quality_index=50.0,
        air_quality_category="Good",
        hourly_air_quality=hourly_data,
    )

    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(temperature_f=70.0, condition="Clear"),
        environmental=environmental,
    )

    await update_weather_displays(app, weather_data)

    display_text = app.current_conditions_display.value
    assert "Air Quality:" in display_text
    assert "Worsening" in display_text
