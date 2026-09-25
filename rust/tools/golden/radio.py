"""
Golden files for ``aw-radio`` (NOAA Weather Radio).

Run from the Python checkout:

    cd C:\\Users\\joshu\\accessiweather
    uv run python <worktree>\\rust\\tools\\golden\\radio.py

Drives the Python app's own ``noaa_radio`` package and the NOAA radio
dialog's station finder with fixed inputs (no network, no audio, frozen
clocks) and writes JSON to ``rust/testdata/golden/radio/``:

* ``stations.json``  bundled stations, stream URL table, state choices, labels
* ``search.json``    station search / nearest / state / call-sign lookups
* ``finder.json``    dialog finder modes -> results, labels, empty status
* ``files.json``     preferences and availability-cache file round trips
* ``clients.json``   WeatherIndex / wxradio.org parsing and URL merging
* ``same.json``      SAME filtering, alert states, station resolution
* ``auto_tune.json`` alert auto-tune decisions and status messages
* ``toggle.json``    hotkey toggle outcomes and notification texts
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import accessiweather.ui.dialogs.noaa_radio_dialog as dialog_module
from accessiweather.alert_notification_system import (
    _should_auto_tune_for_alert_notification,
)
from accessiweather.models import AppSettings, Location, WeatherAlert
from accessiweather.noaa_radio.alert_auto_tune import (
    AlertRadioAutoTuner,
    WeatherIndexAlertStationResolver,
    alert_same_codes,
    normalize_same_code,
    same_event_codes,
    would_wake_same_radio,
)
from accessiweather.noaa_radio.availability_cache import StationAvailabilityCache
from accessiweather.noaa_radio.preferences import RadioPreferences
from accessiweather.noaa_radio.station_availability import StationAvailabilityService
from accessiweather.noaa_radio.station_db import StationDatabase
from accessiweather.noaa_radio.stations import Station
from accessiweather.noaa_radio.stream_url import StreamURLProvider
from accessiweather.noaa_radio.toggle import RadioToggleController
from accessiweather.noaa_radio.weatherindex_client import WeatherIndexClient
from accessiweather.noaa_radio.wxradio_client import WxRadioClient, _extract_call_sign

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "radio"
Dialog = dialog_module.NOAARadioDialog
DB = StationDatabase()


def write(name: str, payload: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT / name}")


def call_signs(stations) -> list[str]:
    return [s.call_sign for s in stations]


# ---------------------------------------------------------------------------
# stations.json


def stations_golden() -> None:
    edge_stations = [
        Station("EDGE1", 162.4375, "Somewhere, TX", 30.0, -97.0, "TX"),
        Station("EDGE2", 162.5, "  Padded  ", 30.0, -97.0, " tx "),
        Station("EDGE3", 162.55, "No State", 30.0, -97.0, ""),
        Station("EDGE4", 162.025, "Lower, tx", 30.0, -97.0, "TX"),
        Station("EDGE5", 162.475, "Toronto, ON", 43.6, -79.3, "ON"),
    ]
    write(
        "stations.json",
        {
            "stations": [dataclasses.asdict(s) for s in DB.get_all_stations()],
            "stream_urls": StreamURLProvider._STREAM_URLS,
            "state_choices": list(Dialog._get_state_choices()),
            "base_labels": [
                {"station": dataclasses.asdict(s), "label": StationAvailabilityService._base_label(s)}
                for s in DB.get_all_stations() + edge_stations
            ],
            "state_choice_codes": {
                label: Dialog._state_choice_code(label)
                for label in [
                    "Texas (TX)",
                    "NY",
                    "U.S. Virgin Islands (VI)",
                    "Weird (Name) (XX)",
                    "Open (",
                    "AB",
                ]
            },
            "station_limit_indexes": [
                [limit, Dialog._get_station_limit_choice_index(object(), limit)]
                for limit in [10, 25, 50, 100, None, 7, 0]
            ],
        },
    )


# ---------------------------------------------------------------------------
# search.json


def search_golden() -> None:
    queries = [
        "",
        "kec",
        "KEC49",
        "tx",
        "TX",
        "austin",
        "New York",
        "30.2672, -97.7431",
        " 40.7 , -74 ",
        "91, 0",
        "+30.5,-97",
        "30,-97.5",
        "1e3, 5",
        "30.5, -97.",
        "ny",
        "a",
        "Bay",
        "  ",
        "Spanish",
    ]
    search = [
        {"query": q, "limit": limit, "result": call_signs(DB.search(q, limit=limit))}
        for q in queries
        for limit in (None, 3, 0)
    ]
    points = [
        (40.7128, -74.0060),
        (30.2672, -97.7431),
        (61.2, -149.9),
        (0.0, 0.0),
        (47.6062, -122.3321),
        (-33.9, 151.2),
    ]
    nearest = [
        {
            "lat": lat,
            "lon": lon,
            "limit": limit,
            "result": [[r.station.call_sign, r.distance_km] for r in DB.find_nearest(lat, lon, limit)],
        }
        for lat, lon in points
        for limit in (None, 5)
    ]
    write(
        "search.json",
        {
            "search": search,
            "nearest": nearest,
            "by_state": {s: call_signs(DB.get_stations_by_state(s)) for s in ["ny", "TX", "zz", "ab", ""]},
            "by_call_signs": [
                {"input": inp, "result": call_signs(DB.get_stations_by_call_signs(inp))}
                for inp in [["wxk27", " ", "KEC49", "WXK27", "NOPE"], [], ["khb60", "WWG24"]]
            ],
        },
    )


# ---------------------------------------------------------------------------
# finder.json


class _Feeds:
    """WeatherIndex stand-in: stations in ``have`` have one feed."""

    def __init__(self, have: set[str]) -> None:
        self.have = have

    def get_stream_urls(self, call_sign: str) -> list[str]:
        return ["https://feed/" + call_sign] if call_sign.upper() in self.have else []


NOW = 1_750_000_000.0
ALL = call_signs(DB.get_all_stations())
# Deterministic subset with feeds: every station except each third one.
FEEDS = sorted(cs for i, cs in enumerate(ALL) if i % 3 != 0)
SUPPRESSED = sorted(FEEDS[::5])


def run_finder(case: dict, tmp: Path) -> dict:
    cache_path = tmp / f"avail-{case['name']}.json"
    cache = StationAvailabilityCache(path=cache_path, time_fn=lambda: NOW)
    for cs in case["suppressed"]:
        cache.suppress(cs, 600, "all_streams_failed")
    prefs = RadioPreferences()
    prefs._favorite_stations = list(case["favorites"])
    saved = [Location(name=n, latitude=lat, longitude=lon) for n, lat, lon in case["saved_locations"]]
    stub = MagicMock()
    stub._prefs = prefs
    stub._lat, stub._lon = case["origin"] if case["origin"] else (None, None)
    stub._saved_locations = saved
    stub._parse_coordinate_query = Dialog._parse_coordinate_query
    stub._station_availability = StationAvailabilityService(
        weatherindex_client=_Feeds(set(case["feeds"])), availability_cache=cache
    )
    mode = dialog_module.FINDER_MODE_LABELS[case["mode"]]
    saved_location = saved[case["saved_index"]] if case["saved_index"] is not None else None
    with patch.object(dialog_module.wx, "CallAfter") as call_after:
        Dialog._load_stations_worker(
            stub,
            show_unavailable=case["show_unavailable"],
            station_limit=case["limit"],
            search_query=case["query"],
            finder_mode=mode,
            state_code=case["state_code"],
            saved_location=saved_location,
            empty_status=None,
            load_generation=1,
        )
    loaded = call_after.call_args_list[0].args
    stations, choices = loaded[1], loaded[2]
    return {
        **case,
        "stations": call_signs(stations),
        "choices": choices,
        "display": [Dialog._format_station_choice_label(stub, s, c) for s, c in zip(stations, choices, strict=True)],
        "empty_status": Dialog._get_empty_station_status(stub, mode),
    }


def finder_golden() -> None:
    base = {
        "query": "",
        "limit": 10,
        "state_code": "",
        "saved_locations": [],
        "saved_index": None,
        "favorites": [],
        "origin": None,
        "show_unavailable": False,
        "feeds": FEEDS,
        "suppressed": SUPPRESSED,
    }
    austin = ["Austin", 30.2672, -97.7431]
    cases = [
        {"name": "search_default", "mode": 0},
        {"name": "search_all_unbounded", "mode": 0, "limit": None},
        {"name": "search_tx_show_unavailable", "mode": 0, "query": "tx", "limit": None, "show_unavailable": True},
        {"name": "search_coordinates", "mode": 0, "query": "30.2672, -97.7431", "limit": 5},
        {"name": "favorites", "mode": 1, "favorites": ["WXK27", "KEC49", "NOPE", "KEC61"], "limit": 1},
        {"name": "favorites_empty", "mode": 1},
        {"name": "favorites_without_streams", "mode": 1, "favorites": ["NOPE"]},
        {"name": "state_tx", "mode": 2, "state_code": "TX", "limit": 3},
        {"name": "state_all", "mode": 2, "limit": 25, "show_unavailable": True},
        {"name": "nearest_query", "mode": 3, "query": "40.7128, -74.0060"},
        {"name": "nearest_origin_fallback", "mode": 3, "query": "Austin", "origin": [30.27, -97.74], "limit": 4},
        {"name": "nearest_no_coordinates", "mode": 3, "query": "Austin"},
        {"name": "nearest_out_of_range", "mode": 3, "query": "95, 10", "origin": [47.6, -122.3]},
        {"name": "saved_location", "mode": 4, "saved_locations": [austin], "saved_index": 0, "limit": 5},
        {"name": "saved_location_none", "mode": 4},
        {
            "name": "saved_location_without_streams",
            "mode": 4,
            "saved_locations": [austin],
            "saved_index": 0,
            "feeds": [],
        },
        {
            "name": "favorite_labels",
            "mode": 0,
            "query": "FL",
            "limit": None,
            "favorites": ["KIH24", "KHB32", "WZ2531"],
            "show_unavailable": True,
        },
    ]
    with tempfile.TemporaryDirectory() as tmp:
        results = [run_finder({**base, **case}, Path(tmp)) for case in cases]
    coordinate_queries = [
        "30.2672, -97.7431",
        "Austin",
        "91, 0",
        "0, 181",
        " 45 ,  -90 ",
        "1e1, 2",
        "nan, 5",
        "inf, 5",
        "1,2,3",
        ".5, 5.",
        "-90, 180",
    ]
    write(
        "finder.json",
        {
            "cases": results,
            "coordinate_queries": {q: Dialog._parse_coordinate_query(q) for q in coordinate_queries},
            "initial_search_text": [
                [lat, lon, f"{lat:.4f}, {lon:.4f}"]
                for lat, lon in [(30.2672, -97.7431), (0.03125, -0.00005), (40.7, -74.0), (1.23456789, 2.5)]
            ],
        },
    )


# ---------------------------------------------------------------------------
# files.json


def prefs_state(prefs: RadioPreferences) -> dict:
    return {
        "preferred": [[k, v] for k, v in prefs._prefs.items()],
        "favorites": prefs.get_favorite_stations(),
        "last_station": prefs.get_last_station(),
        "station_limit": prefs.get_station_limit(),
    }


def run_prefs(case: dict, tmp: Path) -> dict:
    path = tmp / f"{case['name']}.json"
    if case["file"] is not None:
        path.write_text(case["file"], encoding="utf-8")
    prefs = RadioPreferences(path=path)
    loaded = prefs_state(prefs)
    for op, *args in case["ops"]:
        getattr(prefs, op)(*args)
    return {
        **case,
        "loaded": loaded,
        "after": prefs_state(prefs),
        "saved_text": path.read_text(encoding="utf-8") if path.exists() else None,
    }


def run_cache(case: dict, tmp: Path) -> dict:
    path = tmp / f"{case['name']}.json"
    if case["file"] is not None:
        path.write_text(case["file"], encoding="utf-8")
    now = [case["now"]]
    cache = StationAvailabilityCache(path=path, time_fn=lambda: now[0])
    loaded = {cs: cache.get_record(cs) for cs in sorted(cache._records)}
    for op, *args in case["ops"]:
        if op == "advance":
            now[0] += args[0]
        elif op == "suppress":
            cache.suppress(args[0], ttl_seconds=args[1], reason=args[2])
        else:
            getattr(cache, op)(*args)
    return {
        **case,
        "loaded": loaded,
        "suppressed": cache.get_suppressed_call_signs(),
        "saved_text": path.read_text(encoding="utf-8") if path.exists() else None,
    }


def files_golden() -> None:
    new_format = json.dumps(
        {
            "preferred_streams": {"kec49": "https://b", "WXK27": "https://z", "bad": 5},
            "station_limit": 25,
            "favorite_stations": ["wxk27", " KEC49 ", "WXK27", None, 7, True, ""],
            "last_station": "  kec49 ",
        }
    )
    prefs_cases = [
        {"name": "missing_file", "file": None, "ops": []},
        {"name": "new_format", "file": new_format, "ops": []},
        {
            "name": "mutations",
            "file": new_format,
            "ops": [
                ["set_preferred_url", "kih24", "https://k"],
                ["set_preferred_url", "KEC49", "https://c"],
                ["clear_preferred_url", "wxk27"],
                ["clear_preferred_url", "none"],
                ["add_favorite_station", " kih24 "],
                ["add_favorite_station", "KIH24"],
                ["remove_favorite_station", "wxk27"],
                ["set_last_station", "wxl58"],
                ["set_station_limit", None],
            ],
        },
        {"name": "legacy", "file": json.dumps({"kec49": "https://legacy", "bad": 5}), "ops": []},
        {
            "name": "legacy_then_save",
            "file": json.dumps({"kec49": "https://legacy"}),
            "ops": [["set_last_station", "KEC49"]],
        },
        {"name": "invalid_json", "file": "{not json", "ops": [["set_station_limit", 50]]},
        {"name": "not_an_object", "file": "[1, 2]", "ops": []},
        {"name": "limit_all_string", "file": '{"station_limit": "All"}', "ops": []},
        {"name": "limit_zero", "file": '{"station_limit": 0}', "ops": []},
        {"name": "limit_negative", "file": '{"station_limit": -5}', "ops": []},
        {"name": "limit_float", "file": '{"station_limit": 2.5}', "ops": []},
        {"name": "limit_numeric_string", "file": '{"station_limit": "10"}', "ops": []},
        {"name": "limit_null", "file": '{"station_limit": null}', "ops": []},
        {"name": "streams_not_object", "file": '{"preferred_streams": [1], "last_station": 42}', "ops": []},
        {"name": "favorites_not_list", "file": '{"preferred_streams": {}, "favorite_stations": "KEC49"}', "ops": []},
        {"name": "set_favorites", "file": None, "ops": [["set_favorite_stations", ["b", "A", " b ", ""]]]},
        {"name": "blank_last_station", "file": None, "ops": [["set_last_station", "x"], ["set_last_station", "  "]]},
        {"name": "same_last_station_no_write", "file": None, "ops": [["set_last_station", None]]},
        {"name": "non_ascii_url", "file": None, "ops": [["set_preferred_url", "kec49", "https://é/😀"]]},
    ]
    cache_cases = [
        {"name": "missing", "file": None, "now": NOW, "ops": []},
        {
            "name": "load_and_prune",
            "file": json.dumps(
                {
                    "kec49": {"reason": "all_streams_failed", "expires_at": NOW + 60},
                    "WXK27": {"reason": "old", "expires_at": NOW - 1},
                    "KIH24": {"reason": "int", "expires_at": int(NOW) + 5},
                    "BAD1": {"reason": 5, "expires_at": NOW + 60},
                    "BAD2": "nope",
                    "BAD3": {"reason": "x"},
                    "BOOL": {"reason": "b", "expires_at": True},
                    "  ": {"reason": "blank", "expires_at": NOW + 60},
                }
            ),
            "now": NOW,
            "ops": [],
        },
        {
            "name": "suppress_advance_clear",
            "file": None,
            "now": NOW,
            "ops": [
                ["suppress", "kec49", 1800, "all_streams_failed"],
                ["suppress", "WXK27", 60, "x"],
                ["suppress", " ", 60, "blank"],
                ["advance", 60],
                ["clear", "kih24"],
            ],
        },
        {
            "name": "clear_rewrites",
            "file": None,
            "now": NOW + 0.25,
            "ops": [["suppress", "B", 1800, "b"], ["suppress", "A", 30, "a"], ["clear", "b"]],
        },
        {"name": "corrupt", "file": "{nope", "now": NOW, "ops": []},
        {"name": "not_object", "file": "[]", "now": NOW, "ops": [["suppress", "A", 10, "a"]]},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        write(
            "files.json",
            {
                "preferences": [run_prefs(c, Path(tmp)) for c in prefs_cases],
                "availability": [run_cache(c, Path(tmp)) for c in cache_cases],
            },
        )


# ---------------------------------------------------------------------------
# clients.json


def clients_golden() -> None:
    weatherindex_payloads = [
        {"feeds": [{"stream_url": "https://a"}, {"stream_url": " https://b "}, {"stream_url": "https://a"}]},
        {"station": {"callsign": "wxk27", "feeds": [{"stream_url": 5}, "junk", {"stream_url": ""}]}},
        {"station": {}, "feeds": [{"stream_url": "https://outer"}]},
        {"call_sign": "WXK27"},
        {},
        [],
        "text",
        {"feeds": "nope"},
        {
            "callsign": "",
            "call_sign": "kec49",
            "wfo": "  ",
            "latitude": "30.5",
            "longitude": True,
            "served_counties": [
                {"county": " Travis ", "same_code": "048453", "state": " tx ", "area": "All"},
                {"county": "Int", "same_code": 48209, "state": "TX", "area": " "},
                {"county": "Neg", "same_code": -5, "state": "TX"},
                {"county": "Float", "same_code": 48.0, "state": "TX"},
                {"county": "Bool", "same_code": True, "state": "TX"},
                {"county": "Dashes", "same_code": "48-453", "state": "TX", "area": 5},
                {"county": "NoDigits", "same_code": "abc", "state": "TX"},
                {"county": 5, "same_code": "1", "state": "TX"},
                {"county": "NoState", "same_code": "1"},
                "junk",
            ],
        },
        {"callsign": 12345, "latitude": None, "longitude": "x", "served_counties": {"a": 1}},
    ]
    client = WeatherIndexClient(session=MagicMock())
    weatherindex = [
        {
            "payload": p,
            "urls": client._parse(p),
            "metadata": dataclasses.asdict(m) if (m := client._parse_metadata(p, "REQ1")) else None,
        }
        for p in weatherindex_payloads
    ]
    wx = WxRadioClient(session=MagicMock())
    wxradio_payloads = [
        {
            "icestats": {
                "source": [
                    {"listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24"},
                    {"listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24"},
                    {"listenurl": "http://wxradio.org:8000/FL-Tallahassee-KIH24-alt1"},
                    {"server_name": "GA-Atlanta-KEC80"},
                    {"listenurl": "", "server_name": "OK-Tulsa-KIH27"},
                    {"listenurl": "noslash", "server_name": "TX-Austin-WXK27"},
                    {"listenurl": "http://x/", "server_name": "TX-Austin-WXK27"},
                    {"listenurl": 5, "server_name": 7},
                    {"listenurl": "http://x/NE-Omaha-KIH61-A"},
                    {"listenurl": "http://x/MA-Bourne/Hyannis-KEC73"},
                    "junk",
                ]
            }
        },
        {"icestats": {"source": {"listenurl": "http://x/OK-Tulsa-KIH27"}}},
        {"icestats": {}},
        {"icestats": []},
        {"icestats": {"source": "x"}},
        {},
        [],
    ]
    wxradio = [{"payload": p, "streams": wx._parse(p)} for p in wxradio_payloads]
    mounts = [
        "/FL-Tallahassee-KIH24",
        "/NY-New-York-City-KWO35",
        "/MI-MountPleasant-KZZ33-alt2",
        "/NE-Omaha-KIH61-A",
        "/AB-Calgary-XLF339",
        "/IL-Marion-WXM49-ALT1",
        "FL-Tallahassee-KIH24",
        "/FL-Tallahassee",
        "",
        "/",
        "/FL-Tallahassee-nothing",
        "/fl-tallahassee-kih24",
        "/XX-City-ABCDE12",
        "/XX-City-A12",
        "/XX-City-ABCD1234",
        "/XX-City-ABC12345",
        "/XX-KIH24-City",
    ]
    merge_cases = [
        {"call_sign": "KIH24", "weatherindex": ["https://wi/1", "https://wxradio.org/FL-Tallahassee-KIH24"],
         "wxradio": {"KIH24": ["https://wxradio.org/FL-Tallahassee-KIH24-alt"]}, "use_fallback": True},
        {"call_sign": " kih24 ", "weatherindex": [], "wxradio": {}, "use_fallback": False},
        {"call_sign": "ZZZ99", "weatherindex": [], "wxradio": {}, "use_fallback": True},
        {"call_sign": "ZZZ99", "weatherindex": [], "wxradio": {}, "use_fallback": False},
        {"call_sign": "ZZZ99", "weatherindex": ["https://only"], "wxradio": {"ZZZ99": ["https://only", "https://w"]},
         "use_fallback": True},
        {"call_sign": "", "weatherindex": ["https://x"], "wxradio": {}, "use_fallback": True},
    ]
    merged = []
    for case in merge_cases:
        wi = MagicMock()
        wi.get_stream_urls.return_value = case["weatherindex"]
        wxr = MagicMock()
        wxr.get_streams.return_value = case["wxradio"]
        provider = StreamURLProvider(use_fallback=case["use_fallback"], wxradio_client=wxr, weatherindex_client=wi)
        merged.append({**case, "urls": provider.get_stream_urls(case["call_sign"])})
    write(
        "clients.json",
        {
            "weatherindex": weatherindex,
            "wxradio": wxradio,
            "mounts": {m: _extract_call_sign(m) for m in mounts},
            "merge": merged,
        },
    )


# ---------------------------------------------------------------------------
# same.json


def make_alert(spec: dict) -> WeatherAlert:
    return WeatherAlert(
        title=spec.get("title", "Alert"),
        description="body",
        event=spec.get("event"),
        message_type=spec.get("message_type"),
        affected_zones=spec.get("affected_zones", []),
        same_codes=spec.get("same_codes", []),
        same_event_codes=spec.get("same_event_codes", []),
    )


ALERTS = [
    {"name": "tornado", "event": "Tornado Warning", "affected_zones": ["TXC453"], "same_codes": ["048453"],
     "same_event_codes": ["TOR"]},
    {"name": "air_quality", "same_codes": ["048453"], "same_event_codes": ["NWS"]},
    {"name": "no_county_codes", "affected_zones": ["TXC453"], "same_event_codes": ["TOR"]},
    {"name": "forecast_zone", "affected_zones": ["TXZ192"], "same_event_codes": ["TOR"]},
    {"name": "lowercase_smw", "same_codes": ["48453"], "same_event_codes": [" smw ", "nws", ""]},
    {"name": "flood_nj", "affected_zones": [
        "https://api.weather.gov/zones/county/NJC005",
        "https://api.weather.gov/zones/county/NJC007",
    ], "same_codes": ["034005", "034007", "034015"], "same_event_codes": ["FLS"]},
    {"name": "malformed", "affected_zones": ["XXC001", "txc453", "TXC45", " https://x/zones/county/okc001 "],
     "same_codes": ["abc", "", "1234567", "99001", "072001"], "same_event_codes": ["TOR"]},
    {"name": "marine", "affected_zones": ["GMZ250"], "same_codes": ["077250"], "same_event_codes": ["SMW"]},
]


class _Metadata:
    def __init__(self, coverage: dict[str, list[str]]) -> None:
        self.coverage = coverage
        self.calls: list[str] = []

    def get_station_metadata(self, call_sign: str):
        from accessiweather.noaa_radio.weatherindex_client import (
            WeatherIndexServedCounty,
            WeatherIndexStationMetadata,
        )

        self.calls.append(call_sign.upper())
        codes = self.coverage.get(call_sign.upper())
        if codes is None:
            return None
        return WeatherIndexStationMetadata(
            call_sign=call_sign,
            wfo=None,
            latitude=None,
            longitude=None,
            served_counties=tuple(WeatherIndexServedCounty(county="C", same_code=c, state="TX") for c in codes),
        )


def same_golden() -> None:
    by_name = {a["name"]: a for a in ALERTS}
    resolver_cases = [
        {"name": "austin_nearest", "alerts": ["tornado"], "location": [30.2672, -97.7431],
         "coverage": {"WXK27": ["048453"], "KEC56": ["048453"]}},
        {"name": "no_location_state_first", "alerts": ["tornado"], "location": None,
         "coverage": {"KEC56": ["048453"], "WXK38": ["048453"]}},
        {"name": "no_location_same_state", "alerts": ["lowercase_smw"], "location": None,
         "coverage": {"WXK35": ["048453"]}},
        {"name": "nj_flood", "alerts": ["flood_nj"], "location": None, "coverage": {"KIH28": ["034007"]}},
        {"name": "empty_coverage_skipped", "alerts": ["tornado"], "location": [30.2672, -97.7431],
         "coverage": {"WXK27": [], "WXK30": ["048453"]}},
        {"name": "no_same_codes", "alerts": ["no_county_codes"], "location": None, "coverage": {"WXK27": ["048453"]}},
        {"name": "no_match", "alerts": ["marine"], "location": [29.3, -94.8], "coverage": {}},
        {"name": "batch", "alerts": ["malformed", "flood_nj"], "location": None, "coverage": {"KHB36": ["001001"]}},
    ]
    resolved = []
    for case in resolver_cases:
        fake = _Metadata(case["coverage"])
        resolver = WeatherIndexAlertStationResolver(station_database=DB, weatherindex_client=fake)
        alerts = [make_alert(by_name[n]) for n in case["alerts"]]
        location = Location(name="Here", latitude=case["location"][0], longitude=case["location"][1]) \
            if case["location"] else None
        station = resolver.resolve_station(alerts, location)
        resolved.append({**case, "station": station.call_sign if station else None, "calls": fake.calls})
    resolver = WeatherIndexAlertStationResolver(station_database=DB, weatherindex_client=_Metadata({}))
    write(
        "same.json",
        {
            "normalize": {v: normalize_same_code(v) for v in ["048453", " 48453 ", "abc", "12-345", "1234567", "", "0"]},
            "alerts": [
                {
                    **a,
                    "same_codes_normalized": sorted(alert_same_codes(make_alert(a))),
                    "event_codes": sorted(same_event_codes(make_alert(a))),
                    "would_wake": would_wake_same_radio(make_alert(a)),
                    "states": sorted(resolver._alert_states([make_alert(a)])),
                }
                for a in ALERTS
            ],
            "notification_reasons": [
                [mt, reason, _should_auto_tune_for_alert_notification(make_alert({"message_type": mt}), reason)]
                for mt in [None, "Alert", " alert ", "", "Update", "Cancel"]
                for reason in ["new_alert", "severity_escalated", "updated", "reminder"]
            ],
            "resolver": resolved,
        },
    )


# ---------------------------------------------------------------------------
# auto_tune.json


class _Thread:
    def __init__(self, target, started):
        self.target, self.started = target, started

    def start(self):
        self.started.append(self.target)


class _Wake:
    def __init__(self):
        self.waits = []
        self.sets = 0

    def wait(self, timeout=None):
        self.waits.append(timeout)
        return False

    def set(self):
        self.sets += 1

    def clear(self):
        pass


class _URLStream:
    """``sound_lib.stream.URLStream`` stand-in; opens succeed unless queued."""

    results: list[bool] = []
    opened: list[str] = []

    def __init__(self, url: str) -> None:
        _URLStream.opened.append(url)
        if _URLStream.results and not _URLStream.results.pop(0):
            raise RuntimeError("refused")
        self.volume = 1.0
        self.is_playing = False
        self.is_stalled = False
        self.stopped = False

    def play(self) -> None:
        self.is_playing = True

    def stop(self) -> None:
        self.is_playing = False
        self.stopped = True

    def free(self) -> None:
        pass

    def get_level(self) -> int:
        return 100


def real_session(results: list[bool], prefs: RadioPreferences):
    """The app's own RadioSession/RadioPlayer over a fake URLStream."""
    from accessiweather.noaa_radio.session import RadioSession

    _URLStream.results = list(results)
    _URLStream.opened = []
    session = RadioSession(preferences=prefs)
    stops = [0]
    real_stop = session.stop

    def counting_stop(*args, **kwargs):
        stops[0] += 1
        return real_stop(*args, **kwargs)

    session.stop = counting_stop
    return session, stops


