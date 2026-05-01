"""Aviation weather presentation helpers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from ...models import AviationData, Location
from ...utils import decode_taf_text
from .models import AviationPresentation


def build_aviation(
    aviation: AviationData | None,
    location: Location,
    format_timestamp: Callable[[datetime], str],
) -> AviationPresentation | None:
    """Build an aviation presentation from METAR/TAF advisory data."""
    if aviation is None:
        return None

    has_advisories = bool(aviation.active_sigmets or aviation.active_cwas)
    taf_available = bool(
        (aviation.raw_taf and aviation.raw_taf.strip())
        or (aviation.decoded_taf and aviation.decoded_taf.strip())
    )
    if not (taf_available or has_advisories):
        return None

    station_label = aviation.airport_name or aviation.station_id
    header_location = (
        f"{station_label} near {location.name}"
        if station_label and station_label.lower() != location.name.lower()
        else station_label or location.name
    )
    header = f"Aviation weather for {header_location}."

    taf_summary = aviation.decoded_taf
    if not taf_summary and aviation.raw_taf:
        taf_summary = decode_taf_text(aviation.raw_taf)

    sigmet_lines = [
        summary
        for summary in (
            _summarize_sigmet(entry, format_timestamp) for entry in aviation.active_sigmets[:5]
        )
        if summary
    ]
    cwa_lines = [
        summary
        for summary in (
            _summarize_cwa(entry, format_timestamp) for entry in aviation.active_cwas[:5]
        )
        if summary
    ]

    fallback_lines: list[str] = [header]
    if taf_summary:
        fallback_lines.append("Terminal Aerodrome Forecast:")
        fallback_lines.append(taf_summary)
        if aviation.raw_taf and aviation.raw_taf.strip():
            fallback_lines.append("Raw TAF message:")
            fallback_lines.append(aviation.raw_taf.strip())
    elif aviation.raw_taf and aviation.raw_taf.strip():
        fallback_lines.append("Raw Terminal Aerodrome Forecast:")
        fallback_lines.append(aviation.raw_taf.strip())
    else:
        fallback_lines.append("No Terminal Aerodrome Forecast available.")

    if sigmet_lines:
        fallback_lines.append("SIGMET and AIRMET advisories:")
        fallback_lines.extend(f"• {line}" for line in sigmet_lines)
    if cwa_lines:
        fallback_lines.append("Center Weather Advisories:")
        fallback_lines.extend(f"• {line}" for line in cwa_lines)

    return AviationPresentation(
        title="Aviation Weather",
        airport_name=aviation.airport_name,
        station_id=aviation.station_id,
        taf_summary=taf_summary,
        raw_taf=aviation.raw_taf,
        sigmets=sigmet_lines,
        cwas=cwa_lines,
        fallback_text="\n".join(fallback_lines),
    )


def _format_aviation_time(
    value: str | None,
    format_timestamp: Callable[[datetime], str],
) -> str | None:
    if not value:
        return None
    try:
        sanitized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        timestamp = datetime.fromisoformat(sanitized)
    except ValueError:
        return value
    return format_timestamp(timestamp)


def _summarize_sigmet(data: Any, format_timestamp: Callable[[datetime], str]) -> str | None:
    if not isinstance(data, dict):
        return None

    name = (
        data.get("name")
        or data.get("event")
        or data.get("hazard")
        or data.get("phenomenon")
        or "SIGMET"
    )
    severity = data.get("severity") or data.get("intensity")
    area = data.get("fir") or data.get("area") or data.get("regions") or data.get("airspace")
    if isinstance(area, list):
        area = ", ".join(str(item) for item in area if item)

    start = _format_aviation_time(
        data.get("startTime")
        or data.get("beginTime")
        or data.get("validTimeStart")
        or data.get("issueTime"),
        format_timestamp,
    )
    end = _format_aviation_time(
        data.get("endTime")
        or data.get("expires")
        or data.get("validTimeEnd")
        or data.get("validUntil"),
        format_timestamp,
    )
    description = data.get("description") or data.get("text") or data.get("summary")

    summary_parts = [name]
    if severity:
        summary_parts.append(f"severity {severity}")
    summary = " ".join(summary_parts)

    detail_parts: list[str] = []
    if area:
        detail_parts.append(f"Area: {area}")
    if start or end:
        if start and end:
            detail_parts.append(f"Valid {start} to {end}")
        elif end:
            detail_parts.append(f"Valid until {end}")
        elif start:
            detail_parts.append(f"Effective {start}")
    if description:
        detail_parts.append(description)

    details = "; ".join(detail_parts)
    return f"{summary}; {details}" if details else summary


def _summarize_cwa(data: Any, format_timestamp: Callable[[datetime], str]) -> str | None:
    if not isinstance(data, dict):
        return None

    name = (
        data.get("event")
        or data.get("phenomenon")
        or data.get("hazard")
        or data.get("productType")
        or "Center Weather Advisory"
    )
    cwsu = data.get("cwsu") or data.get("issuingOffice")
    area = data.get("area") or data.get("regions") or data.get("airspace") or cwsu
    if isinstance(area, list):
        area = ", ".join(str(item) for item in area if item)

    start = _format_aviation_time(data.get("startTime") or data.get("issueTime"), format_timestamp)
    end = _format_aviation_time(data.get("endTime") or data.get("expires"), format_timestamp)
    description = data.get("description") or data.get("text") or data.get("summary")

    summary_parts = [name]
    if cwsu and cwsu not in summary_parts:
        summary_parts.append(f"({cwsu})")
    summary = " ".join(summary_parts)

    detail_parts: list[str] = []
    if area and area not in summary:
        detail_parts.append(f"Area: {area}")
    if start or end:
        if start and end:
            detail_parts.append(f"Valid {start} to {end}")
        elif end:
            detail_parts.append(f"Valid until {end}")
        elif start:
            detail_parts.append(f"Issued {start}")
    if description:
        detail_parts.append(description)

    details = "; ".join(detail_parts)
    return f"{summary}; {details}" if details else summary
