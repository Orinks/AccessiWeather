"""Shared helpers for the golden parity generators.

Run the generators from the Python checkout, e.g.
``uv run python <worktree>/rust/tools/golden/fusion.py``.
"""

from __future__ import annotations

import dataclasses
import enum
import json
from datetime import date, datetime
from pathlib import Path

GOLDEN_ROOT = Path(__file__).resolve().parents[2] / "testdata" / "golden"


def jsonable(obj):
    """dataclasses.asdict with ISO-8601 (offset) datetimes, enum values and sorted sets."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, datetime):
        return (obj if obj.tzinfo else obj.astimezone()).isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, set | frozenset):
        return sorted(jsonable(v) for v in obj)
    if isinstance(obj, list | tuple):
        return [jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj
    return None  # asyncio tasks and other runtime-only values


def write(area: str, name: str, data) -> None:
    path = GOLDEN_ROOT / area / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(data), indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {path}")


def frozen_datetime(frozen: datetime):
    """A datetime subclass whose now() returns ``frozen`` (naive now() is local time)."""

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen.astimezone().replace(tzinfo=None)
            return frozen.astimezone(tz)

    return FrozenDatetime
