"""Tests for UV Index menu integration and handler."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

os.environ["TOGA_BACKEND"] = "toga_dummy"

import toga

from accessiweather.dialogs.uv_index_dialog import UVIndexDialog
from accessiweather.handlers.weather_handlers import on_view_uv_index
from accessiweather.models import (
    AppConfig,
    AppSettings,
    EnvironmentalConditions,
    HourlyUVIndex,
    Location,
)


@pytest.fixture
def mock_location():
    """Create a mock location."""
    return Location(name="Test City", latitude=40.7128, longitude=-74.006)


@pytest.fixture
def mock_environmental_data():
    """Environmental data with UV index info."""
    hourly = HourlyUVIndex(
        timestamp=datetime.now(timezone.utc),
        uv_index=6.5,
        category="High",
    )
    return EnvironmentalConditions(
        uv_index=6.5,
        uv_category="High",
        hourly_uv_index=[hourly],
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_app_settings():
    """Application settings."""
    return AppSettings(time_format_12hour=True)


@pytest.fixture
def mock_app_config(mock_app_settings):
    """Application config with settings."""
    config = MagicMock(spec=AppConfig)
    config.settings = mock_app_settings
    return config


@pytest.fixture
def mock_widget():
    """Create a mock widget."""
    return Mock()


@pytest.fixture
def mock_app(mock_location, mock_environmental_data, mock_app_config):
    """Create a mock AccessiWeatherApp with full config."""
    app = MagicMock()
    app.config_manager = MagicMock()
    app.config_manager.get_current_location.return_value = mock_location
    app.config_manager.get_config.return_value = mock_app_config
    app.main_window = MagicMock()
    app.main_window.dialog = AsyncMock()

    app.current_weather_data = MagicMock()
    app.current_weather_data.environmental = mock_environmental_data

    return app


@pytest.mark.unit
class TestUVIndexMenuCommand:
    """Tests for UV Index menu command existence and configuration."""

    def test_uv_index_command_exists_in_view_menu(self):
        """Test that UV Index command is created and added to View menu group."""
        toga.App.app = None
        mock_app = MagicMock()
        mock_app.commands = MagicMock()
        mock_app.commands.add = MagicMock()

        with patch("accessiweather.ui_builder.toga.Group.VIEW", toga.Group.VIEW):
            from accessiweather import ui_builder

            ui_builder.create_menu_system(mock_app)

        mock_app.commands.add.assert_called_once()
        added_commands = mock_app.commands.add.call_args[0]

        uv_index_cmd = None
        for cmd in added_commands:
            if hasattr(cmd, "text") and "UV Index" in cmd.text:
                uv_index_cmd = cmd
                break

        assert uv_index_cmd is not None, "UV Index command should exist"
        assert uv_index_cmd.group == toga.Group.VIEW

    def test_uv_index_command_has_correct_tooltip(self):
        """Test that UV Index command has appropriate tooltip."""
        toga.App.app = None
        mock_app = MagicMock()
        mock_app.commands = MagicMock()
        mock_app.commands.add = MagicMock()

        from accessiweather import ui_builder

        ui_builder.create_menu_system(mock_app)

        added_commands = mock_app.commands.add.call_args[0]

        uv_index_cmd = None
        for cmd in added_commands:
            if hasattr(cmd, "text") and "UV Index" in cmd.text:
                uv_index_cmd = cmd
                break

        assert uv_index_cmd is not None
        assert "uv" in uv_index_cmd.tooltip.lower()


@pytest.mark.unit
class TestOnViewUVIndexHandler:
    """Tests for on_view_uv_index handler."""

    @pytest.mark.asyncio
    async def test_handler_shows_dialog_with_correct_location(
        self, mock_app, mock_widget, mock_location
    ):
        """Test handler shows dialog with the current location name."""
        dialog_instance = MagicMock()
        dialog_instance.show_and_focus = AsyncMock()

        with patch(
            "accessiweather.handlers.weather_handlers.UVIndexDialog",
            return_value=dialog_instance,
        ) as dialog_cls:
            await on_view_uv_index(mock_app, mock_widget)

        dialog_cls.assert_called_once()
        call_args = dialog_cls.call_args[0]
        assert call_args[1] == "Test City"
        dialog_instance.show_and_focus.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handler_shows_info_when_no_location_selected(self, mock_app, mock_widget):
        """Test handler shows info dialog when no location is selected."""
        mock_app.config_manager.get_current_location.return_value = None

        captured_dialogs = []

        async def capture_dialog(dialog):
            captured_dialogs.append(dialog)

        mock_app.main_window.dialog = capture_dialog

        await on_view_uv_index(mock_app, mock_widget)

        assert len(captured_dialogs) == 1
        dialog = captured_dialogs[0]
        assert isinstance(dialog, toga.InfoDialog)

    @pytest.mark.asyncio
    async def test_handler_shows_info_when_no_weather_data(
        self, mock_app, mock_widget, mock_location
    ):
        """Test handler shows info dialog when no weather data is available."""
        mock_app.current_weather_data = None

        captured_dialogs = []

        async def capture_dialog(dialog):
            captured_dialogs.append(dialog)

        mock_app.main_window.dialog = capture_dialog

        await on_view_uv_index(mock_app, mock_widget)

        assert len(captured_dialogs) == 1
        assert isinstance(captured_dialogs[0], toga.InfoDialog)

    @pytest.mark.asyncio
    async def test_handler_shows_info_when_no_environmental_data(
        self, mock_app, mock_widget, mock_location
    ):
        """Test handler shows info dialog when environmental data is missing."""
        mock_app.current_weather_data = MagicMock()
        mock_app.current_weather_data.environmental = None

        captured_dialogs = []

        async def capture_dialog(dialog):
            captured_dialogs.append(dialog)

        mock_app.main_window.dialog = capture_dialog

        await on_view_uv_index(mock_app, mock_widget)

        assert len(captured_dialogs) == 1
        assert isinstance(captured_dialogs[0], toga.InfoDialog)

    @pytest.mark.asyncio
    async def test_handler_shows_info_when_environmental_has_no_data(
        self, mock_app, mock_widget, mock_location
    ):
        """Test handler shows info dialog when environmental.has_data() is False."""
        empty_environmental = EnvironmentalConditions()
        mock_app.current_weather_data.environmental = empty_environmental

        captured_dialogs = []

        async def capture_dialog(dialog):
            captured_dialogs.append(dialog)

        mock_app.main_window.dialog = capture_dialog

        await on_view_uv_index(mock_app, mock_widget)

        assert len(captured_dialogs) == 1
        assert isinstance(captured_dialogs[0], toga.InfoDialog)

    @pytest.mark.asyncio
    async def test_handler_passes_settings_to_dialog(
        self, mock_app, mock_widget, mock_app_settings
    ):
        """Test handler passes app settings to the dialog."""
        dialog_instance = MagicMock()
        dialog_instance.show_and_focus = AsyncMock()

        with patch(
            "accessiweather.handlers.weather_handlers.UVIndexDialog",
            return_value=dialog_instance,
        ) as dialog_cls:
            await on_view_uv_index(mock_app, mock_widget)

        call_args = dialog_cls.call_args[0]
        assert call_args[3] == mock_app_settings

    @pytest.mark.asyncio
    async def test_handler_updates_status_on_success(self, mock_app, mock_widget):
        """Test handler updates status when dialog opens successfully."""
        dialog_instance = MagicMock()
        dialog_instance.show_and_focus = AsyncMock()

        with (
            patch(
                "accessiweather.handlers.weather_handlers.UVIndexDialog",
                return_value=dialog_instance,
            ),
            patch("accessiweather.handlers.weather_handlers.app_helpers") as mock_helpers,
        ):
            await on_view_uv_index(mock_app, mock_widget)

        mock_helpers.update_status.assert_called_once()
        assert "UV index dialog opened" in mock_helpers.update_status.call_args[0][1]

    @pytest.mark.asyncio
    async def test_handler_shows_error_on_exception(self, mock_app, mock_widget):
        """Test handler shows error dialog when exception occurs."""
        captured_dialogs = []

        async def capture_dialog(dialog):
            captured_dialogs.append(dialog)

        mock_app.main_window.dialog = capture_dialog

        with patch(
            "accessiweather.handlers.weather_handlers.UVIndexDialog",
            side_effect=Exception("Dialog error"),
        ):
            await on_view_uv_index(mock_app, mock_widget)

        assert len(captured_dialogs) == 1
        assert isinstance(captured_dialogs[0], toga.InfoDialog)


@pytest.mark.unit
class TestUVIndexDialogLocationProperty:
    """Property tests: Location name appears in dialog title/header."""

    @pytest.fixture
    def mock_toga_app(self):
        """Create a real Toga app instance with dummy backend."""
        toga.App.app = None
        app = toga.App("Test AccessiWeather", "org.beeware.test")
        app.config = MagicMock()
        app.on_exit = lambda: True
        yield app
        toga.App.app = None

    @pytest.fixture
    def valid_environmental_data(self):
        """Environmental data with UV index info."""
        hourly = HourlyUVIndex(
            timestamp=datetime.now(timezone.utc),
            uv_index=6.5,
            category="High",
        )
        return EnvironmentalConditions(
            uv_index=6.5,
            uv_category="High",
            hourly_uv_index=[hourly],
        )

    def test_dialog_title_contains_location_name_simple(
        self, mock_toga_app, valid_environmental_data
    ):
        """Test dialog title contains a simple location name."""
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="New York",
            environmental=valid_environmental_data,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert "New York" in dialog.window.title

    def test_dialog_title_contains_location_name_with_spaces(
        self, mock_toga_app, valid_environmental_data
    ):
        """Test dialog title contains location name with spaces."""
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Los Angeles",
            environmental=valid_environmental_data,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert "Los Angeles" in dialog.window.title

    def test_dialog_title_contains_location_name_with_special_chars(
        self, mock_toga_app, valid_environmental_data
    ):
        """Test dialog title contains location name with special characters."""
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="St. Louis, MO",
            environmental=valid_environmental_data,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert "St. Louis, MO" in dialog.window.title

    def test_dialog_title_contains_location_name_unicode(
        self, mock_toga_app, valid_environmental_data
    ):
        """Test dialog title contains location name with unicode characters."""
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="São Paulo",
            environmental=valid_environmental_data,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert "São Paulo" in dialog.window.title

    def test_dialog_title_contains_location_name_long(
        self, mock_toga_app, valid_environmental_data
    ):
        """Test dialog title contains a long location name."""
        long_name = "Springfield, Massachusetts, United States"
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name=long_name,
            environmental=valid_environmental_data,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert long_name in dialog.window.title

    def test_dialog_title_format_is_consistent(self, mock_toga_app, valid_environmental_data):
        """Test dialog title follows expected format: 'UV Index - <location>'."""
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Chicago",
            environmental=valid_environmental_data,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert dialog.window.title == "UV Index - Chicago"

    def test_dialog_title_contains_location_when_no_uv_data(self, mock_toga_app):
        """Test dialog title contains location even when no UV data."""
        empty_environmental = EnvironmentalConditions()
        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Empty City",
            environmental=empty_environmental,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert "Empty City" in dialog.window.title


@pytest.mark.unit
class TestUVIndexDialogDataValidation:
    """Integration tests for UV Index dialog data validation."""

    @pytest.fixture
    def mock_toga_app(self):
        """Create a real Toga app instance with dummy backend."""
        toga.App.app = None
        app = toga.App("Test AccessiWeather", "org.beeware.test")
        app.config = MagicMock()
        app.on_exit = lambda: True
        yield app
        toga.App.app = None

    def test_dialog_displays_current_uv_index(self, mock_toga_app):
        """Test dialog displays current UV index value."""
        environmental = EnvironmentalConditions(
            uv_index=7.5,
            uv_category="High",
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
        )

        summary_box = dialog._build_summary_section()
        assert summary_box is not None

    def test_dialog_displays_uv_category(self, mock_toga_app):
        """Test dialog displays UV category."""
        environmental = EnvironmentalConditions(
            uv_index=6.5,
            uv_category="High",
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
        )

        summary_box = dialog._build_summary_section()
        assert summary_box is not None

    def test_dialog_handles_extreme_uv_index(self, mock_toga_app):
        """Test dialog handles extreme UV index values."""
        hourly = HourlyUVIndex(
            timestamp=datetime.now(timezone.utc),
            uv_index=12.0,
            category="Extreme",
        )
        environmental = EnvironmentalConditions(
            uv_index=12.0,
            uv_category="Extreme",
            hourly_uv_index=[hourly],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
        )

        dialog._build_ui()
        assert dialog.window is not None

    def test_dialog_handles_low_uv_index(self, mock_toga_app):
        """Test dialog handles low UV index values."""
        hourly = HourlyUVIndex(
            timestamp=datetime.now(timezone.utc),
            uv_index=1.5,
            category="Low",
        )
        environmental = EnvironmentalConditions(
            uv_index=1.5,
            uv_category="Low",
            hourly_uv_index=[hourly],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
        )

        dialog._build_ui()
        assert dialog.window is not None

    def test_dialog_handles_multiple_hourly_values(self, mock_toga_app):
        """Test dialog handles multiple hourly UV values."""
        hourly_data = [
            HourlyUVIndex(
                timestamp=datetime.now(timezone.utc),
                uv_index=5.0,
                category="Moderate",
            ),
            HourlyUVIndex(
                timestamp=datetime.now(timezone.utc),
                uv_index=7.5,
                category="High",
            ),
            HourlyUVIndex(
                timestamp=datetime.now(timezone.utc),
                uv_index=3.0,
                category="Moderate",
            ),
        ]
        environmental = EnvironmentalConditions(
            uv_index=5.0,
            uv_category="Moderate",
            hourly_uv_index=hourly_data,
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
        )

        hourly_box = dialog._build_hourly_section()
        assert hourly_box is not None

    def test_dialog_handles_missing_hourly_data(self, mock_toga_app):
        """Test dialog handles missing hourly UV data gracefully."""
        environmental = EnvironmentalConditions(
            uv_index=6.5,
            uv_category="High",
            hourly_uv_index=None,
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
        )

        hourly_box = dialog._build_hourly_section()
        assert hourly_box is not None

    def test_dialog_handles_empty_hourly_list(self, mock_toga_app):
        """Test dialog handles empty hourly UV list."""
        environmental = EnvironmentalConditions(
            uv_index=6.5,
            uv_category="High",
            hourly_uv_index=[],
        )

        dialog = UVIndexDialog(
            app=mock_toga_app,
            location_name="Test City",
            environmental=environmental,
        )

        hourly_box = dialog._build_hourly_section()
        assert hourly_box is not None


@pytest.mark.unit
class TestUVIndexWorkflowIntegration:
    """End-to-end workflow integration tests."""

    @pytest.fixture
    def mock_toga_app(self):
        """Create a real Toga app instance with dummy backend."""
        toga.App.app = None
        app = toga.App("Test AccessiWeather", "org.beeware.test")
        app.config = MagicMock()
        app.on_exit = lambda: True
        yield app
        toga.App.app = None

    @pytest.mark.asyncio
    async def test_complete_workflow_from_handler_to_dialog(
        self, mock_location, mock_environmental_data, mock_app_settings
    ):
        """Test complete workflow from handler invocation to dialog display."""
        # Setup mock app
        app = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.get_current_location.return_value = mock_location

        config = MagicMock()
        config.settings = mock_app_settings
        app.config_manager.get_config.return_value = config

        app.main_window = MagicMock()
        app.main_window.dialog = AsyncMock()

        app.current_weather_data = MagicMock()
        app.current_weather_data.environmental = mock_environmental_data

        # Execute handler
        dialog_instance = MagicMock()
        dialog_instance.show_and_focus = AsyncMock()

        with (
            patch(
                "accessiweather.handlers.weather_handlers.UVIndexDialog",
                return_value=dialog_instance,
            ) as dialog_cls,
            patch("accessiweather.handlers.weather_handlers.app_helpers") as mock_helpers,
        ):
            await on_view_uv_index(app, Mock())

        # Verify dialog was created with correct parameters
        dialog_cls.assert_called_once()
        call_args = dialog_cls.call_args[0]
        assert call_args[0] == app
        assert call_args[1] == "Test City"
        assert call_args[2] == mock_environmental_data
        assert call_args[3] == mock_app_settings

        # Verify dialog was shown
        dialog_instance.show_and_focus.assert_awaited_once()

        # Verify status was updated
        mock_helpers.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_handles_missing_location_gracefully(self):
        """Test workflow handles missing location gracefully."""
        app = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.get_current_location.return_value = None
        app.main_window = MagicMock()

        captured_dialogs = []

        async def capture_dialog(dialog):
            captured_dialogs.append(dialog)

        app.main_window.dialog = capture_dialog

        await on_view_uv_index(app, Mock())

        assert len(captured_dialogs) == 1
        assert isinstance(captured_dialogs[0], toga.InfoDialog)

    @pytest.mark.asyncio
    async def test_workflow_handles_missing_environmental_data_gracefully(self, mock_location):
        """Test workflow handles missing environmental data gracefully."""
        app = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.get_current_location.return_value = mock_location
        app.main_window = MagicMock()
        app.current_weather_data = None

        captured_dialogs = []

        async def capture_dialog(dialog):
            captured_dialogs.append(dialog)

        app.main_window.dialog = capture_dialog

        await on_view_uv_index(app, Mock())

        assert len(captured_dialogs) == 1
        assert isinstance(captured_dialogs[0], toga.InfoDialog)
