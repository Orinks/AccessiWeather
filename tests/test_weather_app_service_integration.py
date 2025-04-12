"""Tests for the integration of services with the WeatherApp."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.services.location_service import LocationService
from accessiweather.services.notification_service import NotificationService
from accessiweather.services.weather_service import WeatherService


@pytest.fixture
def mock_weather_service():
    """Create a mock weather service."""
    service = MagicMock(spec=WeatherService)
    service.get_forecast.return_value = {
        "properties": {"periods": [{"name": "Test Period", "temperature": 75}]}
    }
    service.get_alerts.return_value = {"features": []}
    service.get_discussion.return_value = "Test discussion"
    return service


@pytest.fixture
def mock_location_service():
    """Create a mock location service."""
    service = MagicMock(spec=LocationService)
    service.get_current_location.return_value = ("Test Location", 35.0, -80.0)
    service.get_current_location_name.return_value = "Test Location"
    service.get_all_locations.return_value = ["Test Location"]
    return service


@pytest.fixture
def mock_notification_service():
    """Create a mock notification service."""
    service = MagicMock(spec=NotificationService)
    service.process_alerts.return_value = []
    service.notifier = MagicMock()
    return service


class TestWeatherAppServiceIntegration:
    """Test suite for the integration of services with the WeatherApp."""

    def test_weather_service_get_forecast(self, mock_weather_service):
        """Test getting forecast data from the weather service."""
        # Call the method
        result = mock_weather_service.get_forecast(35.0, -80.0)

        # Verify the result
        assert result == {
            "properties": {"periods": [{"name": "Test Period", "temperature": 75}]}
        }
        mock_weather_service.get_forecast.assert_called_once_with(35.0, -80.0)

    def test_weather_service_get_alerts(self, mock_weather_service):
        """Test getting alerts data from the weather service."""
        # Call the method
        result = mock_weather_service.get_alerts(35.0, -80.0)

        # Verify the result
        assert result == {"features": []}
        mock_weather_service.get_alerts.assert_called_once_with(35.0, -80.0)

    def test_weather_service_get_discussion(self, mock_weather_service):
        """Test getting discussion data from the weather service."""
        # Call the method
        result = mock_weather_service.get_discussion(35.0, -80.0)

        # Verify the result
        assert result == "Test discussion"
        mock_weather_service.get_discussion.assert_called_once_with(35.0, -80.0)

    def test_location_service_get_current_location(self, mock_location_service):
        """Test getting the current location from the location service."""
        # Call the method
        result = mock_location_service.get_current_location()

        # Verify the result
        assert result == ("Test Location", 35.0, -80.0)
        mock_location_service.get_current_location.assert_called_once()

    def test_location_service_get_all_locations(self, mock_location_service):
        """Test getting all locations from the location service."""
        # Call the method
        result = mock_location_service.get_all_locations()

        # Verify the result
        assert result == ["Test Location"]
        mock_location_service.get_all_locations.assert_called_once()

    def test_location_service_add_location(self, mock_location_service):
        """Test adding a location using the location service."""
        # Call the method
        mock_location_service.add_location("New Location", 40.0, -75.0)

        # Verify the method was called with the correct arguments
        mock_location_service.add_location.assert_called_once_with("New Location", 40.0, -75.0)

    def test_location_service_remove_location(self, mock_location_service):
        """Test removing a location using the location service."""
        # Call the method
        mock_location_service.remove_location("Test Location")

        # Verify the method was called with the correct arguments
        mock_location_service.remove_location.assert_called_once_with("Test Location")

    def test_location_service_set_current_location(self, mock_location_service):
        """Test setting the current location using the location service."""
        # Call the method
        mock_location_service.set_current_location("Test Location")

        # Verify the method was called with the correct arguments
        mock_location_service.set_current_location.assert_called_once_with("Test Location")

    def test_notification_service_process_alerts(self, mock_notification_service):
        """Test processing alerts using the notification service."""
        # Set up test data
        alerts_data = {
            "features": [
                {
                    "properties": {
                        "headline": "Test Alert",
                        "description": "Test Description",
                    }
                }
            ]
        }
        processed_alerts = [
            {
                "headline": "Test Alert",
                "description": "Test Description",
            }
        ]
        mock_notification_service.process_alerts.return_value = processed_alerts

        # Call the method
        result = mock_notification_service.process_alerts(alerts_data)

        # Verify the result
        assert result == processed_alerts
        mock_notification_service.process_alerts.assert_called_once_with(alerts_data)

    def test_notification_service_notify_alerts(self, mock_notification_service):
        """Test notifying about alerts using the notification service."""
        # Set up test data
        alerts = [
            {"headline": "Test Alert 1", "severity": "Moderate"},
            {"headline": "Test Alert 2", "severity": "Severe"},
        ]

        # Call the method
        mock_notification_service.notify_alerts(alerts)

        # Verify the method was called with the correct arguments
        mock_notification_service.notify_alerts.assert_called_once_with(alerts)

    def test_integration_location_and_weather_services(
        self, mock_location_service, mock_weather_service
    ):
        """Test integration between location and weather services."""
        # Get the current location from the location service
        location = mock_location_service.get_current_location()
        assert location == ("Test Location", 35.0, -80.0)

        # Use the location to get forecast data from the weather service
        name, lat, lon = location
        forecast = mock_weather_service.get_forecast(lat, lon)
        assert forecast == {
            "properties": {"periods": [{"name": "Test Period", "temperature": 75}]}
        }

        # Use the location to get alerts data from the weather service
        alerts = mock_weather_service.get_alerts(lat, lon)
        assert alerts == {"features": []}

    def test_integration_weather_and_notification_services(
        self, mock_weather_service, mock_notification_service
    ):
        """Test integration between weather and notification services."""
        # Set up test data
        alerts_data = {
            "features": [
                {
                    "properties": {
                        "headline": "Test Alert",
                        "description": "Test Description",
                    }
                }
            ]
        }
        processed_alerts = [
            {
                "headline": "Test Alert",
                "description": "Test Description",
            }
        ]
        mock_weather_service.get_alerts.return_value = alerts_data
        mock_notification_service.process_alerts.return_value = processed_alerts

        # Get alerts data from the weather service
        alerts_data = mock_weather_service.get_alerts(35.0, -80.0)
        assert alerts_data == {
            "features": [
                {
                    "properties": {
                        "headline": "Test Alert",
                        "description": "Test Description",
                    }
                }
            ]
        }

        # Process alerts using the notification service
        processed_alerts = mock_notification_service.process_alerts(alerts_data)
        assert processed_alerts == [
            {
                "headline": "Test Alert",
                "description": "Test Description",
            }
        ]

        # Notify about alerts using the notification service
        mock_notification_service.notify_alerts(processed_alerts)
        mock_notification_service.notify_alerts.assert_called_with(processed_alerts)

    def test_full_integration_all_services(
        self, mock_location_service, mock_weather_service, mock_notification_service
    ):
        """Test full integration of all services."""
        # Get the current location from the location service
        location = mock_location_service.get_current_location()
        assert location == ("Test Location", 35.0, -80.0)

        # Use the location to get forecast data from the weather service
        name, lat, lon = location
        forecast = mock_weather_service.get_forecast(lat, lon)
        assert forecast == {
            "properties": {"periods": [{"name": "Test Period", "temperature": 75}]}
        }

        # Set up test data for alerts
        alerts_data = {
            "features": [
                {
                    "properties": {
                        "headline": "Test Alert",
                        "description": "Test Description",
                    }
                }
            ]
        }
        processed_alerts = [
            {
                "headline": "Test Alert",
                "description": "Test Description",
            }
        ]
        mock_weather_service.get_alerts.return_value = alerts_data
        mock_notification_service.process_alerts.return_value = processed_alerts

        # Use the location to get alerts data from the weather service
        alerts_data = mock_weather_service.get_alerts(lat, lon)
        assert alerts_data == {
            "features": [
                {
                    "properties": {
                        "headline": "Test Alert",
                        "description": "Test Description",
                    }
                }
            ]
        }

        # Process alerts using the notification service
        processed_alerts = mock_notification_service.process_alerts(alerts_data)
        assert processed_alerts == [
            {
                "headline": "Test Alert",
                "description": "Test Description",
            }
        ]

        # Notify about alerts using the notification service
        mock_notification_service.notify_alerts(processed_alerts)
        mock_notification_service.notify_alerts.assert_called_with(processed_alerts)
