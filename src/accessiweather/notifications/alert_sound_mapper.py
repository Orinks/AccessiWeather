"""
Alert-to-sound mapping utilities.

This module maps weather alerts to sound event keys. The default path is
severity-first so providers do not need exact event text to agree before a
useful sound can play. Users can opt into specific alert sounds, which tries
normalized alert-event keys before the severity fallback.
"""

from __future__ import annotations

import re

from ..models import WeatherAlert

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
    for key in KNOWN_ALERT_TYPE_KEYS:
        if (
            _contains_token(alert.event, key)
            or _contains_token(alert.headline, key)
            or _contains_token(alert.title, key)
        ):
            return key
    return None


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


HAZARD_KEYWORDS = {
    "flood": ["flood"],
    "tornado": ["tornado"],
    "heat": ["heat", "excessive heat"],
    "wind": ["wind", "high wind"],
    "winter": ["winter", "winter storm"],
    "snow": ["snow", "heavy snow"],
    "ice": ["ice", "freezing rain", "freezing drizzle"],
    "thunderstorm": ["thunderstorm", "severe thunderstorm"],
    "hurricane": ["hurricane"],
    "fire": ["fire", "red flag"],
    "fog": ["fog", "dense fog"],
    "dust": ["dust", "blowing dust"],
    "air_quality": ["air quality", "smoke"],
}


def _find_hazard_in_text(text: str) -> str | None:
    text = text.lower()
    for hazard_key, phrases in HAZARD_KEYWORDS.items():
        for phrase in phrases:
            if phrase in text:
                return hazard_key
    return None


def _extract_hazard(alert: WeatherAlert) -> str | None:
    primary_text = " ".join(
        [
            getattr(alert, "event", "") or "",
            getattr(alert, "headline", "") or "",
            getattr(alert, "title", "") or "",
        ]
    )
    description_text = getattr(alert, "description", "") or ""
    return _find_hazard_in_text(primary_text) or _find_hazard_in_text(description_text)


def _normalize_event_to_key(text: str | None) -> str | None:
    """
    Normalize an alert event/title/headline to a pack key.

    Example: "Excessive Heat Watch" -> "excessive_heat_watch"
    """
    if not text:
        return None
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return s or None


def _add_unique(candidates: list[str], key: str | None) -> None:
    if key and key not in candidates:
        candidates.append(key)


def _add_specific_candidates(alert: WeatherAlert, candidates: list[str], sev: str | None) -> None:
    normalized_event = _normalize_event_to_key(getattr(alert, "event", None))
    _add_unique(candidates, normalized_event)

    atype = _extract_alert_type(alert)
    hazard = _extract_hazard(alert)

    if hazard and atype:
        _add_unique(candidates, f"{hazard}_{atype}")
    if hazard and sev:
        _add_unique(candidates, f"{hazard}_{sev}")
    _add_unique(candidates, hazard)
    _add_unique(candidates, atype)


def get_candidate_sound_events(
    alert: WeatherAlert, *, include_specific_events: bool = False
) -> list[str]:
    """
    Return an ordered list of candidate sound event keys for an alert.

    Order of preference:
    - Optional specific alert keys when include_specific_events is true
    - Severity level (extreme/severe/moderate/minor), including provider aliases
    - Generic fallbacks (alert, notify)
    """
    candidates: list[str] = []

    sev = _normalize_severity(getattr(alert, "severity", None))
    if include_specific_events:
        _add_specific_candidates(alert, candidates, sev)

    _add_unique(candidates, sev)

    for fb in GENERIC_FALLBACKS:
        _add_unique(candidates, fb)

    return candidates


def choose_sound_event(alert: WeatherAlert, *, include_specific_events: bool = False) -> str:
    """Return the preferred sound event key for this alert (first candidate)."""
    return get_candidate_sound_events(alert, include_specific_events=include_specific_events)[0]
