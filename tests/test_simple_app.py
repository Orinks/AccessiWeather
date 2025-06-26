"""Tests for the simplified AccessiWeather Toga application.

This module provides comprehensive tests for the AccessiWeatherApp in the simplified
implementation, focusing on app initialization, UI components, event handlers,
background tasks, and configuration integration using appropriate mocking to avoid
actual GUI rendering.
"""

from unittest.mock import Mock, patch

import pytest

# Import simplified app components
from accessiweather.simple.app import AccessiWeatherApp
from accessiweather.simple.models import AppConfig, AppSettings, Location


class TestAccessiWeatherAppInitialization:
    """Test AccessiWeatherApp initialization and startup - new Toga-specific tests."""

    @pytest.fixture
    def mock_toga_app(self):
        """Create a mock Toga app for testing."""
        with patch("toga.App.__init__") as mock_init:
            mock_init.return_value = None
            app = AccessiWeatherApp("AccessiWeather", "org.example.accessiweather")

            # Mock the app properties that Toga would normally provide
            app.formal_name = "AccessiWeather"
            app.app_name = "accessiweather"
            app.paths = Mock()
            app.paths.config = Mock()

            return app

    def test_app_initialization(self, mock_toga_app):
        """Test AccessiWeatherApp initialization."""
        app = mock_toga_app

        # Check initial state
        assert app.config_manager is None
        assert app.weather_client is None
        assert app.location_manager is None
        assert app.formatter is None

        # Check UI components are None initially
        assert app.location_selection is None
        assert app.current_conditions_display is None
        assert app.forecast_display is None
        assert app.alerts_display is None
        assert app.refresh_button is None
        assert app.status_label is None

        # Check background task state
        assert app.update_task is None
        assert app.is_updating is False

    def test_startup_success(self, mock_toga_app):
        """Test successful app startup sequence."""
        app = mock_toga_app

        with (
            patch.object(app, "_initialize_components") as mock_init_components,
            patch.object(app, "_create_main_ui") as mock_create_ui,
            patch.object(app, "_create_menu_system") as mock_create_menu,
            patch.object(app, "_load_initial_data") as mock_load_data,
        ):
            app.startup()

            # Verify startup sequence
            mock_init_components.assert_called_once()
            mock_create_ui.assert_called_once()
            mock_create_menu.assert_called_once()
            mock_load_data.assert_called_once()

    def test_startup_component_initialization_failure(self, mock_toga_app):
        """Test startup failure during component initialization."""
        app = mock_toga_app

        with (
            patch.object(app, "_initialize_components") as mock_init_components,
            patch.object(app, "_show_error_dialog") as mock_show_error,
        ):
            mock_init_components.side_effect = Exception("Component init failed")

            app.startup()

            mock_show_error.assert_called_once_with(
                "Startup Error", "Failed to start application: Component init failed"
            )

    def test_startup_ui_creation_failure(self, mock_toga_app):
        """Test startup failure during UI creation."""
        app = mock_toga_app

        with (
            patch.object(app, "_initialize_components"),
            patch.object(app, "_create_main_ui") as mock_create_ui,
            patch.object(app, "_show_error_dialog") as mock_show_error,
        ):
            mock_create_ui.side_effect = Exception("UI creation failed")

            app.startup()

            mock_show_error.assert_called_once_with(
                "Startup Error", "Failed to start application: UI creation failed"
            )

    def test_initialize_components_success(self, mock_toga_app):
        """Test successful component initialization."""
        app = mock_toga_app

        with (
            patch("accessiweather.simple.app.ConfigManager") as mock_config_manager_class,
            patch("accessiweather.simple.app.WeatherClient") as mock_weather_client_class,
            patch("accessiweather.simple.app.LocationManager") as mock_location_manager_class,
            patch("accessiweather.simple.app.WxStyleWeatherFormatter") as mock_formatter_class,
        ):
            # Mock the instances
            mock_config_manager = Mock()
            mock_config_manager.get_config.return_value = AppConfig(settings=AppSettings())
            mock_config_manager_class.return_value = mock_config_manager

            mock_weather_client = Mock()
            mock_weather_client_class.return_value = mock_weather_client

            mock_location_manager = Mock()
            mock_location_manager_class.return_value = mock_location_manager

            mock_formatter = Mock()
            mock_formatter_class.return_value = mock_formatter

            app._initialize_components()

            # Verify components were created
            assert app.config_manager == mock_config_manager
            assert app.weather_client == mock_weather_client
            assert app.location_manager == mock_location_manager
            assert app.formatter == mock_formatter

            # Verify correct initialization parameters
            mock_config_manager_class.assert_called_once_with(app)
            mock_weather_client_class.assert_called_once_with(user_agent="AccessiWeather/2.0")
            mock_location_manager_class.assert_called_once()
            mock_formatter_class.assert_called_once_with(mock_config_manager.get_config().settings)

    @pytest.mark.asyncio
    async def test_on_running_success(self, mock_toga_app):
        """Test successful on_running method."""
        app = mock_toga_app

        with patch.object(app, "_start_background_updates") as mock_start_updates:
            mock_start_updates.return_value = None  # Async method

            await app.on_running()

            mock_start_updates.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_running_failure(self, mock_toga_app):
        """Test on_running method with background task failure."""
        app = mock_toga_app

        with patch.object(app, "_start_background_updates") as mock_start_updates:
            mock_start_updates.side_effect = Exception("Background task failed")

            # Should not raise exception, just log error
            await app.on_running()

            mock_start_updates.assert_called_once()


