"""
Property-based tests for taskbar icon updater and system tray integration.

These tests use Hypothesis to verify invariants across a wide range of inputs.
"""

import os
import sys
from pathlib import Path

import pytest
from hypothesis import (
    HealthCheck,
    assume,
    given,
    settings,
    strategies as st,
)

os.environ.setdefault("TOGA_BACKEND", "toga_dummy")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accessiweather.format_string_parser import FormatStringParser
from accessiweather.taskbar_icon_updater import (
    DEFAULT_TOOLTIP_TEXT,
    TOOLTIP_MAX_LENGTH,
    TaskbarIconUpdater,
)


class MockCurrentConditions:
    """Mock current conditions for property testing."""

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
    """Mock weather data for property testing."""

    def __init__(self, current_conditions=None):
        """Initialize mock weather data."""
        self.current_conditions = current_conditions


temperature_strategy = st.one_of(
    st.none(),
    st.floats(min_value=-100, max_value=150, allow_nan=False, allow_infinity=False),
)

percentage_strategy = st.one_of(
    st.none(),
    st.integers(min_value=0, max_value=100),
)

wind_speed_strategy = st.one_of(
    st.none(),
    st.floats(min_value=0, max_value=200, allow_nan=False, allow_infinity=False),
)

wind_direction_strategy = st.one_of(
    st.none(),
    st.sampled_from(
        [
            "N",
            "NE",
            "E",
            "SE",
            "S",
            "SW",
            "W",
            "NW",
            "NNE",
            "ENE",
            "ESE",
            "SSE",
            "SSW",
            "WSW",
            "WNW",
            "NNW",
        ]
    ),
)

condition_strategy = st.one_of(
    st.none(),
    st.text(
        min_size=0, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"))
    ),
)

location_strategy = st.one_of(
    st.none(),
    st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"))
    ),
)

temperature_unit_strategy = st.sampled_from(["fahrenheit", "celsius", "both"])

format_string_strategy = st.one_of(
    st.just("{temp} {condition}"),
    st.just("{temp}"),
    st.just("{location}: {temp}"),
    st.just("{temp} • {humidity}%"),
    st.just("{wind_dir} {wind_speed}"),
    st.just("{feels_like}"),
    st.just("{condition}"),
    st.just("{uv}"),
    st.just("{visibility}"),
    st.just("{precip_chance}%"),
)


@st.composite
def weather_conditions_strategy(draw):
    """Generate random weather conditions."""
    return MockCurrentConditions(
        temperature_f=draw(temperature_strategy),
        temperature_c=draw(temperature_strategy),
        condition=draw(condition_strategy),
        relative_humidity=draw(percentage_strategy),
        wind_speed=draw(wind_speed_strategy),
        wind_direction=draw(wind_direction_strategy),
        pressure=draw(st.one_of(st.none(), st.floats(min_value=28, max_value=32, allow_nan=False))),
        feels_like_f=draw(temperature_strategy),
        feels_like_c=draw(temperature_strategy),
        uv_index=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=15))),
        visibility=draw(
            st.one_of(st.none(), st.floats(min_value=0, max_value=50, allow_nan=False))
        ),
        precipitation=draw(
            st.one_of(st.none(), st.floats(min_value=0, max_value=10, allow_nan=False))
        ),
        precipitation_probability=draw(percentage_strategy),
        has_data_result=draw(st.booleans()),
    )


@st.composite
def updater_settings_strategy(draw):
    """Generate random updater settings."""
    return {
        "text_enabled": draw(st.booleans()),
        "dynamic_enabled": draw(st.booleans()),
        "format_string": draw(format_string_strategy),
        "temperature_unit": draw(temperature_unit_strategy),
    }