def audio_patches():
    import accessiweather.noaa_radio.player as player_module

    return (
        patch.object(player_module, "_ensure_sound_lib", return_value=True),
        patch("sound_lib.stream.URLStream", _URLStream),
    )


class _Resolver:
    def __init__(self, station):
        self.station = station

    def resolve_station(self, alerts, location):
        return self.station


def station_by(call_sign: str | None) -> Station | None:
    if call_sign is None:
        return None
    found = DB.get_stations_by_call_signs([call_sign])
    return found[0] if found else Station(call_sign, 162.4, f"{call_sign} City, TX", 30.0, -97.0, "TX")


def run_auto_tune(case: dict) -> dict:
    statuses: list[str] = []
    started: list = []
    prefs = RadioPreferences()
    for cs, url in case["preferred"].items():
        prefs.set_preferred_url(cs, url)
    manual_first = case["playing_before"] or case["playing_unknown"] or case["manual_during_resolution"]
    ensure, url_stream = audio_patches()
    with ensure, url_stream, patch(
        "accessiweather.noaa_radio.alert_auto_tune.wx.CallAfter", side_effect=lambda f, *a: f(*a)
    ):
        session, stops = real_session(([True] if manual_first else []) + case["play_results"], prefs)
        if case["playing_before"] or case["playing_unknown"]:
            session.playing_station = station_by(case["playing_before"])
            session.player.play("manual")
        urls = MagicMock()
        urls.get_stream_urls.return_value = case["urls"]
        clock = iter(case["clock"])
        tuner = AlertRadioAutoTuner(
            settings_provider=lambda: AppSettings(
                auto_tune_weather_radio_alerts=case["enabled"],
                auto_tune_weather_radio_duration_minutes=case["duration"],
            ),
            location_provider=lambda: None,
            status_callback=statuses.append,
            session=session,
            preferences=prefs,
            station_resolver=_Resolver(station_by(case["resolved"])),
            url_provider=urls,
            thread_factory=lambda target: _Thread(target, started),
            monotonic=lambda: next(clock),
        )
        wake = _Wake()
        tuner._wake_event = wake
        for batch in case["batches"]:
            tuner.tune_for_alerts([make_alert({**by_name(n)}) for n in batch])
        if case["manual_during_resolution"]:
            session.playing_station = station_by(case["manual_during_resolution"])
            session.player.play("manual")
        if case["cancel_before_run"]:
            tuner.stop()
        worker_count = len(started)
        for target in started:
            target()
    return {
        **case,
        "workers": worker_count,
        "statuses": statuses,
        "played": [u for u in _URLStream.opened if u != "manual"],
        "waits": wake.waits,
        "wake_sets": wake.sets,
        "stops": stops[0],
        "url_lookups": urls.get_stream_urls.call_count,
        "final_station": session.playing_station.call_sign if session.playing_station else None,
        "last_station": prefs.get_last_station(),
    }


