"""Time formatting helpers for decoded TAF text."""

from __future__ import annotations

from .taf_patterns import TIME_RANGE_RE


def _format_issue_time(token: str) -> str:
    day = int(token[:2])
    hour = int(token[2:4])
    minute = int(token[4:6])
    return f"{hour:02d}:{minute:02d} UTC on the {_format_day(day)}"


def _format_time_range(token: str) -> str:
    if not TIME_RANGE_RE.match(token):
        return token
    start_raw, end_raw = token.split("/")
    start_day = int(start_raw[:2])
    start_hour = int(start_raw[2:4])
    end_day = int(end_raw[:2])
    end_hour = int(end_raw[2:4])
    return (
        f"from {start_hour:02d}:00 UTC on the {_format_day(start_day)} "
        f"until {end_hour:02d}:00 UTC on the {_format_day(end_day)}"
    )


def _format_from_time(token: str) -> str:
    if len(token) != 6 or not token.isdigit():
        return token
    day = int(token[:2])
    hour = int(token[2:4])
    minute = int(token[4:6])
    return f"{hour:02d}:{minute:02d} UTC on the {_format_day(day)}"


def _format_day(day: int) -> str:
    suffix = "th" if 10 <= day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"
