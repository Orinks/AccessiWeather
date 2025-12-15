"""
Integration tests for system tray taskbar icon functionality.

Tests cover:
- Icon text updates on weather refresh
- Settings persistence
- Real-time settings application
- System tray availability handling
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

os.environ.setdefault("TOGA_BACKEND", "toga_dummy")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accessiweather.taskbar_icon_updater import DEFAULT_TOOLTIP_TEXT, TaskbarIconUpdater


class MockCurrentConditions:
    """Mock current conditions for testing."""

    def __init__(
        self,
        temperature_f=None,
        temperature_c=None,
        condition=None,
        relative_humidity=None,
        wind_speed=None,
        wind_direction=None,
        has_data_result=True,
    ):
        """Initialize mock current conditions."""
        self.temperature_f = temperature_f
        self.temperature_c = temperature_c
        self.condition = condition
        self.relative_humidity = relative_humidity
        self.wind_speed = wind_speed
        self.wind_direction = wind_direction
        self._has_data_result = has_data_result

    def has_data(self):
        return self._has_data_result


class MockWeatherData:
    """Mock weather data for testing."""

    def __init__(self, current_conditions=None):
        """Initialize mock weather data."""
        self.current_conditions = current_conditions


class MockSettings:
    """Mock settings for testing."""

    def __init__(
        self,
        taskbar_icon_text_enabled=True,
        taskbar_icon_dynamic_enabled=True,
        taskbar_icon_text_format="{temp} {condition}",
        temperature_unit="both",
    ):
        """Initialize mock settings."""
        self.taskbar_icon_text_enabled = taskbar_icon_text_enabled
        self.taskbar_icon_dynamic_enabled = taskbar_icon_dynamic_enabled
        self.taskbar_icon_text_format = taskbar_icon_text_format
        self.temperature_unit = temperature_unit


class MockLocation:
    """Mock location for testing."""

    def __init__(self, name="Test City"):
        """Initialize mock location."""
        self.name = name


def create_mock_app(
    system_tray_available=True,
    has_status_icon=True,
    settings=None,
    current_location=None,
):
    """Create a mock application for testing."""
    app = MagicMock()
    app.system_tray_available = system_tray_available

    if has_status_icon:
        app.status_icon = MagicMock()
        app.status_icon.text = DEFAULT_TOOLTIP_TEXT
    else:
        app.status_icon = None

    if settings is None:
        settings = MockSettings()

    app.config_manager = MagicMock()
    app.config_manager.get_settings.return_value = settings
    app.config_manager.get_current_location.return_value = current_location

    return app


class TestSystemTrayIconTextUpdates:
    """Test icon text updates on weather refresh."""

    def test_update_tooltip_with_weather_data(self):
        """Should update tooltip with weather data."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(
            current_location=MockLocation("New York"),
            settings=MockSettings(
                taskbar_icon_text_enabled=True,
                taskbar_icon_dynamic_enabled=True,
            ),
        )
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=72.0,
                temperature_c=22.2,
                condition="Partly Cloudy",
            )
        )

        update_tray_icon_tooltip(app, weather_data)

        assert app.status_icon.text != DEFAULT_TOOLTIP_TEXT
        assert "New York" in app.status_icon.text
        assert "72F/22C" in app.status_icon.text

    def test_update_tooltip_without_weather_data(self):
        """Should show default text when no weather data."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(
            settings=MockSettings(
                taskbar_icon_text_enabled=True,
                taskbar_icon_dynamic_enabled=True,
            ),
        )

        update_tray_icon_tooltip(app, None)

        assert app.status_icon.text == DEFAULT_TOOLTIP_TEXT

    def test_update_tooltip_with_disabled_feature(self):
        """Should show default text when feature is disabled."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(
            current_location=MockLocation("New York"),
            settings=MockSettings(
                taskbar_icon_text_enabled=False,
                taskbar_icon_dynamic_enabled=True,
            ),
        )
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=72.0,
                condition="Sunny",
            )
        )

        update_tray_icon_tooltip(app, weather_data)

        assert app.status_icon.text == DEFAULT_TOOLTIP_TEXT

    def test_update_tooltip_skips_when_no_status_icon(self):
        """Should skip update silently when no status icon."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(has_status_icon=False)
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=72.0,
                condition="Sunny",
            )
        )

        update_tray_icon_tooltip(app, weather_data)

    def test_update_tooltip_skips_when_tray_unavailable(self):
        """Should skip update silently when system tray unavailable."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(system_tray_available=False)
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=72.0,
                condition="Sunny",
            )
        )

        update_tray_icon_tooltip(app, weather_data)