def by_name(name: str) -> dict:
    return next(a for a in ALERTS if a["name"] == name)


def auto_tune_golden() -> None:
    base = {
        "enabled": True,
        "duration": 5,
        "batches": [["tornado"]],
        "resolved": "WXK27",
        "urls": ["https://u1", "https://u2"],
        "preferred": {},
        "play_results": [True],
        "clock": [100.0, 401.0],
        "playing_before": None,
        "playing_unknown": False,
        "manual_during_resolution": None,
        "cancel_before_run": False,
    }
    cases = [
        {"name": "plays_then_stops"},
        {"name": "disabled", "enabled": False},
        {"name": "non_radio_batch", "batches": [["air_quality", "no_county_codes", "forecast_zone"]]},
        {"name": "empty_batch", "batches": [[]]},
        {"name": "no_station_match", "resolved": None, "clock": [100.0]},
        {"name": "no_streams", "urls": [], "clock": [100.0]},
        {"name": "all_streams_fail", "play_results": [False, False], "clock": [100.0]},
        {"name": "fallback_stream", "play_results": [False, True]},
        {"name": "preferred_first", "preferred": {"WXK27": "https://u2"}},
        {"name": "already_playing", "playing_before": "KHB40", "clock": [100.0]},
        {"name": "already_playing_unknown", "playing_unknown": True, "clock": [100.0]},
        {"name": "manual_during_resolution", "manual_during_resolution": "KHB40", "clock": [100.0]},
        {"name": "cancelled", "cancel_before_run": True, "clock": [100.0]},
        {"name": "duration_8", "duration": 8, "clock": [100.0, 579.0, 580.0]},
        {"name": "invalid_duration", "duration": 0},
        {"name": "duration_61", "duration": 61, "clock": [100.0, 401.0]},
        {"name": "duration_60", "duration": 60, "clock": [100.0, 3700.0]},
        {"name": "duplicate_extends", "batches": [["tornado"], ["tornado"]], "clock": [100.0, 150.0, 399.0, 450.0]},
        {"name": "same_less_does_not_extend", "batches": [["tornado"], ["no_county_codes"]]},
    ]
    write("auto_tune.json", [run_auto_tune({**base, **c}) for c in cases])


