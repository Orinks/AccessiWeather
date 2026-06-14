"""Unit normalization helpers for Open-Meteo payloads."""

from __future__ import annotations

from .provider_normalization import normalize_visibility_pair

CM_PER_INCH = 2.54
FEET_PER_METER = 3.28084
INCHES_PER_FOOT = 12
VISIBILITY_CAP_MILES = 10.0


def _unit_text(unit: str | None) -> str:
    return (unit or "").strip().lower().replace(" ", "_")


def normalize_snow_depth_to_inches_and_cm(
    value: float | int | None,
    unit: str | None,
) -> tuple[float | None, float | None]:
    """Return Open-Meteo snow depth normalized to inches and centimeters."""
    if value is None:
        return None, None

    numeric = float(value)
    unit_text = _unit_text(unit)

    if "ft" in unit_text or "feet" in unit_text:
        inches = numeric * INCHES_PER_FOOT
    elif "mm" in unit_text or "millimeter" in unit_text or "millimetre" in unit_text:
        inches = numeric / 25.4
    elif "cm" in unit_text or "centimeter" in unit_text or "centimetre" in unit_text:
        inches = numeric / CM_PER_INCH
    elif unit_text in {"in", "inch", "inches"}:
        inches = numeric
    else:
        # Open-Meteo uses meters when no precipitation_unit override is applied.
        inches = numeric * FEET_PER_METER * INCHES_PER_FOOT

    return inches, inches * CM_PER_INCH


def normalize_height_to_feet(value: float | int | None, unit: str | None) -> float | None:
    """Return a height value normalized to feet."""
    if value is None:
        return None

    numeric = float(value)
    unit_text = _unit_text(unit)

    if "ft" in unit_text or "feet" in unit_text:
        return numeric
    if "km" in unit_text or "kilometer" in unit_text or "kilometre" in unit_text:
        return numeric * 1000 * FEET_PER_METER

    return numeric * FEET_PER_METER


def normalize_visibility_to_miles_and_km(
    value: float | int | None,
    unit: str | None,
) -> tuple[float | None, float | None]:
    """Return Open-Meteo visibility normalized to capped miles and kilometers."""
    visibility = normalize_visibility_pair(value, unit, cap_miles=VISIBILITY_CAP_MILES)
    return visibility.miles, visibility.kilometers
