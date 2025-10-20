"""Utilities for decoding Terminal Aerodrome Forecast (TAF) text."""

from __future__ import annotations

import logging
import re
from fractions import Fraction
from typing import Any

logger = logging.getLogger(__name__)

_ISSUE_TIME_RE = re.compile(r"^\d{6}Z$")
_TIME_RANGE_RE = re.compile(r"^\d{4}/\d{4}$")
_FM_TIME_RE = re.compile(r"^FM\d{6}$")
_PROB_RE = re.compile(r"^PROB(?P<prob>\d{2})(?P<period>\d{4}/\d{4})?$")
_TEMPO_RE = re.compile(r"^TEMPO(?P<period>\d{4}/\d{4})?$")
_BECMG_RE = re.compile(r"^BECMG(?P<period>\d{4}/\d{4})?$")
_WIND_RE = re.compile(
    r"^(?P<dir>\d{3}|VRB)(?P<speed>\d{2,3})(?P<gust>G\d{2,3})?(?P<unit>KT|MPS|KMH)$"
)
_CLOUD_RE = re.compile(r"^(FEW|SCT|BKN|OVC|NSC|SKC|CLR|VV)(\d{3}|///)?(CB|TCU|///)?$")

_DESCRIPTORS = {
    "MI": "shallow",
    "PR": "partial",
    "BC": "patches of",
    "DR": "low drifting",
    "BL": "blowing",
    "SH": "showers of",
    "TS": "thunderstorms with",
    "FZ": "freezing",
    "RE": "recent",
}

_PHENOMENA = {
    "DZ": "drizzle",
    "RA": "rain",
    "SN": "snow",
    "SG": "snow grains",
    "IC": "ice crystals",
    "PL": "ice pellets",
    "GR": "hail",
    "GS": "small hail",
    "UP": "unknown precipitation",
    "BR": "mist",
    "FG": "fog",
    "FU": "smoke",
    "VA": "volcanic ash",
    "DU": "dust",
    "SA": "sand",
    "HZ": "haze",
    "PY": "spray",
    "PO": "dust/sand whirls",
    "SQ": "squalls",
    "FC": "funnel clouds",
    "SS": "sandstorm",
    "DS": "dust storm",
    "SH": "showers",
    "TS": "thunderstorms",
}

_INTENSITY = {"+": "heavy", "-": "light"}


def decode_taf_text(raw_taf: str) -> str:
    """Decode a raw TAF string into an accessible textual summary."""
    if not raw_taf:
        return "No TAF available."

    cleaned = " ".join(raw_taf.strip().split())
    if not cleaned:
        return "No TAF available."

    tokens = [token.rstrip("=") for token in cleaned.split() if token and token != "="]
    if not tokens:
        return "No TAF available."

    try:
        return _decode_tokens(tokens)
    except Exception:  # noqa: BLE001
        logger.exception("Unable to decode TAF")
        return cleaned


def _decode_tokens(tokens: list[str]) -> str:
    working = tokens.copy()
    prefixes = {"TAF", "AMD", "COR"}
    while working and working[0] in prefixes:
        working.pop(0)

    station = working.pop(0) if working else None
    if not working:
        return _format_header_only(station)

    if working and working[0] == "NIL":
        station_text = f" for station {station}" if station else ""
        return f"No TAF available{station_text}."

    issue_time = working.pop(0) if working and _ISSUE_TIME_RE.match(working[0]) else None
    validity = working.pop(0) if working and _TIME_RANGE_RE.match(working[0]) else None

    segments, remarks = _split_segments(working)

    lines: list[str] = []
    if station:
        lines.append(f"Forecast for station {station}.")
    else:
        lines.append("Terminal Aerodrome Forecast.")

    if issue_time:
        lines.append(f"Issued at {_format_issue_time(issue_time)}.")
    if validity:
        lines.append(f"Valid {_format_time_range(validity)}.")

    for segment in segments:
        intro = _segment_intro(segment)
        description = _describe_segment(segment)
        if description:
            if intro:
                lines.append(f"{intro} {description}".strip())
            else:
                lines.append(description)

    if remarks:
        lines.append(f"Remarks: {remarks}.")

    return "\n".join(lines)


