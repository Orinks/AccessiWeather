"""Tests for WeatherApp initialization and core functionality."""

import os
import tempfile
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.gui.weather_app import WeatherApp
from accessiweather.services.location_service import LocationService
from accessiweather.services.notification_service import NotificationService
from accessiweather.services.weather_service import WeatherService


@contextmanager
def mock_wx_components():
    """Context manager to mock all wx components needed for WeatherApp initialization."""
    with patch("accessiweather.gui.weather_app.UIManager"):
        with patch.object(WeatherApp, "CreateStatusBar"):
            with patch.object(WeatherApp, "SetStatusText"):
                with patch.object(WeatherApp, "SetStatusBar"):
                    with patch("wx.Timer"):
                        with patch.object(WeatherApp, "Bind"):
                            with patch.object(WeatherApp, "SetName"):
                                with patch.object(WeatherApp, "GetAccessible", return_value=None):
                                    with patch("accessiweather.gui.system_tray.TaskBarIcon"):
                                        with patch(
                                            "accessiweather.gui.debug_status_bar.DebugStatusBar"
                                        ):
                                            yield


@pytest.fixture
def mock_services():
    """Create mock services for WeatherApp."""
    weather_service = MagicMock(spec=WeatherService)
    location_service = MagicMock(spec=LocationService)
    notification_service = MagicMock(spec=NotificationService)

    # Configure the notification service mock to have a notifier attribute
    notification_service.notifier = MagicMock()

    # Set up location service defaults
    location_service.get_all_locations.return_value = [
        {"name": "Test City", "lat": 40.0, "lon": -75.0}
    ]
    location_service.get_current_location.return_value = "Test City"

    return {
        "weather_service": weather_service,
        "location_service": location_service,
        "notification_service": notification_service,
    }


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"settings": {"temperature_unit": "fahrenheit"}, "locations": []}')
        temp_path = f.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except OSError:
        pass


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return {
        "settings": {
            "temperature_unit": "fahrenheit",
            "update_interval_minutes": 10,
            "minimize_to_tray": False,
            "data_source": "auto",
            "alert_radius": 50,
            "precise_location_alerts": False,
        },
        "api_settings": {"api_contact": "test@example.com"},
        "api_keys": {},
        "locations": [{"name": "Test City", "lat": 40.0, "lon": -75.0}],
    }


@pytest.mark.gui
@pytest.mark.unit
class TestWeatherAppInitialization:
    """Test WeatherApp initialization."""

    @patch("wx.Frame.__init__", return_value=None)
    @patch(
        "accessiweather.gui.weather_app_modules.event_handlers.WeatherAppEventHandlers._create_menu_bar"
    )
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    def test_init_with_all_services(
        self,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        mock_config,
    ):
        """Test WeatherApp initialization with all services provided."""
        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.UIManager") as mock_ui_manager:
                with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                    # Configure the mock TaskBarIcon
                    mock_instance = MagicMock()
                    mock_instance.cleanup = MagicMock()
                    mock_taskbar.return_value = mock_instance

                    app = WeatherApp(
                        weather_service=mock_services["weather_service"],
                        location_service=mock_services["location_service"],
                        notification_service=mock_services["notification_service"],
                        config=mock_config,
                    )

            # Verify Frame initialization
            mock_frame_init.assert_called_once()

            # Verify services are assigned
            assert app.weather_service == mock_services["weather_service"]
            assert app.location_service == mock_services["location_service"]
            assert app.notification_service == mock_services["notification_service"]

            # Verify config is assigned
            assert app.config == mock_config

            # Verify UI manager is created
            mock_ui_manager.assert_called_once_with(
                app, mock_services["notification_service"].notifier
            )

            # Verify initialization methods are called
            mock_create_menu.assert_called_once()
            mock_update_dropdown.assert_called_once()
            mock_update_weather.assert_called_once()

    @patch("wx.Frame.__init__", return_value=None)
    @patch(
        "accessiweather.gui.weather_app_modules.event_handlers.WeatherAppEventHandlers._create_menu_bar"
    )
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    def test_init_with_debug_mode(
        self,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        mock_config,
    ):
        """Test WeatherApp initialization with debug mode enabled."""
        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                # Configure the mock TaskBarIcon
                mock_instance = MagicMock()
                mock_instance.cleanup = MagicMock()
                mock_taskbar.return_value = mock_instance

                app = WeatherApp(
                    weather_service=mock_services["weather_service"],
                    location_service=mock_services["location_service"],
                    notification_service=mock_services["notification_service"],
                    config=mock_config,
                    debug_mode=True,
                )

            # Verify debug mode is set
            assert app.debug_mode is True

    @patch("wx.Frame.__init__", return_value=None)
    @patch(
        "accessiweather.gui.weather_app_modules.event_handlers.WeatherAppEventHandlers._create_menu_bar"
    )
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    def test_init_with_custom_config_path(
        self,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        temp_config_file,
    ):
        """Test WeatherApp initialization with custom config path."""
        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                # Configure the mock TaskBarIcon
                mock_instance = MagicMock()
                mock_instance.cleanup = MagicMock()
                mock_taskbar.return_value = mock_instance

                app = WeatherApp(
                    weather_service=mock_services["weather_service"],
                    location_service=mock_services["location_service"],
                    notification_service=mock_services["notification_service"],
                    config_path=temp_config_file,
                )

            # Verify config path is set
            assert app._config_path == temp_config_file

    @patch("wx.Frame.__init__", return_value=None)
    @patch(
        "accessiweather.gui.weather_app_modules.event_handlers.WeatherAppEventHandlers._create_menu_bar"
    )
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    def test_init_sets_default_attributes(
        self,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        mock_config,
    ):
        """Test that WeatherApp initialization sets default attributes correctly."""
        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                # Configure the mock TaskBarIcon
                mock_instance = MagicMock()
                mock_instance.cleanup = MagicMock()
                mock_taskbar.return_value = mock_instance

                app = WeatherApp(
                    weather_service=mock_services["weather_service"],
                    location_service=mock_services["location_service"],
                    notification_service=mock_services["notification_service"],
                    config=mock_config,
                )

            # Verify default attributes
            assert app.updating is False
            assert app.last_update == 0.0
            assert app._force_close is True
            assert app.debug_mode is False

            # Verify testing callbacks are initialized
            assert app._testing_forecast_callback is None
            assert app._testing_forecast_error_callback is None
            assert app._testing_alerts_callback is None
            assert app._testing_alerts_error_callback is None
            assert app._testing_discussion_callback is None
            assert app._testing_discussion_error_callback is None

    @patch("wx.Frame.__init__", return_value=None)
    @patch(
        "accessiweather.gui.weather_app_modules.event_handlers.WeatherAppEventHandlers._create_menu_bar"
    )
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    def test_init_with_backward_compatibility_api_client(
        self,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        mock_config,
    ):
        """Test WeatherApp initialization with backward compatibility api_client parameter."""
        mock_api_client = MagicMock()

        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                # Configure the mock TaskBarIcon
                mock_instance = MagicMock()
                mock_instance.cleanup = MagicMock()
                mock_taskbar.return_value = mock_instance

                app = WeatherApp(
                    weather_service=mock_services["weather_service"],
                    location_service=mock_services["location_service"],
                    notification_service=mock_services["notification_service"],
                    api_client=mock_api_client,
                    config=mock_config,
                )

            # Verify the app initializes without error
            assert app.weather_service == mock_services["weather_service"]
