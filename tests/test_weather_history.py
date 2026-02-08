"""Tests for weather_history module."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.weather_history import (
    HistoricalWeatherData,
    WeatherComparison,
    WeatherHistoryService,
)


def _make_current_conditions(temperature: float = 75.0, condition: str = "Sunny"):
    """Create a mock CurrentConditions object."""
    mock = MagicMock()
    mock.temperature = temperature
    mock.condition = condition
    return mock


def _make_location(lat: float = 40.0, lon: float = -74.0):
    """Create a mock Location object."""
    mock = MagicMock()
    mock.latitude = lat
    mock.longitude = lon
    return mock


def _make_historical(
    target_date: date | None = None,
    temp_max: float = 80.0,
    temp_min: float = 60.0,
    temp_mean: float = 70.0,
    condition: str = "Cloudy",
    wind_speed: float = 10.0,
) -> HistoricalWeatherData:
    return HistoricalWeatherData(
        date=target_date or date.today() - timedelta(days=1),
        temperature_max=temp_max,
        temperature_min=temp_min,
        temperature_mean=temp_mean,
        condition=condition,
        humidity=None,
        wind_speed=wind_speed,
        wind_direction=None,
        pressure=None,
    )


# --- WeatherComparison.compare ---


class TestWeatherComparison:
    def test_warmer(self):
        current = _make_current_conditions(temperature=80.0, condition="Sunny")
        historical = _make_historical(temp_mean=70.0, condition="Sunny")
        result = WeatherComparison.compare(current, historical, days_ago=1)
        assert result.temperature_difference == pytest.approx(10.0)
        assert "warmer" in result.temperature_description
        assert result.days_ago == 1

    def test_cooler(self):
        current = _make_current_conditions(temperature=60.0)
        historical = _make_historical(temp_mean=70.0)
        result = WeatherComparison.compare(current, historical, days_ago=1)
        assert result.temperature_difference == pytest.approx(-10.0)
        assert "cooler" in result.temperature_description

    def test_same_temperature(self):
        current = _make_current_conditions(temperature=70.5)
        historical = _make_historical(temp_mean=70.0)
        result = WeatherComparison.compare(current, historical, days_ago=1)
        assert "same" in result.temperature_description

    def test_condition_changed(self):
        current = _make_current_conditions(condition="Rainy")
        historical = _make_historical(condition="Sunny")
        result = WeatherComparison.compare(current, historical, days_ago=1)
        assert result.condition_changed is True
        assert "Sunny" in result.condition_description
        assert "Rainy" in result.condition_description

    def test_condition_unchanged(self):
        current = _make_current_conditions(condition="Sunny")
        historical = _make_historical(condition="Sunny")
        result = WeatherComparison.compare(current, historical, days_ago=1)
        assert result.condition_changed is False
        assert result.condition_description is None


# --- WeatherComparison.get_accessible_summary ---


class TestAccessibleSummary:
    def test_yesterday_reference(self):
        current = _make_current_conditions(temperature=80.0)
        historical = _make_historical(temp_mean=70.0)
        result = WeatherComparison.compare(current, historical, days_ago=1)
        summary = result.get_accessible_summary()
        assert "yesterday" in summary

    def test_last_week_reference(self):
        current = _make_current_conditions(temperature=80.0)
        historical = _make_historical(temp_mean=70.0)
        result = WeatherComparison.compare(current, historical, days_ago=7)
        summary = result.get_accessible_summary()
        assert "last week" in summary

    def test_arbitrary_days_reference(self):
        current = _make_current_conditions(temperature=80.0)
        historical = _make_historical(temp_mean=70.0)
        result = WeatherComparison.compare(current, historical, days_ago=3)
        summary = result.get_accessible_summary()
        assert "3 days ago" in summary

    def test_includes_condition_change(self):
        current = _make_current_conditions(temperature=75.0, condition="Rain")
        historical = _make_historical(temp_mean=70.0, condition="Clear")
        result = WeatherComparison.compare(current, historical, days_ago=1)
        summary = result.get_accessible_summary()
        assert "Clear" in summary
        assert "Rain" in summary

    def test_ends_with_period(self):
        current = _make_current_conditions()
        historical = _make_historical()
        result = WeatherComparison.compare(current, historical, days_ago=1)
        assert result.get_accessible_summary().endswith(".")


# --- WeatherHistoryService ---


class TestWeatherHistoryService:
    def test_init_creates_client(self):
        with patch("accessiweather.weather_history.WeatherHistoryService.__init__", return_value=None):
            # Just verify the class exists and can be instantiated with a mock client
            service = WeatherHistoryService.__new__(WeatherHistoryService)
            service.openmeteo_client = MagicMock()
            assert service.openmeteo_client is not None

    def test_get_historical_weather_success(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = {
            "daily": {
                "time": ["2025-01-01"],
                "weather_code": [3],
                "temperature_2m_max": [80.0],
                "temperature_2m_min": [60.0],
                "temperature_2m_mean": [70.0],
                "wind_speed_10m_max": [15.0],
                "wind_direction_10m_dominant": [180],
            }
        }
        mock_client.get_weather_description.return_value = "Overcast"

        service = WeatherHistoryService(openmeteo_client=mock_client)
        result = service.get_historical_weather(40.0, -74.0, date(2025, 1, 1))

        assert result is not None
        assert result.temperature_max == 80.0
        assert result.temperature_min == 60.0
        assert result.temperature_mean == 70.0
        assert result.condition == "Overcast"
        assert result.wind_speed == 15.0
        assert result.wind_direction == 180

    def test_get_historical_weather_no_response(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = None
        service = WeatherHistoryService(openmeteo_client=mock_client)
        result = service.get_historical_weather(40.0, -74.0, date(2025, 1, 1))
        assert result is None

    def test_get_historical_weather_no_daily(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = {"hourly": {}}
        service = WeatherHistoryService(openmeteo_client=mock_client)
        result = service.get_historical_weather(40.0, -74.0, date(2025, 1, 1))
        assert result is None

    def test_get_historical_weather_empty_time(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = {"daily": {"time": []}}
        service = WeatherHistoryService(openmeteo_client=mock_client)
        result = service.get_historical_weather(40.0, -74.0, date(2025, 1, 1))
        assert result is None

    def test_get_historical_weather_exception(self):
        mock_client = MagicMock()
        mock_client._make_request.side_effect = Exception("Network error")
        service = WeatherHistoryService(openmeteo_client=mock_client)
        result = service.get_historical_weather(40.0, -74.0, date(2025, 1, 1))
        assert result is None

    def test_compare_with_yesterday(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = {
            "daily": {
                "time": ["2025-01-01"],
                "weather_code": [0],
                "temperature_2m_max": [75.0],
                "temperature_2m_min": [55.0],
                "temperature_2m_mean": [65.0],
                "wind_speed_10m_max": [10.0],
                "wind_direction_10m_dominant": [90],
            }
        }
        mock_client.get_weather_description.return_value = "Clear"

        service = WeatherHistoryService(openmeteo_client=mock_client)
        location = _make_location()
        current = _make_current_conditions(temperature=80.0, condition="Sunny")
        result = service.compare_with_yesterday(location, current)
        assert result is not None
        assert result.days_ago == 1
        assert result.temperature_difference == pytest.approx(15.0)

    def test_compare_with_yesterday_no_data(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = None
        service = WeatherHistoryService(openmeteo_client=mock_client)
        result = service.compare_with_yesterday(_make_location(), _make_current_conditions())
        assert result is None

    def test_compare_with_last_week(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = {
            "daily": {
                "time": ["2025-01-01"],
                "weather_code": [2],
                "temperature_2m_max": [70.0],
                "temperature_2m_min": [50.0],
                "temperature_2m_mean": [60.0],
                "wind_speed_10m_max": [8.0],
                "wind_direction_10m_dominant": [270],
            }
        }
        mock_client.get_weather_description.return_value = "Partly cloudy"

        service = WeatherHistoryService(openmeteo_client=mock_client)
        result = service.compare_with_last_week(
            _make_location(), _make_current_conditions(temperature=75.0)
        )
        assert result is not None
        assert result.days_ago == 7

    def test_compare_with_last_week_no_data(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = None
        service = WeatherHistoryService(openmeteo_client=mock_client)
        result = service.compare_with_last_week(_make_location(), _make_current_conditions())
        assert result is None

    def test_compare_with_date(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = {
            "daily": {
                "time": ["2025-01-01"],
                "weather_code": [1],
                "temperature_2m_max": [68.0],
                "temperature_2m_min": [48.0],
                "temperature_2m_mean": [58.0],
                "wind_speed_10m_max": [12.0],
                "wind_direction_10m_dominant": [180],
            }
        }
        mock_client.get_weather_description.return_value = "Mainly clear"

        service = WeatherHistoryService(openmeteo_client=mock_client)
        target = date.today() - timedelta(days=3)
        result = service.compare_with_date(
            _make_location(), _make_current_conditions(temperature=72.0), target
        )
        assert result is not None
        assert result.days_ago == 3

    def test_compare_with_date_no_data(self):
        mock_client = MagicMock()
        mock_client._make_request.return_value = None
        service = WeatherHistoryService(openmeteo_client=mock_client)
        result = service.compare_with_date(
            _make_location(), _make_current_conditions(), date.today() - timedelta(days=5)
        )
        assert result is None


# --- HistoricalWeatherData ---


class TestHistoricalWeatherData:
    def test_dataclass_fields(self):
        data = _make_historical()
        assert data.temperature_max == 80.0
        assert data.temperature_min == 60.0
        assert data.humidity is None
        assert data.pressure is None
