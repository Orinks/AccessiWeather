"""
Tests for unit utility formatting helpers.

Validates unit conversions, formatting, and edge cases.
"""

from __future__ import annotations

import pytest

from accessiweather.utils.temperature_utils import TemperatureUnit
from accessiweather.utils.unit_utils import (
    convert_wind_direction_to_cardinal,
    format_combined_wind,
    format_precipitation,
    format_pressure,
    format_visibility,
    format_wind_speed,
)


class TestFormatWindSpeed:
    """Tests for wind speed formatting."""

    @pytest.mark.parametrize(
        ("unit", "expected"),
        [
            (TemperatureUnit.FAHRENHEIT, "10.0 mph"),
            (TemperatureUnit.CELSIUS, "16.1 km/h"),
            (TemperatureUnit.BOTH, "10.0 mph (16.1 km/h)"),
        ],
    )
    def test_format_wind_speed_all_units(self, unit: TemperatureUnit, expected: str) -> None:
        """Format wind speed for all temperature units."""
        result = format_wind_speed(10.0, unit=unit, wind_speed_kph=16.0934, precision=1)
        assert result == expected

    def test_format_wind_speed_none(self) -> None:
        """Return N/A when both wind speed values are missing."""
        assert format_wind_speed(None, unit=TemperatureUnit.FAHRENHEIT) == "N/A"

    def test_format_wind_speed_conversion_from_mph(self) -> None:
        """Convert mph to km/h when only mph is provided."""
        result = format_wind_speed(10.0, unit=TemperatureUnit.CELSIUS, wind_speed_kph=None)
        assert result == "16.1 km/h"

    def test_format_wind_speed_conversion_from_kph(self) -> None:
        """Convert km/h to mph when only kph is provided."""
        result = format_wind_speed(None, unit=TemperatureUnit.FAHRENHEIT, wind_speed_kph=16.0934)
        assert result == "10.0 mph"

    def test_format_wind_speed_zero(self) -> None:
        """Handle zero values without returning N/A."""
        assert format_wind_speed(0.0, unit=TemperatureUnit.FAHRENHEIT) == "0.0 mph"

    def test_format_wind_speed_precision(self) -> None:
        """Honor the precision parameter."""
        result = format_wind_speed(5.556, unit=TemperatureUnit.FAHRENHEIT, precision=2)
        assert result == "5.56 mph"


class TestFormatPressure:
    """Tests for pressure formatting."""

    @pytest.mark.parametrize(
        ("unit", "expected"),
        [
            (TemperatureUnit.FAHRENHEIT, "30.00 inHg"),
            (TemperatureUnit.CELSIUS, "1015.92 hPa"),
            (TemperatureUnit.BOTH, "30.00 inHg (1015.92 hPa)"),
        ],
    )
    def test_format_pressure_all_units(self, unit: TemperatureUnit, expected: str) -> None:
        """Format pressure for all temperature units."""
        result = format_pressure(30.0, unit=unit, pressure_mb=1015.917, precision=2)
        assert result == expected

    def test_format_pressure_none(self) -> None:
        """Return N/A when both pressure values are missing."""
        assert format_pressure(None, unit=TemperatureUnit.FAHRENHEIT) == "N/A"

    def test_format_pressure_conversion_from_inhg(self) -> None:
        """Convert inHg to hPa when only inHg is provided."""
        result = format_pressure(30.0, unit=TemperatureUnit.CELSIUS, pressure_mb=None, precision=2)
        assert result == "1015.92 hPa"

    def test_format_pressure_conversion_from_mb(self) -> None:
        """Convert hPa to inHg when only hPa is provided."""
        result = format_pressure(None, unit=TemperatureUnit.FAHRENHEIT, pressure_mb=1015.92)
        assert result == "30.00 inHg"

    def test_format_pressure_zero(self) -> None:
        """Handle zero values without returning N/A."""
        assert format_pressure(0.0, unit=TemperatureUnit.FAHRENHEIT) == "0.00 inHg"

    def test_format_pressure_precision(self) -> None:
        """Honor the precision parameter."""
        result = format_pressure(29.1234, unit=TemperatureUnit.FAHRENHEIT, precision=3)
        assert result == "29.123 inHg"


