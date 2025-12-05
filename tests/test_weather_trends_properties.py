"""Property tests for weather trend logic."""

from __future__ import annotations

from hypothesis import (
    given,
    strategies as st,
)

from accessiweather.models import Forecast, ForecastPeriod, Location, WeatherData
from accessiweather.weather_client_trends import compute_daily_trend

# Strategy for valid Fahrenheit temperatures
temp_strategy = st.floats(min_value=-100.0, max_value=150.0, allow_nan=False, allow_infinity=False)


@given(today_temp=temp_strategy, yesterday_temp=temp_strategy)
def test_compute_daily_trend_properties(today_temp, yesterday_temp):
    """Verify daily trend logic holds true for any valid pair of temperatures."""
    # Setup mock data
    weather_data = WeatherData(location=Location(name="Test", latitude=0, longitude=0))

    weather_data.forecast = Forecast(
        periods=[ForecastPeriod(name="Today", temperature=today_temp, temperature_unit="F")]
    )

    weather_data.daily_history = [
        ForecastPeriod(name="Yesterday", temperature=yesterday_temp, temperature_unit="F")
    ]

    # Execute
    insight = compute_daily_trend(weather_data)

    # Verification
    assert insight is not None
    assert insight.metric == "daily_trend"

    diff = today_temp - yesterday_temp

    # Floating point comparison tolerance
    assert abs(insight.change - diff) < 0.11  # Rounded to 1 decimal place in implementation

    if diff > 2.0:
        assert insight.direction == "warmer"
        assert "warmer" in insight.summary.lower()
    elif diff < -2.0:
        assert insight.direction == "cooler"
        assert "cooler" in insight.summary.lower()
    else:
        assert insight.direction == "similar"
        assert "similar" in insight.summary.lower()
