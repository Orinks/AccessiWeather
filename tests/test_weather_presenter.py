"""Unit tests for WeatherPresenter accuracy-sensitive output."""

import pytest

from accessiweather.display import WeatherPresenter
from accessiweather.models import AppSettings, CurrentConditions, Location


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
