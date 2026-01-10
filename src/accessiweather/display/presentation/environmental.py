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

_UV_INDEX_GUIDANCE: dict[str, str] = {
    "Low": "No protection needed. You can safely stay outside.",
    "Moderate": (
        "Take precautions: wear sunscreen SPF 30+, a hat, and sunglasses."
        " Seek shade during midday hours when the sun is strongest."
    ),
    "High": (
        "Protection essential: apply SPF 30+ sunscreen every 2 hours, wear protective"
        " clothing, a wide-brimmed hat, and UV-blocking sunglasses. Seek shade during midday."
    ),
    "Very High": (
        "Extra protection required: use SPF 50+ sunscreen, wear long sleeves and pants,"
        " a wide-brimmed hat, and sunglasses. Minimize sun exposure between 10 AM and 4 PM."
    ),
    "Extreme": (
        "Take all precautions: avoid sun exposure between 10 AM and 4 PM if possible."
        " Use SPF 50+ sunscreen, wear full protective clothing, and stay in shade when outdoors."
    ),
}

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

    # Pollen data
    pollen_line = _build_pollen_line(environmental)
    if pollen_line:
        lines.append(f"• {pollen_line}")
        details.append(pollen_line)

        # Add detailed pollen breakdown if available
        pollen_details = format_pollen_details(environmental)
        if pollen_details:
            details.append(pollen_details)

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
    if pollen_line and not summary_line:
        summary_value = pollen_line
    elif pollen_line:
        summary_value = f"{summary_value}. {pollen_line}"

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


def _build_pollen_line(environmental: EnvironmentalConditions) -> str | None:
    """Build a summary line for pollen conditions."""
    if environmental.pollen_index is None and not environmental.pollen_category:
        return None

    parts: list[str] = []
    if environmental.pollen_category:
        parts.append(f"Pollen: {environmental.pollen_category}")
    elif environmental.pollen_index is not None:
        parts.append(f"Pollen Index: {int(round(environmental.pollen_index))}")

    if environmental.pollen_primary_allergen:
        parts.append(f"({environmental.pollen_primary_allergen})")

    return " ".join(parts) if parts else None


def _build_updated_line(
    updated_at: datetime | None, settings: AppSettings | None = None
) -> str | None:
    if not updated_at:
        return None

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

    # Add individual hourly entries (show up to 12 hours)
    hourly_entries = data[:12]
    if hourly_entries:
        lines.append("")
        lines.append("Hourly Forecast:")
        for entry in hourly_entries:
            entry_time = _format_time(entry.timestamp, time_format_12hour)
            lines.append(f"  {entry_time}: AQI {entry.aqi} ({entry.category})")

    return "\n".join(lines)


def _format_time(dt: datetime, use_12hour: bool = True) -> str:
    """Format a datetime as a simple time string."""
    if use_12hour:
        return dt.strftime("%I:%M %p").lstrip("0")
    return dt.strftime("%H:%M")


def format_air_quality_summary(
    environmental: EnvironmentalConditions,
    settings: AppSettings | None = None,
) -> str:
    """
    Format current air quality as a summary string for the dialog.

    This is a pure function that accepts data and settings and returns formatted text.

    Args:
        environmental: Environmental conditions data containing AQI info.
        settings: App settings for time formatting preferences.

    Returns:
        Formatted summary string with AQI, category, pollutant, guidance, and timestamp.

    """
    lines: list[str] = []

    aqi = environmental.air_quality_index
    category = environmental.air_quality_category

    if aqi is not None or category:
        aqi_text = ""
        if aqi is not None:
            aqi_text = f"AQI: {int(round(aqi))}"
        if category:
            if aqi_text:
                aqi_text += f" ({category})"
            else:
                aqi_text = category
        lines.append(aqi_text)

    pollutant = environmental.air_quality_pollutant
    if pollutant:
        pollutant_name = _get_pollutant_display_name(pollutant)
        lines.append(f"Dominant pollutant: {pollutant_name}")

    guidance = _AIR_QUALITY_GUIDANCE.get(category or "", _DEFAULT_GUIDANCE)
    lines.append(f"Health guidance: {guidance}")

    if environmental.updated_at:
        time_format_12hour = getattr(settings, "time_format_12hour", True) if settings else True
        if time_format_12hour:
            timestamp = environmental.updated_at.strftime("%I:%M %p").lstrip("0")
        else:
            timestamp = environmental.updated_at.strftime("%H:%M")
        date_str = environmental.updated_at.strftime("%B %d, %Y")
        lines.append(f"Last updated: {timestamp} on {date_str}")

    return "\n".join(lines) if lines else "Air quality data not available."


