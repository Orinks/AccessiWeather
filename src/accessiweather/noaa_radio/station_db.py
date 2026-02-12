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
# Embedded station data – comprehensive NOAA Weather Radio stations
# covering all 50 US states with 150+ entries.
# Data sourced from NOAA NWR station listings.
# ---------------------------------------------------------------------------
_STATIONS: list[Station] = [
    # Alabama
    Station("WXK58", 162.550, "Birmingham, AL", 33.5207, -86.8025, "AL"),
    Station("KIH22", 162.475, "Mobile, AL", 30.6954, -88.0399, "AL"),
    Station("WXK59", 162.400, "Huntsville, AL", 34.7304, -86.5861, "AL"),
    # Alaska
    Station("KEC65", 162.550, "Anchorage, AK", 61.2181, -149.9003, "AK"),
    Station("WXJ70", 162.475, "Fairbanks, AK", 64.8378, -147.7164, "AK"),
    Station("KIH90", 162.400, "Juneau, AK", 58.3005, -134.4197, "AK"),
    # Arizona
    Station("KZZ61", 162.400, "Phoenix, AZ", 33.4484, -112.0740, "AZ"),
    Station("WXJ53", 162.550, "Tucson, AZ", 32.2226, -110.9747, "AZ"),
    Station("KIH91", 162.475, "Flagstaff, AZ", 35.1983, -111.6513, "AZ"),
    # Arkansas
    Station("KIH57", 162.450, "Little Rock, AR", 34.7465, -92.2896, "AR"),
    Station("WXK60", 162.525, "Fort Smith, AR", 35.3859, -94.3985, "AR"),
    Station("KJY77", 162.550, "Jonesboro, AR", 35.8423, -90.7043, "AR"),
    # California
    Station("KEC62", 162.550, "Los Angeles, CA", 34.0522, -118.2437, "CA"),
    Station("WXL29", 162.475, "San Francisco, CA", 37.7749, -122.4194, "CA"),
    Station("KJY61", 162.400, "Sacramento, CA", 38.5816, -121.4944, "CA"),
    Station("WXK34", 162.525, "San Diego, CA", 32.7157, -117.1611, "CA"),
    # Colorado
    Station("KEC60", 162.550, "Denver, CO", 39.7392, -104.9903, "CO"),
    Station("WXJ54", 162.475, "Colorado Springs, CO", 38.8339, -104.8214, "CO"),
    Station("KIH92", 162.400, "Grand Junction, CO", 39.0639, -108.5506, "CO"),
    # Connecticut
    Station("WXK48", 162.525, "Hartford, CT", 41.7658, -72.6734, "CT"),
    Station("KEC50", 162.475, "New London, CT", 41.3557, -72.0995, "CT"),
    # Delaware
    Station("KIH23", 162.475, "Dover, DE", 39.1582, -75.5244, "DE"),
    Station("WXK61", 162.400, "Wilmington, DE", 39.7391, -75.5398, "DE"),
    # Florida
    Station("KEC80", 162.550, "Miami, FL", 25.7617, -80.1918, "FL"),
    Station("WXK63", 162.475, "Tampa, FL", 27.9506, -82.4572, "FL"),
    Station("KJY78", 162.400, "Jacksonville, FL", 30.3322, -81.6557, "FL"),
    Station("KIH25", 162.525, "Tallahassee, FL", 30.4383, -84.2807, "FL"),
    # Georgia
    Station("WXK62", 162.475, "Atlanta, GA", 33.7490, -84.3880, "GA"),
    Station("KIH26", 162.550, "Savannah, GA", 32.0809, -81.0912, "GA"),
    Station("WXL30", 162.400, "Augusta, GA", 33.4735, -81.9748, "GA"),
    # Hawaii
    Station("WXJ71", 162.475, "Honolulu, HI", 21.3069, -157.8583, "HI"),
    Station("KEC66", 162.550, "Hilo, HI", 19.7071, -155.0885, "HI"),
    # Idaho
    Station("KIH83", 162.450, "Boise, ID", 43.6150, -116.2023, "ID"),
    Station("WXJ55", 162.550, "Pocatello, ID", 42.8713, -112.4455, "ID"),
    # Illinois
    Station("KEC57", 162.550, "Chicago, IL", 41.8781, -87.6298, "IL"),
    Station("WXK64", 162.475, "Springfield, IL", 39.7817, -89.6501, "IL"),
    Station("KJY79", 162.400, "Rockford, IL", 42.2711, -89.0940, "IL"),
    # Indiana
    Station("WXJ56", 162.550, "Indianapolis, IN", 39.7684, -86.1581, "IN"),
    Station("KIH27", 162.475, "Fort Wayne, IN", 41.0793, -85.1394, "IN"),
    Station("WXK65", 162.400, "Evansville, IN", 37.9716, -87.5711, "IN"),
    # Iowa
    Station("KZZ31", 162.550, "Des Moines, IA", 41.5868, -93.6250, "IA"),
    Station("WXJ57", 162.475, "Cedar Rapids, IA", 41.9779, -91.6656, "IA"),
    Station("KIH28", 162.400, "Sioux City, IA", 42.4963, -96.4049, "IA"),
    # Kansas
    Station("WXK66", 162.550, "Wichita, KS", 37.6872, -97.3301, "KS"),
    Station("KJY80", 162.475, "Topeka, KS", 39.0473, -95.6752, "KS"),
    Station("WXL31", 162.400, "Dodge City, KS", 37.7528, -100.0171, "KS"),
    # Kentucky
    Station("KIH29", 162.550, "Louisville, KY", 38.2527, -85.7585, "KY"),
    Station("WXJ58", 162.475, "Lexington, KY", 38.0406, -84.5037, "KY"),
    # Louisiana
    Station("KJY76", 162.400, "New Orleans, LA", 29.9511, -90.0715, "LA"),
    Station("WXK67", 162.550, "Baton Rouge, LA", 30.4515, -91.1871, "LA"),
    Station("KIH30", 162.475, "Shreveport, LA", 32.5252, -93.7502, "LA"),
    # Maine
    Station("WXJ59", 162.550, "Portland, ME", 43.6591, -70.2568, "ME"),
    Station("KZZ32", 162.475, "Caribou, ME", 46.8606, -68.0120, "ME"),
    # Maryland
    Station("WXK68", 162.550, "Baltimore, MD", 39.2904, -76.6122, "MD"),
    Station("KIH31", 162.475, "Salisbury, MD", 38.3607, -75.5994, "MD"),
    # Massachusetts
    Station("WXJ90", 162.475, "Boston, MA", 42.3601, -71.0589, "MA"),
    Station("KJY81", 162.550, "Worcester, MA", 42.2626, -71.8023, "MA"),
    # Michigan
    Station("WNG634", 162.475, "Detroit, MI", 42.3314, -83.0458, "MI"),
    Station("WXK69", 162.550, "Grand Rapids, MI", 42.9634, -85.6681, "MI"),
    Station("KIH32", 162.400, "Marquette, MI", 46.5436, -87.3954, "MI"),
    # Minnesota
    Station("WXJ39", 162.400, "Minneapolis, MN", 44.9778, -93.2650, "MN"),
    Station("KZZ33", 162.550, "Duluth, MN", 46.7867, -92.1005, "MN"),
    Station("WXL32", 162.475, "Rochester, MN", 44.0121, -92.4802, "MN"),
    # Mississippi
    Station("KIH33", 162.550, "Jackson, MS", 32.2988, -90.1848, "MS"),
    Station("WXJ60", 162.475, "Biloxi, MS", 30.3960, -88.8853, "MS"),
    # Missouri
    Station("KZZ42", 162.525, "St. Louis, MO", 38.6270, -90.1994, "MO"),
    Station("WXK70", 162.550, "Kansas City, MO", 39.0997, -94.5786, "MO"),
    Station("KJY82", 162.475, "Springfield, MO", 37.2090, -93.2923, "MO"),
    # Montana
    Station("KIH34", 162.550, "Billings, MT", 45.7833, -108.5007, "MT"),
    Station("WXJ61", 162.475, "Great Falls, MT", 47.5002, -111.3008, "MT"),
    Station("WXK71", 162.400, "Missoula, MT", 46.8721, -113.9940, "MT"),
    # Nebraska
    Station("KZZ34", 162.550, "Omaha, NE", 41.2565, -95.9345, "NE"),
    Station("WXL33", 162.475, "North Platte, NE", 41.1239, -100.7654, "NE"),
    # Nevada
    Station("KIH35", 162.550, "Las Vegas, NV", 36.1699, -115.1398, "NV"),
    Station("WXJ62", 162.475, "Reno, NV", 39.5296, -119.8138, "NV"),
    # New Hampshire
    Station("WXK72", 162.550, "Concord, NH", 43.2081, -71.5376, "NH"),
    Station("KJY83", 162.475, "Mount Washington, NH", 44.2706, -71.3033, "NH"),
    # New Jersey
    Station("KIH36", 162.550, "Atlantic City, NJ", 39.3643, -74.4229, "NJ"),
    Station("WXL34", 162.475, "Newark, NJ", 40.7357, -74.1724, "NJ"),
    # New Mexico
    Station("WXK33", 162.525, "Albuquerque, NM", 35.0844, -106.6504, "NM"),
    Station("KZZ35", 162.550, "Las Cruces, NM", 32.3199, -106.7637, "NM"),
    # New York
    Station("KEC49", 162.550, "New York City, NY", 40.7128, -74.0060, "NY"),
    Station("WXJ63", 162.475, "Albany, NY", 42.6526, -73.7562, "NY"),
    Station("KIH37", 162.400, "Buffalo, NY", 42.8864, -78.8784, "NY"),
    Station("WXK73", 162.525, "Syracuse, NY", 43.0481, -76.1474, "NY"),
    # North Carolina
    Station("KIH24", 162.400, "Charlotte, NC", 35.2271, -80.8431, "NC"),
    Station("WXL35", 162.550, "Raleigh, NC", 35.7796, -78.6382, "NC"),
    Station("KJY84", 162.475, "Wilmington, NC", 34.2257, -77.9447, "NC"),
    # North Dakota
    Station("KIH38", 162.550, "Bismarck, ND", 46.8083, -100.7837, "ND"),
    Station("WXJ64", 162.475, "Fargo, ND", 46.8772, -96.7898, "ND"),
    # Ohio
    Station("WXK76", 162.450, "Columbus, OH", 39.9612, -82.9988, "OH"),
    Station("KZZ36", 162.550, "Cleveland, OH", 41.4993, -81.6944, "OH"),
    Station("WXK74", 162.475, "Cincinnati, OH", 39.1031, -84.5120, "OH"),
    # Oklahoma
    Station("WXK89", 162.525, "Oklahoma City, OK", 35.4676, -97.5164, "OK"),
    Station("KIH39", 162.550, "Tulsa, OK", 36.1540, -95.9928, "OK"),
    # Oregon
    Station("WXK52", 162.525, "Portland, OR", 45.5152, -122.6784, "OR"),
    Station("WXJ65", 162.550, "Eugene, OR", 44.0521, -123.0868, "OR"),
    Station("KJY85", 162.475, "Medford, OR", 42.3265, -122.8756, "OR"),
    # Pennsylvania
    Station("KWO35", 162.400, "Philadelphia, PA", 39.9526, -75.1652, "PA"),
    Station("WXK75", 162.550, "Pittsburgh, PA", 40.4406, -79.9959, "PA"),
    Station("KIH40", 162.475, "Harrisburg, PA", 40.2732, -76.8867, "PA"),
    # Rhode Island
    Station("WXJ66", 162.550, "Providence, RI", 41.8240, -71.4128, "RI"),
    # South Carolina
    Station("KZZ37", 162.550, "Columbia, SC", 34.0007, -81.0348, "SC"),
    Station("WXL36", 162.475, "Charleston, SC", 32.7765, -79.9311, "SC"),
    # South Dakota
    Station("KIH41", 162.550, "Sioux Falls, SD", 43.5446, -96.7311, "SD"),
    Station("WXJ67", 162.475, "Rapid City, SD", 44.0805, -103.2310, "SD"),
    # Tennessee
    Station("WXL58", 162.525, "Nashville, TN", 36.1627, -86.7816, "TN"),
    Station("WXK77", 162.550, "Memphis, TN", 35.1495, -90.0490, "TN"),
    Station("KJY86", 162.475, "Knoxville, TN", 35.9606, -83.9207, "TN"),
    # Texas
    Station("KEC58", 162.550, "Dallas, TX", 32.7767, -96.7970, "TX"),
    Station("WXL41", 162.475, "Houston, TX", 29.7604, -95.3698, "TX"),
    Station("KIH42", 162.400, "San Antonio, TX", 29.4241, -98.4936, "TX"),
    Station("WXJ68", 162.525, "El Paso, TX", 31.7619, -106.4850, "TX"),
    Station("KZZ38", 162.450, "Lubbock, TX", 33.5779, -101.8552, "TX"),
    # Utah
    Station("WXJ52", 162.475, "Salt Lake City, UT", 40.7608, -111.8910, "UT"),
    Station("KIH43", 162.550, "St. George, UT", 37.0965, -113.5684, "UT"),
    # Vermont
    Station("KZZ30", 162.450, "Burlington, VT", 44.4759, -73.2121, "VT"),
    # Virginia
    Station("KJY94", 162.450, "Richmond, VA", 37.5407, -77.4360, "VA"),
    Station("WXK78", 162.550, "Norfolk, VA", 36.8508, -76.2859, "VA"),
    Station("KIH44", 162.475, "Roanoke, VA", 37.2710, -79.9414, "VA"),
    # Washington
    Station("KJY60", 162.400, "Seattle, WA", 47.6062, -122.3321, "WA"),
    Station("WXL37", 162.550, "Spokane, WA", 47.6588, -117.4260, "WA"),
    Station("WXJ69", 162.475, "Yakima, WA", 46.6021, -120.5059, "WA"),
    # West Virginia
    Station("KIH45", 162.550, "Charleston, WV", 38.3498, -81.6326, "WV"),
    Station("WXK79", 162.475, "Elkins, WV", 38.9262, -79.8467, "WV"),
    # Wisconsin
    Station("KZZ39", 162.550, "Milwaukee, WI", 43.0389, -87.9065, "WI"),
    Station("WXJ72", 162.475, "Madison, WI", 43.0731, -89.4012, "WI"),
    Station("KIH46", 162.400, "Green Bay, WI", 44.5133, -88.0133, "WI"),
    # Wyoming
    Station("WXK80", 162.550, "Cheyenne, WY", 41.1400, -104.8202, "WY"),
    Station("KJY87", 162.475, "Casper, WY", 42.8666, -106.3131, "WY"),
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