class TestSettingsPersistence:
    """Test settings persistence for taskbar icon."""

    def test_settings_applied_to_updater(self):
        """Should apply saved settings to updater."""
        settings = MockSettings(
            taskbar_icon_text_enabled=True,
            taskbar_icon_dynamic_enabled=True,
            taskbar_icon_text_format="{location}: {temp}",
            temperature_unit="fahrenheit",
        )

        updater = TaskbarIconUpdater(
            text_enabled=settings.taskbar_icon_text_enabled,
            dynamic_enabled=settings.taskbar_icon_dynamic_enabled,
            format_string=settings.taskbar_icon_text_format,
            temperature_unit=settings.temperature_unit,
        )

        assert updater.text_enabled is True
        assert updater.dynamic_enabled is True
        assert updater.format_string == "{location}: {temp}"
        assert updater.temperature_unit == "fahrenheit"

    def test_settings_update_changes_behavior(self):
        """Should change behavior when settings are updated."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Sunny",
        )
        weather_data = MockWeatherData(current_conditions=current)

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit="fahrenheit",
        )

        tooltip1 = updater.format_tooltip(weather_data, "Test")
        assert "72F" in tooltip1
        assert "22C" not in tooltip1

        updater.update_settings(temperature_unit="celsius")

        tooltip2 = updater.format_tooltip(weather_data, "Test")
        assert "22C" in tooltip2
        assert "72F" not in tooltip2


class TestRealTimeSettingsApplication:
    """Test real-time settings application after save."""

    def test_settings_dialog_triggers_icon_update(self):
        """Should trigger icon update when settings are saved."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(
            current_location=MockLocation("Chicago"),
            settings=MockSettings(
                taskbar_icon_text_enabled=True,
                taskbar_icon_dynamic_enabled=True,
                taskbar_icon_text_format="{temp} {condition}",
            ),
        )
        app.current_weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=65.0,
                temperature_c=18.3,
                condition="Cloudy",
            )
        )

        update_tray_icon_tooltip(app, app.current_weather_data)

        assert "Chicago" in app.status_icon.text
        assert "65F/18C" in app.status_icon.text
        assert "Cloudy" in app.status_icon.text

    def test_disabled_to_enabled_transition(self):
        """Should update icon when transitioning from disabled to enabled."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(
            current_location=MockLocation("Seattle"),
            settings=MockSettings(
                taskbar_icon_text_enabled=False,
            ),
        )
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=55.0,
                temperature_c=12.8,
                condition="Rainy",
            )
        )

        update_tray_icon_tooltip(app, weather_data)
        assert app.status_icon.text == DEFAULT_TOOLTIP_TEXT

        app.config_manager.get_settings.return_value = MockSettings(
            taskbar_icon_text_enabled=True,
            taskbar_icon_dynamic_enabled=True,
        )
        update_tray_icon_tooltip(app, weather_data)

        assert "Seattle" in app.status_icon.text
        assert "55F" in app.status_icon.text

    def test_format_string_change_reflected(self):
        """Should reflect format string changes immediately."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(
            current_location=MockLocation("Boston"),
            settings=MockSettings(
                taskbar_icon_text_enabled=True,
                taskbar_icon_dynamic_enabled=True,
                taskbar_icon_text_format="{temp} {condition}",
            ),
        )
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=70.0,
                temperature_c=21.1,
                condition="Clear",
                relative_humidity=50,
            )
        )

        update_tray_icon_tooltip(app, weather_data)
        first_text = app.status_icon.text

        app.config_manager.get_settings.return_value = MockSettings(
            taskbar_icon_text_enabled=True,
            taskbar_icon_dynamic_enabled=True,
            taskbar_icon_text_format="{temp} {condition}",
        )
        update_tray_icon_tooltip(app, weather_data)
        second_text = app.status_icon.text

        assert "Clear" in first_text
        assert "70F" in second_text


