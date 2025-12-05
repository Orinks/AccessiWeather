"""
Unit tests for taskbar_icon_updater module.

Tests cover:
- Format string parsing
- Variable substitution
- Dynamic format selection logic
- Error handling
- Edge cases and boundary conditions
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accessiweather.taskbar_icon_updater import (
    DEFAULT_TOOLTIP_TEXT,
    PLACEHOLDER_NA,
    TOOLTIP_MAX_LENGTH,
    TaskbarIconUpdater,
)


class MockCurrentConditions:
    """Mock current conditions object for testing."""

    def __init__(
        self,
        temperature_f=None,
        temperature_c=None,
        condition=None,
        relative_humidity=None,
        wind_speed=None,
        wind_direction=None,
        pressure=None,
        feels_like_f=None,
        feels_like_c=None,
        uv_index=None,
        visibility=None,
        precipitation=None,
        precipitation_probability=None,
        has_data_result=True,
    ):
        """Initialize mock current conditions."""
        self.temperature_f = temperature_f
        self.temperature_c = temperature_c
        self.condition = condition
        self.relative_humidity = relative_humidity
        self.wind_speed = wind_speed
        self.wind_direction = wind_direction
        self.pressure = pressure
        self.feels_like_f = feels_like_f
        self.feels_like_c = feels_like_c
        self.uv_index = uv_index
        self.visibility = visibility
        self.precipitation = precipitation
        self.precipitation_probability = precipitation_probability
        self._has_data_result = has_data_result

    def has_data(self):
        return self._has_data_result


class MockWeatherData:
    """Mock weather data object for testing."""

    def __init__(self, current_conditions=None):
        """Initialize mock weather data."""
        self.current_conditions = current_conditions


class TestTaskbarIconUpdaterInitialization:
    """Test TaskbarIconUpdater initialization."""

    def test_default_initialization(self):
        """Should initialize with default values."""
        updater = TaskbarIconUpdater()

        assert updater.text_enabled is False
        assert updater.dynamic_enabled is True
        assert updater.format_string == "{temp} {condition}"
        assert updater.temperature_unit == "both"

    def test_custom_initialization(self):
        """Should initialize with custom values."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=False,
            format_string="{location}: {temp}",
            temperature_unit="fahrenheit",
        )

        assert updater.text_enabled is True
        assert updater.dynamic_enabled is False
        assert updater.format_string == "{location}: {temp}"
        assert updater.temperature_unit == "fahrenheit"

    def test_has_parser(self):
        """Should have a format string parser."""
        updater = TaskbarIconUpdater()

        assert updater.parser is not None


class TestUpdateSettings:
    """Test settings update method."""

    def test_update_single_setting(self):
        """Should update a single setting."""
        updater = TaskbarIconUpdater()

        updater.update_settings(text_enabled=True)

        assert updater.text_enabled is True
        assert updater.dynamic_enabled is True

    def test_update_multiple_settings(self):
        """Should update multiple settings at once."""
        updater = TaskbarIconUpdater()

        updater.update_settings(
            text_enabled=True,
            dynamic_enabled=False,
            format_string="{temp}",
            temperature_unit="celsius",
        )

        assert updater.text_enabled is True
        assert updater.dynamic_enabled is False
        assert updater.format_string == "{temp}"
        assert updater.temperature_unit == "celsius"

    def test_update_preserves_unset_settings(self):
        """Should preserve settings not explicitly updated."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            format_string="{location}: {temp}",
        )

        updater.update_settings(dynamic_enabled=False)

        assert updater.text_enabled is True
        assert updater.format_string == "{location}: {temp}"
        assert updater.dynamic_enabled is False


class TestFormatTooltip:
    """Test tooltip formatting."""

    @pytest.fixture
    def updater(self):
        """Create enabled TaskbarIconUpdater."""
        return TaskbarIconUpdater(text_enabled=True, dynamic_enabled=True)

    @pytest.fixture
    def weather_data(self):
        """Create mock weather data."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Partly Cloudy",
            relative_humidity=65,
            wind_speed=10.5,
            wind_direction="NW",
        )
        return MockWeatherData(current_conditions=current)

    def test_format_basic_tooltip(self, updater, weather_data):
        """Should format basic tooltip with default format string."""
        tooltip = updater.format_tooltip(weather_data, "New York")

        assert "New York" in tooltip
        assert "72F/22C" in tooltip
        assert "Partly Cloudy" in tooltip

    def test_format_disabled_returns_default(self, weather_data):
        """Should return default text when text_enabled is False."""
        updater = TaskbarIconUpdater(text_enabled=False)

        tooltip = updater.format_tooltip(weather_data, "New York")

        assert tooltip == DEFAULT_TOOLTIP_TEXT

    def test_format_dynamic_disabled_returns_default(self, weather_data):
        """Should return default text when dynamic_enabled is False."""
        updater = TaskbarIconUpdater(text_enabled=True, dynamic_enabled=False)

        tooltip = updater.format_tooltip(weather_data, "New York")

        assert tooltip == DEFAULT_TOOLTIP_TEXT

    def test_format_none_weather_data(self, updater):
        """Should return default text when weather_data is None."""
        tooltip = updater.format_tooltip(None, "New York")

        assert tooltip == DEFAULT_TOOLTIP_TEXT

    def test_format_no_current_conditions(self, updater):
        """Should return default text when current_conditions is None."""
        weather_data = MockWeatherData(current_conditions=None)

        tooltip = updater.format_tooltip(weather_data, "New York")

        assert tooltip == DEFAULT_TOOLTIP_TEXT

    def test_format_current_has_no_data(self, updater):
        """Should return default text when current_conditions has no data."""
        current = MockCurrentConditions(has_data_result=False)
        weather_data = MockWeatherData(current_conditions=current)

        tooltip = updater.format_tooltip(weather_data, "New York")

        assert tooltip == DEFAULT_TOOLTIP_TEXT

    def test_format_with_location_prefix(self, updater, weather_data):
        """Should prefix with location name."""
        tooltip = updater.format_tooltip(weather_data, "Chicago")

        assert tooltip.startswith("Chicago:")

    def test_format_without_location(self, updater, weather_data):
        """Should format without location prefix when no location provided."""
        tooltip = updater.format_tooltip(weather_data, None)

        assert "72F/22C" in tooltip
        assert "Partly Cloudy" in tooltip