def _format_header_only(station: str | None) -> str:
    if station:
        return f"TAF issued for station {station}."
    return "TAF issued, but no additional information was provided."


def _split_segments(tokens: list[str]) -> tuple[list[dict[str, Any]], str | None]:
    segments: list[dict[str, Any]] = [{"type": "base", "tokens": []}]
    remarks: str | None = None

    current = segments[0]
    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token == "RMK":
            remarks = " ".join(tokens[i + 1 :]).strip()
            break

        fm_match = _FM_TIME_RE.match(token)
        if fm_match:
            current = {"type": "from", "time": token[2:], "tokens": []}
            segments.append(current)
            i += 1
            continue

        tempo_match = _TEMPO_RE.match(token)
        if tempo_match:
            period = tempo_match.group("period")
            if not period and i + 1 < len(tokens) and _TIME_RANGE_RE.match(tokens[i + 1]):
                i += 1
                period = tokens[i]
            current = {"type": "tempo", "period": period, "tokens": []}
            segments.append(current)
            i += 1
            continue

        becmg_match = _BECMG_RE.match(token)
        if becmg_match:
            period = becmg_match.group("period")
            if not period and i + 1 < len(tokens) and _TIME_RANGE_RE.match(tokens[i + 1]):
                i += 1
                period = tokens[i]
            current = {"type": "becmg", "period": period, "tokens": []}
            segments.append(current)
            i += 1
            continue

        prob_match = _PROB_RE.match(token)
        if prob_match:
            probability = int(prob_match.group("prob"))
            period = prob_match.group("period")
            if not period and i + 1 < len(tokens) and _TIME_RANGE_RE.match(tokens[i + 1]):
                i += 1
                period = tokens[i]

            qualifier = None
            if i + 1 < len(tokens) and tokens[i + 1].startswith("TEMPO"):
                i += 1
                tempo_token = tokens[i]
                tempo_match = _TEMPO_RE.match(tempo_token)
                qualifier = "tempo"
                if tempo_match:
                    tempo_period = tempo_match.group("period")
                    if tempo_period:
                        period = tempo_period
                    elif i + 1 < len(tokens) and _TIME_RANGE_RE.match(tokens[i + 1]):
                        i += 1
                        period = tokens[i]

            current = {
                "type": "probability",
                "prob": probability,
                "period": period,
                "qualifier": qualifier,
                "tokens": [],
            }
            segments.append(current)
            i += 1
            continue

        current.setdefault("tokens", []).append(token)
        i += 1

    filtered = [segment for segment in segments if segment.get("tokens")]
    if not filtered:
        filtered = [segments[0]]

    return filtered, remarks


def _segment_intro(segment: dict[str, Any]) -> str:
    seg_type = segment.get("type")
    if seg_type == "base":
        return "Base forecast:"
    if seg_type == "from":
        time_token = segment.get("time")
        if isinstance(time_token, str):
            return f"From {_format_from_time(time_token)}:"
        return "From forecast period:"
    if seg_type == "tempo":
        period = segment.get("period")
        if isinstance(period, str):
            return f"Temporary between {_format_time_range(period)}:"
        return "Temporary conditions:"
    if seg_type == "becmg":
        period = segment.get("period")
        if isinstance(period, str):
            return f"Becoming {_format_time_range(period)}:"
        return "Becoming conditions:"
    if seg_type == "probability":
        probability = segment.get("prob")
        period = segment.get("period")
        qualifier = segment.get("qualifier")
        prefix = (
            f"Probability {probability}%" if probability is not None else "Probability forecast"
        )
        if qualifier == "tempo":
            prefix += " of temporary conditions"
        if isinstance(period, str):
            return f"{prefix} {_format_time_range(period)}:"
        return f"{prefix}:"
    return ""


