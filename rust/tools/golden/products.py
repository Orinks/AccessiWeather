"""Golden parity data for the Rust text-products port (aw_providers::products).

Run from the Python checkout:

    uv run python <worktree>/rust/tools/golden/products.py

Drives the real Python code (iem_client, weather_client_nws text products,
surf_conditions, ForecastProductService, NationalDiscussionService, the
Forecaster Notes loaders and the Advanced Lookup executor) through a fake
httpx transport and writes the parsed results, the exact request URLs and
the canned responses to rust/testdata/golden/products/*.json.

Responses are matched by longest URL prefix, like the Rust FixtureClient.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import inspect
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import yaml

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "products"
CASSETTES = Path.cwd() / "tests" / "integration" / "cassettes"
NOW = datetime(2026, 5, 1, 18, 0, tzinfo=UTC)
IEM = "https://mesonet.agron.iastate.edu"
NWS = "https://api.weather.gov"
MARINE = "https://marine-api.open-meteo.com/v1"

# ---------------------------------------------------------------------------
# Fake httpx transport
# ---------------------------------------------------------------------------


class Transport:
    def __init__(self, responses: list[dict]):
        self.responses = responses
        self.requests: list[str] = []

    def respond(self, url: str, params):
        wire = str(httpx.Request("GET", url, params=params).url)
        self.requests.append(wire)
        matches = [r for r in self.responses if wire.startswith(r["url"])]
        if not matches:
            raise AssertionError(f"no golden response for {wire}")
        spec = max(matches, key=lambda r: len(r["url"]))
        if "error" in spec:
            raise httpx.ConnectError(spec["error"])
        return FakeResponse(spec)


class FakeResponse:
    def __init__(self, spec: dict):
        self.status_code = spec.get("status", 200)
        self._spec = spec

    @property
    def text(self) -> str:
        if "text" in self._spec:
            return self._spec["text"]
        return json.dumps(self._spec.get("json"))

    def json(self):
        if "text" in self._spec:
            return json.loads(self._spec["text"])
        return copy.deepcopy(self._spec.get("json"))


CURRENT: Transport | None = None


class FakeAsyncClient:
    def __init__(self, *_args, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, url, params=None, headers=None, **_kwargs):
        del headers
        return CURRENT.respond(url, params)


class FakeClient:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def get(self, url, params=None, headers=None, **_kwargs):
        del headers
        return CURRENT.respond(url, params)


httpx.AsyncClient = FakeAsyncClient
httpx.Client = FakeClient

# Imports after patching so nothing captures the real clients.
from accessiweather import iem_client, surf_conditions  # noqa: E402
from accessiweather.cache import Cache  # noqa: E402
from accessiweather.iem_client import IemProductFetchError  # noqa: E402
from accessiweather.models import Location, TextProduct  # noqa: E402
from accessiweather.services.forecast_product_service import (  # noqa: E402
    ForecastProductService,
)
from accessiweather.services.national_discussion_service import (  # noqa: E402
    NationalDiscussionService,
)
from accessiweather.ui.dialogs import forecast_product_formatting as fmt  # noqa: E402
from accessiweather.ui.dialogs import forecast_products_dialog as fpd  # noqa: E402
from accessiweather.ui.dialogs.advanced_text_product_dialog import (  # noqa: E402
    AdvancedTextProductDialog,
)
from accessiweather.ui.dialogs.national_products_dialog import (  # noqa: E402
    NationalProductsDialog,
)
from accessiweather.weather_client_nws import (  # noqa: E402
    TextProductFetchError,
    get_nws_daily_climate_locations,
    get_nws_daily_climate_report,
    get_nws_discussion,
    get_nws_observation_station_ids_for_point,
    get_nws_text_product,
    get_nws_text_product_history,
)

iem_client._now_utc = lambda: NOW


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is not None else NOW.replace(tzinfo=None)


surf_conditions.datetime = FrozenDatetime

# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def iso(value: datetime | None):
    if value is None:
        return None
    if value.tzinfo is None:
        return "naive:" + value.isoformat()
    return value.isoformat()


def product(p):
    if p is None:
        return None
    data = dataclasses.asdict(p)
    data["issuance_time"] = iso(p.issuance_time)
    return data


def product_result(r):
    if isinstance(r, list):
        return {"many": [product(p) for p in r]}
    return {"one": product(r)}


def location_json(loc: Location) -> dict:
    data = dataclasses.asdict(loc)
    return {k: v for k, v in data.items() if v not in (None, False)}


def run(make, responses: list[dict], serialise):
    """Run ``make()`` (a value or coroutine) against canned responses."""
    global CURRENT
    CURRENT = Transport(responses)
    try:
        value = make()
        if inspect.iscoroutine(value):
            value = asyncio.run(value)
        outcome = {"ok": serialise(value)}
    except (IemProductFetchError, TextProductFetchError) as exc:
        outcome = {"error": str(exc)}
    return outcome, CURRENT.requests


def case(name: str, call: dict, responses: list[dict], make, serialise=product) -> dict:
    outcome, requests = run(make, responses, serialise)
    return {
        "name": name,
        "call": call,
        "responses": responses,
        "requests": requests,
        "expect": outcome,
    }


def cassette(path: str) -> list[dict]:
    data = yaml.safe_load((CASSETTES / path).read_text(encoding="utf-8"))
    return data["interactions"]


def cassette_body(path: str, index: int = 0) -> str:
    return cassette(path)[index]["response"]["body"]["string"]


def write(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# IEM
# ---------------------------------------------------------------------------

AFOS = f"{IEM}/cgi-bin/afos/retrieve.py"


def afos_case(name, pil, responses, **kwargs):
    query = {
        "limit": kwargs.get("limit", 1),
        "start": iso(kwargs.get("start")),
        "end": iso(kwargs.get("end")),
        "order": kwargs.get("order", "desc"),
        "center": kwargs.get("center"),
        "wmo_id": kwargs.get("wmo_id"),
        "matches": kwargs.get("matches"),
        "aviation_afd": kwargs.get("aviation_afd", False),
    }
    return case(
        name,
        {"fn": "afos", "pil": pil, "query": query},
        responses,
        lambda: iem_client.fetch_iem_afos_text(pil, **kwargs),
    )


def iem_cases() -> list[dict]:
    cases = [
        afos_case(
            "afos_cassette_swody1",
            "SWODY1",
            [{"url": AFOS, "text": cassette_body("iem/afos_swody1.yaml")}],
        ),
        afos_case(
            "afos_history_filters",
            " afddmx ",
            [{"url": AFOS, "text": "historical text"}],
            limit=5,
            start=datetime(2026, 4, 1, tzinfo=UTC),
            end=datetime(2026, 4, 1, 19, 30, 0, 250000, tzinfo=timezone(timedelta(hours=-5))),
            order="asc",
            center="kdmx",
            wmo_id="fxus63",
            matches=" AVIATION ",
        ),
        afos_case(
            "afos_aviation_flag",
            "AFDDMX",
            [{"url": AFOS, "text": "aviation section"}],
            aviation_afd=True,
            limit=0,
        ),
        afos_case(
            "afos_blank_center_is_sent_empty",
            "AFDDMX",
            [{"url": AFOS, "text": "text"}],
            center="  ",
        ),
        afos_case(
            "afos_strips_control_characters",
            "AFDRAH",
            [{"url": AFOS, "text": "\x01 627\r\nAFDRAH text\x03\n"}],
        ),
        afos_case("afos_http_error", "SWODY1", [{"url": AFOS, "status": 503, "text": "slow"}]),
        afos_case(
            "afos_iem_error_text",
            "PMDSPD",
            [{"url": AFOS, "text": "\n  ERROR: Could not Find: PMDSPD\nmore\n"}],
        ),
        afos_case("afos_empty_text", "PMDSPD", [{"url": AFOS, "text": " \x03\x01 \n"}]),
        afos_case("afos_transport_error", "PMDSPD", [{"url": AFOS, "error": "boom"}]),
        afos_case("afos_blank_pil", "   ", []),
    ]

    def spc_outlook(name, body, lat, lon, day, current, valid_at, max_items, status=200):
        responses = [{"url": f"{IEM}/json/spcoutlook.py", "status": status, **body}]
        return case(
            name,
            {
                "fn": "spc_outlook",
                "lat": lat,
                "lon": lon,
                "day": day,
                "current": current,
                "valid_at": iso(valid_at),
                "max_items": max_items,
            },
            responses,
            lambda: iem_client.fetch_iem_spc_outlook(
                lat, lon, day=day, current=current, valid_at=valid_at, max_items=max_items
            ),
        )

    cases += [
        spc_outlook(
            "spc_outlook_cassette",
            {"text": cassette_body("iem/spc_outlook_day1.yaml")},
            35.7796,
            -78.6382,
            1,
            False,
            datetime(2026, 5, 7, 12, tzinfo=UTC),
            2,
        ),
        spc_outlook(
            "spc_outlook_plural",
            {
                "json": {
                    "generated_at": "2026-05-01T12:00:00Z",
                    "outlooks": [
                        {"category": "ENH", "threshold": "CATEGORICAL", "valid": "2026-05-01T13:00:00Z"}
                    ],
                }
            },
            38.907,
            -77.037,
            1,
            True,
            None,
            5,
        ),
        spc_outlook(
            "spc_outlook_current_ignores_valid_time",
            {"json": {"outlook": {"category": "MRGL", "threshold": "CATEGORICAL"}}},
            38.907,
            -77.0,
            2,
            True,
            datetime(2026, 3, 6, 20, tzinfo=UTC),
            5,
        ),
        spc_outlook(
            "spc_outlook_value_formatting_and_limit",
            {
                "json": {
                    "generated_at": "",
                    "generated": 1714500000,
                    "features": [
                        {"category": 0, "threshold": False, "valid": 2.5, "mdnum": [1, "a", None]},
                        "not a dict",
                        {"category": "", "threshold": None, "watch_prob": 1e20},
                        {"concerning": "third"},
                    ],
                }
            },
            40.0,
            -100.25,
            12,
            True,
            None,
            3,
        ),
        spc_outlook("spc_outlook_list_payload", {"json": []}, 40.0, -100.0, 0, True, None, None),
        spc_outlook(
            "spc_outlook_empty_list_stops_key_search",
            {"json": {"outlooks": [], "outlook": {"category": "SLGT"}}},
            40.0,
            -100.0,
            1,
            True,
            None,
            5,
        ),
        spc_outlook("spc_outlook_http_error", {"json": {}}, 40.0, -100.0, 1, True, None, 5, 500),
    ]

    def mcds(name, body, active_only, start=None, end=None, max_items=5, lat=42.0, lon=-95.0):
        return case(
            name,
            {
                "fn": "spc_mcds",
                "lat": lat,
                "lon": lon,
                "active_at": iso(NOW) if active_only else None,
                "start": iso(start),
                "end": iso(end),
                "max_items": max_items,
            },
            [{"url": f"{IEM}/json/spcmcd.py", **body}],
            lambda: iem_client.fetch_iem_spc_mcds(
                lat,
                lon,
                active_only=active_only,
                start=start,
                end=end,
                max_items=max_items,
            ),
        )

    cases += [
        mcds(
            "spc_mcd_active_summary",
            {
                "json": {
                    "mcds": [
                        {
                            "mdnum": 123,
                            "product_issue": "2026-05-01T17:00:00Z",
                            "concerning": "Severe potential",
                            "watch_prob": 60,
                        },
                        {"mdnum": 124, "utc_issue": "2026-05-01T19:00:00Z"},
                        {"mdnum": 125, "utc_expire": "2026-05-01T18:00:00Z"},
                        {"mdnum": 126, "utc_expire": "2026-05-01T18:00:01+00:00"},
                    ]
                }
            },
            True,
        ),
        mcds(
            "spc_mcd_limit",
            {
                "json": {
                    "mcds": [
                        {"mdnum": 1, "concerning": "first"},
                        {"mdnum": 2, "concerning": "second"},
                        {"mdnum": 3, "concerning": "third"},
                    ]
                }
            },
            True,
            max_items=2,
        ),
        mcds(
            "spc_mcd_archive_window",
            {
                "json": {
                    "mcds": [
                        {"mdnum": 1, "utc_issue": "2026-05-01T12:00:00Z", "concerning": "inside"},
                        {"mdnum": 2, "utc_issue": "2026-04-01T12:00:00Z", "concerning": "outside"},
                        {"mdnum": 3, "concerning": "undated"},
                        {"mdnum": 4, "utc_issue": "2026-05-02T00:00:00Z", "concerning": "at end"},
                    ]
                }
            },
            False,
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 5, 2, tzinfo=UTC),
        ),
        mcds(
            "spc_mcd_none_active",
            {"json": {"mcds": [{"mdnum": 9, "utc_expire": "2026-05-01T10:00:00Z"}]}},
            True,
        ),
        mcds(
            "spc_mcd_features_with_properties",
            {
                "json": {
                    "features": [
                        {
                            "properties": {"utc_issue": "2026-05-01T17:00:00Z"},
                            "mdnum": 77,
                            "concerning": "top-level fields render",
                        }
                    ]
                }
            },
            True,
            max_items=0,
        ),
        mcds("spc_mcd_archive_no_items", {"json": {"mcds": []}}, False),
    ]

    def watches(name, body, valid_at, max_items=5):
        return case(
            name,
            {
                "fn": "spc_watches",
                "lat": 38.0,
                "lon": -77.0,
                "active_at": iso(valid_at or NOW),
                "max_items": max_items,
            },
            [{"url": f"{IEM}/json/spcwatch.py", **body}],
            lambda: iem_client.fetch_iem_spc_watches(
                38.0, -77.0, valid_at=valid_at, max_items=max_items
            ),
        )

    cases += [
        watches(
            "spc_watches_summary",
            {
                "json": {
                    "features": [
                        {
                            "properties": {
                                "sel": "SEL7",
                                "type": "TOR",
                                "number": 67,
                                "issue": "2026-03-16T14:50:00Z",
                                "expire": "2026-03-16T23:13:00Z",
                                "is_pds": False,
                                "max_hail_size": 1.75,
                            }
                        },
                        {"no_properties": True},
                        {
                            "properties": {
                                "sel": "SEL8",
                                "type": "SVR",
                                "issue": "2026-03-16T15:00:00Z",
                                "expire": "2026-03-17T04:00:00Z",
                            }
                        },
                    ]
                }
            },
            datetime(2026, 3, 16, 18, tzinfo=UTC),
            max_items=2,
        ),
        watches(
            "spc_watches_filters_expired",
            {
                "json": {
                    "features": [
                        {
                            "properties": {
                                "sel": "SEL7",
                                "issue": "2026-03-16T14:50:00Z",
                                "expire": "2026-03-16T23:13:00Z",
                            }
                        },
                        {
                            "properties": {
                                "sel": "SEL8",
                                "issue": "2026-03-16T23:00:00Z",
                                "expire": "2026-03-17T04:00:00Z",
                            }
                        },
                    ]
                }
            },
            datetime(2026, 3, 16, 23, 30, tzinfo=timezone(timedelta(hours=-4))),
        ),
        watches("spc_watches_none_active_uses_now", {"json": {"features": [
            {"properties": {"sel": "SEL1", "expire": "2026-05-01T12:00:00Z"}}
        ]}}, None),
        watches("spc_watches_empty", {"json": {"features": []}}, None),
        watches("spc_watches_list_payload", {"json": ["x"]}, None),
        watches("spc_watches_transport_error", {"error": "timed out"}, None),
    ]

    def wpc_outlook(name, body, valid_at, day=1, limit=1, max_items=5):
        return case(
            name,
            {
                "fn": "wpc_outlook",
                "lat": 38.907,
                "lon": -77.037,
                "day": day,
                "valid_at": iso(valid_at),
                "now": iso(NOW),
                "limit": limit,
                "max_items": max_items,
            },
            [{"url": f"{IEM}/json/wpcoutlook.py", **body}],
            lambda: iem_client.fetch_iem_wpc_outlook(
                38.907, -77.037, day=day, valid_at=valid_at, limit=limit, max_items=max_items
            ),
        )

    cases += [
        wpc_outlook(
            "wpc_outlook_cassette",
            {"text": cassette_body("iem/wpc_outlook_day1.yaml")},
            datetime(2026, 5, 7, 12, tzinfo=UTC),
            max_items=2,
        ),
        wpc_outlook(
            "wpc_outlook_valid_time",
            {
                "json": {
                    "generated_at": "2026-05-01T12:00:00Z",
                    "outlooks": [
                        {
                            "day": 1,
                            "utc_product_issue": "2026-03-16T07:22:00Z",
                            "utc_issue": "2026-03-16T12:00:00Z",
                            "utc_expire": "2026-03-17T12:00:00Z",
                            "threshold": "MRGL",
                            "category": "CATEGORICAL",
                        }
                    ],
                }
            },
            datetime(2026, 3, 16, 18, tzinfo=UTC),
        ),
        wpc_outlook(
            "wpc_outlook_current_keyword",
            {
                "json": {
                    "generated_at": "2026-05-01T12:00:00Z",
                    "outlook": {
                        "day": 1,
                        "utc_issue": "2026-05-01T12:00:00Z",
                        "utc_expire": "2026-05-02T12:00:00Z",
                        "threshold": "MRGL",
                    },
                }
            },
            None,
            limit=0,
        ),
        wpc_outlook(
            "wpc_outlook_no_outlooks_drops_generated",
            {"json": {"generated_at": "2026-05-01T12:00:00Z", "outlooks": []}},
            None,
            day=9,
        ),
        wpc_outlook(
            "wpc_outlook_inactive",
            {"json": {"outlooks": [{"utc_expire": "2026-05-01T00:00:00Z"}]}},
            None,
            limit=3,
        ),
        wpc_outlook("wpc_outlook_http_error", {"status": 502, "json": {}}, None),
    ]

    def mpds(name, body, active_only, start=None, end=None, max_items=5):
        return case(
            name,
            {
                "fn": "wpc_mpds",
                "lat": 38.907,
                "lon": -77.037,
                "active_at": iso(NOW) if active_only else None,
                "start": iso(start),
                "end": iso(end),
                "max_items": max_items,
            },
            [{"url": f"{IEM}/json/wpcmpd.py", **body}],
            lambda: iem_client.fetch_iem_wpc_mpds(
                38.907,
                -77.037,
                active_only=active_only,
                start=start,
                end=end,
                max_items=max_items,
            ),
        )

    mpd_items = {
        "mpds": [
            {
                "product_num": 934,
                "product_id": "202605011728-KWNH-AWUS01-FFGMPD",
                "utc_issue": "2026-05-01T17:27:00Z",
                "utc_expire": "2026-05-01T20:27:00Z",
                "concerning": "HEAVY RAINFALL...FLASH FLOODING POSSIBLE",
                "product_href": "https://www.wpc.ncep.noaa.gov/metwatch/metwatch_mpd_multi.php?md=934",
            },
            {
                "product_num": 933,
                "utc_issue": "2026-05-01T10:00:00Z",
                "utc_expire": "2026-05-01T13:00:00Z",
            },
        ]
    }
    cases += [
        mpds("wpc_mpd_active", {"json": mpd_items}, True, max_items=3),
        mpds(
            "wpc_mpd_archive_window",
            {"json": mpd_items},
            False,
            start=datetime(2026, 5, 1, 9, tzinfo=UTC),
            end=datetime(2026, 5, 1, 12, tzinfo=UTC),
        ),
        mpds(
            "wpc_mpd_window_excludes_all",
            {"json": mpd_items},
            False,
            start=datetime(2026, 6, 1, tzinfo=UTC),
        ),
        mpds(
            "wpc_mpd_all_expired",
            {"json": {"mpds": [mpd_items["mpds"][1]]}},
            True,
        ),
        mpds("wpc_mpd_not_a_list", {"json": {"mpds": {"product_num": 1}}}, True),
    ]
    return cases


# ---------------------------------------------------------------------------
# NWS text products
# ---------------------------------------------------------------------------


def nws_product(pid, text, issued, **extra):
    return {"url": f"{NWS}/products/{pid}", "json": {"productText": text, "issuanceTime": issued, **extra}}


def nws_cases() -> list[dict]:
    disc = cassette("nws/discussion_nyc.yaml")
    listing_body = disc[1]["response"]["body"]["string"]
    product_body = disc[2]["response"]["body"]["string"]
    grid_body = json.loads(disc[0]["response"]["body"]["string"])
    newest_id = json.loads(listing_body)["@graph"][0]["id"]

    def text_product(name, product_type, office, responses):
        return case(
            name,
            {"fn": "text_product", "product_type": product_type, "office": office},
            responses,
            lambda: get_nws_text_product(product_type, office),
            product_result,
        )

    def history(name, product_type, office, responses, limit=10, start=None, end=None):
        return case(
            name,
            {
                "fn": "history",
                "product_type": product_type,
                "office": office,
                "limit": limit,
                "start": iso(start),
                "end": iso(end),
            },
            responses,
            lambda: get_nws_text_product_history(
                product_type, office, limit=limit, start=start, end=end
            ),
            lambda products: [product(p) for p in products],
        )

    afd_listing = f"{NWS}/products/types/AFD/locations/PHI"
    cases = [
        text_product(
            "afd_cassette_okx",
            "AFD",
            "OKX",
            [
                {"url": f"{NWS}/products/types/AFD/locations/OKX", "text": listing_body},
                {"url": f"{NWS}/products/{newest_id}", "text": product_body},
            ],
        ),
        text_product(
            "afd_unsorted_listing_picks_newest",
            "AFD",
            "PHI",
            [
                {
                    "url": afd_listing,
                    "json": {
                        "@graph": [
                            {"id": "afd-old", "issuanceTime": "2026-04-16T06:45:00+00:00"},
                            "junk",
                            {"id": "afd-new", "issuanceTime": "2026-04-16T13:32:00-04:00"},
                            {"id": "afd-tie", "issuanceTime": "2026-04-16T17:32:00+00:00"},
                        ]
                    },
                },
                nws_product("afd-new", "NEW AREA FORECAST DISCUSSION", None, headline=""),
            ],
        ),
        text_product("afd_empty_graph", "AFD", "PHI", [{"url": afd_listing, "json": {"@graph": []}}]),
        text_product("afd_no_office", "AFD", "", []),
        text_product(
            "hwo_body_issuance_wins_and_entry_headline",
            "HWO",
            "PHI",
            [
                {
                    "url": f"{NWS}/products/types/HWO/locations/PHI",
                    "json": {
                        "@graph": [
                            {
                                "id": "hwo-001",
                                "issuanceTime": "2026-04-16T10:00:00+00:00",
                                "headline": "Entry headline",
                            }
                        ]
                    },
                },
                nws_product("hwo-001", "HAZARDOUS WEATHER OUTLOOK", "2026-04-16T11:00:00"),
            ],
        ),
        text_product(
            "srf_headline_non_string",
            "SRF",
            "PHI",
            [
                {
                    "url": f"{NWS}/products/types/SRF/locations/PHI",
                    "json": {"@graph": [{"id": 42, "issuanceTime": "2026-06-07T10:00:00+00:00"}]},
                },
                nws_product("42", "SURF ZONE FORECAST", None, headline=123),
            ],
        ),
        text_product(
            "afd_missing_product_text",
            "AFD",
            "PHI",
            [
                {"url": afd_listing, "json": {"@graph": [{"id": "afd-1"}]}},
                {"url": f"{NWS}/products/afd-1", "json": {"productText": ""}},
            ],
        ),
        text_product(
            "sps_sorted_newest_first",
            "SPS",
            "PHI",
            [
                {
                    "url": f"{NWS}/products/types/SPS/locations/PHI",
                    "json": {
                        "@graph": [
                            {"id": "sps-middle", "issuanceTime": "2026-04-16T12:00:00+00:00"},
                            {"id": "sps-undated"},
                            {"issuanceTime": "2026-04-16T15:00:00+00:00"},
                            {"id": "sps-newest", "issuanceTime": "2026-04-16T14:00:00+00:00"},
                            {"id": "sps-empty", "issuanceTime": "2026-04-16T16:00:00+00:00"},
                            {"id": "sps-oldest", "issuanceTime": "2026-04-16T10:00:00+00:00"},
                        ]
                    },
                },
                nws_product("sps-middle", "SPS middle", "2026-04-16T12:00:00+00:00"),
                nws_product("sps-undated", "SPS undated", None),
                nws_product("sps-newest", "SPS newest", "2026-04-16T14:00:00+00:00", headline="Newest"),
                {"url": f"{NWS}/products/sps-empty", "json": {}},
                nws_product("sps-oldest", "SPS oldest", "2026-04-16T10:00:00+00:00"),
            ],
        ),
        text_product(
            "sps_empty_graph",
            "SPS",
            "PHI",
            [{"url": f"{NWS}/products/types/SPS/locations/PHI", "json": {}}],
        ),
        text_product(
            "sps_product_http_error",
            "SPS",
            "PHI",
            [
                {
                    "url": f"{NWS}/products/types/SPS/locations/PHI",
                    "json": {"@graph": [{"id": "sps-1"}]},
                },
                {"url": f"{NWS}/products/sps-1", "status": 500, "json": {}},
            ],
        ),
        text_product(
            "sps_product_transport_error",
            "SPS",
            "PHI",
            [
                {
                    "url": f"{NWS}/products/types/SPS/locations/PHI",
                    "json": {"@graph": [{"id": "sps-1"}]},
                },
                {"url": f"{NWS}/products/sps-1", "error": "reset by peer"},
            ],
        ),
        text_product(
            "afd_listing_http_error",
            "AFD",
            "PHI",
            [{"url": afd_listing, "status": 500, "json": {}}],
        ),
        text_product(
            "afd_listing_transport_error",
            "AFD",
            "PHI",
            [{"url": afd_listing, "error": "timed out"}],
        ),
        text_product(
            "afd_product_transport_error",
            "AFD",
            "PHI",
            [
                {"url": afd_listing, "json": {"@graph": [{"id": "afd-1"}]}},
                {"url": f"{NWS}/products/afd-1", "error": "timed out"},
            ],
        ),
        history(
            "history_newest_first",
            "AFD",
            "PHI",
            [
                {
                    "url": f"{NWS}/products?",
                    "json": {
                        "@graph": [
                            {"id": "afd-old", "issuanceTime": "2026-04-16T06:45:00+00:00"},
                            {"id": "afd-new", "issuanceTime": "2026-04-16T17:32:00+00:00"},
                        ]
                    },
                },
                nws_product("afd-old", "OLD", "2026-04-16T06:45:00+00:00"),
                nws_product("afd-new", "NEW", "2026-04-16T17:32:00+00:00"),
            ],
        ),
        history(
            "history_date_filters",
            "CLI",
            "PHI",
            [{"url": f"{NWS}/products?", "json": {"@graph": []}}],
            limit=3,
            start=datetime(2026, 4, 1, tzinfo=UTC),
            end=datetime(2026, 4, 2, 6, 30, tzinfo=timezone(timedelta(hours=-5))),
        ),
        history("history_no_office", "AFD", "", []),
        history(
            "history_listing_http_error",
            "LSR",
            "PHI",
            [{"url": f"{NWS}/products?", "status": 503, "json": {}}],
        ),
        history(
            "history_product_http_error",
            "LSR",
            "PHI",
            [
                {"url": f"{NWS}/products?", "json": {"@graph": [{"id": "lsr-1"}]}},
                {"url": f"{NWS}/products/lsr-1", "status": 404, "json": {}},
            ],
        ),
        case(
            "daily_climate_report_station",
            {"fn": "daily_climate_report", "station": "RDU"},
            [
                {
                    "url": f"{NWS}/products?",
                    "json": {
                        "@graph": [
                            {"id": "cli-rdu", "issuanceTime": "2026-05-22T20:54:00+00:00"}
                        ]
                    },
                },
                nws_product("cli-rdu", "CLIMATE REPORT\n...RALEIGH...", "2026-05-22T20:54:00+00:00"),
            ],
            lambda: get_nws_daily_climate_report("RDU"),
        ),
        case(
            "daily_climate_report_k_prefix",
            {"fn": "daily_climate_report", "station": " kttn "},
            [{"url": f"{NWS}/products?", "json": {"@graph": []}}],
            lambda: get_nws_daily_climate_report(" kttn "),
        ),
        case(
            "daily_climate_report_blank",
            {"fn": "daily_climate_report", "station": ""},
            [],
            lambda: get_nws_daily_climate_report(""),
        ),
        case(
            "daily_climate_locations",
            {"fn": "daily_climate_locations"},
            [
                {
                    "url": f"{NWS}/products/types/CLI/locations",
                    "json": {"locations": {"TTN": None, "phl": "Philadelphia", " ": None}},
                }
            ],
            lambda: get_nws_daily_climate_locations(),
            sorted,
        ),
        case(
            "daily_climate_locations_http_error",
            {"fn": "daily_climate_locations"},
            [{"url": f"{NWS}/products/types/CLI/locations", "status": 503, "json": {}}],
            lambda: get_nws_daily_climate_locations(),
            sorted,
        ),
        case(
            "daily_climate_locations_malformed",
            {"fn": "daily_climate_locations"},
            [{"url": f"{NWS}/products/types/CLI/locations", "json": {"locations": []}}],
            lambda: get_nws_daily_climate_locations(),
            sorted,
        ),
    ]

    stations_url = f"{NWS}/gridpoints/PHI/62,81/stations"
    cases += [
        case(
            "observation_stations_limited",
            {"fn": "observation_stations", "lat": 39.965, "lon": -74.80505, "limit": 2},
            [
                {
                    "url": f"{NWS}/points/",
                    "json": {"properties": {"observationStations": stations_url}},
                },
                {
                    "url": stations_url,
                    "json": {
                        "observationStations": [
                            f"{NWS}/stations/kvay/",
                            f"{NWS}/stations/KTTN",
                            f"{NWS}/stations/KTTN",
                            123,
                            f"{NWS}/stations/KPHL",
                        ]
                    },
                },
            ],
            lambda: get_nws_observation_station_ids_for_point(39.965, -74.80505, limit=2),
            list,
        ),
        case(
            "observation_stations_missing_url",
            {"fn": "observation_stations", "lat": 39.965, "lon": -74.805, "limit": 12},
            [{"url": f"{NWS}/points/", "json": {"properties": {}}}],
            lambda: get_nws_observation_station_ids_for_point(39.965, -74.805),
            list,
        ),
        case(
            "observation_stations_point_error",
            {"fn": "observation_stations", "lat": 39.965, "lon": -74.805, "limit": 12},
            [{"url": f"{NWS}/points/", "status": 404, "json": {}}],
            lambda: get_nws_observation_station_ids_for_point(39.965, -74.805),
            list,
        ),
    ]

    def discussion(name, grid, responses):
        async def _run():
            async with httpx.AsyncClient() as client:
                return await get_nws_discussion(client, {"User-Agent": "x"}, grid, NWS)

        return case(
            name,
            {"fn": "discussion", "grid": grid},
            responses,
            _run,
            lambda pair: [pair[0], iso(pair[1])],
        )

    cases += [
        discussion(
            "discussion_cassette_okx",
            grid_body,
            [
                {"url": f"{NWS}/products/types/AFD/locations/OKX", "text": listing_body},
                {"url": f"{NWS}/products/{newest_id}", "text": product_body},
            ],
        ),
        discussion(
            "discussion_empty_graph",
            {"properties": {"forecast": f"{NWS}/gridpoints/PHI/36,38/forecast"}},
            [{"url": afd_listing, "json": {"@graph": []}}],
        ),
        discussion(
            "discussion_listing_error",
            {"properties": {"forecast": f"{NWS}/gridpoints/PHI/36,38/forecast"}},
            [{"url": afd_listing, "status": 500, "json": {}}],
        ),
        discussion("discussion_no_forecast_url", {"properties": {}}, []),
        discussion("discussion_short_url", {"properties": {"forecast": "https://x/forecast"}}, []),
    ]
    return cases


# ---------------------------------------------------------------------------
# Surf / beach conditions
# ---------------------------------------------------------------------------


def surf_cases() -> list[dict]:
    porto = Location(name="Porto", latitude=41.15, longitude=-8.63, country_code="PT")

    def marine(name, data, loc=porto):
        return case(
            name,
            {"fn": "marine_format", "data": data, "location": location_json(loc), "now": iso(NOW)},
            [],
            lambda: (
                report.to_text_product()
                if (report := surf_conditions.format_openmeteo_marine_report(data, loc))
                else None
            ),
        )

    full = {
        "current": {
            "time": "2026-06-07T12:00",
            "wave_height": 1.4,
            "wave_direction": 270,
            "wave_period": 8,
            "swell_wave_height": 0.9,
            "swell_wave_direction": 11.25,
            "swell_wave_period": 11.04,
            "sea_surface_temperature": 18.5,
        },
        "current_units": {
            "wave_height": "m",
            "wave_period": "s",
            "swell_wave_height": "m",
            "swell_wave_period": "s",
            "sea_surface_temperature": "°C",
        },
    }
    cases = [
        marine("marine_full_report", full),
        marine(
            "marine_list_values_and_odd_units",
            {
                "current": {
                    "time": "2026-06-07T12:00Z",
                    "wave_height": [2.0, 3.0],
                    "wave_direction": "offshore",
                    "wave_period": [],
                    "swell_wave_direction": " 33.75 ",
                    "swell_wave_height": "  ",
                    "sea_surface_temperature": 0.04,
                },
                "current_units": {"wave_height": 5, "sea_surface_temperature": ""},
            },
        ),
        marine("marine_invalid_time_uses_now", {"current": {"time": "not-a-time", "wave_height": 1.2}}),
        marine("marine_offset_time", {"current": {"time": "2026-06-07T12:00+01:00", "wave_height": True}}),
        marine("marine_empty_current", {"current": {}}),
        marine("marine_only_time", {"current": {"time": "2026-06-07T12:00"}}),
        marine("marine_units_not_dict", {"current": {"wave_height": 1}, "current_units": []}),
        case(
            "marine_fetch",
            {"fn": "marine_fetch", "location": location_json(porto), "now": iso(NOW)},
            [
                {
                    "url": f"{MARINE}/marine",
                    "json": {
                        "current": {"time": "2026-06-07T12:00", "wave_height": 2.0},
                        "current_units": {"wave_height": "m"},
                    },
                }
            ],
            lambda: surf_conditions.fetch_openmeteo_marine_surf_conditions(porto),
        ),
        case(
            "marine_fetch_http_error",
            {"fn": "marine_fetch", "location": location_json(porto), "now": iso(NOW)},
            [{"url": f"{MARINE}/marine", "status": 500, "json": {}}],
            lambda: surf_conditions.fetch_openmeteo_marine_surf_conditions(porto),
        ),
    ]

    def pirate(name, payload, loc):
        client = SimpleNamespace(
            _pirate_weather_client_for_location=lambda _loc: SimpleNamespace(
                get_forecast_data=lambda _loc: _async(payload)
            )
        )
        return case(
            name,
            {"fn": "pirate", "payload": payload, "location": location_json(loc), "now": iso(NOW)},
            [],
            lambda: surf_conditions.fetch_pirate_weather_beach_conditions(loc, client),
        )

    brighton = Location(name="Brighton", latitude=50.82, longitude=-0.14, country_code="GB")
    cases += [
        pirate(
            "pirate_full",
            {
                "currently": {
                    "summary": "Breezy",
                    "temperature": 70,
                    "apparentTemperature": 68.25,
                    "windSpeed": 14,
                    "windGust": 24,
                    "windBearing": 180,
                    "uvIndex": 6,
                    "visibility": 9.99,
                    "precipProbability": 0.285,
                }
            },
            brighton,
        ),
        pirate(
            "pirate_partial",
            {"currently": {"summary": "Clear", "windSpeed": 8, "windBearing": "calm", "precipProbability": True}},
            porto,
        ),
        pirate("pirate_currently_not_dict", {"currently": []}, porto),
        pirate("pirate_currently_empty", {"currently": {}}, porto),
        pirate("pirate_only_nulls", {"currently": {"summary": None, "temperature": None}}, porto),
    ]
    return cases


async def _async(value):
    return value


# ---------------------------------------------------------------------------
# National discussions
# ---------------------------------------------------------------------------


def national_cases() -> list[dict]:
    def afos_response(pil, **spec):
        return {"url": f"{AFOS}?pil={pil}&", **spec}

    responses = [
        afos_response("PMDSPD", text="PMDSPD\nShort Range Discussion text"),
        afos_response("PMDEPD", status=503, text="busy"),
        afos_response("PMDET4", text="ERROR: Could not Find: PMDET4"),
        afos_response("SWODY1", text="SWODY1\nDay 1"),
        afos_response("SWODY2", text="\x01SWODY2\nDay 2\x03"),
        afos_response("SWODY3", error="timed out"),
        afos_response("QPFPFD", text="QPF text"),
        afos_response("PMDMRD", text=" \n "),
        afos_response("TWOAT", text="Atlantic outlook"),
        afos_response("TWOEP", text="East Pacific outlook"),
    ]

    def serialise(result):
        return result

    cases = []
    for season in (True, False):
        service = NationalDiscussionService(request_delay=0)
        NationalDiscussionService.is_hurricane_season = staticmethod(lambda season=season: season)
        month_now = datetime(2026, 9 if season else 1, 15, tzinfo=UTC)
        cases.append(
            case(
                f"fetch_all_{'in' if season else 'out_of'}_season",
                {"fn": "fetch_all", "now": iso(month_now)},
                responses,
                lambda service=service: service.fetch_all_discussions(),
                serialise,
            )
        )
    return cases


# ---------------------------------------------------------------------------
# Forecaster Notes tabs
# ---------------------------------------------------------------------------


def borrow(cls, names, base=object):
    attrs = {name: inspect.getattr_static(cls, name) for name in names}
    return type(f"{cls.__name__}Stub", (base,), attrs)


DialogStub = borrow(
    fpd.ForecastProductsDialog,
    [
        "_TABS",
        "_create_widgets",
        "_should_autoload_tab",
        "_add_tab_panel",
        "_make_loader",
        "_make_advanced_lookup_opener",
        "_active_iem_tab_product_or_none",
        "_load_active_iem_tab_product",
        "_check_daily_climate_notification",
        "_on_panel_availability_resolved",
    ],
)


def dialog_stub(location, service=None):
    stub = DialogStub()
    stub._location = location
    stub._service = service
    stub._ai_explainer = None
    stub._app = None
    stub.SetSizer = MagicMock()
    stub._on_panel_availability_resolved = MagicMock()
    return stub


class RecordingPanel:
    created: list[dict] = []

    def __init__(self, **kwargs):
        self.product_type = kwargs["product_type"]
        RecordingPanel.created.append(kwargs)


def tab_plans(location) -> dict:
    fpd.wx = MagicMock()
    fpd.ForecastProductPanel = RecordingPanel
    RecordingPanel.created = []
    stub = dialog_stub(location)
    stub._create_widgets()
    labels = [c.args[1] for c in stub.notebook.AddPage.call_args_list]
    return {
        "location": location_json(location),
        "tabs": [
            {
                "product_type": kw["product_type"],
                "label": label,
                "autoload": kw["autoload"],
                "panel_cwa": kw["cwa_office"],
            }
            for kw, label in zip(RecordingPanel.created, labels, strict=True)
        ],
        "pending": [tab.product_type for tab in stub._pending_iem_tabs],
    }


def advanced_lookup_products(location) -> dict:
    opened: dict[str, str] = {}
    stub = dialog_stub(location)
    for tab in fpd.ForecastProductsDialog._TABS:
        fpd.show_advanced_text_product_dialog = lambda *_a, initial_product_type, **_k: opened.update(
            {tab.product_type: initial_product_type}
        )
        stub._make_advanced_lookup_opener(tab.product_type)()
    return opened


def tab_cases() -> dict:
    raleigh = Location(
        name="Raleigh, NC",
        latitude=35.78,
        longitude=-78.64,
        country_code="US",
        cwa_office="RAH",
        radar_station="KRAX",
    )
    plans = [
        tab_plans(raleigh),
        tab_plans(Location(name="Porto", latitude=41.15, longitude=-8.63, country_code="PT")),
        tab_plans(Location(name="Blank office", latitude=40.0, longitude=-100.0, cwa_office="")),
    ]

    listing = f"{NWS}/products/types"
    loader_responses = {
        "AFD": [
            {"url": f"{listing}/AFD/locations/RAH", "json": {"@graph": [{"id": "afd-rah"}]}},
            nws_product("afd-rah", "AFD RAH", "2026-05-01T15:00:00+00:00"),
        ],
        "HWO": [{"url": f"{listing}/HWO/locations/RAH", "json": {"@graph": []}}],
        "SPS": [
            {"url": f"{listing}/SPS/locations/RAH", "json": {"@graph": [{"id": "s1"}, {"id": "s2"}]}},
            nws_product("s1", "SPS one", "2026-05-01T12:00:00+00:00"),
            nws_product("s2", "SPS two", "2026-05-01T13:00:00+00:00"),
        ],
        "SURF": [
            {"url": f"{listing}/SRF/locations/RAH", "json": {"@graph": []}},
            {
                "url": f"{MARINE}/marine",
                "json": {"current": {"time": "2026-05-01T14:00:00Z", "wave_height": 0.5}},
            },
        ],
        "CLI": [
            {
                "url": f"{NWS}/points/",
                "json": {"properties": {"observationStations": f"{NWS}/gridpoints/RAH/1,1/stations"}},
            },
            {
                "url": f"{NWS}/gridpoints/RAH/1,1/stations",
                "json": {"observationStations": [f"{NWS}/stations/KRDU", f"{NWS}/stations/KIGX"]},
            },
            {"url": f"{listing}/CLI/locations", "json": {"locations": {"RDU": "Raleigh", "GSO": ""}}},
            {"url": f"{NWS}/products?", "json": {"@graph": [{"id": "cli-rdu"}]}},
            nws_product("cli-rdu", "CLIMATE REPORT RDU", "2026-05-01T06:00:00+00:00"),
        ],
        "SPC_OUTLOOK": [
            {
                "url": f"{IEM}/json/spcoutlook.py",
                "json": {
                    "generated_at": "2026-05-01T12:00:00Z",
                    "outlooks": [{"category": "SLGT", "threshold": "CATEGORICAL"}] * 4,
                },
            }
        ],
        "SPC_MCD": [
            {
                "url": f"{IEM}/json/spcmcd.py",
                "json": {"mcds": [{"mdnum": 5, "utc_expire": "2026-05-01T12:00:00Z"}]},
            }
        ],
        "SPC_WATCHES": [{"url": f"{IEM}/json/spcwatch.py", "error": "timed out"}],
        "WPC_ERO": [
            {
                "url": f"{IEM}/json/wpcoutlook.py",
                "json": {"outlook": {"threshold": "MRGL", "utc_issue": "2026-05-01T12:00:00Z"}},
            }
        ],
        "WPC_MPD": [{"url": f"{IEM}/json/wpcmpd.py", "json": {"mpds": []}}],
    }
    loaders = []
    for tab in fpd.ForecastProductsDialog._TABS:
        service = ForecastProductService(Cache())
        stub = dialog_stub(raleigh, service)
        entry = case(
            f"loader_{tab.product_type.lower()}",
            {"fn": "load_tab", "product_type": tab.product_type, "location": location_json(raleigh)},
            loader_responses[tab.product_type],
            lambda stub=stub, tab=tab: stub._make_loader(tab)(),
            product_result,
        )
        loaders.append(entry)

    active_texts = [
        "WPC Day 1 Excessive Rainfall Outlook\n\nGenerated: 2026-05-01T12:00:00Z\n\nNo active outlooks were returned.",
        "SPC Watches\n\nWatch 1:\nSEL: SEL8\nType: SVR\n",
        "SPC Mesoscale Discussions\n\nNo matching point-based products were returned for this location.",
        "Title\n\n  No structured data returned.  ",
        "Title\nGenerated: No active products",
        "Title\n\nProduct 1:\nConcerning: No active severe weather expected\n",
        "",
    ]
    active = [
        {
            "text": text,
            "active": fpd.ForecastProductsDialog._active_iem_tab_product_or_none(
                TextProduct("X", "X", "IEM", None, text, None)
            )
            is not None,
        }
        for text in active_texts
    ]

    availability = []
    for types, index, has_product in [
        (["AFD", "HWO", "SPS"], 1, False),
        (["AFD", "HWO", "SPS"], 0, False),
        (["AFD", "HWO", "SPS"], 2, True),
        (["SURF"], 0, False),
        (["SURF", "CLI"], 1, False),
        (["SPC_OUTLOOK", "WPC_ERO"], 0, False),
    ]:
        stub = SimpleNamespace(
            notebook=MagicMock(),
            panels=[SimpleNamespace(product_type=t) for t in types],
        )
        fpd.ForecastProductsDialog._on_panel_availability_resolved(
            stub, stub.panels[index], has_product
        )
        availability.append(
            {
                "types": types,
                "index": index,
                "has_product": has_product,
                "kept": not stub.notebook.DeletePage.called,
            }
        )

    product_types = list(fmt.EMPTY_COPY) + ["UNKNOWN"]
    formatting = {
        "full_names": fmt.PRODUCT_FULL_NAMES,
        "empty_copy": [
            {"product_type": t, "cwa": cwa, "text": fmt.EMPTY_COPY.get(t, f"{t} not currently available for {{cwa_office}}.").format(cwa_office=cwa)}
            for t in product_types
            for cwa in ("RAH", None)
        ],
        "intro": [
            {"product_type": t, "cwa": cwa, "text": fmt.regional_product_intro(t, cwa)}
            for t in ("SRF", "SURF_CONDITIONS", "AFD")
            for cwa in (" phi ", None, "")
        ],
        "no_cwa": fmt.NO_CWA_COPY,
    }
    return {
        "forecaster_tabs": [
            {
                "product_type": t.product_type,
                "label": t.label,
                "loader_kind": t.loader_kind,
                "requires_cwa": t.requires_cwa,
            }
            for t in fpd.ForecastProductsDialog._TABS
        ],
        "national_tabs": [[t.product_id, t.label] for t in NationalProductsDialog._TABS],
        "plans": plans,
        "loaders": loaders,
        "active": active,
        "availability": availability,
        "advanced_lookup_product": advanced_lookup_products(raleigh),
        "formatting": formatting,
    }


# ---------------------------------------------------------------------------
# Advanced lookup
# ---------------------------------------------------------------------------

ADV = AdvancedTextProductDialog
LookupStub = borrow(
    ADV,
    [
        "_lookup",
        "_selected_office",
        "_parse_limit",
        "_control_value",
        "_text_value",
        "_selected_order",
        "_selected_datetime",
        "_date_from_choice_parts",
        "_parse_optional_datetime",
        "_spc_outlook_day",
        "_wpc_outlook_day",
        "_iem_pil",
        "_validate_iem_afos_lookup",
        "_format_products",
        "_lookup_nws_history",
        "_lookup_spc_outlook",
        "_lookup_spc_mcd",
        "_lookup_spc_watches",
        "_lookup_wpc_outlook",
        "_lookup_wpc_mpd",
    ],
)


class Ctl:
    def __init__(self, value="", selection=""):
        self.value = value
        self.selection = selection

    def GetValue(self):
        return self.value

    def GetStringSelection(self):
        return self.selection


DEFAULT_FORM = {
    "product": "AFD",
    "office_choice": "Selected location office (RAH)",
    "custom_office": "RAH",
    "limit": "1",
    "source": "Prefer NWS when available",
    "order": "Newest first",
    "aviation_afd": False,
    "center": "",
    "wmo_id": "",
    "start_parts": ["", "", ""],
    "end_parts": ["", "", ""],
    "start_text": "",
    "end_text": "",
}


def lookup_case(name, location, responses, **form_overrides):
    form = {**DEFAULT_FORM, **form_overrides}
    stub = LookupStub()
    stub._location = location
    stub._service = ForecastProductService(Cache())
    stub.product_input = Ctl(form["product"])
    stub.office_choice = Ctl(selection=form["office_choice"])
    stub.location_input = Ctl(form["custom_office"])
    stub.limit_input = Ctl(form["limit"])
    stub.source_choice = Ctl(selection=form["source"])
    stub.order_choice = Ctl(selection=form["order"])
    stub.afd_aviation_only = Ctl(form["aviation_afd"])
    stub.center_input = Ctl(form["center"])
    stub.wmo_input = Ctl(form["wmo_id"])
    for prefix in ("start", "end"):
        for part, value in zip(("year", "month", "day"), form[f"{prefix}_parts"], strict=True):
            setattr(stub, f"{prefix}_{part}_choice", Ctl(selection=value))
    stub.start_input = Ctl(form["start_text"])
    stub.end_input = Ctl(form["end_text"])

    async def _run():
        try:
            return await stub._lookup()
        except AssertionError:
            raise
        except Exception as exc:  # noqa: BLE001 - mirrors _run_lookup
            return f"Lookup failed: {exc}"

    entry = case(
        name,
        {"fn": "lookup", "location": location_json(location), "form": form, "now": iso(NOW)},
        responses,
        _run,
        lambda text: text,
    )
    return entry


def advanced_cases() -> dict:
    raleigh = Location(
        name="Raleigh, NC", latitude=35.78, longitude=-78.64, country_code="US", cwa_office="RAH"
    )
    history = [
        {
            "url": f"{NWS}/products?",
            "json": {"@graph": [{"id": "afd-1", "issuanceTime": "2026-05-01T15:00:00+00:00"}]},
        },
        nws_product("afd-1", "official text", "2026-05-01T15:00:00+00:00", headline="Official product"),
    ]
    srf_history = [
        {"url": f"{NWS}/products?", "json": {"@graph": [{"id": "srf-1"}]}},
        nws_product("srf-1", "SURF ZONE FORECAST", None),
    ]
    empty_history = [{"url": f"{NWS}/products?", "json": {"@graph": []}}]
    afos = [{"url": AFOS, "text": "AFOS PRODUCT TEXT"}]

    lookups = [
        lookup_case(
            "afd_prefers_nws_history",
            raleigh,
            history,
            limit="5",
            start_text="2026-05-01",
            end_text="2026-05-02T12:00:00Z",
        ),
        lookup_case("srf_nws_regional_note", raleigh, srf_history, product="srf"),
        lookup_case(
            "national_pil_uses_iem",
            raleigh,
            afos,
            product="SWODY1",
            office_choice="No office or national product",
        ),
        lookup_case(
            "spc_outlook_current",
            raleigh,
            [{"url": f"{IEM}/json/spcoutlook.py", "json": {"outlook": {"threshold": "TSTM"}}}],
            product="SPC Day 1 Outlook",
        ),
        lookup_case(
            "spc_outlook_valid_time",
            raleigh,
            [{"url": f"{IEM}/json/spcoutlook.py", "json": {"outlooks": []}}],
            product="spc day 3 convective outlook",
            start_text="2026-03-06T20:00:00Z",
        ),
        lookup_case(
            "iem_only_with_filters",
            raleigh,
            afos,
            source="IEM AFOS only",
            order="Oldest first",
            aviation_afd=True,
            limit="5",
            center=" krah ",
            wmo_id="fxus62",
        ),
        lookup_case(
            "date_choices_beat_text_fields",
            raleigh,
            afos,
            product="SWODY1",
            office_choice="No office or national product",
            limit="3",
            source="IEM AFOS only",
            start_parts=["2024", "01 - January", "15"],
            end_parts=["2024", "01 - January", "16"],
            start_text="2020-01-01",
            end_text="2020-01-02",
        ),
        lookup_case(
            "incomplete_date_choice", raleigh, [], start_parts=["2024", "", "15"]
        ),
        lookup_case(
            "invalid_calendar_date", raleigh, [], end_parts=["2023", "02 - February", "29"]
        ),
        lookup_case("bad_date_text", raleigh, [], start_text="not a date"),
        lookup_case("bad_plain_date", raleigh, [], end_text="2026-02-30"),
        lookup_case(
            "invalid_custom_product",
            raleigh,
            [],
            product="TOO-LONG",
            office_choice="No office or national product",
            source="IEM AFOS only",
        ),
        lookup_case(
            "wpc_outlook_valid_time",
            raleigh,
            [{"url": f"{IEM}/json/wpcoutlook.py", "json": {"outlook": {"threshold": "SLGT"}}}],
            product="WPC Day 2 Excessive Rainfall Outlook",
            start_text="2026-05-01T12:00:00Z",
            limit="2",
        ),
        lookup_case(
            "wpc_mpd_archive",
            raleigh,
            [
                {
                    "url": f"{IEM}/json/wpcmpd.py",
                    "json": {
                        "mpds": [
                            {"product_num": 1, "utc_issue": "2026-04-30T12:00:00Z"},
                            {"product_num": 2, "utc_issue": "2026-04-30T13:00:00Z"},
                        ]
                    },
                }
            ],
            product="MPD",
            limit="1",
        ),
        lookup_case(
            "spc_mcd_archive",
            raleigh,
            [{"url": f"{IEM}/json/spcmcd.py", "json": {"mcds": [{"mdnum": 3}]}}],
            product="SPC Mesoscale Discussion",
            start_text="2026-04-01",
            end_text="2026-05-01",
        ),
        lookup_case(
            "spc_watches_valid_time",
            raleigh,
            [{"url": f"{IEM}/json/spcwatch.py", "json": {"features": []}}],
            product="SPC Watches",
            start_text="2026-03-16T15:00:00-04:00",
        ),
        lookup_case(
            "spc_watches_now",
            raleigh,
            [{"url": f"{IEM}/json/spcwatch.py", "json": {"features": []}}],
            product="watches",
        ),
        lookup_case(
            "nws_only_empty_history",
            raleigh,
            empty_history,
            product="LSR",
            source="NWS history only",
        ),
        lookup_case("prefer_nws_empty_falls_back_to_iem", raleigh, empty_history + afos, product="PNS"),
        lookup_case(
            "custom_office_invalid",
            raleigh,
            empty_history,
            office_choice="Custom office below",
            custom_office=" ra ",
        ),
        lookup_case(
            "custom_office_valid",
            raleigh,
            history,
            office_choice="Custom office below",
            custom_office=" mhx ",
            limit="abc",
        ),
        lookup_case(
            "history_http_error",
            raleigh,
            [{"url": f"{NWS}/products?", "status": 500, "json": {}}],
        ),
        lookup_case(
            "iem_error_text",
            raleigh,
            [{"url": AFOS, "text": "ERROR: No products found"}],
            source="IEM AFOS only",
            limit="99",
        ),
        lookup_case(
            "aviation_requires_afd",
            raleigh,
            [],
            product="HWO",
            source="IEM AFOS only",
            aviation_afd=True,
        ),
        lookup_case("center_invalid", raleigh, [], source="IEM AFOS only", center="KR"),
        lookup_case("wmo_invalid", raleigh, [], source="IEM AFOS only", wmo_id="FX1234"),
        lookup_case("empty_product", raleigh, [], product="   "),
        lookup_case(
            "unmatched_outlook_is_invalid_pil",
            raleigh,
            [],
            product="SPC DAY 9 OUTLOOK",
            source="IEM AFOS only",
        ),
        lookup_case("blank_source_and_office", raleigh, afos, source="", office_choice=""),
        lookup_case("blank_source_prefers_nws", raleigh, history, source=""),
    ]

    parse_inputs = [
        "",
        "  ",
        "2026-05-01",
        " 2026-05-01 ",
        "2026-02-30",
        "2026-05-01T12:00:00Z",
        "2026-05-01T12:00:00",
        "2026-05-01 08:00-04:00",
        "20260501",
        "20260501T1200Z",
        "2026-05-01T12:00:00.5Z",
        "yesterday",
        "2026-05-01Z",
    ]
    parsed = []
    for text in parse_inputs:
        try:
            value = ADV._parse_optional_datetime(text)
            parsed.append({"input": text, "ok": iso(value)})
        except ValueError as exc:
            parsed.append({"input": text, "error": str(exc)})

    parts_inputs = [
        ["", "", ""],
        ["2024", "", ""],
        ["2024", "02 - February", "29"],
        ["2023", "02 - February", "29"],
        ["1983", "12 - December", "31"],
    ]
    parts = []
    stub = LookupStub()
    for year, month, day in parts_inputs:
        stub.start_year_choice = Ctl(selection=year)
        stub.start_month_choice = Ctl(selection=month)
        stub.start_day_choice = Ctl(selection=day)
        try:
            parts.append({"input": [year, month, day], "ok": iso(stub._date_from_choice_parts("start"))})
        except ValueError as exc:
            parts.append({"input": [year, month, day], "error": str(exc)})

    outlook_inputs = [
        "SPC DAY 1 OUTLOOK",
        "SPC DAY 3 CONVECTIVE OUTLOOK",
        "SPCDAY8OUTLOOK",
        "DAY 2 OUTLOOK",
        "DAY 2 CONVECTIVEOUTLOOK",
        "SPC DAY 9 OUTLOOK",
        "SPC DAY 1 OUTLOOKS",
        "SPC  DAY\t4  OUTLOOK",
        "WPC DAY 1 EXCESSIVE RAINFALL OUTLOOK",
        "WPC DAY 2 OUTLOOK",
        "WPC DAY 3 EXCESSIVERAINFALLOUTLOOK",
        "WPC DAY 3 EXCESSIVE OUTLOOK",
        "DAY 1 EXCESSIVE RAINFALL OUTLOOK",
        "spc day 5 outlook",
        "SPC MCD",
    ]
    outlooks = [
        {"input": text, "spc": ADV._spc_outlook_day(text), "wpc": ADV._wpc_outlook_day(text)}
        for text in outlook_inputs
    ]

    limits = [
        {"input": v, "limit": ADV._parse_limit(v)}
        for v in ["1", "5", " 7 ", "25", "26", "999999999999999999999", "0", "-3", "abc", "", "+4", "3.5"]
    ]

    validations = [
        {
            "args": list(args),
            "message": ADV._validate_iem_afos_lookup(*args),
        }
        for args in [
            ("AFD", "AFDRAH", "RAH", False, "", ""),
            ("AFD", "AFDRA", "RA", False, "", ""),
            ("AFD", "AFDR1H", "R1H", False, "", ""),
            ("SWODY1", "SWODY1", "", False, "", ""),
            ("AB", "AB", "", False, "", ""),
            ("TOOLONG1", "TOOLONG1", "", False, "", ""),
            ("HWO", "HWORAH", "RAH", True, "", ""),
            ("AFD", "AFDRAH", "RAH", True, "KRAH", "FXUS62"),
            ("AFD", "AFDRAH", "RAH", False, "KRA", ""),
            ("AFD", "AFDRAH", "RAH", False, "", "FXUS6"),
            ("AFD", "AFDRAH", "RAH", False, "", "FX1234"),
            ("PMD SPD", "PMD SPD", "", False, "", ""),
        ]
    ]

    import accessiweather.ui.dialogs.advanced_text_product_dialog as adv_mod

    now = datetime(2026, 9, 25, 14, 30, 45, 123456, tzinfo=UTC)
    presets = []
    for preset in ["", *ADV_DATE_PRESETS(), "Bogus"]:
        with_now(now)
        start, end = ADV._date_range_for_preset(preset)
        presets.append({"preset": preset, "start": iso(start), "end": iso(end)})
    adv_mod.datetime = datetime

    preset_changes = []
    for label in [item.label for item in adv_mod._PRODUCT_PRESET_ITEMS] + [
        "SPC MCD (Mesoscale Discussions) near location",
        "CPC 6-10 and 8-14 Day Outlook (Climate Prediction Center)",
        "Unknown label",
    ]:
        change = {"label": label, "product": adv_mod._PRODUCT_PRESETS.get(label, "")}
        item = ADV._preset_by_label(label)
        change["source_index"] = None
        change["office_choice"] = None
        if change["product"]:
            if item and item.uses_local_office:
                change["source_index"] = 0
                change["office_choice"] = adv_mod._OFFICE_SELECTED
            if item and item.iem_only:
                change["source_index"] = 1
                change["office_choice"] = adv_mod._OFFICE_NONE
        preset_changes.append(change)

    formatted = ADV._format_products(
        "IEM",
        [
            TextProduct("SRF", "srf-1", "PHI", datetime(2026, 6, 7, 10, 0, 0, 500, tzinfo=UTC), "SURF", "Surf Zone Forecast"),
            TextProduct("AFDRAH", "AFDRAH", "IEM", None, "", ""),
        ],
    )

    return {
        "lookups": lookups,
        "parse_optional_datetime": parsed,
        "date_from_choice_parts": parts,
        "outlook_days": outlooks,
        "parse_limit": limits,
        "validate": validations,
        "date_presets": {"now": iso(now), "ranges": presets},
        "categories": list(adv_mod._PRODUCT_CATEGORIES),
        "labels_by_category": {c: ADV._preset_labels_for_category(c) for c in adv_mod._PRODUCT_CATEGORIES},
        "preset_changes": preset_changes,
        "format_products": formatted,
        "format_products_empty": ADV._format_products("NWS", []),
        "form_datetime": ADV._format_form_datetime(datetime(2026, 7, 4, 8, 0, 0, 5, tzinfo=timezone(timedelta(hours=-4)))),
    }


def ADV_DATE_PRESETS():
    import accessiweather.ui.dialogs.advanced_text_product_dialog as adv_mod

    return list(adv_mod._DATE_PRESETS)


def with_now(now: datetime) -> None:
    import accessiweather.ui.dialogs.advanced_text_product_dialog as adv_mod

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    adv_mod.datetime = Frozen


# ---------------------------------------------------------------------------
# Python helpers
# ---------------------------------------------------------------------------


def py_cases() -> dict:
    iso_inputs = [
        "2026-05-01",
        "20260501",
        "2026-05-01T12:00",
        "2026-05-01T12:00:00Z",
        "2026-05-01T12:00:00+00:00",
        "2026-05-01 12:00:00-05:00",
        "2026-05-01T12:00:00.123+05:30",
        "2026-05-01T12:00:00,5",
        "2026-05-01T1230",
        "2026-05-01T123045",
        "2026-05-01T12",
        "2026-05-01T12:00:00.1234567",
        "2026-05-01T12:00+0530",
        "2026-05-01T12:00+05",
        "2026-05-01T12:00:00+05:30:15",
        "2026-05-01X12:00",
        "2026-02-30",
        "2026-05-01T25:00",
        "2026-05-01T12:60",
        "not-a-time",
        "2026-05-01T",
        "2026-05-01T12:00:00Zjunk",
        "2026-05-01T12:3",
        "2026-5-1",
        "2026-05-01T12:00:00+24:00",
        "2026-05-01T12:00:00-00:00",
        "2026-06-07T12:00",
        "2026-05-01T12:00:00.",
        "2026-05-01T12:00:00x",
        "2026-05-01T12:00+053",
        "2026-05-01T12:00-05:99",
        "2026-05-01T1230451",
        "2026-05-01T12:30:45.12abc",
    ]
    fromiso = []
    for text in iso_inputs:
        try:
            fromiso.append({"input": text, "ok": iso(datetime.fromisoformat(text))})
        except ValueError:
            fromiso.append({"input": text, "ok": None})
    floats = [-77.0, 35.7796, 1e20, 1e16, 1234567890123456.0, 0.0001, 0.00001, 0.1 + 0.2, 2.5, -0.5, 100.0, 1e-7, 123456789.123]
    return {
        "fromisoformat": fromiso,
        "float_repr": [{"value": f, "repr": repr(f)} for f in floats],
    }


def main() -> None:
    write("iem", iem_cases())
    write("nws", nws_cases())
    write("surf", surf_cases())
    write("national", national_cases())
    write("tabs", tab_cases())
    write("advanced", advanced_cases())
    write("py", py_cases())
    print(f"wrote golden files to {OUT}")


if __name__ == "__main__":
    main()
