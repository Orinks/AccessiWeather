"""Tests for weather history feature using Open-Meteo archive API."""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.models import CurrentConditions, Location
from accessiweather.weather_history import (
    HistoricalWeatherData,
    WeatherComparison,
    WeatherHistoryService,
)


class TestHistoricalWeatherData:
    """Test HistoricalWeatherData data model."""

    def test_create_historical_data(self):
        """Test creating historical weather data."""
        data = HistoricalWeatherData(
            date=date(2025, 1, 1),
            temperature_max=80.0,
            temperature_min=60.0,
            temperature_mean=70.0,
            condition="Sunny",
            humidity=55,
            wind_speed=10.0,
            wind_direction=180,
            pressure=30.1,
        )

        assert data.date == date(2025, 1, 1)
        assert data.temperature_mean == 70.0
        assert data.condition == "Sunny"


class TestWeatherComparison:
    """Test weather comparison functionality."""

    def test_compare_temperature_warmer(self):
        """Test comparison shows temperature increase."""
        current = CurrentConditions(
            temperature=80.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )

        historical = HistoricalWeatherData(
            date=date(2025, 1, 1),
            temperature_max=78.0,
            temperature_min=68.0,
            temperature_mean=73.0,
            condition="Partly Cloudy",
            humidity=65,
            wind_speed=8.0,
            wind_direction=270,
            pressure=30.0,
        )

        comparison = WeatherComparison.compare(current, historical, days_ago=1)

        assert comparison.temperature_difference == 7.0
        assert "warmer" in comparison.temperature_description.lower()
        assert comparison.days_ago == 1

    def test_compare_temperature_cooler(self):
        """Test comparison shows temperature decrease."""
        current = CurrentConditions(
            temperature=65.0,
            condition="Cloudy",
            humidity=70,
            wind_speed=12.0,
            wind_direction="E",
            pressure=29.9,
        )

        historical = HistoricalWeatherData(
            date=date(2025, 1, 1),
            temperature_max=78.0,
            temperature_min=68.0,
            temperature_mean=73.0,
            condition="Sunny",
            humidity=55,
            wind_speed=8.0,
            wind_direction=270,
            pressure=30.1,
        )

        comparison = WeatherComparison.compare(current, historical, days_ago=1)

        assert comparison.temperature_difference == -8.0
        assert "cooler" in comparison.temperature_description.lower()

    def test_compare_same_temperature(self):
        """Test comparison when temperature is similar."""
        current = CurrentConditions(
            temperature=73.5,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )

        historical = HistoricalWeatherData(
            date=date(2025, 1, 1),
            temperature_max=75.0,
            temperature_min=71.0,
            temperature_mean=73.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction=270,
            pressure=30.1,
        )

        comparison = WeatherComparison.compare(current, historical, days_ago=1)

        assert abs(comparison.temperature_difference) < 1.0
        assert "same" in comparison.temperature_description.lower()

    def test_compare_condition_changed(self):
        """Test comparison when weather condition changed."""
        current = CurrentConditions(
            temperature=75.0,
            condition="Rainy",
            humidity=85,
            wind_speed=15.0,
            wind_direction="S",
            pressure=29.8,
        )

        historical = HistoricalWeatherData(
            date=date(2025, 1, 1),
            temperature_max=78.0,
            temperature_min=68.0,
            temperature_mean=73.0,
            condition="Sunny",
            humidity=55,
            wind_speed=8.0,
            wind_direction=270,
            pressure=30.1,
        )

        comparison = WeatherComparison.compare(current, historical, days_ago=1)

        assert comparison.condition_changed is True
        assert comparison.previous_condition == "Sunny"
        assert "Rainy" in comparison.condition_description
        assert "Sunny" in comparison.condition_description

    def test_comparison_summary_accessible(self):
        """Test that comparison summary is screen-reader friendly."""
        current = CurrentConditions(
            temperature=80.0,
            condition="Sunny",
            humidity=55,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )

        historical = HistoricalWeatherData(
            date=date(2025, 1, 1),
            temperature_max=78.0,
            temperature_min=68.0,
            temperature_mean=73.0,
            condition="Cloudy",
            humidity=70,
            wind_speed=8.0,
            wind_direction=180,
            pressure=30.0,
        )

        comparison = WeatherComparison.compare(current, historical, days_ago=1)
        summary = comparison.get_accessible_summary()

        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "yesterday" in summary.lower()
        assert "degrees" in summary.lower() or "temperature" in summary.lower()

    def test_comparison_summary_last_week(self):
        """Test summary uses 'last week' for 7 days ago."""
        current = CurrentConditions(
            temperature=80.0,
            condition="Sunny",
            humidity=55,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )

        historical = HistoricalWeatherData(
            date=date(2025, 1, 1),
            temperature_max=78.0,
            temperature_min=68.0,
            temperature_mean=73.0,
            condition="Sunny",
            humidity=60,
            wind_speed=10.0,
            wind_direction=270,
            pressure=30.1,
        )

        comparison = WeatherComparison.compare(current, historical, days_ago=7)
        summary = comparison.get_accessible_summary()

        assert "last week" in summary.lower()


