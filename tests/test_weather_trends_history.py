"""Tests for weather trend history integration."""

from accessiweather.models import Forecast, ForecastPeriod, WeatherData
from accessiweather.weather_client_trends import compute_daily_trend


def test_daily_trend_warmer():
    """Test that daily trend detects warmer temperatures."""
    weather_data = WeatherData(location=None)

    # Today: 75F
    weather_data.forecast = Forecast(
        periods=[ForecastPeriod(name="Today", temperature=75.0, temperature_unit="F")]
    )

    # Yesterday: 70F
    weather_data.daily_history = [
        ForecastPeriod(name="Yesterday", temperature=70.0, temperature_unit="F")
    ]

    insight = compute_daily_trend(weather_data)

    assert insight is not None
    assert insight.direction == "warmer"
    assert insight.change == 5.0
    assert "5°F warmer than yesterday" in insight.summary


def test_daily_trend_cooler():
    """Test that daily trend detects cooler temperatures."""
    weather_data = WeatherData(location=None)

    # Today: 65F
    weather_data.forecast = Forecast(
        periods=[ForecastPeriod(name="Today", temperature=65.0, temperature_unit="F")]
    )

    # Yesterday: 70F
    weather_data.daily_history = [
        ForecastPeriod(name="Yesterday", temperature=70.0, temperature_unit="F")
    ]

    insight = compute_daily_trend(weather_data)

    assert insight is not None
    assert insight.direction == "cooler"
    assert insight.change == -5.0
    assert "5°F cooler than yesterday" in insight.summary


def test_daily_trend_similar():
    """Test that daily trend detects similar temperatures."""
    weather_data = WeatherData(location=None)

    # Today: 71F
    weather_data.forecast = Forecast(
        periods=[ForecastPeriod(name="Today", temperature=71.0, temperature_unit="F")]
    )

    # Yesterday: 70F
    weather_data.daily_history = [
        ForecastPeriod(name="Yesterday", temperature=70.0, temperature_unit="F")
    ]

    insight = compute_daily_trend(weather_data)

    assert insight is not None
    # Change is small (1.0 < 2.0 threshold)
    assert insight.direction == "similar"
    assert "Temperatures similar to yesterday" in insight.summary


def test_daily_trend_missing_data():
    """Test response when data is missing."""
    weather_data = WeatherData(location=None)

    # No history
    assert compute_daily_trend(weather_data) is None

    # No forecast
    weather_data.daily_history = [ForecastPeriod(name="Yesterday", temperature=70.0)]
    assert compute_daily_trend(weather_data) is None
