"""Tests for unit utility functions."""

from accessiweather.utils.temperature_utils import TemperatureUnit
from accessiweather.utils.unit_utils import (
    format_precipitation,
    format_pressure,
    format_visibility,
    format_wind_speed,
)


class TestUnitUtils:
    """Test unit utility functions."""

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
