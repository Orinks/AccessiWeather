"""Tests for the API contact check when config file is missing."""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.weather_app import WeatherApp


# Create a wx App fixture for testing
@pytest.fixture
def wx_app():
    """Create a wx App for testing."""
    app = wx.App()
    yield app


class TestApiContactMissingConfig:
    """Test suite for the API contact check when config file is missing."""

    @pytest.fixture
    def mock_components(self):
        """Mock the components used by WeatherApp."""
        with patch("accessiweather.api_client.NoaaApiClient") as mock_api_client_class, patch(
            "accessiweather.notifications.WeatherNotifier"
        ) as mock_notifier_class, patch(
            "accessiweather.location.LocationManager"
        ) as mock_location_manager_class:

            # Create mock instances
            mock_api_client = MagicMock()
            mock_notifier = MagicMock()
            mock_location_manager = MagicMock()

            # Configure mock location manager to return valid data
            mock_location_manager.get_all_locations.return_value = ["Test City"]
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

    # Define patch target string to avoid long line
    _CHECK_API_CONTACT_PATCH_TARGET = (
        "accessiweather.gui.weather_app.WeatherApp." "_check_api_contact_configured"
    )

    @patch("accessiweather.gui.ui_manager.UIManager")  # Patch UIManager
    @patch("accessiweather.gui.weather_app.WeatherAppEventHandlers")
    @patch("wx.MessageDialog")
    @patch("os.path.exists", return_value=False)  # Mock os.path.exists here
    def test_dialog_shown_when_config_file_missing(
        self,
        mock_exists,
        mock_message_dialog_class,
        mock_event_handlers_class,
        mock_ui_manager,
        wx_app,
        mock_components,
    ):
        """Test that dialog is shown when config file doesn't exist."""
        # Configure the mock MessageDialog instance
        mock_dialog_instance = MagicMock()
        mock_dialog_instance.ShowModal.return_value = wx.ID_OK
        mock_message_dialog_class.return_value = mock_dialog_instance

        # Configure the mock EventHandlers instance
        mock_handlers_instance = MagicMock()
        mock_event_handlers_class.return_value = mock_handlers_instance

        # Create a WeatherApp instance. os.path.exists is already mocked.
        app = None
        try:
            # No need for inner patches

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

            # Assert that MessageDialog was created and shown
            mock_message_dialog_class.assert_called_once()
            mock_dialog_instance.ShowModal.assert_called_once()

            # Assert OnSettings called on the mocked handlers instance
            mock_handlers_instance.OnSettings.assert_called_once()
        finally:
            if app:
                app.Destroy()
