"""
Alert-to-sound mapping utilities.

This module maps weather alerts to a compact set of sound event keys. Alert
sounds are intentionally severity-first so providers do not need exact event
text to agree before a useful sound can play.
"""

from __future__ import annotations

from ..models import WeatherAlert

KNOWN_SEVERITY_KEYS = [
    "extreme",
    "severe",
    "moderate",
    "minor",
]

# Ultimate fallbacks for weather alerts
GENERIC_FALLBACKS = ["alert", "notify"]


def _normalize_severity(sev: str | None) -> str | None:
    if not sev:
        return None
    s = sev.strip().lower()
    if s in KNOWN_SEVERITY_KEYS:
        return s
    # Accept common provider aliases in addition to the canonical severity keys.
    alias = {
        "high": "severe",
        "medium": "moderate",
        "low": "minor",
        "critical": "extreme",
    }.get(s)
    return alias if alias in KNOWN_SEVERITY_KEYS else None


def get_candidate_sound_events(alert: WeatherAlert) -> list[str]:
    """
    Return an ordered list of candidate sound event keys for an alert.

    Order of preference:
    - Severity level (extreme/severe/moderate/minor), including provider aliases
    - Generic fallbacks (alert, notify)
    """
    candidates: list[str] = []

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
