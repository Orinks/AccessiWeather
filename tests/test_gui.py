"""Tests for the GUI components"""

import json
import os
import time
import wx

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import NoaaApiClient
from accessiweather.gui.dialogs import LocationDialog, WeatherDiscussionDialog
from accessiweather.gui.weather_app import WeatherApp

# import wx.richtext  # Not used directly in this file's tests


# from accessiweather.location import LocationManager # Unused import


# Fixtures `wx_app` and `temp_config_file` moved to conftest.py


class TestLocationDialog:
    """Test suite for LocationDialog"""

    def setup_method(self):
        """Set up test fixture"""
        # Create geocoding service mock
        patch_target = "accessiweather.gui.dialogs.GeocodingService"
        self.geocoding_patcher = patch(patch_target)
        self.mock_geocoding_class = self.geocoding_patcher.start()
        self.mock_geocoding = MagicMock()
        self.mock_geocoding_class.return_value = self.mock_geocoding

    def teardown_method(self):
        """Tear down test fixture"""
        # Stop geocoding patch
        self.geocoding_patcher.stop()

    def test_init(self, wx_app_isolated):
        """Test initialization"""
        # Ensure we have a wx.App instance
        assert wx.App.Get() is not None

        dialog = LocationDialog(
            None, title="Test Dialog", location_name="Test", lat=35.0, lon=-80.0
        )
        try:
            assert dialog.name_ctrl.GetValue() == "Test"
            assert dialog.latitude == 35.0
            assert dialog.longitude == -80.0
            assert "Custom coordinates: 35.0" in dialog.result_text.GetValue()
        finally:
            dialog.Destroy()
            wx.SafeYield()

    def test_validation(self, wx_app_isolated):
        """Test input validation"""
        # Ensure we have a wx.App instance
        assert wx.App.Get() is not None

        dialog = LocationDialog(None)
        try:
            # Set initial state with valid coordinates
            dialog.latitude = 35.0
            dialog.longitude = -80.0
            dialog.result_text.SetValue("Custom coordinates: 35.0, -80.0")

            # Test with valid inputs
            dialog.name_ctrl.SetValue("Test")

            # Mock the event
            event = MagicMock()
            dialog.OnOK(event)

            # Skip should have been called for valid inputs
            event.Skip.assert_called_once()

            # Test with empty name
            event.reset_mock()
            dialog.name_ctrl.SetValue("")

            # Need to patch MessageBox
            with patch("wx.MessageBox") as mock_message_box:
                dialog.OnOK(event)

                # Skip should not have been called
                assert not event.Skip.called

                # MessageBox should have been called
                mock_message_box.assert_called_once()
                args = mock_message_box.call_args[0]
                assert "name" in args[0].lower()
        finally:
            dialog.Destroy()
            wx.SafeYield()

    def test_get_values(self, wx_app_isolated):
        """Test getting values from the dialog"""
        # Ensure we have a wx.App instance
        assert wx.App.Get() is not None

        dialog = LocationDialog(None)
        try:
            dialog.name_ctrl.SetValue("Test")
            dialog.latitude = 35.0
            dialog.longitude = -80.0

            name, lat, lon = dialog.GetValues()
            assert name == "Test"
            assert lat == 35.0
            assert lon == -80.0
        finally:
            dialog.Destroy()
            wx.SafeYield()


class TestWeatherDiscussionDialog:
    """Test suite for WeatherDiscussionDialog"""

    def test_init(self, wx_app_isolated):
        """Test initialization"""
        # Ensure we have a wx.App instance
        assert wx.App.Get() is not None

        dialog = WeatherDiscussionDialog(None, title="Test Discussion", text="Test discussion text")
        try:
            assert dialog.text_ctrl.GetValue() == "Test discussion text"
        finally:
            dialog.Destroy()
            wx.SafeYield()


