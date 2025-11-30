"""Property-based tests for temperature utilities using Hypothesis."""

from __future__ import annotations

import math

import pytest
from hypothesis import (
    given,
    settings,
    strategies as st,
)

from accessiweather.utils.temperature_utils import (
    TemperatureUnit,
    calculate_dewpoint,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    format_temperature,
)

# Strategy for reasonable temperature values
reasonable_temps = st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False)

# Strategy for valid humidity values (0-100, excluding 0 which returns None)
valid_humidity = st.floats(min_value=0.1, max_value=100, allow_nan=False, allow_infinity=False)

# Strategy for extreme but finite temperatures
extreme_temps = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)


@pytest.mark.unit
class TestTemperatureConversionProperties:
    """Property tests for temperature conversion functions."""

    @given(temp=reasonable_temps)
    @settings(max_examples=100)
    def test_fahrenheit_roundtrip(self, temp: float) -> None:
        """celsius_to_fahrenheit(fahrenheit_to_celsius(x)) ≈ x."""
        celsius = fahrenheit_to_celsius(temp)
        back_to_fahrenheit = celsius_to_fahrenheit(celsius)
        assert back_to_fahrenheit == pytest.approx(temp, rel=1e-9)

    @given(temp=reasonable_temps)
    @settings(max_examples=100)
    def test_celsius_roundtrip(self, temp: float) -> None:
        """fahrenheit_to_celsius(celsius_to_fahrenheit(x)) ≈ x."""
        fahrenheit = celsius_to_fahrenheit(temp)
        back_to_celsius = fahrenheit_to_celsius(fahrenheit)
        assert back_to_celsius == pytest.approx(temp, rel=1e-9)

    @given(temp=extreme_temps)
    @settings(max_examples=100)
    def test_extreme_temps_no_overflow(self, temp: float) -> None:
        """Extreme temperatures don't cause overflow."""
        fahrenheit = celsius_to_fahrenheit(temp)
        celsius = fahrenheit_to_celsius(temp)
        assert math.isfinite(fahrenheit)
        assert math.isfinite(celsius)

    @given(temp=st.floats(allow_nan=True, allow_infinity=True))
    @settings(max_examples=50)
    def test_nan_and_infinity_propagation(self, temp: float) -> None:
        """NaN and infinity values propagate through conversions."""
        fahrenheit = celsius_to_fahrenheit(temp)
        celsius = fahrenheit_to_celsius(temp)

        if math.isnan(temp):
            assert math.isnan(fahrenheit)
            assert math.isnan(celsius)
        elif math.isinf(temp):
            assert math.isinf(fahrenheit)
            assert math.isinf(celsius)


@pytest.mark.unit
class TestDewpointProperties:
    """Property tests for dewpoint calculation."""

    @given(temp=reasonable_temps, humidity=valid_humidity)
    @settings(max_examples=100)
    def test_dewpoint_never_exceeds_temperature(self, temp: float, humidity: float) -> None:
        """Dewpoint should always be less than or equal to temperature."""
        dewpoint = calculate_dewpoint(temp, humidity, unit=TemperatureUnit.FAHRENHEIT)
        assert dewpoint is not None
        assert dewpoint <= temp + 0.01  # Small tolerance for floating point

    @given(temp=reasonable_temps, humidity=valid_humidity)
    @settings(max_examples=100)
    def test_dewpoint_celsius_never_exceeds_temperature(self, temp: float, humidity: float) -> None:
        """Dewpoint in Celsius should always be less than or equal to temperature."""
        dewpoint = calculate_dewpoint(temp, humidity, unit=TemperatureUnit.CELSIUS)
        assert dewpoint is not None
        assert dewpoint <= temp + 0.01

    @given(temp=reasonable_temps)
    @settings(max_examples=100)
    def test_dewpoint_at_100_percent_humidity_equals_temp(self, temp: float) -> None:
        """At 100% humidity, dewpoint should approximately equal temperature."""
        dewpoint_f = calculate_dewpoint(temp, 100.0, unit=TemperatureUnit.FAHRENHEIT)
        assert dewpoint_f is not None
        assert dewpoint_f == pytest.approx(temp, rel=0.01, abs=0.5)

        dewpoint_c = calculate_dewpoint(temp, 100.0, unit=TemperatureUnit.CELSIUS)
        assert dewpoint_c is not None
        assert dewpoint_c == pytest.approx(temp, rel=0.01, abs=0.5)

    @given(temp=reasonable_temps, humidity=valid_humidity)
    @settings(max_examples=100)
    def test_dewpoint_returns_finite_value(self, temp: float, humidity: float) -> None:
        """Dewpoint calculation always returns a finite value for valid inputs."""
        dewpoint = calculate_dewpoint(temp, humidity, unit=TemperatureUnit.FAHRENHEIT)
        assert dewpoint is not None
        assert math.isfinite(dewpoint)

    @given(temp=reasonable_temps)
    @settings(max_examples=50)
    def test_dewpoint_with_zero_humidity_returns_none(self, temp: float) -> None:
        """Zero humidity should return None (dewpoint would be -infinity)."""
        dewpoint = calculate_dewpoint(temp, 0.0, unit=TemperatureUnit.FAHRENHEIT)
        assert dewpoint is None

    @given(temp=reasonable_temps)
    @settings(max_examples=50)
    def test_dewpoint_with_negative_humidity_returns_none(self, temp: float) -> None:
        """Negative humidity should return None."""
        dewpoint = calculate_dewpoint(temp, -10.0, unit=TemperatureUnit.FAHRENHEIT)
        assert dewpoint is None


