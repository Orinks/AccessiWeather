from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from accessiweather.display.presentation.forecast import _resolve_forecast_display_time


def test_resolve_forecast_display_time_location_keeps_timestamp() -> None:
    start_time = datetime(2026, 2, 10, 9, 0, tzinfo=timezone(timedelta(hours=-8)))

    resolved = _resolve_forecast_display_time(
        start_time,
        forecast_time_reference="location",
        local_timezone=UTC,
    )

    assert resolved == start_time


def test_resolve_forecast_display_time_user_local_converts_aware_timestamp() -> None:
    start_time = datetime(2026, 2, 10, 9, 0, tzinfo=timezone(timedelta(hours=-8)))

    resolved = _resolve_forecast_display_time(
        start_time,
        forecast_time_reference="user_local",
        local_timezone=UTC,
    )

    assert resolved == datetime(2026, 2, 10, 17, 0, tzinfo=UTC)


def test_resolve_forecast_display_time_user_local_keeps_naive_timestamp() -> None:
    start_time = datetime(2026, 2, 10, 9, 0)

    resolved = _resolve_forecast_display_time(
        start_time,
        forecast_time_reference="user_local",
        local_timezone=UTC,
    )

    assert resolved == start_time
