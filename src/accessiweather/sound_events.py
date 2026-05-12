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
        "Alert severity fallbacks",
        "Fallbacks by alert severity.",
        (
            ("extreme", "Extreme severity"),
            ("severe", "Severe severity"),
            ("moderate", "Moderate severity"),
            ("minor", "Minor severity"),
        ),
    ),
    (
        "Alert type fallbacks",
        "Fallbacks by alert type.",
        (
            ("warning", "Generic warning"),
            ("watch", "Generic watch"),
            ("advisory", "Generic advisory"),
            ("statement", "Generic statement"),
        ),
    ),
    (
        "Alert events",
        "Specific alert sounds.",
        (
            ("tornado_warning", "Tornado Warning"),
            ("tornado_watch", "Tornado Watch"),
            ("thunderstorm_warning", "Severe Thunderstorm Warning"),
            ("thunderstorm_watch", "Severe Thunderstorm Watch"),
            ("flood_warning", "Flood Warning"),
            ("flood_watch", "Flood Watch"),
            ("flood_advisory", "Flood Advisory"),
            ("flash_flood_warning", "Flash Flood Warning"),
            ("flash_flood_watch", "Flash Flood Watch"),
            ("coastal_flood_warning", "Coastal Flood Warning"),
            ("coastal_flood_watch", "Coastal Flood Watch"),
            ("coastal_flood_advisory", "Coastal Flood Advisory"),
            ("river_flood_warning", "River Flood Warning"),
            ("river_flood_watch", "River Flood Watch"),
            ("excessive_heat_warning", "Excessive Heat Warning"),
            ("excessive_heat_watch", "Excessive Heat Watch"),
            ("heat_advisory", "Heat Advisory"),
            ("winter_storm_warning", "Winter Storm Warning"),
            ("winter_storm_watch", "Winter Storm Watch"),
            ("winter_weather_advisory", "Winter Weather Advisory"),
            ("blizzard_warning", "Blizzard Warning"),
            ("ice_storm_warning", "Ice Storm Warning"),
            ("ice_warning", "Generic ice warning"),
            ("snow_warning", "Generic snow warning"),
            ("snow_squall_warning", "Snow Squall Warning"),
            ("freeze_warning", "Freeze Warning"),
            ("freeze_watch", "Freeze Watch"),
            ("frost_advisory", "Frost Advisory"),
            ("extreme_cold_warning", "Extreme Cold Warning"),
            ("cold_weather_advisory", "Cold Weather Advisory"),
            ("high_wind_warning", "High Wind Warning"),
            ("high_wind_watch", "High Wind Watch"),
            ("wind_advisory", "Wind Advisory"),
            ("wind_warning", "Generic wind warning"),
            ("extreme_wind_warning", "Extreme Wind Warning"),
            ("hurricane_warning", "Hurricane Warning"),
            ("hurricane_watch", "Hurricane Watch"),
            ("tropical_storm_warning", "Tropical Storm Warning"),
            ("tropical_storm_watch", "Tropical Storm Watch"),
            ("storm_surge_warning", "Storm Surge Warning"),
            ("storm_surge_watch", "Storm Surge Watch"),
            ("red_flag_warning", "Red Flag Warning"),
            ("fire_weather_watch", "Fire Weather Watch"),
            ("fire_warning", "Generic fire warning"),
            ("small_craft_advisory", "Small Craft Advisory"),
            ("gale_warning", "Gale Warning"),
            ("storm_warning", "Marine storm warning"),
            ("hurricane_force_wind_warning", "Hurricane Force Wind Warning"),
            ("special_marine_warning", "Special Marine Warning"),
            ("dense_fog_advisory", "Dense Fog Advisory"),
            ("fog_advisory", "Generic fog advisory"),
            ("air_quality_alert", "Air Quality Alert"),
            ("dust_storm_warning", "Dust Storm Warning"),
            ("dust_advisory", "Dust Advisory"),
            ("dust_warning", "Generic dust warning"),
        ),
    ),
)

USER_MUTABLE_SOUND_EVENTS: tuple[tuple[str, str], ...] = tuple(
    chain.from_iterable(
        section_events for _title, _description, section_events in SOUND_EVENT_SECTIONS
    )
)

USER_MUTABLE_SOUND_EVENT_KEYS: frozenset[str] = frozenset(
    event_key for event_key, _label in USER_MUTABLE_SOUND_EVENTS
)

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
        event
        for event in normalize_muted_sound_events(events)
        if event in USER_MUTABLE_SOUND_EVENT_KEYS
    ]
