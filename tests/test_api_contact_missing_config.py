"""Tests for the API contact check when config file is missing"""

from unittest.mock import MagicMock, patch
import unittest
import wx
from accessiweather.gui.weather_app import WeatherApp

class TestApiContactMissingConfig(unittest.TestCase):
    """Test suite for the API contact check when config file is missing"""
    app = None

    @classmethod
    def setUpClass(cls):
        """Create a wx.App instance before running tests."""
        # Prevent wx errors in CI/headless environments
        if 'wxAssertionError' not in wx.__dict__:
            wx.DisableAsserts()
        cls.app = wx.App(False) # False means don't enter main loop

    @classmethod
    def tearDownClass(cls):
        """Clean up the wx.App instance after tests."""
        if cls.app:
            # Ensure pending events are processed before destroying
            # Use wx.GetApp().Yield() if available, otherwise skip
            current_app = wx.GetApp()
            if current_app and hasattr(current_app, 'Yield'):
                 current_app.Yield() 
            # Schedule destruction for after the current event loop iteration
            # Check if Destroy is callable before calling
            if hasattr(cls.app, 'Destroy') and callable(cls.app.Destroy):
                 wx.CallAfter(cls.app.Destroy) 
            cls.app = None

    def setUp(self):
        """Set up mocks for each test."""
        patcher_api_client = patch("accessiweather.api_client.NoaaApiClient")
        patcher_notifier = patch("accessiweather.notifications.WeatherNotifier")
        patcher_location_service = patch("accessiweather.services.location_service.LocationService")
        patcher_weather_service = patch("accessiweather.services.weather_service.WeatherService") # Mock weather service too
        # Centralize MessageDialog patch
        self.patcher_msg_dialog = patch("wx.MessageDialog", MagicMock()) 
        self.addCleanup(patcher_api_client.stop)
        self.addCleanup(patcher_notifier.stop)
        self.addCleanup(patcher_location_service.stop)
        self.addCleanup(patcher_weather_service.stop)
        self.addCleanup(self.patcher_msg_dialog.stop)
        self.mock_api_client_class = patcher_api_client.start()
        self.mock_notifier_class = patcher_notifier.start()
        self.mock_location_service_class = patcher_location_service.start()
        self.mock_weather_service_class = patcher_weather_service.start() # Start weather service mock
        self.mock_dialog_class = self.patcher_msg_dialog.start()
        self.mock_api_client = MagicMock()
        self.mock_notifier = MagicMock()
        self.mock_location_service = MagicMock()
        self.mock_weather_service = MagicMock() # Instance for weather service
        self.mock_location_service.get_all_locations.return_value = ["Test City"]
        self.mock_location_service.get_current_location.return_value = ("Test City", 35.0, -80.0)
        self.mock_api_client_class.return_value = self.mock_api_client
        self.mock_notifier_class.return_value = self.mock_notifier
        self.mock_location_service_class.return_value = self.mock_location_service
        self.mock_weather_service_class.return_value = self.mock_weather_service # Return instance

    def test_dialog_shown_when_config_file_missing(self):
        """Test that dialog is shown when config file doesn't exist"""
        mock_on_settings = MagicMock()
        # Use the class-level mock dialog
        mock_dialog_instance = self.mock_dialog_class.return_value 
        mock_dialog_instance.ShowModal.return_value = wx.ID_YES 
        app_instance = None # Renamed to avoid conflict with cls.app
        try:
            # Patch os.path.exists locally for this test
            # Patch OnSettings locally
            # No need to patch MessageDialog again, it's done in setUp
            with patch("os.path.exists", return_value=False), \
                 patch.object(WeatherApp, "OnSettings", new=mock_on_settings):
                app_instance = WeatherApp( 
                    parent=None,
                    # Pass mocked service instances
                    weather_service=self.mock_weather_service,
                    location_service=self.mock_location_service,
                    api_client=self.mock_api_client, # Keep for backward compatibility if needed
                    notification_service=self.mock_notifier,
                    # Pass a non-existent config path to trigger the missing file logic
                    config_path="nonexistent_config.json" 
                )
                # Check that the class mock was called
                self.mock_dialog_class.assert_called_once() 
                # Check the arguments passed to MessageDialog if needed
                # args, kwargs = self.mock_dialog_class.call_args
                # self.assertIn("API contact information is required", args[1])
                mock_on_settings.assert_called_once()
        finally:
            if app_instance:
                # Need to destroy the Frame instance safely using CallAfter
                wx.CallAfter(app_instance.Destroy) 
