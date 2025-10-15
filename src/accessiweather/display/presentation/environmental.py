"""Presentation helpers for environmental data such as air quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ...models import EnvironmentalConditions, Location
from .formatters import format_timestamp

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
) -> AirQualityPresentation | None:
    """Create an accessible presentation of air quality metrics."""
    index = environmental.air_quality_index
    pollutant = environmental.air_quality_pollutant
    category = environmental.air_quality_category

    if index is None and not category and not pollutant:
        return None

    summary_line = _build_summary_line(index, category)
    pollutant_line = _build_pollutant_line(pollutant)
    updated_line = _build_updated_line(environmental.updated_at)
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


def _build_updated_line(updated_at: datetime | None) -> str | None:
    if not updated_at:
        return None
    return f"Updated {format_timestamp(updated_at)}"
