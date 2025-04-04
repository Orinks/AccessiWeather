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

    @patch("accessiweather.gui.ui_manager.UIManager")  # Patch UIManager
    def test_no_dialog_when_api_contact_present(
        self, mock_ui_manager, wx_app, mock_components, config_with_api_contact
    ):
        """Test that no dialog is shown when API contact is present."""
        # Patch MessageDialog. No need to patch _check_api_contact_configured
        with patch("wx.MessageDialog") as mock_dialog:
            # mock_ui_manager is already active due to the decorator
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

                # Patch OnSettings on the actual event_handlers instance
                with patch.object(app.event_handlers, "OnSettings") as mock_on_settings:
                    # Call the method under test again directly
                    # (it was already called during init, but we want to check
                    # behaviour with the specific config provided)
                    app._check_api_contact_configured()

                    # Assert that MessageDialog was not created or shown
                    mock_dialog.assert_not_called()
                    # If called during init check ShowModal
                    if mock_dialog.call_count > 0:
                        mock_dialog.return_value.ShowModal.assert_not_called()

                    # Assert that OnSettings on the handler was not called
                    mock_on_settings.assert_not_called()
            finally:
                if app:
                    app.Destroy()

    @patch("accessiweather.gui.weather_app.WeatherAppEventHandlers")
    @patch("wx.MessageDialog")
    def test_dialog_shown_when_api_contact_missing(
        self,
        mock_message_dialog_class,
        mock_event_handlers_class,
        wx_app,
        mock_components,
        config_without_api_contact,
    ):
        """Test that dialog is shown when API contact is missing."""
        # Configure the mock MessageDialog instance
        mock_dialog_instance = MagicMock()
        mock_dialog_instance.ShowModal.return_value = wx.ID_OK
        mock_message_dialog_class.return_value = mock_dialog_instance

        # Configure the mock EventHandlers instance
        mock_handlers_instance = MagicMock()
        mock_event_handlers_class.return_value = mock_handlers_instance

        # Create a WeatherApp instance with the empty API contact config
        app = None
        try:
            # No need for inner patches, outer patches handle it

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

            # Assert that MessageDialog was created and shown
            mock_message_dialog_class.assert_called_once()
            mock_dialog_instance.ShowModal.assert_called_once()

            # Assert OnSettings called on the mocked handlers instance
            mock_handlers_instance.OnSettings.assert_called_once()
        finally:
            if app:
                app.Destroy()

    @patch("accessiweather.gui.weather_app.WeatherAppEventHandlers")
    @patch("wx.MessageDialog")
    def test_dialog_shown_when_api_settings_missing(
        self,
        mock_message_dialog_class,
        mock_event_handlers_class,
        wx_app,
        mock_components,
        config_without_api_settings,
    ):
        """Test that dialog is shown when api_settings section is missing."""
        # Configure the mock MessageDialog instance
        mock_dialog_instance = MagicMock()
        mock_dialog_instance.ShowModal.return_value = wx.ID_OK
        mock_message_dialog_class.return_value = mock_dialog_instance

        # Configure the mock EventHandlers instance
        mock_handlers_instance = MagicMock()
        mock_event_handlers_class.return_value = mock_handlers_instance

        # Create a WeatherApp instance with the config missing api_settings
        app = None
        try:
            # No need for inner patches, outer patches handle it
            # Create the app with our config that has no api_settings section
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

            # Assert that MessageDialog was created and shown
            mock_message_dialog_class.assert_called_once()
            mock_dialog_instance.ShowModal.assert_called_once()

            # Assert OnSettings called on the mocked handlers instance
            mock_handlers_instance.OnSettings.assert_called_once()
        finally:
            if app:
                app.Destroy()

    @patch("accessiweather.gui.weather_app.WeatherAppEventHandlers")
    @patch("wx.MessageDialog")
    def test_settings_not_opened_if_dialog_cancelled(
        self,
        mock_message_dialog_class,
        mock_event_handlers_class,
        wx_app,
        mock_components,
        config_without_api_contact,
    ):
        """Test that settings are not opened if dialog is cancelled."""
        # Configure the mock MessageDialog instance to return CANCEL
        mock_dialog_instance = MagicMock()
        mock_dialog_instance.ShowModal.return_value = wx.ID_CANCEL
        mock_message_dialog_class.return_value = mock_dialog_instance

        # Configure the mock EventHandlers instance
        mock_handlers_instance = MagicMock()
        mock_event_handlers_class.return_value = mock_handlers_instance

        # Create a WeatherApp instance with the empty API contact config
        app = None
        try:
            # No need for inner patches, outer patches handle it

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

            # Assert that MessageDialog was created and shown
            mock_message_dialog_class.assert_called_once()
            mock_dialog_instance.ShowModal.assert_called_once()

            # Assert that OnSettings was NOT called on the handler instance
            mock_handlers_instance.OnSettings.assert_not_called()
        finally:
            if app:
                app.Destroy()

    def test_check_called_on_init(self, wx_app, mock_components, config_without_api_contact):
        """Test that the API contact check is called during initialization."""
        # Patch method and MessageDialog to prevent popups
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
