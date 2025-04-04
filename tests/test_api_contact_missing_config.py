"""Tests for the API contact check when config file is missing"""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.weather_app import WeatherApp


# Create a wx App fixture for testing
@pytest.fixture
def wx_app():
    """Create a wx App for testing"""
    app = wx.App()
    yield app


class TestApiContactMissingConfig:
    """Test suite for the API contact check when config file is missing"""

    @pytest.fixture
    def mock_components(self):
        """Mock the components used by WeatherApp"""
        with patch(
            "accessiweather.api_client.NoaaApiClient"
        ) as mock_api_client_class, patch(
            "accessiweather.notifications.WeatherNotifier"
        ) as mock_notifier_class, patch(
            "accessiweather.location.LocationManager"
        ) as mock_location_manager_class:

            # Create mock instances
            mock_api_client = MagicMock()
            mock_notifier = MagicMock()
            mock_location_manager = MagicMock()

            # Configure mock location manager to return valid data
            mock_location_manager.get_all_locations.return_value = [
                "Test City"
            ]
            mock_location_manager.get_current_location.return_value = (
                "Test City",
                35.0,
                -80.0,
            )

            # Configure mock classes to return mock instances
            mock_api_client_class.return_value = mock_api_client
            mock_notifier_class.return_value = mock_notifier
            mock_location_manager_class.return_value = mock_location_manager

            yield {
                "api_client": mock_api_client,
                "notifier": mock_notifier,
                "location_manager": mock_location_manager,
            }

    def test_dialog_shown_when_config_file_missing(
        self, wx_app, mock_components
    ):
        """Test that dialog is shown when config file doesn't exist"""
        # Create a mock for OnSettings
        mock_on_settings = MagicMock()

        # Create a mock for MessageDialog
        mock_dialog = MagicMock()
        mock_dialog.ShowModal.return_value = wx.ID_OK
        # Create a WeatherApp instance with a mocked config path that
        # doesn't exist
        app = None
        try:
            # Patch the methods we want to test and os.path.exists
            with patch("os.path.exists", return_value=False), patch.object(
                WeatherApp, "OnSettings", mock_on_settings
            ), patch("wx.MessageDialog", return_value=mock_dialog):

                # Create the app - this should trigger the API contact check
                app = WeatherApp(
                    parent=None,
                    location_manager=mock_components["location_manager"],
                    api_client=mock_components["api_client"],
                    notifier=mock_components["notifier"],
                )
                # The _check_api_contact_configured method should have been
                # called during initialization and should have shown a dialog
                # and called OnSettings

                # Assert that MessageDialog was created
                wx.MessageDialog.assert_called_once()
                # Assert that OnSettings was called since dialog returned
                # wx.ID_OK
                mock_on_settings.assert_called_once()
        finally:
            if app:
                app.Destroy()
