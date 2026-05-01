"""Forecast time-resolution helpers."""

from __future__ import annotations

from datetime import datetime, tzinfo


def _resolve_forecast_display_time(
    start_time: datetime,
    *,
    forecast_time_reference: str,
    location_timezone: tzinfo | None = None,
    local_timezone: tzinfo | None = None,
) -> datetime:
    """
    Resolve forecast hour display time to the configured timezone reference.

    Location mode keeps the source timestamp unchanged. My-local mode converts
    timezone-aware values to the system's local timezone.
    """
    if start_time.tzinfo is None:
        return start_time

    if forecast_time_reference != "user_local":
        if location_timezone is None:
            return start_time
        return start_time.astimezone(location_timezone)

    target_tz = local_timezone or datetime.now().astimezone().tzinfo
    if target_tz is None:
        return start_time.astimezone()
    return start_time.astimezone(target_tz)
