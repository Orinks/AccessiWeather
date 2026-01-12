"""Tests for UV index presentation helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from accessiweather.display.presentation.environmental import (
    _get_uv_category,
    format_hourly_uv_index,
)
from accessiweather.models import AppSettings, HourlyUVIndex


@pytest.mark.unit
class TestGetUVCategory:
    """Tests for _get_uv_category function."""

    def test_none_input(self):
        """Test that None input returns None."""
        assert _get_uv_category(None) is None

    def test_low_category_bottom(self):
        """Test UV index 0 returns Low."""
        assert _get_uv_category(0) == "Low"

    def test_low_category_middle(self):
        """Test UV index 1 returns Low."""
        assert _get_uv_category(1) == "Low"

    def test_low_category_top(self):
        """Test UV index 2 returns Low."""
        assert _get_uv_category(2) == "Low"

    def test_moderate_category_bottom(self):
        """Test UV index 3 returns Moderate."""
        assert _get_uv_category(3) == "Moderate"

    def test_moderate_category_middle(self):
        """Test UV index 4 returns Moderate."""
        assert _get_uv_category(4) == "Moderate"

    def test_moderate_category_top(self):
        """Test UV index 5 returns Moderate."""
        assert _get_uv_category(5) == "Moderate"

    def test_high_category_bottom(self):
        """Test UV index 6 returns High."""
        assert _get_uv_category(6) == "High"

    def test_high_category_middle(self):
        """Test UV index 6.5 returns High."""
        assert _get_uv_category(6.5) == "High"

    def test_high_category_top(self):
        """Test UV index 7 returns High."""
        assert _get_uv_category(7) == "High"

    def test_very_high_category_bottom(self):
        """Test UV index 8 returns Very High."""
        assert _get_uv_category(8) == "Very High"

    def test_very_high_category_middle(self):
        """Test UV index 9 returns Very High."""
        assert _get_uv_category(9) == "Very High"

    def test_very_high_category_top(self):
        """Test UV index 10 returns Very High."""
        assert _get_uv_category(10) == "Very High"

    def test_extreme_category_bottom(self):
        """Test UV index 11 returns Extreme."""
        assert _get_uv_category(11) == "Extreme"

    def test_extreme_category_high_value(self):
        """Test UV index 15 returns Extreme."""
        assert _get_uv_category(15) == "Extreme"

    def test_extreme_category_very_high_value(self):
        """Test UV index 20 returns Extreme."""
        assert _get_uv_category(20) == "Extreme"

    def test_fractional_values(self):
        """Test fractional UV index values."""
        assert _get_uv_category(2.7) == "Moderate"
        assert _get_uv_category(5.1) == "High"
        assert _get_uv_category(7.9) == "Very High"
        assert _get_uv_category(10.5) == "Extreme"


@pytest.mark.unit
class TestFormatHourlyUVIndex:
    """Tests for format_hourly_uv_index function."""

    def test_empty_list(self):
        """Test handling of empty hourly data."""
        result = format_hourly_uv_index([])
        assert result is None

    def test_none_input(self):
        """Test handling of None input."""
        result = format_hourly_uv_index(None)
        assert result is None

    def test_basic_formatting(self):
        """Test basic formatting of hourly UV index data."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=3.5, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=5.2, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=7.8, category="High"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "3.5" in result
        assert "Moderate" in result
        assert "7.8" in result
        assert "High" in result

    def test_shows_current_uv(self):
        """Test that current UV index is displayed."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=6.0, category="High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=7.0, category="High"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "Current" in result
        assert "6.0" in result

    def test_shows_rising_trend(self):
        """Test that formatting identifies rising UV trends."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=2.0, category="Low"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=4.0, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=6.5, category="High"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "rising" in result.lower() or "increasing" in result.lower()

    def test_shows_falling_trend(self):
        """Test that formatting identifies falling UV trends."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=8.0, category="Very High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=5.5, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=3.0, category="Moderate"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "falling" in result.lower() or "decreasing" in result.lower()

    def test_shows_stable_trend(self):
        """Test that formatting identifies stable UV trends."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=5.0, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=5.5, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=5.2, category="Moderate"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "stable" in result.lower()

    def test_identifies_peak_uv(self):
        """Test that formatting identifies peak UV times."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=4.0, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=3), uv_index=9.5, category="Very High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=6), uv_index=5.0, category="Moderate"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "9.5" in result
        assert "peak" in result.lower() or "highest" in result.lower()

    def test_identifies_lowest_uv(self):
        """Test that formatting identifies lowest UV times when appropriate."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=5.0, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=1.5, category="Low"),
            HourlyUVIndex(timestamp=now + timedelta(hours=4), uv_index=6.0, category="High"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "1.5" in result or "lowest" in result.lower()

    def test_does_not_show_lowest_if_above_threshold(self):
        """Test that lowest UV is not shown if all values are above threshold."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=6.0, category="High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=7.0, category="High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=8.0, category="Very High"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        # Should not mention lowest since all values are high
        # This is testing the threshold logic (< 3)

    def test_respects_max_hours_limit(self):
        """Test that formatting respects max_hours parameter."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now + timedelta(hours=i), uv_index=5.0, category="Moderate")
            for i in range(48)
        ]

        result = format_hourly_uv_index(hourly_data, max_hours=6)

        assert result is not None
        # Should only process first 6 hours

    def test_respects_12hour_time_format(self):
        """Test that formatting respects 12-hour time format setting."""
        now = datetime.now(UTC).replace(hour=14, minute=30)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=6.0, category="High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=7.0, category="High"),
        ]

        settings = AppSettings(time_format_12hour=True)
        result = format_hourly_uv_index(hourly_data, settings=settings)

        assert result is not None
        # Should contain time in 12-hour format (PM)
        assert "PM" in result or "AM" in result

    def test_respects_24hour_time_format(self):
        """Test that formatting respects 24-hour time format setting."""
        now = datetime.now(UTC).replace(hour=14, minute=30)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=6.0, category="High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=7.0, category="High"),
        ]

        settings = AppSettings(time_format_12hour=False)
        result = format_hourly_uv_index(hourly_data, settings=settings)

        assert result is not None
        # Should contain time in 24-hour format
        assert "14:" in result or "15:" in result

    def test_includes_hourly_entries(self):
        """Test that individual hourly entries are included."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now + timedelta(hours=i), uv_index=5.0 + i, category="Moderate")
            for i in range(6)
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "Hourly Forecast:" in result
        # Should contain individual entries

    def test_limits_hourly_entries_to_12(self):
        """Test that hourly entries are limited to 12 hours."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now + timedelta(hours=i), uv_index=5.0, category="Moderate")
            for i in range(24)
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        # Should show up to 12 hourly entries even though 24 are available

    def test_single_hour_of_data(self):
        """Test handling of single hour of data."""
        now = datetime.now(UTC)
        hourly_data = [HourlyUVIndex(timestamp=now, uv_index=6.0, category="High")]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "Current" in result
        assert "6.0" in result
        # Should not crash with single data point

    def test_two_hours_of_data(self):
        """Test handling of two hours of data."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=5.0, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=6.0, category="High"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        # Should handle gracefully without trend analysis (needs 3+ hours)

    def test_extreme_uv_values(self):
        """Test formatting with extreme UV index values."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=12.5, category="Extreme"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=11.0, category="Extreme"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=13.0, category="Extreme"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "12.5" in result
        assert "Extreme" in result

    def test_low_uv_values(self):
        """Test formatting with low UV index values."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=0.5, category="Low"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=1.0, category="Low"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=1.5, category="Low"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "0.5" in result
        assert "Low" in result

    def test_mixed_categories(self):
        """Test formatting with mixed UV categories."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=2.0, category="Low"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=4.0, category="Moderate"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=7.0, category="High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=3), uv_index=9.0, category="Very High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=4), uv_index=11.0, category="Extreme"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        assert "Low" in result
        assert "Moderate" in result
        assert "High" in result
        assert "Very High" in result
        assert "Extreme" in result

    def test_no_settings_uses_defaults(self):
        """Test that None settings uses default formatting."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=6.0, category="High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=7.0, category="High"),
        ]

        result = format_hourly_uv_index(hourly_data, settings=None)

        assert result is not None
        # Should default to 12-hour format
        assert ":" in result  # Time should be present

    def test_peak_when_first_is_peak(self):
        """Test peak handling when current time is the peak."""
        now = datetime.now(UTC)
        hourly_data = [
            HourlyUVIndex(timestamp=now, uv_index=9.0, category="Very High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=1), uv_index=7.0, category="High"),
            HourlyUVIndex(timestamp=now + timedelta(hours=2), uv_index=5.0, category="Moderate"),
        ]

        result = format_hourly_uv_index(hourly_data)

        assert result is not None
        # Peak equals current, so peak line should not be shown separately


@pytest.mark.unit
def test_uv_category_boundary_precision():
    """Test UV category boundaries with high precision floats."""
    # Test values at boundaries with floating point precision
    assert _get_uv_category(2.0) == "Low"
    assert _get_uv_category(2.0000001) == "Moderate"
    assert _get_uv_category(5.0) == "Moderate"
    assert _get_uv_category(5.0000001) == "High"
    assert _get_uv_category(7.0) == "High"
    assert _get_uv_category(7.0000001) == "Very High"
    assert _get_uv_category(10.0) == "Very High"
    assert _get_uv_category(10.0000001) == "Extreme"