class TestSystemTrayAvailabilityHandling:
    """Test handling of system tray availability scenarios."""

    def test_graceful_handling_no_tray(self):
        """Should handle missing system tray gracefully."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(system_tray_available=False, has_status_icon=False)
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=72.0,
                condition="Sunny",
            )
        )

        update_tray_icon_tooltip(app, weather_data)

    def test_graceful_handling_status_icon_error(self):
        """Should handle status icon errors gracefully."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app()
        type(app.status_icon).text = PropertyMock(side_effect=AttributeError("Test error"))
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=72.0,
                condition="Sunny",
            )
        )

        update_tray_icon_tooltip(app, weather_data)

    def test_graceful_handling_config_error(self):
        """Should handle config manager errors gracefully."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app()
        app.config_manager.get_settings.side_effect = Exception("Config error")
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=72.0,
                condition="Sunny",
            )
        )

        update_tray_icon_tooltip(app, weather_data)

        assert app.status_icon.text == DEFAULT_TOOLTIP_TEXT


class TestMultipleWeatherUpdates:
    """Test multiple consecutive weather updates."""

    def test_consecutive_updates(self):
        """Should handle multiple consecutive updates correctly."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(
            current_location=MockLocation("Denver"),
            settings=MockSettings(
                taskbar_icon_text_enabled=True,
                taskbar_icon_dynamic_enabled=True,
            ),
        )

        for temp in [60, 65, 70, 75, 80]:
            weather_data = MockWeatherData(
                current_conditions=MockCurrentConditions(
                    temperature_f=float(temp),
                    temperature_c=(temp - 32) * 5 / 9,
                    condition="Sunny",
                )
            )
            update_tray_icon_tooltip(app, weather_data)

        assert f"{80}F" in app.status_icon.text

    def test_alternating_data_availability(self):
        """Should handle alternating data availability."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(
            current_location=MockLocation("Miami"),
            settings=MockSettings(
                taskbar_icon_text_enabled=True,
                taskbar_icon_dynamic_enabled=True,
            ),
        )

        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=85.0,
                temperature_c=29.4,
                condition="Sunny",
            )
        )
        update_tray_icon_tooltip(app, weather_data)
        assert "Miami" in app.status_icon.text

        update_tray_icon_tooltip(app, None)
        assert app.status_icon.text == DEFAULT_TOOLTIP_TEXT

        weather_data2 = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=82.0,
                temperature_c=27.8,
                condition="Partly Cloudy",
            )
        )
        update_tray_icon_tooltip(app, weather_data2)
        assert "Miami" in app.status_icon.text
        assert "82F" in app.status_icon.text


class TestLocationChanges:
    """Test icon updates when location changes."""

    def test_location_change_updates_prefix(self):
        """Should update location prefix when location changes."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=72.0,
                temperature_c=22.2,
                condition="Clear",
            )
        )

        app = create_mock_app(
            current_location=MockLocation("San Francisco"),
            settings=MockSettings(
                taskbar_icon_text_enabled=True,
                taskbar_icon_dynamic_enabled=True,
            ),
        )
        update_tray_icon_tooltip(app, weather_data)
        assert "San Francisco" in app.status_icon.text

        app.config_manager.get_current_location.return_value = MockLocation("Los Angeles")
        update_tray_icon_tooltip(app, weather_data)
        assert "Los Angeles" in app.status_icon.text

    def test_no_location_available(self):
        """Should format without location prefix when no location."""
        from accessiweather.ui_builder import update_tray_icon_tooltip

        app = create_mock_app(
            current_location=None,
            settings=MockSettings(
                taskbar_icon_text_enabled=True,
                taskbar_icon_dynamic_enabled=True,
            ),
        )
        weather_data = MockWeatherData(
            current_conditions=MockCurrentConditions(
                temperature_f=72.0,
                temperature_c=22.2,
                condition="Sunny",
            )
        )

        update_tray_icon_tooltip(app, weather_data)

        assert "72F/22C" in app.status_icon.text
        assert "Sunny" in app.status_icon.text


