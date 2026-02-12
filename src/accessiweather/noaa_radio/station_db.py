"""NOAA Weather Radio station database with geolocation lookup."""

from __future__ import annotations

import math
from dataclasses import dataclass

from accessiweather.noaa_radio.stations import Station

# Earth's mean radius in kilometres
_EARTH_RADIUS_KM = 6371.0


@dataclass
class StationResult:
    """A station paired with its distance from a query point."""

    station: Station
    distance_km: float


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in km between two points."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Embedded station data – representative stations across US regions
# ---------------------------------------------------------------------------
_STATIONS: list[Station] = [
    # Northeast
    Station("KEC49", 162.550, "New York City, NY", 40.7128, -74.0060, "NY"),
    Station("WXJ90", 162.475, "Boston, MA", 42.3601, -71.0589, "MA"),
    Station("KWO35", 162.400, "Philadelphia, PA", 39.9526, -75.1652, "PA"),
    Station("WXK48", 162.525, "Hartford, CT", 41.7658, -72.6734, "CT"),
    Station("KZZ30", 162.450, "Burlington, VT", 44.4759, -73.2121, "VT"),
    # Southeast
    Station("KEC80", 162.550, "Miami, FL", 25.7617, -80.1918, "FL"),
    Station("WXK62", 162.475, "Atlanta, GA", 33.7490, -84.3880, "GA"),
    Station("KIH24", 162.400, "Charlotte, NC", 35.2271, -80.8431, "NC"),
    Station("WXL58", 162.525, "Nashville, TN", 36.1627, -86.7816, "TN"),
    Station("KJY94", 162.450, "Richmond, VA", 37.5407, -77.4360, "VA"),
    # Midwest
    Station("KEC57", 162.550, "Chicago, IL", 41.8781, -87.6298, "IL"),
    Station("WNG634", 162.475, "Detroit, MI", 42.3314, -83.0458, "MI"),
    Station("WXJ39", 162.400, "Minneapolis, MN", 44.9778, -93.2650, "MN"),
    Station("KZZ42", 162.525, "St. Louis, MO", 38.6270, -90.1994, "MO"),
    Station("WXK76", 162.450, "Columbus, OH", 39.9612, -82.9988, "OH"),
    # South Central
    Station("KEC58", 162.550, "Dallas, TX", 32.7767, -96.7970, "TX"),
    Station("WXL41", 162.475, "Houston, TX", 29.7604, -95.3698, "TX"),
    Station("KJY76", 162.400, "New Orleans, LA", 29.9511, -90.0715, "LA"),
    Station("WXK89", 162.525, "Oklahoma City, OK", 35.4676, -97.5164, "OK"),
    Station("KIH57", 162.450, "Little Rock, AR", 34.7465, -92.2896, "AR"),
    # Mountain West
    Station("KEC60", 162.550, "Denver, CO", 39.7392, -104.9903, "CO"),
    Station("WXJ52", 162.475, "Salt Lake City, UT", 40.7608, -111.8910, "UT"),
    Station("KZZ61", 162.400, "Phoenix, AZ", 33.4484, -112.0740, "AZ"),
    Station("WXK33", 162.525, "Albuquerque, NM", 35.0844, -106.6504, "NM"),
    Station("KIH83", 162.450, "Boise, ID", 43.6150, -116.2023, "ID"),
    # Pacific West
    Station("KEC62", 162.550, "Los Angeles, CA", 34.0522, -118.2437, "CA"),
    Station("WXL29", 162.475, "San Francisco, CA", 37.7749, -122.4194, "CA"),
    Station("KJY60", 162.400, "Seattle, WA", 47.6062, -122.3321, "WA"),
    Station("WXK52", 162.525, "Portland, OR", 45.5152, -122.6784, "OR"),
    # Alaska & Hawaii
    Station("KEC65", 162.550, "Anchorage, AK", 61.2181, -149.9003, "AK"),
    Station("WXJ71", 162.475, "Honolulu, HI", 21.3069, -157.8583, "HI"),
]


class StationDatabase:
    """In-memory database of NOAA Weather Radio stations."""

    def __init__(self, stations: list[Station] | None = None) -> None:
        """Initialize the station database with optional custom stations."""
        self._stations = list(stations) if stations is not None else list(_STATIONS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all_stations(self) -> list[Station]:
        """Return all stations in the database."""
        return list(self._stations)

    def get_stations_by_state(self, state: str) -> list[Station]:
        """Return stations filtered by US state abbreviation (case-insensitive)."""
        state_upper = state.upper()
        return [s for s in self._stations if s.state.upper() == state_upper]

    def find_nearest(self, lat: float, lon: float, limit: int = 5) -> list[StationResult]:
        """Return the *limit* nearest stations sorted by distance ascending."""
        results = [
            StationResult(station=s, distance_km=_haversine(lat, lon, s.lat, s.lon))
            for s in self._stations
        ]
        results.sort(key=lambda r: r.distance_km)
        return results[:limit]
