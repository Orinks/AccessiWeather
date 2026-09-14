"""Timestamp and raw measurement helpers for weather tool output."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def mapping(value: Any) -> dict:
    """Accept mappings from provider JSON without trusting container types."""
    return value if isinstance(value, dict) else {}


def scalar(value: Any) -> bool:
    """Weather values must be finite numbers or nonempty strings."""
    return (isinstance(value, str) and bool(value)) or (
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    )


def measurement(value: Any, unit: Any = "") -> str | None:
    """Format raw NWS quantities and Open-Meteo scalar measurements."""
    if isinstance(value, dict):
        unit = value.get("unitCode", "")
        value = value.get("value")
    if not scalar(value):
        return None
    unit = unit if isinstance(unit, str) else ""
    units = {
        "wmoUnit:degC": "°C",
        "wmoUnit:degF": "°F",
        "wmoUnit:percent": "%",
        "wmoUnit:km_h-1": "km/h",
        "wmoUnit:m_s-1": "m/s",
        "wmoUnit:Pa": "Pa",
        "wmoUnit:degree_(angle)": "°",
        "wmoUnit:m": "m",
    }
    return f"{value}{units.get(unit, unit)}"


def local_zone(data: dict):
    """Resolve provider time zone, using its UTC offset when needed."""
    name = data.get("timezone")
    if isinstance(name, str):
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    offset = data.get("utc_offset_seconds")
    if (
        isinstance(offset, (int, float))
        and not isinstance(offset, bool)
        and math.isfinite(offset)
        and abs(offset) < 86400
    ):
        return timezone(timedelta(seconds=offset))
    return None


def timestamp(value: Any, data: dict) -> datetime | None:
    """Parse an ISO provider time without guessing a missing local timezone."""
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result if result.tzinfo else result.replace(tzinfo=local_zone(data))


def current_or_future(value: Any, data: dict, now: datetime | None = None, end: Any = None) -> bool:
    """Exclude elapsed hours; preserve unresolvable times as explicitly supplied."""
    start = timestamp(value, data)
    if start is None or start.tzinfo is None:
        return True
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    finish = timestamp(end, data) if end else None
    if finish is None or finish.tzinfo is None:
        finish = start + timedelta(hours=1)
    return finish > moment


def provenance(data: dict, source: str) -> list[str]:
    """Keep provider origin and time interpretation explicit."""
    zone = data.get("timezone")
    if not isinstance(zone, str) or not zone:
        zone = str(local_zone(data) or "not supplied; use timestamps' explicit offsets")
    return [f"Source: {source}", f"Timezone: {zone}"]


def series_lines(data: dict, section: str, limit: int, now: datetime | None = None) -> list[str]:
    """Format aligned Open-Meteo arrays without dropping units or printing metadata."""
    values = mapping(data.get(section))
    units = mapping(data.get(f"{section}_units"))
    times = values.get("time")
    if not isinstance(times, list):
        return []
    result = []
    for index, time in enumerate(times):
        if not isinstance(time, str) or not time:
            continue
        if section == "hourly" and not current_or_future(time, data, now):
            continue
        parts = [time]
        for key, column in values.items():
            if key == "time" or not isinstance(column, list) or index >= len(column):
                continue
            text = measurement(column[index], units.get(key, ""))
            if text is not None:
                parts.append(f"{key}: {text}")
        if len(parts) > 1:
            result.append(" | ".join(parts))
        if len(result) >= limit:
            break
    return result
