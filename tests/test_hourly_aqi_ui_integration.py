"""Tests for hourly AQI UI integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from accessiweather.handlers.weather_handlers import update_weather_displays
from accessiweather.models import (
    CurrentConditions,
    EnvironmentalConditions,
    HourlyAirQuality,
    Location,
    WeatherData,
)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_hourly_aqi_displayed_in_current_conditions():
    """Test that hourly AQI forecast is displayed in current conditions."""
    # Create mock app
    app = MagicMock()
    app.current_conditions_display = MagicMock()
    app.current_conditions_display.value = ""
    app.forecast_display = MagicMock()
    app.alerts_table = MagicMock()
    app.alert_details_button = MagicMock()
    app.alert_details_button.enabled = False
    app.config.settings.temperature_unit = "fahrenheit"
    app.config.settings.time_format_12hour = True
    app.current_alerts_data = None

    # Mock the presenter to return a simple presentation
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
    app.presenter.present.return_value = mock_presentation

    # Create weather data with hourly AQI
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

    # Update displays
    await update_weather_displays(app, weather_data)

    # Verify hourly forecast is in the display
    display_text = app.current_conditions_display.value
    assert "Hourly forecast:" in display_text
    assert "Current: AQI 50" in display_text
    assert "Good" in display_text


@pytest.mark.asyncio
@pytest.mark.unit
async def test_hourly_aqi_not_displayed_when_unavailable():
    """Test that hourly forecast section is omitted when no data."""
    app = MagicMock()
    app.current_conditions_display = MagicMock()
    app.current_conditions_display.value = ""
    app.forecast_display = MagicMock()
    app.alerts_table = MagicMock()
    app.alert_details_button = MagicMock()
    app.alert_details_button.enabled = False
    app.config.settings.temperature_unit = "fahrenheit"
    app.current_alerts_data = None

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
    app.presenter.present.return_value = mock_presentation

    location = Location(name="Test City", latitude=40.0, longitude=-74.0)

    # Environmental data without hourly forecast
    environmental = EnvironmentalConditions(
        air_quality_index=50.0,
        air_quality_category="Good",
        hourly_air_quality=[],  # Empty list
    )

    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(temperature_f=70.0, condition="Clear"),
        environmental=environmental,
    )

    await update_weather_displays(app, weather_data)

    display_text = app.current_conditions_display.value
    assert "Hourly forecast:" not in display_text


@pytest.mark.asyncio
@pytest.mark.unit
async def test_hourly_aqi_shows_trend_and_peak():
    """Test that hourly forecast shows trend analysis and peak times."""
    app = MagicMock()
    app.current_conditions_display = MagicMock()
    app.current_conditions_display.value = ""
    app.forecast_display = MagicMock()
    app.alerts_table = MagicMock()
    app.alert_details_button = MagicMock()
    app.alert_details_button.enabled = False
    app.config.settings.temperature_unit = "fahrenheit"
    app.config.settings.time_format_12hour = True
    app.current_alerts_data = None

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
    app.presenter.present.return_value = mock_presentation

    location = Location(name="Test City", latitude=40.0, longitude=-74.0)
    now = datetime.now(UTC)

    # Create worsening trend
    hourly_data = [
        HourlyAirQuality(timestamp=now, aqi=50, category="Good"),
        HourlyAirQuality(timestamp=now + timedelta(hours=1), aqi=75, category="Moderate"),
        HourlyAirQuality(timestamp=now + timedelta(hours=2), aqi=150, category="Unhealthy"),
        HourlyAirQuality(
            timestamp=now + timedelta(hours=3), aqi=125, category="Unhealthy for Sensitive Groups"
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
    assert "Hourly forecast:" in display_text
    assert "Trend:" in display_text
    assert "Peak:" in display_text or "150" in display_text
