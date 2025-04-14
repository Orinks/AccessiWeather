"""Tests for the API contact check feature on application startup"""

# Import faulthandler setup first to enable faulthandler
from tests.faulthandler_setup import cleanup_wx_app

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.weather_app import WeatherApp
from accessiweather.gui.settings_dialog import API_CONTACT_KEY


# Use the wx_app fixture from conftest.py


class TestApiContactCheck:
    """Test suite for the API contact check feature on application startup"""

    @pytest.fixture
    def mock_components(self):
        """Mock the components used by WeatherApp"""
        with (
            patch("accessiweather.api_client.NoaaApiClient") as mock_api_client_class,
            patch("accessiweather.notifications.WeatherNotifier") as mock_notifier_class,
            patch("accessiweather.location.LocationManager") as mock_location_manager_class,
        ):

            # Create mock instances
            mock_api_client = MagicMock()
            mock_notifier = MagicMock()
            mock_location_manager = MagicMock()

            # Configure mock location manager to return valid data
            mock_location_manager.get_all_locations.return_value = ["Test City"]
            mock_location_manager.get_current_location.return_value = ("Test City", 35.0, -80.0)

            # Configure mock classes to return mock instances
            mock_api_client_class.return_value = mock_api_client
            mock_notifier_class.return_value = mock_notifier
            mock_location_manager_class.return_value = mock_location_manager

            yield {
                "api_client": mock_api_client,
                "notifier": mock_notifier,
                "location_manager": mock_location_manager,
            }

    def test_no_dialog_when_api_contact_present(self, mock_components):
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
                location_manager=mock_components["location_manager"],
                api_client=mock_components["api_client"],
                notifier=mock_components["notifier"],
                config=config,
            )

            try:
                # Verify the method was called
                mock_check.assert_called_once()
            finally:
                cleanup_wx_app(app)

    def test_dialog_shown_when_api_contact_missing(self, mock_components):
        """Test that dialog is shown when API contact is missing"""
        # Create a config without API contact
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: ""},  # Empty string
        }

        # Mock the dialog and OnSettings method
        with patch("wx.MessageDialog") as mock_dialog_class, \
             patch.object(WeatherApp, "OnSettings") as mock_on_settings:
            # Configure the mock dialog
            mock_dialog = MagicMock()
            mock_dialog.ShowModal.return_value = wx.ID_OK
            mock_dialog_class.return_value = mock_dialog

            # Create the app
            app = WeatherApp(
                parent=None,
                location_manager=mock_components["location_manager"],
                api_client=mock_components["api_client"],
                notifier=mock_components["notifier"],
                config=config,
            )

            try:
                # Verify the dialog was shown
                mock_dialog_class.assert_called_once()
                # Verify OnSettings was called
                mock_on_settings.assert_called_once()
            finally:
                cleanup_wx_app(app)

    def test_dialog_shown_when_api_settings_missing(self, mock_components):
        """Test that dialog is shown when api_settings section is missing"""
        # Create a config without api_settings section
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            # No api_settings section
        }

        # Mock the dialog and OnSettings method
        with patch("wx.MessageDialog") as mock_dialog_class, \
             patch.object(WeatherApp, "OnSettings") as mock_on_settings:
            # Configure the mock dialog
            mock_dialog = MagicMock()
            mock_dialog.ShowModal.return_value = wx.ID_OK
            mock_dialog_class.return_value = mock_dialog

            # Create the app
            app = WeatherApp(
                parent=None,
                location_manager=mock_components["location_manager"],
                api_client=mock_components["api_client"],
                notifier=mock_components["notifier"],
                config=config,
            )

            try:
                # Verify the dialog was shown
                mock_dialog_class.assert_called_once()
                # Verify OnSettings was called
                mock_on_settings.assert_called_once()
            finally:
                cleanup_wx_app(app)

    def test_settings_not_opened_if_dialog_cancelled(self, mock_components):
        """Test that settings are not opened if dialog is cancelled"""
        # Create a config without API contact
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: ""},  # Empty string
        }

        # Mock the dialog and OnSettings method
        with patch("wx.MessageDialog") as mock_dialog_class, \
             patch.object(WeatherApp, "OnSettings") as mock_on_settings:
            # Configure the mock dialog to return CANCEL
            mock_dialog = MagicMock()
            mock_dialog.ShowModal.return_value = wx.ID_CANCEL
            mock_dialog_class.return_value = mock_dialog

            # Create the app
            app = WeatherApp(
                parent=None,
                location_manager=mock_components["location_manager"],
                api_client=mock_components["api_client"],
                notifier=mock_components["notifier"],
                config=config,
            )

            try:
                # Verify the dialog was shown
                mock_dialog_class.assert_called_once()
                # Verify OnSettings was NOT called
                mock_on_settings.assert_not_called()
            finally:
                cleanup_wx_app(app)

    def test_check_called_on_init(self, mock_components):
        """Test that the API contact check is called during initialization"""
        # Create a config without API contact
        config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {API_CONTACT_KEY: ""},  # Empty string
        }

        # Mock the _check_api_contact_configured method
        with patch.object(WeatherApp, "_check_api_contact_configured") as mock_check, \
             patch("wx.MessageDialog"):  # Prevent dialog from showing
            # Create the app
            app = WeatherApp(
                parent=None,
                location_manager=mock_components["location_manager"],
                api_client=mock_components["api_client"],
                notifier=mock_components["notifier"],
                config=config,
            )

            try:
                # Verify the method was called
                mock_check.assert_called_once()
            finally:
                cleanup_wx_app(app)
