"""Presentation helpers for environmental data such as air quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ...models import AppSettings, EnvironmentalConditions, HourlyAirQuality, Location
from .formatters import format_display_datetime

_AIR_QUALITY_GUIDANCE: dict[str, str] = {
    "Good": "Air quality is satisfactory; enjoy normal outdoor activities.",
    "Moderate": (
        "Air quality is acceptable. People unusually sensitive to air pollution should"
        " reduce prolonged or heavy outdoor exertion."
    ),
    "Unhealthy for Sensitive Groups": (
        "Sensitive groups (people with lung or heart disease, older adults, children)"
        " should reduce prolonged or heavy outdoor exertion."
    ),
    "Unhealthy": (
        "Everyone should reduce prolonged or heavy outdoor exertion; sensitive groups"
        " should avoid extended time outdoors."
    ),
    "Very Unhealthy": "Avoid outdoor exertion and move activities indoors when possible.",
    "Hazardous": "Avoid all outdoor activity and follow local emergency air quality guidance.",
}

_DEFAULT_GUIDANCE = "Monitor local guidance and limit exposure if you notice symptoms."

_POLLUTANT_LABELS: dict[str, str] = {
    "PM2_5": "PM2.5",
    "PM10": "PM10",
    "O3": "Ozone",
    "SO2": "Sulfur Dioxide",
    "NO2": "Nitrogen Dioxide",
    "CO": "Carbon Monoxide",
}


@dataclass(slots=True)
class AirQualityPresentation:
    """Structured representation of air quality metrics."""

    title: str
    summary: str
    guidance: str | None = None
    details: list[str] = field(default_factory=list)
    fallback_text: str = ""
    updated_at: str | None = None
    sources: list[str] = field(default_factory=list)


def build_air_quality_panel(
    location: Location,
    environmental: EnvironmentalConditions,
    settings: AppSettings | None = None,
) -> AirQualityPresentation | None:
    """Create an accessible presentation of air quality metrics."""
    index = environmental.air_quality_index
    pollutant = environmental.air_quality_pollutant
    category = environmental.air_quality_category

    if index is None and not category and not pollutant:
        return None

    summary_line = _build_summary_line(index, category)
    pollutant_line = _build_pollutant_line(pollutant)
    updated_line = _build_updated_line(environmental.updated_at, settings)
    guidance = _AIR_QUALITY_GUIDANCE.get(category or "", _DEFAULT_GUIDANCE)
    sources = sorted({source for source in environmental.sources if source})

    lines = [f"Air quality for {location.name}"]
    details: list[str] = []

    if summary_line:
        lines.append(f"• {summary_line}")
        details.append(summary_line)
    if pollutant_line:
        lines.append(f"• {pollutant_line}")
        details.append(pollutant_line)
    if updated_line:
        lines.append(f"• {updated_line}")
        details.append(updated_line)
    if guidance:
        lines.append(f"• Advice: {guidance}")

    if sources:
        lines.append(f"Sources: {', '.join(sources)}")

    fallback_text = "\n".join(lines)

    summary_value = summary_line or "Air quality data not available."
    if pollutant_line:
        summary_value = f"{summary_value} – {pollutant_line}"

    return AirQualityPresentation(
        title=f"Air quality for {location.name}",
        summary=summary_value,
        guidance=guidance,
        details=details,
        fallback_text=fallback_text,
        updated_at=updated_line,
        sources=sources,
    )


def _build_summary_line(index: float | None, category: str | None) -> str | None:
    if index is None and not category:
        return None

    parts: list[str] = []
    if index is not None:
        rounded = int(round(index))
        parts.append(f"AQI {rounded}")
    if category:
        category_text = category.strip()
        parts.append(f"({category_text})" if parts else category_text)

    return " ".join(parts).strip() if parts else None


def _build_pollutant_line(pollutant: str | None) -> str | None:
    if not pollutant:
        return None

    label = pollutant.strip().upper()
    pretty = _POLLUTANT_LABELS.get(label)
    if pretty is None:
        pretty = label.replace("_", " ").title() if "_" in label else label
    return f"Dominant pollutant: {pretty}"


def _build_updated_line(
    updated_at: datetime | None, settings: AppSettings | None = None
) -> str | None:
    if not updated_at:
        return None

    # Extract time preferences
    if settings:
        time_display_mode = getattr(settings, "time_display_mode", "local")
        time_format_12hour = getattr(settings, "time_format_12hour", True)
        show_timezone_suffix = getattr(settings, "show_timezone_suffix", False)
    else:
        time_display_mode = "local"
        time_format_12hour = True
        show_timezone_suffix = False

    timestamp = format_display_datetime(
        updated_at,
        time_display_mode=time_display_mode,
        use_12hour=time_format_12hour,
        show_timezone=show_timezone_suffix,
    )
    return f"Updated {timestamp}"


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

    # Extract time preferences
    time_format_12hour = getattr(settings, "time_format_12hour", True) if settings else True

    # Limit to max_hours
    data = hourly_data[:max_hours]

    # Find current, peak, and best times
    current = data[0]
    peak = max(data, key=lambda h: h.aqi)
    best = min(data, key=lambda h: h.aqi)

    lines = []

    # Current AQI
    lines.append(f"Current: AQI {current.aqi} ({current.category})")

    # Trend analysis (compare first 3 hours if available)
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

    # Peak time
    if peak.aqi != current.aqi:
        peak_time = _format_time(peak.timestamp, time_format_12hour)
        lines.append(f"Peak: AQI {peak.aqi} ({peak.category}) at {peak_time}")

    # Best time for outdoor activities
    if best.aqi < 100 and best.aqi != current.aqi:
        best_time = _format_time(best.timestamp, time_format_12hour)
        lines.append(f"Best time: AQI {best.aqi} at {best_time}")

    return "\n".join(lines)


def _format_time(dt: datetime, use_12hour: bool = True) -> str:
    """Format a datetime as a simple time string."""
    if use_12hour:
        return dt.strftime("%I:%M %p").lstrip("0")
    return dt.strftime("%H:%M")