class TestFormatVisibility:
    """Tests for visibility formatting."""

    @pytest.mark.parametrize(
        ("unit", "expected"),
        [
            (TemperatureUnit.FAHRENHEIT, "5.0 mi"),
            (TemperatureUnit.CELSIUS, "8.0 km"),
            (TemperatureUnit.BOTH, "5.0 mi (8.0 km)"),
        ],
    )
    def test_format_visibility_all_units(self, unit: TemperatureUnit, expected: str) -> None:
        """Format visibility for all temperature units."""
        result = format_visibility(5.0, unit=unit, visibility_km=8.0467, precision=1)
        assert result == expected

    def test_format_visibility_none(self) -> None:
        """Return N/A when both visibility values are missing."""
        assert format_visibility(None, unit=TemperatureUnit.FAHRENHEIT) == "N/A"

    def test_format_visibility_conversion_from_miles(self) -> None:
        """Convert miles to km when only miles is provided."""
        result = format_visibility(5.0, unit=TemperatureUnit.CELSIUS, visibility_km=None, precision=1)
        assert result == "8.0 km"

    def test_format_visibility_conversion_from_km(self) -> None:
        """Convert km to miles when only km is provided."""
        result = format_visibility(None, unit=TemperatureUnit.FAHRENHEIT, visibility_km=8.0467)
        assert result == "5.0 mi"

    def test_format_visibility_zero(self) -> None:
        """Handle zero values without returning N/A."""
        assert format_visibility(0.0, unit=TemperatureUnit.FAHRENHEIT) == "0.0 mi"

    def test_format_visibility_precision(self) -> None:
        """Honor the precision parameter."""
        result = format_visibility(3.333, unit=TemperatureUnit.FAHRENHEIT, precision=2)
        assert result == "3.33 mi"


class TestFormatPrecipitation:
    """Tests for precipitation formatting."""

    @pytest.mark.parametrize(
        ("unit", "expected"),
        [
            (TemperatureUnit.FAHRENHEIT, "1.00 in"),
            (TemperatureUnit.CELSIUS, "25.40 mm"),
            (TemperatureUnit.BOTH, "1.00 in (25.40 mm)"),
        ],
    )
    def test_format_precipitation_all_units(self, unit: TemperatureUnit, expected: str) -> None:
        """Format precipitation for all temperature units."""
        result = format_precipitation(1.0, unit=unit, precipitation_mm=25.4, precision=2)
        assert result == expected

    def test_format_precipitation_none(self) -> None:
        """Return N/A when both precipitation values are missing."""
        assert format_precipitation(None, unit=TemperatureUnit.FAHRENHEIT) == "N/A"

    def test_format_precipitation_conversion_from_inches(self) -> None:
        """Convert inches to mm when only inches are provided."""
        result = format_precipitation(
            1.0, unit=TemperatureUnit.CELSIUS, precipitation_mm=None, precision=2
        )
        assert result == "25.40 mm"

    def test_format_precipitation_conversion_from_mm(self) -> None:
        """Convert mm to inches when only mm are provided."""
        result = format_precipitation(
            None, unit=TemperatureUnit.FAHRENHEIT, precipitation_mm=25.4
        )
        assert result == "1.00 in"

    def test_format_precipitation_zero(self) -> None:
        """Handle zero values without returning N/A."""
        assert format_precipitation(0.0, unit=TemperatureUnit.FAHRENHEIT) == "0.00 in"

    def test_format_precipitation_precision(self) -> None:
        """Honor the precision parameter."""
        result = format_precipitation(0.12345, unit=TemperatureUnit.FAHRENHEIT, precision=3)
        assert result == "0.123 in"


class TestConvertWindDirectionToCardinal:
    """Tests for wind direction conversion."""

    @pytest.mark.parametrize(
        ("degrees", "expected"),
        [
            (0.0, "N"),
            (22.5, "NNE"),
            (45.0, "NE"),
            (67.5, "ENE"),
            (90.0, "E"),
            (112.5, "ESE"),
            (135.0, "SE"),
            (157.5, "SSE"),
            (180.0, "S"),
            (202.5, "SSW"),
            (225.0, "SW"),
            (247.5, "WSW"),
            (270.0, "W"),
            (292.5, "WNW"),
            (315.0, "NW"),
            (337.5, "NNW"),
        ],
    )
    def test_all_cardinal_directions(self, degrees: float, expected: str) -> None:
        """Convert degree values into all 16 cardinal directions."""
        assert convert_wind_direction_to_cardinal(degrees) == expected

    def test_direction_none(self) -> None:
        """Return N/A when direction is missing."""
        assert convert_wind_direction_to_cardinal(None) == "N/A"


class TestFormatCombinedWind:
    """Tests for combined wind formatting."""

    def test_combined_wind_calm(self) -> None:
        """Return Calm when wind speed is zero."""
        assert format_combined_wind(0, wind_direction=90) == "Calm"

    def test_combined_wind_direction_string(self) -> None:
        """Accept direction as a string."""
        assert format_combined_wind(12.3, wind_direction="NW") == "12 mph NW"

    def test_combined_wind_direction_degrees(self) -> None:
        """Convert degree directions to cardinal in combined output."""
        assert format_combined_wind(12.3, wind_direction=315) == "12 mph NW"

    def test_combined_wind_none(self) -> None:
        """Return N/A when wind speed is missing."""
        assert format_combined_wind(None, wind_direction=90) == "N/A"
