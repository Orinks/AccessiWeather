"""Date and time formatting helpers for weather presentation output."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

_DATE_FORMATS = {
    "iso": "%Y-%m-%d",
    "us_short": "%m/%d/%Y",
    "us_long": "%B %d, %Y",
    "eu": "%d/%m/%Y",
}


def format_date(dt: datetime | None, style: str) -> str:
    """Format a date using a preset style key; unknown keys fall back to ISO."""
    if dt is None:
        return ""
    fmt = _DATE_FORMATS.get(style, _DATE_FORMATS["iso"])
    return dt.strftime(fmt)


def format_datetime(dt: datetime | None, date_style: str, time_12hour: bool) -> str:
    """Format a full datetime as "<date> <time>"; 12h output strips leading zero."""
    if dt is None:
        return ""
    date_part = format_date(dt, date_style)
    time_fmt = "%I:%M %p" if time_12hour else "%H:%M"
    time_part = dt.strftime(time_fmt)
    if time_12hour:
        time_part = time_part.lstrip("0")
    return f"{date_part} {time_part}"


def format_display_time(
    start_time: datetime | None,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
) -> str:
    """
    Format time with user preferences for display mode, format, and timezone labels.

    Note: "local" mode shows the LOCATION'S local time (e.g., PST for LA weather),
    not the user's system timezone.

    Args:
    ----
        start_time: Datetime to format (should be in location's timezone)
        time_display_mode: One of "local", "utc", or "both"
        use_12hour: If True, use 12-hour format; if False, use 24-hour format
        show_timezone: If True, append timezone abbreviation

    Returns:
    -------
        Formatted time string according to preferences

    """
    if not start_time:
        return "Unknown"

    # Prepare time format
    # For 12-hour, we typically want to remove leading zero for hours (e.g., "6:00 PM" not "06:00 PM")
    # But strftime %I produces zero-padded. We'll handle stripping later if needed.
    time_format = "%I:%M %p" if use_12hour else "%H:%M"

    def _fmt(dt: datetime) -> str:
        s = dt.strftime(time_format)
        if use_12hour and s.startswith("0"):
            s = s[1:]
        return s

    if time_display_mode == "utc":
        # Show UTC time
        utc_time = start_time
        if start_time.tzinfo is not None:
            utc_time = start_time.astimezone(UTC)
        time_str = _fmt(utc_time)
        if show_timezone:
            time_str += " UTC"
        return time_str

    if time_display_mode == "both":
        # Show both location's local time and UTC: "3:00 PM PST (23:00 UTC)"
        # Keep time in location's timezone - don't convert to system timezone
        local_str = _fmt(start_time)

        # Get timezone abbreviation for location's time
        if show_timezone:
            tz_abbr = _get_timezone_abbreviation(start_time)
            if tz_abbr:
                local_str += f" {tz_abbr}"

        # Add UTC time in parentheses
        utc_time = start_time.astimezone(UTC) if start_time.tzinfo else start_time
        utc_str = _fmt(utc_time)
        return f"{local_str} ({utc_str} UTC)"

    # Default: location's local time only
    time_str = _fmt(start_time)
    if show_timezone:
        tz_abbr = _get_timezone_abbreviation(start_time)
        # Defensive guard: if upstream lost the location timezone and attached UTC,
        # avoid labeling "local" mode as UTC. The canonical fix is upstream.
        if tz_abbr and start_time.utcoffset() != timedelta(0):
            time_str += f" {tz_abbr}"
    return time_str


def format_hour_time(
    start_time: datetime | None,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
) -> str:
    """Render an hour label for hourly forecast output."""
    return format_display_time(
        start_time,
        time_display_mode=time_display_mode,
        use_12hour=use_12hour,
        show_timezone=show_timezone,
    )


def format_display_datetime(
    value: datetime,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
    date_format: str = "%b %d",
) -> str:
    """
    Format date and time with user preferences.

    Args:
    ----
        value: Datetime to format
        time_display_mode: Display mode preference
        use_12hour: 12/24 hour format preference
        show_timezone: Whether to show timezone suffix
        date_format: Strftime format for the date part

    """
    time_format = "%I:%M %p" if use_12hour else "%H:%M"

    def _fmt(dt: datetime) -> str:
        d_str = dt.strftime(date_format)
        t_str = dt.strftime(time_format)
        if use_12hour and t_str.startswith("0"):
            t_str = t_str[1:]
        return f"{d_str} {t_str}"

    if time_display_mode == "utc":
        utc_time = value
        if value.tzinfo is not None:
            utc_time = value.astimezone(UTC)
        s = _fmt(utc_time)
        if show_timezone:
            s += " UTC"
        return s

    if time_display_mode == "both":
        # Local
        local_str = _fmt(value)
        if show_timezone:
            tz_abbr = _get_timezone_abbreviation(value)
            if tz_abbr:
                local_str += f" {tz_abbr}"

        # UTC
        utc_time = value.astimezone(UTC) if value.tzinfo else value
        utc_str = _fmt(utc_time)
        return f"{local_str} ({utc_str} UTC)"

    # Local
    s = _fmt(value)
    if show_timezone:
        tz_abbr = _get_timezone_abbreviation(value)
        if tz_abbr:
            s += f" {tz_abbr}"
    return s


def format_timestamp(
    value: datetime,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
) -> str:
    """Return a timestamp suitable for metric labels."""
    return format_display_time(
        value,
        time_display_mode=time_display_mode,
        use_12hour=use_12hour,
        show_timezone=show_timezone,
    )


def format_sun_time(
    sun_time: datetime | None,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
) -> str | None:
    """
    Format sunrise or sunset time for display.

    Args:
    ----
        sun_time: Datetime object for sunrise or sunset (should be timezone-aware
                  in the location's local timezone)
        time_display_mode: Display mode preference
        use_12hour: 12/24 hour format preference
        show_timezone: Whether to show timezone suffix

    Returns:
    -------
        Formatted time string (e.g., "6:32 AM PST") or None if time is not available

    """
    if sun_time is None:
        return None
    return format_display_time(
        sun_time,
        time_display_mode=time_display_mode,
        use_12hour=use_12hour,
        show_timezone=show_timezone,
    )


def _get_timezone_abbreviation(dt: datetime) -> str:
    """
    Get timezone abbreviation for a datetime, handling cross-platform differences.

    Returns consistent abbreviations like 'EST', 'PST', 'UTC' instead of platform-specific
    names like 'Eastern Standard Time' on Windows.
    """
    if dt.tzinfo is None:
        return ""

    # Try to get tzname from the datetime
    tzname = dt.strftime("%Z")
    if not tzname:
        return ""

    # Handle common full timezone names and convert to abbreviations
    # This ensures consistency across Windows and Unix systems
    timezone_map = {
        "Eastern Standard Time": "EST",
        "Eastern Daylight Time": "EDT",
        "Central Standard Time": "CST",
        "Central Daylight Time": "CDT",
        "Mountain Standard Time": "MST",
        "Mountain Daylight Time": "MDT",
        "Pacific Standard Time": "PST",
        "Pacific Daylight Time": "PDT",
        "Coordinated Universal Time": "UTC",
    }

    # Return mapped abbreviation or original if already abbreviated
    return timezone_map.get(tzname, tzname)


# Backwards compatibility alias if needed, though ideally should be removed/replaced
format_hour_time_with_preferences = format_display_time
