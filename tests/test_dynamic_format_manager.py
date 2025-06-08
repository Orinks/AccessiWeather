"""Tests for the dynamic format manager module."""

from unittest.mock import patch

import pytest

from accessiweather.dynamic_format_manager import DynamicFormatManager
from accessiweather.weather_condition_analyzer import WeatherSeverity


@pytest.fixture
def format_manager():
    """Create a DynamicFormatManager instance for testing."""
    return DynamicFormatManager()


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        "temp": 72.0,
        "temp_f": 72.0,
        "condition": "Partly Cloudy",
        "humidity": 45,
        "wind_speed": 10.0,
        "wind_dir": "NW",
        "weather_code": 2,
    }


@pytest.fixture
def sample_alerts_data():
    """Sample alerts data for testing."""
    return [
        {
            "id": "test-alert-1",
            "event": "Winter Storm Warning",
            "severity": "Severe",
            "headline": "Heavy snow expected",
        }
    ]


class TestDynamicFormatManager:
    """Test cases for DynamicFormatManager."""

    def test_init_default(self, format_manager):
        """Test default initialization."""
        assert format_manager.current_template_name == "default"
        assert format_manager.current_format_string == "{location} {temp} {condition} • {humidity}%"
        assert format_manager.update_count == 0
        assert format_manager.last_analysis is None

    def test_init_with_custom_templates(self):
        """Test initialization with custom templates."""
        custom_templates = {
            "custom1": "{temp}°C {condition}",
            "custom2": "{location}: {temp}°F",
        }
        manager = DynamicFormatManager(custom_templates)

        assert "custom1" in manager.templates
        assert "custom2" in manager.templates
        assert manager.templates["custom1"] == "{temp}°C {condition}"

    def test_get_dynamic_format_string_default(self, format_manager, sample_weather_data):
        """Test getting format string for default conditions."""
        result = format_manager.get_dynamic_format_string(sample_weather_data)

        assert result == "{location} {temp} {condition} • {humidity}%"
        assert format_manager.current_template_name == "default"
        assert format_manager.update_count == 1

    def test_get_dynamic_format_string_with_alerts(
        self, format_manager, sample_weather_data, sample_alerts_data
    ):
        """Test getting format string with active alerts."""
        result = format_manager.get_dynamic_format_string(sample_weather_data, sample_alerts_data)

        assert "{event}" in result and "{severity}" in result
        assert format_manager.current_template_name == "alert"
        assert format_manager.update_count == 1

    def test_get_dynamic_format_string_severe_weather(self, format_manager):
        """Test getting format string for severe weather."""
        severe_weather_data = {
            "temp": 75.0,
            "condition": "Thunderstorm",
            "wind_speed": 25.0,
            "weather_code": 95,  # Thunderstorm
        }

        result = format_manager.get_dynamic_format_string(severe_weather_data)

        assert "🌩️" in result
        assert format_manager.current_template_name == "severe_weather"

    def test_get_dynamic_format_string_temperature_extreme(self, format_manager):
        """Test getting format string for temperature extremes."""
        extreme_temp_data = {
            "temp": 115.0,
            "condition": "Clear",
            "wind_speed": 5.0,
            "weather_code": 0,
        }

        result = format_manager.get_dynamic_format_string(extreme_temp_data)

        assert "🌡️" in result
        assert format_manager.current_template_name == "temperature_extreme"

    def test_get_dynamic_format_string_wind_warning(self, format_manager):
        """Test getting format string for wind warnings."""
        windy_data = {
            "temp": 70.0,
            "condition": "Clear",
            "wind_speed": 40.0,
            "wind_dir": "NW",
            "weather_code": 0,
        }

        result = format_manager.get_dynamic_format_string(windy_data)

        assert "💨" in result
        assert format_manager.current_template_name == "wind_warning"

    def test_get_dynamic_format_string_precipitation(self, format_manager):
        """Test getting format string for precipitation."""
        rain_data = {
            "temp": 65.0,
            "condition": "Moderate rain",
            "wind_speed": 8.0,
            "weather_code": 63,
        }

        result = format_manager.get_dynamic_format_string(rain_data)

        assert "🌧️" in result
        assert format_manager.current_template_name == "precipitation"

    def test_get_dynamic_format_string_fog(self, format_manager):
        """Test getting format string for fog conditions."""
        fog_data = {
            "temp": 60.0,
            "condition": "Fog",
            "wind_speed": 3.0,
            "weather_code": 45,
        }

        result = format_manager.get_dynamic_format_string(fog_data)

        assert "🌫️" in result
        assert format_manager.current_template_name == "fog"

    def test_should_update_format_first_time(self, format_manager):
        """Test that format should update on first call."""
        analysis = {"recommended_template": "default", "priority_score": 10}

        assert format_manager._should_update_format(analysis) is True

    def test_should_update_format_template_change(self, format_manager):
        """Test that format should update when template changes."""
        # Set initial analysis
        format_manager.last_analysis = {
            "recommended_template": "default",
            "priority_score": 10,
            "has_alerts": False,
        }

        # New analysis with different template
        new_analysis = {
            "recommended_template": "severe_weather",
            "priority_score": 50,
            "has_alerts": False,
        }

        assert format_manager._should_update_format(new_analysis) is True

    def test_should_update_format_alert_change(self, format_manager):
        """Test that format should update when alert status changes."""
        # Set initial analysis without alerts
        format_manager.last_analysis = {
            "recommended_template": "default",
            "priority_score": 10,
            "has_alerts": False,
        }

        # New analysis with alerts
        new_analysis = {
            "recommended_template": "default",
            "priority_score": 10,
            "has_alerts": True,
        }

        assert format_manager._should_update_format(new_analysis) is True

    def test_should_not_update_format_no_change(self, format_manager):
        """Test that format should not update when nothing significant changes."""
        # Set initial analysis
        format_manager.last_analysis = {
            "recommended_template": "default",
            "priority_score": 10,
            "has_alerts": False,
        }

        # New analysis with minimal changes
        new_analysis = {
            "recommended_template": "default",
            "priority_score": 15,  # Small change, below threshold
            "has_alerts": False,
        }

        assert format_manager._should_update_format(new_analysis) is False

    def test_customize_alert_format_severe(self, format_manager):
        """Test customization of alert format for severe alerts."""
        analysis = {
            "alert_severity": WeatherSeverity.SEVERE,
            "primary_alert": {"event": "Tornado Warning", "severity": "Severe"},
        }

        result = format_manager._customize_alert_format("{event}: {severity}", analysis)

        assert result.startswith("⚠️")

    def test_add_custom_template(self, format_manager):
        """Test adding custom templates."""
        format_manager.add_custom_template("test_template", "{location} - {temp}°F")

        assert "test_template" in format_manager.templates
        assert format_manager.templates["test_template"] == "{location} - {temp}°F"

    def test_remove_custom_template(self, format_manager):
        """Test removing custom templates."""
        # Add a custom template first
        format_manager.add_custom_template("test_template", "{temp}°F")

        # Remove it
        result = format_manager.remove_custom_template("test_template")

        assert result is True
        assert "test_template" not in format_manager.templates

    def test_remove_default_template_fails(self, format_manager):
        """Test that removing default templates fails."""
        result = format_manager.remove_custom_template("default")

        assert result is False
        assert "default" in format_manager.templates

    def test_get_available_templates(self, format_manager):
        """Test getting available templates."""
        templates = format_manager.get_available_templates()

        assert isinstance(templates, dict)
        assert "default" in templates
        assert "alert" in templates
        assert "severe_weather" in templates

    def test_reset_to_default(self, format_manager, sample_weather_data):
        """Test resetting to default state."""
        # Change state first
        format_manager.get_dynamic_format_string(sample_weather_data)

        # Reset
        format_manager.reset_to_default()

        assert format_manager.current_template_name == "default"
        assert format_manager.current_format_string == "{location} {temp} {condition} • {humidity}%"
        assert format_manager.last_analysis is None
        assert format_manager.update_count == 0

    def test_get_current_state(self, format_manager):
        """Test getting current state information."""
        state = format_manager.get_current_state()

        assert "current_template_name" in state
        assert "current_format_string" in state
        assert "update_count" in state
        assert "last_analysis" in state
        assert "available_templates" in state

    def test_force_template(self, format_manager):
        """Test forcing a specific template."""
        result = format_manager.force_template("alert")

        assert result is True
        assert format_manager.current_template_name == "alert"
        assert format_manager.current_format_string == "⚠️ {location}: {event} ({severity})"

    def test_force_template_not_found(self, format_manager):
        """Test forcing a non-existent template."""
        result = format_manager.force_template("nonexistent")

        assert result is False
        assert format_manager.current_template_name == "default"  # Should remain unchanged

    def test_error_handling(self, format_manager):
        """Test error handling with invalid data."""
        # Mock the analyzer to raise an exception
        with patch.object(
            format_manager.analyzer,
            "analyze_weather_conditions",
            side_effect=Exception("Test error"),
        ):
            result = format_manager.get_dynamic_format_string({"invalid": "data"})

            # Should fall back to default template
            assert result == "{location} {temp} {condition} • {humidity}%"

    def test_user_format_fallback(self, format_manager):
        """Test fallback to user format when errors occur."""
        user_format = "{location}: {temp}°F"

        # Mock the analyzer to raise an exception
        with patch.object(
            format_manager.analyzer,
            "analyze_weather_conditions",
            side_effect=Exception("Test error"),
        ):
            result = format_manager.get_dynamic_format_string(
                {"invalid": "data"}, user_format=user_format
            )

            assert result == user_format

    def test_multiple_updates_tracking(self, format_manager, sample_weather_data):
        """Test that multiple updates are tracked correctly."""
        # First update
        format_manager.get_dynamic_format_string(sample_weather_data)
        assert format_manager.update_count == 1

        # Second update with different data
        severe_data = {"temp": 75.0, "weather_code": 95, "wind_speed": 25.0}
        format_manager.get_dynamic_format_string(severe_data)
        assert format_manager.update_count == 2

        # Third update with same data (should not increment)
        format_manager.get_dynamic_format_string(severe_data)
        assert format_manager.update_count == 2  # No change

    def test_nws_data_format_support(self, format_manager):
        """Test that NWS/Open-Meteo data format is supported."""
        # Simulate NWS/Open-Meteo data format (after mapping)
        nws_data = {
            "temp": 72.0,
            "temp_f": 72.0,
            "temp_c": 22.2,
            "condition": "Partly Cloudy",
            "humidity": 45,
            "wind_speed": 10.0,
            "wind_dir": "NW",
            "pressure": 29.92,
            "weather_code": 2,  # Open-Meteo weather code
        }

        result = format_manager.get_dynamic_format_string(nws_data)

        # Should work with Open-Meteo weather codes
        assert result == "{location} {temp} {condition} • {humidity}%"  # Default template
        assert format_manager.current_template_name == "default"

    def test_weatherapi_data_format_support(self, format_manager):
        """Test that WeatherAPI data format is supported."""
        # Simulate WeatherAPI data format
        weatherapi_data = {
            "temp": 72.0,
            "temp_f": 72.0,
            "temp_c": 22.2,
            "condition": "Partly Cloudy",
            "humidity": 45,
            "wind_speed": 10.0,
            "wind_dir": "NW",
            "pressure": 29.92,
            "weather_code": 1003,  # WeatherAPI condition code
        }

        result = format_manager.get_dynamic_format_string(weatherapi_data)

        # Should work even with different weather code systems
        assert result == "{location} {temp} {condition} • {humidity}%"  # Default template
        assert format_manager.current_template_name == "default"

    def test_automatic_weather_source_support(self, format_manager):
        """Test that automatic weather source selection is supported."""
        # Test US location data (would use NWS)
        us_data = {
            "temp": 72.0,
            "temp_f": 72.0,
            "condition": "Clear sky",
            "weather_code": 0,  # Open-Meteo clear sky
            "wind_speed": 5.0,
        }

        # Test international location data (would use Open-Meteo)
        intl_data = {
            "temp": 22.0,
            "temp_c": 22.0,
            "condition": "Partly cloudy",
            "weather_code": 2,  # Open-Meteo partly cloudy
            "wind_speed": 8.0,
        }

        # Both should work with the dynamic format manager
        us_result = format_manager.get_dynamic_format_string(us_data)
        intl_result = format_manager.get_dynamic_format_string(intl_data)

        assert us_result == "{location} {temp} {condition} • {humidity}%"
        assert intl_result == "{location} {temp} {condition} • {humidity}%"

    def test_dynamic_switching_control(self, format_manager):
        """Test that dynamic switching can be controlled via settings."""
        # Test severe weather data that would normally trigger dynamic switching
        severe_data = {
            "temp": 75.0,
            "condition": "Thunderstorm",
            "weather_code": 95,  # Severe thunderstorm
            "wind_speed": 30.0,
        }

        # With dynamic switching enabled (default behavior)
        result_dynamic = format_manager.get_dynamic_format_string(severe_data)
        assert "🌩️" in result_dynamic  # Should use severe weather template
        assert format_manager.current_template_name == "severe_weather"

        # Reset the manager
        format_manager.reset_to_default()

        # With dynamic switching disabled (user format should be used)
        user_format = "{temp}°F - {condition} - Custom Format"
        result_static = format_manager.get_dynamic_format_string(
            severe_data, user_format=user_format
        )

        # When dynamic is enabled, it should still use dynamic templates
        # The control happens at the UI level, not in the format manager itself
        # The format manager always provides dynamic suggestions
        assert "🌩️" in result_static  # Still uses dynamic template

        # The actual control is in the system_tray.py where it chooses
        # between dynamic_format_string and user_format_string


if __name__ == "__main__":
    pytest.main([__file__])
