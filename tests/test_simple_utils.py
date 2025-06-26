"""Tests for utility functions in the simplified AccessiWeather application.

This module provides comprehensive tests for the utility functions in the simplified
AccessiWeather implementation, adapted from the existing wxPython test suite while
updating imports and module references for the simplified Toga architecture.
"""

# Import utility functions from the simplified app
from accessiweather.simple.utils import (
    TemperatureUnit,
    celsius_to_fahrenheit,
    convert_wind_direction_to_cardinal,
    fahrenheit_to_celsius,
    format_combined_wind,
    format_precipitation,
    format_pressure,
    format_temperature,
    format_visibility,
    format_wind_speed,
    get_temperature_values,
)


class TestTemperatureUtils:
    """Test temperature utility functions - adapted from existing test logic."""

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


class TestUnitUtils:
    """Test unit utility functions - adapted from existing test logic."""

    def test_format_wind_speed_fahrenheit(self):
        """Test format_wind_speed function with Fahrenheit preference."""
        # Test with Fahrenheit preference
        assert format_wind_speed(10, TemperatureUnit.FAHRENHEIT) == "10.0 mph"
        assert format_wind_speed(15.5, TemperatureUnit.FAHRENHEIT) == "15.5 mph"
        assert format_wind_speed(None, TemperatureUnit.FAHRENHEIT) == "N/A"

        # Test with Fahrenheit preference but providing km/h value
        assert (
            format_wind_speed(None, TemperatureUnit.FAHRENHEIT, wind_speed_kph=16.1) == "10.0 mph"
        )
        assert (
            format_wind_speed(None, TemperatureUnit.FAHRENHEIT, wind_speed_kph=24.9) == "15.5 mph"
        )

    def test_format_wind_speed_celsius(self):
        """Test format_wind_speed function with Celsius preference."""
        # Test with Celsius preference
        assert format_wind_speed(10, TemperatureUnit.CELSIUS) == "16.1 km/h"
        assert format_wind_speed(15.5, TemperatureUnit.CELSIUS) == "24.9 km/h"
        assert format_wind_speed(None, TemperatureUnit.CELSIUS) == "N/A"

        # Test with Celsius preference but providing km/h value
        assert format_wind_speed(None, TemperatureUnit.CELSIUS, wind_speed_kph=16.1) == "16.1 km/h"
        assert format_wind_speed(None, TemperatureUnit.CELSIUS, wind_speed_kph=24.9) == "24.9 km/h"

    def test_format_wind_speed_both(self):
        """Test format_wind_speed function with Both preference."""
        # Test with Both preference
        assert format_wind_speed(10, TemperatureUnit.BOTH) == "10.0 mph (16.1 km/h)"
        assert format_wind_speed(15.5, TemperatureUnit.BOTH) == "15.5 mph (24.9 km/h)"
        assert format_wind_speed(None, TemperatureUnit.BOTH) == "N/A"

        # Test with Both preference but providing km/h value
        assert (
            format_wind_speed(None, TemperatureUnit.BOTH, wind_speed_kph=16.1)
            == "10.0 mph (16.1 km/h)"
        )
        assert (
            format_wind_speed(None, TemperatureUnit.BOTH, wind_speed_kph=24.9)
            == "15.5 mph (24.9 km/h)"
        )


