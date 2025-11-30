"""Tests for Air Quality menu integration and handler."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

os.environ["TOGA_BACKEND"] = "toga_dummy"

import toga

from accessiweather.dialogs.air_quality_dialog import AirQualityDialog
from accessiweather.handlers.weather_handlers import on_view_air_quality
from accessiweather.models import (
    AppConfig,
    AppSettings,
    EnvironmentalConditions,
    HourlyAirQuality,
    Location,
)


@pytest.fixture
def mock_location():
    """Create a mock location."""
    return Location(name="Test City", latitude=40.7128, longitude=-74.006)


@pytest.fixture
def mock_environmental_data():
    """Environmental data with air quality info."""
    hourly = HourlyAirQuality(
        timestamp=datetime.now(timezone.utc),
        aqi=45,
        category="Good",
        pm2_5=12.5,
        pm10=25.0,
    )
    return EnvironmentalConditions(
        air_quality_index=45.0,
        air_quality_category="Good",
        air_quality_pollutant="PM2_5",
        hourly_air_quality=[hourly],
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
class TestAirQualityMenuCommand:
    """Tests for Air Quality menu command existence and configuration."""

    def test_air_quality_command_exists_in_view_menu(self):
        """Test that Air Quality command is created and added to View menu group."""
        toga.App.app = None
        mock_app = MagicMock()
        mock_app.commands = MagicMock()
        mock_app.commands.add = MagicMock()

        with patch("accessiweather.ui_builder.toga.Group.VIEW", toga.Group.VIEW):
            from accessiweather import ui_builder

            ui_builder.create_menu_system(mock_app)

        mock_app.commands.add.assert_called_once()
        added_commands = mock_app.commands.add.call_args[0]

        air_quality_cmd = None
        for cmd in added_commands:
            if hasattr(cmd, "text") and "Air Quality" in cmd.text:
                air_quality_cmd = cmd
                break

        assert air_quality_cmd is not None, "Air Quality command should exist"
        assert air_quality_cmd.group == toga.Group.VIEW

    def test_air_quality_command_has_correct_tooltip(self):
        """Test that Air Quality command has appropriate tooltip."""
        toga.App.app = None
        mock_app = MagicMock()
        mock_app.commands = MagicMock()
        mock_app.commands.add = MagicMock()

        from accessiweather import ui_builder

        ui_builder.create_menu_system(mock_app)

        added_commands = mock_app.commands.add.call_args[0]

        air_quality_cmd = None
        for cmd in added_commands:
            if hasattr(cmd, "text") and "Air Quality" in cmd.text:
                air_quality_cmd = cmd
                break

        assert air_quality_cmd is not None
        assert "air quality" in air_quality_cmd.tooltip.lower()


@pytest.mark.unit
class TestOnViewAirQualityHandler:
    """Tests for on_view_air_quality handler."""

    @pytest.mark.asyncio
    async def test_handler_shows_dialog_with_correct_location(
        self, mock_app, mock_widget, mock_location
    ):
        """Test handler shows dialog with the current location name."""
        dialog_instance = MagicMock()
        dialog_instance.show_and_focus = AsyncMock()

        with patch(
            "accessiweather.handlers.weather_handlers.AirQualityDialog",
            return_value=dialog_instance,
        ) as dialog_cls:
            await on_view_air_quality(mock_app, mock_widget)

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

        await on_view_air_quality(mock_app, mock_widget)

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

        await on_view_air_quality(mock_app, mock_widget)

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

        await on_view_air_quality(mock_app, mock_widget)

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

        await on_view_air_quality(mock_app, mock_widget)

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
            "accessiweather.handlers.weather_handlers.AirQualityDialog",
            return_value=dialog_instance,
        ) as dialog_cls:
            await on_view_air_quality(mock_app, mock_widget)

        call_args = dialog_cls.call_args[0]
        assert call_args[3] == mock_app_settings

    @pytest.mark.asyncio
    async def test_handler_updates_status_on_success(self, mock_app, mock_widget):
        """Test handler updates status when dialog opens successfully."""
        dialog_instance = MagicMock()
        dialog_instance.show_and_focus = AsyncMock()

        with (
            patch(
                "accessiweather.handlers.weather_handlers.AirQualityDialog",
                return_value=dialog_instance,
            ),
            patch("accessiweather.handlers.weather_handlers.app_helpers") as mock_helpers,
        ):
            await on_view_air_quality(mock_app, mock_widget)

        mock_helpers.update_status.assert_called_once()
        assert "Air quality dialog opened" in mock_helpers.update_status.call_args[0][1]

    @pytest.mark.asyncio
    async def test_handler_shows_error_on_exception(self, mock_app, mock_widget):
        """Test handler shows error dialog when exception occurs."""
        captured_dialogs = []

        async def capture_dialog(dialog):
            captured_dialogs.append(dialog)

        mock_app.main_window.dialog = capture_dialog

        with patch(
            "accessiweather.handlers.weather_handlers.AirQualityDialog",
            side_effect=Exception("Dialog error"),
        ):
            await on_view_air_quality(mock_app, mock_widget)

        assert len(captured_dialogs) == 1
        assert isinstance(captured_dialogs[0], toga.InfoDialog)


@pytest.mark.unit
class TestAirQualityDialogLocationProperty:
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
        """Environmental data with air quality info."""
        hourly = HourlyAirQuality(
            timestamp=datetime.now(timezone.utc),
            aqi=45,
            category="Good",
            pm2_5=12.5,
        )
        return EnvironmentalConditions(
            air_quality_index=45.0,
            air_quality_category="Good",
            hourly_air_quality=[hourly],
        )

    def test_dialog_title_contains_location_name_simple(
        self, mock_toga_app, valid_environmental_data
    ):
        """Test dialog title contains a simple location name."""
        dialog = AirQualityDialog(
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
        dialog = AirQualityDialog(
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
        dialog = AirQualityDialog(
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
        dialog = AirQualityDialog(
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
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name=long_name,
            environmental=valid_environmental_data,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert long_name in dialog.window.title

    def test_dialog_title_format_is_consistent(self, mock_toga_app, valid_environmental_data):
        """Test dialog title follows expected format: 'Air Quality - <location>'."""
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Chicago",
            environmental=valid_environmental_data,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert dialog.window.title == "Air Quality - Chicago"

    def test_dialog_title_contains_location_when_no_aq_data(self, mock_toga_app):
        """Test dialog title contains location even when no AQ data."""
        empty_environmental = EnvironmentalConditions()
        dialog = AirQualityDialog(
            app=mock_toga_app,
            location_name="Empty City",
            environmental=empty_environmental,
        )
        dialog._build_ui()

        assert dialog.window is not None
        assert "Empty City" in dialog.window.title