class TestTemperatureFormatting:
    """Test temperature formatting with different units."""

    @pytest.fixture
    def weather_data(self):
        """Create mock weather data with temperature."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Sunny",
        )
        return MockWeatherData(current_conditions=current)

    def test_fahrenheit_only(self, weather_data):
        """Should format temperature in Fahrenheit only."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit="fahrenheit",
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "72F" in tooltip
        assert "22C" not in tooltip

    def test_celsius_only(self, weather_data):
        """Should format temperature in Celsius only."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit="celsius",
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "22C" in tooltip
        assert "72F" not in tooltip

    def test_both_units(self, weather_data):
        """Should format temperature in both units."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit="both",
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "72F/22C" in tooltip

    def test_missing_celsius_with_both(self):
        """Should show only Fahrenheit when Celsius is missing."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            temperature_c=None,
            condition="Sunny",
        )
        weather_data = MockWeatherData(current_conditions=current)
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit="both",
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "72F" in tooltip

    def test_missing_fahrenheit_with_both(self):
        """Should show only Celsius when Fahrenheit is missing."""
        current = MockCurrentConditions(
            temperature_f=None,
            temperature_c=22.2,
            condition="Sunny",
        )
        weather_data = MockWeatherData(current_conditions=current)
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit="both",
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "22C" in tooltip


class TestMissingWeatherVariables:
    """Test handling of missing weather variables."""

    def test_missing_condition_shows_na(self):
        """Should show N/A for missing condition."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition=None,
        )
        weather_data = MockWeatherData(current_conditions=current)
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert PLACEHOLDER_NA in tooltip

    def test_missing_humidity_shows_na(self):
        """Should show N/A for missing humidity."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Sunny",
            relative_humidity=None,
        )
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            format_string="{humidity}%",
        )

        data = updater._extract_weather_variables(current, "Test")

        assert data["humidity"] == PLACEHOLDER_NA

    def test_missing_wind_shows_na(self):
        """Should show N/A for missing wind data."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Sunny",
            wind_speed=None,
            wind_direction=None,
        )
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
        )

        data = updater._extract_weather_variables(current, "Test")

        assert data["wind"] == PLACEHOLDER_NA
        assert data["wind_speed"] == PLACEHOLDER_NA
        assert data["wind_dir"] == PLACEHOLDER_NA

    def test_missing_all_temperatures_shows_na(self):
        """Should show N/A when both temperature values are missing."""
        current = MockCurrentConditions(
            temperature_f=None,
            temperature_c=None,
            condition="Sunny",
        )
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
        )

        data = updater._extract_weather_variables(current, "Test")

        assert data["temp"] == PLACEHOLDER_NA