@pytest.mark.unit
class TestFormatTemperatureProperties:
    """Property tests for temperature formatting."""

    @given(temp=reasonable_temps)
    @settings(max_examples=100)
    def test_format_contains_temperature_value_fahrenheit(self, temp: float) -> None:
        """Formatted output should contain the temperature value for Fahrenheit."""
        result = format_temperature(temp, unit=TemperatureUnit.FAHRENHEIT)
        assert result != "N/A"
        assert "°F" in result
        if temp < 0:
            assert "-" in result

    @given(temp=reasonable_temps)
    @settings(max_examples=100)
    def test_format_contains_temperature_value_celsius(self, temp: float) -> None:
        """Formatted output should contain the temperature value for Celsius."""
        result = format_temperature(temp, unit=TemperatureUnit.CELSIUS)
        assert result != "N/A"
        assert "°C" in result

    @given(temp=reasonable_temps)
    @settings(max_examples=100)
    def test_format_both_contains_both_units(self, temp: float) -> None:
        """BOTH unit format should contain both F and C."""
        result = format_temperature(temp, unit=TemperatureUnit.BOTH)
        assert "°F" in result
        assert "°C" in result
        assert "(" in result and ")" in result

    @given(temp=st.integers(min_value=-100, max_value=100))
    @settings(max_examples=50)
    def test_smart_precision_for_whole_numbers(self, temp: int) -> None:
        """Whole numbers should have no decimal places with smart_precision."""
        result = format_temperature(
            float(temp), unit=TemperatureUnit.FAHRENHEIT, smart_precision=True
        )
        # Should not have decimal point followed by non-zero digits
        assert result == f"{temp}°F"

    @given(temp=extreme_temps)
    @settings(max_examples=50)
    def test_format_handles_extreme_values(self, temp: float) -> None:
        """Formatting should handle extreme temperature values without error."""
        result = format_temperature(temp, unit=TemperatureUnit.FAHRENHEIT)
        assert isinstance(result, str)
        assert len(result) > 0
        assert result != "N/A"

    def test_format_none_returns_na(self) -> None:
        """None temperature should return N/A."""
        result = format_temperature(None, unit=TemperatureUnit.FAHRENHEIT)
        assert result == "N/A"


@pytest.mark.unit
class TestConsistencyProperties:
    """Cross-function consistency properties."""

    @given(temp_f=reasonable_temps)
    @settings(max_examples=100)
    def test_dewpoint_unit_consistency(self, temp_f: float) -> None:
        """Dewpoint in F converted to C should match dewpoint calculated in C."""
        humidity = 50.0
        temp_c = fahrenheit_to_celsius(temp_f)

        dewpoint_f = calculate_dewpoint(temp_f, humidity, unit=TemperatureUnit.FAHRENHEIT)
        dewpoint_c = calculate_dewpoint(temp_c, humidity, unit=TemperatureUnit.CELSIUS)

        assert dewpoint_f is not None
        assert dewpoint_c is not None

        # Convert dewpoint_f to Celsius and compare
        dewpoint_f_as_c = fahrenheit_to_celsius(dewpoint_f)
        assert dewpoint_f_as_c == pytest.approx(dewpoint_c, rel=1e-6)

    @given(temp=reasonable_temps, humidity=valid_humidity)
    @settings(max_examples=100)
    def test_higher_humidity_means_higher_dewpoint(self, temp: float, humidity: float) -> None:
        """Higher humidity should result in higher dewpoint (for same temperature)."""
        if humidity <= 1.0:
            return  # Skip if we can't have a lower humidity

        low_humidity = humidity / 2
        high_humidity = humidity

        dewpoint_low = calculate_dewpoint(temp, low_humidity, unit=TemperatureUnit.FAHRENHEIT)
        dewpoint_high = calculate_dewpoint(temp, high_humidity, unit=TemperatureUnit.FAHRENHEIT)

        assert dewpoint_low is not None
        assert dewpoint_high is not None
        assert dewpoint_high >= dewpoint_low - 0.01  # Small tolerance
