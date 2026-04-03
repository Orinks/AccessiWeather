"""Minutely precipitation timeline and summary generation for UI display."""

from __future__ import annotations

from ...models import MinutelyPrecipitationForecast
from ...notifications.minutely_precipitation import (
    detect_minutely_precipitation_transition,
    is_wet,
    precipitation_type_label,
)

INTENSITY_THRESHOLD_LIGHT = 0.01
INTENSITY_THRESHOLD_MODERATE = 0.1
INTENSITY_THRESHOLD_HEAVY = 1.0


def _classify_intensity(intensity: float | None) -> str:
    """Classify a precipitation intensity value into a human-readable label."""
    if intensity is None or intensity <= 0:
        return "None"
    if intensity < INTENSITY_THRESHOLD_MODERATE:
        return "Light"
    if intensity < INTENSITY_THRESHOLD_HEAVY:
        return "Moderate"
    return "Heavy"


def _dominant_intensity_label(forecast: MinutelyPrecipitationForecast) -> str:
    """Return a lowercase intensity descriptor for the wettest points."""
    max_intensity = 0.0
    for point in forecast.points:
        if point.precipitation_intensity is not None:
            max_intensity = max(max_intensity, point.precipitation_intensity)
    classification = _classify_intensity(max_intensity)
    return classification.lower() if classification != "None" else "light"


def _dominant_precip_type(forecast: MinutelyPrecipitationForecast) -> str:
    """Return the most common precipitation type label from wet points."""
    for point in forecast.points:
        if is_wet(point) and point.precipitation_type:
            return precipitation_type_label(point.precipitation_type).lower()
    return "precipitation"


def generate_minutely_summary(
    forecast: MinutelyPrecipitationForecast | None,
) -> str | None:
    """
    Generate a human-readable summary from minutely precipitation data.

    Returns *None* when *forecast* is ``None`` or has no points.
    """
    if forecast is None or not forecast.points:
        return None

    # Check for a transition first
    transition = detect_minutely_precipitation_transition(forecast)
    if transition is not None:
        precip_label = precipitation_type_label(transition.precipitation_type).capitalize()
        if transition.transition_type == "starting":
            return f"{precip_label} starting in ~{transition.minutes_until} minutes"
        return f"{precip_label} stopping in ~{transition.minutes_until} minutes"

    # No transition – either all dry or all wet
    if is_wet(forecast.points[0]):
        intensity = _dominant_intensity_label(forecast)
        precip_type = _dominant_precip_type(forecast)
        return f"{intensity.capitalize()} {precip_type} for the next hour"

    return "No precipitation expected"


def build_minutely_timeline(
    forecast: MinutelyPrecipitationForecast | None,
) -> str | None:
    """
    Build a screen-reader-friendly timeline at 5-minute intervals.

    Returns *None* when *forecast* is ``None`` or has no points.
    """
    if forecast is None or not forecast.points:
        return None

    parts: list[str] = []
    # Sample at indices 0, 5, 10, ... up to 60 minutes (index 60)
    for i in range(0, min(len(forecast.points), 61), 5):
        point = forecast.points[i]
        intensity = _classify_intensity(point.precipitation_intensity)
        label = "Now" if i == 0 else f"+{i}m"
        parts.append(f"{label}: {intensity}")

    if not parts:
        return None

    return ", ".join(parts)
