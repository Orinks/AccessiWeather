"""Tests for the API contact check feature on application startup"""

# Import faulthandler setup first to enable faulthandler
from unittest.mock import MagicMock, patch

import unittest
import wx

# Ensure wx.App is created before any wx controls
if not wx.GetApp():
    wx.App(False)
from accessiweather.gui.weather_app import WeatherApp
from accessiweather.gui.settings_dialog import API_CONTACT_KEY
from accessiweather.services.location_service import LocationService


class TestApiContactCheck(unittest.TestCase):
    """Test suite for the API contact check feature on application startup"""

    def setUp(self):
        # Ensure a wx.App exists for GUI object creation (even mocks)
        # Using False prevents starting the real event loop
        self.app = wx.App(False)

        # Patch the dependencies
        patcher_api_client = patch("accessiweather.api_client.NoaaApiClient")
        patcher_notifier = patch("accessiweather.notifications.WeatherNotifier")
        patcher_location_service = patch("accessiweather.services.location_service.LocationService")
        patcher_weather_service = patch("accessiweather.services.weather_service.WeatherService")
        self.patcher_dialog = patch("wx.MessageDialog")  # Centralize dialog patching

        self.addCleanup(patcher_api_client.stop)
        self.addCleanup(patcher_notifier.stop)
        self.addCleanup(patcher_location_service.stop)
        self.addCleanup(patcher_weather_service.stop)
        self.addCleanup(self.patcher_dialog.stop)  # Add cleanup for dialog patcher

        self.mock_api_client_class = patcher_api_client.start()
        self.mock_notifier_class = patcher_notifier.start()
        self.mock_location_service_class = patcher_location_service.start()
        self.mock_weather_service_class = patcher_weather_service.start()
        self.mock_dialog_class = self.patcher_dialog.start()  # Start dialog patcher

        # Configure the mock dialog instance
        self.mock_dialog_instance = MagicMock()
        self.mock_dialog_class.return_value = self.mock_dialog_instance

        # Create mock instances for other dependencies
        self.mock_api_client = MagicMock()
        self.mock_notifier = MagicMock()
        self.mock_location_service = MagicMock(spec=LocationService)
        self.mock_location_service.get_all_locations.return_value = ["Test City"]
        self.mock_location_service.get_current_location.return_value = ("Test City", 35.0, -80.0)
        self.mock_api_client_class.return_value = self.mock_api_client
        self.mock_notifier_class.return_value = self.mock_notifier
        self.mock_location_service_class.return_value = self.mock_location_service
        self.mock_weather_service = MagicMock()
        self.mock_weather_service_class.return_value = self.mock_weather_service

    def tearDown(self):
        # Clean up wx App if necessary
        if self.app:
            # Process any pending events
            wx.SafeYield()
            # Destroy the app
            self.app.Destroy()

    def test_no_dialog_when_api_contact_present(self):
        """Test that no dialog is shown when API contact is present"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: "test@example.com"},
        }
        # No longer patching _check_api_contact_configured here
        app = WeatherApp(
            parent=None,
            weather_service=self.mock_weather_service,
            location_service=self.mock_location_service,
            notification_service=self.mock_notifier,
            api_client=self.mock_api_client,
            config=config,
        )
        try:
            # Assert the mocked dialog was NOT called
            self.mock_dialog_class.assert_not_called()
        finally:
            if app:
                # Hide the window first
                wx.CallAfter(app.Hide)
                wx.SafeYield()
                # Then destroy it
                wx.CallAfter(app.Destroy)
                wx.SafeYield()

    def test_check_called_on_init(self):
        """Test that the API contact check is called during initialization"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: ""},
        }
        # This test specifically checks if the method is called
        with patch.object(WeatherApp, "_check_api_contact_configured") as mock_check:
            app = WeatherApp(
                parent=None,
                weather_service=self.mock_weather_service,
                location_service=self.mock_location_service,
                notification_service=self.mock_notifier,
                api_client=self.mock_api_client,
                config=config
            )
            try:
                mock_check.assert_called_once()
            finally:
                if app:
                    # Hide the window first
                    wx.CallAfter(app.Hide)
                    wx.SafeYield()
                    # Then destroy it
                    wx.CallAfter(app.Destroy)
                    wx.SafeYield()

    def test_dialog_shown_when_api_contact_missing(self):
        """Test that dialog is shown when API contact is missing"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: ""},
        }
        # Set dialog return value for this test case - Use wx.ID_YES
        self.mock_dialog_instance.ShowModal.return_value = wx.ID_YES

        # Use patch only for OnSettings, dialog is patched in setUp
        with patch.object(WeatherApp, "OnSettings") as mock_on_settings:
            app = WeatherApp(
                parent=None,
                weather_service=self.mock_weather_service,
                location_service=self.mock_location_service,
                notification_service=self.mock_notifier,
                api_client=self.mock_api_client,
                config=config
            )
            try:
                self.mock_dialog_class.assert_called_once()
                mock_on_settings.assert_called_once()
            finally:
                if app:
                    # Hide the window first
                    wx.CallAfter(app.Hide)
                    wx.SafeYield()
                    # Then destroy it
                    wx.CallAfter(app.Destroy)
                    wx.SafeYield()

    def test_dialog_shown_when_api_settings_missing(self):
        """Test that dialog is shown when api_settings section is missing"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            # api_settings section is missing
        }
        # Set dialog return value for this test case - Use wx.ID_YES
        self.mock_dialog_instance.ShowModal.return_value = wx.ID_YES

        # Use patch only for OnSettings
        with patch.object(WeatherApp, "OnSettings") as mock_on_settings:
            app = WeatherApp(
                parent=None,
                weather_service=self.mock_weather_service,
                location_service=self.mock_location_service,
                notification_service=self.mock_notifier,
                api_client=self.mock_api_client,
                config=config
            )
            try:
                self.mock_dialog_class.assert_called_once()
                mock_on_settings.assert_called_once()
            finally:
                if app:
                    # Hide the window first
                    wx.CallAfter(app.Hide)
                    wx.SafeYield()
                    # Then destroy it
                    wx.CallAfter(app.Destroy)
                    wx.SafeYield()

    def test_settings_not_opened_if_dialog_cancelled(self):
        """Test that settings are not opened if dialog is cancelled"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: ""},
        }
        # Set dialog return value for this test case
        self.mock_dialog_instance.ShowModal.return_value = wx.ID_CANCEL

        # Use patch only for OnSettings
        with patch.object(WeatherApp, "OnSettings") as mock_on_settings:
            app = WeatherApp(
                parent=None,
                weather_service=self.mock_weather_service,
                location_service=self.mock_location_service,
                notification_service=self.mock_notifier,
                api_client=self.mock_api_client,
                config=config
            )
            try:
                self.mock_dialog_class.assert_called_once()
                mock_on_settings.assert_not_called()
            finally:
                if app:
                    # Hide the window first
                    wx.CallAfter(app.Hide)
                    wx.SafeYield()
                    # Then destroy it
                    wx.CallAfter(app.Destroy)
                    wx.SafeYield()