class TestAccessiWeatherAppUICreation:
    """Test AccessiWeatherApp UI creation methods - new Toga-specific tests."""

    @pytest.fixture
    def mock_app_with_components(self):
        """Create a mock app with initialized components."""
        with patch("toga.App.__init__") as mock_init:
            mock_init.return_value = None
            app = AccessiWeatherApp("AccessiWeather", "org.example.accessiweather")

            # Mock app properties
            app.formal_name = "AccessiWeather"
            app.paths = Mock()

            # Mock components
            app.config_manager = Mock()
            app.config_manager.get_location_names.return_value = [
                "Philadelphia, PA",
                "New York, NY",
            ]
            app.config_manager.get_current_location.return_value = Location(
                "Philadelphia, PA", 39.9526, -75.1652
            )

            return app

    def test_create_main_ui_structure(self, mock_app_with_components):
        """Test main UI creation structure."""
        app = mock_app_with_components

        with (
            patch("toga.Box") as mock_box,
            patch("toga.Label") as mock_label,
            patch("toga.MainWindow") as mock_main_window,
            patch.object(app, "_create_location_section") as mock_create_location,
            patch.object(app, "_create_weather_display_section") as mock_create_weather,
            patch.object(app, "_create_control_buttons_section") as mock_create_buttons,
        ):
            # Mock return values
            mock_location_box = Mock()
            mock_weather_box = Mock()
            mock_buttons_box = Mock()

            mock_create_location.return_value = mock_location_box
            mock_create_weather.return_value = mock_weather_box
            mock_create_buttons.return_value = mock_buttons_box

            mock_main_box = Mock()
            mock_box.return_value = mock_main_box

            mock_window = Mock()
            mock_main_window.return_value = mock_window

            app._create_main_ui()

            # Verify UI structure creation
            mock_create_location.assert_called_once()
            mock_create_weather.assert_called_once()
            mock_create_buttons.assert_called_once()

            # Verify main window setup
            mock_main_window.assert_called_once_with(title=app.formal_name)
            assert app.main_window == mock_window
            mock_window.show.assert_called_once()

    def test_get_location_choices_with_locations(self, mock_app_with_components):
        """Test getting location choices when locations exist."""
        app = mock_app_with_components

        choices = app._get_location_choices()

        assert choices == ["Philadelphia, PA", "New York, NY"]
        app.config_manager.get_location_names.assert_called_once()

    def test_get_location_choices_no_locations(self, mock_app_with_components):
        """Test getting location choices when no locations exist."""
        app = mock_app_with_components
        app.config_manager.get_location_names.return_value = []

        choices = app._get_location_choices()

        assert choices == ["No locations available"]

    def test_get_location_choices_error(self, mock_app_with_components):
        """Test getting location choices when error occurs."""
        app = mock_app_with_components
        app.config_manager.get_location_names.side_effect = Exception("Config error")

        choices = app._get_location_choices()

        assert choices == ["Error loading locations"]

    def test_update_status(self, mock_app_with_components):
        """Test status label update."""
        app = mock_app_with_components
        app.status_label = Mock()

        app._update_status("Test status message")

        assert app.status_label.text == "Test status message"


# Smoke test functions that can be run with briefcase dev --test
def test_accessiweather_app_can_be_imported():
    """Test that AccessiWeatherApp can be imported successfully."""
    from accessiweather.simple.app import AccessiWeatherApp

    # Basic instantiation test with mock
    with patch("toga.App.__init__") as mock_init:
        mock_init.return_value = None
        app = AccessiWeatherApp("AccessiWeather", "org.example.accessiweather")
        assert app is not None


def test_accessiweather_app_basic_functionality():
    """Test basic AccessiWeatherApp functionality without GUI rendering."""
    from accessiweather.simple.app import AccessiWeatherApp

    with patch("toga.App.__init__") as mock_init:
        mock_init.return_value = None
        app = AccessiWeatherApp("AccessiWeather", "org.example.accessiweather")

        # Test initial state
        assert app.config_manager is None
        assert app.weather_client is None
        assert app.location_manager is None
        assert app.formatter is None
        assert app.is_updating is False

        # Test utility methods
        app.config_manager = Mock()
        app.config_manager.get_location_names.return_value = ["Test City"]

        choices = app._get_location_choices()
        assert choices == ["Test City"]
