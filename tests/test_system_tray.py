"""Tests for the system tray functionality."""

import logging
import time
from unittest.mock import MagicMock, patch

import pytest
import wx
import wx.adv

from accessiweather.gui.system_tray import TaskBarIcon
from accessiweather.gui.weather_app import WeatherApp

# Import faulthandler setup first to enable faulthandler
import tests.faulthandler_setup  # noqa: F401

logger = logging.getLogger(__name__)


class TestTaskBarIcon:
    """Tests for the TaskBarIcon class."""

    @pytest.fixture
    def mock_frame(self, wx_app):
        """Create a mock frame for testing."""
        frame = MagicMock(spec=WeatherApp)
        frame.IsIconized.return_value = False
        frame.IsShown.return_value = True
        yield frame

    def test_taskbar_icon_creation(self, wx_app, mock_frame):
        """Test that the TaskBarIcon can be created."""
        icon = None
        try:
            icon = TaskBarIcon(mock_frame)
            assert icon is not None
            assert isinstance(icon, wx.adv.TaskBarIcon)
        finally:
            if icon:
                icon.Destroy()
                time.sleep(0.1)  # Allow time for destruction

    def test_taskbar_icon_menu_creation(self, wx_app, mock_frame):
        """Test that the TaskBarIcon creates a menu."""
        icon = None
        try:
            icon = TaskBarIcon(mock_frame)
            # Call CreatePopupMenu which should return a wx.Menu
            menu = icon.CreatePopupMenu()
            assert menu is not None
            assert isinstance(menu, wx.Menu)

            # Check that the menu has items
            items = menu.GetMenuItems()
            assert len(items) > 0

            # Clean up
            menu.Destroy()
        finally:
            if icon:
                icon.Destroy()
                time.sleep(0.1)  # Allow time for destruction

    def test_show_hide_handler(self, wx_app, mock_frame):
        """Test the show/hide handler."""
        icon = None
        try:
            icon = TaskBarIcon(mock_frame)

            # Test when frame is shown
            mock_frame.IsShown.return_value = True
            icon.on_show_hide(None)
            mock_frame.Hide.assert_called_once()

            # Reset mock
            mock_frame.reset_mock()

            # Test when frame is hidden
            mock_frame.IsShown.return_value = False
            icon.on_show_hide(None)
            mock_frame.Show.assert_called_once()
            mock_frame.Raise.assert_called_once()
        finally:
            if icon:
                icon.Destroy()
                time.sleep(0.1)  # Allow time for destruction

    def test_exit_handler(self, wx_app, mock_frame):
        """Test the exit handler."""
        icon = None
        try:
            icon = TaskBarIcon(mock_frame)

            # Call the exit handler
            icon.on_exit(None)

            # Check that the frame's Close method was called with force=True
            mock_frame.Close.assert_called_once_with(force=True)
        finally:
            if icon:
                icon.Destroy()
                time.sleep(0.1)  # Allow time for destruction


