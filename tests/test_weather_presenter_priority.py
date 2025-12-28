"""Tests for priority ordering in WeatherPresenter."""

import pytest

from accessiweather.display.weather_presenter import WeatherPresenter
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)


class TestWeatherPresenterPriority:
    """Test WeatherPresenter uses priority ordering."""

    @pytest.mark.unit
    def test_presenter_passes_alerts_to_current_conditions(self):
        """
        WeatherPresenter should pass alerts for priority calculation.

        When there's a High Wind Warning, the wind category should be
        prioritized before temperature in the metrics list.
        """
        settings = AppSettings(severe_weather_override=True)
        presenter = WeatherPresenter(settings)

        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed_mph=15,
            condition="Windy",
        )
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

        weather_data = WeatherData(
            location=location,
            current=current,
            alerts=alerts,
        )

        result = presenter.present(weather_data)
        # Wind should be prioritized in the metrics
        metric_labels = [m.label for m in result.current_conditions.metrics]
        wind_idx = next((i for i, label in enumerate(metric_labels) if "Wind" in label), 999)
        temp_idx = next((i for i, label in enumerate(metric_labels) if "Temperature" in label), 999)

        # With a High Wind Warning and severe_weather_override=True,
        # wind should appear before temperature
        assert wind_idx < temp_idx, (
            f"Wind should be prioritized before temperature with High Wind Warning. "
            f"Got wind at index {wind_idx}, temperature at index {temp_idx}. "
            f"Metric order: {metric_labels}"
        )

    @pytest.mark.unit
    def test_present_current_passes_alerts_for_priority(self):
        """present_current should accept alerts for priority calculation."""
        settings = AppSettings(severe_weather_override=True)
        presenter = WeatherPresenter(settings)

        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed_mph=15,
            condition="Windy",
        )
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

        result = presenter.present_current(current, location, alerts=alerts)

        # Wind should be prioritized in the metrics
        metric_labels = [m.label for m in result.metrics]
        wind_idx = next((i for i, label in enumerate(metric_labels) if "Wind" in label), 999)
        temp_idx = next((i for i, label in enumerate(metric_labels) if "Temperature" in label), 999)

        # With a High Wind Warning and severe_weather_override=True,
        # wind should appear before temperature
        assert wind_idx < temp_idx, (
            f"Wind should be prioritized before temperature with High Wind Warning. "
            f"Got wind at index {wind_idx}, temperature at index {temp_idx}. "
            f"Metric order: {metric_labels}"
        )
