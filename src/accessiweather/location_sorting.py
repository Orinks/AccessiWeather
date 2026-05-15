"""Helpers for ordering saved locations."""

from __future__ import annotations

from collections.abc import Iterable
from math import atan2, cos, radians, sin, sqrt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Location

LOCATION_SORT_ALPHABETICAL = "alphabetical"
LOCATION_SORT_NEAREST_CURRENT = "nearest_current"


def normalize_location_sort_order(value: object) -> str:
    """Return a supported location sort order."""
    if value == LOCATION_SORT_NEAREST_CURRENT:
        return LOCATION_SORT_NEAREST_CURRENT
    return LOCATION_SORT_ALPHABETICAL


def location_name_sort_key(location: Location) -> tuple[str, str]:
    """Return a stable, case-insensitive sort key for saved locations."""
    return (location.name.casefold(), location.name)


def sort_locations_for_display(
    locations: Iterable[Location],
    sort_order: object,
    *,
    anchor: Location | None = None,
) -> list[Location]:
    """Sort saved locations for user-facing lists."""
    sorted_locations = sorted(locations, key=location_name_sort_key)
    if normalize_location_sort_order(sort_order) != LOCATION_SORT_NEAREST_CURRENT or anchor is None:
        return sorted_locations

    return sorted(
        sorted_locations,
        key=lambda location: (_distance_miles(anchor, location), location_name_sort_key(location)),
    )


def _distance_miles(first: Location, second: Location) -> float:
    """Return the great-circle distance between two locations in miles."""
    try:
        first_lat = float(first.latitude)
        first_lon = float(first.longitude)
        second_lat = float(second.latitude)
        second_lon = float(second.longitude)
    except (TypeError, ValueError):
        return float("inf")

    earth_radius_miles = 3958.7613
    lat1 = radians(first_lat)
    lat2 = radians(second_lat)
    delta_lat = radians(second_lat - first_lat)
    delta_lon = radians(second_lon - first_lon)

    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(max(0, 1 - a)))
    return earth_radius_miles * c