def format_pollutant_details(
    hourly_data: list[HourlyAirQuality],
    dominant_pollutant: str | None = None,
) -> str:
    """
    Format pollutant measurements into readable text.

    This is a pure function that accepts data and returns formatted text.

    Args:
        hourly_data: List of hourly air quality data (uses first entry for current values).
        dominant_pollutant: Code of the dominant pollutant to highlight.

    Returns:
        Formatted pollutant breakdown with human-readable names and dominant indicator.

    """
    if not hourly_data:
        return "No pollutant data available."

    current = hourly_data[0]
    dominant_code = dominant_pollutant.strip().upper() if dominant_pollutant else None

    pollutants = [
        ("PM2_5", current.pm2_5, "µg/m³"),
        ("PM10", current.pm10, "µg/m³"),
        ("O3", current.ozone, "µg/m³"),
        ("NO2", current.nitrogen_dioxide, "µg/m³"),
        ("SO2", current.sulphur_dioxide, "µg/m³"),
        ("CO", current.carbon_monoxide, "µg/m³"),
    ]

    lines: list[str] = []
    for code, value, unit in pollutants:
        if value is not None:
            name = _POLLUTANT_LABELS.get(code, code)
            line = f"{name}: {value:.1f} {unit}"
            if dominant_code and code == dominant_code:
                line += " (dominant)"
            lines.append(line)

    return "\n".join(lines) if lines else "No pollutant measurements available."


def format_pollen_details(environmental: EnvironmentalConditions) -> str | None:
    """
    Format pollen measurements into readable text.

    Args:
        environmental: Environmental conditions data.

    Returns:
        Formatted pollen breakdown or None if no data.

    """
    items = []
    if environmental.pollen_tree_index is not None:
        items.append(f"Tree: {int(round(environmental.pollen_tree_index))}")
    if environmental.pollen_grass_index is not None:
        items.append(f"Grass: {int(round(environmental.pollen_grass_index))}")
    if environmental.pollen_weed_index is not None:
        items.append(f"Weed: {int(round(environmental.pollen_weed_index))}")

    if not items:
        return None

    return "Pollen Levels: " + ", ".join(items)


def _get_pollutant_display_name(pollutant_code: str) -> str:
    """Convert pollutant code to human-readable display name."""
    code = pollutant_code.strip().upper()
    if code in _POLLUTANT_LABELS:
        return _POLLUTANT_LABELS[code]
    if code == "PM2.5":
        return "PM2.5"
    if code == "OZONE":
        return "Ozone"
    return code.replace("_", " ").title() if "_" in code else code


def format_air_quality_brief(
    environmental: EnvironmentalConditions,
    settings: AppSettings | None = None,
) -> str:
    """
    Format a brief air quality summary for Current Conditions section.

    This is a pure function that returns a concise one-line summary with
    AQI value, category, and trend only. No detailed hourly breakdown.

    Args:
        environmental: Environmental conditions data containing AQI info.
        settings: App settings (unused, kept for API consistency).

    Returns:
        Brief summary like "AQI: 45 (Good) - Stable" or empty string if no data.

    """
    parts: list[str] = []

    aqi = environmental.air_quality_index
    category = environmental.air_quality_category

    if aqi is not None:
        aqi_text = f"AQI: {int(round(aqi))}"
        if category:
            aqi_text += f" ({category})"
        parts.append(aqi_text)
    elif category:
        parts.append(category)

    hourly_data = environmental.hourly_air_quality
    if hourly_data and len(hourly_data) >= 3:
        trend_start = hourly_data[0].aqi
        trend_end = hourly_data[2].aqi
        diff = trend_end - trend_start

        if diff > 20:
            parts.append("Worsening")
        elif diff < -20:
            parts.append("Improving")
        else:
            parts.append("Stable")
    elif parts:
        parts.append("Stable")

    return " - ".join(parts) if parts else ""
