"""Pirate Weather minutely precipitation parsing and transition detection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..models import MinutelyPrecipitationForecast, MinutelyPrecipitationPoint

NO_TRANSITION_SIGNATURE = "__none__"

# Intensity thresholds (mm/h) for wet detection.
# Pirate Weather light rain is typically 0.01–0.1 mm/h; moderate 0.1–1.0 mm/h.
INTENSITY_THRESHOLD_LIGHT = 0.01
INTENSITY_THRESHOLD_MODERATE = 0.1
INTENSITY_THRESHOLD_HEAVY = 1.0

# Map setting values to thresholds
SENSITIVITY_THRESHOLDS: dict[str, float] = {
    "light": INTENSITY_THRESHOLD_LIGHT,
    "moderate": INTENSITY_THRESHOLD_MODERATE,
    "heavy": INTENSITY_THRESHOLD_HEAVY,
}


@dataclass(frozen=True)
class MinutelyPrecipitationTransition:
    """A dry/wet transition detected in minutely precipitation data."""

    transition_type: str  # "starting" or "stopping"
    minutes_until: int
    precipitation_type: str | None = None

    @property
    def event_type(self) -> str:
        return (
            "minutely_precipitation_start"
            if self.transition_type == "starting"
            else "minutely_precipitation_stop"
        )

    @property
    def title(self) -> str:
        precipitation_label = precipitation_type_label(self.precipitation_type)
        minute_label = "minute" if self.minutes_until == 1 else "minutes"
        verb = "starting" if self.transition_type == "starting" else "stopping"
        return f"{precipitation_label} {verb} in {self.minutes_until} {minute_label}"


def parse_pirate_weather_minutely_block(
    payload: Mapping[str, Any] | None,
) -> MinutelyPrecipitationForecast | None:
    """
    Parse a Pirate Weather minutely block or full response.

    Accepts either the full API response containing a ``minutely`` object or the
    ``minutely`` object itself.
    """
    if not payload:
        return None

    minutely_payload = payload.get("minutely") if "minutely" in payload else payload
    if not isinstance(minutely_payload, Mapping):
        return None

    raw_points = minutely_payload.get("data")
    if not isinstance(raw_points, list):
        return None

    points: list[MinutelyPrecipitationPoint] = []
    for raw_point in raw_points:
        if not isinstance(raw_point, Mapping):
            continue
        raw_time = raw_point.get("time")
        if not isinstance(raw_time, (int, float)):
            continue
        points.append(
            MinutelyPrecipitationPoint(
                time=datetime.fromtimestamp(raw_time, tz=UTC),
                precipitation_intensity=_coerce_float(raw_point.get("precipIntensity")),
                precipitation_probability=_coerce_float(raw_point.get("precipProbability")),
                precipitation_type=_normalize_precipitation_type(raw_point.get("precipType")),
            )
        )

    if not points:
        return None

    summary = minutely_payload.get("summary")
    icon = minutely_payload.get("icon")
    return MinutelyPrecipitationForecast(
        summary=str(summary) if isinstance(summary, str) else None,
        icon=str(icon) if isinstance(icon, str) else None,
        points=points,
    )


def detect_minutely_precipitation_transition(
    forecast: MinutelyPrecipitationForecast | None,
    threshold: float = 0.0,
) -> MinutelyPrecipitationTransition | None:
    """
    Detect the first dry/wet transition in the next hour of minutely data.

    Args:
        forecast: Minutely precipitation forecast to analyse.
        threshold: Minimum precipitation intensity (mm/h) to count as wet.
            Defaults to ``0.0`` (any non-zero intensity).  Use one of the
            ``INTENSITY_THRESHOLD_*`` constants or ``SENSITIVITY_THRESHOLDS``
            to select a named sensitivity level.

    """
    if forecast is None or not forecast.points:
        return None

    baseline_is_wet = is_wet(forecast.points[0], threshold=threshold)
    for idx, point in enumerate(forecast.points[1:], start=1):
        if is_wet(point, threshold=threshold) == baseline_is_wet:
            continue
        if baseline_is_wet:
            return MinutelyPrecipitationTransition(
                transition_type="stopping",
                minutes_until=idx,
                precipitation_type=_first_precipitation_type(
                    forecast.points[:idx], threshold=threshold
                ),
            )
        return MinutelyPrecipitationTransition(
            transition_type="starting",
            minutes_until=idx,
            precipitation_type=_first_precipitation_type(
                forecast.points[idx:], threshold=threshold
            ),
        )

    return None


def build_minutely_transition_signature(
    forecast: MinutelyPrecipitationForecast | None,
    threshold: float = 0.0,
) -> str | None:
    """
    Return a stable signature for the current minutely transition state.

    ``None`` means the forecast was unavailable. ``NO_TRANSITION_SIGNATURE`` means
    the forecast was available but no dry/wet transition was detected.

    Args:
        forecast: Minutely precipitation forecast to analyse.
        threshold: Minimum precipitation intensity (mm/h) to count as wet.

    """
    if forecast is None or not forecast.points:
        return None

    transition = detect_minutely_precipitation_transition(forecast, threshold=threshold)
    if transition is None:
        return NO_TRANSITION_SIGNATURE

    precip_type = transition.precipitation_type or "precipitation"
    return f"{transition.transition_type}:{transition.minutes_until}:{precip_type}"


def is_wet(point: MinutelyPrecipitationPoint, threshold: float = 0.0) -> bool:
    """
    Return True when a minutely point indicates precipitation.

    Args:
        point: A single minutely data point.
        threshold: Minimum precipitation intensity (mm/h) required to be
            considered wet.  Defaults to ``0.0`` (any non-zero intensity).
            Pass one of the ``INTENSITY_THRESHOLD_*`` constants to filter out
            noise — e.g. ``INTENSITY_THRESHOLD_LIGHT`` (0.01 mm/h) ignores
            trace/sensor-noise readings while still catching light rain.

    """
    if point.precipitation_intensity is not None:
        return point.precipitation_intensity > threshold
    if point.precipitation_probability is not None:
        return point.precipitation_probability > 0
    return False


def precipitation_type_label(precipitation_type: str | None) -> str:
    """Return a user-facing precipitation label."""
    if precipitation_type == "sleet":
        return "Sleet"
    if precipitation_type == "snow":
        return "Snow"
    if precipitation_type == "hail":
        return "Hail"
    if precipitation_type == "freezing-rain":
        return "Freezing rain"
    if precipitation_type == "ice":
        return "Ice"
    if precipitation_type == "rain":
        return "Rain"
    return "Precipitation"


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_precipitation_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _first_precipitation_type(
    points: list[MinutelyPrecipitationPoint], threshold: float = 0.0
) -> str | None:
    for point in points:
        if is_wet(point, threshold=threshold) and point.precipitation_type:
            return point.precipitation_type
    return None