class TestWindDirectionUtils:
    """Test wind direction utility functions - adapted from existing test logic."""

    def test_convert_wind_direction_to_cardinal(self):
        """Test wind direction conversion from degrees to cardinal directions."""
        # Test cardinal directions
        assert convert_wind_direction_to_cardinal(0) == "N"
        assert convert_wind_direction_to_cardinal(90) == "E"
        assert convert_wind_direction_to_cardinal(180) == "S"
        assert convert_wind_direction_to_cardinal(270) == "W"

        # Test intermediate directions
        assert convert_wind_direction_to_cardinal(45) == "NE"
        assert convert_wind_direction_to_cardinal(135) == "SE"
        assert convert_wind_direction_to_cardinal(225) == "SW"
        assert convert_wind_direction_to_cardinal(315) == "NW"

        # Test more specific directions
        assert convert_wind_direction_to_cardinal(330) == "NNW"
        assert convert_wind_direction_to_cardinal(22.5) == "NNE"

        # Test edge cases
        assert convert_wind_direction_to_cardinal(None) == "N/A"
        assert convert_wind_direction_to_cardinal(360) == "N"  # Should wrap around

        # Test boundary values - the function uses round() so 11.25 rounds to 0 (N)
        assert convert_wind_direction_to_cardinal(11.25) == "N"  # Boundary value (rounds to 0)
        assert convert_wind_direction_to_cardinal(22.5) == "NNE"  # Exact boundary

    def test_format_combined_wind(self):
        """Test combined wind formatting with speed and direction."""
        # Test with mph and cardinal direction
        result = format_combined_wind(15.0, "NW", TemperatureUnit.FAHRENHEIT)
        assert "15" in result and "NW" in result

        # Test with numeric direction (should convert to cardinal)
        result = format_combined_wind(15.0, 330, TemperatureUnit.FAHRENHEIT)
        assert "15" in result and "NNW" in result

        # Test calm conditions
        result = format_combined_wind(0, None, TemperatureUnit.FAHRENHEIT)
        assert result == "Calm"

        # Test None values
        result = format_combined_wind(None, None, TemperatureUnit.FAHRENHEIT)
        assert result == "N/A"


class TestPressureUtils:
    """Test pressure utility functions - adapted from existing test logic."""

    def test_format_pressure_fahrenheit(self):
        """Test format_pressure function with Fahrenheit preference."""
        # Test with Fahrenheit preference
        assert format_pressure(30.1, TemperatureUnit.FAHRENHEIT, precision=0) == "30 inHg"
        assert format_pressure(29.92, TemperatureUnit.FAHRENHEIT, precision=0) == "30 inHg"
        assert format_pressure(None, TemperatureUnit.FAHRENHEIT, precision=0) == "N/A"

        # Test with Fahrenheit preference but providing mb value
        assert (
            format_pressure(None, TemperatureUnit.FAHRENHEIT, pressure_mb=1019, precision=0)
            == "30 inHg"
        )
        assert (
            format_pressure(None, TemperatureUnit.FAHRENHEIT, pressure_mb=1013, precision=0)
            == "30 inHg"
        )

    def test_format_pressure_celsius(self):
        """Test format_pressure function with Celsius preference."""
        # Test with Celsius preference
        assert format_pressure(30.1, TemperatureUnit.CELSIUS, precision=0) == "1019 hPa"
        assert format_pressure(29.92, TemperatureUnit.CELSIUS, precision=0) == "1013 hPa"
        assert format_pressure(None, TemperatureUnit.CELSIUS, precision=0) == "N/A"

        # Test with Celsius preference but providing mb value
        assert (
            format_pressure(None, TemperatureUnit.CELSIUS, pressure_mb=1019, precision=0)
            == "1019 hPa"
        )
        assert (
            format_pressure(None, TemperatureUnit.CELSIUS, pressure_mb=1013, precision=0)
            == "1013 hPa"
        )

    def test_format_pressure_both(self):
        """Test format_pressure function with Both preference."""
        # Test with Both preference
        assert format_pressure(30.1, TemperatureUnit.BOTH, precision=0) == "30 inHg (1019 hPa)"
        assert format_pressure(29.92, TemperatureUnit.BOTH, precision=0) == "30 inHg (1013 hPa)"
        assert format_pressure(None, TemperatureUnit.BOTH, precision=0) == "N/A"

        # Test with Both preference but providing mb value
        assert (
            format_pressure(None, TemperatureUnit.BOTH, pressure_mb=1019, precision=0)
            == "30 inHg (1019 hPa)"
        )
        assert (
            format_pressure(None, TemperatureUnit.BOTH, pressure_mb=1013, precision=0)
            == "30 inHg (1013 hPa)"
        )


