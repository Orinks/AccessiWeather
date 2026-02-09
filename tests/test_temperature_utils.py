"""Tests for accessiweather.utils.temperature_utils module."""

import pytest

from accessiweather.utils.temperature_utils import (
    TemperatureUnit,
    _normalize_dewpoint_unit,
    calculate_dewpoint,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    format_temperature,
    get_temperature_values,
)

# --- celsius_to_fahrenheit / fahrenheit_to_celsius ---


class TestConversions:
    def test_celsius_to_fahrenheit_freezing(self):
        assert celsius_to_fahrenheit(0) == 32

    def test_celsius_to_fahrenheit_boiling(self):
        assert celsius_to_fahrenheit(100) == 212

    def test_fahrenheit_to_celsius_freezing(self):
        assert fahrenheit_to_celsius(32) == 0

    def test_fahrenheit_to_celsius_boiling(self):
        assert fahrenheit_to_celsius(212) == 100

    def test_roundtrip(self):
        assert abs(fahrenheit_to_celsius(celsius_to_fahrenheit(25)) - 25) < 1e-9


# --- _normalize_dewpoint_unit ---


class TestNormalizeDewpointUnit:
    @pytest.mark.parametrize("val", ["c", "celsius", "°c", "degc", "wmounit:degc"])
    def test_celsius_strings(self, val):
        assert _normalize_dewpoint_unit(val) == TemperatureUnit.CELSIUS

    @pytest.mark.parametrize("val", ["f", "fahrenheit", "°f", "degf", "wmounit:degf"])
    def test_fahrenheit_strings(self, val):
        assert _normalize_dewpoint_unit(val) == TemperatureUnit.FAHRENHEIT

    def test_celsius_enum(self):
        assert _normalize_dewpoint_unit(TemperatureUnit.CELSIUS) == TemperatureUnit.CELSIUS

    def test_fahrenheit_enum(self):
        assert _normalize_dewpoint_unit(TemperatureUnit.FAHRENHEIT) == TemperatureUnit.FAHRENHEIT

    def test_both_enum_maps_to_fahrenheit(self):
        assert _normalize_dewpoint_unit(TemperatureUnit.BOTH) == TemperatureUnit.FAHRENHEIT

    def test_none_defaults_to_fahrenheit(self):
        assert _normalize_dewpoint_unit(None) == TemperatureUnit.FAHRENHEIT

    def test_invalid_string_defaults_to_fahrenheit(self):
        assert _normalize_dewpoint_unit("kelvin") == TemperatureUnit.FAHRENHEIT

    def test_whitespace_stripped(self):
        assert _normalize_dewpoint_unit("  celsius  ") == TemperatureUnit.CELSIUS


# --- calculate_dewpoint ---


class TestCalculateDewpoint:
    def test_basic_fahrenheit(self):
        result = calculate_dewpoint(72, 50, unit=TemperatureUnit.FAHRENHEIT)
        assert result is not None
        assert 50 < result < 60  # rough sanity

    def test_basic_celsius(self):
        result = calculate_dewpoint(22, 50, unit=TemperatureUnit.CELSIUS)
        assert result is not None
        assert 10 < result < 15

    def test_none_temperature(self):
        assert calculate_dewpoint(None, 50) is None

    def test_none_humidity(self):
        assert calculate_dewpoint(72, None) is None

    def test_both_none(self):
        assert calculate_dewpoint(None, None) is None

    def test_non_numeric_temperature(self):
        assert calculate_dewpoint("abc", 50) is None

    def test_non_numeric_humidity(self):
        assert calculate_dewpoint(72, "xyz") is None

    def test_zero_humidity(self):
        assert calculate_dewpoint(72, 0) is None

    def test_negative_humidity(self):
        assert calculate_dewpoint(72, -5) is None

    def test_hundred_percent_humidity(self):
        # At 100% humidity, dewpoint should equal temperature
        result = calculate_dewpoint(20, 100, unit=TemperatureUnit.CELSIUS)
        assert result is not None
        assert abs(result - 20) < 0.5

    def test_string_unit(self):
        result = calculate_dewpoint(72, 50, unit="celsius")
        # unit="celsius" means input is Celsius
        assert result is not None

    def test_very_low_humidity(self):
        # 0.05% humidity should clamp to 0.1
        result = calculate_dewpoint(72, 0.05, unit=TemperatureUnit.FAHRENHEIT)
        assert result is not None


# --- format_temperature ---


class TestFormatTemperature:
    def test_fahrenheit_only(self):
        result = format_temperature(72, TemperatureUnit.FAHRENHEIT)
        assert "72" in result
        assert "°F" in result

    def test_celsius_only(self):
        result = format_temperature(72, TemperatureUnit.CELSIUS)
        assert "°C" in result

    def test_both_units(self):
        result = format_temperature(72, TemperatureUnit.BOTH)
        assert "°F" in result
        assert "°C" in result

    def test_none_temperature_with_celsius(self):
        result = format_temperature(None, TemperatureUnit.FAHRENHEIT, temperature_c=20)
        assert "°F" in result

    def test_none_temperature_none_celsius(self):
        assert format_temperature(None) == "N/A"

    def test_smart_precision_whole_number(self):
        result = format_temperature(72.0, TemperatureUnit.FAHRENHEIT, smart_precision=True)
        assert result == "72°F"

    def test_smart_precision_decimal(self):
        result = format_temperature(72.5, TemperatureUnit.FAHRENHEIT, smart_precision=True)
        assert result == "72.5°F"

    def test_smart_precision_off(self):
        result = format_temperature(
            72.0, TemperatureUnit.FAHRENHEIT, smart_precision=False, precision=1
        )
        assert result == "72.0°F"

    def test_celsius_smart_precision_whole(self):
        result = format_temperature(
            None, TemperatureUnit.CELSIUS, temperature_c=20.0, smart_precision=True
        )
        assert result == "20°C"

    def test_both_with_temperature_c_none(self):
        result = format_temperature(72, TemperatureUnit.BOTH)
        assert "°F" in result
        assert "°C" in result

    def test_both_smart_precision(self):
        result = format_temperature(
            32.0, TemperatureUnit.BOTH, temperature_c=0.0, smart_precision=True
        )
        assert result == "32°F (0°C)"

    def test_precision_2(self):
        result = format_temperature(
            72.123, TemperatureUnit.FAHRENHEIT, smart_precision=False, precision=2
        )
        assert result == "72.12°F"

    def test_only_temperature_c_celsius_unit(self):
        result = format_temperature(None, TemperatureUnit.CELSIUS, temperature_c=25.0)
        assert "25" in result
        assert "°C" in result

    def test_only_temperature_c_both_unit(self):
        result = format_temperature(None, TemperatureUnit.BOTH, temperature_c=0.0)
        assert "°F" in result
        assert "°C" in result


# --- get_temperature_values ---


class TestGetTemperatureValues:
    def test_both_none(self):
        assert get_temperature_values(None, None) == (None, None)

    def test_only_fahrenheit(self):
        f, c = get_temperature_values(32, None)
        assert f == 32
        assert abs(c - 0) < 0.01

    def test_only_celsius(self):
        f, c = get_temperature_values(None, 100)
        assert abs(f - 212) < 0.01
        assert c == 100

    def test_both_provided(self):
        f, c = get_temperature_values(72, 22.2)
        assert f == 72
        assert c == 22.2
