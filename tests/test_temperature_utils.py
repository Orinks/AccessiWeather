"""Tests for temperature utility functions."""

import pytest

from accessiweather.utils.temperature_utils import (
    TemperatureUnit,
    calculate_dewpoint,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    format_temperature,
    get_temperature_values,
)


pytestmark = pytest.mark.unit


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
        # Test with Fahrenheit preference - smart precision removes decimals for whole numbers
        assert format_temperature(32, TemperatureUnit.FAHRENHEIT) == "32°F"
        assert format_temperature(68.5, TemperatureUnit.FAHRENHEIT) == "68.5°F"
        assert format_temperature(None, TemperatureUnit.FAHRENHEIT) == "N/A"

        # Test with Fahrenheit preference but providing Celsius value
        assert format_temperature(None, TemperatureUnit.FAHRENHEIT, temperature_c=0) == "32°F"
        assert format_temperature(None, TemperatureUnit.FAHRENHEIT, temperature_c=20) == "68°F"

    def test_format_temperature_celsius(self):
        """Test format_temperature function with Celsius preference."""
        # Test with Celsius preference - smart precision removes decimals for whole numbers
        assert format_temperature(32, TemperatureUnit.CELSIUS) == "0°C"
        assert format_temperature(68, TemperatureUnit.CELSIUS) == "20°C"
        assert format_temperature(None, TemperatureUnit.CELSIUS) == "N/A"

        # Test with Celsius preference but providing Celsius value
        assert format_temperature(None, TemperatureUnit.CELSIUS, temperature_c=0) == "0°C"
        assert format_temperature(None, TemperatureUnit.CELSIUS, temperature_c=20) == "20°C"

    def test_format_temperature_both(self):
        """Test format_temperature function with Both preference."""
        # Test with Both preference - smart precision removes decimals for whole numbers
        assert format_temperature(32, TemperatureUnit.BOTH) == "32°F (0°C)"
        assert format_temperature(68, TemperatureUnit.BOTH) == "68°F (20°C)"
        assert format_temperature(None, TemperatureUnit.BOTH) == "N/A"

        # Test with Both preference but providing Celsius value
        assert format_temperature(None, TemperatureUnit.BOTH, temperature_c=0) == "32°F (0°C)"
        assert format_temperature(None, TemperatureUnit.BOTH, temperature_c=20) == "68°F (20°C)"

    def test_format_temperature_precision(self):
        """Test format_temperature function with different precision."""
        assert format_temperature(68.5, TemperatureUnit.FAHRENHEIT, precision=0) == "68°F"
        assert format_temperature(68.5, TemperatureUnit.FAHRENHEIT, precision=2) == "68.50°F"
        assert format_temperature(68.5, TemperatureUnit.BOTH, precision=2) == "68.50°F (20.28°C)"

    def test_format_temperature_smart_precision(self):
        """Test format_temperature function with smart precision."""
        # Smart precision should remove decimals for whole numbers
        assert format_temperature(70.0, TemperatureUnit.FAHRENHEIT, smart_precision=True) == "70°F"
        assert (
            format_temperature(70.5, TemperatureUnit.FAHRENHEIT, smart_precision=True) == "70.5°F"
        )
        # 70°F = 21.11111°C, which with precision=1 becomes 21.1°C (not a whole number)
        assert (
            format_temperature(70.0, TemperatureUnit.BOTH, smart_precision=True) == "70°F (21.1°C)"
        )

        # Disabled smart precision should keep decimals
        assert (
            format_temperature(70.0, TemperatureUnit.FAHRENHEIT, smart_precision=False) == "70.0°F"
        )
        assert (
            format_temperature(70.5, TemperatureUnit.FAHRENHEIT, smart_precision=False) == "70.5°F"
        )

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

    def test_calculate_dewpoint_fahrenheit(self):
        """Dewpoint calculation returns Fahrenheit when requested."""
        dewpoint = calculate_dewpoint(77.0, 65.0, unit=TemperatureUnit.FAHRENHEIT)
        assert dewpoint is not None
        assert dewpoint == pytest.approx(64.31, rel=1e-3)

    def test_calculate_dewpoint_celsius(self):
        """Dewpoint calculation returns Celsius when requested."""
        dewpoint = calculate_dewpoint(25.0, 65.0, unit=TemperatureUnit.CELSIUS)
        assert dewpoint is not None
        assert dewpoint == pytest.approx(17.95, rel=1e-3)

    def test_calculate_dewpoint_invalid_inputs(self):
        """Dewpoint calculation handles humidity edge cases gracefully."""
        assert calculate_dewpoint(None, 65.0) is None
        assert calculate_dewpoint(77.0, None) is None
        assert calculate_dewpoint(77.0, 0.0) is None