class TestWeatherApp:
    """Test suite for WeatherApp"""

    @pytest.fixture
    def mock_components(self):
        """Mock the components used by WeatherApp"""
        # Create mock instances
        mock_api_client = MagicMock(spec=NoaaApiClient)
        mock_notifier = MagicMock()
        mock_location_service = MagicMock()
        mock_weather_service = MagicMock()

        # Configure mock location service to return valid data
        mock_location_service.get_all_locations.return_value = ["Test City"]
        mock_location_service.get_current_location.return_value = ("Test City", 35.0, -80.0)

        yield {
            "api_client": mock_api_client,
            "notifier": mock_notifier,
            "location_service": mock_location_service,
            "weather_service": mock_weather_service,
        }

    def test_init_with_default_config(self, wx_app_isolated, mock_components, monkeypatch):
        """Test initialization with default config"""
        # Ensure we have a wx.App instance
        assert wx.App.Get() is not None

        # Patch os.path.exists to return False for all config paths
        monkeypatch.setattr(os.path, "exists", lambda path: False)

        # Create app with mocked components
        app = None
        try:
            # Patch the _check_api_contact_configured method to avoid UI interactions
            with patch.object(WeatherApp, "_check_api_contact_configured"):
                app = WeatherApp(
                    parent=None,
                    weather_service=mock_components["weather_service"],
                    location_service=mock_components["location_service"],
                    notification_service=mock_components["notifier"],
                    api_client=mock_components["api_client"],
                )

                # Check that the dependencies were properly set
                assert app.api_client == mock_components["api_client"]
                assert app.location_service == mock_components["location_service"]
        finally:
            if app:
                app.Destroy()
                wx.SafeYield()

    def test_init_with_config_file(
        self, wx_app_isolated, mock_components, temp_config_file, monkeypatch
    ):
        """Test initialization with config file"""
        # Ensure we have a wx.App instance
        assert wx.App.Get() is not None

        # Patch os.path.exists to return True only for our temp config file
        original_exists = os.path.exists

        def mock_exists(path):
            if path == temp_config_file:
                return True
            return original_exists(path)

        monkeypatch.setattr(os.path, "exists", mock_exists)

        # Patch open to return our temp config file content
        original_open = open

        def mock_open(file, *args, **kwargs):
            if file == temp_config_file:
                return original_open(temp_config_file, *args, **kwargs)
            return original_open(file, *args, **kwargs)

        monkeypatch.setattr("builtins.open", mock_open)

        # Load config from the temp file
        with open(temp_config_file, "r") as f:
            config = json.load(f)

        # Create a new WeatherApp instance
        app = None
        try:
            # Patch the _check_api_contact_configured method to avoid UI interactions
            with patch.object(WeatherApp, "_check_api_contact_configured"):
                # Create app with the loaded config
                app = WeatherApp(
                    parent=None,
                    weather_service=mock_components["weather_service"],
                    location_service=mock_components["location_service"],
                    notification_service=mock_components["notifier"],
                    api_client=mock_components["api_client"],
                    config=config,
                )

                # Check that the dependencies were properly set
                assert app.api_client == mock_components["api_client"]
                assert app.location_service == mock_components["location_service"]
                assert app.config == config
        finally:
            if app:
                app.Destroy()
                wx.SafeYield()

    @patch("wx.CallAfter")
    def test_fetch_weather_data_with_proper_headers(
        self, mock_call_after, wx_app_isolated, mock_components, monkeypatch
    ):
        """Test that _FetchWeatherData uses proper headers from API client"""
        # Ensure we have a wx.App instance
        assert wx.App.Get() is not None

        # Create real API client with contact info
        api_client = NoaaApiClient(user_agent="AccessiWeather", contact_info="test@example.com")

        # Mock requests.get to check headers
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"properties": {"forecast": "https://api.example.com/forecast"}}
        )

        # Mock for the second request to forecast URL
        mock_forecast_response = MagicMock()
        mock_forecast_response.status_code = 200
        mock_forecast_response.json = MagicMock(return_value={"properties": {"periods": []}})

        # Create a mock for requests.get that returns appropriate responses
        def mock_requests_get(url, **kwargs):
            # Since we're making two different requests, return different
            # mock responses
            if "api.example.com/forecast" in url:
                return mock_forecast_response
            return mock_response

        mock_get = MagicMock(side_effect=mock_requests_get)
        monkeypatch.setattr("requests.get", mock_get)

        # Create a WeatherApp with our mocked components
        app = None
        try:
            # Patch the _check_api_contact_configured method to avoid UI interactions
            with patch.object(WeatherApp, "_check_api_contact_configured"):
                app = WeatherApp(
                    parent=None,
                    weather_service=mock_components["weather_service"],
                    location_service=mock_components["location_service"],
                    notification_service=mock_components["notifier"],
                    api_client=api_client,
                )

                # Need to wait a moment for all initialization to complete
                time.sleep(0.1)

                # Call the method with a test location
                location = ("Test City", 35.0, -80.0)
                app._FetchWeatherData(location)

                # Give a moment for async threads to execute
                time.sleep(0.1)

                # Verify that requests.get was called at least once
                assert mock_get.call_count > 0, "requests.get was never called"

                # Verify that the headers were set properly
                for call in mock_get.call_args_list:
                    _, kwargs = call
                    if "headers" in kwargs:
                        headers = kwargs["headers"]
                        if "User-Agent" in headers:
                            user_agent = headers["User-Agent"]
                            assert "test@example.com" in user_agent
                            break
                else:
                    # No call to requests.get had User-Agent header
                    # with contact info
                    assert False, "No call to requests.get had User-Agent header with contact info"
        finally:
            if app:
                app.Destroy()
                wx.SafeYield()

    # Removed announcement tests as the feature was removed based on user
    # feedback


# SettingsDialog tests moved to tests/test_settings_dialog.py
