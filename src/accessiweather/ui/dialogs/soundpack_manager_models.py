"""Shared sound pack manager models and category metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Alert categories for mapping sounds
# These correspond to keys used by alert_sound_mapper.py for fallback resolution
FRIENDLY_ALERT_CATEGORIES: list[tuple[str, str]] = [
    # Core application sounds
    ("General Alert", "alert"),
    ("General Notification", "notify"),
    ("Error Sound", "error"),
    ("Success Sound", "success"),
    ("App Startup", "startup"),
    ("App Exit", "exit"),
    # Notification events
    ("Forecast Discussion Update", "discussion_update"),
    ("Severe Weather Risk Change", "severe_risk"),
    ("Weather Data Successfully Refreshed", "data_updated"),
    ("Weather Data Fetch Failed", "fetch_error"),
    # ----- Severity-based fallbacks (used when specific event sound not found) -----
    ("Extreme Severity (fallback)", "extreme"),
    ("Severe Severity (fallback)", "severe"),
    ("Moderate Severity (fallback)", "moderate"),
    ("Minor Severity (fallback)", "minor"),
    # ----- Tornado -----
    ("Tornado Warning", "tornado_warning"),
    ("Tornado Watch", "tornado_watch"),
    # ----- Severe Thunderstorm -----
    ("Severe Thunderstorm Warning", "thunderstorm_warning"),
    ("Severe Thunderstorm Watch", "thunderstorm_watch"),
    # ----- Flood -----
    ("Flood Warning", "flood_warning"),
    ("Flood Watch", "flood_watch"),
    ("Flood Advisory", "flood_advisory"),
    ("Flash Flood Warning", "flash_flood_warning"),
    ("Flash Flood Watch", "flash_flood_watch"),
    ("Coastal Flood Warning", "coastal_flood_warning"),
    ("Coastal Flood Watch", "coastal_flood_watch"),
    ("Coastal Flood Advisory", "coastal_flood_advisory"),
    ("River Flood Warning", "river_flood_warning"),
    ("River Flood Watch", "river_flood_watch"),
    # ----- Heat -----
    ("Excessive Heat Warning", "excessive_heat_warning"),
    ("Excessive Heat Watch", "excessive_heat_watch"),
    ("Heat Advisory", "heat_advisory"),
    # ----- Winter / Cold -----
    ("Winter Storm Warning", "winter_storm_warning"),
    ("Winter Storm Watch", "winter_storm_watch"),
    ("Winter Weather Advisory", "winter_weather_advisory"),
    ("Blizzard Warning", "blizzard_warning"),
    ("Ice Storm Warning", "ice_storm_warning"),
    ("Ice Warning (generic)", "ice_warning"),
    ("Snow Warning (generic)", "snow_warning"),
    ("Snow Squall Warning", "snow_squall_warning"),
    ("Freeze Warning", "freeze_warning"),
    ("Freeze Watch", "freeze_watch"),
    ("Frost Advisory", "frost_advisory"),
    ("Extreme Cold Warning", "extreme_cold_warning"),
    ("Cold Weather Advisory", "cold_weather_advisory"),
    # ----- Wind -----
    ("High Wind Warning", "high_wind_warning"),
    ("High Wind Watch", "high_wind_watch"),
    ("Wind Advisory", "wind_advisory"),
    ("Wind Warning (generic)", "wind_warning"),
    ("Extreme Wind Warning", "extreme_wind_warning"),
    # ----- Tropical -----
    ("Hurricane Warning", "hurricane_warning"),
    ("Hurricane Watch", "hurricane_watch"),
    ("Tropical Storm Warning", "tropical_storm_warning"),
    ("Tropical Storm Watch", "tropical_storm_watch"),
    ("Storm Surge Warning", "storm_surge_warning"),
    ("Storm Surge Watch", "storm_surge_watch"),
    # ----- Fire -----
    ("Red Flag Warning", "red_flag_warning"),
    ("Fire Weather Watch", "fire_weather_watch"),
    ("Fire Warning (generic)", "fire_warning"),
    # ----- Marine -----
    ("Small Craft Advisory", "small_craft_advisory"),
    ("Gale Warning", "gale_warning"),
    ("Storm Warning (marine)", "storm_warning"),
    ("Hurricane Force Wind Warning", "hurricane_force_wind_warning"),
    ("Special Marine Warning", "special_marine_warning"),
    # ----- Fog / Visibility -----
    ("Dense Fog Advisory", "dense_fog_advisory"),
    ("Fog Advisory (generic)", "fog_advisory"),
    # ----- Air Quality / Dust -----
    ("Air Quality Alert", "air_quality_alert"),
    ("Dust Storm Warning", "dust_storm_warning"),
    ("Dust Advisory", "dust_advisory"),
    ("Dust Warning (generic)", "dust_warning"),
    # ----- Generic fallbacks (catch-all by alert type) -----
    ("Generic Warning", "warning"),
    ("Generic Watch", "watch"),
    ("Generic Advisory", "advisory"),
    ("Generic Statement", "statement"),
]


@dataclass
class SoundPackInfo:
    """Information about a sound pack."""

    pack_id: str
    name: str
    author: str
    description: str
    path: Path
    sounds: dict[str, str]
