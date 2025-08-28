"""Alert-to-sound mapping utilities.

This module provides a small, dependency-free mapper that determines which
sound "event" key should be used for a given WeatherAlert. It produces an
ordered list of candidate event keys, allowing the sound system to try the
first available one in the currently selected pack, then gracefully fall back
by severity and finally to generic defaults.
"""

from __future__ import annotations

import re

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

# Canonical alert category keys that can be emitted by the mapper
# These are the keys that sound packs should support and UI should reference
CANONICAL_ALERT_KEYS = [
    # Specific hazard types (from HAZARD_KEYWORDS)
    "flood",
    "tornado",
    "heat",
    "wind",
    "winter",
    "snow",
    "ice",
    "thunderstorm",
    "hurricane",
    "fire",
    "fog",
    "dust",
    "air_quality",
    # Combined hazard + type keys
    "flood_warning",
    "tornado_warning",
    "heat_advisory",
    "wind_warning",
    "winter_storm_warning",
    "snow_warning",
    "ice_warning",
    "thunderstorm_warning",
    "hurricane_warning",
    "fire_warning",
    "fog_advisory",
    "dust_warning",
    "air_quality_alert",
    # Alert types
    "warning",
    "watch",
    "advisory",
    "statement",
    # Severity levels
    "extreme",
    "severe",
    "moderate",
    "minor",
    # Generic fallbacks
    "alert",
    "notify",
]


def _contains_token(text: str | None, token: str) -> bool:
    if not text:
        return False
    return re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE) is not None


def _extract_alert_type(alert: WeatherAlert) -> str | None:
    # Look at event and headline/title for NWS-style type words
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
    # Visual Crossing aliases are already mapped earlier in visual_crossing_client,
    # but accept a few extras just in case.
    alias = {
        "high": "severe",
        "medium": "moderate",
        "low": "minor",
        "critical": "extreme",
    }.get(s)
    return alias if alias in KNOWN_SEVERITY_KEYS else None


HAZARD_KEYWORDS = {
    # core
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


def _extract_hazard(alert: WeatherAlert) -> str | None:
    text = " ".join(
        [
            getattr(alert, "event", "") or "",
            getattr(alert, "headline", "") or "",
            getattr(alert, "title", "") or "",
            getattr(alert, "description", "") or "",
        ]
    ).lower()
    for hazard_key, phrases in HAZARD_KEYWORDS.items():
        for phrase in phrases:
            if phrase in text:
                return hazard_key
    return None


def _normalize_event_to_key(text: str | None) -> str | None:
    """Normalize an alert event/title/headline to a pack key.

    Example: "Excessive Heat Watch" -> "excessive_heat_watch"
    """
    if not text:
        return None
    import re as _re

    s = text.strip().lower()
    # Replace any non-alphanumeric with underscores
    s = _re.sub(r"[^a-z0-9]+", "_", s)
    # Collapse multiple underscores
    s = _re.sub(r"_+", "_", s)
    # Trim leading/trailing underscores
    s = s.strip("_")
    return s or None


def get_candidate_sound_events(alert: WeatherAlert) -> list[str]:
    """Return an ordered list of candidate sound event keys for an alert.

    Order of preference:
    - Exact normalized event key from alert.event (e.g., excessive_heat_watch)
    - Hazard + Type (e.g., flood_warning) if both can be detected
    - Hazard + Severity (e.g., heat_extreme) if detected
    - Hazard only (e.g., flood, heat)
    - Specific alert type (warning/watch/advisory/statement)
    - Severity level (extreme/severe/moderate/minor)
    - Generic fallbacks (alert, notify)
    """
    candidates: list[str] = []

    # Exact normalized event key first
    normalized_event = _normalize_event_to_key(getattr(alert, "event", None))
    if normalized_event:
        candidates.append(normalized_event)

    atype = _extract_alert_type(alert)
    sev = _normalize_severity(getattr(alert, "severity", None))
    hazard = _extract_hazard(alert)

    # Hazard combinations next
    if hazard and atype:
        candidates.append(f"{hazard}_{atype}")
    if hazard and sev:
        key = f"{hazard}_{sev}"
        if key not in candidates:
            candidates.append(key)
    if hazard and hazard not in candidates:
        candidates.append(hazard)

    # Then type and severity
    if atype and atype not in candidates:
        candidates.append(atype)
    if sev and sev not in candidates:
        candidates.append(sev)

    for fb in GENERIC_FALLBACKS:
        if fb not in candidates:
            candidates.append(fb)

    return candidates


def choose_sound_event(alert: WeatherAlert) -> str:
    """Return the preferred sound event key for this alert (first candidate)."""
    return get_candidate_sound_events(alert)[0]
