"""Tests for the simplified AccessiWeather Toga application.

This module provides comprehensive tests for the AccessiWeatherApp in the simplified
implementation, focusing on app initialization, UI components, event handlers,
background tasks, and configuration integration using appropriate mocking to avoid
actual GUI rendering.
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest

# Import simplified app components
from accessiweather import background_tasks, ui_builder
from accessiweather.app import AccessiWeatherApp
from accessiweather.models import AppConfig, AppSettings, Location


class TestAccessiWeatherAppInitialization:
    """Test AccessiWeatherApp initialization and startup - new Toga-specific tests."""

    @pytest.fixture
    def mock_toga_app(self):
        """Create a mock Toga app for testing."""
        import tempfile
        from pathlib import Path

        with (
            patch("toga.App.__init__") as mock_init,
            patch.object(
                AccessiWeatherApp, "formal_name", new_callable=PropertyMock
            ) as mock_formal_name,
            patch.object(AccessiWeatherApp, "app_name", new_callable=PropertyMock) as mock_app_name,
            patch.object(AccessiWeatherApp, "paths", new_callable=PropertyMock) as mock_paths,
        ):
            mock_init.return_value = None
            mock_formal_name.return_value = "AccessiWeather"
            mock_app_name.return_value = "accessiweather"

            # Create a temporary directory for config paths
            temp_dir = Path(tempfile.mkdtemp())
            mock_paths_obj = Mock()
            mock_paths_obj.config = temp_dir / "config"
            mock_paths_obj.config.mkdir(parents=True, exist_ok=True)
            mock_paths.return_value = mock_paths_obj

            app = AccessiWeatherApp("AccessiWeather", "org.example.accessiweather")

            # Set up the underlying attributes that Toga expects
            app._formal_name = "AccessiWeather"
            app._app_name = "accessiweather"
            app._paths = mock_paths_obj

            return app

    def test_app_initialization(self, mock_toga_app):
        """Test AccessiWeatherApp initialization."""
        app = mock_toga_app

        # Check initial state
        assert app.config_manager is None
        assert app.weather_client is None
        assert app.location_manager is None
        assert app.presenter is None

        # Check UI components are None initially
        assert app.location_selection is None
        assert app.current_conditions_display is None
        assert app.forecast_display is None
        assert app.alerts_table is None
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
            patch.object(ui_builder, "create_main_ui") as mock_create_ui,
            patch.object(ui_builder, "create_menu_system") as mock_create_menu,
            patch.object(app, "_load_initial_data") as mock_load_data,
        ):
            app.startup()

            # Verify startup sequence
            mock_init_components.assert_called_once()
            mock_create_ui.assert_called_once_with(app)
            mock_create_menu.assert_called_once_with(app)
            mock_load_data.assert_called_once()

    def test_startup_component_initialization_failure(self, mock_toga_app):
        """Test startup failure during component initialization."""
        app = mock_toga_app

        with (
            patch.object(app, "_initialize_components") as mock_init_components,
            patch.object(app, "_show_error_dialog") as mock_show_error,
            patch("toga.MainWindow"),
            patch.object(type(app), "main_window", new_callable=PropertyMock),
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
            patch("accessiweather.ui_builder.create_main_ui") as mock_create_ui,
            patch.object(app, "_show_error_dialog") as mock_show_error,
            patch("toga.MainWindow"),
            patch.object(type(app), "main_window", new_callable=PropertyMock),
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
            patch("accessiweather.app.ConfigManager") as mock_config_manager_class,
            patch("accessiweather.app.WeatherClient") as mock_weather_client_class,
            patch("accessiweather.app.LocationManager") as mock_location_manager_class,
            patch("accessiweather.app.WeatherPresenter") as mock_presenter_class,
            patch("accessiweather.app.AlertManager"),
            patch("accessiweather.app.AlertNotificationSystem"),
            patch("accessiweather.ui_builder.initialize_system_tray"),
        ):
            # Mock the instances
            mock_config_manager = Mock()
            mock_config = AppConfig(settings=AppSettings(), locations=[])
            mock_config_manager.load_config.return_value = mock_config
            mock_config_manager.get_config.return_value = mock_config
            mock_config_manager_class.return_value = mock_config_manager

            mock_weather_client = Mock()
            mock_weather_client_class.return_value = mock_weather_client

            mock_location_manager = Mock()
            mock_location_manager_class.return_value = mock_location_manager

            mock_presenter = Mock()
            mock_presenter_class.return_value = mock_presenter

            app._initialize_components()

            # Verify components were created
            assert app.config_manager == mock_config_manager
            assert app.weather_client == mock_weather_client
            assert app.location_manager == mock_location_manager
            assert app.presenter == mock_presenter

    @pytest.mark.asyncio
    async def test_on_running_success(self, mock_toga_app):
        """Test successful on_running method."""
        app = mock_toga_app

        with patch.object(
            background_tasks, "start_background_updates", new_callable=AsyncMock
        ) as mock_start_updates:
            await app.on_running()

            mock_start_updates.assert_called_once_with(app)

            if app.update_task:
                app.update_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await app.update_task

    @pytest.mark.asyncio
    async def test_on_running_failure(self, mock_toga_app):
        """Test on_running method with background task failure."""
        app = mock_toga_app

        with patch.object(
            background_tasks, "start_background_updates", new_callable=AsyncMock
        ) as mock_start_updates:
            mock_start_updates.side_effect = Exception("Background task failed")

            await app.on_running()

            mock_start_updates.assert_called_once_with(app)

            if app.update_task:
                app.update_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await app.update_task

    @pytest.mark.asyncio
    async def test_on_exit_cancels_background_task(self, mock_toga_app):
        """on_exit should cancel a running background update task."""
        app = mock_toga_app

        cancelled = False

        async def long_running():
            nonlocal cancelled
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                cancelled = True
                raise

        # Inject a long-running task
        app.update_task = asyncio.create_task(long_running())
        assert not app.update_task.done()

        # Trigger exit cleanup
        result = app.on_exit()
        assert result is True

        # Let the event loop process the cancellation
        with pytest.raises(asyncio.CancelledError):
            await app.update_task

        # Verify the task was cancelled
        assert cancelled or app.update_task.cancelled()


class TestAccessiWeatherAppUICreation:
    """Test AccessiWeatherApp UI creation methods - new Toga-specific tests."""

    @pytest.fixture
    def mock_app_with_components(self):
        """Create a mock app with initialized components."""
        with (
            patch("toga.App.__init__") as mock_init,
            patch.object(
                AccessiWeatherApp, "formal_name", new_callable=PropertyMock
            ) as mock_formal_name,
            patch.object(AccessiWeatherApp, "paths", new_callable=PropertyMock) as mock_paths,
        ):
            mock_init.return_value = None
            app = AccessiWeatherApp("AccessiWeather", "org.example.accessiweather")

            # Mock app properties
            mock_formal_name.return_value = "AccessiWeather"
            import tempfile
            from pathlib import Path

            temp_dir = Path(tempfile.mkdtemp())
            mock_paths_obj = Mock()
            mock_paths_obj.config = temp_dir / "config"
            mock_paths_obj.config.mkdir(parents=True, exist_ok=True)
            mock_paths.return_value = mock_paths_obj

            # Set up the underlying attributes that Toga expects
            app._formal_name = "AccessiWeather"
            app._paths = mock_paths_obj

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
            patch.object(ui_builder.toga, "Box") as mock_box,
            patch.object(ui_builder.toga, "Label"),
            patch.object(ui_builder.toga, "MainWindow") as mock_main_window,
            patch.object(ui_builder, "create_location_section") as mock_create_location,
            patch.object(ui_builder, "create_weather_display_section") as mock_create_weather,
            patch.object(ui_builder, "create_control_buttons_section") as mock_create_buttons,
            patch.object(
                type(app), "main_window", new_callable=PropertyMock
            ) as mock_main_window_prop,
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
            # Make the mocked main_window property return our mock window
            mock_main_window_prop.return_value = mock_window

            ui_builder.create_main_ui(app)

            # Verify UI structure creation
            mock_create_location.assert_called_once_with(app)
            mock_create_weather.assert_called_once_with(app)
            mock_create_buttons.assert_called_once_with(app)

            # Verify main window setup
            mock_main_window.assert_called_once_with(title=app.formal_name)
            # Verify that the window was shown
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
    from accessiweather.app import AccessiWeatherApp

    # Basic instantiation test with mock
    with patch("toga.App.__init__") as mock_init:
        mock_init.return_value = None
        app = AccessiWeatherApp("AccessiWeather", "org.example.accessiweather")
        assert app is not None


def test_accessiweather_app_basic_functionality():
    """Test basic AccessiWeatherApp functionality without GUI rendering."""
    from accessiweather.app import AccessiWeatherApp

    with patch("toga.App.__init__") as mock_init:
        mock_init.return_value = None
        app = AccessiWeatherApp("AccessiWeather", "org.example.accessiweather")

        # Test initial state
        assert app.config_manager is None
        assert app.weather_client is None
        assert app.location_manager is None
        assert app.presenter is None
        assert app.is_updating is False

        # Test utility methods
        app.config_manager = Mock()
        app.config_manager.get_location_names.return_value = ["Test City"]

        choices = app._get_location_choices()
        assert choices == ["Test City"]


class TestAccessiWeatherAppAsyncOperations:
    """Test async operations and Toga testing infrastructure."""

    @pytest.mark.asyncio
    async def test_async_weather_refresh(
        self, mock_weather_client, mock_weather_data, mock_location
    ):
        """Test async weather data refresh."""
        # Test async weather client
        weather_data = await mock_weather_client.get_weather_data(mock_location)
        assert weather_data == mock_weather_data
        mock_weather_client.get_weather_data.assert_called_once_with(mock_location)

    @pytest.mark.asyncio
    async def test_async_error_handling(self, failing_weather_client, mock_location):
        """Test async error handling."""
        with pytest.raises(Exception, match="Mock weather client failure"):
            await failing_weather_client.get_weather_data(mock_location)

    def test_toga_dummy_backend_setup(self, mock_widgets):
        """Test that toga-dummy backend is properly configured."""
        # Create mock widgets to verify testing infrastructure
        button = mock_widgets.create_widget("Button", text="Refresh")
        selection = mock_widgets.create_widget("Selection", items=["City A", "City B"])
        text_input = mock_widgets.create_widget("MultilineTextInput", readonly=True)

        assert button.widget_type == "Button"
        assert button.text == "Refresh"
        assert selection.widget_type == "Selection"
        assert selection.items == ["City A", "City B"]
        assert text_input.widget_type == "MultilineTextInput"
        assert text_input.readonly is True

    @pytest.mark.asyncio
    async def test_background_task_simulation(self, async_helper):
        """Test background task simulation."""
        task_completed = False

        async def background_task():
            nonlocal task_completed
            await asyncio.sleep(0.1)
            task_completed = True
            return "completed"

        # Test async helper
        result = await async_helper.run_with_timeout(background_task())
        assert result == "completed"
        assert task_completed is True

    def test_weather_data_factory(self, weather_factory, mock_location, mock_weather_data):
        """Test weather data factory for creating test data."""
        # Test factory creates proper data structures
        assert mock_location.name == "Test City, ST"
        assert mock_location.latitude == 40.0
        assert mock_location.longitude == -75.0

        assert mock_weather_data.location is not None
        assert mock_weather_data.current is not None
        assert mock_weather_data.forecast is not None

        # Test factory methods
        custom_location = weather_factory.create_location("Custom City", 41.0, -76.0)
        assert custom_location.name == "Custom City"
        assert custom_location.latitude == 41.0