# ---------------------------------------------------------------------------
# toggle.json


def run_toggle(case: dict) -> dict:
    notes: list[str] = []
    prefs = RadioPreferences()
    if case["last_station"] is not None:
        prefs.set_last_station(case["last_station"])
    prefs.set_favorite_stations(case["favorites"])
    for cs, url in case["preferred"].items():
        prefs.set_preferred_url(cs, url)
    ensure, url_stream = audio_patches()
    with ensure, url_stream:
        session, stops = real_session(([True] if case["playing"] else []) + case["play_results"], prefs)
        if case["playing"]:
            session.player.play("manual")
        urls = MagicMock()
        urls.get_stream_urls.return_value = case["urls"]
        controller = RadioToggleController(
            session=session,
            preferences=prefs,
            station_database=DB,
            url_provider=urls,
            notify=notes.append,
            thread_factory=lambda target: type("T", (), {"start": staticmethod(target)})(),
        )
        controller.toggle()
    return {
        **case,
        "notifications": notes,
        "played": [u for u in _URLStream.opened if u != "manual"],
        "stops": stops[0],
        "lookups": [c.args[0] for c in urls.get_stream_urls.call_args_list],
        "final_station": session.playing_station.call_sign if session.playing_station else None,
        "current_url_index": session.current_url_index,
        "last_station": prefs.get_last_station(),
    }


def toggle_golden() -> None:
    base = {
        "playing": False,
        "last_station": "wxk27",
        "favorites": [],
        "urls": ["http://a", "http://b"],
        "preferred": {},
        "play_results": [True],
    }
    cases = [
        {"name": "stops_when_playing", "playing": True},
        {"name": "plays_last_station"},
        {"name": "first_favorite", "last_station": None, "favorites": ["kec61", "WXK27"]},
        {"name": "nothing_known", "last_station": None},
        {"name": "unknown_station", "last_station": "NOPE1"},
        {"name": "no_streams", "urls": []},
        {"name": "second_stream", "play_results": [False, True]},
        {"name": "all_fail", "play_results": [False, False]},
        {"name": "preferred", "preferred": {"WXK27": "http://b"}},
        {"name": "state_in_name", "last_station": "KEC61"},
    ]
    write("toggle.json", [run_toggle({**base, **c}) for c in cases])


if __name__ == "__main__":
    stations_golden()
    search_golden()
    finder_golden()
    files_golden()
    clients_golden()
    same_golden()
    auto_tune_golden()
    toggle_golden()
