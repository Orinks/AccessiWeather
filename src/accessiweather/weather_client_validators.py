"""Post-fusion plausibility validation layer for weather data."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.weather import CurrentConditions, Location

logger = logging.getLogger(__name__)

# UV index physical maximum (WMO scale tops out ~17 in extreme conditions)
UV_INDEX_MAX = 20.0
UV_INDEX_MIN = 0.0

# Feels-like divergence threshold (°F). Beyond this, log a warning.
FEELS_LIKE_DIVERGENCE_THRESHOLD_F = 50.0


def _solar_elevation_deg(lat_deg: float, lon_deg: float, utc_time: datetime) -> float:
    """
    Compute the solar elevation angle (degrees) for a location at a UTC time.

    Positive values indicate the sun is above the horizon (daytime).
    Uses a standard solar position approximation; accuracy is within ~1°.
    """
    day_of_year = utc_time.timetuple().tm_yday

    # Solar declination
    decl = math.radians(23.45 * math.sin(math.radians(360.0 / 365.0 * (day_of_year - 81))))

    # Equation of time correction (minutes)
    b = math.radians(360.0 / 365.0 * (day_of_year - 81))
    eot_minutes = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

    # UTC decimal hours
    utc_hours = utc_time.hour + utc_time.minute / 60.0 + utc_time.second / 3600.0

    # Apparent solar time (hours)
    solar_time = utc_hours + lon_deg / 15.0 + eot_minutes / 60.0

    # Hour angle (degrees, then radians)
    hour_angle = math.radians(15.0 * (solar_time - 12.0))

    lat = math.radians(lat_deg)
    sin_elev = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(
        hour_angle
    )
    # Clamp to [-1, 1] to guard against floating-point drift
    sin_elev = max(-1.0, min(1.0, sin_elev))
    return math.degrees(math.asin(sin_elev))


def _is_daytime(lat: float, lon: float, now: datetime) -> bool:
    """Return True when the sun is above the horizon at the given location and time."""
    utc_now = now.astimezone(UTC) if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return _solar_elevation_deg(lat, lon, utc_now) > 0.0


# ---------------------------------------------------------------------------
# Individual validator functions
# Each has signature:
#   (conditions, location, now) -> (corrected_conditions, changed: bool)
# ---------------------------------------------------------------------------

ValidatorFn = Callable[
    ["CurrentConditions", "Location | None", datetime],
    tuple["CurrentConditions", bool],
]


def _validate_uv_nighttime(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Zero out UV index when the sun is below the horizon."""
    if (
        conditions.uv_index is None
        or not isinstance(conditions.uv_index, (int, float))
        or conditions.uv_index == 0.0
    ):
        return conditions, False

    if location is None:
        # No location data — cannot determine daytime, skip this check.
        logger.debug("UV nighttime check skipped: no location data")
        return conditions, False

    if not _is_daytime(location.latitude, location.longitude, now):
        logger.info(
            "Plausibility fix: UV index %.1f -> 0 (nighttime at %.4f, %.4f)",
            conditions.uv_index,
            location.latitude,
            location.longitude,
        )
        return replace(conditions, uv_index=0.0), True

    return conditions, False


def _validate_uv_range(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Clamp UV index to [0, UV_INDEX_MAX]."""
    uv = conditions.uv_index
    if uv is None or not isinstance(uv, (int, float)):
        return conditions, False

    clamped = max(UV_INDEX_MIN, min(UV_INDEX_MAX, uv))
    if clamped != uv:
        logger.info(
            "Plausibility fix: UV index %.1f clamped to %.1f (valid range 0–%g)",
            uv,
            clamped,
            UV_INDEX_MAX,
        )
        return replace(conditions, uv_index=clamped), True

    return conditions, False


def _validate_feels_like(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Warn when feels-like temperature diverges too far from actual temperature."""
    feels_f = conditions.feels_like_f
    temp_f = (
        conditions.temperature_f if conditions.temperature_f is not None else conditions.temperature
    )

    if (
        feels_f is None
        or temp_f is None
        or not isinstance(feels_f, (int, float))
        or not isinstance(temp_f, (int, float))
    ):
        return conditions, False

    divergence = abs(feels_f - temp_f)
    if divergence > FEELS_LIKE_DIVERGENCE_THRESHOLD_F:
        logger.warning(
            "Plausibility warning: feels_like_f=%.1f deviates %.1f°F from temperature_f=%.1f "
            "(threshold %g°F) — data retained but may be erroneous",
            feels_f,
            divergence,
            temp_f,
            FEELS_LIKE_DIVERGENCE_THRESHOLD_F,
        )

    # Flag only — no correction applied
    return conditions, False


# ---------------------------------------------------------------------------
# Public validator class
# ---------------------------------------------------------------------------

# Default pipeline: ordered list of validators applied in sequence.
_DEFAULT_VALIDATORS: list[ValidatorFn] = [
    _validate_uv_range,  # clamp before nighttime so 0 is already correct after clamping
    _validate_uv_nighttime,
    _validate_feels_like,
]


class PlausibilityValidator:
    """
    Post-fusion plausibility validation layer.

    Runs a configurable pipeline of validators against merged
    ``CurrentConditions`` and corrects or flags physically impossible values.

    To add a new validator, write a function with the signature::

        def my_validator(
            conditions: CurrentConditions,
            location: Location | None,
            now: datetime,
        ) -> tuple[CurrentConditions, bool]:
            ...

    and append it to ``PlausibilityValidator.validators`` or pass a custom
    list to the constructor.
    """

    def __init__(self, validators: list[ValidatorFn] | None = None) -> None:
        """Initialize with an optional custom validator pipeline."""
        self.validators: list[ValidatorFn] = (
            validators if validators is not None else list(_DEFAULT_VALIDATORS)
        )

    def validate(
        self,
        conditions: CurrentConditions,
        location: Location | None = None,
        now: datetime | None = None,
    ) -> CurrentConditions:
        """
        Run all validators against *conditions* and return the (possibly corrected) result.

        Args:
            conditions: Merged ``CurrentConditions`` from the fusion engine.
            location: Location metadata used for sun-position checks.
            now: Current UTC time. Defaults to ``datetime.now(UTC)`` when omitted.

        Returns:
            Corrected ``CurrentConditions``.  The original object is never mutated.

        """
        if now is None:
            now = datetime.now(UTC)

        current = conditions
        for validator in self.validators:
            current, _ = validator(current, location, now)

        return current
