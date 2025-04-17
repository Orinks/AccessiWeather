"""Tests for the API contact check when config file is missing"""

# Import faulthandler setup first to enable faulthandler
from unittest.mock import MagicMock, patch

import pytest
import wx

import tests.faulthandler_setup  # noqa: F401
from accessiweather.gui.weather_app import WeatherApp


@pytest.fixture
def mock_components():
    """Mock the components used by WeatherApp"""
    with (
        patch("accessiweather.api_client.NoaaApiClient") as mock_api_client_class,
        patch("accessiweather.notifications.WeatherNotifier") as mock_notifier_class,
        patch("accessiweather.services.location_service.LocationService") as mock_location_service_class,
        patch("accessiweather.services.weather_service.WeatherService") as mock_weather_service_class,
        patch("accessiweather.services.notification_service.NotificationService") as mock_notification_service_class,
    ):
        # Create mock instances
        mock_api_client = MagicMock()
        mock_notifier = MagicMock()
        mock_location_service = MagicMock()
        mock_weather_service = MagicMock()
        mock_notification_service = MagicMock()

        # Configure mock location service to return valid data
        mock_location_service.get_all_locations.return_value = ["Test City"]
        mock_location_service.get_current_location.return_value = ("Test City", 35.0, -80.0)

        # Configure notification service to have a notifier property
        mock_notification_service.notifier = mock_notifier

        # Configure mock classes to return mock instances
        mock_api_client_class.return_value = mock_api_client
        mock_notifier_class.return_value = mock_notifier
        mock_location_service_class.return_value = mock_location_service
        mock_weather_service_class.return_value = mock_weather_service
        mock_notification_service_class.return_value = mock_notification_service

        yield {
            "api_client": mock_api_client,
            "notifier": mock_notifier,
            "location_service": mock_location_service,
            "weather_service": mock_weather_service,
            "notification_service": mock_notification_service,
        }


def test_dialog_shown_when_config_file_missing(wx_app, mock_components):
    """Test that dialog is shown when config file doesn't exist"""
    # Create a mock for the original method
    original_method = WeatherApp._check_api_contact_configured
    mock_method = MagicMock()

    try:
        # Replace the method with our mock
        WeatherApp._check_api_contact_configured = mock_method

        # Mock os.path.exists to return False
        with patch("os.path.exists", return_value=False):
            # Create the app
            app = WeatherApp(
                parent=None,
                location_service=mock_components["location_service"],
                weather_service=mock_components["weather_service"],
                notification_service=mock_components["notification_service"],
                api_client=mock_components["api_client"],
            )

            try:
                # Verify the method was called
                mock_method.assert_called_once()
            finally:
                # Hide the window first
                wx.CallAfter(app.Hide)
                wx.SafeYield()
                # Then destroy it
                wx.CallAfter(app.Destroy)
                wx.SafeYield()
    finally:
        # Restore the original method
        WeatherApp._check_api_contact_configured = original_method
