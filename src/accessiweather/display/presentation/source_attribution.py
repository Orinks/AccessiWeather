"""Source attribution presentation helpers."""

from __future__ import annotations

from ...models import WeatherData
from .models import SourceAttributionPresentation

_WET_CONDITION_MARKERS = (
    "thunderstorm",
    "t-storm",
    "rain",
    "shower",
    "drizzle",
    "snow",
    "sleet",
    "hail",
    "freezing rain",
)
_DRY_CONDITION_MARKERS = (
    "clear",
    "sunny",
    "cloudy",
    "overcast",
    "fair",
)


def build_source_attribution(weather_data: WeatherData) -> SourceAttributionPresentation | None:
    """Build source attribution presentation for transparency."""
    attribution = weather_data.source_attribution
    if not attribution:
        return None

    source_names = {
        "nws": "National Weather Service",
        "openmeteo": "Open-Meteo",
        "visualcrossing": "Visual Crossing",
        "pirateweather": "Pirate Weather",
    }

    contributing = [
        source_names.get(source, source.title())
        for source in sorted(attribution.contributing_sources)
    ]
    failed = [
        source_names.get(source, source.title()) for source in sorted(attribution.failed_sources)
    ]
    incomplete = list(weather_data.incomplete_sections)

    if contributing:
        summary = f"Data from: {', '.join(contributing)}"
        if failed:
            summary += f". Unavailable: {', '.join(failed)}"
    elif failed:
        summary = f"Sources unavailable: {', '.join(failed)}"
    else:
        summary = ""

    disagreement_note = _build_source_disagreement_note(weather_data, source_names)
    if disagreement_note:
        summary = f"{summary}. {disagreement_note}" if summary else disagreement_note

    aria_parts = []
    if contributing:
        aria_parts.append(f"Weather data provided by {', '.join(contributing)}")
    if failed:
        aria_parts.append(f"Data unavailable from {', '.join(failed)}")
    if incomplete:
        aria_parts.append(f"Missing sections: {', '.join(incomplete)}")
    if disagreement_note:
        aria_parts.append(disagreement_note)
    aria_label = ". ".join(aria_parts) if aria_parts else "Weather data source information"

    return SourceAttributionPresentation(
        contributing_sources=contributing,
        failed_sources=failed,
        incomplete_sections=incomplete,
        summary_text=summary,
        aria_label=aria_label,
    )


def _build_source_disagreement_note(
    weather_data: WeatherData, source_names: dict[str, str]
) -> str | None:
    """Return a short note when obvious condition sources disagree."""
    attribution = weather_data.source_attribution
    if attribution is None or weather_data.current is None:
        return None

    current_text = _clean_condition_text(weather_data.current.condition)
    current_state = _precipitation_state(current_text)
    if current_text is None or current_state is None:
        return None

    hourly_period = (
        weather_data.hourly_forecast.periods[0]
        if weather_data.hourly_forecast and weather_data.hourly_forecast.periods
        else None
    )
    hourly_text = _clean_condition_text(
        getattr(hourly_period, "short_forecast", None) if hourly_period else None
    )
    hourly_state = _precipitation_state(hourly_text)

    minutely = weather_data.minutely_precipitation
    minutely_text = _clean_condition_text(getattr(minutely, "summary", None))
    minutely_state = _minutely_precipitation_state(minutely)

    parts: list[str] = []
    field_sources = attribution.field_sources
    current_source = _format_source_name(field_sources.get("condition"), source_names)
    hourly_source = _format_source_name(field_sources.get("hourly_source"), source_names)
    minutely_source = _format_source_name(
        field_sources.get("minutely_precipitation") or field_sources.get("hourly_summary"),
        source_names,
    )

    if hourly_text and hourly_state is not None and hourly_state != current_state:
        parts.append(f"hourly forecast from {hourly_source} says {hourly_text}")

    if minutely_text and minutely_state is not None and minutely_state != current_state:
        parts.append(
            f"minute-by-minute precipitation outlook from {minutely_source} says {minutely_text}"
        )

    if not parts:
        return None

    return (
        f"Data note: current conditions from {current_source} report {current_text}; "
        f"{'; '.join(parts)}."
    )


def _clean_condition_text(value: str | None) -> str | None:
    """Normalize condition text for display while preserving user-facing wording."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned.rstrip(".") if cleaned else None


def _precipitation_state(value: str | None) -> str | None:
    """Classify obvious wet/dry condition wording; return None when ambiguous."""
    if value is None:
        return None
    normalized = value.casefold()
    if any(marker in normalized for marker in _WET_CONDITION_MARKERS):
        return "wet"
    if any(marker in normalized for marker in _DRY_CONDITION_MARKERS):
        return "dry"
    return None


def _minutely_precipitation_state(minutely: object | None) -> str | None:
    """Classify minutely precipitation data from explicit points or summary text."""
    if minutely is None:
        return None

    points = getattr(minutely, "points", None)
    if points:
        for point in points:
            intensity = getattr(point, "precipitation_intensity", None)
            probability = getattr(point, "precipitation_probability", None)
            if (isinstance(intensity, int | float) and intensity > 0) or (
                isinstance(probability, int | float) and probability > 0
            ):
                return "wet"
        return "dry"

    return _precipitation_state(_clean_condition_text(getattr(minutely, "summary", None)))


def _format_source_name(source: str | None, source_names: dict[str, str]) -> str:
    """Return a readable source label, falling back to a generic label."""
    if not source:
        return "another source"
    return source_names.get(source, source.title())
