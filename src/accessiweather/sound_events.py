"""Shared user-facing sound event metadata."""

from __future__ import annotations

from collections.abc import Collection
from itertools import chain

DEFAULT_MUTED_SOUND_EVENTS: tuple[str, ...] = ("data_updated",)

SOUND_EVENT_SECTIONS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Core notifications",
        "General app sounds.",
        (
            ("alert", "General alert"),
            ("notify", "General notification"),
            ("error", "General error"),
            ("success", "General success"),
            ("data_updated", "Weather refresh completed"),
            ("fetch_error", "Weather refresh failed"),
            ("discussion_update", "Forecast discussion updated"),
            ("severe_risk", "Severe weather risk changed"),
        ),
    ),
    (
        "App lifecycle",
        "Startup and exit sounds.",
        (
            ("startup", "App startup"),
            ("exit", "App exit"),
        ),
    ),
    (
        "Alert severities",
        "Weather alert sounds by severity.",
        (
            ("extreme", "Extreme severity"),
            ("severe", "Severe severity"),
            ("moderate", "Moderate severity"),
            ("minor", "Minor severity"),
        ),
    ),
)

LEGACY_SOUND_EVENT_KEYS: frozenset[str] = frozenset(
    {
        "warning",
        "watch",
        "advisory",
        "statement",
        "tornado_warning",
        "tornado_watch",
        "thunderstorm_warning",
        "thunderstorm_watch",
        "flood_warning",
        "flood_watch",
        "flood_advisory",
        "flash_flood_warning",
        "flash_flood_watch",
        "coastal_flood_warning",
        "coastal_flood_watch",
        "coastal_flood_advisory",
        "river_flood_warning",
        "river_flood_watch",
        "excessive_heat_warning",
        "excessive_heat_watch",
        "heat_advisory",
        "winter_storm_warning",
        "winter_storm_watch",
        "winter_weather_advisory",
        "blizzard_warning",
        "ice_storm_warning",
        "ice_warning",
        "snow_warning",
        "snow_squall_warning",
        "freeze_warning",
        "freeze_watch",
        "frost_advisory",
        "extreme_cold_warning",
        "cold_weather_advisory",
        "high_wind_warning",
        "high_wind_watch",
        "wind_advisory",
        "wind_warning",
        "extreme_wind_warning",
        "hurricane_warning",
        "hurricane_watch",
        "tropical_storm_warning",
        "tropical_storm_watch",
        "storm_surge_warning",
        "storm_surge_watch",
        "red_flag_warning",
        "fire_weather_watch",
        "fire_warning",
        "small_craft_advisory",
        "gale_warning",
        "storm_warning",
        "hurricane_force_wind_warning",
        "special_marine_warning",
        "dense_fog_advisory",
        "fog_advisory",
        "air_quality_alert",
        "dust_storm_warning",
        "dust_advisory",
        "dust_warning",
        "tornado",
        "flood",
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
    }
)

USER_MUTABLE_SOUND_EVENTS: tuple[tuple[str, str], ...] = tuple(
    chain.from_iterable(
        section_events for _title, _description, section_events in SOUND_EVENT_SECTIONS
    )
)

USER_MUTABLE_SOUND_EVENT_KEYS: frozenset[str] = frozenset(
    event_key for event_key, _label in USER_MUTABLE_SOUND_EVENTS
)

KNOWN_SOUND_EVENT_KEYS: frozenset[str] = USER_MUTABLE_SOUND_EVENT_KEYS | LEGACY_SOUND_EVENT_KEYS

FRIENDLY_SOUND_EVENT_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (label, event_key) for event_key, label in USER_MUTABLE_SOUND_EVENTS
)


def normalize_muted_sound_events(events: Collection[str] | None) -> list[str]:
    """Normalize muted event names while preserving order."""
    if not events:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in events:
        event = str(item).strip()
        if not event or event in seen:
            continue
        seen.add(event)
        normalized.append(event)
    return normalized


def normalize_known_muted_sound_events(events: Collection[str] | None) -> list[str]:
    """Normalize muted events and drop unknown keys from the shared catalog."""
    return [
        event for event in normalize_muted_sound_events(events) if event in KNOWN_SOUND_EVENT_KEYS
    ]
