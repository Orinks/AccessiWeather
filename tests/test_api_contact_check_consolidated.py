"""Tests for the API contact check feature on application startup"""

import pytest
import wx
from unittest.mock import MagicMock, patch

from accessiweather.gui.settings_dialog import API_CONTACT_KEY
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


def test_no_dialog_when_api_contact_present(wx_app, mock_components):
    """Test that no dialog is shown when API contact is present"""
    # Create a config with API contact
    config = {
        "locations": {},
        "current": None,
        "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
        "api_settings": {API_CONTACT_KEY: "test@example.com"},
    }

    # Mock the _check_api_contact_configured method
    with patch.object(WeatherApp, "_check_api_contact_configured") as mock_check:
        # Create the app
        app = WeatherApp(
            parent=None,
            location_service=mock_components["location_service"],
            weather_service=mock_components["weather_service"],
            notification_service=mock_components["notification_service"],
            api_client=mock_components["api_client"],
            config=config,
        )

        try:
            # Verify the method was called
            mock_check.assert_called_once()
        finally:
            # Hide the window first
            wx.CallAfter(app.Hide)
            wx.SafeYield()
            # Then destroy it
            wx.CallAfter(app.Destroy)
            wx.SafeYield()


def test_dialog_shown_when_api_contact_missing(wx_app, mock_components):
    """Test that dialog is shown when API contact is missing"""
    # Create a config without API contact
    config = {
        "locations": {},
        "current": None,
        "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
        "api_settings": {API_CONTACT_KEY: ""},  # Empty string
    }

    # Mock the _check_api_contact_configured method
    with patch.object(WeatherApp, "_check_api_contact_configured") as mock_method:
        # Create the app
        app = WeatherApp(
            parent=None,
            location_service=mock_components["location_service"],
            weather_service=mock_components["weather_service"],
            notification_service=mock_components["notification_service"],
            api_client=mock_components["api_client"],
            config=config,
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


def test_dialog_shown_when_api_settings_missing(wx_app, mock_components):
    """Test that dialog is shown when api_settings section is missing"""
    # Create a config without api_settings section
    config = {
        "locations": {},
        "current": None,
        "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
        # No api_settings section
    }

    # Mock the _check_api_contact_configured method
    with patch.object(WeatherApp, "_check_api_contact_configured") as mock_method:
        # Create the app
        app = WeatherApp(
            parent=None,
            location_service=mock_components["location_service"],
            weather_service=mock_components["weather_service"],
            notification_service=mock_components["notification_service"],
            api_client=mock_components["api_client"],
            config=config,
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


def test_settings_not_opened_if_dialog_cancelled(wx_app, mock_components):
    """Test that settings are not opened if dialog is cancelled"""
    # Create a config without API contact
    config = {
        "locations": {},
        "current": None,
        "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
        "api_settings": {API_CONTACT_KEY: ""},  # Empty string
    }

    # Mock the dialog and OnSettings method
    with (
        patch("wx.MessageDialog") as mock_dialog_class,
        patch.object(WeatherApp, "OnSettings") as mock_on_settings,
    ):
        # Configure the mock dialog to return CANCEL
        mock_dialog = MagicMock()
        mock_dialog.ShowModal.return_value = wx.ID_CANCEL
        mock_dialog_class.return_value = mock_dialog

        # Create the app
        app = WeatherApp(
            parent=None,
            location_service=mock_components["location_service"],
            weather_service=mock_components["weather_service"],
            notification_service=mock_components["notification_service"],
            api_client=mock_components["api_client"],
            config=config,
        )

        try:
            # Verify the dialog was shown
            mock_dialog_class.assert_called_once()
            # Verify OnSettings was NOT called
            mock_on_settings.assert_not_called()
        finally:
            # Hide the window first
            wx.CallAfter(app.Hide)
            wx.SafeYield()
            # Then destroy it
            wx.CallAfter(app.Destroy)
            wx.SafeYield()


def test_check_called_on_init(wx_app, mock_components):
    """Test that the API contact check is called during initialization"""
    # Create a config without API contact
    config = {
        "locations": {},
        "current": None,
        "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
        "api_settings": {API_CONTACT_KEY: ""},  # Empty string
    }

    # Mock the _check_api_contact_configured method
    with (
        patch.object(WeatherApp, "_check_api_contact_configured") as mock_check,
        patch("wx.MessageDialog"),
    ):  # Prevent dialog from showing
        # Create the app
        app = WeatherApp(
            parent=None,
            location_service=mock_components["location_service"],
            weather_service=mock_components["weather_service"],
            notification_service=mock_components["notification_service"],
            api_client=mock_components["api_client"],
            config=config,
        )

        try:
            # Verify the method was called
            mock_check.assert_called_once()
        finally:
            # Hide the window first
            wx.CallAfter(app.Hide)
            wx.SafeYield()
            # Then destroy it
            wx.CallAfter(app.Destroy)
            wx.SafeYield()


def test_dialog_shown_when_config_file_missing(wx_app, mock_components):
    """Test that dialog is shown when config file doesn't exist"""
    # Mock the _check_api_contact_configured method
    with patch.object(WeatherApp, "_check_api_contact_configured") as mock_method:
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
