"""Unit tests for WeatherPresenter accuracy-sensitive output."""

import pytest

from accessiweather.display import WeatherPresenter
from datetime import datetime

from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    EnvironmentalConditions,
    Location,
    TrendInsight,
    WeatherData,
)


@pytest.mark.unit
def test_presenter_includes_precise_dewpoint_in_metrics():
    """Presenter should surface dewpoint derived from temperature and humidity."""
    settings = AppSettings(temperature_unit="both")
    presenter = WeatherPresenter(settings)
    location = Location(name="Test City", latitude=40.0, longitude=-75.0)

    conditions = CurrentConditions(
        temperature_f=77.0,
        humidity=65,
        feels_like_f=77.0,
        wind_speed_mph=5.0,
        wind_direction=180,
        pressure_in=30.0,
    )

    presentation = presenter.present_current(conditions, location)

    assert presentation is not None
    dewpoint_metric = next((m for m in presentation.metrics if m.label == "Dewpoint"), None)
    assert dewpoint_metric is not None
    assert "64°F (18°C)" in dewpoint_metric.value
    assert "Dewpoint: 64°F (18°C)" in presentation.fallback_text


@pytest.mark.unit
def test_presenter_reports_calm_wind_when_speed_is_zero():
    settings = AppSettings(temperature_unit="fahrenheit")
    presenter = WeatherPresenter(settings)
    location = Location(name="Calm Town", latitude=0.0, longitude=0.0)
    conditions = CurrentConditions(
        temperature_f=70.0,
        condition="Clear",
        wind_speed_mph=0.0,
        wind_direction=45,
    )

    presentation = presenter.present_current(conditions, location)

    assert presentation is not None
    wind_metric = next((m for m in presentation.metrics if m.label == "Wind"), None)
    assert wind_metric is not None
    assert wind_metric.value == "Calm"
    assert "Wind: Calm" in presentation.fallback_text


@pytest.mark.unit
def test_presenter_includes_environmental_metrics():
    settings = AppSettings(temperature_unit="fahrenheit")
    presenter = WeatherPresenter(settings)
    location = Location(name="Env City", latitude=35.0, longitude=-90.0)
    conditions = CurrentConditions(temperature_f=70.0, condition="Sunny")
    env = EnvironmentalConditions(
        air_quality_index=105,
        air_quality_category="Unhealthy for Sensitive Groups",
        air_quality_pollutant="PM2.5",
        pollen_index=75,
        pollen_category="High",
        pollen_primary_allergen="Tree",
    )

    presentation = presenter.present_current(conditions, location, environmental=env)

    assert presentation is not None
    aq_metric = next((m for m in presentation.metrics if m.label == "Air Quality"), None)
    assert aq_metric is not None
    assert "105" in aq_metric.value
    pollen_metric = next((m for m in presentation.metrics if m.label == "Pollen"), None)
    assert pollen_metric is not None
    assert "High" in pollen_metric.value


@pytest.mark.unit
def test_presenter_includes_trend_summary_and_status():
    settings = AppSettings()
    presenter = WeatherPresenter(settings)
    location = Location(name="Trend Town", latitude=10.0, longitude=20.0)
    weather_data = WeatherData(location=location, current=CurrentConditions(condition="Clear"))
    weather_data.trend_insights = [
        TrendInsight(
            metric="temperature",
            direction="rising",
            change=4.0,
            unit="°F",
            timeframe_hours=24,
            summary="Temperature rising +4.0°F over 24h",
        )
    ]
    weather_data.stale = True
    weather_data.stale_since = datetime(2025, 1, 1, 12, 0)
    presentation = presenter.present(weather_data)

    assert presentation.trend_summary
    assert presentation.trend_summary[0].startswith("Temperature rising")
    assert presentation.status_messages
    assert "cached" in presentation.status_messages[0].lower()
