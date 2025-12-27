"""Tests for priority ordering in current conditions presentation."""

import pytest

from accessiweather.display.presentation.current_conditions import build_current_conditions
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Location,
    WeatherAlert,
    WeatherAlerts,
)
from accessiweather.utils import TemperatureUnit


class TestCurrentConditionsPriority:
    """Test priority ordering in current conditions."""

    @pytest.fixture
    def location(self):
        return Location(name="Test City", latitude=40.0, longitude=-75.0)

    @pytest.fixture
    def current_conditions(self):
        return CurrentConditions(
            temperature_f=75.0,
            temperature_c=24.0,
            feels_like_f=78.0,
            humidity=65,
            wind_speed=15,
            wind_direction="NW",
            pressure_in=30.1,
            visibility_miles=10.0,
            uv_index=6,
            condition="Partly Cloudy",
        )

    def test_minimal_verbosity_reduces_metrics(self, location, current_conditions):
        """Minimal verbosity should show fewer metrics."""
        settings = AppSettings(verbosity_level="minimal")
        result = build_current_conditions(
            current_conditions,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        # Should have temperature but not feels_like as separate metric
        metric_labels = [m.label for m in result.metrics]
        assert "Temperature" in metric_labels
        # In minimal mode, feels_like should not appear as separate metric
        assert len(result.metrics) < 10  # Fewer than detailed

    def test_detailed_verbosity_includes_more_metrics(self, location, current_conditions):
        """Detailed verbosity should include all available metrics."""
        settings = AppSettings(verbosity_level="detailed")
        result = build_current_conditions(
            current_conditions,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        metric_labels = [m.label for m in result.metrics]
        assert "Temperature" in metric_labels
        assert len(result.metrics) > 5  # More comprehensive

    def test_wind_alert_reorders_metrics(self, location, current_conditions):
        """Wind alert should put wind info near the top."""
        settings = AppSettings(severe_weather_override=True)
        alerts = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="High Wind Warning",
                    description="Dangerous winds",
                    event="High Wind Warning",
                    severity="Severe",
                )
            ]
        )
        result = build_current_conditions(
            current_conditions,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
            alerts=alerts,
        )
        metric_labels = [m.label for m in result.metrics]
        # Wind should appear in first 3 metrics
        wind_idx = next(i for i, label in enumerate(metric_labels) if "Wind" in label)
        assert wind_idx < 3

    def test_custom_category_order_respected(self, location, current_conditions):
        """Custom category order should affect metric ordering."""
        settings = AppSettings(category_order=["wind", "temperature", "precipitation"])
        result = build_current_conditions(
            current_conditions,
            location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        metric_labels = [m.label for m in result.metrics]
        # Wind should come before temperature
        wind_idx = next((i for i, label in enumerate(metric_labels) if "Wind" in label), 999)
        temp_idx = next((i for i, label in enumerate(metric_labels) if "Temperature" in label), 999)
        assert wind_idx < temp_idx