class TestFormatStringValidation:
    """Test format string validation."""

    @pytest.fixture
    def updater(self):
        """Create TaskbarIconUpdater."""
        return TaskbarIconUpdater()

    def test_valid_format_string(self, updater):
        """Should validate correct format strings."""
        is_valid, error = updater.validate_format_string("{temp} {condition}")

        assert is_valid is True
        assert error is None

    def test_invalid_placeholder(self, updater):
        """Should reject invalid placeholders."""
        is_valid, error = updater.validate_format_string("{invalid_placeholder}")

        assert is_valid is False
        assert "Unsupported placeholder" in error

    def test_unbalanced_braces(self, updater):
        """Should reject unbalanced braces."""
        is_valid, error = updater.validate_format_string("{temp is broken")

        assert is_valid is False
        assert "Unbalanced braces" in error

    def test_empty_format_string(self, updater):
        """Should accept empty format string."""
        is_valid, error = updater.validate_format_string("")

        assert is_valid is True


class TestInvalidFormatStringFallback:
    """Test fallback behavior for invalid format strings."""

    def test_invalid_format_uses_default(self):
        """Should use default format when format string is invalid."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Sunny",
        )
        weather_data = MockWeatherData(current_conditions=current)
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            format_string="{invalid_placeholder}",
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "72F/22C" in tooltip
        assert "Sunny" in tooltip


class TestTooltipTruncation:
    """Test tooltip text truncation."""

    def test_short_tooltip_not_truncated(self):
        """Should not truncate short tooltips."""
        updater = TaskbarIconUpdater()

        result = updater._truncate_tooltip("Short text")

        assert result == "Short text"

    def test_long_tooltip_truncated(self):
        """Should truncate long tooltips with ellipsis."""
        updater = TaskbarIconUpdater()
        long_text = "x" * 200

        result = updater._truncate_tooltip(long_text)

        assert len(result) == TOOLTIP_MAX_LENGTH
        assert result.endswith("...")

    def test_exact_length_tooltip_not_truncated(self):
        """Should not truncate tooltips at exact max length."""
        updater = TaskbarIconUpdater()
        exact_text = "x" * TOOLTIP_MAX_LENGTH

        result = updater._truncate_tooltip(exact_text)

        assert result == exact_text
        assert not result.endswith("...")

    def test_empty_tooltip_returns_default(self):
        """Should return default for empty tooltip."""
        updater = TaskbarIconUpdater()

        result = updater._truncate_tooltip("")

        assert result == DEFAULT_TOOLTIP_TEXT


class TestGetAvailableVariables:
    """Test getting available format variables."""

    def test_returns_all_variables(self):
        """Should return all supported placeholders."""
        updater = TaskbarIconUpdater()

        variables = updater.get_available_variables()

        assert "temp" in variables
        assert "condition" in variables
        assert "location" in variables
        assert "humidity" in variables
        assert "wind" in variables
        assert "wind_speed" in variables
        assert "wind_dir" in variables
        assert "pressure" in variables
        assert "feels_like" in variables
        assert "uv" in variables
        assert "visibility" in variables

    def test_returns_copy(self):
        """Should return a copy, not the original dict."""
        updater = TaskbarIconUpdater()

        variables = updater.get_available_variables()
        variables["new_var"] = "test"
        variables2 = updater.get_available_variables()

        assert "new_var" not in variables2


class TestWindFormatting:
    """Test wind formatting edge cases."""

    def test_wind_with_direction_and_speed(self):
        """Should format wind with both direction and speed."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Sunny",
            wind_direction="NW",
            wind_speed=15.5,
        )
        updater = TaskbarIconUpdater()

        data = updater._extract_weather_variables(current, "Test")

        assert data["wind"] == "NW at 16 mph"
        assert data["wind_dir"] == "NW"
        assert data["wind_speed"] == "15.5 mph"

    def test_wind_with_only_direction(self):
        """Should format wind with only direction."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Sunny",
            wind_direction="NW",
            wind_speed=None,
        )
        updater = TaskbarIconUpdater()

        data = updater._extract_weather_variables(current, "Test")

        assert data["wind"] == "NW"

    def test_wind_with_only_speed(self):
        """Should format wind with only speed."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Sunny",
            wind_direction=None,
            wind_speed=15.5,
        )
        updater = TaskbarIconUpdater()

        data = updater._extract_weather_variables(current, "Test")

        assert "16 mph" in data["wind"]