class TestVisibilityUtils:
    """Test visibility utility functions - adapted from existing test logic."""

    def test_format_visibility_fahrenheit(self):
        """Test format_visibility function with Fahrenheit preference."""
        # Test with Fahrenheit preference
        assert format_visibility(10, TemperatureUnit.FAHRENHEIT) == "10.0 mi"
        assert format_visibility(5.5, TemperatureUnit.FAHRENHEIT) == "5.5 mi"
        assert format_visibility(None, TemperatureUnit.FAHRENHEIT) == "N/A"

        # Test with Fahrenheit preference but providing km value
        assert format_visibility(None, TemperatureUnit.FAHRENHEIT, visibility_km=16.1) == "10.0 mi"
        assert format_visibility(None, TemperatureUnit.FAHRENHEIT, visibility_km=8.85) == "5.5 mi"

    def test_format_visibility_celsius(self):
        """Test format_visibility function with Celsius preference."""
        # Test with Celsius preference
        assert format_visibility(10, TemperatureUnit.CELSIUS) == "16.1 km"
        assert format_visibility(5.5, TemperatureUnit.CELSIUS) == "8.9 km"
        assert format_visibility(None, TemperatureUnit.CELSIUS) == "N/A"

        # Test with Celsius preference but providing km value
        assert format_visibility(None, TemperatureUnit.CELSIUS, visibility_km=16.1) == "16.1 km"
        assert format_visibility(None, TemperatureUnit.CELSIUS, visibility_km=8.85) == "8.8 km"

    def test_format_visibility_both(self):
        """Test format_visibility function with Both preference."""
        # Test with Both preference
        assert format_visibility(10, TemperatureUnit.BOTH) == "10.0 mi (16.1 km)"
        assert format_visibility(5.5, TemperatureUnit.BOTH) == "5.5 mi (8.9 km)"
        assert format_visibility(None, TemperatureUnit.BOTH) == "N/A"

        # Test with Both preference but providing km value
        assert (
            format_visibility(None, TemperatureUnit.BOTH, visibility_km=16.1) == "10.0 mi (16.1 km)"
        )
        assert (
            format_visibility(None, TemperatureUnit.BOTH, visibility_km=8.85) == "5.5 mi (8.8 km)"
        )


class TestPrecipitationUtils:
    """Test precipitation utility functions - adapted from existing test logic."""

    def test_format_precipitation_fahrenheit(self):
        """Test format_precipitation function with Fahrenheit preference."""
        # Test with Fahrenheit preference
        assert format_precipitation(0.5, TemperatureUnit.FAHRENHEIT) == "0.50 in"
        assert format_precipitation(1.25, TemperatureUnit.FAHRENHEIT) == "1.25 in"
        assert format_precipitation(None, TemperatureUnit.FAHRENHEIT) == "N/A"

        # Test with Fahrenheit preference but providing mm value
        assert (
            format_precipitation(None, TemperatureUnit.FAHRENHEIT, precipitation_mm=12.7)
            == "0.50 in"
        )
        assert (
            format_precipitation(None, TemperatureUnit.FAHRENHEIT, precipitation_mm=31.75)
            == "1.25 in"
        )

    def test_format_precipitation_celsius(self):
        """Test format_precipitation function with Celsius preference."""
        # Test with Celsius preference
        assert format_precipitation(0.5, TemperatureUnit.CELSIUS) == "12.70 mm"
        assert format_precipitation(1.25, TemperatureUnit.CELSIUS) == "31.75 mm"
        assert format_precipitation(None, TemperatureUnit.CELSIUS) == "N/A"

        # Test with Celsius preference but providing mm value
        assert (
            format_precipitation(None, TemperatureUnit.CELSIUS, precipitation_mm=12.7) == "12.70 mm"
        )
        assert (
            format_precipitation(None, TemperatureUnit.CELSIUS, precipitation_mm=31.75)
            == "31.75 mm"
        )

    def test_format_precipitation_both(self):
        """Test format_precipitation function with Both preference."""
        # Test with Both preference
        assert format_precipitation(0.5, TemperatureUnit.BOTH) == "0.50 in (12.70 mm)"
        assert format_precipitation(1.25, TemperatureUnit.BOTH) == "1.25 in (31.75 mm)"
        assert format_precipitation(None, TemperatureUnit.BOTH) == "N/A"

        # Test with Both preference but providing mm value
        assert (
            format_precipitation(None, TemperatureUnit.BOTH, precipitation_mm=12.7)
            == "0.50 in (12.70 mm)"
        )
        assert (
            format_precipitation(None, TemperatureUnit.BOTH, precipitation_mm=31.75)
            == "1.25 in (31.75 mm)"
        )


