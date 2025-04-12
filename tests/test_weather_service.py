"""Tests for the WeatherService class."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.services.weather_service import WeatherService


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    mock_client = MagicMock(spec=NoaaApiClient)
    # Default values, tests can override
    mock_client.get_forecast.return_value = {
        "properties": {"periods": [{"name": "Default", "temperature": 0}]}
    }
    mock_client.get_alerts.return_value = {"features": []}
    mock_client.get_discussion.return_value = "Test discussion"
    return mock_client


@pytest.fixture
def weather_service(mock_api_client):
    """Create a WeatherService instance with a mock API client."""
    return WeatherService(mock_api_client)


class TestWeatherService:
    """Test suite for WeatherService."""

    def test_init(self, mock_api_client):
        """Test service initialization."""
        service = WeatherService(mock_api_client)
        assert service.api_client == mock_api_client

    def test_get_forecast(self, weather_service, mock_api_client):
        """Test getting forecast data."""
        # Set up mock return value
        expected_forecast = {"properties": {"periods": [{"name": "Today", "temperature": 75}]}}
        mock_api_client.get_forecast.return_value = expected_forecast

        # Call the method
        result = weather_service.get_forecast(35.0, -80.0)

        # Verify the result
        assert result == expected_forecast
        mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)

    def test_get_forecast_error(self, weather_service, mock_api_client):
        """Test error handling when getting forecast data."""
        # Set up mock to raise an exception
        mock_api_client.get_forecast.side_effect = Exception("Test error")

        # Call the method and verify it raises the expected exception
        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_forecast(35.0, -80.0)

        # Verify the error message
        assert "Unable to retrieve forecast data" in str(exc_info.value)
        assert "Test error" in str(exc_info.value)
        mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)

    def test_get_alerts(self, weather_service, mock_api_client):
        """Test getting alerts data."""
        # Set up mock return value
        expected_alerts = {
            "features": [
                {"properties": {"headline": "Test Alert", "description": "Test Description"}}
            ]
        }
        mock_api_client.get_alerts.return_value = expected_alerts

        # Call the method
        result = weather_service.get_alerts(35.0, -80.0, radius=25, precise_location=True)

        # Verify the result
        assert result == expected_alerts
        mock_api_client.get_alerts.assert_called_once_with(
            35.0, -80.0, radius=25, precise_location=True
        )

    def test_get_alerts_error(self, weather_service, mock_api_client):
        """Test error handling when getting alerts data."""
        # Set up mock to raise an exception
        mock_api_client.get_alerts.side_effect = Exception("Test error")

        # Call the method and verify it raises the expected exception
        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_alerts(35.0, -80.0)

        # Verify the error message
        assert "Unable to retrieve alerts data" in str(exc_info.value)
        assert "Test error" in str(exc_info.value)
        mock_api_client.get_alerts.assert_called_once_with(
            35.0, -80.0, radius=50, precise_location=True
        )

    def test_get_discussion(self, weather_service, mock_api_client):
        """Test getting discussion data."""
        # Set up mock return value
        expected_discussion = "Test forecast discussion"
        mock_api_client.get_discussion.return_value = expected_discussion

        # Call the method
        result = weather_service.get_discussion(35.0, -80.0)

        # Verify the result
        assert result == expected_discussion
        mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0)

    def test_get_discussion_none(self, weather_service, mock_api_client):
        """Test getting discussion data when none is available."""
        # Set up mock return value
        mock_api_client.get_discussion.return_value = None

        # Call the method
        result = weather_service.get_discussion(35.0, -80.0)

        # Verify the result
        assert result is None
        mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0)

    def test_get_discussion_error(self, weather_service, mock_api_client):
        """Test error handling when getting discussion data."""
        # Set up mock to raise an exception
        mock_api_client.get_discussion.side_effect = Exception("Test error")

        # Call the method and verify it raises the expected exception
        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_discussion(35.0, -80.0)

        # Verify the error message
        assert "Unable to retrieve discussion data" in str(exc_info.value)
        assert "Test error" in str(exc_info.value)
        mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0)

    def test_process_alerts(self, weather_service):
        """Test processing alerts data."""
        # Sample alerts data
        alerts_data = {
            "features": [
                {
                    "id": "alert-1",
                    "properties": {
                        "headline": "Test Alert 1",
                        "description": "Test Description 1",
                        "instruction": "Test Instruction 1",
                        "severity": "Moderate",
                        "event": "Test Event 1",
                        "effective": "2023-01-01T00:00:00Z",
                        "expires": "2023-01-02T00:00:00Z",
                        "status": "Actual",
                        "messageType": "Alert",
                        "areaDesc": "Test Area 1",
                    },
                },
                {
                    "id": "alert-2",
                    "properties": {
                        "headline": "Test Alert 2",
                        "description": "Test Description 2",
                        "severity": "Severe",
                        "event": "Test Event 2",
                    },
                },
            ]
        }

        # Call the method
        result = weather_service.process_alerts(alerts_data)

        # Verify the result
        assert len(result) == 2
        assert result[0]["id"] == "alert-1"
        assert result[0]["headline"] == "Test Alert 1"
        assert result[0]["description"] == "Test Description 1"
        assert result[0]["instruction"] == "Test Instruction 1"
        assert result[0]["severity"] == "Moderate"
        assert result[0]["event"] == "Test Event 1"
        assert result[0]["effective"] == "2023-01-01T00:00:00Z"
        assert result[0]["expires"] == "2023-01-02T00:00:00Z"
        assert result[0]["status"] == "Actual"
        assert result[0]["messageType"] == "Alert"
        assert result[0]["areaDesc"] == "Test Area 1"

        assert result[1]["id"] == "alert-2"
        assert result[1]["headline"] == "Test Alert 2"
        assert result[1]["description"] == "Test Description 2"
        assert result[1]["instruction"] == ""  # Default value
        assert result[1]["severity"] == "Severe"
        assert result[1]["event"] == "Test Event 2"
        assert result[1]["areaDesc"] == "Unknown Area"  # Default value

    def test_process_alerts_empty(self, weather_service):
        """Test processing empty alerts data."""
        # Empty alerts data
        alerts_data = {"features": []}

        # Call the method
        result = weather_service.process_alerts(alerts_data)

        # Verify the result
        assert result == []

    def test_process_alerts_missing_features(self, weather_service):
        """Test processing alerts data with missing features."""
        # Alerts data with missing features
        alerts_data = {}

        # Call the method
        result = weather_service.process_alerts(alerts_data)

        # Verify the result
        assert result == []