def _describe_segment(segment: dict[str, Any]) -> str:
    tokens = segment.get("tokens", [])
    if not tokens:
        return "No additional details provided."

    wind_text: str | None = None
    visibility_text: str | None = None
    weather_texts: list[str] = []
    cloud_texts: list[str] = []
    extra_tokens: list[str] = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        next_token = tokens[i + 1] if i + 1 < len(tokens) else None

        if token.isdigit() and next_token and next_token.endswith("SM") and "/" in next_token:
            combined_token = f"{token} {next_token}"
            visibility = _decode_visibility(combined_token)
            if visibility and not visibility_text:
                visibility_text = visibility
            elif visibility:
                weather_texts.append(visibility)
            i += 2
            continue

        wind = _decode_wind(token)
        if wind and wind_text is None:
            wind_text = wind
            i += 1
            continue

        visibility = _decode_visibility(token)
        if visibility and visibility_text is None:
            visibility_text = visibility
            i += 1
            continue

        weather = _decode_weather(token)
        if weather:
            weather_texts.append(weather)
            i += 1
            continue

        cloud = _decode_cloud(token)
        if cloud:
            cloud_texts.append(cloud)
            i += 1
            continue

        if token == "CAVOK":
            if visibility_text is None:
                visibility_text = "Ceiling and visibility OK (CAVOK)"
            else:
                cloud_texts.append("Ceiling and visibility OK (CAVOK)")
            i += 1
            continue

        if token == "NSW":
            weather_texts.append("No significant weather (NSW)")
            i += 1
            continue

        extra_tokens.append(token)
        i += 1

    sentences: list[str] = []
    if wind_text:
        sentences.append(f"{wind_text}.")
    if visibility_text:
        sentences.append(f"{visibility_text}.")
    if weather_texts:
        sentences.append(f"Weather: {'; '.join(weather_texts)}.")
    if cloud_texts:
        sentences.append(f"Clouds: {'; '.join(cloud_texts)}.")
    if extra_tokens:
        sentences.append(f"Additional codes: {' '.join(extra_tokens)}.")

    return " ".join(sentences) if sentences else "No additional details provided."


def _decode_wind(token: str) -> str | None:
    match = _WIND_RE.match(token)
    if not match:
        return None

    direction = match.group("dir")
    speed = match.group("speed")
    gust = match.group("gust")
    unit = match.group("unit")

    unit_text = {
        "KT": "knots",
        "MPS": "meters per second",
        "KMH": "kilometres per hour",
    }.get(unit, unit.lower())

    speed_value = int(speed)
    if direction == "000" and speed_value == 0:
        base = "Calm winds"
    elif direction == "VRB":
        base = f"Winds variable at {speed_value} {unit_text}"
    else:
        base = f"Winds from {direction} degrees at {speed_value} {unit_text}"

    if gust:
        gust_value = int(gust[1:])
        base += f" with gusts to {gust_value} {unit_text}"

    return f"{base} ({token})"


def _decode_visibility(token: str) -> str | None:
    working = token.strip()
    if not working:
        return None

    if working.endswith("SM"):
        magnitude = working[:-2].strip()
        prefix = None
        if magnitude.startswith(("P", "M")):
            prefix = magnitude[0]
            magnitude = magnitude[1:]

        whole_number = None
        fraction_part = magnitude
        if " " in magnitude:
            parts = magnitude.split()
            whole_number = parts[0]
            fraction_part = parts[-1]
        elif " " in token:
            parts = token.replace("SM", "").split()
            if len(parts) == 2:
                whole_number, fraction_part = parts

        decimal_value: float | None = None
        display_value = magnitude

        if whole_number is not None and "/" in fraction_part:
            try:
                fraction = Fraction(fraction_part)
                decimal_value = int(whole_number) + float(fraction)
                display_value = f"{whole_number} {fraction_part}"
            except (ValueError, ZeroDivisionError):
                display_value = f"{whole_number} {fraction_part}"
        elif "/" in fraction_part:
            try:
                fraction = Fraction(fraction_part)
                decimal_value = float(fraction)
                display_value = fraction_part
            except (ValueError, ZeroDivisionError):
                display_value = fraction_part
        else:
            try:
                decimal_value = float(fraction_part)
                display_value = fraction_part
            except ValueError:
                display_value = fraction_part

        descriptor = "Visibility"
        if prefix == "P":
            descriptor = "Visibility greater than"
        elif prefix == "M":
            descriptor = "Visibility less than"

        if decimal_value is not None:
            decimal_str = f"{decimal_value:.2f}".rstrip("0").rstrip(".")
            decimal_text = f" ({decimal_str} SM)"
        else:
            decimal_text = ""

        return f"{descriptor} {display_value} statute miles{decimal_text} ({token})"

    if len(working) == 4 and working.isdigit():
        distance_m = int(working)
        if distance_m == 9999:
            return "Visibility 10 kilometres or more (9999 meters)"
        distance_km = distance_m / 1000
        return f"Visibility {distance_km:.1f} kilometres ({working} meters)"

    return None


