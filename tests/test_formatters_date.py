"""Tests for date/datetime format helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import (
    given,
    strategies as st,
)

from accessiweather.display.presentation.formatters import (
    format_date,
    format_datetime,
)

FIXED_DT = datetime(2026, 4, 18, 14, 5)  # 2:05 PM / 14:05


class TestFormatDate:
    @pytest.mark.parametrize(
        "style, expected",
        [
            ("iso", "2026-04-18"),
            ("us_short", "04/18/2026"),
            ("us_long", "April 18, 2026"),
            ("eu", "18/04/2026"),
        ],
    )
    def test_each_preset(self, style: str, expected: str) -> None:
        assert format_date(FIXED_DT, style) == expected

    def test_unknown_style_falls_back_to_iso(self) -> None:
        assert format_date(FIXED_DT, "not-a-real-style") == "2026-04-18"

    def test_none_returns_empty_string(self) -> None:
        assert format_date(None, "iso") == ""

    @given(
        st.datetimes(
            min_value=datetime(1900, 1, 1),
            max_value=datetime(2100, 12, 31),
        ),
        st.sampled_from(["iso", "us_short", "us_long", "eu", "bogus"]),
    )
    def test_never_crashes(self, dt: datetime, style: str) -> None:
        result = format_date(dt, style)
        assert isinstance(result, str)
        assert result  # non-empty for any real datetime


class TestFormatDatetime:
    def test_us_long_12hour(self) -> None:
        assert format_datetime(FIXED_DT, "us_long", True) == "April 18, 2026 2:05 PM"

    def test_iso_24hour(self) -> None:
        assert format_datetime(FIXED_DT, "iso", False) == "2026-04-18 14:05"

    def test_us_short_24hour(self) -> None:
        assert format_datetime(FIXED_DT, "us_short", False) == "04/18/2026 14:05"

    def test_morning_12hour_strips_leading_zero(self) -> None:
        morning = datetime(2026, 4, 18, 9, 7)
        assert format_datetime(morning, "iso", True) == "2026-04-18 9:07 AM"

    def test_none_returns_empty_string(self) -> None:
        assert format_datetime(None, "iso", True) == ""

    def test_morning_24hour_keeps_leading_zero(self) -> None:
        morning = datetime(2026, 4, 18, 9, 7)
        assert format_datetime(morning, "iso", False) == "2026-04-18 09:07"

    def test_midnight_24hour_not_corrupted(self) -> None:
        midnight = datetime(2026, 4, 18, 0, 0)
        assert format_datetime(midnight, "iso", False) == "2026-04-18 00:00"

    def test_midnight_12hour(self) -> None:
        midnight = datetime(2026, 4, 18, 0, 0)
        assert format_datetime(midnight, "iso", True) == "2026-04-18 12:00 AM"

    def test_noon_12hour(self) -> None:
        noon = datetime(2026, 4, 18, 12, 0)
        assert format_datetime(noon, "iso", True) == "2026-04-18 12:00 PM"

    def test_double_digit_hour_12hour(self) -> None:
        ten_am = datetime(2026, 4, 18, 10, 5)
        assert format_datetime(ten_am, "iso", True) == "2026-04-18 10:05 AM"

    def test_tz_aware_datetime_formats_without_tz_info(self) -> None:
        aware = datetime(2026, 4, 18, 14, 5, tzinfo=UTC)
        assert format_datetime(aware, "iso", False) == "2026-04-18 14:05"
