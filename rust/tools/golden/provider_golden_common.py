"""Shared helpers for the provider golden generators (openmeteo, pirateweather,
environmental, geocoding, normalization).

Run the generators from the Python checkout so `accessiweather` imports:

    cd C:\\Users\\joshu\\accessiweather
    uv run python <worktree>\\rust\\tools\\golden\\openmeteo.py
"""

from __future__ import annotations

import asyncio
import dataclasses
import enum
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import yaml

RUST_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_ROOT = RUST_ROOT / "testdata" / "golden"
CASSETTES = Path.cwd() / "tests" / "integration" / "cassettes"

# Frozen "now" for every generator: 2025-01-15 17:30 UTC (the NYC cassettes'
# day). Python code that calls datetime.now() sees this instant.
FROZEN_UTC = datetime(2025, 1, 15, 17, 30, tzinfo=UTC)


def to_jsonable(obj: Any) -> Any:
    """Serialize like the porting rules: dataclasses via asdict semantics,
    datetimes ISO with offset (naive → astimezone()), enums by value, sets
    sorted."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, datetime):
        return (obj if obj.tzinfo else obj.astimezone()).isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, set | frozenset):
        return sorted(to_jsonable(v) for v in obj)
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_jsonable(v) for v in obj]
    return obj


def now_local_iso() -> str:
    """The frozen instant with this machine's local offset (what a naive
    `datetime.now()` serializes to)."""
    return FROZEN_UTC.astimezone().isoformat()


class _AnyDatetime(type):
    """Keep `isinstance(x, datetime)` true for ordinary datetimes after the
    module's `datetime` name is swapped for the frozen subclass."""

    def __instancecheck__(cls, obj: Any) -> bool:
        return isinstance(obj, datetime)


class FrozenDatetime(datetime, metaclass=_AnyDatetime):
    """`datetime` whose `now()` returns the frozen instant."""

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        if tz is None:
            return FROZEN_UTC.astimezone().replace(tzinfo=None)
        return FROZEN_UTC.astimezone(tz)


def freeze(*modules: Any) -> None:
    """Replace `datetime` in the given modules with the frozen subclass."""
    for module in modules:
        module.datetime = FrozenDatetime


def cassette_bodies(relative: str) -> list[tuple[str, Any]]:
    """(uri, decoded JSON body) for every 200 interaction in a cassette."""
    data = yaml.safe_load((CASSETTES / relative).read_text(encoding="utf-8"))
    out = []
    for interaction in data["interactions"]:
        response = interaction["response"]
        if response["status"]["code"] != 200:
            continue
        body = response["body"]["string"]
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        out.append((interaction["request"]["uri"], json.loads(body)))
    return out


def unique_bodies(relatives: list[str], host: str | None = None) -> list[tuple[str, Any]]:
    """Distinct bodies across cassettes, named after the cassette."""
    seen: set[str] = set()
    out = []
    for relative in relatives:
        for index, (uri, body) in enumerate(cassette_bodies(relative)):
            if host and urlsplit(uri).hostname != host:
                continue
            digest = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            name = Path(relative).stem + (f"_{index}" if index else "")
            out.append((name, body))
    return out


class Router:
    """httpx MockTransport that answers by URL prefix and records requests.

    Routes are (prefix, status, body) where body may be an exception class
    instance to raise. The longest matching prefix wins.
    """

    def __init__(self, routes: list[tuple[str, int, Any]]):
        self.routes = routes
        self.requests: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        headers = {}
        agent = request.headers.get("user-agent", "")
        if agent and not agent.startswith("python-httpx"):
            headers["user-agent"] = agent
        accept = request.headers.get("accept", "")
        if accept and accept != "*/*":
            headers["accept"] = accept
        self.requests.append({"url": url, "headers": headers})
        matches = [r for r in self.routes if url.startswith(r[0])]
        if not matches:
            raise httpx.ConnectError("no route", request=request)
        prefix, status, body = max(matches, key=lambda r: len(r[0]))
        if isinstance(body, Exception):
            raise body
        return httpx.Response(status, json=body)

    def exchanges(self) -> list[dict[str, Any]]:
        """Requests with the canned answer each got (consecutive duplicate
        retries collapsed, since the Rust HTTP layer retries internally)."""
        out: list[dict[str, Any]] = []
        for request in self.requests:
            if out and out[-1]["url"] == request["url"]:
                continue
            matches = [r for r in self.routes if request["url"].startswith(r[0])]
            entry = dict(request)
            if matches:
                _, status, body = max(matches, key=lambda r: len(r[0]))
                if isinstance(body, httpx.TimeoutException):
                    entry["error"] = "timeout"
                elif isinstance(body, Exception):
                    entry["error"] = "transport"
                else:
                    entry["status"] = status
                    entry["body"] = body
            else:
                entry["error"] = "transport"
            out.append(entry)
        return out


def patch_httpx(router: Router) -> None:
    """Route every new httpx client through `router`."""
    original_async = _ORIGINALS["AsyncClient"]
    original_sync = _ORIGINALS["Client"]

    class AsyncClient(original_async):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = httpx.MockTransport(router.handler)
            super().__init__(*args, **kwargs)

    class Client(original_sync):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = httpx.MockTransport(router.handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = AsyncClient  # type: ignore[misc]
    httpx.Client = Client  # type: ignore[misc]


_ORIGINALS = {"AsyncClient": httpx.AsyncClient, "Client": httpx.Client}


async def _no_sleep(*_args: Any, **_kwargs: Any) -> None:
    return None


def fast_retries() -> None:
    """Skip retry back-off sleeps."""
    import time

    asyncio.sleep = _no_sleep  # type: ignore[assignment]
    time.sleep = lambda *_a, **_k: None  # type: ignore[assignment]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def write(area: str, name: str, data: Any) -> None:
    folder = GOLDEN_ROOT / area
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    payload = to_jsonable(data)
    text = json.dumps(payload, indent=1, ensure_ascii=False, allow_nan=False)
    if len(text) > 64_000:  # keep big cassette-backed cases compact
        text = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    path.write_text(text + "\n", encoding="utf-8")


def reset(area: str) -> None:
    folder = GOLDEN_ROOT / area
    if folder.exists():
        for path in folder.glob("*.json"):
            path.unlink()
