"""Tests for temperature utility functions."""

from accessiweather.utils.temperature_utils import (
    TemperatureUnit,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    format_temperature,
    get_temperature_values,
)


class TestTemperatureUtils:
    """Test temperature utility functions."""

    def test_celsius_to_fahrenheit(self):
        """Test celsius_to_fahrenheit function."""
        assert celsius_to_fahrenheit(0) == 32
        assert celsius_to_fahrenheit(100) == 212
        assert celsius_to_fahrenheit(-40) == -40
        assert celsius_to_fahrenheit(20) == 68

    def test_fahrenheit_to_celsius(self):
        """Test fahrenheit_to_celsius function."""
        assert fahrenheit_to_celsius(32) == 0
        assert fahrenheit_to_celsius(212) == 100
        assert fahrenheit_to_celsius(-40) == -40
        assert fahrenheit_to_celsius(68) == 20

    def test_format_temperature_fahrenheit(self):
        """Test format_temperature function with Fahrenheit preference."""
        # Test with Fahrenheit preference
        assert format_temperature(32, TemperatureUnit.FAHRENHEIT) == "32.0°F"
        assert format_temperature(68.5, TemperatureUnit.FAHRENHEIT) == "68.5°F"
        assert format_temperature(None, TemperatureUnit.FAHRENHEIT) == "N/A"

        # Test with Fahrenheit preference but providing Celsius value
        assert format_temperature(None, TemperatureUnit.FAHRENHEIT, temperature_c=0) == "32.0°F"
        assert format_temperature(None, TemperatureUnit.FAHRENHEIT, temperature_c=20) == "68.0°F"

    def test_format_temperature_celsius(self):
        """Test format_temperature function with Celsius preference."""
        # Test with Celsius preference
        assert format_temperature(32, TemperatureUnit.CELSIUS) == "0.0°C"
        assert format_temperature(68, TemperatureUnit.CELSIUS) == "20.0°C"
        assert format_temperature(None, TemperatureUnit.CELSIUS) == "N/A"

        # Test with Celsius preference but providing Celsius value
        assert format_temperature(None, TemperatureUnit.CELSIUS, temperature_c=0) == "0.0°C"
        assert format_temperature(None, TemperatureUnit.CELSIUS, temperature_c=20) == "20.0°C"

    def test_format_temperature_both(self):
        """Test format_temperature function with Both preference."""
        # Test with Both preference
        assert format_temperature(32, TemperatureUnit.BOTH) == "32.0°F (0.0°C)"
        assert format_temperature(68, TemperatureUnit.BOTH) == "68.0°F (20.0°C)"
        assert format_temperature(None, TemperatureUnit.BOTH) == "N/A"

        # Test with Both preference but providing Celsius value
        assert format_temperature(None, TemperatureUnit.BOTH, temperature_c=0) == "32.0°F (0.0°C)"
        assert format_temperature(None, TemperatureUnit.BOTH, temperature_c=20) == "68.0°F (20.0°C)"

    def test_format_temperature_precision(self):
        """Test format_temperature function with different precision."""
        assert format_temperature(68.5, TemperatureUnit.FAHRENHEIT, precision=0) == "68°F"
        assert format_temperature(68.5, TemperatureUnit.FAHRENHEIT, precision=2) == "68.50°F"
        assert format_temperature(68.5, TemperatureUnit.BOTH, precision=2) == "68.50°F (20.28°C)"

    def test_get_temperature_values(self):
        """Test get_temperature_values function."""
        # Test with Fahrenheit value
        f, c = get_temperature_values(32)
        assert f == 32
        assert c == 0

        # Test with Celsius value
        f, c = get_temperature_values(None, 0)
        assert f == 32
        assert c == 0

        # Test with both values
        f, c = get_temperature_values(32, 0)
        assert f == 32
        assert c == 0

        # Test with no values
        f, c = get_temperature_values(None, None)
        assert f is None
        assert c is None
