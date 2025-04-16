"""Tests for the WeatherService class with caching."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.services.weather_service import WeatherService


@pytest.fixture
def mock_api_client():
    """Create a mock API client with caching enabled."""
    mock_client = MagicMock(spec=NoaaApiClient)
    # Default values, tests can override
    mock_client.get_forecast.return_value = {
        "properties": {"periods": [{"name": "Default", "temperature": 0}]}
    }
    mock_client.get_alerts.return_value = {"features": []}
    mock_client.get_discussion.return_value = "Test discussion"
    mock_client.cache = MagicMock()  # Mock the cache
    return mock_client


@pytest.fixture
def weather_service(mock_api_client):
    """Create a WeatherService instance with a mock API client."""
    return WeatherService(mock_api_client)


class TestWeatherServiceCaching:
    """Test suite for WeatherService with caching."""

    def test_get_forecast_with_cache(self, weather_service, mock_api_client):
        """Test getting forecast data with caching."""
        # Call the method
        weather_service.get_forecast(35.0, -80.0)

        # Verify the API client was called with default caching behavior
        mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0, force_refresh=False)

    def test_get_forecast_force_refresh(self, weather_service, mock_api_client):
        """Test getting forecast data with force_refresh."""
        # Call the method with force_refresh
        weather_service.get_forecast(35.0, -80.0, force_refresh=True)

        # Verify the API client was called with force_refresh=True
        mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0, force_refresh=True)

    def test_get_alerts_with_cache(self, weather_service, mock_api_client):
        """Test getting alerts data with caching."""
        # Call the method
        weather_service.get_alerts(35.0, -80.0, radius=25, precise_location=True)

        # Verify the API client was called with default caching behavior
        mock_api_client.get_alerts.assert_called_once_with(
            35.0, -80.0, radius=25, precise_location=True, force_refresh=False
        )

    def test_get_alerts_force_refresh(self, weather_service, mock_api_client):
        """Test getting alerts data with force_refresh."""
        # Call the method with force_refresh
        weather_service.get_alerts(
            35.0, -80.0, radius=25, precise_location=True, force_refresh=True
        )

        # Verify the API client was called with force_refresh=True
        mock_api_client.get_alerts.assert_called_once_with(
            35.0, -80.0, radius=25, precise_location=True, force_refresh=True
        )

    def test_get_discussion_with_cache(self, weather_service, mock_api_client):
        """Test getting discussion data with caching."""
        # Call the method
        weather_service.get_discussion(35.0, -80.0)

        # Verify the API client was called with default caching behavior
        mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0, force_refresh=False)

    def test_get_discussion_force_refresh(self, weather_service, mock_api_client):
        """Test getting discussion data with force_refresh."""
        # Call the method with force_refresh
        weather_service.get_discussion(35.0, -80.0, force_refresh=True)

        # Verify the API client was called with force_refresh=True
        mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0, force_refresh=True)

    def test_api_error_handling(self, weather_service, mock_api_client):
        """Test that API errors are properly handled."""
        # Configure the mock to raise an error
        mock_api_client.get_forecast.side_effect = ApiClientError("Test error")

        # Test that the error is raised
        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_forecast(35.0, -80.0)

        # Verify the error message
        assert "Test error" in str(exc_info.value)
