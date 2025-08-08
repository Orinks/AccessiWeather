"""Alert-to-sound mapping utilities.

This module provides a small, dependency-free mapper that determines which
sound "event" key should be used for a given WeatherAlert. It produces an
ordered list of candidate event keys, allowing the sound system to try the
first available one in the currently selected pack, then gracefully fall back
by severity and finally to generic defaults.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from ..models import WeatherAlert

# Normalized keys we may support in sound packs.
# Packs remain simple JSON dictionaries of event->filename.
# We don't require all keys; missing keys are skipped with fallback.
KNOWN_ALERT_TYPE_KEYS = [
    "warning",
    "watch",
    "advisory",
    "statement",
]

KNOWN_SEVERITY_KEYS = [
    "extreme",
    "severe",
    "moderate",
    "minor",
]

# Ultimate fallbacks for weather alerts
GENERIC_FALLBACKS = ["alert", "notify"]


def _contains_token(text: str | None, token: str) -> bool:
    if not text:
        return False
    return re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE) is not None


def _extract_alert_type(alert: WeatherAlert) -> str | None:
    # Look at event and headline/title for NWS-style type words
    for key in KNOWN_ALERT_TYPE_KEYS:
        if _contains_token(alert.event, key) or _contains_token(alert.headline, key) or _contains_token(alert.title, key):
            return key
    return None


def _normalize_severity(sev: str | None) -> str | None:
    if not sev:
        return None
    s = sev.strip().lower()
    if s in KNOWN_SEVERITY_KEYS:
        return s
    # Visual Crossing aliases are already mapped earlier in visual_crossing_client,
    # but accept a few extras just in case.
    alias = {
        "high": "severe",
        "medium": "moderate",
        "low": "minor",
        "critical": "extreme",
    }.get(s)
    return alias if alias in KNOWN_SEVERITY_KEYS else None


def get_candidate_sound_events(alert: WeatherAlert) -> List[str]:
    """Return an ordered list of candidate sound event keys for an alert.

    Order of preference:
    - Specific alert type (warning/watch/advisory/statement) if detected
    - Severity level (extreme/severe/moderate/minor)
    - Generic fallbacks (alert, notify)
    """
    candidates: list[str] = []

    atype = _extract_alert_type(alert)
    if atype:
        candidates.append(atype)

    sev = _normalize_severity(getattr(alert, "severity", None))
    if sev and sev not in candidates:
        candidates.append(sev)

    for fb in GENERIC_FALLBACKS:
        if fb not in candidates:
            candidates.append(fb)

    return candidates


def choose_sound_event(alert: WeatherAlert) -> str:
    """Return the preferred sound event key for this alert (first candidate)."""
    return get_candidate_sound_events(alert)[0]

