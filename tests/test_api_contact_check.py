"""Tests for the API contact check feature on application startup"""

# Import faulthandler setup first to enable faulthandler
<<<<<<< Updated upstream
=======


>>>>>>> Stashed changes
from unittest.mock import MagicMock, patch

import unittest
from unittest.mock import MagicMock, patch
import wx
<<<<<<< Updated upstream

from accessiweather.gui.settings_dialog import API_CONTACT_KEY
from accessiweather.gui.weather_app import WeatherApp
from tests.faulthandler_setup import cleanup_wx_app

# Use the wx_app fixture from conftest.py


@pytest.fixture(autouse=True)
def wx_app_for_tests():
    """Create a wx App for testing"""
    app = wx.App()
    yield app


@pytest.fixture(autouse=True)
def patch_weather_app_update():
    """Patch the WeatherApp.UpdateWeatherData method to prevent weather data updates"""
    with patch.object(WeatherApp, "UpdateWeatherData"):
        yield


@pytest.fixture
def mock_location_service():
    """Create a mock location service that returns a valid location"""
    mock_service = MagicMock()
    mock_service.get_current_location.return_value = ("Test City", 35.0, -80.0)
    return mock_service


@pytest.fixture
def mock_weather_service():
    """Create a mock weather service"""
    return MagicMock()


class TestApiContactCheck:
=======
# Ensure wx.App is created before any wx controls
if not wx.GetApp():
    wx.App(False) 
from accessiweather.gui.weather_app import WeatherApp
from accessiweather.gui.settings_dialog import API_CONTACT_KEY

class TestApiContactCheck(unittest.TestCase):
>>>>>>> Stashed changes
    """Test suite for the API contact check feature on application startup"""

    def setUp(self):
        # Ensure a wx.App exists for GUI object creation (even mocks)
        # Using False prevents starting the real event loop
        self.app = wx.App(False) 

        # Patch the dependencies
        patcher_api_client = patch("accessiweather.api_client.NoaaApiClient")
        patcher_notifier = patch("accessiweather.notifications.WeatherNotifier")
        patcher_location_service = patch("accessiweather.services.location_service.LocationService")
        self.patcher_dialog = patch("wx.MessageDialog") # Centralize dialog patching

        self.addCleanup(patcher_api_client.stop)
        self.addCleanup(patcher_notifier.stop)
        self.addCleanup(patcher_location_service.stop)
        self.addCleanup(self.patcher_dialog.stop) # Add cleanup for dialog patcher

        self.mock_api_client_class = patcher_api_client.start()
        self.mock_notifier_class = patcher_notifier.start()
        self.mock_location_service_class = patcher_location_service.start()
        self.mock_dialog_class = self.patcher_dialog.start() # Start dialog patcher

        # Configure the mock dialog instance
        self.mock_dialog_instance = MagicMock()
        self.mock_dialog_class.return_value = self.mock_dialog_instance

<<<<<<< Updated upstream
    def test_no_dialog_when_api_contact_present(self, mock_components, mock_location_service, mock_weather_service):
=======
        # Create mock instances for other dependencies
        self.mock_api_client = MagicMock()
        self.mock_notifier = MagicMock()
        self.mock_location_service = MagicMock()
        self.mock_location_service.get_all_locations.return_value = ["Test City"]
        self.mock_location_service.get_current_location.return_value = ("Test City", 35.0, -80.0)
        self.mock_api_client_class.return_value = self.mock_api_client
        self.mock_notifier_class.return_value = self.mock_notifier
        self.mock_location_service_class.return_value = self.mock_location_service

    def tearDown(self):
        # Clean up wx App if necessary, though wx.App(False) often handles itself
        # It's safer to explicitly manage if needed, but start without it.
        # Example: if self.app: self.app.Destroy()
        pass

    def test_no_dialog_when_api_contact_present(self):
>>>>>>> Stashed changes
        """Test that no dialog is shown when API contact is present"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: "test@example.com"},
        }
        # No longer patching _check_api_contact_configured here
        app = WeatherApp(weather_service=MagicMock(), 
            parent=None,
            location_service=self.mock_location_service,
            api_client=self.mock_api_client,
            notification_service=self.mock_notifier,
            config=config,
        )
        try:
            # Assert the mocked dialog was NOT called
            self.mock_dialog_class.assert_not_called()
        finally:
            if app: app.Destroy() # Basic cleanup

<<<<<<< Updated upstream
        # Mock the _check_api_contact_configured method
        with patch.object(WeatherApp, "_check_api_contact_configured") as mock_check:
            # Create the app
            app = WeatherApp(
                parent=None,
                weather_service=mock_weather_service,
                location_service=mock_location_service,
                notification_service=MagicMock(),
                api_client=mock_components["api_client"],
                config=config,
            )

            try:
                # Verify the method was called
                mock_check.assert_called_once()
            finally:
                cleanup_wx_app(app)

    def test_dialog_shown_when_api_contact_missing(self, mock_components, mock_location_service, mock_weather_service):
=======
    def test_dialog_shown_when_api_contact_missing(self):
>>>>>>> Stashed changes
        """Test that dialog is shown when API contact is missing"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: ""},
        }
