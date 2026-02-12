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
# Embedded station data – real NOAA Weather Radio stations sourced from
# weatherUSA.net/radio and NOAA NWR official listings.
# Coordinates are transmitter-area city coordinates.
# ---------------------------------------------------------------------------
_STATIONS: list[Station] = [
    # Alaska
    Station("KEC96", 162.550, "Anchorage, AK", 61.2181, -149.9003, "AK"),
    # Alabama
    Station("KEC61", 162.550, "Mobile, AL", 30.6954, -88.0399, "AL"),
    Station("WNG642", 0.0, "Arab, AL", 34.3281, -86.4961, "AL"),
    # Arkansas
    Station("KZZ99", 162.550, "Little Rock, AR", 34.7465, -92.2896, "AR"),
    Station("WNG694", 0.0, "Springdale, AR", 36.1867, -94.1288, "AR"),
    # Arizona
    Station("KEC94", 162.550, "Phoenix, AZ", 33.4484, -112.0740, "AZ"),
    Station("WWG42", 162.500, "Globe, AZ", 33.3942, -110.7865, "AZ"),
    Station("WWG41", 162.425, "Payson, AZ", 34.2309, -111.3251, "AZ"),
    Station("WXL87", 162.550, "Yuma, AZ", 32.6927, -114.6277, "AZ"),
    # California
    Station("KEC49", 162.550, "San Francisco Bay, CA", 37.7749, -122.4194, "CA"),
    Station("KIG78", 162.400, "Coachella, CA", 33.6803, -116.1739, "CA"),
    Station("WNG712", 0.0, "Coachella (Spanish), CA", 33.6803, -116.1739, "CA"),
    Station("WNG659", 0.0, "El Paso Mountains, CA", 35.4300, -117.5800, "CA"),
    Station("KIH62", 162.400, "Fresno, CA", 36.7378, -119.7871, "CA"),
    Station("KWO37", 0.0, "Los Angeles, CA", 34.0522, -118.2437, "CA"),
    Station("WWF64", 162.450, "Monterey Marine, CA", 36.6002, -121.8947, "CA"),
    # Colorado
    Station("KWN54", 162.425, "Durango, CO", 37.2753, -107.8801, "CO"),
    # Delaware
    Station("KIH30", 162.475, "Lewes, DE", 38.7746, -75.1393, "DE"),
    # Connecticut
    Station("WXJ42", 162.400, "Meriden, CT", 41.5382, -72.8070, "CT"),
    # Florida
    Station("WXK83", 162.475, "Cape Coral, FL", 26.5629, -81.9495, "FL"),
    Station("KIH26", 0.0, "Daytona Beach, FL", 29.2108, -81.0228, "FL"),
    Station("WZ2531", 0.0, "Hialeah (Spanish), FL", 25.8576, -80.2781, "FL"),
    Station("KHB39", 0.0, "Jacksonville, FL", 30.3322, -81.6557, "FL"),
    Station("KEC38", 0.0, "Largo, FL", 27.9095, -82.7873, "FL"),
    Station("KHB34", 0.0, "Miami, FL", 25.7617, -80.1918, "FL"),
    Station("KIH63", 162.475, "Orlando, FL", 28.5383, -81.3792, "FL"),
    Station("WNG522", 162.425, "Palatka, FL", 29.6486, -81.6376, "FL"),
    Station("KPS505", 162.500, "Sumterville, FL", 28.7483, -82.0681, "FL"),
    Station("KIH24", 162.400, "Tallahassee, FL", 30.4383, -84.2807, "FL"),
    Station("WNG663", 0.0, "Princeton, FL", 25.5384, -80.4089, "FL"),
    Station("KHB32", 162.550, "Tampa Bay, FL", 27.9506, -82.4572, "FL"),
    # Georgia
    Station("WXK56", 162.400, "Athens, GA", 33.9519, -83.3576, "GA"),
    Station("KEC80", 162.550, "Atlanta, GA", 33.7490, -84.3880, "GA"),
    Station("WWH23", 162.425, "Buchanan, GA", 33.8037, -85.1885, "GA"),
    Station("KXI81", 0.0, "Clayton, GA", 34.8782, -83.4010, "GA"),
    Station("WXJ53", 0.0, "Cleveland, GA", 34.5970, -83.7632, "GA"),
    Station("WXM32", 162.400, "Columbus, GA", 32.4610, -84.9877, "GA"),
    Station("WWH24", 0.0, "Toccoa, GA", 34.5773, -83.3324, "GA"),
    # Idaho
    Station("WWG53", 162.550, "Boise, ID", 43.6150, -116.2023, "ID"),
    # Hawaii
    Station("WWG75", 162.400, "Maui, HI", 20.7984, -156.3319, "HI"),
    # Iowa
    Station("WXL57", 162.550, "Des Moines, IA", 41.5868, -93.6250, "IA"),
    Station("KZZ80", 162.550, "Milford, IA", 43.3247, -95.1500, "IA"),
    Station("WXL62", 162.475, "Sioux City, IA", 42.4963, -96.4049, "IA"),
    Station("KXI68", 162.450, "St. Ansgar, IA", 43.3836, -92.9188, "IA"),
    # Illinois
    Station("WXJ76", 162.550, "Champaign, IL", 40.1164, -88.2434, "IL"),
    Station("KXI41", 162.500, "Crystal Lake, IL", 42.2411, -88.3162, "IL"),
    Station("KZZ55", 162.525, "Dixon, IL", 41.8389, -89.4795, "IL"),
    Station("KZZ66", 162.400, "Galesburg, IL", 40.9478, -90.3712, "IL"),
    Station("KZZ58", 162.525, "Kankakee, IL", 41.1200, -87.8612, "IL"),
    Station("WXM49", 162.425, "Marion, IL", 37.7306, -88.9331, "IL"),
    Station("WXJ71", 162.475, "Peoria, IL", 40.6936, -89.5890, "IL"),
    Station("KXI58", 162.400, "Plano, IL", 41.6628, -88.5368, "IL"),
    Station("WXJ73", 162.550, "Quad Cities, IL", 41.5236, -90.5776, "IL"),
    Station("WXJ75", 162.400, "Springfield, IL", 39.7817, -89.6501, "IL"),
    Station("KZZ81", 0.0, "Lockport, IL", 41.5895, -88.0573, "IL"),
    # Indiana
    Station("KEC74", 162.550, "Indianapolis, IN", 39.7684, -86.1581, "IN"),
    Station("KIG76", 0.0, "Evansville, IN", 37.9716, -87.5711, "IN"),
    Station("WXJ57", 162.400, "South Bend, IN", 41.6764, -86.2520, "IN"),
    # Kansas
    Station("WXK91", 162.475, "Topeka, KS", 39.0473, -95.6752, "KS"),
    # Kentucky
    Station("WZ2523", 162.500, "Frankfort, KY", 38.2009, -84.8733, "KY"),
    Station("KZZ48", 162.450, "Owenton, KY", 38.5365, -84.8419, "KY"),
    # Louisiana
    Station("KHB46", 162.400, "Baton Rouge, LA", 30.4515, -91.1871, "LA"),
    Station("WXK80", 162.550, "Lafayette, LA", 30.2241, -92.0198, "LA"),
    Station("WXJ96", 162.550, "Monroe, LA", 32.5093, -92.1193, "LA"),
    Station("WXJ97", 162.400, "Shreveport, LA", 32.5252, -93.7502, "LA"),
    # Maine
    Station("WSM60", 162.475, "Dresden, ME", 44.0834, -69.7312, "ME"),
    Station("KDO95", 162.550, "Portland, ME", 43.6591, -70.2568, "ME"),
    # Maryland
    Station("KEC83", 162.400, "Baltimore, MD", 39.2904, -76.6122, "MD"),
    Station("WXM42", 162.475, "Hagerstown, MD", 39.6418, -77.7200, "MD"),
    # Massachusetts
    Station("KHB35", 162.475, "Boston, MA", 42.3601, -71.0589, "MA"),
    Station("KEC73", 162.550, "Bourne, MA", 41.7415, -70.5989, "MA"),
    Station("WNG574", 162.425, "Gloucester, MA", 42.6159, -70.6620, "MA"),
    Station("WXL93", 162.550, "Worcester, MA", 42.2626, -71.8023, "MA"),
    # Montana
    Station("KEC59", 162.550, "Great Falls, MT", 47.5063, -111.3008, "MT"),
    Station("WXL25", 0.0, "Missoula, MT", 46.8721, -113.9940, "MT"),
    # Michigan
    Station("KEC63", 162.550, "Detroit, MI", 42.3314, -83.0458, "MI"),
    Station("KIH29", 162.475, "Flint, MI", 43.0125, -83.6875, "MI"),
    Station("WWF70", 162.500, "Gaylord, MI", 45.0275, -84.6747, "MI"),
    Station("WWF36", 162.475, "Hesperia, MI", 43.5672, -86.0403, "MI"),
    Station("WWF34", 162.475, "Kalamazoo, MI", 42.2917, -85.5872, "MI"),
    Station("KZZ33", 162.525, "Mount Pleasant, MI", 43.5978, -84.7675, "MI"),
    Station("WXK81", 162.400, "Onondaga, MI", 42.4392, -84.5519, "MI"),
    Station("KXI33", 162.450, "West Branch, MI", 44.2764, -84.2386, "MI"),
    Station("WXN99", 162.425, "West Olive, MI", 42.9189, -86.1767, "MI"),
    Station("WNG672", 162.425, "Wolf Lake, MI", 43.7786, -85.4942, "MI"),
    Station("WZ2560", 0.0, "Cannonsburg, MI", 43.0631, -85.4967, "MI"),
    # Minnesota
    Station("KEC65", 162.550, "Minneapolis, MN", 44.9778, -93.2650, "MN"),
    Station("WXM99", 162.425, "Bemidji, MN", 47.4736, -94.8803, "MN"),
    Station("WNG676", 162.500, "Clearwater, MN", 45.4183, -93.9810, "MN"),
    Station("WXJ86", 162.550, "La Crescent, MN", 43.8280, -91.3040, "MN"),
    Station("WWG98", 162.475, "Park Rapids, MN", 46.9222, -95.0536, "MN"),
    Station("WNG678", 0.0, "Pine City, MN", 45.8261, -92.9688, "MN"),
    Station("WXK41", 162.475, "Rochester, MN", 44.0121, -92.4802, "MN"),
    # Mississippi
    Station("KIH53", 162.400, "Tupelo, MS", 34.2576, -88.7034, "MS"),
    # Missouri
    Station("KID77", 162.550, "Kansas City, MO", 39.0997, -94.5786, "MO"),
    Station("KDO89", 162.550, "St. Louis, MO", 38.6270, -90.1994, "MO"),
    Station("WXJ61", 0.0, "Joplin, MO", 37.0842, -94.5133, "MO"),
    Station("WXL46", 162.400, "Springfield, MO", 37.2090, -93.2923, "MO"),
    # North Carolina
    Station("WXL58", 0.0, "Chapel Hill, NC", 35.9132, -79.0558, "NC"),
    Station("WXL70", 162.475, "Charlotte, NC", 35.2271, -80.8431, "NC"),
    Station("WNG706", 0.0, "Garner, NC", 35.7113, -78.6142, "NC"),
    Station("KEC84", 0.0, "New Bern, NC", 35.1085, -77.0441, "NC"),
    Station("WXL59", 0.0, "Rocky Mount, NC", 35.9382, -77.7905, "NC"),
    Station("KXI95", 0.0, "Warsaw, NC", 34.9988, -78.0911, "NC"),
    Station("KHB31", 162.550, "Wilmington, NC", 34.2257, -77.9447, "NC"),
    # North Dakota
    Station("WXL78", 162.475, "Bismarck, ND", 46.8083, -100.7837, "ND"),
    Station("WWF83", 0.0, "Grand Forks, ND", 47.9253, -97.0329, "ND"),
    Station("WXM38", 0.0, "Petersburg, ND", 48.0158, -98.0018, "ND"),
    # Nebraska
    Station("KZZ69", 162.450, "Beatrice, NE", 40.2681, -96.7475, "NE"),
    Station("WXL74", 162.400, "Grand Island, NE", 40.9264, -98.3420, "NE"),
    Station("WXM20", 162.475, "Lincoln, NE", 40.8136, -96.7026, "NE"),
    Station("KIH61", 162.400, "Omaha, NE", 41.2565, -95.9345, "NE"),
    Station("WXL67", 162.475, "Scottsbluff, NE", 41.8666, -103.6672, "NE"),
    # Nevada
    Station("WWG20", 162.450, "Fernley, NV", 39.6080, -119.2518, "NV"),
    Station("WXK58", 162.550, "Reno, NV", 39.5296, -119.8138, "NV"),
    # New Hampshire
    Station("WXL29", 162.400, "Concord, NH", 43.2081, -71.5376, "NH"),
    # New Jersey
    Station("KWO72", 162.475, "Atlantic City, NJ", 39.3643, -74.4229, "NJ"),
    # New Mexico
    Station("WXJ37", 162.475, "Farmington, NM", 36.7281, -108.2187, "NM"),
    # New York
    Station("KWO35", 162.550, "New York City, NY", 40.7128, -74.0060, "NY"),
    Station("WXL34", 162.550, "Albany, NY", 42.6526, -73.7562, "NY"),
    Station("KEB98", 162.550, "Buffalo, NY", 42.8864, -78.8784, "NY"),
    Station("WXL37", 162.475, "Highland, NY", 41.7212, -73.9610, "NY"),
    Station("WXM80", 0.0, "Riverhead, NY", 40.9170, -72.6621, "NY"),
    Station("WZ2536", 162.475, "Lyons, NY", 43.0642, -76.9905, "NY"),
    Station("WXM45", 162.425, "Middleville, NY", 43.1198, -74.9790, "NY"),
    Station("KHA53", 162.400, "Rochester, NY", 43.1566, -77.6088, "NY"),
    Station("WXL31", 162.550, "Syracuse, NY", 43.0481, -76.1474, "NY"),
    # Ohio
    Station("KDO94", 162.400, "Akron, OH", 41.0814, -81.5190, "OH"),
    Station("KIG86", 162.550, "Columbus, OH", 39.9612, -82.9988, "OH"),
    Station("WNG698", 162.500, "Grafton, OH", 41.1726, -82.0546, "OH"),
    Station("WWG57", 162.450, "Mansfield, OH", 40.7589, -82.5155, "OH"),
    Station("WXJ93", 0.0, "Lima, OH", 40.7428, -84.1052, "OH"),
    Station("WXL51", 162.500, "Toledo, OH", 41.6528, -83.5379, "OH"),
    # Oregon
    Station("KIG71", 162.550, "Portland, OR", 45.5152, -122.6784, "OR"),
    # Oklahoma
    Station("WXK85", 162.400, "Oklahoma City, OK", 35.4676, -97.5164, "OK"),
    Station("WXK86", 162.550, "Lawton, OK", 34.6036, -98.3959, "OK"),
    Station("WNG654", 162.500, "Stillwater, OK", 36.1156, -97.0584, "OK"),
    Station("KIH27", 162.550, "Tulsa, OK", 36.1540, -95.9928, "OK"),
    # Pennsylvania
    Station("KIH28", 162.475, "Philadelphia, PA", 39.9526, -75.1652, "PA"),
    Station("KIH35", 162.550, "Pittsburgh, PA", 40.4406, -79.9959, "PA"),
    Station("WXL39", 0.0, "Allentown, PA", 40.6084, -75.4902, "PA"),
    Station("WXL40", 162.550, "Harrisburg, PA", 40.2732, -76.8867, "PA"),
    Station("WNG704", 162.425, "Hibernia Park, PA", 40.0521, -75.8166, "PA"),
    Station("WXL43", 162.550, "Wilkes-Barre, PA", 41.2459, -75.8813, "PA"),
    # Rhode Island
    Station("WXJ24", 162.400, "Providence, RI", 41.8240, -71.4128, "RI"),
    # South Carolina
    Station("WXJ21", 162.550, "Greer, SC", 34.9388, -82.2271, "SC"),
    Station("KEC85", 162.400, "Jasper County, SC", 32.4316, -81.0112, "SC"),
    Station("KHC27", 162.425, "Rock Hill, SC", 34.9249, -81.0251, "SC"),
    # South Dakota
    Station("WXL82", 162.400, "Sioux Falls, SD", 43.5446, -96.7311, "SD"),
    # Tennessee
    Station("WXK47", 162.550, "Bristol, TN", 36.5951, -82.1887, "TN"),
    Station("KWN52", 0.0, "Lobelville, TN", 35.7753, -87.8142, "TN"),
    Station("WXK49", 162.475, "Memphis, TN", 35.1495, -90.0490, "TN"),
    Station("WXK63", 162.475, "Shelbyville, TN", 35.4834, -86.4603, "TN"),
    Station("KIG79", 162.550, "White House, TN", 36.4706, -86.6514, "TN"),
    # Texas
    Station("WXK38", 162.550, "Amarillo, TX", 35.2220, -101.8313, "TX"),
    Station("WXK27", 162.400, "Austin, TX", 30.2672, -97.7431, "TX"),
    Station("WXK30", 162.550, "College Station, TX", 30.6280, -96.3344, "TX"),
    Station("KHB41", 162.550, "Corpus Christi, TX", 27.8006, -97.3964, "TX"),
    Station("KXI87", 162.525, "Corsicana, TX", 32.0954, -96.4689, "TX"),
    Station("KEC56", 162.400, "Dallas, TX", 32.7767, -96.7970, "TX"),
    Station("KEC55", 162.550, "Fort Worth, TX", 32.7555, -97.3308, "TX"),
    Station("KHB40", 162.550, "Galveston, TX", 29.3013, -94.7977, "TX"),
    Station("KWN32", 162.425, "Gregg County, TX", 32.4638, -94.8374, "TX"),
    Station("KGG68", 162.400, "Houston/Tomball, TX", 30.0972, -95.6161, "TX"),
    Station("WXK23", 162.550, "Lufkin, TX", 31.3382, -94.7291, "TX"),
    Station("WXK32", 162.400, "Odessa, TX", 31.8457, -102.3676, "TX"),
    Station("KXI55", 0.0, "Onalaska, TX", 30.8060, -95.1177, "TX"),
    Station("KWN34", 162.450, "Palestine, TX", 31.7621, -95.6308, "TX"),
    Station("WXK33", 0.0, "San Angelo, TX", 31.4638, -100.4370, "TX"),
    Station("WXK67", 0.0, "San Antonio, TX", 29.4241, -98.4936, "TX"),
    Station("WXK36", 162.475, "Tyler, TX", 32.3513, -95.3011, "TX"),
    Station("WXK35", 162.475, "Waco, TX", 31.5493, -97.1467, "TX"),
    # Utah
    Station("KEC86", 162.550, "Salt Lake City, UT", 40.7608, -111.8910, "UT"),
    # Vermont
    Station("WXJ43", 162.550, "Burlington, VT", 44.4759, -73.2121, "VT"),
    # Virginia
    Station("KHB36", 162.550, "Manassas, VA", 38.7509, -77.4753, "VA"),
    Station("WXL60", 162.475, "Roanoke, VA", 37.2710, -79.9414, "VA"),
    Station("KHB37", 162.550, "Virginia Beach, VA", 36.8529, -75.9780, "VA"),
    # Washington
    Station("KHB60", 162.550, "Seattle, WA", 47.6062, -122.3321, "WA"),
    Station("WNG604", 162.550, "Davis Peak, WA", 48.0294, -122.5422, "WA"),
    Station("WWG24", 162.425, "Puget Sound Marine, WA", 47.6062, -122.3321, "WA"),
    Station("WWF56", 162.450, "Richland, WA", 46.2856, -119.2845, "WA"),
    # West Virginia
    Station("WXM71", 0.0, "Beckley, WV", 37.7782, -81.1882, "WV"),
    Station("WXJ84", 0.0, "Charleston, WV", 38.3498, -81.6326, "WV"),
    Station("WXM70", 162.500, "Parkersburg, WV", 39.2667, -81.5615, "WV"),
    Station("WXM74", 0.0, "Sutton, WV", 38.6646, -80.7098, "WV"),
    # Wisconsin
    Station("KZZ78", 162.525, "Ashland, WI", 46.5925, -90.8838, "WI"),
    Station("KIG65", 162.550, "Green Bay, WI", 44.5133, -88.0133, "WI"),
    Station("WXJ88", 162.400, "Menomonie, WI", 44.8755, -91.9193, "WI"),
    Station("WNG553", 162.400, "Wausaukee, WI", 45.3808, -87.9651, "WI"),
    Station("KGG95", 162.425, "Winona, WI", 44.0461, -91.6393, "WI"),
    Station("KZZ77", 162.425, "Withee, WI", 44.9572, -90.5932, "WI"),
    # Wyoming
    Station("WXM61", 162.475, "Lander, WY", 42.8330, -108.7307, "WY"),
    # Canada - Alberta
    Station("XLF339", 0.0, "Calgary, AB", 51.0447, -114.0719, "AB"),
    Station("XLM572", 0.0, "Edmonton, AB", 53.5461, -113.4938, "AB"),
    # Canada - Ontario
    Station("XMJ316", 0.0, "Collingwood, ON", 44.5001, -80.2169, "ON"),
    Station("XMJ225", 0.0, "Toronto, ON", 43.6532, -79.3832, "ON"),
    # Canada - Quebec
    Station("XLM300", 0.0, "Montreal, QC", 45.5017, -73.5673, "QC"),
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
