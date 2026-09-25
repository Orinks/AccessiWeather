r"""
Golden files for the Rust data path: the live source adapters
(``crates/aw-providers/src/client/live.rs``), the orchestrator and
``aw_core::display::WeatherPresenter``, end to end.

Run from the Python checkout on a machine set to US Eastern time:

    cd C:\\Users\\joshu\\accessiweather
    uv run python <worktree>\\rust\\tools\\golden\\datapath.py

Each case runs the real Python ``WeatherClient.get_weather_data`` (no
offline cache, no environmental client) against recorded cassette bodies
served by URL prefix -- the longest registered prefix of the full URL wins,
anything else is a 404, exactly how ``FixtureClient`` answers -- with a
frozen clock, then ``WeatherPresenter.present`` and the main window's panel
texts (``_on_weather_data_received``). The file records the routes, the
settings overrides, the location, the URLs Python requested, the
presentation and the panel texts.

Every route also carries ``recorded_at``: the instant its body belongs to,
which the app's ``--offline`` fixtures use to move the bodies to today.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
import time
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import httpx
import yaml

import accessiweather
from accessiweather.display import WeatherPresenter
from accessiweather.models import AppSettings, Location
from accessiweather.utils import retry, retry_utils
from accessiweather.weather_client import WeatherClient

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "testdata" / "golden" / "datapath"
CASSETTES = Path.cwd() / "tests" / "integration" / "cassettes"
LOCAL_TZ = "America/New_York"

if time.tzname != ("Eastern Standard Time", "Eastern Daylight Time"):
    sys.exit("Generate these on a machine set to US Eastern time (the files record it).")

# ---------------------------------------------------------------------------
# Frozen clock: every accessiweather module's `datetime` reads a fixed now.
# ---------------------------------------------------------------------------

_REAL_DATETIME = datetime
_FROZEN = [datetime(2026, 1, 1, tzinfo=UTC)]


class _FrozenMeta(type):
    def __instancecheck__(cls, obj):
        return isinstance(obj, _REAL_DATETIME)

    def __subclasscheck__(cls, sub):
        return issubclass(sub, _REAL_DATETIME)


class FrozenDatetime(datetime, metaclass=_FrozenMeta):
    @classmethod
    def now(cls, tz=None):  # noqa: D102
        now = _FROZEN[0]
        if tz is None:
            return now.astimezone().replace(tzinfo=None)
        return now.astimezone(tz)


def patch_clock() -> None:
    for name, module in list(sys.modules.items()):
        if not name.startswith(accessiweather.__name__) or module is None:
            continue
        for attr, value in list(vars(module).items()):
            if value is _REAL_DATETIME:
                setattr(module, attr, FrozenDatetime)


async def _no_sleep(_delay):
    return None


for _module in (retry, retry_utils):
    _module.asyncio = SimpleNamespace(
        sleep=_no_sleep,
        wait_for=asyncio.wait_for,
        TimeoutError=asyncio.TimeoutError,
        CancelledError=asyncio.CancelledError,
    )

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def cassette(path: str, index: int) -> tuple[int, str]:
    data = yaml.safe_load((CASSETTES / path).read_text(encoding="utf-8"))
    item = data["interactions"][index]
    return item["response"]["status"]["code"], item["response"]["body"]["string"]


def compact(text: str) -> str:
    try:
        return json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)
    except ValueError:
        return text


def route(prefix: str, recorded_at: str, source, trim=None) -> dict:
    status, body = source if isinstance(source, tuple) else (200, source)
    if trim is not None:
        data = json.loads(body)
        trim(data)
        body = json.dumps(data)
    return {"prefix": prefix, "status": status, "body": compact(body), "recorded_at": recorded_at}


def not_found(prefix: str) -> dict:
    return {"prefix": prefix, "status": 404, "body": "", "recorded_at": None}


NWS = "https://api.weather.gov"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast?"
NYC_NOW = "2026-01-20T18:30:00+00:00"
NYC_OPEN_METEO_AT = "2025-01-15T17:30:00+00:00"
LONDON_NOW = "2026-05-11T22:40:00+00:00"


def keep_hours(count: int):
    def trim(data):
        del data["properties"]["periods"][count:]

    return trim


def nyc_routes() -> list[dict]:
    om = f"{OPEN_METEO}latitude=40.7128&longitude=-74.006"
    at = NYC_NOW
    return [
        route(f"{NWS}/points/40.7128,-74.006", at, cassette("nws/point_nyc.yaml", 0)),
        route(
            f"{NWS}/gridpoints/OKX/33,35/stations", at, cassette("nws/stations_nyc.yaml", 1)
        ),
        route(
            f"{NWS}/stations/KNYC/observations/latest",
            at,
            cassette("nws/current_nyc.yaml", 2),
        ),
        route(
            f"{NWS}/gridpoints/OKX/33,35/forecast", at, cassette("nws/forecast_nyc.yaml", 1)
        ),
        route(
            f"{NWS}/gridpoints/OKX/33,35/forecast/hourly",
            at,
            cassette("nws/hourly_nyc.yaml", 1),
            trim=keep_hours(72),
        ),
        route(f"{NWS}/alerts/active", at, cassette("nws/alerts_nyc.yaml", 0)),
        route(
            f"{NWS}/products/types/AFD/locations/OKX",
            at,
            cassette("nws/discussion_nyc.yaml", 1),
        ),
        route(
            f"{NWS}/products/bdb45bc8-aa3a-473c-bc13-aa079f05f816",
            at,
            cassette("nws/discussion_nyc.yaml", 2),
        ),
        route(f"{NWS}/stations/KNYC", at, cassette("weather_client/cache_test.yaml", 5)),
        route(f"{NWS}/stations/KNYC/tafs", at, cassette("weather_client/cache_test.yaml", 6)),
        route(
            "https://aviationweather.gov/api/data/taf",
            at,
            cassette("weather_client/cache_test.yaml", 7),
        ),
        route(
            f"{om}&current=", NYC_OPEN_METEO_AT, cassette("openmeteo/current_weather_nyc.yaml", 0)
        ),
        route(f"{om}&daily=", NYC_OPEN_METEO_AT, cassette("openmeteo/forecast_daily.yaml", 0)),
        route(f"{om}&hourly=", NYC_OPEN_METEO_AT, cassette("openmeteo/hourly_forecast.yaml", 0)),
        not_found(f"{NWS}/"),
        not_found("https://api.open-meteo.com/"),
        not_found("https://aviationweather.gov/"),
    ]


def london_routes() -> list[dict]:
    om = f"{OPEN_METEO}latitude=51.5074&longitude=-0.1278"
    at = LONDON_NOW
    return [
        route(f"{om}&current=", at, cassette("weather_client/openmeteo_current.yaml", 5)),
        route(f"{om}&daily=", at, cassette("weather_client/openmeteo_current.yaml", 3)),
        route(f"{om}&hourly=", at, cassette("weather_client/openmeteo_current.yaml", 4)),
        not_found(f"{NWS}/"),
        not_found("https://api.open-meteo.com/"),
        not_found("https://aviationweather.gov/"),
    ]


class MockClient:
    """AsyncClient stand-in answering by longest URL prefix, like FixtureClient."""

    def __init__(self, routes: list[dict]):
        self.routes = routes
        self.requests: list[str] = []

    async def get(self, url, headers=None, params=None, **_kwargs):
        full = str(httpx.Request("GET", url, params=params).url)
        self.requests.append(full)
        matches = [r for r in self.routes if full.startswith(r["prefix"])]
        best = max(matches, key=lambda r: len(r["prefix"]), default=None)
        status, body = (best["status"], best["body"]) if best else (404, "")
        return httpx.Response(status, content=body.encode(), request=httpx.Request("GET", full))

    async def aclose(self):
        return None


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def to_json(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: to_json(getattr(value, f.name))
            for f in dataclasses.fields(value)
            if f.name != "pending_enrichments"
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, _REAL_DATETIME):
        return (value if value.tzinfo else value.astimezone()).isoformat()
    if isinstance(value, set | frozenset):
        return sorted(to_json(v) for v in value)
    if isinstance(value, list | tuple):
        return [to_json(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    return value


def panel_texts(presentation) -> dict:
    """What `_on_weather_data_received` puts in each panel."""
    if presentation.current_conditions:
        current = presentation.current_conditions.fallback_text
    else:
        current = "No current conditions available."
    if presentation.source_attribution and presentation.source_attribution.summary_text:
        current += f"\n\n{presentation.source_attribution.summary_text}"
    briefing = None
    if presentation.forecast:
        sections = [presentation.forecast.daily_section_text]
        if presentation.forecast.marine_section_text:
            sections.append(presentation.forecast.marine_section_text)
        daily = "\n\n".join(s for s in sections if s).rstrip() or "No daily forecast available."
        hourly = presentation.forecast.hourly_section_text or "No hourly forecast available."
        briefing = presentation.forecast.mobility_briefing or None
    else:
        daily, hourly = "No daily forecast available.", "No hourly forecast available."
    return {
        "current": current,
        "stale_warning": " ".join(presentation.status_messages),
        "daily": daily,
        "hourly": hourly,
        "briefing": briefing,
    }


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

NYC = {"name": "New York, NY", "latitude": 40.7128, "longitude": -74.006, "country_code": "US"}
LONDON = {
    "name": "London, England, United Kingdom",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "country_code": "GB",
    "timezone": "Europe/London",
}
# The environmental client would call real services; the adapters for it
# have their own tests.
BASE_SETTINGS = {"air_quality_enabled": False, "pollen_enabled": False}

CASES = [
    ("us_auto", NYC, NYC_NOW, {}, nyc_routes),
    ("us_nws", NYC, NYC_NOW, {"data_source": "nws"}, nyc_routes),
    ("intl_auto", LONDON, LONDON_NOW, {}, london_routes),
]


async def run_case(name, place, now, overrides, routes_fn) -> None:
    _FROZEN[0] = _REAL_DATETIME.fromisoformat(now)
    settings_overrides = {**BASE_SETTINGS, **overrides}
    settings = AppSettings(**settings_overrides)
    routes = routes_fn()
    mock = MockClient(routes)
    client = WeatherClient(
        user_agent="AccessiWeather/2.0",
        data_source=settings.data_source,
        settings=settings,
    )
    client._http_client = mock
    location = Location(**place)
    weather = await client.get_weather_data(location)
    presentation = WeatherPresenter(settings).present(weather)
    doc = {
        "now": now,
        "local_tz": LOCAL_TZ,
        "settings": settings_overrides,
        "location": place,
        "routes": routes,
        "requests": mock.requests,
        "weather": to_json(weather),
        "presentation": to_json(presentation),
        "panels": panel_texts(presentation),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path}")


async def main() -> None:
    patch_clock()
    for case in CASES:
        await run_case(*case)


if __name__ == "__main__":
    asyncio.run(main())