class TestWeatherAppSystemTray:
    """Tests for the WeatherApp system tray integration."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for the WeatherApp."""
        with (
            patch("accessiweather.api_client.NoaaApiClient") as mock_api_client_class,
            patch("accessiweather.services.notification_service.NotificationService") as mock_notification_service_class,
            patch("accessiweather.services.location_service.LocationService") as mock_location_service_class,
            patch("accessiweather.services.weather_service.WeatherService") as mock_weather_service_class,
            patch("accessiweather.gui.system_tray.TaskBarIcon") as mock_taskbar_icon_class,
            patch("accessiweather.gui.weather_app_handlers.WeatherAppHandlers._check_api_contact_configured"),
        ):
            mock_api_client = mock_api_client_class.return_value
            mock_notification_service = mock_notification_service_class.return_value
            mock_location_service = mock_location_service_class.return_value
            mock_weather_service = mock_weather_service_class.return_value
            mock_taskbar_icon = mock_taskbar_icon_class.return_value

            # Configure mock location service
            mock_location_service.get_locations.return_value = {"Test City": (35.0, -80.0)}
            mock_location_service.get_current_location.return_value = ("Test City", 35.0, -80.0)
            mock_location_service.get_current_location_name.return_value = "Test City"

            # Create a default config with API contact info
            default_config = {
                "locations": {"Test City": {"lat": 35.0, "lon": -80.0}},
                "current": "Test City",
                "settings": {
                    "update_interval_minutes": 30,
                    "alert_radius_miles": 25,
                    "minimize_on_startup": False,
                },
                "api_settings": {"contact_info": "test@example.com"},
            }

            yield {
                "api_client": mock_api_client,
                "notification_service": mock_notification_service,
                "location_service": mock_location_service,
                "weather_service": mock_weather_service,
                "taskbar_icon": mock_taskbar_icon,
                "default_config": default_config,
            }

    def test_weather_app_creates_taskbar_icon(self, wx_app, mock_components):
        """Test that WeatherApp creates a TaskBarIcon."""
        app = None
        try:
            # Create the app
            app = WeatherApp(
                parent=None,
                weather_service=mock_components["weather_service"],
                location_service=mock_components["location_service"],
                notification_service=mock_components["notification_service"],
                api_client=mock_components["api_client"],
                config=mock_components["default_config"],
            )

            # Check that the app has a taskbar_icon attribute
            assert hasattr(app, "taskbar_icon")
            # Check that the taskbar_icon is an instance of wx.adv.TaskBarIcon
            assert isinstance(app.taskbar_icon, wx.adv.TaskBarIcon)
        finally:
            if app:
                app.Destroy()
                time.sleep(0.1)  # Allow time for destruction

    def test_weather_app_close_with_taskbar_icon(self, wx_app, mock_components):
        """Test that WeatherApp handles close events correctly with TaskBarIcon."""
        app = None
        try:
            # Create a mock TaskBarIcon
            mock_taskbar_icon = MagicMock()

            # Create the app
            app = WeatherApp(
                parent=None,
                weather_service=mock_components["weather_service"],
                location_service=mock_components["location_service"],
                notification_service=mock_components["notification_service"],
                api_client=mock_components["api_client"],
                config=mock_components["default_config"],
            )

            # Replace the taskbar_icon with our mock
            app.taskbar_icon = mock_taskbar_icon

            # Mock the Hide and Destroy methods
            original_hide = app.Hide
            original_destroy = app.Destroy
            app.Hide = MagicMock()
            app.Destroy = MagicMock()

            # Create a mock close event
            mock_event = MagicMock()

            # Call the OnClose method
            app.OnClose(mock_event)

            # Check that the event was vetoed (app should hide instead of close)
            mock_event.Veto.assert_called_once()

            # Check that the app was hidden
            app.Hide.assert_called_once()

            # Check that the app was not destroyed
            app.Destroy.assert_not_called()

            # Now test with force_close=True
            mock_event.reset_mock()
            app.Hide.reset_mock()
            app.OnClose(mock_event, force_close=True)

            # Check that the event was not vetoed
            assert not mock_event.Veto.called

            # Check that the taskbar_icon was destroyed
            mock_taskbar_icon.Destroy.assert_called_once()

            # Check that the app was destroyed
            app.Destroy.assert_called_once()

            # Restore original methods
            app.Hide = original_hide
            app.Destroy = original_destroy
        finally:
            if app:
                app.Destroy()
                time.sleep(0.1)  # Allow time for destruction

    def test_minimize_to_tray_button(self, wx_app, mock_components):
        """Test the 'Minimize to Tray' button."""
        app = None
        try:
            # Create the app
            app = WeatherApp(
                parent=None,
                weather_service=mock_components["weather_service"],
                location_service=mock_components["location_service"],
                notification_service=mock_components["notification_service"],
                api_client=mock_components["api_client"],
                config=mock_components["default_config"],
            )

            # Check that the minimize_to_tray_btn exists
            assert hasattr(app, "minimize_to_tray_btn")

            # Mock the Hide method
            original_hide = app.Hide
            app.Hide = MagicMock()

            # Create a mock event
            mock_event = MagicMock()

            # Call the OnMinimizeToTray method
            app.OnMinimizeToTray(mock_event)

            # Check that the app was hidden
            app.Hide.assert_called_once()

            # Restore original method
            app.Hide = original_hide
        finally:
            if app:
                app.Destroy()
                time.sleep(0.1)  # Allow time for destruction

    def test_start_minimized_setting(self, wx_app, mock_components):
        """Test the 'Start Minimized' setting."""
        app = None
        try:
            # Create a config with minimize_on_startup=True
            config = {
                "locations": {"Test City": {"lat": 35.0, "lon": -80.0}},
                "current": "Test City",
                "settings": {
                    "update_interval_minutes": 30,
                    "alert_radius_miles": 25,
                    "minimize_on_startup": True,
                },
                "api_settings": {"contact_info": "test@example.com"},
            }

            # Mock the Show and Hide methods
            with patch.object(wx.Frame, 'Show') as mock_show, \
                 patch.object(wx.Frame, 'Hide') as mock_hide, \
                 patch("accessiweather.gui.system_tray.TaskBarIcon"):

                # Create the app with the config
                app = WeatherApp(
                    parent=None,
                    weather_service=mock_components["weather_service"],
                    location_service=mock_components["location_service"],
                    notification_service=mock_components["notification_service"],
                    api_client=mock_components["api_client"],
                    config=config,
                )

                # Check that Hide was called (for minimize_on_startup=True)
                mock_hide.assert_called_once()

                # Create a new config with minimize_on_startup=False
                config = {
                    "locations": {"Test City": {"lat": 35.0, "lon": -80.0}},
                    "current": "Test City",
                    "settings": {
                        "update_interval_minutes": 30,
                        "alert_radius_miles": 25,
                        "minimize_on_startup": False,
                    },
                    "api_settings": {"contact_info": "test@example.com"},
                }

                # Reset the mocks
                mock_show.reset_mock()
                mock_hide.reset_mock()

                # Create a new app with the config
                app.Destroy()
                time.sleep(0.1)  # Allow time for destruction

                app = WeatherApp(
                    parent=None,
                    weather_service=mock_components["weather_service"],
                    location_service=mock_components["location_service"],
                    notification_service=mock_components["notification_service"],
                    api_client=mock_components["api_client"],
                    config=config,
                )

                # Check that Hide was not called (for minimize_on_startup=False)
                mock_hide.assert_not_called()
        finally:
            if app:
                app.Destroy()
                time.sleep(0.1)  # Allow time for destruction
