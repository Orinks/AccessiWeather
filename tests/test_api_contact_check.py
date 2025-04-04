"""Tests for the API contact check feature on application startup."""

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


class TestApiContactCheck:
    """Test suite for the API contact check feature on application startup."""

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

    @pytest.fixture
    def config_with_api_contact(self):
        """Config with valid API contact information."""
        return {
            "locations": {},
            "current": None,
            "settings": {
                "update_interval_minutes": 30,
                "alert_radius_miles": 25,
            },
            "api_settings": {"api_contact": "test@example.com"},
        }

    @pytest.fixture
    def config_without_api_contact(self):
        """Config with missing API contact information."""
        return {
            "locations": {},
            "current": None,
            "settings": {
                "update_interval_minutes": 30,
                "alert_radius_miles": 25,
            },
            "api_settings": {"api_contact": ""},  # Empty string
        }

    @pytest.fixture
    def config_without_api_settings(self):
        """Config without api_settings section."""
        return {
            "locations": {},
            "current": None,
            "settings": {
                "update_interval_minutes": 30,
                "alert_radius_miles": 25,
            },
            # No api_settings section
        }

    def test_no_dialog_when_api_contact_present(
        self, wx_app, mock_components, config_with_api_contact
    ):
        """Test that no dialog is shown when API contact is present."""
        with patch("wx.MessageDialog") as mock_dialog, patch.object(
            WeatherApp, "_check_api_contact_configured"
        ):
            app = None
            try:
                app = WeatherApp(
                    parent=None,
                    location_manager=mock_components["location_manager"],
                    api_client=mock_components["api_client"],
                    notifier=mock_components["notifier"],
                    config=config_with_api_contact,
                )

                # Reset the mock to clear any calls during initialization
                mock_dialog.reset_mock()

                # Now call the method directly
                app._check_api_contact_configured.restore()

                # Also verify that OnSettings was not called
                with patch.object(app, "OnSettings") as mock_on_settings:
                    app._check_api_contact_configured()

                    # Assert that MessageDialog was not created
                    mock_dialog.assert_not_called()

                    # Assert that OnSettings was not called
                    mock_on_settings.assert_not_called()
            finally:
                if app:
                    app.Destroy()

    def test_dialog_shown_when_api_contact_missing(
        self, wx_app, mock_components, config_without_api_contact
    ):
        """Test that dialog is shown when API contact is missing."""
        # Create a mock for OnSettings
        mock_on_settings = MagicMock()

        # Create a mock for MessageDialog
        mock_dialog = MagicMock()
        mock_dialog.ShowModal.return_value = wx.ID_OK

        # Create a WeatherApp instance with the empty API contact config
        app = None
        try:
            # Patch the methods we want to test
            with patch.object(WeatherApp, "OnSettings", mock_on_settings), patch(
                "wx.MessageDialog", return_value=mock_dialog
            ):

                # Create the app with our config that has empty API contact
                app = WeatherApp(
                    parent=None,
                    location_manager=mock_components["location_manager"],
                    api_client=mock_components["api_client"],
                    notifier=mock_components["notifier"],
                    config=config_without_api_contact,
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

    def test_dialog_shown_when_api_settings_missing(
        self, wx_app, mock_components, config_without_api_settings
    ):
        """Test that dialog is shown when api_settings section is missing."""
        # Create a mock for OnSettings
        mock_on_settings = MagicMock()

        # Create a mock for MessageDialog
        mock_dialog = MagicMock()
        mock_dialog.ShowModal.return_value = wx.ID_OK

        # Create a WeatherApp instance with the config missing api_settings
        app = None
        try:
            # Patch the methods we want to test
            with patch.object(WeatherApp, "OnSettings", mock_on_settings), patch(
                "wx.MessageDialog", return_value=mock_dialog
            ):
                # Create the app with our config that has no api_settings
                # section
                app = WeatherApp(
                    parent=None,
                    location_manager=mock_components["location_manager"],
                    api_client=mock_components["api_client"],
                    notifier=mock_components["notifier"],
                    config=config_without_api_settings,
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

    def test_settings_not_opened_if_dialog_cancelled(
        self, wx_app, mock_components, config_without_api_contact
    ):
        """Test that settings are not opened if dialog is cancelled."""
        # Create a mock for OnSettings
        mock_on_settings = MagicMock()

        # Create a mock for MessageDialog that returns CANCEL
        mock_dialog = MagicMock()
        mock_dialog.ShowModal.return_value = wx.ID_CANCEL

        # Create a WeatherApp instance with the empty API contact config
        app = None
        try:
            # Patch the methods we want to test
            with patch.object(WeatherApp, "OnSettings", mock_on_settings), patch(
                "wx.MessageDialog", return_value=mock_dialog
            ):

                # Create the app with our config that has empty API contact
                app = WeatherApp(
                    parent=None,
                    location_manager=mock_components["location_manager"],
                    api_client=mock_components["api_client"],
                    notifier=mock_components["notifier"],
                    config=config_without_api_contact,
                )
                # The _check_api_contact_configured method should have been
                # called during initialization and should have shown a dialog
                # but NOT called OnSettings since we returned CANCEL

                # Assert that MessageDialog was created
                wx.MessageDialog.assert_called_once()
                # Assert that OnSettings was NOT called since dialog returned
                # wx.ID_CANCEL
                mock_on_settings.assert_not_called()
        finally:
            if app:
                app.Destroy()

    def test_check_called_on_init(self, wx_app, mock_components, config_without_api_contact):
        """Test that the API contact check is called during initialization."""
        with patch.object(WeatherApp, "_check_api_contact_configured") as mock_check, patch(
            "wx.MessageDialog"
        ):
            app = None
            try:
                app = WeatherApp(
                    parent=None,
                    location_manager=mock_components["location_manager"],
                    api_client=mock_components["api_client"],
                    notifier=mock_components["notifier"],
                    config=config_without_api_contact,
                )
                # Assert that _check_api_contact_configured was called
                # during initialization
                mock_check.assert_called_once()
            finally:
                if app:
                    app.Destroy()