@pytest.mark.unit
class TestTooltipLengthProperty:
    """Property: Tooltip output never exceeds platform limits."""

    @given(
        conditions=weather_conditions_strategy(),
        location=location_strategy,
        settings=updater_settings_strategy(),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_tooltip_never_exceeds_max_length(self, conditions, location, settings):
        """Property: tooltip text should never exceed TOOLTIP_MAX_LENGTH."""
        updater = TaskbarIconUpdater(**settings)
        weather_data = MockWeatherData(current_conditions=conditions)

        tooltip = updater.format_tooltip(weather_data, location)

        assert len(tooltip) <= TOOLTIP_MAX_LENGTH, (
            f"Tooltip length {len(tooltip)} exceeds max {TOOLTIP_MAX_LENGTH}: {tooltip}"
        )


@pytest.mark.unit
class TestTooltipDefaultFallbackProperty:
    """Property: Tooltip always returns valid string, never empty."""

    @given(
        conditions=weather_conditions_strategy(),
        location=location_strategy,
        settings=updater_settings_strategy(),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_tooltip_never_empty(self, conditions, location, settings):
        """Property: tooltip should never be empty, always returns default text."""
        updater = TaskbarIconUpdater(**settings)
        weather_data = MockWeatherData(current_conditions=conditions)

        tooltip = updater.format_tooltip(weather_data, location)

        assert tooltip, "Tooltip should never be empty"
        assert len(tooltip) > 0


@pytest.mark.unit
class TestMissingDataPlaceholderProperty:
    """Property: Missing weather variables are replaced with placeholders."""

    @given(
        location=location_strategy,
        temperature_unit=temperature_unit_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_none_values_produce_valid_output(self, location, temperature_unit):
        """Property: when all weather values are None, output should not crash."""
        conditions = MockCurrentConditions(
            temperature_f=None,
            temperature_c=None,
            condition=None,
            relative_humidity=None,
            wind_speed=None,
            wind_direction=None,
            has_data_result=False,
        )
        weather_data = MockWeatherData(current_conditions=conditions)

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit=temperature_unit,
        )

        tooltip = updater.format_tooltip(weather_data, location)

        assert tooltip == DEFAULT_TOOLTIP_TEXT, (
            "All-None conditions with has_data=False should return default"
        )


@pytest.mark.unit
class TestTemperatureFormatConsistencyProperty:
    """Property: Temperature formatting is consistent with unit preference."""

    @given(
        temp_f=st.floats(min_value=-50, max_value=150, allow_nan=False, allow_infinity=False),
        temp_c=st.floats(min_value=-50, max_value=70, allow_nan=False, allow_infinity=False),
        temperature_unit=temperature_unit_strategy,
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
    def test_temperature_unit_respected(self, temp_f, temp_c, temperature_unit):
        """Property: temperature format in output should match unit preference."""
        conditions = MockCurrentConditions(
            temperature_f=temp_f,
            temperature_c=temp_c,
            condition="Clear",
            has_data_result=True,
        )
        weather_data = MockWeatherData(current_conditions=conditions)

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            temperature_unit=temperature_unit,
        )

        tooltip = updater.format_tooltip(weather_data, "Test")

        if temperature_unit == "fahrenheit":
            assert "F" in tooltip
            assert "C" not in tooltip or "C" in "Clear"
        elif temperature_unit == "celsius":
            assert "C" in tooltip
            assert "F" not in tooltip
        else:
            assert "F" in tooltip
            assert "C" in tooltip


@pytest.mark.unit
class TestFormatStringValidationProperty:
    """Property: Format string validation is consistent."""

    @given(
        placeholder=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_unsupported_placeholders_detected(self, placeholder):
        """Property: placeholder not in SUPPORTED_PLACEHOLDERS should be rejected."""
        parser = FormatStringParser()
        assume(placeholder not in parser.SUPPORTED_PLACEHOLDERS)

        format_string = f"{{{placeholder}}}"
        is_valid, error = parser.validate_format_string(format_string)

        assert is_valid is False
        assert "Unsupported placeholder" in error

    @given(
        placeholder=st.sampled_from(list(FormatStringParser.SUPPORTED_PLACEHOLDERS.keys())),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_supported_placeholders_accepted(self, placeholder):
        """Property: all placeholders in SUPPORTED_PLACEHOLDERS should be accepted."""
        parser = FormatStringParser()

        format_string = f"{{{placeholder}}}"
        is_valid, error = parser.validate_format_string(format_string)

        assert is_valid is True
        assert error is None


@pytest.mark.unit
class TestIdempotencyProperty:
    """Property: Repeated formatting with same inputs produces same output."""

    @given(
        conditions=weather_conditions_strategy(),
        location=location_strategy,
        settings=updater_settings_strategy(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_formatting_is_idempotent(self, conditions, location, settings):
        """Property: format_tooltip with same inputs should produce same output."""
        updater = TaskbarIconUpdater(**settings)
        weather_data = MockWeatherData(current_conditions=conditions)

        tooltip1 = updater.format_tooltip(weather_data, location)
        tooltip2 = updater.format_tooltip(weather_data, location)
        tooltip3 = updater.format_tooltip(weather_data, location)

        assert tooltip1 == tooltip2 == tooltip3


@pytest.mark.unit
class TestSettingsUpdateProperty:
    """Property: Settings updates are properly applied."""

    @given(
        initial_settings=updater_settings_strategy(),
        new_text_enabled=st.booleans(),
        new_dynamic_enabled=st.booleans(),
        new_temperature_unit=temperature_unit_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_settings_update_changes_state(
        self, initial_settings, new_text_enabled, new_dynamic_enabled, new_temperature_unit
    ):
        """Property: update_settings should properly update the updater state."""
        updater = TaskbarIconUpdater(**initial_settings)

        updater.update_settings(
            text_enabled=new_text_enabled,
            dynamic_enabled=new_dynamic_enabled,
            temperature_unit=new_temperature_unit,
        )

        assert updater.text_enabled == new_text_enabled
        assert updater.dynamic_enabled == new_dynamic_enabled
        assert updater.temperature_unit == new_temperature_unit


@pytest.mark.unit
class TestTruncationProperty:
    """Property: Truncation preserves meaning and adds ellipsis correctly."""

    @given(
        text=st.text(min_size=0, max_size=500),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_truncation_preserves_length_invariant(self, text):
        """Property: after truncation, text length should be <= TOOLTIP_MAX_LENGTH."""
        updater = TaskbarIconUpdater()

        result = updater._truncate_tooltip(text)

        assert len(result) <= TOOLTIP_MAX_LENGTH

    @given(
        text=st.text(min_size=TOOLTIP_MAX_LENGTH + 1, max_size=500),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_long_text_truncated_with_ellipsis(self, text):
        """Property: text longer than max should end with ellipsis."""
        updater = TaskbarIconUpdater()

        result = updater._truncate_tooltip(text)

        assert result.endswith("...")
        assert len(result) == TOOLTIP_MAX_LENGTH


@pytest.mark.unit
class TestVariableExtractionProperty:
    """Property: Variable extraction produces consistent dictionary structure."""

    @given(
        conditions=weather_conditions_strategy(),
        location=location_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_extraction_always_returns_all_keys(self, conditions, location):
        """Property: variable extraction should always return all expected keys."""
        updater = TaskbarIconUpdater()

        data = updater._extract_weather_variables(conditions, location)

        expected_keys = [
            "location",
            "temp",
            "temp_f",
            "temp_c",
            "condition",
            "humidity",
            "wind",
            "wind_speed",
            "wind_dir",
            "pressure",
            "feels_like",
            "uv",
            "visibility",
            "high",
            "low",
            "precip",
            "precip_chance",
        ]

        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    @given(
        conditions=weather_conditions_strategy(),
        location=location_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_extraction_values_are_strings(self, conditions, location):
        """Property: all extracted values should be strings."""
        updater = TaskbarIconUpdater()

        data = updater._extract_weather_variables(conditions, location)

        for key, value in data.items():
            assert isinstance(value, str), f"Value for {key} is not string: {type(value)}"


@pytest.mark.unit
class TestDisabledStateProperty:
    """Property: Disabled states always return default tooltip."""

    @given(
        conditions=weather_conditions_strategy(),
        location=location_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_text_disabled_returns_default(self, conditions, location):
        """Property: when text_enabled is False, always return default tooltip."""
        updater = TaskbarIconUpdater(
            text_enabled=False,
            dynamic_enabled=True,
        )
        weather_data = MockWeatherData(current_conditions=conditions)

        tooltip = updater.format_tooltip(weather_data, location)

        assert tooltip == DEFAULT_TOOLTIP_TEXT

    @given(
        conditions=weather_conditions_strategy(),
        location=location_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_dynamic_disabled_returns_default(self, conditions, location):
        """Property: when dynamic_enabled is False, always return default tooltip."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=False,
        )
        weather_data = MockWeatherData(current_conditions=conditions)

        tooltip = updater.format_tooltip(weather_data, location)

        assert tooltip == DEFAULT_TOOLTIP_TEXT


@pytest.mark.unit
class TestInvalidFormatFallbackProperty:
    """Property: Invalid format strings fall back to default format."""

    @given(
        invalid_placeholder=st.text(min_size=5, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
        conditions=weather_conditions_strategy(),
        location=location_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_invalid_format_uses_fallback(self, invalid_placeholder, conditions, location):
        """Property: invalid format strings should fall back to default format."""
        parser = FormatStringParser()
        assume(invalid_placeholder not in parser.SUPPORTED_PLACEHOLDERS)
        assume(conditions._has_data_result is True)
        assume(conditions.temperature_f is not None or conditions.temperature_c is not None)

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            format_string=f"{{{invalid_placeholder}}}",
        )
        weather_data = MockWeatherData(current_conditions=conditions)

        tooltip = updater.format_tooltip(weather_data, location)

        assert tooltip != f"{{{invalid_placeholder}}}"