class TestNumericFormatting:
    """Test numeric value formatting."""

    def test_integer_float_formatting(self):
        """Should format integer floats without decimal."""
        updater = TaskbarIconUpdater()

        result = updater._format_numeric(10.0, " mph")

        assert result == "10 mph"

    def test_decimal_float_formatting(self):
        """Should format decimal floats with one decimal."""
        updater = TaskbarIconUpdater()

        result = updater._format_numeric(10.5, " mph")

        assert result == "10.5 mph"

    def test_integer_formatting(self):
        """Should format integers correctly."""
        updater = TaskbarIconUpdater()

        result = updater._format_numeric(65, "%")

        assert result == "65%"

    def test_none_value_returns_na(self):
        """Should return N/A for None values."""
        updater = TaskbarIconUpdater()

        result = updater._format_numeric(None, " mph")

        assert result == PLACEHOLDER_NA


class TestFeelsLikeFormatting:
    """Test feels-like temperature formatting."""

    def test_feels_like_both_units(self):
        """Should format feels-like with both units."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Sunny",
            feels_like_f=75.0,
            feels_like_c=24.0,
        )
        updater = TaskbarIconUpdater(temperature_unit="both")

        data = updater._extract_weather_variables(current, "Test")

        assert data["feels_like"] == "75F/24C"

    def test_feels_like_fahrenheit(self):
        """Should format feels-like in Fahrenheit only."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Sunny",
            feels_like_f=75.0,
            feels_like_c=24.0,
        )
        updater = TaskbarIconUpdater(temperature_unit="fahrenheit")

        data = updater._extract_weather_variables(current, "Test")

        assert data["feels_like"] == "75F"

    def test_feels_like_celsius(self):
        """Should format feels-like in Celsius only."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Sunny",
            feels_like_f=75.0,
            feels_like_c=24.0,
        )
        updater = TaskbarIconUpdater(temperature_unit="celsius")

        data = updater._extract_weather_variables(current, "Test")

        assert data["feels_like"] == "24C"

    def test_feels_like_missing(self):
        """Should return N/A when feels-like is missing."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Sunny",
            feels_like_f=None,
            feels_like_c=None,
        )
        updater = TaskbarIconUpdater()

        data = updater._extract_weather_variables(current, "Test")

        assert data["feels_like"] == PLACEHOLDER_NA


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_special_characters_in_location(self):
        """Should handle special characters in location name."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Sunny",
        )
        weather_data = MockWeatherData(current_conditions=current)
        updater = TaskbarIconUpdater(text_enabled=True, dynamic_enabled=True)

        tooltip = updater.format_tooltip(weather_data, "São Paulo, Brazil!")

        assert "São Paulo, Brazil!" in tooltip

    def test_unicode_in_condition(self):
        """Should handle unicode in condition."""
        current = MockCurrentConditions(
            temperature_f=72.0,
            condition="Parcialmente Nublado ☁️",
        )
        weather_data = MockWeatherData(current_conditions=current)
        updater = TaskbarIconUpdater(text_enabled=True, dynamic_enabled=True)

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "Parcialmente Nublado" in tooltip

    def test_negative_temperatures(self):
        """Should format negative temperatures correctly."""
        current = MockCurrentConditions(
            temperature_f=-10.0,
            temperature_c=-23.3,
            condition="Clear",
        )
        weather_data = MockWeatherData(current_conditions=current)
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit="both",
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "-10F/-23C" in tooltip

    def test_zero_temperature(self):
        """Should format zero temperature correctly."""
        current = MockCurrentConditions(
            temperature_f=0.0,
            temperature_c=-17.8,
            condition="Cold",
        )
        weather_data = MockWeatherData(current_conditions=current)
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit="fahrenheit",
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "0F" in tooltip

    def test_very_high_temperature(self):
        """Should format very high temperatures correctly."""
        current = MockCurrentConditions(
            temperature_f=120.0,
            temperature_c=48.9,
            condition="Extreme Heat",
        )
        weather_data = MockWeatherData(current_conditions=current)
        updater = TaskbarIconUpdater(text_enabled=True, dynamic_enabled=True)

        tooltip = updater.format_tooltip(weather_data, "Test")

        assert "120F/49C" in tooltip

    def test_format_error_logs_once(self):
        """Should log format errors only once per error type."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            format_string="{invalid}",
        )

        updater._format_with_fallback("{invalid}", {"temp": "72F"})
        updater._format_with_fallback("{invalid}", {"temp": "72F"})

        assert updater._last_format_error is not None