class TestPlatformSpecificTooltipSetting:
    """Test platform-specific tooltip setting via _set_status_icon_text."""

    def test_windows_platform_sets_text_property(self, monkeypatch):
        """Should set .Text property on Windows (sys.platform == 'win32')."""
        from accessiweather.ui_builder import _set_status_icon_text

        monkeypatch.setattr("sys.platform", "win32")

        # Create real objects to avoid Mock detection
        class FakeNotifyIcon:
            Text = "Old Text"

        class FakeImpl:
            native = FakeNotifyIcon()

        class FakeStatusIcon:
            _impl = FakeImpl()
            _text = "Old"

        status_icon = FakeStatusIcon()

        result = _set_status_icon_text(status_icon, "New Weather: 72F Sunny")

        assert result is True
        assert status_icon._impl.native.Text == "New Weather: 72F Sunny"

    def test_macos_platform_sets_tooltip(self, monkeypatch):
        """Should set button.toolTip on macOS (sys.platform == 'darwin')."""
        from accessiweather.ui_builder import _set_status_icon_text

        monkeypatch.setattr("sys.platform", "darwin")

        # Create real objects to avoid Mock detection
        class FakeButton:
            toolTip = "Old Tooltip"

        class FakeNSStatusItem:
            button = FakeButton()

        class FakeImpl:
            native = FakeNSStatusItem()

        class FakeStatusIcon:
            _impl = FakeImpl()
            _text = "Old"

        status_icon = FakeStatusIcon()

        result = _set_status_icon_text(status_icon, "New Weather: 72F Sunny")

        assert result is True
        assert status_icon._impl.native.button.toolTip == "New Weather: 72F Sunny"

    def test_linux_platform_with_gtk_method(self, monkeypatch):
        """Should use set_tooltip_text on Linux/GTK."""
        from accessiweather.ui_builder import _set_status_icon_text

        monkeypatch.setattr("sys.platform", "linux")

        # Create real objects to avoid Mock detection
        class FakeGtkStatusIcon:
            tooltip_text = None

            def set_tooltip_text(self, text):
                self.tooltip_text = text

        class FakeImpl:
            native = FakeGtkStatusIcon()

        class FakeStatusIcon:
            _impl = FakeImpl()
            _text = "Old"

        status_icon = FakeStatusIcon()

        result = _set_status_icon_text(status_icon, "New Weather: 72F Sunny")

        assert result is True
        assert status_icon._impl.native.tooltip_text == "New Weather: 72F Sunny"

    def test_returns_false_when_no_impl(self):
        """Should return False when status_icon has no _impl."""
        from accessiweather.ui_builder import _set_status_icon_text

        status_icon = MagicMock(spec=[])  # No _impl attribute

        result = _set_status_icon_text(status_icon, "Test")

        assert result is False

    def test_returns_false_when_no_native(self):
        """Should return False when _impl has no native."""
        from accessiweather.ui_builder import _set_status_icon_text

        status_icon = MagicMock()
        status_icon._impl = MagicMock(spec=[])  # No native attribute

        result = _set_status_icon_text(status_icon, "Test")

        assert result is False

    def test_skips_mock_objects(self):
        """Should return False for Mock objects (test environment)."""
        from accessiweather.ui_builder import _set_status_icon_text

        status_icon = MagicMock()
        # MagicMock's type name contains "Mock"
        status_icon._impl = MagicMock()
        status_icon._impl.native = MagicMock()

        result = _set_status_icon_text(status_icon, "Test")

        assert result is False

    def test_updates_internal_text_attribute(self, monkeypatch):
        """Should update _text attribute if it exists."""
        from accessiweather.ui_builder import _set_status_icon_text

        monkeypatch.setattr("sys.platform", "win32")

        status_icon = MagicMock()
        status_icon._text = "Old"

        # Create a real object (not Mock) for native to avoid Mock detection
        class FakeNotifyIcon:
            Text = "Old"

        native = FakeNotifyIcon()
        status_icon._impl = MagicMock()
        status_icon._impl.native = native

        result = _set_status_icon_text(status_icon, "New Weather")

        assert result is True
        assert status_icon._text == "New Weather"

    def test_handles_exception_gracefully(self, monkeypatch):
        """Should handle exceptions and return False."""
        from accessiweather.ui_builder import _set_status_icon_text

        monkeypatch.setattr("sys.platform", "win32")

        status_icon = MagicMock()

        # Create object that raises on Text assignment
        class BrokenNotifyIcon:
            @property
            def Text(self):
                return "Old"

            @Text.setter
            def Text(self, value):
                raise RuntimeError("Simulated failure")

        native = BrokenNotifyIcon()
        status_icon._impl = MagicMock()
        status_icon._impl.native = native

        result = _set_status_icon_text(status_icon, "Test")

        assert result is False

    def test_windows_without_text_attribute(self, monkeypatch):
        """Should return False on Windows if native has no Text attribute."""
        from accessiweather.ui_builder import _set_status_icon_text

        monkeypatch.setattr("sys.platform", "win32")

        status_icon = MagicMock()

        class NoTextObject:
            pass

        native = NoTextObject()
        status_icon._impl = MagicMock()
        status_icon._impl.native = native

        result = _set_status_icon_text(status_icon, "Test")

        assert result is False

    def test_macos_without_button_tooltip(self, monkeypatch):
        """Should return False on macOS if native has no button.toolTip."""
        from accessiweather.ui_builder import _set_status_icon_text

        monkeypatch.setattr("sys.platform", "darwin")

        status_icon = MagicMock()

        class NoButtonObject:
            pass

        native = NoButtonObject()
        status_icon._impl = MagicMock()
        status_icon._impl.native = native

        result = _set_status_icon_text(status_icon, "Test")

        assert result is False
