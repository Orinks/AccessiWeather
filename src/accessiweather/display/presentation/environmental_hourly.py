"""Hourly environmental forecast formatting helpers."""

from __future__ import annotations

from datetime import datetime

from ...models import AppSettings, HourlyAirQuality, HourlyUVIndex


def format_hourly_air_quality(
    hourly_data: list[HourlyAirQuality],
    settings: AppSettings | None = None,
    max_hours: int = 24,
) -> str | None:
    """
    Format hourly air quality forecast into readable text.

    Args:
        hourly_data: List of hourly air quality forecasts.
        settings: App settings for time formatting.
        max_hours: Maximum number of hours to include.

    Returns:
        Formatted string describing the hourly forecast, or None if no data.

    """
    if not hourly_data:
        return None

    time_format_12hour = getattr(settings, "time_format_12hour", True) if settings else True
    data = hourly_data[:max_hours]

    current = data[0]
    peak = max(data, key=lambda h: h.aqi)
    best = min(data, key=lambda h: h.aqi)

    lines = []
    lines.append(f"Current: AQI {current.aqi} ({current.category})")

    if len(data) >= 3:
        trend_start = data[0].aqi
        trend_end = data[2].aqi
        diff = trend_end - trend_start

        if diff > 20:
            lines.append(f"Trend: Worsening (AQI {trend_start} → {trend_end})")
        elif diff < -20:
            lines.append(f"Trend: Improving (AQI {trend_start} → {trend_end})")
        else:
            lines.append("Trend: Stable")

    if peak.aqi != current.aqi:
        peak_time = _format_time(peak.timestamp, time_format_12hour)
        lines.append(f"Peak: AQI {peak.aqi} ({peak.category}) at {peak_time}")

    if best.aqi < 100 and best.aqi != current.aqi:
        best_time = _format_time(best.timestamp, time_format_12hour)
        lines.append(f"Best time: AQI {best.aqi} at {best_time}")

    hourly_entries = data[:12]
    if hourly_entries:
        lines.append("")
        lines.append("Hourly Forecast:")
        for entry in hourly_entries:
            entry_time = _format_time(entry.timestamp, time_format_12hour)
            lines.append(f"  {entry_time}: AQI {entry.aqi} ({entry.category})")

    return "\n".join(lines)


def format_hourly_uv_index(
    hourly_data: list[HourlyUVIndex],
    settings: AppSettings | None = None,
    max_hours: int = 24,
) -> str | None:
    """
    Format hourly UV index forecast into readable text.

    Args:
        hourly_data: List of hourly UV index forecasts.
        settings: App settings for time formatting.
        max_hours: Maximum number of hours to include.

    Returns:
        Formatted string describing the hourly forecast, or None if no data.

    """
    if not hourly_data:
        return None

    time_format_12hour = getattr(settings, "time_format_12hour", True) if settings else True
    data = hourly_data[:max_hours]

    current = data[0]
    peak = max(data, key=lambda h: h.uv_index)
    lowest = min(data, key=lambda h: h.uv_index)

    lines = []
    lines.append(f"Current: UV Index {current.uv_index:.1f} ({current.category})")

    if len(data) >= 3:
        trend_start = data[0].uv_index
        trend_end = data[2].uv_index
        diff = trend_end - trend_start

        if diff > 2:
            lines.append(f"Trend: Rising (UV {trend_start:.1f} → {trend_end:.1f})")
        elif diff < -2:
            lines.append(f"Trend: Falling (UV {trend_start:.1f} → {trend_end:.1f})")
        else:
            lines.append("Trend: Stable")

    if peak.uv_index != current.uv_index:
        peak_time = _format_time(peak.timestamp, time_format_12hour)
        lines.append(f"Peak: UV Index {peak.uv_index:.1f} ({peak.category}) at {peak_time}")

    if lowest.uv_index < 3 and lowest.uv_index != current.uv_index:
        lowest_time = _format_time(lowest.timestamp, time_format_12hour)
        lines.append(f"Lowest UV: {lowest.uv_index:.1f} at {lowest_time}")

    hourly_entries = data[:12]
    if hourly_entries:
        lines.append("")
        lines.append("Hourly Forecast:")
        for entry in hourly_entries:
            entry_time = _format_time(entry.timestamp, time_format_12hour)
            lines.append(f"  {entry_time}: UV Index {entry.uv_index:.1f} ({entry.category})")

    return "\n".join(lines)


def _format_time(dt: datetime, use_12hour: bool = True) -> str:
    """Format a datetime as a simple time string."""
    if use_12hour:
        return dt.strftime("%I:%M %p").lstrip("0")
    return dt.strftime("%H:%M")
