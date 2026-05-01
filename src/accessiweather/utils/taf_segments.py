"""TAF segment parsing and description helpers."""

from __future__ import annotations

from typing import Any

from .taf_elements import _decode_cloud, _decode_visibility, _decode_weather, _decode_wind
from .taf_patterns import BECMG_RE, FM_TIME_RE, ISSUE_TIME_RE, PROB_RE, TEMPO_RE, TIME_RANGE_RE
from .taf_time import _format_from_time, _format_issue_time, _format_time_range


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

    issue_time = working.pop(0) if working and ISSUE_TIME_RE.match(working[0]) else None
    validity = working.pop(0) if working and TIME_RANGE_RE.match(working[0]) else None
    segments, remarks = _split_segments(working)

    lines: list[str] = []
    lines.append(f"Forecast for station {station}." if station else "Terminal Aerodrome Forecast.")

    if issue_time:
        lines.append(f"Issued at {_format_issue_time(issue_time)}.")
    if validity:
        lines.append(f"Valid {_format_time_range(validity)}.")

    for segment in segments:
        intro = _segment_intro(segment)
        description = _describe_segment(segment)
        if description:
            lines.append(f"{intro} {description}".strip() if intro else description)

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

        segment = _new_change_segment(token, tokens, i)
        if segment is not None:
            current, i = segment
            segments.append(current)
            continue

        current.setdefault("tokens", []).append(token)
        i += 1

    filtered = [segment for segment in segments if segment.get("tokens")]
    if not filtered:
        filtered = [segments[0]]

    return filtered, remarks


def _new_change_segment(
    token: str, tokens: list[str], index: int
) -> tuple[dict[str, Any], int] | None:
    if FM_TIME_RE.match(token):
        return {"type": "from", "time": token[2:], "tokens": []}, index + 1

    simple = _new_period_segment(token, tokens, index, TEMPO_RE, "tempo")
    if simple is not None:
        return simple

    simple = _new_period_segment(token, tokens, index, BECMG_RE, "becmg")
    if simple is not None:
        return simple

    return _new_probability_segment(token, tokens, index)


def _new_period_segment(
    token: str, tokens: list[str], index: int, regex, segment_type: str
) -> tuple[dict[str, Any], int] | None:
    match = regex.match(token)
    if not match:
        return None

    period = match.group("period")
    next_index = index + 1
    if not period and next_index < len(tokens) and TIME_RANGE_RE.match(tokens[next_index]):
        period = tokens[next_index]
        next_index += 1
    return {"type": segment_type, "period": period, "tokens": []}, next_index


def _new_probability_segment(
    token: str, tokens: list[str], index: int
) -> tuple[dict[str, Any], int] | None:
    match = PROB_RE.match(token)
    if not match:
        return None

    probability = int(match.group("prob"))
    period = match.group("period")
    next_index = index + 1
    if not period and next_index < len(tokens) and TIME_RANGE_RE.match(tokens[next_index]):
        period = tokens[next_index]
        next_index += 1

    qualifier = None
    if next_index < len(tokens) and tokens[next_index].startswith("TEMPO"):
        qualifier = "tempo"
        tempo_match = TEMPO_RE.match(tokens[next_index])
        next_index += 1
        if tempo_match:
            tempo_period = tempo_match.group("period")
            if tempo_period:
                period = tempo_period
            elif next_index < len(tokens) and TIME_RANGE_RE.match(tokens[next_index]):
                period = tokens[next_index]
                next_index += 1

    return {
        "type": "probability",
        "prob": probability,
        "period": period,
        "qualifier": qualifier,
        "tokens": [],
    }, next_index


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
        return _probability_intro(segment)
    return ""


def _probability_intro(segment: dict[str, Any]) -> str:
    probability = segment.get("prob")
    period = segment.get("period")
    qualifier = segment.get("qualifier")
    prefix = f"Probability {probability}%" if probability is not None else "Probability forecast"
    if qualifier == "tempo":
        prefix += " of temporary conditions"
    if isinstance(period, str):
        return f"{prefix} {_format_time_range(period)}:"
    return f"{prefix}:"


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
        consumed, wind_text, visibility_text = _consume_visibility_or_wind(
            token, next_token, wind_text, visibility_text, weather_texts
        )
        if consumed:
            i += consumed
            continue

        consumed = _consume_weather_or_cloud(token, weather_texts, cloud_texts)
        if consumed:
            i += consumed
            continue

        extra_tokens.append(token)
        i += 1

    return _format_segment_sentences(
        wind_text, visibility_text, weather_texts, cloud_texts, extra_tokens
    )


def _consume_visibility_or_wind(
    token: str,
    next_token: str | None,
    wind_text: str | None,
    visibility_text: str | None,
    weather_texts: list[str],
) -> tuple[int, str | None, str | None]:
    if token.isdigit() and next_token and next_token.endswith("SM") and "/" in next_token:
        visibility = _decode_visibility(f"{token} {next_token}")
        if visibility and not visibility_text:
            visibility_text = visibility
        elif visibility:
            weather_texts.append(visibility)
        return 2, wind_text, visibility_text

    wind = _decode_wind(token)
    if wind and wind_text is None:
        return 1, wind, visibility_text

    visibility = _decode_visibility(token)
    if visibility and visibility_text is None:
        return 1, wind_text, visibility

    return 0, wind_text, visibility_text


def _consume_weather_or_cloud(token: str, weather_texts: list[str], cloud_texts: list[str]) -> int:
    weather = _decode_weather(token)
    if weather:
        weather_texts.append(weather)
        return 1

    cloud = _decode_cloud(token)
    if cloud:
        cloud_texts.append(cloud)
        return 1

    if token == "CAVOK":
        cloud_texts.append("Ceiling and visibility OK (CAVOK)")
        return 1

    if token == "NSW":
        weather_texts.append("No significant weather (NSW)")
        return 1

    return 0


def _format_segment_sentences(
    wind_text: str | None,
    visibility_text: str | None,
    weather_texts: list[str],
    cloud_texts: list[str],
    extra_tokens: list[str],
) -> str:
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
