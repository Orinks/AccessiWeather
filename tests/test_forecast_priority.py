"""Tests for priority ordering in forecast presentation."""

from datetime import UTC, datetime

import pytest

from accessiweather.display.presentation.forecast import build_forecast, build_hourly_summary
from accessiweather.models import (
    AppSettings,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
)
from accessiweather.utils import TemperatureUnit


class TestForecastPriority:
    """Test priority ordering in forecast presentation."""

    @pytest.fixture
    def location(self):
        return Location(name="Test City", latitude=40.0, longitude=-75.0)

    @pytest.fixture
    def forecast(self):
        return Forecast(
            periods=[
                ForecastPeriod(
                    name="Today",
                    temperature=75,
                    temperature_unit="F",
                    short_forecast="Sunny",
                    wind_speed="10 mph",
                    wind_direction="NW",
                    precipitation_probability=20,
                    uv_index=6,
                )
            ],
            generated_at=datetime.now(UTC),
        )

    @pytest.fixture
    def hourly_forecast(self):
        return HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=datetime.now(UTC),
                    temperature=75.0,
                    short_forecast="Sunny",
                    wind_speed="10 mph",
                    wind_direction="NW",
                    precipitation_probability=20,
                )
            ]
        )

    def test_minimal_verbosity_forecast(self, location, forecast, hourly_forecast):
        """Minimal verbosity should reduce forecast detail."""
        settings = AppSettings(verbosity_level="minimal")
        result = build_forecast(
            forecast,
            hourly_forecast,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        # Should have basic info
        assert result.periods[0].temperature is not None
        # Fallback text should be shorter
        assert len(result.fallback_text) < 500
        # Minimal should not include wind, precipitation, uv_index in periods
        assert result.periods[0].wind is None
        assert result.periods[0].precipitation_probability is None
        assert result.periods[0].uv_index is None

    def test_detailed_verbosity_forecast(self, location, forecast, hourly_forecast):
        """Detailed verbosity should include all forecast info."""
        settings = AppSettings(verbosity_level="detailed")
        result = build_forecast(
            forecast,
            hourly_forecast,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        # Should have all available fields
        assert result.periods[0].temperature is not None
        assert result.periods[0].wind is not None
        assert result.periods[0].precipitation_probability is not None
        assert result.periods[0].uv_index is not None

    def test_standard_verbosity_forecast(self, location, forecast, hourly_forecast):
        """Standard verbosity should include temperature, conditions, wind, precipitation."""
        settings = AppSettings(verbosity_level="standard")
        result = build_forecast(
            forecast,
            hourly_forecast,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        # Standard includes temp, conditions, wind, precipitation
        assert result.periods[0].temperature is not None
        assert result.periods[0].conditions is not None
        assert result.periods[0].wind is not None
        assert result.periods[0].precipitation_probability is not None
        # Standard should not include UV index
        assert result.periods[0].uv_index is None

    def test_minimal_verbosity_hourly(self, hourly_forecast):
        """Minimal verbosity should reduce hourly detail."""
        settings = AppSettings(verbosity_level="minimal")
        result = build_hourly_summary(
            hourly_forecast,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        # Should have basic info
        assert len(result) > 0
        assert result[0].temperature is not None
        # Minimal should not include wind, precipitation
        assert result[0].wind is None
        assert result[0].precipitation_probability is None

    def test_detailed_verbosity_hourly(self, hourly_forecast):
        """Detailed verbosity should include all hourly info."""
        settings = AppSettings(verbosity_level="detailed")
        result = build_hourly_summary(
            hourly_forecast,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        # Should have all available fields
        assert len(result) > 0
        assert result[0].temperature is not None
        assert result[0].wind is not None
        assert result[0].precipitation_probability is not None

    def test_default_verbosity_is_standard(self, location, forecast, hourly_forecast):
        """Default verbosity (no settings) should behave like standard."""
        # No settings passed - should use standard behavior
        result = build_forecast(
            forecast,
            hourly_forecast,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=None,
        )
        # Standard includes temp, conditions, wind, precipitation
        assert result.periods[0].temperature is not None
        assert result.periods[0].conditions is not None
        assert result.periods[0].wind is not None
        assert result.periods[0].precipitation_probability is not None
