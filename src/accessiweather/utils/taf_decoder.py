"""Utilities for decoding Terminal Aerodrome Forecast (TAF) text."""

from __future__ import annotations

import logging

from .taf_elements import (
    _decode_cloud,
    _decode_visibility,
    _decode_weather,
    _decode_wind,
    _infer_unknown_precipitation_label,
)
from .taf_segments import (
    _decode_tokens,
    _describe_segment,
    _format_header_only,
    _segment_intro,
    _split_segments,
)
from .taf_time import _format_day, _format_from_time, _format_issue_time, _format_time_range

logger = logging.getLogger(__name__)


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


__all__ = [
    "_decode_cloud",
    "_decode_visibility",
    "_decode_weather",
    "_decode_wind",
    "_describe_segment",
    "_format_day",
    "_format_from_time",
    "_format_header_only",
    "_format_issue_time",
    "_format_time_range",
    "_infer_unknown_precipitation_label",
    "_segment_intro",
    "_split_segments",
    "decode_taf_text",
]