class TestUtilityIntegration:
    """Test integration scenarios for utility functions."""

    def test_temperature_unit_enum(self):
        """Test TemperatureUnit enum functionality."""
        # Test enum values
        assert TemperatureUnit.FAHRENHEIT == "fahrenheit"
        assert TemperatureUnit.CELSIUS == "celsius"
        assert TemperatureUnit.BOTH == "both"

        # Test string conversion
        assert str(TemperatureUnit.FAHRENHEIT) == "fahrenheit"
        assert str(TemperatureUnit.CELSIUS) == "celsius"
        assert str(TemperatureUnit.BOTH) == "both"

    def test_utility_functions_with_edge_cases(self):
        """Test utility functions with edge cases and error conditions."""
        # Test with zero values
        assert format_wind_speed(0, TemperatureUnit.FAHRENHEIT) == "0.0 mph"
        assert format_pressure(0, TemperatureUnit.FAHRENHEIT) == "0.00 inHg"
        assert format_visibility(0, TemperatureUnit.FAHRENHEIT) == "0.0 mi"
        assert format_precipitation(0, TemperatureUnit.FAHRENHEIT) == "0.00 in"

        # Test with very large values
        assert format_wind_speed(999.9, TemperatureUnit.FAHRENHEIT) == "999.9 mph"
        assert format_temperature(999.9, TemperatureUnit.FAHRENHEIT) == "999.9°F"

        # Test wind direction edge cases
        assert convert_wind_direction_to_cardinal(359.9) == "N"  # Close to 360
        assert convert_wind_direction_to_cardinal(0.1) == "N"  # Close to 0

    def test_utility_functions_preserve_precision(self):
        """Test that utility functions preserve appropriate precision."""
        # Test temperature precision
        assert format_temperature(68.123, TemperatureUnit.FAHRENHEIT, precision=2) == "68.12°F"
        assert format_temperature(68.123, TemperatureUnit.FAHRENHEIT, precision=0) == "68°F"

        # Test wind speed precision
        assert format_wind_speed(15.789, TemperatureUnit.FAHRENHEIT, precision=2) == "15.79 mph"
        assert format_wind_speed(15.789, TemperatureUnit.FAHRENHEIT, precision=0) == "16 mph"


# Smoke test functions that can be run with briefcase dev --test
def test_utility_imports_available():
    """Test that all utility functions can be imported successfully."""
    # This test verifies that all utility functions are available for import
    from accessiweather.simple.utils import (
        TemperatureUnit,
        celsius_to_fahrenheit,
        convert_wind_direction_to_cardinal,
        format_wind_speed,
    )

    # Basic functionality test
    assert celsius_to_fahrenheit(0) == 32
    assert convert_wind_direction_to_cardinal(330) == "NNW"
    assert format_wind_speed(15, TemperatureUnit.FAHRENHEIT) == "15.0 mph"


def test_utility_basic_functionality():
    """Test basic utility functionality without complex scenarios."""
    # Temperature conversion
    assert celsius_to_fahrenheit(20) == 68
    assert fahrenheit_to_celsius(68) == 20

    # Wind direction conversion
    assert convert_wind_direction_to_cardinal(0) == "N"
    assert convert_wind_direction_to_cardinal(90) == "E"
    assert convert_wind_direction_to_cardinal(180) == "S"
    assert convert_wind_direction_to_cardinal(270) == "W"

    # Basic formatting
    assert format_temperature(68, TemperatureUnit.FAHRENHEIT) == "68°F"
    assert format_wind_speed(10, TemperatureUnit.FAHRENHEIT) == "10.0 mph"
