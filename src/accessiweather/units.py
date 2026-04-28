"""Helpers for resolving location-aware display unit systems."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from .utils.temperature_utils import TemperatureUnit

if TYPE_CHECKING:
    from .models import Location


class DisplayUnitSystem(str, Enum):
    """Supported single-unit display systems."""

    US = "us"
    UK = "uk"
    CA = "ca"
    SI = "si"


_COUNTRY_UNIT_SYSTEMS: dict[str, DisplayUnitSystem] = {
    "US": DisplayUnitSystem.US,
    "GB": DisplayUnitSystem.UK,
    "CA": DisplayUnitSystem.CA,
}


def resolve_auto_unit_system(location: Location | None) -> DisplayUnitSystem:
    """Return the auto-selected unit system for a location."""
    country_code = (getattr(location, "country_code", None) or "").upper()
    return _COUNTRY_UNIT_SYSTEMS.get(country_code, DisplayUnitSystem.SI)


def resolve_temperature_unit_preference(
    preference: str | None,
    location: Location | None = None,
) -> TemperatureUnit:
    """Resolve a stored unit preference to the effective temperature display mode."""
    normalized = (preference or "both").strip().lower()
    if normalized in {"fahrenheit", "f"}:
        return TemperatureUnit.FAHRENHEIT
    if normalized in {"celsius", "c"}:
        return TemperatureUnit.CELSIUS
    if normalized == "auto":
        return (
            TemperatureUnit.FAHRENHEIT
            if resolve_auto_unit_system(location) == DisplayUnitSystem.US
            else TemperatureUnit.CELSIUS
        )
    return TemperatureUnit.BOTH


def resolve_display_unit_system(
    preference: str | None,
    location: Location | None = None,
) -> DisplayUnitSystem | None:
    """Resolve a stored preference to an explicit display system when needed."""
    normalized = (preference or "both").strip().lower()
    if normalized == "auto":
        return resolve_auto_unit_system(location)
    return None
