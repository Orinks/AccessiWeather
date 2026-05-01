"""
Forecast confidence indicator from cross-source agreement.

Compares key metrics (temperature, precipitation probability) across
multiple forecast sources and produces a human-readable confidence level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from accessiweather.models.weather import SourceData

__all__ = [
    "ForecastConfidenceLevel",
    "ForecastConfidence",
    "calculate_forecast_confidence",
]

# Thresholds for HIGH / MEDIUM confidence
_TEMP_HIGH = 5.0  # °F — both temp and precip within this → HIGH
_TEMP_MED = 10.0  # °F — only temp considered → MEDIUM
_PRECIP_HIGH = 15.0  # % — precip spread for HIGH
_PRECIP_MED = 25.0  # % — precip spread for MEDIUM

# Human-readable display names for source identifiers
_SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "nws": "NWS",
    "openmeteo": "Open-Meteo",
    "pirateweather": "Pirate Weather",
}


def _display_name(source_id: str) -> str:
    """Return a human-readable name for a source identifier."""
    return _SOURCE_DISPLAY_NAMES.get(source_id.lower(), source_id.title())


def _join_sources(names: list[str]) -> str:
    """Join source names naturally: 'A and B' or 'A, B, and C'."""
    if len(names) == 0:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


class ForecastConfidenceLevel(Enum):
    """Three-tier confidence classification."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass
class ForecastConfidence:
    """Result of a cross-source confidence calculation."""

    level: ForecastConfidenceLevel
    rationale: str
    sources_compared: int
    source_names: list[str] = field(default_factory=list)


def _valid_sources(sources: list[SourceData]) -> list[SourceData]:
    """Return only sources that have usable forecast data."""
    return [s for s in sources if s.success and s.forecast is not None and s.forecast.has_data()]


def calculate_forecast_confidence(sources: list[SourceData]) -> ForecastConfidence:
    """
    Compute a confidence level by comparing the first forecast period across sources.

    Args:
        sources: List of :class:`~accessiweather.models.weather.SourceData` objects
            (one per weather provider).

    Returns:
        A :class:`ForecastConfidence` describing the level, rationale, and how
        many valid sources were included in the calculation.

    """
    valid = _valid_sources(sources)
    n = len(valid)
    names = [_display_name(s.source) for s in valid]
    joined = _join_sources(names)

    if n == 0:
        return ForecastConfidence(
            level=ForecastConfidenceLevel.LOW,
            rationale="No forecast sources available",
            sources_compared=0,
            source_names=[],
        )

    if n == 1:
        return ForecastConfidence(
            level=ForecastConfidenceLevel.MEDIUM,
            rationale=f"Based on {joined} — single source, no cross-reference available",
            sources_compared=1,
            source_names=names,
        )

    # --- 2+ sources: extract first-period metrics ---
    temps: list[float] = []
    precips: list[float] = []

    for s in valid:
        assert s.forecast is not None  # already filtered above
        if s.forecast.periods:
            p0 = s.forecast.periods[0]
            if p0.temperature is not None:
                temps.append(p0.temperature)
            if p0.precipitation_probability is not None:
                precips.append(p0.precipitation_probability)

    temp_spread = (max(temps) - min(temps)) if len(temps) >= 2 else 0.0
    precip_spread = (max(precips) - min(precips)) if len(precips) >= 2 else None

    # --- Apply thresholds ---
    if precip_spread is not None:
        # Both temperature AND precipitation data available
        if temp_spread <= _TEMP_HIGH and precip_spread <= _PRECIP_HIGH:
            return ForecastConfidence(
                level=ForecastConfidenceLevel.HIGH,
                rationale=f"{joined} agree on temperature and precipitation",
                sources_compared=n,
                source_names=names,
            )
        if temp_spread <= _TEMP_MED or precip_spread <= _PRECIP_MED:
            return ForecastConfidence(
                level=ForecastConfidenceLevel.MEDIUM,
                rationale=f"Moderate agreement between {joined}",
                sources_compared=n,
                source_names=names,
            )
        return ForecastConfidence(
            level=ForecastConfidenceLevel.LOW,
            rationale=f"{joined} show significant disagreement on temperature or precipitation",
            sources_compared=n,
            source_names=names,
        )

    # Temperature-only comparison
    if temp_spread <= _TEMP_HIGH:
        return ForecastConfidence(
            level=ForecastConfidenceLevel.HIGH,
            rationale=f"{joined} agree on temperature",
            sources_compared=n,
            source_names=names,
        )
    if temp_spread <= _TEMP_MED:
        return ForecastConfidence(
            level=ForecastConfidenceLevel.MEDIUM,
            rationale=f"Moderate temperature agreement between {joined}",
            sources_compared=n,
            source_names=names,
        )
    return ForecastConfidence(
        level=ForecastConfidenceLevel.LOW,
        rationale=f"{joined} show significant temperature disagreement",
        sources_compared=n,
        source_names=names,
    )