class TestWeatherHistoryService:
    """Test WeatherHistoryService functionality."""

    @pytest.fixture
    def mock_openmeteo_client(self):
        """Create a mock Open-Meteo client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def service(self, mock_openmeteo_client):
        """Create a weather history service with mock client."""
        return WeatherHistoryService(openmeteo_client=mock_openmeteo_client)

    def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service.openmeteo_client is not None

    def test_get_historical_weather_success(self, service, mock_openmeteo_client):
        """Test fetching historical weather data successfully."""
        # Mock API response
        mock_response = {
            "daily": {
                "time": ["2025-01-01"],
                "weather_code": [1],
                "temperature_2m_max": [78.0],
                "temperature_2m_min": [68.0],
                "temperature_2m_mean": [73.0],
                "wind_speed_10m_max": [10.0],
                "wind_direction_10m_dominant": [270],
            }
        }
        mock_openmeteo_client._make_request.return_value = mock_response
        mock_openmeteo_client.get_weather_description.return_value = "Mainly clear"

        target_date = date(2025, 1, 1)
        result = service.get_historical_weather(40.7128, -74.0060, target_date)

        assert result is not None
        assert result.date == target_date
        assert result.temperature_mean == 73.0
        assert result.condition == "Mainly clear"
        mock_openmeteo_client._make_request.assert_called_once()

    def test_get_historical_weather_api_error(self, service, mock_openmeteo_client):
        """Test handling API errors gracefully."""
        mock_openmeteo_client._make_request.side_effect = Exception("API Error")

        target_date = date(2025, 1, 1)
        result = service.get_historical_weather(40.7128, -74.0060, target_date)

        assert result is None

    def test_get_historical_weather_no_data(self, service, mock_openmeteo_client):
        """Test handling when no data is available."""
        mock_response = {"daily": {"time": []}}
        mock_openmeteo_client._make_request.return_value = mock_response

        target_date = date(2025, 1, 1)
        result = service.get_historical_weather(40.7128, -74.0060, target_date)

        assert result is None

    def test_compare_with_yesterday(self, service, mock_openmeteo_client):
        """Test comparing with yesterday's weather."""
        # Mock historical data
        mock_response = {
            "daily": {
                "time": ["2025-01-09"],
                "weather_code": [2],
                "temperature_2m_max": [75.0],
                "temperature_2m_min": [65.0],
                "temperature_2m_mean": [70.0],
                "wind_speed_10m_max": [8.0],
                "wind_direction_10m_dominant": [180],
            }
        }
        mock_openmeteo_client._make_request.return_value = mock_response
        mock_openmeteo_client.get_weather_description.return_value = "Partly cloudy"

        location = Location(
            name="Test City",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
        )
        current = CurrentConditions(
            temperature=80.0,
            condition="Sunny",
            humidity=55,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )

        comparison = service.compare_with_yesterday(location, current)

        assert comparison is not None
        assert comparison.days_ago == 1
        assert comparison.temperature_difference > 0

    def test_compare_with_last_week(self, service, mock_openmeteo_client):
        """Test comparing with last week's weather."""
        # Mock historical data
        mock_response = {
            "daily": {
                "time": ["2025-01-03"],
                "weather_code": [61],
                "temperature_2m_max": [68.0],
                "temperature_2m_min": [58.0],
                "temperature_2m_mean": [63.0],
                "wind_speed_10m_max": [15.0],
                "wind_direction_10m_dominant": [90],
            }
        }
        mock_openmeteo_client._make_request.return_value = mock_response
        mock_openmeteo_client.get_weather_description.return_value = "Slight rain"

        location = Location(
            name="Test City",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
        )
        current = CurrentConditions(
            temperature=80.0,
            condition="Sunny",
            humidity=55,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )

        comparison = service.compare_with_last_week(location, current)

        assert comparison is not None
        assert comparison.days_ago == 7
        assert comparison.condition_changed is True

    def test_compare_with_custom_date(self, service, mock_openmeteo_client):
        """Test comparing with a custom date."""
        # Mock historical data
        mock_response = {
            "daily": {
                "time": ["2025-01-05"],
                "weather_code": [3],
                "temperature_2m_max": [72.0],
                "temperature_2m_min": [62.0],
                "temperature_2m_mean": [67.0],
                "wind_speed_10m_max": [12.0],
                "wind_direction_10m_dominant": [225],
            }
        }
        mock_openmeteo_client._make_request.return_value = mock_response
        mock_openmeteo_client.get_weather_description.return_value = "Overcast"

        location = Location(
            name="Test City",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York",
        )
        current = CurrentConditions(
            temperature=80.0,
            condition="Sunny",
            humidity=55,
            wind_speed=10.0,
            wind_direction="NW",
            pressure=30.1,
        )

        target_date = date(2025, 1, 5)
        comparison = service.compare_with_date(location, current, target_date)

        assert comparison is not None
        assert comparison.days_ago == (datetime.now().date() - target_date).days
