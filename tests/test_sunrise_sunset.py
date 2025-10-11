"""Tests for sunrise/sunset times in weather data."""

from datetime import UTC, datetime

from accessiweather.models import CurrentConditions
from accessiweather.display.presentation.formatters import format_sun_time


class TestSunriseSunset:
    """Test sunrise and sunset time functionality."""

    def test_current_conditions_with_sunrise_sunset(self):
        """Test that CurrentConditions can store sunrise and sunset times."""
        sunrise = datetime(2024, 6, 15, 6, 30, 0, tzinfo=UTC)
        sunset = datetime(2024, 6, 15, 20, 45, 0, tzinfo=UTC)
        
        conditions = CurrentConditions(
            temperature_f=75.0,
            temperature_c=23.9,
            condition="Clear",
            sunrise_time=sunrise,
            sunset_time=sunset,
        )
        
        assert conditions.sunrise_time == sunrise
        assert conditions.sunset_time == sunset
        assert conditions.temperature_f == 75.0

    def test_current_conditions_without_sunrise_sunset(self):
        """Test that CurrentConditions works without sunrise/sunset times."""
        conditions = CurrentConditions(
            temperature_f=75.0,
            temperature_c=23.9,
            condition="Clear",
        )
        
        assert conditions.sunrise_time is None
        assert conditions.sunset_time is None

    def test_format_sun_time_with_timezone_aware(self):
        """Test formatting sunrise/sunset time with timezone-aware datetime."""
        sun_time = datetime(2024, 6, 15, 6, 30, 0, tzinfo=UTC)
        formatted = format_sun_time(sun_time)
        
        # Should return a formatted time string
        assert formatted is not None
        assert ":" in formatted
        assert "AM" in formatted or "PM" in formatted

    def test_format_sun_time_with_none(self):
        """Test formatting with None value."""
        formatted = format_sun_time(None)
        assert formatted is None

    def test_format_sun_time_formatting(self):
        """Test that sun time is formatted correctly without leading zeros."""
        # Test morning time
        sun_time = datetime(2024, 6, 15, 6, 5, 0, tzinfo=UTC)
        formatted = format_sun_time(sun_time)
        
        # Should not have leading zero on hour
        assert formatted is not None
        # Check it doesn't start with 0 (e.g., should be "6:05 AM" not "06:05 AM")
        if "AM" in formatted or "PM" in formatted:
            hour_part = formatted.split(":")[0]
            assert not hour_part.startswith("0") or hour_part == "0"
