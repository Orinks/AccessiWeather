"""
Historical temperature anomaly detection for AccessiWeather.

Computes a multi-year baseline temperature for a given date and compares
current conditions against it to produce concise anomaly callouts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .openmeteo_client import OpenMeteoApiClient

logger = logging.getLogger(__name__)

YEARS_OF_HISTORY = 5
MIN_YEARS_REQUIRED = 3
DATE_WINDOW_DAYS = 7


@dataclass
class AnomalyCallout:
    """Describes how current temperature compares to the historical baseline."""

    temp_anomaly: float  # positive = warmer, negative = cooler (°F)
    temp_anomaly_description: str  # human-readable line
    precip_anomaly_description: str | None
    severity: Literal["normal", "notable", "significant"]


def _classify_severity(anomaly_f: float) -> Literal["normal", "notable", "significant"]:
    """Classify anomaly magnitude into severity buckets."""
    abs_diff = abs(anomaly_f)
    if abs_diff >= 5.0:
        return "significant"
    if abs_diff >= 2.0:
        return "notable"
    return "normal"


def _build_description(anomaly_f: float, years: int) -> str:
    """Build a human-readable anomaly description."""
    abs_diff = abs(anomaly_f)
    direction = "warmer" if anomaly_f > 0 else "cooler"
    if abs_diff < 0.5:
        return f"Near the {years}-year average for this date."
    return (
        f"Currently {abs_diff:.1f}\u00b0F {direction} than the {years}-year average for this date."
    )


def compute_anomaly(
    lat: float,
    lon: float,
    current_temp_f: float,
    current_date: date,
    client: OpenMeteoApiClient,
) -> AnomalyCallout | None:
    """
    Compute historical temperature anomaly for the given location and date.

    Fetches the last YEARS_OF_HISTORY years of daily temperature data for a
    +/-DATE_WINDOW_DAYS window around current_date and computes the baseline mean.

    Returns None if fewer than MIN_YEARS_REQUIRED years of data are available
    or if all fetches fail.
    """
    yearly_means: list[float] = []

    for years_back in range(1, YEARS_OF_HISTORY + 1):
        try:
            anchor = current_date.replace(year=current_date.year - years_back)
        except ValueError:
            # Feb 29 on a non-leap year
            anchor = current_date.replace(year=current_date.year - years_back, day=28)

        start = anchor - timedelta(days=DATE_WINDOW_DAYS)
        end = anchor + timedelta(days=DATE_WINDOW_DAYS)

        # Archive API lags ~5 days behind present; clamp to avoid requesting
        # dates that are too recent to have archive data.
        too_recent = date.today() - timedelta(days=5)
        if end > too_recent:
            end = too_recent
        if start >= end:
            logger.debug("Skipping year -%d: date window not yet archived", years_back)
            continue

        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": ["temperature_2m_mean"],
                "temperature_unit": "fahrenheit",
                "timezone": "auto",
            }
            response = client._make_request("archive", params, use_archive=True)
        except Exception as exc:
            logger.debug("Anomaly archive fetch failed for year -%d: %s", years_back, exc)
            continue

        if not response or "daily" not in response:
            continue

        temps = response["daily"].get("temperature_2m_mean") or []
        valid = [t for t in temps if t is not None]
        if not valid:
            continue

        yearly_means.append(sum(valid) / len(valid))

    if len(yearly_means) < MIN_YEARS_REQUIRED:
        logger.debug(
            "Insufficient historical data: %d years (need %d)",
            len(yearly_means),
            MIN_YEARS_REQUIRED,
        )
        return None

    baseline = sum(yearly_means) / len(yearly_means)
    anomaly = current_temp_f - baseline
    severity = _classify_severity(anomaly)
    description = _build_description(anomaly, len(yearly_means))

    return AnomalyCallout(
        temp_anomaly=anomaly,
        temp_anomaly_description=description,
        precip_anomaly_description=None,
        severity=severity,
    )
