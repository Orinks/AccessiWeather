"""
Golden parity data for the Rust NWS client (crates/aw-providers/src/nws).

Runs the Python NWS client code against recorded responses (the VCR cassettes
in tests/integration/cassettes plus fixed synthetic payloads) through a mock
HTTP client -- no network -- and writes one JSON file per scenario to
rust/testdata/golden/nws/. Each file holds the responses served, the
requests Python made (URL, params, headers) and the resulting model objects.

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/nws.py
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import enum
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import httpx
import yaml

from accessiweather import (
    weather_client_aviation,
    weather_client_enrichment,
    weather_client_nws,
    weather_client_nws_alerts,
    weather_client_nws_common,
    weather_client_nws_current,
    weather_client_nws_forecast,
    weather_client_nws_hourly,
    weather_client_nws_parsers,
)
from accessiweather.api import avwx_client
from accessiweather.location_classification import is_us_location
from accessiweather.models import Location, WeatherAlert, WeatherAlerts, WeatherData
from accessiweather.services import zone_enrichment_service
from accessiweather.utils import decode_taf_text, retry_utils
from accessiweather.weather_client_alerts import AlertAggregator

HERE = Path(__file__).resolve()
WORKTREE = HERE.parents[3]
OUT = HERE.parents[2] / "testdata" / "golden" / "nws"
CASSETTES = WORKTREE / "tests" / "integration" / "cassettes"
BASE = "https://api.weather.gov"
UA = "AccessiWeather/2.0"


# ---------------------------------------------------------------------------
# Frozen clock and instant retries
# ---------------------------------------------------------------------------


class FrozenDatetime(dt.datetime):
    """datetime whose now() is fixed (and aware, so goldens are TZ-independent)."""

    FIXED: dt.datetime = dt.datetime(2026, 1, 20, 18, 30, tzinfo=dt.UTC)

    @classmethod
    def now(cls, tz=None):
        fixed = cls.FIXED
        return fixed if tz is None else fixed.astimezone(tz)


for module in (
    weather_client_nws_common,
    weather_client_nws_current,
    weather_client_nws_parsers,
    weather_client_nws_alerts,
    weather_client_nws_forecast,
    weather_client_nws_hourly,
):
    module.datetime = FrozenDatetime


async def _no_sleep(_delay):
    return None


retry_utils.asyncio = SimpleNamespace(
    sleep=_no_sleep,
    wait_for=asyncio.wait_for,
    TimeoutError=asyncio.TimeoutError,
    CancelledError=asyncio.CancelledError,
)


# ---------------------------------------------------------------------------
# Mock HTTP client
# ---------------------------------------------------------------------------


def full_url(url: str, params) -> str:
    return str(httpx.Request("GET", url, params=params).url)


class MockClient:
    """AsyncClient stand-in serving canned (status, body) by full URL."""

    def __init__(self, routes: dict[str, tuple[int, str]]):
        self.routes = routes
        self.requests: list[dict] = []
        self.served: dict[str, tuple[int, str]] = {}

    async def get(self, url, headers=None, params=None, timeout=None):
        full = full_url(url, params)
        self.requests.append(
            {
                "url": url,
                "params": [[k, str(v)] for k, v in (params or {}).items()],
                "headers": [[k, v] for k, v in (headers or {}).items()],
            }
        )
        status, body = self.routes.get(full, (404, ""))
        self.served[full] = (status, body)
        return httpx.Response(status, content=body.encode(), request=httpx.Request("GET", full))


def cassette_routes(*names: str) -> dict[str, tuple[int, str]]:
    routes: dict[str, tuple[int, str]] = {}
    for name in names:
        path = CASSETTES / (name if "/" in name else f"nws/{name}")
        data = yaml.safe_load(path.with_suffix(".yaml").read_text(encoding="utf-8"))
        for item in data["interactions"]:
            uri = item["request"]["uri"]
            body = item["response"]["body"]["string"]
            routes.setdefault(uri, (item["response"]["status"]["code"], body))
    return routes


def body(obj) -> str:
    return json.dumps(obj)


def routes_json(routes: dict) -> dict[str, tuple[int, str]]:
    """Synthetic routes: {url: payload | (status, payload)}."""
    out = {}
    for url, value in routes.items():
        if isinstance(value, tuple):
            status, payload = value
            out[url] = (status, payload if isinstance(payload, str) else body(payload))
        else:
            out[url] = (200, body(value))
    return out


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


# WeatherAlert's text fields are `str` in the Rust model; Python stores the
# None an explicit JSON null produces, which its consumers treat as "".
ALERT_TEXT_FIELDS = ("title", "description", "severity", "urgency", "certainty")


def enc(o):
    if isinstance(o, WeatherAlert):
        out = {f.name: enc(getattr(o, f.name)) for f in dataclasses.fields(o)}
        return {k: ("" if k in ALERT_TEXT_FIELDS and v is None else v) for k, v in out.items()}
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return {f.name: enc(getattr(o, f.name)) for f in dataclasses.fields(o)}
    if isinstance(o, dict):
        return {str(k): enc(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [enc(v) for v in o]
    if isinstance(o, set | frozenset):
        return sorted(enc(v) for v in o)
    if isinstance(o, dt.datetime):
        return (o if o.tzinfo else o.astimezone()).isoformat()
    if isinstance(o, enum.Enum):
        return o.value
    return o


def compact(text: str) -> str:
    try:
        return json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)
    except ValueError:
        return text


def write(name: str, client: MockClient | None, result, **extra) -> None:
    doc = {"now": FrozenDatetime.FIXED.isoformat(), **extra}
    if client is not None:
        doc["responses"] = [
            {"url": url, "status": status, "body": compact(text)}
            for url, (status, text) in client.served.items()
        ]
        doc["requests"] = client.requests
    doc["result"] = enc(result)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(WORKTREE)}")


async def call(coro):
    """Run a coroutine, turning an exception into {"error": ..., "status": ...}."""
    try:
        return await coro
    except httpx.HTTPStatusError as exc:
        return {"error": "status", "status": exc.response.status_code}
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__, "message": str(exc)}


def loc(name, lat, lon, **kw) -> Location:
    return Location(name=name, latitude=lat, longitude=lon, **kw)


NYC = {"name": "New York, NY", "lat": 40.7128, "lon": -74.006}
ALASKA = {"name": "Anchorage, AK", "lat": 61.2181, "lon": -149.9003}


def at(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


async def current_scenarios():
    for name, place, cassette, now in (
        ("current_nyc", NYC, "current_nyc", "2026-01-20T18:21:00+00:00"),
        # Five hours later every observation is stale: all ten stations are
        # tried and the best stale fallback wins.
        ("current_alaska_stale", ALASKA, "current_alaska", "2026-01-20T23:40:00+00:00"),
    ):
        FrozenDatetime.FIXED = at(now)
        location = loc(place["name"], place["lat"], place["lon"])
        before = enc(location)
        client = MockClient(cassette_routes(cassette))
        result = await call(
            weather_client_nws.get_nws_current_conditions(location, BASE, UA, 10.0, client)
        )
        write(
            name,
            client,
            result,
            call="current_conditions",
            location=before,
            location_after=enc(location),
        )


def observation(station_ts: str, **props) -> dict:
    return {"properties": {"timestamp": station_ts, **props}}


async def current_selection_scenario():
    """Station ordering, QC scrubbing, stale and empty observations."""
    FrozenDatetime.FIXED = at("2026-01-20T18:30:00+00:00")
    stations = {
        "features": [
            {"properties": {"stationIdentifier": "PAMR", "distance": {"value": 100}}},
            {"properties": {"stationIdentifier": "KFAR", "distance": {"value": 9000}}},
            {"properties": {"stationIdentifier": "KNEAR", "distance": {"value": 50}}},
            {"properties": {"stationIdentifier": "KSTL", "distance": {"value": 500}}},
            {"properties": {"stationIdentifier": "KEMP", "distance": {"value": 400}}},
            {"properties": {}},
        ]
    }
    routes = routes_json(
        {
            f"{BASE}/points/38.6,-90.2": {
                "properties": {
                    "observationStations": f"{BASE}/gridpoints/LSX/90,74/stations",
                    "timeZone": "America/Chicago",
                }
            },
            f"{BASE}/gridpoints/LSX/90,74/stations": stations,
            # Nearest K station: empty observation (score 0, skipped).
            f"{BASE}/stations/KEMP/observations/latest": observation("2026-01-20T18:00:00+00:00"),
            # Next: stale but with data -> fallback candidate.
            f"{BASE}/stations/KSTL/observations/latest": observation(
                "2026-01-20T12:00:00+00:00",
                temperature={"value": 5.0, "unitCode": "wmoUnit:degC", "qualityControl": "V"},
                textDescription="Cloudy",
            ),
            # Then: fresh, but the temperature fails QC and there is no text.
            f"{BASE}/stations/KFAR/observations/latest": observation(
                "2026-01-20T18:10:00+00:00",
                temperature={"value": 30.0, "unitCode": "wmoUnit:degC", "qualityControl": "X"},
                relativeHumidity={"value": 55.2, "qualityControl": "V"},
                barometricPressure={
                    "value": 101000,
                    "unitCode": "wmoUnit:Pa",
                    "qualityControl": "V",
                },
            ),
            f"{BASE}/stations/PAMR/observations/latest": (500, "oops"),
        }
    )
    location = loc("St. Louis", 38.6, -90.2)
    before = enc(location)
    client = MockClient(routes)
    result = await call(
        weather_client_nws.get_nws_current_conditions(location, BASE, UA, 10.0, client)
    )
    write(
        "current_selection",
        client,
        result,
        call="current_conditions",
        location=before,
        location_after=enc(location),
    )


async def forecast_scenarios():
    FrozenDatetime.FIXED = at("2026-01-20T18:30:00+00:00")
    for name, place, cassettes in (
        ("forecast_discussion_nyc", NYC, ("forecast_nyc", "discussion_nyc")),
        # No AFD listing recorded: the discussion falls back to its sentence.
        ("forecast_alaska", ALASKA, ("forecast_alaska",)),
    ):
        location = loc(place["name"], place["lat"], place["lon"])
        client = MockClient(cassette_routes(*cassettes))
        result = await call(
            weather_client_nws.get_nws_forecast_and_discussion(location, BASE, UA, 10.0, client)
        )
        if isinstance(result, tuple):
            result = dict(
                zip(("forecast", "discussion", "discussion_issuance_time"), result, strict=True)
            )
        write(name, client, result, call="forecast_and_discussion", location=enc(location))

    location = loc(NYC["name"], NYC["lat"], NYC["lon"])
    client = MockClient(cassette_routes("discussion_nyc"))
    result = await call(
        weather_client_nws.get_nws_discussion_only(location, BASE, UA, 10.0, client)
    )
    write(
        "discussion_only_nyc", client, list(result), call="discussion_only", location=enc(location)
    )

    # A retryable /points failure is retried three times, then raised.
    client = MockClient(routes_json({f"{BASE}/points/40.7128,-74.006": (503, "busy")}))
    result = await call(
        weather_client_nws.get_nws_forecast_and_discussion(location, BASE, UA, 10.0, client)
    )
    write(
        "forecast_points_503",
        client,
        result,
        call="forecast_and_discussion",
        location=enc(location),
    )

    # Quantitative-value forecast with a failing forecast request body.
    routes = routes_json(
        {
            f"{BASE}/points/40.7128,-74.006": {
                "properties": {"forecast": f"{BASE}/gridpoints/OKX/33,35/forecast"}
            },
            f"{BASE}/gridpoints/OKX/33,35/forecast": {
                "properties": {
                    "periods": [
                        {
                            "name": "Today",
                            "isDaytime": True,
                            "startTime": "2026-01-20T06:00:00-05:00",
                            "endTime": "2026-01-20T18:00:00-05:00",
                            "temperature": {"unitCode": "wmoUnit:degC", "value": 3.3},
                            "temperatureUnit": "F",
                            "windSpeed": {
                                "unitCode": "wmoUnit:km_h-1",
                                "minValue": 9.26,
                                "maxValue": 18.52,
                            },
                            "windDirection": "NW",
                            "probabilityOfPrecipitation": {
                                "unitCode": "wmoUnit:percent",
                                "value": None,
                            },
                            "shortForecast": "Sunny",
                            "detailedForecast": "Sunny, with a high near 38.",
                            "icon": "https://api.weather.gov/icons/land/day/few?size=medium",
                        },
                        {
                            "name": "Tonight",
                            "isDaytime": False,
                            "startTime": "2026-01-20T18:00:00-05:00",
                            "endTime": "bogus",
                            "temperature": {"unitCode": "wmoUnit:degC", "value": -6.1},
                            "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 12.5},
                            "windDirection": {"value": 270},
                            "probabilityOfPrecipitation": {"value": 20},
                        },
                        {
                            "name": "Wednesday",
                            "isDaytime": True,
                            "temperature": 41,
                            "temperatureUnit": "F",
                            "windSpeed": "5 to 10 mph",
                        },
                        {"temperature": None, "temperatureUnit": "C", "windSpeed": 7.5},
                    ]
                }
            },
            f"{BASE}/products/types/AFD/locations/OKX": {
                "@graph": [
                    {"id": "afd-old", "issuanceTime": "2026-01-20T10:00:00+00:00"},
                    {"id": "afd-new", "issuanceTime": "2026-01-20T16:00:00+00:00"},
                    {"id": "afd-tie", "issuanceTime": "2026-01-20T16:00:00+00:00"},
                ]
            },
            f"{BASE}/products/afd-new": {"productText": "AREA FORECAST DISCUSSION\nnew"},
        }
    )
    client = MockClient(routes)
    result = await call(
        weather_client_nws.get_nws_forecast_and_discussion(location, BASE, UA, 10.0, client)
    )
    result = dict(zip(("forecast", "discussion", "discussion_issuance_time"), result, strict=True))
    write(
        "forecast_quantitative",
        client,
        result,
        call="forecast_and_discussion",
        location=enc(location),
    )


async def hourly_scenarios():
    FrozenDatetime.FIXED = at("2026-01-20T18:30:00+00:00")
    for name, tz in (("hourly_nyc", None), ("hourly_nyc_chicago_tz", "America/Chicago")):
        location = loc(NYC["name"], NYC["lat"], NYC["lon"], timezone=tz)
        client = MockClient(cassette_routes("hourly_nyc"))
        result = await call(
            weather_client_nws.get_nws_hourly_forecast(location, BASE, UA, 10.0, client)
        )
        write(name, client, result, call="hourly_forecast", location=enc(location))

    # Gridpoint pressure fills hourly periods.
    routes = routes_json(
        {
            f"{BASE}/points/40.7128,-74.006": {
                "properties": {
                    "forecastHourly": f"{BASE}/gridpoints/OKX/33,35/forecast/hourly",
                    "forecastGridData": f"{BASE}/gridpoints/OKX/33,35",
                }
            },
            f"{BASE}/gridpoints/OKX/33,35/forecast/hourly": {
                "properties": {
                    "periods": [
                        {
                            "startTime": "2026-01-20T13:00:00-05:00",
                            "endTime": "2026-01-20T14:00:00-05:00",
                            "temperature": {"unitCode": "wmoUnit:degC", "value": 1.1},
                            "windSpeed": "10 mph",
                            "windDirection": "W",
                            "shortForecast": "Sunny",
                            "probabilityOfPrecipitation": {"value": 5},
                        },
                        {
                            "startTime": "2026-01-20T14:00:00-05:00",
                            "temperature": 35,
                            "temperatureUnit": "F",
                            "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 16.0},
                        },
                        {"startTime": "2026-01-20T20:00:00-05:00", "temperature": 30},
                        {"temperature": 29},
                    ]
                }
            },
            f"{BASE}/gridpoints/OKX/33,35": {
                "properties": {
                    "pressure": {
                        "uom": "wmoUnit:Pa",
                        "values": [
                            {"validTime": "2026-01-20T18:00:00+00:00/PT1H", "value": 101325},
                            {
                                "validTime": "2026-01-20T19:00:00+00:00/PT2H",
                                "value": 30.02,
                                "uom": "",
                            },
                            {"validTime": "garbage", "value": 1},
                        ],
                    }
                }
            },
        }
    )
    location = loc(NYC["name"], NYC["lat"], NYC["lon"], timezone="America/New_York")
    client = MockClient(routes)
    result = await call(
        weather_client_nws.get_nws_hourly_forecast(location, BASE, UA, 10.0, client)
    )
    write(
        "hourly_gridpoint_pressure", client, result, call="hourly_forecast", location=enc(location)
    )


def alert_feature(alert_id, event, **props):
    return {"id": alert_id, "properties": {"event": event, "headline": f"{event} issued", **props}}


ALERT_A = alert_feature(
    "urn:oid:a",
    "Tornado Warning",
    severity="Extreme",
    urgency="Immediate",
    certainty="Observed",
    messageType="Alert",
    description="A tornado was sighted.",
    instruction="Take cover now.",
    areaDesc="New York, NY; Kings, NY;",
    affectedZones=[f"{BASE}/zones/county/NYC061", f"{BASE}/zones/forecast/NYZ072"],
    geocode={"SAME": ["036061", 36047]},
    eventCode={"SAME": ["TOR"]},
    sent="2026-01-20T18:00:00Z",
    effective="2026-01-20T18:00:00-05:00",
    onset="2026-01-20T18:05:00-05:00",
    expires="2026-01-20T19:00:00-05:00",
    references=[{"identifier": "urn:oid:prev", "@id": "https://x/prev"}],
)
ALERT_B = alert_feature(
    "urn:oid:b",
    "Winter Storm Warning",
    severity="Severe",
    messageType="Update",
    areaDesc="Queens, NY",
    headline=None,
    description=None,
)


async def alert_scenarios():
    FrozenDatetime.FIXED = at("2026-01-20T18:30:00+00:00")
    points = {
        "properties": {
            "county": f"{BASE}/zones/county/NYC061",
            "forecastZone": f"{BASE}/zones/forecast/NYZ072",
            "relativeLocation": {"properties": {"state": "NY"}},
        }
    }
    active = f"{BASE}/alerts/active"
    routes = routes_json(
        {
            f"{BASE}/points/40.7128,-74.006": points,
            f"{active}?zone=NYC061&status=actual": {"features": [ALERT_A, ALERT_B]},
            f"{active}?zone=NYZ072&status=actual": {"features": [ALERT_A]},
            f"{active}?zone=NYZ999&status=actual": (500, "boom"),
            f"{active}?area=NY&status=actual": {"features": [ALERT_B]},
            f"{active}?point=40.7128%2C-74.006&status=actual": {"features": [ALERT_B, ALERT_B]},
        }
    )
    cases = (
        ("alerts_county_stored", "county", {"county_zone_id": "NYC061"}),
        ("alerts_county_points", "county", {}),
        ("alerts_zone_stored", "zone", {"county_zone_id": "NYC061", "forecast_zone_id": "NYZ072"}),
        ("alerts_zone_one_fails", "zone", {"county_zone_id": "NYZ999", "forecast_zone_id": "NYZ072"}),
        ("alerts_zone_points", "zone", {}),
        ("alerts_state", "state", {}),
        ("alerts_point", "point", {}),
        ("alerts_unknown_radius", "nearby", {}),
    )
    for name, radius, fields in cases:
        location = loc(NYC["name"], NYC["lat"], NYC["lon"], **fields)
        client = MockClient(routes)
        result = await call(
            weather_client_nws.get_nws_alerts(
                location, BASE, UA, 10.0, client, alert_radius_type=radius
            )
        )
        write(name, client, result, call="alerts", location=enc(location), radius=radius)

    # No county in /points: county falls back to a point query.
    bare = routes_json(
        {
            f"{BASE}/points/40.7128,-74.006": {"properties": {}},
            f"{active}?point=40.7128%2C-74.006&status=actual": {"features": [ALERT_A]},
        }
    )
    for name, radius in (
        ("alerts_county_no_zone", "county"),
        ("alerts_state_no_state", "state"),
        ("alerts_zone_no_zones", "zone"),
    ):
        location = loc(NYC["name"], NYC["lat"], NYC["lon"])
        client = MockClient(bare)
        result = await call(
            weather_client_nws.get_nws_alerts(
                location, BASE, UA, 10.0, client, alert_radius_type=radius
            )
        )
        write(name, client, result, call="alerts", location=enc(location), radius=radius)

    # A 404 on the stored zone is not retryable: empty alerts.
    location = loc(NYC["name"], NYC["lat"], NYC["lon"], county_zone_id="XXC000")
    client = MockClient({})
    result = await call(weather_client_nws.get_nws_alerts(location, BASE, UA, 10.0, client))
    write(
        "alerts_county_404", client, result, call="alerts", location=enc(location), radius="county"
    )

    # The cassettes' point queries.
    for name, place, cassette in (
        ("alerts_nyc_cassette", NYC, "alerts_nyc"),
        ("alerts_alaska_cassette", ALASKA, "alerts_alaska"),
    ):
        routes = {}
        for url, value in cassette_routes(cassette).items():
            routes[url + "&status=actual"] = value
        location = loc(place["name"], place["lat"], place["lon"])
        client = MockClient(routes)
        result = await call(
            weather_client_nws.get_nws_alerts(
                location, BASE, UA, 10.0, client, alert_radius_type="point"
            )
        )
        write(name, client, result, call="alerts", location=enc(location), radius="point")

    # Cancel references.
    start = "2026-01-20T18:15:00Z"
    end = "2026-01-20T18:30:00Z"
    url = full_url(f"{BASE}/alerts", {"message_type": "cancel", "start": start, "end": end})
    for name, payload in (
        (
            "cancel_references",
            {
                "features": [
                    {
                        "properties": {
                            "references": [
                                {"identifier": "id-1"},
                                {"@id": "id-2"},
                                {"id": "id-3"},
                                {},
                            ]
                        }
                    },
                    {"properties": {}},
                    {"properties": {"references": [{"identifier": "id-1"}]}},
                ]
            },
        ),
        ("cancel_references_malformed", {"features": [{"properties": {"references": ["bad"]}}]}),
    ):
        client = MockClient({url: (200, body(payload))})
        result = await call(
            weather_client_nws.fetch_nws_cancel_references(BASE, UA, 10.0, client=client)
        )
        write(name, client, result, call="cancel_references")


async def all_data_scenario():
    FrozenDatetime.FIXED = at("2026-01-20T18:21:00+00:00")
    routes = cassette_routes("current_nyc", "forecast_nyc", "discussion_nyc", "hourly_nyc")
    routes.update(
        routes_json({f"{BASE}/alerts/active?zone=NYC061&status=actual": {"features": [ALERT_A]}})
    )
    drift: list = []

    class Sink:
        def update_zone_metadata(self, name, fields):
            drift.append([name, fields])

    weather_client_nws_common.wx = SimpleNamespace(CallAfter=lambda fn, *args: fn(*args))
    weather_client_nws.wx = weather_client_nws_common.wx
    weather_client_nws.set_zone_drift_sink(Sink())
    location = loc(NYC["name"], NYC["lat"], NYC["lon"], cwa_office="XXX", county_zone_id=None)
    before = enc(location)
    client = MockClient(routes)
    result = await call(
        weather_client_nws.get_nws_all_data_parallel(
            location, BASE, UA, 10.0, client, alert_radius_type="county"
        )
    )
    weather_client_nws.set_zone_drift_sink(None)
    keys = (
        "current",
        "forecast",
        "discussion",
        "discussion_issuance_time",
        "alerts",
        "hourly_forecast",
    )
    write(
        "all_data_nyc",
        client,
        dict(zip(keys, result, strict=True)),
        call="all_data_parallel",
        location=before,
        location_after=enc(location),
        radius="county",
        zone_drift=drift,
    )


async def station_scenarios():
    location = loc(NYC["name"], NYC["lat"], NYC["lon"])
    client = MockClient(cassette_routes("stations_nyc"))
    result = await weather_client_nws.get_nws_primary_station_info(location, BASE, UA, 10.0, client)
    write(
        "primary_station_nyc",
        client,
        list(result),
        call="primary_station_info",
        location=enc(location),
    )

    routes = cassette_routes("stations_nyc")
    routes[f"{BASE}/points/40.7128,-74.0060"] = routes[f"{BASE}/points/40.7128,-74.006"]
    client = MockClient(routes)
    result = await weather_client_nws.get_nws_observation_station_ids_for_point(
        40.7128, -74.006, nws_base_url=BASE, client=client, user_agent=UA, limit=5
    )
    write(
        "station_ids_for_point_nyc",
        client,
        result,
        call="observation_station_ids_for_point",
        latitude=40.7128,
        longitude=-74.006,
        limit=5,
    )


async def text_product_scenarios():
    office = "OKX"

    def product(pid, issued, text=None, headline=None):
        payload = {"id": pid, "issuanceTime": issued, "productText": text or f"{pid} TEXT"}
        if headline is not None:
            payload["headline"] = headline
        return payload

    routes = routes_json(
        {
            f"{BASE}/products/types/SPS/locations/{office}": {
                "@graph": [
                    {"id": "sps-middle", "issuanceTime": "2026-01-20T12:00:00+00:00"},
                    {"id": "sps-oldest", "issuanceTime": "2026-01-20T09:00:00+00:00"},
                    {"id": "sps-notext"},
                    {"issuanceTime": "2026-01-20T13:00:00+00:00"},
                    {"id": "sps-newest", "issuanceTime": "2026-01-20T11:00:00+00:00"},
                ]
            },
            f"{BASE}/products/sps-middle": product("sps-middle", "2026-01-20T12:00:00+00:00"),
            f"{BASE}/products/sps-oldest": product("sps-oldest", None),
            f"{BASE}/products/sps-notext": {"productText": ""},
            # The body's issuanceTime overrides the listing's.
            f"{BASE}/products/sps-newest": product(
                "sps-newest", "2026-01-20T15:00:00Z", headline=5
            ),
            f"{BASE}/products/types/HWO/locations/{office}": {"@graph": []},
            f"{BASE}/products/types/SRF/locations/{office}": {
                "@graph": [
                    {
                        "id": "srf-1",
                        "issuanceTime": "2026-01-20T08:00:00+00:00",
                        "headline": "Surf Zone Forecast",
                    }
                ]
            },
            f"{BASE}/products/srf-1": {"productText": "SURF ZONE FORECAST"},
            f"{BASE}/products/types/AFD/locations/BAD": (500, "err"),
            f"{BASE}/products/types/AFD/locations/BADJSON": (200, "not json"),
            f"{BASE}/products/types/SPS/locations/ERR": {"@graph": [{"id": "sps-500"}]},
            f"{BASE}/products/sps-500": (500, ""),
            full_url(
                f"{BASE}/products?"
                + urlencode(
                    {
                        "location": office,
                        "type": "AFD",
                        "limit": 2,
                        "start": "2026-01-19T00:00:00+00:00",
                        "end": "2026-01-20T00:00:00+00:00",
                    }
                ),
                None,
            ): {
                "@graph": [
                    {"id": "afd-old", "issuanceTime": "2026-01-19T10:00:00+00:00"},
                    {"id": "afd-new", "issuanceTime": "2026-01-19T20:00:00+00:00"},
                ]
            },
            f"{BASE}/products/afd-old": product("afd-old", "2026-01-19T10:00:00+00:00"),
            f"{BASE}/products/afd-new": product("afd-new", "2026-01-19T20:00:00+00:00"),
            f"{BASE}/products?location=TTN&type=CLI&limit=1": {"@graph": [{"id": "cli-ttn"}]},
            f"{BASE}/products/cli-ttn": product(
                "cli-ttn", "2026-01-20T06:00:00+00:00", "CLIMATE REPORT"
            ),
            f"{BASE}/products/types/CLI/locations": {
                "locations": {"TTN": "Trenton", " phl ": "Phila", "": "x"}
            },
        }
    )

    async def text(name, product_type, cwa):
        client = MockClient(routes)
        result = await call(
            weather_client_nws.get_nws_text_product(
                product_type, cwa, nws_base_url=BASE, client=client, user_agent=UA
            )
        )
        write(name, client, result, call="text_product", product_type=product_type, office=cwa)

    await text("text_sps", "SPS", office)
    await text("text_hwo_empty", "HWO", office)
    await text("text_srf", "SRF", office)
    await text("text_no_office", "AFD", None)
    await text("text_listing_500", "AFD", "BAD")
    await text("text_listing_bad_json", "AFD", "BADJSON")
    await text("text_sps_product_500", "SPS", "ERR")

    client = MockClient(routes)
    result = await call(
        weather_client_nws.get_nws_text_product_history(
            "AFD",
            office,
            nws_base_url=BASE,
            client=client,
            user_agent=UA,
            limit=2,
            start=at("2026-01-19T00:00:00+00:00"),
            end=at("2026-01-20T00:00:00+00:00"),
        )
    )
    write(
        "text_history",
        client,
        result,
        call="text_product_history",
        product_type="AFD",
        office=office,
        limit=2,
        start="2026-01-19T00:00:00+00:00",
        end="2026-01-20T00:00:00+00:00",
    )

    client = MockClient(routes)
    result = await call(
        weather_client_nws.get_nws_daily_climate_report(
            " kttn ", nws_base_url=BASE, client=client, user_agent=UA
        )
    )
    write("daily_climate_report", client, result, call="daily_climate_report", station=" kttn ")

    client = MockClient(routes)
    result = await call(
        weather_client_nws.get_nws_daily_climate_locations(
            nws_base_url=BASE, client=client, user_agent=UA
        )
    )
    write("daily_climate_locations", client, result, call="daily_climate_locations")


async def aviation_scenarios():
    def weather_client(client, avwx=""):
        return SimpleNamespace(
            _get_http_client=lambda: client,
            nws_base_url=BASE,
            user_agent=UA,
            timeout=10.0,
            avwx_api_key=avwx,
            _is_us_location=lambda location: True,
        )

    # KNYC from the cassette: NWS has no TAF, AWC answers 204.
    client = MockClient(cassette_routes("weather_client/cache_test"))
    result = await call(
        weather_client_aviation.get_aviation_weather(
            weather_client(client), "knyc", include_sigmets=True, include_cwas=True
        )
    )
    write(
        "aviation_knyc_cassette",
        client,
        result,
        call="aviation_weather",
        station="knyc",
        include_sigmets=True,
        include_cwas=True,
    )

    meta = {
        "properties": {
            "name": "John F Kennedy International Airport",
            "cwa": "ZNY",
            "wfo": "OKX",
            "state": "NY",
            "country": "US",
        }
    }
    taf = (
        "TAF KJFK 201730Z 2018/2124 31015G25KT P6SM FEW050 "
        "TEMPO 2018/2022 BKN035 FM210200 32010KT P6SM SKC PROB30 2106/2110 -SN BKN020"
    )
    routes = routes_json(
        {
            f"{BASE}/stations/KJFK": meta,
            f"{BASE}/stations/KJFK/tafs": {
                "features": [
                    {"properties": {"rawMessage": ""}},
                    {"properties": {"rawTAF": f"  {taf}  "}},
                ]
            },
            f"{BASE}/aviation/sigmets?atsu=KKCI": {
                "features": [
                    {"properties": {"name": "SIGMET NOVEMBER 3", "fir": "KZNY", "hazard": "TURB"}},
                    {"properties": {"name": "SIGMET OSCAR 1", "fir": "KZMA"}},
                    {"id": "no-props", "text": "JFK area"},
                ]
            },
            f"{BASE}/aviation/cwsus/ZNY/cwas": {
                "features": [
                    {"properties": {"text": "CWA 101 ... NEAR JFK", "cwsu": "ZNY"}},
                    {"properties": {"text": "elsewhere", "cwsu": "ZDC"}},
                ]
            },
            f"{BASE}/stations/KNIL": {"properties": {}},
            f"{BASE}/stations/KNIL/tafs": (404, ""),
            full_url(
                "https://aviationweather.gov/api/data/taf", {"ids": "KNIL", "format": "json"}
            ): [{"rawTAF": "TAF KNIL 201730Z NIL="}],
            f"{BASE}/stations/KAWC/tafs": {"features": []},
            full_url(
                "https://aviationweather.gov/api/data/taf", {"ids": "KAWC", "format": "json"}
            ): {"data": [{"raw_taf": "KAWC 201730Z 2018/2118 00000KT 9999 SKC"}]},
            full_url(
                "https://aviationweather.gov/api/data/taf", {"ids": "KBAD", "format": "json"}
            ): (200, "<html>"),
            full_url(
                "https://aviationweather.gov/api/data/taf", {"ids": "KERR", "format": "json"}
            ): (503, ""),
            full_url(f"{AVWX}/taf/EGLL", AVWX_PARAMS): {
                "raw": "TAF EGLL 201700Z 2018/2124 24010KT 9999 SCT030",
                "info": {"name": "London Heathrow"},
                "start_time": {"dt": "2026-01-20T18:00:00Z"},
                "end_time": {"repr": "2124"},
                "forecast": [
                    {
                        "type": "FROM",
                        "start_time": {"dt": "2026-01-20T18:00:00Z"},
                        "speech": "Winds 240 at 10kt",
                    },
                    {"type": "TEMPO", "raw": "TEMPO 2020/2024 4000 RA"},
                    {"type": "PROB", "probability": {"value": 30}, "flight_rules": "MVFR"},
                ],
                "translate": {
                    "forecast": [
                        {},
                        {},
                        {"wind": "W-10kt", "visibility": "4km", "wx_codes": "Rain"},
                    ]
                },
            },
            full_url(f"{AVWX}/taf/RJTT", AVWX_PARAMS): (401, ""),
            f"{BASE}/stations/RJTT/tafs": {"features": []},
        }
    )
    for name, station, sigmets, cwas, avwx in (
        ("aviation_kjfk_full", "KJFK", True, True, ""),
        ("aviation_kjfk_taf_only", "KJFK", False, False, ""),
        ("aviation_nil", "KNIL", False, False, ""),
        ("aviation_awc_fallback", "KAWC", False, False, ""),
        ("aviation_awc_bad_json", "KBAD", False, False, ""),
        ("aviation_awc_503", "KERR", False, False, ""),
        ("aviation_avwx", "EGLL", False, False, "secret"),
        ("aviation_avwx_401_fallback", "RJTT", False, False, "secret"),
        ("aviation_empty_station", "  ", False, False, ""),
    ):
        client = MockClient(routes)
        result = await call(
            weather_client_aviation.get_aviation_weather(
                weather_client(client, avwx), station, include_sigmets=sigmets, include_cwas=cwas
            )
        )
        write(
            name,
            client,
            result,
            call="aviation_weather",
            station=station,
            include_sigmets=sigmets,
            include_cwas=cwas,
            avwx_api_key=avwx,
        )

    # Enrichment for a US location's primary station.
    routes = cassette_routes("stations_nyc")
    routes.update(
        routes_json(
            {
                f"{BASE}/stations/KNYC": meta,
                f"{BASE}/stations/KNYC/tafs": {
                    "features": [
                        {
                            "properties": {
                                "rawMessage": "TAF KNYC 201730Z 2018/2124 VRB03KT P6SM SKC"
                            }
                        }
                    ]
                },
            }
        )
    )
    client = MockClient(routes)
    location = loc(NYC["name"], NYC["lat"], NYC["lon"], country_code="US")
    data = WeatherData(location=location)
    await weather_client_aviation.enrich_with_aviation_data(weather_client(client), data, location)
    write(
        "aviation_enrich_nyc",
        client,
        data.aviation,
        call="enrich_with_aviation_data",
        location=enc(location),
    )


AVWX = avwx_client.AVWX_BASE_URL
AVWX_PARAMS = {"token": "secret", "options": "info,translate,speech,summary"}


def marine_client(client):
    return SimpleNamespace(
        _get_http_client=lambda: client,
        user_agent=UA,
        nws_base_url=BASE,
        timeout=10.0,
        _is_us_location=is_us_location,
    )


async def marine_scenarios():
    lat, lon = 40.5, -73.9
    zones_url = full_url(f"{BASE}/zones", {"type": "marine", "point": f"{lat},{lon}"})
    forecast = {
        "properties": {
            "name": "Coastal waters from Sandy Hook",
            "updateTime": "2026-01-20T15:00:00Z",
            "periods": [
                {
                    "name": "Tonight",
                    "detailedForecast": "W winds 15 to 20 kt. Seas 3 to 5 ft; gusts to 25 kt.",
                },
                {"name": None, "shortForecast": "Seas 2 ft. Sunny."},
                {"name": "Wed", "detailedForecast": ""},
                {"name": "Wed Night", "detailedForecast": "Waves 1 ft. Swell from the SE."},
                {"name": "Thu", "detailedForecast": "Winds light."},
            ],
        }
    }
    marine_alert = alert_feature("urn:oid:marine", "Small Craft Advisory", areaDesc="Sandy Hook")
    routes = routes_json(
        {
            zones_url: {
                "features": [
                    {"id": "https://x/ANZ355", "properties": {"id": "ANZ355", "name": "Zone name"}}
                ]
            },
            f"{BASE}/zones/marine/ANZ355/forecast": forecast,
            f"{BASE}/alerts/active?zone=ANZ355&status=actual": {
                "features": [marine_alert, ALERT_A]
            },
        }
    )
    existing = WeatherAlerts(
        alerts=[
            WeatherAlert(title="Existing", description="d", id="urn:oid:a", source="NWS"),
            WeatherAlert(title="Dup", description="first", event="E", severity="Minor"),
            WeatherAlert(title="Dup", description="second", event="E", severity="Minor"),
        ]
    )
    for name, marine_mode, country in (
        ("marine_full", True, "US"),
        ("marine_disabled", False, "US"),
        ("marine_non_us", True, "GB"),
    ):
        location = loc("Sandy Hook", lat, lon, marine_mode=marine_mode, country_code=country)
        data = WeatherData(location=location, alerts=WeatherAlerts(alerts=list(existing.alerts)))
        client = MockClient(routes)
        await weather_client_enrichment.enrich_with_marine_data(
            marine_client(client), data, location
        )
        write(
            name,
            client,
            {"marine": data.marine, "alerts": data.alerts},
            call="enrich_with_marine_data",
            location=enc(location),
            existing_alerts=enc(existing),
        )

    # No marine zone at the point.
    client = MockClient(routes_json({zones_url: {"features": []}}))
    location = loc("Sandy Hook", lat, lon, marine_mode=True, country_code="US")
    data = WeatherData(location=location)
    await weather_client_enrichment.enrich_with_marine_data(marine_client(client), data, location)
    write(
        "marine_no_zone",
        client,
        {"marine": data.marine, "alerts": data.alerts},
        call="enrich_with_marine_data",
        location=enc(location),
        existing_alerts=None,
    )


def pure_scenarios():
    tafs = [
        "",
        "TAF KXYZ NIL=",
        "TAF",
        "TAF AMD KORD 201730Z 2018/2124 VRB03KT 1 1/2SM -FZRA BR OVC005 "
        "BECMG 2020/2022 27012G22KT 3SM -SN BKN010 TEMPO 2022/2102 1/2SM +SN VV002 "
        "FM210300 30015KT P6SM SCT025 PROB40 TEMPO 2106/2110 2SM SHSN RMK NXT FCST BY 21Z",
        "TAF KXYZ 201730Z 2018/2118 00000KT 0800 FG VCSH UP FZUP RAUP TSUP SHUP -UP CAVOK NSW "
        "SKC CLR NSC OVC/// BKN020TCU FEW100CB 12345 9999 M1/4SM 1/0SM WEIRD",
        "TAF KXYZ 201730Z 2018/2118 TEMPO BECMG PROB30 FM201900",
        "KXYZ 201730Z 2018/2118 == 18010MPS 20005KMH 36010KT",
        "TAF == 201730Z",
        # tests/test_taf_decoder.py inputs
        "   \n  ",
        "= = =",
        "TAF KJFK",
        "TAF KJFK NIL",
        "TAF COR KJFK 071730Z 0718/0824 21015KT P6SM SCT250 FM072200 31010KT P6SM FEW250",
        "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 TEMPO 0720/0724 3SM -RA",
        "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 BECMG 0720/0722 BKN040",
        "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 PROB30 0720/0724 1SM +TSRA",
        "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 PROB40 TEMPO 0720/0724 1SM +TSRA",
        "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 RMK NXT FCST BY 08Z",
        "TAF EGLL 071730Z 0718/0824 27010KT CAVOK 5000 BLSN MIFG SCT030TCU BKN///",
        "TAF KJFK 071730Z 0718/0824 21015KT P6SM NSW SCT250=",
        "TAF KJFK 071730Z 0718/0824\n        21015KT P6SM SCT250 270100KT 27020KMH NOSUCH",
    ]
    no_data = list(tafs) + ["TAF KXYZ 201730Z 2018/2118 NO DATA", "KXYZ NO TAF"]
    write(
        "taf_decode",
        None,
        {
            "decoded": [[t, decode_taf_text(t)] for t in tafs],
            "no_data": [[t, weather_client_aviation._taf_indicates_no_data(t)] for t in no_data],
        },
        call="taf",
    )

    # Zone fields from the recorded /points documents.
    out = []
    stored = [
        loc("Legacy", 40.7128, -74.006),
        loc(
            "Current",
            40.7128,
            -74.006,
            timezone="America/New_York",
            cwa_office="OKX",
            forecast_zone_id="NYZ072",
            county_zone_id="NYC061",
            fire_zone_id="NYZ212",
            radar_station="KOKX",
        ),
        loc("Drifted", 40.7128, -74.006, cwa_office="PHI", radar_station="KDIX"),
    ]
    for cassette in ("point_nyc", "point_alaska"):
        routes = cassette_routes(cassette)
        props = json.loads(next(iter(routes.values()))[1])["properties"]
        fresh = zone_enrichment_service._extract_zone_fields(props)
        out.append(
            {
                "properties": props,
                "fields": {k: v for k, v in fresh.items() if v is not None},
                "diffs": [
                    [enc(s), zone_enrichment_service.diff_zone_fields(s, fresh)] for s in stored
                ],
            }
        )
    write("zone_fields", None, out, call="zone_fields")

    # Parsers on edge-case payloads.
    currents = [
        {
            "properties": {
                "textDescription": "",
                "temperature": {"value": "31.5", "unitCode": "wmoUnit:degF"},
                "relativeHumidity": {"value": 92.5},
                "windSpeed": {"value": 5, "unitCode": "wmoUnit:m_s-1"},
                "windDirection": {"value": "N"},
                "barometricPressure": {"value": 1015.2, "unitCode": "wmoUnit:hPa"},
                "visibility": {"value": 402},
                "uvIndex": {"value": True},
                "windChill": {"value": 20.0, "unitCode": "wmoUnit:degF"},
            }
        },
        {
            "properties": {
                "temperature": {"value": 35.0, "unitCode": "wmoUnit:degC"},
                "relativeHumidity": {"value": 60},
                "heatIndex": {"value": 41.0, "unitCode": "wmoUnit:degC"},
                "windSpeed": {"value": None},
                "windDirection": {"value": 182.5},
                "uvIndex": {"value": "x"},
            }
        },
        {
            "properties": {
                "temperature": {"value": 35.0, "unitCode": "wmoUnit:degC"},
                "relativeHumidity": {"value": 10},
                "heatIndex": {"value": 45.0, "unitCode": "wmoUnit:degC"},
            }
        },
        {},
    ]
    alerts = {
        "features": [
            ALERT_A,
            ALERT_B,
            ALERT_A,
            {
                "properties": {
                    "identifier": "ident-42",
                    "references": "nope",
                    "geocode": [],
                    "eventCode": {"SAME": "TOR"},
                    "affectedZones": "x",
                    "areaDesc": 5,
                    "onset": "",
                    "expires": "bad",
                }
            },
        ]
    }
    write(
        "parsers",
        None,
        {
            "current": [[p, weather_client_nws.parse_nws_current_conditions(p)] for p in currents],
            "alerts": [alerts, weather_client_nws.parse_nws_alerts(alerts)],
        },
        call="parsers",
    )

    # Alert aggregation across providers.
    def wa(**kw):
        base = {"title": "t", "description": "d"}
        base.update(kw)
        return WeatherAlert(**base)

    nws = WeatherAlerts(
        alerts=[
            wa(
                title="Flood",
                event="Flood Warning",
                areas=["Kings"],
                onset=at("2026-01-20T12:00:00+00:00"),
                id="urn:1",
                source="NWS",
                headline="short",
                severity="Unknown",
            ),
            wa(title="Wind", event="Wind Advisory", areas=["Queens"]),
        ]
    )
    pirate = WeatherAlerts(
        alerts=[
            wa(
                title="Flood PW",
                event="Flood Warning",
                areas=["kings "],
                onset=at("2026-01-20T12:45:00+00:00"),
                description="much longer description",
                headline="a longer headline",
                instruction="go",
                severity="Severe",
                urgency="Expected",
                source="pirateweather",
            ),
            wa(
                title="Flood later",
                event="Flood Warning",
                areas=["Kings"],
                onset=at("2026-01-20T14:00:00+00:00"),
            ),
            wa(title="Heat", event="Heat Advisory", areas=[]),
        ]
    )
    inputs = {"nws": enc(nws), "secondary": enc(pirate)}  # before tagging mutates them
    merged = AlertAggregator().aggregate_alerts(nws, pirate)
    for alert in merged.alerts:
        alert.areas = sorted(alert.areas)  # Python unions areas through a set
    write("aggregator", None, {**inputs, "merged": merged}, call="aggregator")


async def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    await current_scenarios()
    await current_selection_scenario()
    await forecast_scenarios()
    await hourly_scenarios()
    await alert_scenarios()
    await all_data_scenario()
    await station_scenarios()
    await text_product_scenarios()
    await aviation_scenarios()
    await marine_scenarios()
    pure_scenarios()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
