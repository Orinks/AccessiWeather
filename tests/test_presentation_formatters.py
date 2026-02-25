from __future__ import annotations

from datetime import UTC, datetime

from accessiweather.display.presentation.formatters import format_display_time


def test_format_display_time_local_mode_utc_timestamp_omits_utc_suffix() -> None:
    start_time = datetime(2026, 1, 20, 18, 0, tzinfo=UTC)

    rendered = format_display_time(
        start_time,
        time_display_mode="local",
        use_12hour=False,
        show_timezone=True,
    )

    assert rendered == "18:00"


def test_format_display_time_local_mode_naive_timestamp_stays_as_is() -> None:
    start_time = datetime(2026, 1, 20, 9, 30)

    rendered = format_display_time(
        start_time,
        time_display_mode="local",
        use_12hour=False,
        show_timezone=True,
    )

    assert rendered == "09:30"
