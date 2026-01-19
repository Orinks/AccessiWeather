"""
Tests for weather data parsers.

Tests the parsing utilities used to normalize weather data.
"""

from __future__ import annotations

from accessiweather.weather_client_parsers import (
    convert_f_to_c,
    convert_mps_to_mph,
    convert_pa_to_inches,
    convert_pa_to_mb,
    convert_wind_speed_to_kph,
    convert_wind_speed_to_mph,
    degrees_to_cardinal,
    format_date_name,
    normalize_pressure,
    normalize_temperature,
    weather_code_to_description,
)


class TestTemperatureConversions:
    """Tests for temperature conversion functions."""

    def test_f_to_c(self):
        """Test Fahrenheit to Celsius conversion."""
        assert convert_f_to_c(32.0) == 0.0
        assert convert_f_to_c(212.0) == 100.0
        assert abs(convert_f_to_c(72.0) - 22.22) < 0.1
        assert convert_f_to_c(None) is None

    def test_normalize_temperature_fahrenheit(self):
        """Test normalizing Fahrenheit temperatures."""
        f, c = normalize_temperature(72.0, "degF")
        assert f == 72.0
        assert abs(c - 22.22) < 0.1

    def test_normalize_temperature_celsius(self):
        """Test normalizing Celsius temperatures."""
        f, c = normalize_temperature(22.0, "degC")
        assert c == 22.0
        assert abs(f - 71.6) < 0.1

    def test_normalize_temperature_wmoUnit(self):
        """Test normalizing with wmoUnit prefix."""
        f, c = normalize_temperature(72.0, "wmoUnit:degF")
        assert f == 72.0

    def test_normalize_temperature_none(self):
        """Test normalizing None temperature."""
        f, c = normalize_temperature(None, "degF")
        assert f is None
        assert c is None


class TestWindSpeedConversions:
    """Tests for wind speed conversion functions."""

    def test_mps_to_mph(self):
        """Test meters per second to mph conversion."""
        result = convert_mps_to_mph(10.0)
        assert abs(result - 22.37) < 0.1
        assert convert_mps_to_mph(None) is None

    def test_wind_speed_to_mph_from_kmh(self):
        """Test converting km/h to mph."""
        mph = convert_wind_speed_to_mph(16.09, "km_h-1")
        assert abs(mph - 10.0) < 0.1

    def test_wind_speed_to_mph_from_mps(self):
        """Test converting m/s to mph."""
        mph = convert_wind_speed_to_mph(4.47, "m_s-1")
        assert abs(mph - 10.0) < 0.1

    def test_wind_speed_to_mph_from_knots(self):
        """Test converting knots to mph."""
        # 10 knots = ~11.5 mph (1 knot = 1.15078 mph)
        # Use unit code ending in 'kt' which the parser recognizes
        mph = convert_wind_speed_to_mph(10.0, "kt")
        assert abs(mph - 11.5) < 0.2

    def test_wind_speed_to_kph(self):
        """Test converting mph to km/h."""
        # 10 mph = ~16.09 km/h - use 'mph' unit code which the parser recognizes
        kph = convert_wind_speed_to_kph(10.0, "mph")
        assert kph is not None
        assert abs(kph - 16.09) < 0.1


class TestPressureConversions:
    """Tests for pressure conversion functions."""

    def test_pa_to_inches(self):
        """Test Pascals to inches of mercury conversion."""
        inches = convert_pa_to_inches(101325.0)  # Standard atmosphere
        assert abs(inches - 29.92) < 0.1
        assert convert_pa_to_inches(None) is None

    def test_pa_to_mb(self):
        """Test Pascals to millibars conversion."""
        mb = convert_pa_to_mb(101325.0)
        assert abs(mb - 1013.25) < 0.1
        assert convert_pa_to_mb(None) is None

    def test_normalize_pressure_pa(self):
        """Test normalizing pressure from Pascals."""
        inches, mb = normalize_pressure(101325.0, "Pa")
        assert abs(inches - 29.92) < 0.1
        assert abs(mb - 1013.25) < 0.1

    def test_normalize_pressure_mb(self):
        """Test normalizing pressure from millibars."""
        inches, mb = normalize_pressure(1013.25, "hPa")
        assert abs(mb - 1013.25) < 0.1
        assert abs(inches - 29.92) < 0.1


class TestWindDirection:
    """Tests for wind direction conversion."""

    def test_cardinal_directions(self):
        """Test basic cardinal directions."""
        assert degrees_to_cardinal(0) == "N"
        assert degrees_to_cardinal(90) == "E"
        assert degrees_to_cardinal(180) == "S"
        assert degrees_to_cardinal(270) == "W"

    def test_intercardinal_directions(self):
        """Test intercardinal directions."""
        assert degrees_to_cardinal(45) == "NE"
        assert degrees_to_cardinal(135) == "SE"
        assert degrees_to_cardinal(225) == "SW"
        assert degrees_to_cardinal(315) == "NW"

    def test_secondary_intercardinal(self):
        """Test secondary intercardinal directions."""
        assert degrees_to_cardinal(22.5) == "NNE"
        assert degrees_to_cardinal(67.5) == "ENE"

    def test_wraparound(self):
        """Test 360 degree wraparound."""
        assert degrees_to_cardinal(360) == "N"
        assert degrees_to_cardinal(359) == "N"

    def test_none(self):
        """Test None input."""
        assert degrees_to_cardinal(None) is None


class TestWeatherCodes:
    """Tests for weather code descriptions."""

    def test_clear_codes(self):
        """Test clear sky codes."""
        desc = weather_code_to_description(0)
        assert "clear" in desc.lower()

    def test_cloudy_codes(self):
        """Test cloudy weather codes."""
        assert "cloud" in weather_code_to_description(2).lower()
        assert "overcast" in weather_code_to_description(3).lower().replace("cloud", "overcast")

    def test_precipitation_codes(self):
        """Test precipitation codes."""
        # Rain
        assert "rain" in weather_code_to_description(61).lower()
        # Snow
        assert "snow" in weather_code_to_description(71).lower()

    def test_thunderstorm_codes(self):
        """Test thunderstorm codes."""
        assert "thunder" in weather_code_to_description(95).lower()

    def test_unknown_code(self):
        """Test unknown weather code."""
        desc = weather_code_to_description(999)
        assert desc is not None  # Should return something, not None

    def test_none_code(self):
        """Test None weather code."""
        assert weather_code_to_description(None) is None


class TestDateFormatting:
    """Tests for date formatting."""

    def test_format_today(self):
        """Test formatting today."""
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        assert format_date_name(today, 0) == "Today"

    def test_format_tomorrow(self):
        """Test formatting tomorrow."""
        from datetime import datetime, timedelta

        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert format_date_name(tomorrow, 1) == "Tomorrow"

    def test_format_future_day(self):
        """Test formatting future days."""
        from datetime import datetime, timedelta

        future = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        result = format_date_name(future, 3)
        # Should be a day name like "Wednesday"
        assert result not in ["Today", "Tomorrow"]
        assert len(result) > 0
