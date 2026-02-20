"""
Temperature anomaly calculations vs historical baseline.

Provides pure functions for computing how current temperatures compare to
historical norms, producing accessible plain-English callouts for screen readers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from accessiweather.weather_history import HistoricalWeatherData

__all__ = [
    "HistoricalBaseline",
    "TemperatureAnomaly",
    "build_historical_baseline",
    "compute_temperature_anomaly",
]

# Threshold below which a delta is considered "near normal"
_NEAR_NORMAL_THRESHOLD = 2.0


@dataclass
class HistoricalBaseline:
    """Aggregated historical temperature baseline from multiple samples."""

    baseline_mean_temp: float
    sample_count: int
    years_used: list[int] = field(default_factory=list)


@dataclass
class TemperatureAnomaly:
    """Difference between current temperature and historical baseline."""

    delta: float           # current_temp - baseline_mean_temp (positive = warmer)
    callout: str           # accessible plain-English description
    baseline: HistoricalBaseline


def build_historical_baseline(
    samples: list[HistoricalWeatherData],
) -> HistoricalBaseline | None:
    """
    Build a baseline from a list of historical weather samples.

    Filters out samples with no temperature_mean data.  Returns None when
    fewer than 2 valid samples are available (insufficient for a meaningful
    baseline comparison).

    Args:
        samples: Historical weather records, typically one per past year for the
            same calendar date.

    Returns:
        A :class:`HistoricalBaseline`, or ``None`` if there is insufficient data.

    """
    valid = [s for s in samples if s.temperature_mean is not None]

    if len(valid) < 2:
        return None

    baseline_mean = sum(s.temperature_mean for s in valid) / len(valid)
    years = [s.date.year for s in valid]

    return HistoricalBaseline(
        baseline_mean_temp=baseline_mean,
        sample_count=len(valid),
        years_used=years,
    )


def compute_temperature_anomaly(
    current_temp: float,
    baseline: HistoricalBaseline,
) -> TemperatureAnomaly:
    """
    Compute a temperature anomaly and generate an accessible callout string.

    Thresholds:
    - ``|delta| < 2.0`` → 'Near normal for this time of year'
    - ``delta >= 2.0``  → '{delta:.1f}°F above normal for this time of year'
    - ``delta <= -2.0`` → '{abs(delta):.1f}°F below normal for this time of year'

    Args:
        current_temp: The current observed temperature in °F.
        baseline: Pre-computed historical baseline for this location and date.

    Returns:
        A :class:`TemperatureAnomaly` with the delta and accessible callout text.

    """
    delta = current_temp - baseline.baseline_mean_temp

    if abs(delta) < _NEAR_NORMAL_THRESHOLD:
        callout = "Near normal for this time of year"
    elif delta > 0:
        callout = f"{delta:.1f}°F above normal for this time of year"
    else:
        callout = f"{abs(delta):.1f}°F below normal for this time of year"

    return TemperatureAnomaly(delta=delta, callout=callout, baseline=baseline)
