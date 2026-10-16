"""Golden outputs for geocoding and locations: Open-Meteo geocoding with its
fallbacks, the address/ZIP service, the location manager (Census search,
NWS/Nominatim reverse lookup), location sorting and current-location labels.

    cd C:\\Users\\joshu\\accessiweather
    uv run python <worktree>\\rust\\tools\\golden\\geocoding.py

Writes rust/testdata/golden/geocoding/*.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
import provider_golden_common as common  # noqa: E402

from accessiweather.current_location import (  # noqa: E402
    CurrentCoordinates,
    location_from_coordinates,
)
from accessiweather.geocoding import GeocodingService  # noqa: E402
from accessiweather.location_manager import LocationManager  # noqa: E402
from accessiweather.location_sorting import sort_locations_for_display  # noqa: E402
from accessiweather.models import Location  # noqa: E402
from accessiweather.openmeteo_geocoding_client import OpenMeteoGeocodingClient  # noqa: E402

AREA = "geocoding"
common.fast_retries()

GEO = "https://geocoding-api.open-meteo.com/v1/search"
CENSUS = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
NWS = "https://api.weather.gov/points/"
NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
EMPTY = {"generationtime_ms": 0.5}


def url(base: str, params: dict) -> str:
    return str(httpx.Request("GET", base, params=params).url)


def client_search(name: str, count: int) -> str:
    return url(GEO, {"count": count, "language": "en", "format": "json", "name": name})


def manager_search(name: str, count: int) -> str:
    return url(GEO, {"name": name, "count": count, "language": "en", "format": "json"})


def body(relative: str, index: int = -1) -> dict:
    return common.cassette_bodies(relative)[index][1]


def result(name, country, code, lat, lon, population=None, admin1=None, tz="UTC"):
    item = {
        "name": name,
        "latitude": lat,
        "longitude": lon,
        "country": country,
        "country_code": code,
        "timezone": tz,
        "population": population,
    }
    if admin1:
        item["admin1"] = admin1
    return item


LONDON = body("geocoding/geocode_london.yaml")
NYC = body("geocoding/geocode_nyc.yaml")
SUGGEST_NEW = body("geocoding/suggest_new.yaml")
SUGGEST_LIMIT = body("geocoding/suggest_limit.yaml")
OM_NYC = body("openmeteo/geocoding_search_nyc.yaml")
OM_LONDON = body("openmeteo/geocoding_search_london.yaml")
OM_ANCHORAGE = body("openmeteo/geocoding_search_anchorage.yaml")
ZURICH = {
    "results": [
        result("Zürich", "Switzerland", "CH", 47.36667, 8.55, 341730, "Zurich", "Europe/Zurich"),
        result("Zürichberg", "Switzerland", "CH", 47.38, 8.57, None, "Zurich"),
        result("Neu-Zürich", "Germany", "DE", 50.0, 8.0, 900),
    ]
}
TROMSO = {"results": [result("Tromsø", "Norway", "NO", 69.6489, 18.9551, 72681, "Troms")]}
CENSUS_MATCH = {
    "result": {
        "addressMatches": [
            {
                "coordinates": {"x": -76.928365658124, "y": 38.845053106269},
                "matchedAddress": "4600 SILVER HILL RD, WASHINGTON, DC, 20233",
            },
            {
                "coordinates": {"x": -76.928365658124, "y": 38.845053106269},
                "matchedAddress": "4600 Silver Hill Rd, Washington, DC, 20233",
            },
            {"coordinates": {"x": "bad", "y": 1}, "matchedAddress": "Nowhere"},
            {"coordinates": {"x": -77.0, "y": 38.9}, "matchedAddress": ""},
        ]
    }
}

SERVICE_ROUTES = [
    (GEO, 200, EMPTY),
    (client_search("London", 5), 200, LONDON),
    (client_search("New York", 5), 200, NYC),
    (client_search("New", 10), 200, SUGGEST_NEW),
    (client_search("New", 6), 200, SUGGEST_LIMIT),
    (client_search("Zürich", 5), 200, ZURICH),
    (client_search("Tromsø", 5), 200, TROMSO),
    (client_search("10001", 5), 200, OM_NYC),
]

SERVICE_CASES = [
    ("geocode", "nws", "London, UK"),
    ("geocode", "auto", "London, UK"),
    ("geocode", "nws", "New York, NY"),
    ("geocode", "auto", "  XYZNONEXISTENT12345 "),
    ("geocode", "nws", "10001-1234"),
    ("geocode", "auto", "Zurich"),
    ("geocode", "auto", "Tromso"),
    ("suggest5", "auto", "New"),
    ("suggest3", "nws", "New"),
    ("suggest5", "auto", "N"),
]

MANAGER_ROUTES = [
    (GEO, 200, EMPTY),
    (manager_search("New York", 5), 200, OM_NYC),
    (manager_search("London", 3), 200, OM_LONDON),
    (manager_search("Anchorage", 10), 200, OM_ANCHORAGE),
    (manager_search("Server Down", 5), 503, {}),
    (manager_search("Not Found", 5), 404, {}),
    (client_search("Zürich", 5), 200, ZURICH),
    (
        url(
            CENSUS,
            {
                "address": "4600 Silver Hill Rd, Washington, DC",
                "benchmark": "Public_AR_Current",
                "format": "json",
            },
        ),
        200,
        CENSUS_MATCH,
    ),
    (CENSUS, 200, {"result": {"addressMatches": []}}),
    (manager_search("12 Nowhere Street", 5), 200, OM_NYC),
]

MANAGER_CASES = [
    ("New York", 5),
    ("London", 3),
    ("Anchorage", 10),
    ("4600 Silver Hill Rd, Washington, DC", 5),
    ("12 Nowhere Street", 5),
    ("xyznonexistentlocation12345", 5),
    ("Zurich", 5),
    ("Server Down", 5),
    ("Not Found", 5),
    (" A ", 5),
]

REVERSE_CASES = {
    "nws_city_state": (
        39.9526,
        -75.1652,
        [
            (
                NWS,
                200,
                {
                    "properties": {
                        "timeZone": "America/New_York",
                        "relativeLocation": {
                            "properties": {"city": " Philadelphia ", "state": "PA"}
                        },
                    }
                },
            ),
        ],
    ),
    "nws_city_only": (
        61.2181,
        -149.9003,
        [
            (NWS, 200, {"properties": {"relativeLocation": {"properties": {"city": "Anchorage"}}}}),
        ],
    ),
    "nominatim_city": (
        48.8566,
        2.3522,
        [
            (NWS, 404, {"properties": {}}),
            (
                NOMINATIM,
                200,
                {
                    "display_name": "Paris, Île-de-France, France",
                    "address": {
                        "city": "Paris",
                        "state": "Île-de-France",
                        "country": "France",
                        "country_code": "fr",
                    },
                },
            ),
        ],
    ),
    "nominatim_country_only": (
        0.0,
        -160.0,
        [
            (NWS, 200, {"properties": {"relativeLocation": {"properties": {"city": ""}}}}),
            (NOMINATIM, 200, {"address": {"country": "Kiribati", "country_code": "ki"}}),
        ],
    ),
    "nominatim_display_name": (
        10.0,
        10.0,
        [
            (NWS, 404, {}),
            (NOMINATIM, 200, {"display_name": " Somewhere, Earth ", "address": "not-a-dict"}),
        ],
    ),
    "nothing": (-45.0, 170.0, [(NWS, 500, {}), (NOMINATIM, 200, ["not", "an", "object"])]),
    "nominatim_empty_address": (-45.0, 171.0, [(NWS, 404, {}), (NOMINATIM, 200, {"address": {}})]),
}


def locations_json(locations):
    return [common.to_jsonable(loc) for loc in locations]


def main() -> None:
    common.reset(AREA)

    for mode, source, query in SERVICE_CASES:
        router = common.Router(SERVICE_ROUTES)
        common.patch_httpx(router)
        service = GeocodingService(data_source=source)
        if mode == "geocode":
            output = service.geocode_address(query)
        else:
            output = service.suggest_locations(query, limit=int(mode[-1]))
        common.write(
            AREA,
            f"service_{mode}_{source}_{query.strip().replace(' ', '_').replace(',', '')}",
            {
                "mode": mode,
                "data_source": source,
                "query": query,
                "exchanges": router.exchanges(),
                "output": output,
            },
        )

    for query, limit in MANAGER_CASES:
        router = common.Router(MANAGER_ROUTES)
        common.patch_httpx(router)
        try:
            output = common.run(LocationManager().search_locations(query, limit=limit))
            error = False
        except Exception:  # noqa: BLE001 - retryable failures propagate
            output, error = None, True
        common.write(
            AREA,
            f"search_{query.strip().replace(' ', '_').replace(',', '')}",
            {
                "query": query,
                "limit": limit,
                "exchanges": router.exchanges(),
                "output": locations_json(output) if output is not None else None,
                "error": error,
            },
        )

    for name, (lat, lon, routes) in REVERSE_CASES.items():
        router = common.Router(routes)
        common.patch_httpx(router)
        output = common.run(LocationManager().reverse_geocode_coordinates(lat, lon))
        common.write(
            AREA,
            f"reverse_{name}",
            {"latitude": lat, "longitude": lon, "exchanges": router.exchanges(), "output": output},
        )

    manager = LocationManager()
    om_client = OpenMeteoGeocodingClient()
    service_nws = GeocodingService(data_source="nws")
    places = [
        Location("Home", 40.7128, -74.006),
        Location("los angeles", 34.0522, -118.2437),
        Location("Boston", 42.3601, -71.0589),
        Location("Äpfelstadt", 50.9, 10.9),
        Location("boston", 42.3601, -71.0589),
        Location("Newark", 40.7357, -74.1724),
    ]
    common.write(
        AREA,
        "pure_functions",
        {
            "street_address": {
                q: manager._looks_like_street_address(q)
                for q in [
                    "1600 Pennsylvania Ave NW, Washington, DC",
                    "10 Downing Street",
                    "221B Baker St",
                    "221 Baker, London",
                    "New York, NY",
                    "10001",
                    "Route 66",
                    "5th Avenue",
                    "12 main st apt 4",
                    "Apartment 5, Main",
                    "  42 Wallaby Way, Sydney",
                ]
            },
            "format_coordinates": [
                [lat, lon, manager.format_coordinates(lat, lon)]
                for lat, lon in [
                    (40.7128, -74.006),
                    (-33.8688, 151.2093),
                    (0.0, 0.0),
                    (51.50005, -0.12785),
                ]
            ],
            "distance": [
                [a.name, b.name, manager.calculate_distance(a, b)]
                for a, b in [(places[0], places[1]), (places[0], places[5]), (places[2], places[2])]
            ],
            "validate_us_nws": [
                [lat, lon, service_nws.validate_coordinates(lat, lon)]
                for lat, lon in [
                    (40.0, -75.0),
                    (51.5, -0.1),
                    (61.2, -149.9),
                    (52.0, 175.0),
                    (21.3, -157.8),
                    (18.2, -66.5),
                    (13.4, 144.8),
                    (95.0, 0.0),
                ]
            ],
            "zip_codes": {
                z: service_nws.is_zip_code(z)
                for z in ["12345", "12345-6789", "1234", "123456", "12345-678", "abcde", "12345\n"]
            },
            "fallback_queries": {
                n: om_client._build_fallback_queries(n)
                for n in [
                    "Zurich",
                    "Tromso",
                    "Paris, France",
                    "Munchen",
                    "Sao Paulo",
                    "Reykjavik",
                    "New York",
                    "ALESUND",
                    "Cafe",
                ]
            },
            "normalize_text": {
                t: om_client._normalize_text(t)
                for t in ["  Zürich,  CH ", "São Paulo", "Straße", "Ålesund", "Kraków!!", "東京"]
            },
            "nominatim_name": [
                [data, manager._format_nominatim_location_name(data)]
                for data in [
                    {"address": {"town": "Hamlet", "province": "Hamlet", "country": "Ruritania"}},
                    {
                        "address": {
                            "suburb": "",
                            "county": "Kent",
                            "state_district": "SE",
                            "country": "UK",
                        }
                    },
                    {"display_name": "Only Display", "address": {}},
                    {"display_name": "", "address": {}},
                    {"display_name": 12, "address": None},
                ]
            ],
            "geocoding_result": [
                [data, common.to_jsonable(manager._parse_geocoding_result(data))]
                for data in [
                    {
                        "name": "Paris",
                        "admin1": "Île-de-France",
                        "country": "France",
                        "country_code": "fr",
                        "latitude": 48.85,
                        "longitude": 2.35,
                    },
                    {
                        "name": "Springfield",
                        "admin1": "Springfield",
                        "country": "United States",
                        "latitude": 39.8,
                        "longitude": -89.6,
                    },
                    {"latitude": "1.5", "longitude": 2, "country": "United States of America"},
                ]
            ],
            "sorting": [
                [
                    order,
                    anchor.name if anchor else None,
                    [loc.name for loc in sort_locations_for_display(places, order, anchor=anchor)],
                ]
                for order, anchor in [
                    ("alphabetical", None),
                    ("manual", None),
                    ("nearest_current", places[2]),
                    ("nearest_current", places[3]),
                    ("nearest_current", None),
                    ("bogus", None),
                ]
            ],
            "current_location": [
                common.to_jsonable(
                    location_from_coordinates(CurrentCoordinates(lat, lon), name=name)
                )
                for lat, lon, name in [
                    (40.7128, -74.006, None),
                    (43.65, -79.38, None),
                    (43.65, -79.38, "Toronto"),
                    (51.5, -0.12, ""),
                ]
            ],
        },
    )


if __name__ == "__main__":
    main()
