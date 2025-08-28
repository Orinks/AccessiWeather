from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlertCategoryItem:
    """Data class for alert category selection items."""

    display_name: str
    technical_key: str

    def __str__(self) -> str:  # Shown by Selection and debug; only show friendly name
        return self.display_name

    def __repr__(self) -> str:  # Prevent noisy reprs in lists/debug UIs
        return f"{self.display_name}"


# Friendly alert categories for mapping (display name, technical key)
# Updated to match canonical keys from alert_sound_mapper
FRIENDLY_ALERT_CATEGORIES: list[tuple[str, str]] = [
    ("Tornado Warnings", "tornado_warning"),
    ("Flood Warnings", "flood_warning"),
    ("Heat Advisories", "heat_advisory"),
    ("Thunderstorm Warnings", "thunderstorm_warning"),
    ("Winter Storm Warnings", "winter_storm_warning"),
    ("Hurricane Warnings", "hurricane_warning"),
    ("Wind Warnings", "wind_warning"),
    ("Fire Weather Warnings", "fire_warning"),
    ("Air Quality Alerts", "air_quality_alert"),
    ("Fog Advisories", "fog_advisory"),
    ("Ice Warnings", "ice_warning"),
    ("Snow Warnings", "snow_warning"),
    ("Dust Warnings", "dust_warning"),
    ("Generic Warning", "warning"),
    ("Generic Watch", "watch"),
    ("Generic Advisory", "advisory"),
    ("Generic Statement", "statement"),
    ("General Alert", "alert"),
    ("General Notification", "notify"),
]
