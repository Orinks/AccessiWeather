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

# Visibility limits
VISIBILITY_MAX_MILES = 40.0
VISIBILITY_MAX_KM = 64.0

# Humidity bounds (%)
HUMIDITY_MIN = 0
HUMIDITY_MAX = 100

# Pressure limits
PRESSURE_MIN_INHG = 26.0
PRESSURE_MAX_INHG = 32.0
PRESSURE_MIN_MB = 880.0
PRESSURE_MAX_MB = 1085.0

# Wind speed warning threshold (mph)
WIND_SPEED_MAX_WARN_MPH = 250.0

# Temperature plausibility bounds (°F)
TEMP_MIN_PLAUSIBLE_F = -100.0
TEMP_MAX_PLAUSIBLE_F = 150.0

# Visibility caps by condition keyword (ordered most → least restrictive; first match wins)
_CONDITION_VISIBILITY_CAPS: list[tuple[str, float, float]] = [
    ("dense fog", 0.25, 0.4),
    ("fog", 0.6, 1.0),
    ("mist", 2.0, 3.2),
    ("haze", 6.0, 10.0),
    ("smoke", 6.0, 10.0),
    ("dust", 6.0, 10.0),
]


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


def _validate_visibility(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Cap visibility based on condition string and absolute maximum (40 mi / 64 km)."""
    if conditions.visibility_miles is None and conditions.visibility_km is None:
        return conditions, False

    # Start with the absolute maximum; tighten if the condition implies reduced visibility.
    cap_miles = VISIBILITY_MAX_MILES
    cap_km = VISIBILITY_MAX_KM

    if conditions.condition is not None:
        condition_lower = conditions.condition.lower()
        for keyword, miles, km in _CONDITION_VISIBILITY_CAPS:
            if keyword in condition_lower:
                cap_miles = miles
                cap_km = km
                break  # First match wins (list ordered from most to least restrictive)

    changed = False
    updates: dict[str, float] = {}

    if (
        conditions.visibility_miles is not None
        and isinstance(conditions.visibility_miles, (int, float))
        and conditions.visibility_miles > cap_miles
    ):
        logger.info(
            "Plausibility fix: visibility_miles %.2f -> %.2f (%s cap)",
            conditions.visibility_miles,
            cap_miles,
            "condition" if cap_miles < VISIBILITY_MAX_MILES else "absolute max",
        )
        updates["visibility_miles"] = cap_miles
        changed = True

    if (
        conditions.visibility_km is not None
        and isinstance(conditions.visibility_km, (int, float))
        and conditions.visibility_km > cap_km
    ):
        logger.info(
            "Plausibility fix: visibility_km %.2f -> %.2f (%s cap)",
            conditions.visibility_km,
            cap_km,
            "condition" if cap_km < VISIBILITY_MAX_KM else "absolute max",
        )
        updates["visibility_km"] = cap_km
        changed = True

    if changed:
        return replace(conditions, **updates), True
    return conditions, False


def _validate_humidity(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Clamp humidity to [0, 100]%. Log a warning if the value exceeds 100."""
    humidity = conditions.humidity
    if humidity is None or not isinstance(humidity, (int, float)):
        return conditions, False

    if humidity > HUMIDITY_MAX:
        logger.warning(
            "Plausibility warning: humidity=%d exceeds 100%% — clamping to 100",
            humidity,
        )

    clamped = max(HUMIDITY_MIN, min(HUMIDITY_MAX, int(humidity)))
    if clamped != humidity:
        return replace(conditions, humidity=clamped), True
    return conditions, False


def _validate_pressure(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Clamp pressure fields to physically plausible ranges."""
    changed = False
    updates: dict[str, float] = {}

    pressure_in = conditions.pressure_in
    if pressure_in is not None and isinstance(pressure_in, (int, float)):
        clamped = max(PRESSURE_MIN_INHG, min(PRESSURE_MAX_INHG, pressure_in))
        if clamped != pressure_in:
            logger.info(
                "Plausibility fix: pressure_in %.2f -> %.2f inHg (valid range %.0f–%.0f)",
                pressure_in,
                clamped,
                PRESSURE_MIN_INHG,
                PRESSURE_MAX_INHG,
            )
            updates["pressure_in"] = clamped
            changed = True

    pressure_mb = conditions.pressure_mb
    if pressure_mb is not None and isinstance(pressure_mb, (int, float)):
        clamped_mb = max(PRESSURE_MIN_MB, min(PRESSURE_MAX_MB, pressure_mb))
        if clamped_mb != pressure_mb:
            logger.info(
                "Plausibility fix: pressure_mb %.1f -> %.1f hPa (valid range %.0f–%.0f)",
                pressure_mb,
                clamped_mb,
                PRESSURE_MIN_MB,
                PRESSURE_MAX_MB,
            )
            updates["pressure_mb"] = clamped_mb
            changed = True

    if changed:
        return replace(conditions, **updates), True
    return conditions, False


def _validate_wind_speed(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Set negative wind speeds to 0; warn when mph exceeds physical plausibility."""
    changed = False
    updates: dict[str, float] = {}

    fields: list[tuple[str, float | None]] = [
        ("wind_speed_mph", conditions.wind_speed_mph),
        ("wind_speed_kph", conditions.wind_speed_kph),
        ("wind_speed", conditions.wind_speed),
    ]

    for field_name, value in fields:
        if value is None or not isinstance(value, (int, float)):
            continue
        if value < 0:
            logger.info("Plausibility fix: %s=%.1f -> 0 (negative wind speed)", field_name, value)
            updates[field_name] = 0.0
            changed = True
        elif field_name == "wind_speed_mph" and value > WIND_SPEED_MAX_WARN_MPH:
            logger.warning(
                "Plausibility warning: %s=%.1f exceeds %.0f mph — may be severe weather data,"
                " data retained",
                field_name,
                value,
                WIND_SPEED_MAX_WARN_MPH,
            )

    if changed:
        return replace(conditions, **updates), True
    return conditions, False


def _validate_dewpoint(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Dewpoint cannot exceed the actual temperature (thermodynamic constraint)."""
    dewpoint_f = conditions.dewpoint_f
    temp_f = conditions.temperature_f

    if (
        dewpoint_f is None
        or temp_f is None
        or not isinstance(dewpoint_f, (int, float))
        or not isinstance(temp_f, (int, float))
    ):
        return conditions, False

    if dewpoint_f > temp_f:
        logger.info(
            "Plausibility fix: dewpoint_f=%.1f -> %.1f (cannot exceed temperature_f=%.1f)",
            dewpoint_f,
            temp_f,
            temp_f,
        )
        return replace(conditions, dewpoint_f=temp_f), True

    return conditions, False


def _validate_precipitation(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Set negative precipitation amounts to 0."""
    changed = False
    updates: dict[str, float] = {}

    for field_name, value in [
        ("precipitation_in", conditions.precipitation_in),
        ("precipitation_mm", conditions.precipitation_mm),
    ]:
        if value is None or not isinstance(value, (int, float)):
            continue
        if value < 0:
            logger.info(
                "Plausibility fix: %s=%.3f -> 0 (negative precipitation)", field_name, value
            )
            updates[field_name] = 0.0
            changed = True

    if changed:
        return replace(conditions, **updates), True
    return conditions, False


def _validate_temperature_sanity(
    conditions: CurrentConditions,
    location: Location | None,
    now: datetime,
) -> tuple[CurrentConditions, bool]:
    """Warn when temperature_f is outside the physically plausible range. No correction applied."""
    temp_f = conditions.temperature_f
    if temp_f is None or not isinstance(temp_f, (int, float)):
        return conditions, False

    if temp_f < TEMP_MIN_PLAUSIBLE_F or temp_f > TEMP_MAX_PLAUSIBLE_F:
        logger.warning(
            "Plausibility warning: temperature_f=%.1f is outside plausible range "
            "(%.0f–%.0f °F) — data retained but may be erroneous",
            temp_f,
            TEMP_MIN_PLAUSIBLE_F,
            TEMP_MAX_PLAUSIBLE_F,
        )

    return conditions, False


# ---------------------------------------------------------------------------
# Public validator class
# ---------------------------------------------------------------------------

# Default pipeline: ordered list of validators applied in sequence.
_DEFAULT_VALIDATORS: list[ValidatorFn] = [
    _validate_uv_range,  # clamp before nighttime so 0 is already correct after clamping
    _validate_uv_nighttime,
    _validate_feels_like,
    _validate_visibility,
    _validate_humidity,
    _validate_pressure,
    _validate_wind_speed,
    _validate_dewpoint,
    _validate_precipitation,
    _validate_temperature_sanity,
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
