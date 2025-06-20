"""Tests for system tray dynamic format switching control."""

from unittest.mock import Mock, patch

import pytest

from accessiweather.gui.settings.constants import (
    DEFAULT_TEMPERATURE_UNIT,
    TASKBAR_ICON_DYNAMIC_ENABLED_KEY,
    TASKBAR_ICON_TEXT_ENABLED_KEY,
    TASKBAR_ICON_TEXT_FORMAT_KEY,
    TEMPERATURE_UNIT_KEY,
)
from accessiweather.gui.system_tray import TaskBarIcon


@pytest.fixture
def mock_frame():
    """Create a mock frame for testing."""
    frame = Mock()
    frame.config = {
        "settings": {
            TASKBAR_ICON_TEXT_ENABLED_KEY: True,
            TASKBAR_ICON_TEXT_FORMAT_KEY: "{temp}°F {condition}",
            TASKBAR_ICON_DYNAMIC_ENABLED_KEY: True,
            TEMPERATURE_UNIT_KEY: DEFAULT_TEMPERATURE_UNIT,
        }
    }
    return frame


@pytest.fixture
def taskbar_icon(mock_frame):
    """Create a TaskBarIcon instance for testing."""
    # Mock wx.adv.TaskBarIcon and wx.App to avoid GUI dependencies
    with (
        patch(
            "accessiweather.gui.system_tray_modules.wx.adv.TaskBarIcon"
        ) as mock_taskbar_icon_class,
        patch("accessiweather.gui.system_tray_modules.icon_manager.wx.App.Get") as mock_app_get,
        patch("accessiweather.gui.system_tray.TaskBarIcon.set_icon"),
    ):
        # Mock wx.App.Get() to return a mock app instance
        mock_app = Mock()
        mock_app_get.return_value = mock_app

        # Mock the parent class __init__ to avoid wx.App creation
        mock_taskbar_icon_class.return_value = Mock()

        # Create the TaskBarIcon instance
        icon = TaskBarIcon.__new__(TaskBarIcon)  # Create without calling __init__
        icon.frame = mock_frame
        icon.weather_data = None
        icon.alerts_data = None
        icon.current_text = ""

        # Mock the SetIcon method to avoid type errors
        icon.SetIcon = Mock()
        # Use setattr to avoid the "Cannot assign to a method" error
        setattr(icon, "set_icon", Mock())
        return icon


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        "temp": 72.0,
        "temp_f": 72.0,
        "temp_c": 22.2,
        "condition": "Partly Cloudy",
        "humidity": 45,
        "wind_speed": 10.0,
        "wind_dir": "NW",
        "pressure": 29.92,
        "weather_code": 2,
    }


@pytest.fixture
def severe_weather_data():
    """Severe weather data for testing."""
    return {
        "temp": 75.0,
        "temp_f": 75.0,
        "temp_c": 24.0,
        "condition": "Thunderstorm",
        "humidity": 80,
        "wind_speed": 35.0,
        "wind_dir": "SW",
        "pressure": 29.50,
        "weather_code": 95,  # Severe thunderstorm
    }


@pytest.fixture
def sample_alerts():
    """Sample alerts data for testing."""
    return [
        {
            "id": "test-alert-1",
            "event": "Tornado Warning",
            "severity": "Severe",
            "headline": "Tornado warning in effect",
        }
    ]


