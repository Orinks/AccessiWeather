"""Unit tests for DetailedWeatherFormatter accuracy-sensitive output."""

import pytest

from accessiweather.display import DetailedWeatherFormatter
from accessiweather.models import AppSettings, CurrentConditions, Location


@pytest.mark.unit
def test_detailed_formatter_includes_precise_dewpoint():
    """Formatter should surface dewpoint derived from temperature and humidity."""
    settings = AppSettings(temperature_unit="both")
    formatter = DetailedWeatherFormatter(settings)
    location = Location(name="Test City", latitude=40.0, longitude=-75.0)

    conditions = CurrentConditions(
        temperature_f=77.0,
        humidity=65,
        feels_like_f=77.0,
        wind_speed_mph=5.0,
        wind_direction=180,
        pressure_in=30.0,
    )

    formatted = formatter.format_current_conditions(conditions, location)

    assert "Dewpoint: 64°F (18°C)" in formatted