def _decode_weather(token: str) -> str | None:
    if not token:
        return None

    original = token
    qualifier = ""
    intensity = ""
    working = token

    if working.startswith("VC"):
        qualifier = "In the vicinity, "
        working = working[2:]

    if working and working[0] in _INTENSITY:
        intensity = _INTENSITY[working[0]]
        working = working[1:]

    descriptors: list[str] = []
    phenomena: list[str] = []

    while working:
        code = working[:2]
        if code in _DESCRIPTORS:
            descriptors.append(_DESCRIPTORS[code])
            working = working[2:]
            continue
        if code in _PHENOMENA:
            phenomena.append(_PHENOMENA[code])
            working = working[2:]
            continue
        break

    if not descriptors and not phenomena and not intensity:
        return None

    descriptor_text = " ".join(descriptors).strip()
    phenomena_text = " and ".join(phenomena).strip()

    pieces = [part for part in [intensity, descriptor_text, phenomena_text] if part]
    if not pieces:
        pieces.append("weather conditions")

    description = " ".join(pieces)
    description = description.replace("  ", " ").strip()

    return f"{qualifier}{description} ({original})"


def _decode_cloud(token: str) -> str | None:
    if not token:
        return None

    if token in {"SKC", "CLR"}:
        return f"Sky clear ({token})"
    if token == "NSC":
        return "No significant clouds (NSC)"

    match = _CLOUD_RE.match(token)
    if not match:
        return None

    cover = match.group(1)
    height = match.group(2)
    cloud_type = match.group(3)

    cover_text = {
        "FEW": "A few clouds",
        "SCT": "Scattered clouds",
        "BKN": "Broken clouds",
        "OVC": "Overcast",
        "VV": "Vertical visibility",
    }.get(cover, cover)

    if cover == "VV" and height and height.isdigit():
        altitude = int(height) * 100
        return f"Vertical visibility {altitude:,} feet ({token})"

    altitude_text = ""
    if height and height.isdigit():
        altitude = int(height) * 100
        altitude_text = f" at {altitude:,} feet"

    type_text = ""
    if cloud_type == "CB":
        type_text = " with cumulonimbus"
    elif cloud_type == "TCU":
        type_text = " with towering cumulus"

    return f"{cover_text}{altitude_text}{type_text} ({token})"


def _format_issue_time(token: str) -> str:
    day = int(token[:2])
    hour = int(token[2:4])
    minute = int(token[4:6])
    return f"{hour:02d}:{minute:02d} UTC on the {_format_day(day)}"


def _format_time_range(token: str) -> str:
    if not _TIME_RANGE_RE.match(token):
        return token
    start_raw, end_raw = token.split("/")
    start_day = int(start_raw[:2])
    start_hour = int(start_raw[2:4])
    end_day = int(end_raw[:2])
    end_hour = int(end_raw[2:4])
    return (
        f"from {start_hour:02d}:00 UTC on the {_format_day(start_day)} "
        f"until {end_hour:02d}:00 UTC on the {_format_day(end_day)}"
    )


def _format_from_time(token: str) -> str:
    if len(token) != 6 or not token.isdigit():
        return token
    day = int(token[:2])
    hour = int(token[2:4])
    minute = int(token[4:6])
    return f"{hour:02d}:{minute:02d} UTC on the {_format_day(day)}"


def _format_day(day: int) -> str:
    suffix = "th" if 10 <= day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


__all__ = ["decode_taf_text"]