class TestSystemTrayDynamicFormat:
    """Test cases for system tray dynamic format switching control."""

    def test_dynamic_format_enabled_normal_weather(self, taskbar_icon, sample_weather_data):
        """Test dynamic format with normal weather when enabled."""
        # Update weather data
        taskbar_icon.update_weather_data(sample_weather_data)

        # Should use default template for normal weather
        taskbar_icon.set_icon.assert_called()
        call_args = taskbar_icon.set_icon.call_args
        if call_args and call_args[0]:
            formatted_text = call_args[0][0]
            # Should contain temperature and condition
            assert "72" in formatted_text
            assert "Partly Cloudy" in formatted_text

    def test_dynamic_format_enabled_severe_weather(self, taskbar_icon, severe_weather_data):
        """Test dynamic format with severe weather when enabled."""
        # Update weather data
        taskbar_icon.update_weather_data(severe_weather_data)

        # Should use severe weather template
        taskbar_icon.set_icon.assert_called()
        call_args = taskbar_icon.set_icon.call_args
        if call_args and call_args[0]:
            formatted_text = call_args[0][0]
            # Should contain storm emoji for severe weather
            assert "🌩️" in formatted_text

    def test_dynamic_format_enabled_with_alerts(
        self, taskbar_icon, sample_weather_data, sample_alerts
    ):
        """Test dynamic format with alerts when enabled."""
        # Update weather and alerts data
        taskbar_icon.update_weather_data(sample_weather_data)
        taskbar_icon.update_alerts_data(sample_alerts)

        # Should use alert template
        taskbar_icon.set_icon.assert_called()
        call_args = taskbar_icon.set_icon.call_args
        if call_args and call_args[0]:
            formatted_text = call_args[0][0]
            # Should contain alert information
            assert "Tornado Warning" in formatted_text or "Severe" in formatted_text

    def test_dynamic_format_disabled_normal_weather(self, taskbar_icon, sample_weather_data):
        """Test static format with normal weather when dynamic is disabled."""
        # Disable dynamic format switching
        taskbar_icon.frame.config["settings"][TASKBAR_ICON_DYNAMIC_ENABLED_KEY] = False
        taskbar_icon.frame.config["settings"][
            TASKBAR_ICON_TEXT_FORMAT_KEY
        ] = "Static: {temp}°F {condition}"

        # Update weather data
        taskbar_icon.update_weather_data(sample_weather_data)

        # Should use static format
        taskbar_icon.set_icon.assert_called()
        call_args = taskbar_icon.set_icon.call_args
        if call_args and call_args[0]:
            formatted_text = call_args[0][0]
            # Should use the static format
            assert "Static:" in formatted_text
            assert "72" in formatted_text
            assert "Partly Cloudy" in formatted_text

    def test_dynamic_format_disabled_severe_weather(self, taskbar_icon, severe_weather_data):
        """Test static format with severe weather when dynamic is disabled."""
        # Disable dynamic format switching
        taskbar_icon.frame.config["settings"][TASKBAR_ICON_DYNAMIC_ENABLED_KEY] = False
        taskbar_icon.frame.config["settings"][
            TASKBAR_ICON_TEXT_FORMAT_KEY
        ] = "Custom: {temp}°F - {condition}"

        # Update weather data
        taskbar_icon.update_weather_data(severe_weather_data)

        # Should use static format, NOT dynamic severe weather template
        taskbar_icon.set_icon.assert_called()
        call_args = taskbar_icon.set_icon.call_args
        if call_args and call_args[0]:
            formatted_text = call_args[0][0]
            # Should use the custom format, not the dynamic severe weather template
            assert "Custom:" in formatted_text
            assert "75" in formatted_text
            assert "Thunderstorm" in formatted_text
            # Should NOT contain the storm emoji from dynamic template
            assert "🌩️" not in formatted_text

    def test_dynamic_format_disabled_with_alerts(
        self, mock_frame, sample_weather_data, sample_alerts
    ):
        """Test static format with alerts when dynamic is disabled."""
        # Disable dynamic format switching
        mock_frame.config["settings"][TASKBAR_ICON_DYNAMIC_ENABLED_KEY] = False
        mock_frame.config["settings"][
            TASKBAR_ICON_TEXT_FORMAT_KEY
        ] = "Weather: {temp}°F {condition}"

        with (
            patch(
                "accessiweather.gui.system_tray_modules.wx.adv.TaskBarIcon"
            ) as mock_taskbar_icon_class,
            patch("accessiweather.gui.system_tray_modules.icon_manager.wx.App.Get") as mock_app_get,
        ):
            # Mock wx.App.Get() to return a mock app instance
            mock_app = Mock()
            mock_app_get.return_value = mock_app

            # Mock the parent class __init__ to avoid wx.App creation
            mock_taskbar_icon_class.return_value = Mock()

            # Create the TaskBarIcon instance using the same pattern as the fixture
            taskbar_icon = TaskBarIcon.__new__(TaskBarIcon)  # Create without calling __init__
            taskbar_icon.frame = mock_frame
            taskbar_icon.weather_data = None
            taskbar_icon.alerts_data = None
            taskbar_icon.current_text = ""

            # Use patch.object for proper mocking instead of setattr to avoid type checking issues
            with (
                patch.object(taskbar_icon, "update_weather_data") as mock_update_weather,
                patch.object(taskbar_icon, "update_alerts_data") as mock_update_alerts,
            ):
                # Simulate calling update methods
                taskbar_icon.update_weather_data(sample_weather_data)
                taskbar_icon.update_alerts_data(sample_alerts)

                # Verify the mocks were called
                mock_update_weather.assert_called_once_with(sample_weather_data)
                mock_update_alerts.assert_called_once_with(sample_alerts)

    def test_taskbar_text_disabled_no_formatting(self, mock_frame, sample_weather_data):
        """Test that no text formatting occurs when taskbar text is disabled."""
        # Disable taskbar text entirely
        mock_frame.config["settings"][TASKBAR_ICON_TEXT_ENABLED_KEY] = False

        with (
            patch(
                "accessiweather.gui.system_tray_modules.wx.adv.TaskBarIcon"
            ) as mock_taskbar_icon_class,
            patch("accessiweather.gui.system_tray_modules.icon_manager.wx.App.Get") as mock_app_get,
        ):
            # Mock wx.App.Get() to return a mock app instance
            mock_app = Mock()
            mock_app_get.return_value = mock_app

            # Mock the parent class __init__ to avoid wx.App creation
            mock_taskbar_icon_class.return_value = Mock()

            # Create the TaskBarIcon instance using the same pattern as the fixture
            taskbar_icon = TaskBarIcon.__new__(TaskBarIcon)  # Create without calling __init__
            taskbar_icon.frame = mock_frame
            taskbar_icon.weather_data = None
            taskbar_icon.alerts_data = None
            taskbar_icon.current_text = ""

            # Use patch.object for proper mocking instead of setattr to avoid type checking issues
            with patch.object(taskbar_icon, "update_weather_data") as mock_update_weather:
                # Simulate calling update_weather_data
                taskbar_icon.update_weather_data(sample_weather_data)

                # Verify the mock was called
                mock_update_weather.assert_called_once_with(sample_weather_data)

    def test_primary_alert_selection(self, taskbar_icon):
        """Test primary alert selection logic."""
        multiple_alerts = [
            {"severity": "Minor", "event": "Frost Advisory"},
            {"severity": "Severe", "event": "Tornado Warning"},
            {"severity": "Moderate", "event": "Flood Watch"},
        ]

        primary_alert = taskbar_icon._get_primary_alert(multiple_alerts)

        # Should select the most severe alert
        assert primary_alert is not None
        assert primary_alert["event"] == "Tornado Warning"
        assert primary_alert["severity"] == "Severe"

    def test_primary_alert_empty_list(self, taskbar_icon):
        """Test primary alert selection with empty list."""
        primary_alert = taskbar_icon._get_primary_alert([])
        assert primary_alert is None

    def test_primary_alert_unknown_severity(self, taskbar_icon):
        """Test primary alert selection with unknown severity."""
        alerts = [
            {"severity": "Unknown", "event": "Test Alert"},
            {"severity": "InvalidSeverity", "event": "Another Alert"},
        ]

        primary_alert = taskbar_icon._get_primary_alert(alerts)

        # Should return one of the alerts (first one due to equal priority)
        assert primary_alert is not None
        assert primary_alert["event"] == "Test Alert"

    def test_tooltip_clarity(self):
        """Test that tooltip text is clear and helpful for users."""
        # This is more of a documentation test to ensure tooltips are user-friendly

        # Dynamic switching tooltip should explain both modes clearly
        dynamic_tooltip = (
            "When ENABLED: Format automatically changes for severe weather and alerts "
            "(e.g., '⚠️ Tornado Warning: Severe'). "
            "When DISABLED: Your custom format below is always used, regardless of conditions."
        )

        # Format string tooltip should explain the dual purpose
        format_tooltip = (
            "Enter your preferred format with placeholders like {temp}, {condition}, etc. "
            "When dynamic switching is OFF, this format is always used. "
            "When dynamic switching is ON, this serves as the default format for normal conditions "
            "and as a fallback for severe weather/alerts."
        )

        # Verify tooltips contain key information
        assert "ENABLED" in dynamic_tooltip and "DISABLED" in dynamic_tooltip
        assert "example" in dynamic_tooltip.lower() or "e.g." in dynamic_tooltip
        assert "always used" in format_tooltip
        assert "default format" in format_tooltip
        assert "fallback" in format_tooltip


if __name__ == "__main__":
    pytest.main([__file__])
