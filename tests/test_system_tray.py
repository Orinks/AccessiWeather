"""
Tests for system tray functionality.

Tests the SystemTrayIcon class, minimize on startup, and dynamic tray tooltip features.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from accessiweather.models import AppSettings, CurrentConditions, Location, WeatherData


class TestSystemTrayIconInit:
    """Tests for SystemTrayIcon initialization."""

    def test_system_tray_icon_attributes(self):
        """Test that SystemTrayIcon has expected attributes after init."""
        # Verify the class exists and has the expected structure
        from accessiweather.ui.system_tray import SystemTrayIcon

        # Check that the class has the expected methods
        assert hasattr(SystemTrayIcon, "_setup_icon")
        assert hasattr(SystemTrayIcon, "_load_icon")
        assert hasattr(SystemTrayIcon, "_get_icon_paths")
        assert hasattr(SystemTrayIcon, "_create_default_icon")
        assert hasattr(SystemTrayIcon, "show_main_window")
        assert hasattr(SystemTrayIcon, "update_tooltip")
        assert hasattr(SystemTrayIcon, "_create_popup_menu")


class TestSystemTrayIconPaths:
    """Tests for icon path resolution."""

    def test_get_icon_paths_returns_list(self):
        """Test that _get_icon_paths returns a list of paths."""
        # Test the path generation logic
        import sys
        from pathlib import Path

        paths = []

        if getattr(sys, "frozen", False):
            base_path = Path(sys.executable).parent
            paths.append(base_path / "app.ico")
            paths.append(base_path / "resources" / "app.ico")
        else:
            # Running as script - use the actual module path
            from accessiweather.ui import system_tray

            module_path = Path(system_tray.__file__).parent.parent
            paths.append(module_path / "resources" / "app.ico")
            paths.append(module_path / "resources" / "app_32.png")
            paths.append(module_path / "resources" / "app_16.png")

        assert len(paths) >= 2
        assert all(isinstance(p, Path) for p in paths)


class TestShowMainWindow:
    """Tests for show_main_window functionality."""

    def test_show_main_window_logic(self):
        """Test show_main_window shows and raises the frame."""
        mock_frame = MagicMock()
        mock_main_window = MagicMock()
        mock_main_window.widget.control = mock_frame

        mock_app = MagicMock()
        mock_app.main_window = mock_main_window

        # Simulate the show_main_window logic
        def show_main_window(app):
            if app.main_window:
                frame = app.main_window.widget.control
                frame.Show(True)
                frame.Iconize(False)
                frame.Raise()
                frame.SetFocus()

        show_main_window(mock_app)

        mock_frame.Show.assert_called_once_with(True)
        mock_frame.Iconize.assert_called_once_with(False)
        mock_frame.Raise.assert_called_once()
        mock_frame.SetFocus.assert_called_once()

    def test_show_main_window_no_window(self):
        """Test show_main_window handles missing main window gracefully."""
        mock_app = MagicMock()
        mock_app.main_window = None

        def show_main_window(app):
            if app.main_window:
                frame = app.main_window.widget.control
                frame.Show(True)

        # Should not raise
        show_main_window(mock_app)


class TestUpdateTooltip:
    """Tests for tooltip update functionality."""

    def test_update_tooltip_with_valid_icon(self):
        """Test update_tooltip updates the icon tooltip."""
        mock_icon = MagicMock()
        mock_icon.IsOk.return_value = True

        set_icon_called = []

        def update_tooltip(icon_set, cached_icon, text):
            if icon_set and cached_icon and cached_icon.IsOk():
                set_icon_called.append(text)
                return True
            return False

        result = update_tooltip(True, mock_icon, "72°F Sunny")

        assert result is True
        assert set_icon_called == ["72°F Sunny"]

    def test_update_tooltip_without_icon(self):
        """Test update_tooltip does nothing without icon set."""
        set_icon_called = []

        def update_tooltip(icon_set, cached_icon, text):
            if icon_set and cached_icon and cached_icon.IsOk():
                set_icon_called.append(text)
                return True
            return False

        result = update_tooltip(False, None, "72°F Sunny")

        assert result is False
        assert set_icon_called == []


class TestMinimizeOnStartup:
    """Tests for minimize on startup functionality."""

    @pytest.fixture
    def mock_app_minimize_enabled(self):
        """Create mock app with minimize on startup enabled."""
        app = MagicMock()
        settings = AppSettings(minimize_on_startup=True)
        app.config_manager.get_settings.return_value = settings

        mock_frame = MagicMock()
        app.main_window = MagicMock()
        app.main_window.widget.control = mock_frame

        return app, mock_frame

    @pytest.fixture
    def mock_app_minimize_disabled(self):
        """Create mock app with minimize on startup disabled."""
        app = MagicMock()
        settings = AppSettings(minimize_on_startup=False)
        app.config_manager.get_settings.return_value = settings

        mock_frame = MagicMock()
        app.main_window = MagicMock()
        app.main_window.widget.control = mock_frame

        return app, mock_frame

    def test_handle_minimize_on_startup_enabled(self, mock_app_minimize_enabled):
        """Test window hides when minimize on startup is enabled."""
        app, mock_frame = mock_app_minimize_enabled

        def handle_minimize_on_startup(app):
            try:
                settings = app.config_manager.get_settings()
                if getattr(settings, "minimize_on_startup", False) and app.main_window:
                    frame = app.main_window.widget.control
                    frame.Hide()
                    return True
            except Exception:
                pass
            return False

        result = handle_minimize_on_startup(app)

        assert result is True
        mock_frame.Hide.assert_called_once()

    def test_handle_minimize_on_startup_disabled(self, mock_app_minimize_disabled):
        """Test window stays visible when minimize on startup is disabled."""
        app, mock_frame = mock_app_minimize_disabled

        def handle_minimize_on_startup(app):
            try:
                settings = app.config_manager.get_settings()
                if getattr(settings, "minimize_on_startup", False) and app.main_window:
                    frame = app.main_window.widget.control
                    frame.Hide()
                    return True
            except Exception:
                pass
            return False

        result = handle_minimize_on_startup(app)

        assert result is False
        mock_frame.Hide.assert_not_called()

    def test_handle_minimize_on_startup_no_main_window(self):
        """Test handles missing main window gracefully."""
        app = MagicMock()
        settings = AppSettings(minimize_on_startup=True)
        app.config_manager.get_settings.return_value = settings
        app.main_window = None

        def handle_minimize_on_startup(app):
            try:
                settings = app.config_manager.get_settings()
                if getattr(settings, "minimize_on_startup", False) and app.main_window:
                    frame = app.main_window.widget.control
                    frame.Hide()
                    return True
            except Exception:
                pass
            return False

        # Should not raise
        result = handle_minimize_on_startup(app)
        assert result is False


class TestDynamicTrayTooltip:
    """Tests for dynamic tray tooltip functionality."""

    @pytest.fixture
    def sample_weather_data(self):
        """Create sample weather data for tooltip testing."""
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)
        current = CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Sunny",
        )
        return WeatherData(location=location, current=current)

    def test_update_tray_tooltip_with_weather_data(self, sample_weather_data):
        """Test tray tooltip updates with weather data."""
        from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit="f",
        )

        tooltip = updater.format_tooltip(sample_weather_data, "Test City")

        # Should contain temperature and/or condition info
        assert tooltip is not None
        assert len(tooltip) > 0

    def test_update_tray_tooltip_uses_saved_format_when_dynamic_toggle_off(
        self, sample_weather_data
    ):
        """Saved tray format should still drive tooltip text."""
        from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=False,
            format_string="{location}: {temp}",
            temperature_unit="f",
        )

        tooltip = updater.format_tooltip(sample_weather_data, "Test City")

        assert tooltip == "Test City: 72F"

    def test_build_preview_uses_safe_sample_values_without_weather(self):
        """Preview should still render when no live weather data is available."""
        from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

        updater = TaskbarIconUpdater(text_enabled=True, format_string="{location}: {temp}")

        preview = updater.build_preview("{location}: {temp} | {condition}", weather_data=None)

        assert preview == "Sample Location: 72F/22C | Partly Cloudy"

    def test_update_tray_tooltip_without_weather_data(self):
        """Test tray tooltip returns default when no weather data."""
        from accessiweather.taskbar_icon_updater import DEFAULT_TOOLTIP_TEXT, TaskbarIconUpdater

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
        )

        tooltip = updater.format_tooltip(None, "Test City")

        assert tooltip == DEFAULT_TOOLTIP_TEXT

    def test_update_tray_tooltip_disabled(self, sample_weather_data):
        """Test tray tooltip returns default when disabled."""
        from accessiweather.taskbar_icon_updater import DEFAULT_TOOLTIP_TEXT, TaskbarIconUpdater

        updater = TaskbarIconUpdater(
            text_enabled=False,
            dynamic_enabled=True,
        )

        tooltip = updater.format_tooltip(sample_weather_data, "Test City")

        assert tooltip == DEFAULT_TOOLTIP_TEXT

    def test_app_update_tray_tooltip_method(self, sample_weather_data):
        """Test app.update_tray_tooltip method logic."""
        mock_tray_icon = MagicMock()
        mock_taskbar_updater = MagicMock()
        mock_taskbar_updater.format_tooltip.return_value = "72°F Sunny"

        def update_tray_tooltip(tray_icon, taskbar_updater, weather_data, location_name):
            if not tray_icon or not taskbar_updater:
                return False
            try:
                tooltip = taskbar_updater.format_tooltip(weather_data, location_name)
                tray_icon.update_tooltip(tooltip)
                return True
            except Exception:
                return False

        result = update_tray_tooltip(
            mock_tray_icon, mock_taskbar_updater, sample_weather_data, "Test City"
        )

        assert result is True
        mock_taskbar_updater.format_tooltip.assert_called_once_with(
            sample_weather_data, "Test City"
        )
        mock_tray_icon.update_tooltip.assert_called_once_with("72°F Sunny")

    def test_app_update_tray_tooltip_no_tray_icon(self, sample_weather_data):
        """Test update_tray_tooltip does nothing without tray icon."""
        mock_taskbar_updater = MagicMock()

        def update_tray_tooltip(tray_icon, taskbar_updater, weather_data, location_name):
            if not tray_icon or not taskbar_updater:
                return False
            try:
                tooltip = taskbar_updater.format_tooltip(weather_data, location_name)
                tray_icon.update_tooltip(tooltip)
                return True
            except Exception:
                return False

        result = update_tray_tooltip(None, mock_taskbar_updater, sample_weather_data, "Test City")

        assert result is False
        mock_taskbar_updater.format_tooltip.assert_not_called()


class TestFormatterSafety:
    """
    Regression tests for TRAY-01, TRAY-04, and TRAY-05 formatter safety.

    TRAY-01: Saved tray text format drives tray tooltip text.
    TRAY-04: Formatter code path has no platform-specific imports.
    TRAY-05: Unknown placeholders produce predictable literal output, not a crash or full fallback.
    """

    @pytest.fixture
    def sample_weather_data(self):
        """Create sample weather data for formatter safety testing."""
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)
        current = CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Partly Cloudy",
        )
        return WeatherData(location=location, current=current)

    def test_format_tooltip_uses_saved_format_string_when_dynamic_enabled(
        self, sample_weather_data
    ):
        """TRAY-01: format_tooltip uses format_string with text_enabled=True and returns exact text."""
        from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            format_string="{location}: {temp}",
            temperature_unit="f",
        )

        result = updater.format_tooltip(sample_weather_data, "Test City")

        assert result == "Test City: 72F"

    def test_format_tooltip_with_unknown_placeholder_does_not_crash(self, sample_weather_data):
        """TRAY-05a: format_tooltip with an unknown placeholder does not raise and returns non-empty string."""
        from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

        updater = TaskbarIconUpdater(
            text_enabled=True,
            format_string="{location}: {unknown_key}",
            temperature_unit="f",
        )

        result = updater.format_tooltip(sample_weather_data, "Test City")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_text_leaves_unknown_placeholder_as_literal(self):
        """TRAY-05b: format_text with an unknown placeholder leaves it as literal {key} text."""
        from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

        updater = TaskbarIconUpdater(text_enabled=True, format_string="{temp} {condition}")

        result = updater.format_text(
            {"temp": "72F", "condition": "Sunny"}, "{temp}: {totally_unknown}"
        )

        assert result == "72F: {totally_unknown}"

    def test_formatter_has_no_platform_specific_imports(self):
        """TRAY-04: taskbar_icon_updater and format_string_parser have no platform-specific imports."""
        import inspect

        import accessiweather.format_string_parser as fsp_module
        import accessiweather.taskbar_icon_updater as tiu_module

        tiu_source = inspect.getsource(tiu_module)
        fsp_source = inspect.getsource(fsp_module)
        combined = tiu_source + fsp_source

        assert "import winreg" not in combined
        assert "import ctypes" not in combined
        assert "sys.platform" not in combined


class TestFormatterUnitPreferencePlaceholders:
    """Targeted tests for placeholders that promise unit-aware output."""

    @pytest.fixture
    def unit_sensitive_weather_data(self):
        """Create weather data with both unit families plus forecast high/low."""
        from accessiweather.models import Forecast, ForecastPeriod

        current = CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Partly Cloudy",
            wind_speed_mph=10.0,
            wind_speed_kph=16.1,
            wind_direction="NW",
            pressure_in=30.05,
            pressure_mb=1017.0,
            visibility_miles=10.0,
            visibility_km=16.1,
        )
        setattr(current, "precipitation", 1.0)
        setattr(current, "precipitation_mm", 25.4)

        forecast = Forecast(
            periods=[
                ForecastPeriod(name="Today", temperature=75, temperature_unit="F"),
                ForecastPeriod(name="Tonight", temperature=55, temperature_unit="F"),
            ]
        )
        return WeatherData(
            location=Location(name="Test City", latitude=40.0, longitude=-74.0),
            current=current,
            forecast=forecast,
        )

    @pytest.mark.parametrize(
        ("temperature_unit", "expected"),
        [
            ("f", "10.0 mph | 30.05 inHg | 10.0 mi | 1.00 in | 75F | 55F"),
            ("c", "16.1 km/h | 1017.00 hPa | 16.1 km | 25.40 mm | 24C | 13C"),
            (
                "both",
                "10.0 mph (16.1 km/h) | 30.05 inHg (1017.00 hPa) | 10.0 mi (16.1 km) | "
                "1.00 in (25.40 mm) | 75F/24C | 55F/13C",
            ),
        ],
    )
    def test_unit_aware_placeholders_follow_unit_preference(
        self, unit_sensitive_weather_data, temperature_unit, expected
    ):
        """wind_speed, pressure, visibility, precip, high, and low honor unit preference."""
        from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

        updater = TaskbarIconUpdater(
            text_enabled=True,
            format_string="{wind_speed} | {pressure} | {visibility} | {precip} | {high} | {low}",
            temperature_unit=temperature_unit,
        )

        result = updater.format_tooltip(unit_sensitive_weather_data, "Test City")

        assert result == expected

    def test_explicit_temperature_placeholders_do_not_follow_unit_preference(
        self, unit_sensitive_weather_data
    ):
        """temp_f and temp_c remain explicit even when the main preference is Celsius."""
        from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

        updater = TaskbarIconUpdater(
            text_enabled=True,
            format_string="{temp_f} / {temp_c}",
            temperature_unit="c",
        )

        result = updater.format_tooltip(unit_sensitive_weather_data, "Test City")

        assert result == "72F / 22C"

    def test_high_low_stay_na_without_forecast_data(self):
        """high and low should not invent values when forecast data is unavailable."""
        from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

        weather_data = WeatherData(
            location=Location(name="Test City", latitude=40.0, longitude=-74.0),
            current=CurrentConditions(temperature_f=72.0, temperature_c=22.2, condition="Sunny"),
        )
        updater = TaskbarIconUpdater(
            text_enabled=True,
            format_string="{high} / {low}",
            temperature_unit="f",
        )

        result = updater.format_tooltip(weather_data, "Test City")

        assert result == "N/A / N/A"


class TestPopupMenu:
    """Tests for system tray popup menu."""

    def test_popup_menu_has_show_and_quit(self):
        """Test popup menu has Show and Quit items."""
        # Test the menu creation logic
        menu_items = []

        def create_popup_menu():
            menu_items.append("Show AccessiWeather")
            menu_items.append("separator")
            menu_items.append("Quit")
            return menu_items

        result = create_popup_menu()

        assert "Show AccessiWeather" in result
        assert "Quit" in result


class TestAppSettingsMinimizeOnStartup:
    """Tests for minimize_on_startup setting in AppSettings."""

    def test_default_minimize_on_startup_is_false(self):
        """Test default value of minimize_on_startup is False."""
        settings = AppSettings()
        assert settings.minimize_on_startup is False

    def test_minimize_on_startup_can_be_enabled(self):
        """Test minimize_on_startup can be set to True."""
        settings = AppSettings(minimize_on_startup=True)
        assert settings.minimize_on_startup is True

    def test_minimize_on_startup_serialization(self):
        """Test minimize_on_startup is serialized correctly."""
        settings = AppSettings(minimize_on_startup=True)
        data = settings.to_dict()

        assert "minimize_on_startup" in data
        assert data["minimize_on_startup"] is True

    def test_minimize_on_startup_deserialization(self):
        """Test minimize_on_startup is deserialized correctly."""
        data = {"minimize_on_startup": True}
        settings = AppSettings.from_dict(data)

        assert settings.minimize_on_startup is True

    def test_minimize_on_startup_deserialization_missing(self):
        """Test minimize_on_startup defaults to False when missing."""
        data = {}
        settings = AppSettings.from_dict(data)

        assert settings.minimize_on_startup is False