<<<<<<< Updated upstream

        # Mock the dialog and OnSettings method
        with (
            patch("wx.MessageDialog") as mock_dialog_class,
            patch.object(WeatherApp, "OnSettings") as mock_on_settings,
        ):
            # Configure the mock dialog
            mock_dialog = MagicMock()
            mock_dialog.ShowModal.return_value = wx.ID_OK
            mock_dialog_class.return_value = mock_dialog

            # Create the app
            app = WeatherApp(
                parent=None,
                weather_service=MagicMock(),
                location_service=MagicMock(),
                notification_service=MagicMock(),
                api_client=mock_components["api_client"],
=======
        # Set dialog return value for this test case - Use wx.ID_YES
        self.mock_dialog_instance.ShowModal.return_value = wx.ID_YES
        
        # Use patch only for OnSettings, dialog is patched in setUp
        with patch.object(WeatherApp, "OnSettings") as mock_on_settings:
            app = WeatherApp(weather_service=MagicMock(), 
                parent=None,
                location_service=self.mock_location_service,
                api_client=self.mock_api_client,
                notification_service=self.mock_notifier,
>>>>>>> Stashed changes
                config=config,
            )
            try:
                self.mock_dialog_class.assert_called_once()
                mock_on_settings.assert_called_once()
            finally:
                 if app: app.Destroy()

<<<<<<< Updated upstream
    def test_dialog_shown_when_api_settings_missing(self, mock_components, mock_location_service, mock_weather_service):
=======
    def test_dialog_shown_when_api_settings_missing(self):
>>>>>>> Stashed changes
        """Test that dialog is shown when api_settings section is missing"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            # api_settings section is missing
        }
<<<<<<< Updated upstream

        # Mock the dialog and OnSettings method
        with (
            patch("wx.MessageDialog") as mock_dialog_class,
            patch.object(WeatherApp, "OnSettings") as mock_on_settings,
        ):
            # Configure the mock dialog
            mock_dialog = MagicMock()
            mock_dialog.ShowModal.return_value = wx.ID_OK
            mock_dialog_class.return_value = mock_dialog

            # Create the app
            app = WeatherApp(
                parent=None,
                weather_service=MagicMock(),
                location_service=MagicMock(),
                notification_service=MagicMock(),
                api_client=mock_components["api_client"],
=======
        # Set dialog return value for this test case - Use wx.ID_YES
        self.mock_dialog_instance.ShowModal.return_value = wx.ID_YES
        
        # Use patch only for OnSettings
        with patch.object(WeatherApp, "OnSettings") as mock_on_settings:
            app = WeatherApp(weather_service=MagicMock(), 
                parent=None,
                location_service=self.mock_location_service,
                api_client=self.mock_api_client,
                notification_service=self.mock_notifier,
>>>>>>> Stashed changes
                config=config,
            )
            try:
                self.mock_dialog_class.assert_called_once()
                mock_on_settings.assert_called_once()
            finally:
                 if app: app.Destroy()

<<<<<<< Updated upstream
    def test_settings_not_opened_if_dialog_cancelled(self, mock_components, mock_location_service, mock_weather_service):
=======
    def test_settings_not_opened_if_dialog_cancelled(self):
>>>>>>> Stashed changes
        """Test that settings are not opened if dialog is cancelled"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: ""},
        }
<<<<<<< Updated upstream

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
                weather_service=MagicMock(),
                location_service=MagicMock(),
                notification_service=MagicMock(),
                api_client=mock_components["api_client"],
=======
        # Set dialog return value for this test case
        self.mock_dialog_instance.ShowModal.return_value = wx.ID_CANCEL
        
        # Use patch only for OnSettings
        with patch.object(WeatherApp, "OnSettings") as mock_on_settings:
            app = WeatherApp(weather_service=MagicMock(), 
                parent=None,
                location_service=self.mock_location_service,
                api_client=self.mock_api_client,
                notification_service=self.mock_notifier,
>>>>>>> Stashed changes
                config=config,
            )
            try:
                self.mock_dialog_class.assert_called_once()
                mock_on_settings.assert_not_called()
            finally:
                 if app: app.Destroy()

<<<<<<< Updated upstream
    def test_check_called_on_init(self, mock_components, mock_location_service, mock_weather_service):
=======
    def test_check_called_on_init(self):
>>>>>>> Stashed changes
        """Test that the API contact check is called during initialization"""
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: ""},
        }
<<<<<<< Updated upstream

        # Mock the _check_api_contact_configured method
        with (
            patch.object(WeatherApp, "_check_api_contact_configured") as mock_check,
            patch("wx.MessageDialog"),
        ):  # Prevent dialog from showing
            # Create the app
            app = WeatherApp(
                parent=None,
                weather_service=MagicMock(),
                location_service=MagicMock(),
                notification_service=MagicMock(),
                api_client=mock_components["api_client"],
=======
        # This test specifically checks if the method is called,
        # so patching it directly is appropriate here. Dialog patch from setUp is active but irrelevant.
        with patch.object(WeatherApp, "_check_api_contact_configured") as mock_check: 
            app = WeatherApp(weather_service=MagicMock(), 
                parent=None,
                location_service=self.mock_location_service,
                api_client=self.mock_api_client,
                notification_service=self.mock_notifier,
>>>>>>> Stashed changes
                config=config,
            )
            try:
                mock_check.assert_called_once()
            finally:
                 if app: app.Destroy()
