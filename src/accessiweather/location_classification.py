"""Location classification helpers shared by weather-source decisions."""

from __future__ import annotations

from typing import Any


def is_us_location(location: Any) -> bool:
    """
    Return whether a location should use US/NWS weather surfaces.

    Country codes are authoritative. Coordinate fallback is intentionally
    conservative near the Canadian border, where legacy/manual locations may
    lack ``country_code`` and otherwise look like US coordinates.
    """
    country_code = getattr(location, "country_code", None)
    if country_code:
        return str(country_code).upper() == "US"

    lat = float(getattr(location, "latitude", 0.0))
    lon = float(getattr(location, "longitude", 0.0))

    in_alaska_bounds = 51.0 <= lat <= 71.5 and -172.0 <= lon <= -130.0
    in_hawaii_bounds = 18.0 <= lat <= 23.0 and -161.0 <= lon <= -154.0
    if in_alaska_bounds or in_hawaii_bounds:
        return True

    in_continental_bounds = 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0
    if not in_continental_bounds:
        return False

    # Victoria/Vancouver Island and the lower mainland sit inside the broad
    # continental US box. Without a country code, avoid firing NWS /points at
    # Canadian coordinates in this ambiguous western border strip.
    in_western_canada_border_strip = lat >= 48.0 and -125.0 <= lon <= -122.0
    if in_western_canada_border_strip:
        return False

    # Great Lakes and St. Lawrence corridor coordinates overlap many Canadian
    # cities. Require a country code there too; geocoder-created locations have
    # one, while old/manual entries can still fall back to Open-Meteo safely.
    in_eastern_canada_border_strip = lat >= 43.0 and -95.0 < lon < -70.0
    return not in_eastern_canada_border_strip
