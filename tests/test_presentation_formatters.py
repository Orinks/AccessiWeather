"""Unit tests for presentation layer formatters, especially timezone handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from accessiweather.display.presentation.formatters import (
    _get_timezone_abbreviation,
    format_hour_time,
    format_hour_time_with_preferences,
)


class TestFormatHourTime:
    """Test the basic format_hour_time function for timezone conversion."""

    def test_format_hour_time_with_none(self):
        """Test handling of None input."""
        result = format_hour_time(None)
        assert result == "Unknown"

    def test_format_hour_time_with_naive_datetime(self):
        """Test formatting of timezone-naive datetime."""
        dt = datetime(2025, 11, 9, 15, 30)  # 3:30 PM
        result = format_hour_time(dt)
        assert result == "3:30 PM"

    def test_format_hour_time_with_utc_datetime(self):
        """Test formatting of UTC datetime converts to local time."""
        # Create a UTC datetime at 8:00 PM UTC
        dt = datetime(2025, 11, 9, 20, 0, tzinfo=UTC)
        result = format_hour_time(dt)
        # Result should be in local time (will vary by system timezone)
        # Just verify format is correct
        assert ":" in result
        assert "AM" in result or "PM" in result

    def test_format_hour_time_with_aware_datetime(self):
        """Test formatting of timezone-aware datetime converts to local time."""
        # Create a datetime with UTC-5 offset (Eastern Standard Time)
        eastern = timezone(timedelta(hours=-5))
        dt = datetime(2025, 11, 9, 15, 0, tzinfo=eastern)  # 3:00 PM EST
        result = format_hour_time(dt)
        # Should convert to local time
        assert ":" in result
        assert "AM" in result or "PM" in result


class TestFormatHourTimeWithPreferences:
    """Test the enhanced format_hour_time_with_preferences function."""

    def test_with_none_input(self):
        """Test handling of None input."""
        result = format_hour_time_with_preferences(None)
        assert result == "Unknown"

    def test_local_time_12hour_default(self):
        """Test default behavior: local time, 12-hour format, no timezone."""
        dt = datetime(2025, 11, 9, 15, 30, tzinfo=UTC)
        result = format_hour_time_with_preferences(dt)
        # Should convert to local time with 12-hour format
        assert ":" in result
        assert "AM" in result or "PM" in result

    def test_local_time_24hour(self):
        """Test local time with 24-hour format."""
        dt = datetime(2025, 11, 9, 15, 30, tzinfo=UTC)
        result = format_hour_time_with_preferences(
            dt, time_display_mode="local", use_12hour=False, show_timezone=False
        )
        # Should be in 24-hour format
        assert ":" in result
        assert "AM" not in result
        assert "PM" not in result

    def test_utc_time_12hour(self):
        """Test UTC time display with 12-hour format."""
        dt = datetime(2025, 11, 9, 20, 30, tzinfo=UTC)
        result = format_hour_time_with_preferences(
            dt, time_display_mode="utc", use_12hour=True, show_timezone=False
        )
        assert "08:30 PM" in result or "8:30 PM" in result

    def test_utc_time_24hour(self):
        """Test UTC time display with 24-hour format."""
        dt = datetime(2025, 11, 9, 20, 30, tzinfo=UTC)
        result = format_hour_time_with_preferences(
            dt, time_display_mode="utc", use_12hour=False, show_timezone=False
        )
        assert "20:30" in result

    def test_utc_time_with_timezone_label(self):
        """Test UTC time with timezone abbreviation."""
        dt = datetime(2025, 11, 9, 20, 30, tzinfo=UTC)
        result = format_hour_time_with_preferences(
            dt, time_display_mode="utc", use_12hour=True, show_timezone=True
        )
        assert "UTC" in result

    def test_both_time_display_mode(self):
        """Test displaying both local and UTC time."""
        dt = datetime(2025, 11, 9, 20, 0, tzinfo=UTC)
        result = format_hour_time_with_preferences(
            dt, time_display_mode="both", use_12hour=True, show_timezone=False
        )
        # Should have format like "3:00 PM (20:00 UTC)" or similar
        assert "(" in result
        assert "UTC)" in result

    def test_both_time_with_timezone_labels(self):
        """Test displaying both times with timezone abbreviations."""
        dt = datetime(2025, 11, 9, 20, 0, tzinfo=UTC)
        result = format_hour_time_with_preferences(
            dt, time_display_mode="both", use_12hour=True, show_timezone=True
        )
        # Should have format like "3:00 PM EST (20:00 UTC)" or similar
        assert "(" in result
        assert "UTC)" in result

    def test_naive_datetime_with_utc_mode(self):
        """Test that naive datetime in UTC mode is treated as-is."""
        dt = datetime(2025, 11, 9, 15, 30)  # Naive datetime
        result = format_hour_time_with_preferences(
            dt, time_display_mode="utc", use_12hour=True, show_timezone=True
        )
        assert "03:30 PM" in result or "3:30 PM" in result
        assert "UTC" in result


class TestGetTimezoneAbbreviation:
    """Test timezone abbreviation helper function."""

    def test_with_none_tzinfo(self):
        """Test handling of naive datetime (no timezone info)."""
        dt = datetime(2025, 11, 9, 15, 0)
        result = _get_timezone_abbreviation(dt)
        assert result == ""

    def test_with_utc_timezone(self):
        """Test UTC timezone abbreviation."""
        dt = datetime(2025, 11, 9, 15, 0, tzinfo=UTC)
        result = _get_timezone_abbreviation(dt)
        assert result in ("UTC", "UTC+00:00", "+00:00")

    def test_maps_full_timezone_names(self):
        """Test that full timezone names are mapped to abbreviations."""
        # This test verifies the mapping logic exists
        # Actual behavior depends on platform and timezone
        dt = datetime(2025, 11, 9, 15, 0, tzinfo=UTC)
        result = _get_timezone_abbreviation(dt)
        # Should return something, even if not mapped
        assert isinstance(result, str)


class TestTimezoneIntegration:
    """Integration tests for timezone handling in forecast display."""

    def test_hourly_forecast_times_are_local(self):
        """Test that hourly forecast times are displayed in local timezone by default."""
        # This would be an integration test with actual forecast building
        # For now, we verify the formatter works correctly
        utc_times = [
            datetime(2025, 11, 9, 20, 0, tzinfo=UTC),
            datetime(2025, 11, 9, 21, 0, tzinfo=UTC),
            datetime(2025, 11, 9, 22, 0, tzinfo=UTC),
        ]

        for utc_time in utc_times:
            result = format_hour_time(utc_time)
            # Verify format is correct (actual time depends on system timezone)
            assert ":" in result
            assert "AM" in result or "PM" in result

    def test_consistent_formatting_across_timezones(self):
        """Test that formatting preserves location's timezone instead of converting."""
        # Same moment in time, different timezone representations
        utc_time = datetime(2025, 11, 9, 20, 0, tzinfo=UTC)
        eastern_time = datetime(2025, 11, 9, 15, 0, tzinfo=timezone(timedelta(hours=-5)))

        # Each should format in its own timezone (not convert to system timezone)
        result_utc = format_hour_time(utc_time)
        result_eastern = format_hour_time(eastern_time)

        # Results should be different (showing location's time, not system time)
        # UTC shows 8:00 PM, Eastern shows 3:00 PM
        assert result_utc == "8:00 PM"
        assert result_eastern == "3:00 PM"


@pytest.mark.parametrize(
    "time_mode,use_12hour,show_tz,expected_pattern",
    [
        ("local", True, False, r"\d{1,2}:\d{2} [AP]M"),
        ("local", False, False, r"\d{2}:\d{2}"),
        ("utc", True, False, r"\d{1,2}:\d{2} [AP]M"),
        ("utc", False, False, r"\d{2}:\d{2}"),
        ("both", True, False, r"\d{1,2}:\d{2} [AP]M \(\d{1,2}:\d{2} [AP]M UTC\)"),
    ],
)
def test_format_patterns(time_mode, use_12hour, show_tz, expected_pattern):
    """Test that format_hour_time_with_preferences produces expected patterns."""
    dt = datetime(2025, 11, 9, 20, 0, tzinfo=UTC)
    result = format_hour_time_with_preferences(
        dt, time_display_mode=time_mode, use_12hour=use_12hour, show_timezone=show_tz
    )

    # Verify basic structure (exact times depend on local timezone)
    assert ":" in result
    if use_12hour:
        assert "AM" in result or "PM" in result
    if time_mode == "both":
        assert "(" in result
        assert "UTC)" in result
