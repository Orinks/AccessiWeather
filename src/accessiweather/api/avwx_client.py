"""AVWX REST API client for international aviation weather (TAF/METAR)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models.weather import AviationData

logger = logging.getLogger(__name__)

AVWX_BASE_URL = "https://avwx.rest/api"

# ICAO prefixes that belong to US/US-territories and are covered by NWS/AWC.
# K  = contiguous United States
# PA = Alaska
# PH = Hawaii
# PG = Guam
# PF = Alaska bush
# PK = Wake Island / Micronesia (US-affiliated)
# PP = Pacific islands
_US_ICAO_PREFIXES: tuple[str, ...] = ("K", "PA", "PH", "PG", "PF", "PK", "PP")


def is_us_station(icao: str) -> bool:
    """
    Return True when the ICAO code belongs to US or US-territory coverage.

    US stations are handled by the NWS/AWC path.  Everything else should be
    routed through AVWX for better translated/TTS output.
    """
    code = (icao or "").strip().upper()
    if not code:
        return False
    return any(code.startswith(prefix) for prefix in _US_ICAO_PREFIXES)


class AvwxApiError(Exception):
    """Raised when the AVWX API returns a non-success response."""


async def fetch_avwx_taf(
    station: str,
    api_key: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    timeout: float = 10.0,
) -> AviationData:
    """
    Fetch and parse a TAF from the AVWX REST API.

    Args:
        station: ICAO airport identifier (e.g. ``EGLL``, ``RJTT``).
        api_key: AVWX API token (free tier accepted).
        http_client: Optional reusable :class:`httpx.AsyncClient`.  A
            temporary client is created and closed if not supplied.
        timeout: Request timeout in seconds.

    Returns:
        :class:`~accessiweather.models.weather.AviationData` populated with
        raw TAF text and an accessible decoded/TTS-ready summary.

    Raises:
        :class:`AvwxApiError`: When the API returns an error status.
        :class:`httpx.HTTPError`: On network failures.

    """
    station = (station or "").strip().upper()
    if not station:
        raise ValueError("station must be a non-empty ICAO identifier")

    url = f"{AVWX_BASE_URL}/taf/{station}"
    params: dict[str, str] = {
        "token": api_key,
        "options": "info,translate,speech,summary",
    }
    headers = {"Accept": "application/json"}

    own_client = http_client is None
    client: httpx.AsyncClient = http_client or httpx.AsyncClient(timeout=timeout)

    try:
        response = await client.get(url, params=params, headers=headers)

        if response.status_code == 401:
            raise AvwxApiError(
                "AVWX API key is invalid or expired. "
                "Please update your key in Settings → Data Sources."
            )
        if response.status_code == 404:
            raise AvwxApiError(
                f"Station {station} was not found in AVWX. Verify the ICAO code and try again."
            )
        if response.status_code != 200:
            raise AvwxApiError(
                f"AVWX API returned HTTP {response.status_code} for station {station}."
            )

        data: dict[str, Any] = response.json()

        return _build_aviation_data(station, data)

    finally:
        if own_client:
            await client.aclose()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_aviation_data(station: str, data: dict[str, Any]) -> AviationData:
    """Construct an :class:`AviationData` object from a raw AVWX TAF payload."""
    aviation = AviationData(station_id=station, airport_name=station)

    # Station info
    info: dict[str, Any] = data.get("info") or {}
    name = info.get("name") or info.get("city")
    if name:
        aviation.airport_name = str(name)

    # Raw TAF text
    raw = data.get("raw")
    if raw:
        aviation.raw_taf = str(raw).strip() or None

    # Build the decoded/accessible summary
    decoded = _build_decoded_taf(station, data, info)
    aviation.decoded_taf = decoded or None

    return aviation


def _build_decoded_taf(
    station: str,
    data: dict[str, Any],
    info: dict[str, Any],
) -> str:
    """
    Build a screen-reader-friendly TAF summary from AVWX response data.

    AVWX provides several accessibility-oriented fields:

    * ``data["speech"]`` – a full TTS-ready sentence for the entire TAF.
    * ``forecast[i]["speech"]`` – per-period spoken summary.
    * ``translate["forecast"][i]`` – plain-English field-by-field translation.

    We prefer the top-level ``speech`` field when available because it is
    already optimised for text-to-speech delivery.
    """
    # Best case: use the top-level TTS speech string
    speech: str = (data.get("speech") or "").strip()
    if speech:
        return speech

    # Fallback: build from individual period translations
    lines: list[str] = []

    station_label = info.get("name") or info.get("city") or station
    lines.append(f"Terminal Aerodrome Forecast for {station_label}.")

    start_str = _format_avwx_time(data.get("start_time"))
    end_str = _format_avwx_time(data.get("end_time"))
    if start_str and end_str:
        lines.append(f"Valid from {start_str} to {end_str}.")
    elif start_str:
        lines.append(f"Valid from {start_str}.")

    forecast: list[dict[str, Any]] = data.get("forecast") or []
    translate_list: list[dict[str, Any]] = (data.get("translate") or {}).get("forecast") or []

    for idx, period in enumerate(forecast):
        trans: dict[str, Any] | None = translate_list[idx] if idx < len(translate_list) else None
        period_lines = _format_period(period, trans)
        lines.extend(period_lines)

    return "\n".join(lines)


def _format_period(
    period: dict[str, Any],
    trans: dict[str, Any] | None,
) -> list[str]:
    """Format a single forecast period into readable lines."""
    lines: list[str] = []

    # Period type label
    period_type: str = (period.get("type") or "FM").upper()
    type_labels: dict[str, str] = {
        "FM": "From",
        "FROM": "From",
        "TEMPO": "Temporary",
        "BECMG": "Becoming",
        "PROB": "Probability",
    }
    type_label = type_labels.get(period_type, period_type)

    prob = period.get("probability")
    if prob is not None and period_type in ("PROB", "PROBABILITY"):
        prob_val = prob.get("value") if isinstance(prob, dict) else prob
        if prob_val is not None:
            type_label = f"Probability {prob_val}%"

    start_str = _format_avwx_time(period.get("start_time"))
    end_str = _format_avwx_time(period.get("end_time"))

    if start_str and end_str:
        header = f"{type_label} from {start_str} to {end_str}:"
    elif start_str:
        header = f"{type_label} from {start_str}:"
    else:
        header = f"{type_label}:"

    lines.append(header)

    # Prefer the per-period spoken string
    period_speech: str = (period.get("speech") or "").strip()
    if period_speech:
        lines.append(f"  {period_speech}")
        return lines

    # Build from translation fields
    if trans:
        parts: list[str] = []
        if trans.get("wind"):
            parts.append(str(trans["wind"]))
        if trans.get("visibility"):
            parts.append(f"Visibility: {trans['visibility']}")
        if trans.get("clouds"):
            parts.append(f"Clouds: {trans['clouds']}")
        if trans.get("wx_codes"):
            parts.append(f"Weather: {trans['wx_codes']}")

        # Flight rules
        flight_rules: str | None = period.get("flight_rules") or (
            trans.get("flight_rules") if trans else None
        )
        if flight_rules:
            lines.append(f"  Flight rules: {flight_rules}.")

        if parts:
            lines.append("  " + "; ".join(parts) + ".")
    else:
        # Absolute fallback: raw encoded period string
        raw_period: str = (period.get("raw") or "").strip()
        if raw_period:
            lines.append(f"  {raw_period}")

    return lines


def _format_avwx_time(time_data: Any) -> str | None:
    """Convert an AVWX time object or ISO string into a human-readable string."""
    if not time_data:
        return None

    if isinstance(time_data, str):
        return time_data

    if isinstance(time_data, dict):
        dt_str: str | None = time_data.get("dt")
        if dt_str:
            try:
                from datetime import datetime, timezone

                dt_str = dt_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str)
                utc_dt = dt.astimezone(timezone.utc)
                day = utc_dt.day
                suffix = (
                    "th"
                    if 10 <= day % 100 <= 20
                    else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
                )
                return utc_dt.strftime(f"%H:%MZ on the {day}{suffix}")
            except (ValueError, TypeError):
                pass

        # Fall back to the "repr" field (e.g. "1812/1912")
        repr_val = time_data.get("repr")
        if repr_val:
            return str(repr_val)

    return None


__all__ = [
    "AvwxApiError",
    "AVWX_BASE_URL",
    "fetch_avwx_taf",
    "is_us_station",
]
