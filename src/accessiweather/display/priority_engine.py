# src/accessiweather/display/priority_engine.py
"""Priority ordering engine for weather information display."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import WeatherAlerts

# Alert event keywords mapped to categories they affect
ALERT_CATEGORY_MAP = {
    # Heat-related
    "heat": ["temperature", "uv_index"],
    "excessive heat": ["temperature", "uv_index"],
    # Wind-related
    "wind": ["wind"],
    "high wind": ["wind"],
    "gale": ["wind"],
    "hurricane": ["wind", "precipitation"],
    "tropical storm": ["wind", "precipitation"],
    "tornado": ["wind"],
    # Precipitation/flood-related
    "flood": ["precipitation"],
    "flash flood": ["precipitation"],
    "rain": ["precipitation"],
    "thunderstorm": ["precipitation", "wind"],
    "severe thunderstorm": ["precipitation", "wind"],
    # Winter-related
    "winter storm": ["precipitation", "temperature"],
    "winter weather": ["precipitation", "temperature"],
    "blizzard": ["precipitation", "temperature", "wind"],
    "ice storm": ["precipitation", "temperature"],
    "freeze": ["temperature"],
    "frost": ["temperature"],
    "cold": ["temperature"],
    "snow": ["precipitation", "temperature"],
    # Visibility-related
    "fog": ["visibility_clouds"],
    "dense fog": ["visibility_clouds"],
    "smoke": ["visibility_clouds"],
}

# Fields per category per verbosity level
CATEGORY_FIELDS = {
    "temperature": {
        "minimal": ["temperature"],
        "standard": ["temperature", "feels_like"],
        "detailed": ["temperature", "feels_like", "dewpoint", "heat_index", "wind_chill"],
    },
    "precipitation": {
        "minimal": ["precipitation_chance"],
        "standard": ["precipitation_chance", "precipitation_amount"],
        "detailed": [
            "precipitation_chance",
            "precipitation_amount",
            "precipitation_type",
            "snowfall",
        ],
    },
    "wind": {
        "minimal": ["wind_speed"],
        "standard": ["wind_speed", "wind_direction"],
        "detailed": ["wind_speed", "wind_direction", "wind_gusts"],
    },
    "humidity_pressure": {
        "minimal": ["humidity"],
        "standard": ["humidity", "pressure"],
        "detailed": ["humidity", "pressure", "pressure_trend"],
    },
    "visibility_clouds": {
        "minimal": [],
        "standard": ["visibility"],
        "detailed": ["visibility", "cloud_cover"],
    },
    "uv_index": {
        "minimal": [],
        "standard": ["uv_index"],
        "detailed": ["uv_index"],
    },
}


class WeatherCategory(Enum):
    """Weather information categories for priority ordering."""

    TEMPERATURE = "temperature"
    PRECIPITATION = "precipitation"
    WIND = "wind"
    HUMIDITY_PRESSURE = "humidity_pressure"
    VISIBILITY_CLOUDS = "visibility_clouds"
    UV_INDEX = "uv_index"

    @classmethod
    def from_string(cls, value: str) -> WeatherCategory:
        """Convert string to WeatherCategory."""
        return cls(value.lower())


class PriorityEngine:
    """Determines display order and field selection for weather information."""

    DEFAULT_ORDER = [
        "temperature",
        "precipitation",
        "wind",
        "humidity_pressure",
        "visibility_clouds",
        "uv_index",
    ]

    def __init__(
        self,
        verbosity_level: str = "standard",
        category_order: list[str] | None = None,
        severe_weather_override: bool = True,
    ):
        """Initialize the priority engine with user preferences."""
        self.verbosity_level = verbosity_level
        self.category_order = category_order or self.DEFAULT_ORDER.copy()
        self.severe_weather_override = severe_weather_override

    def get_category_order(
        self,
        alerts: WeatherAlerts | None = None,
    ) -> list[WeatherCategory]:
        """Get the ordered list of categories based on alerts and preferences."""
        # Start with user's preferred order
        base_order = [WeatherCategory.from_string(cat) for cat in self.category_order]

        # If no alerts or override disabled, return user order
        if not alerts or not self.severe_weather_override:
            return self._ensure_all_categories(base_order)

        # Check for active alerts and adjust order
        active_alerts = alerts.get_active_alerts()
        if not active_alerts:
            return self._ensure_all_categories(base_order)

        # Find categories to prioritize based on alert events
        priority_categories: list[str] = []
        for alert in active_alerts:
            event = (alert.event or alert.title or "").lower()
            for keyword, categories in ALERT_CATEGORY_MAP.items():
                if keyword in event:
                    for cat in categories:
                        if cat not in priority_categories:
                            priority_categories.append(cat)

        if not priority_categories:
            return self._ensure_all_categories(base_order)

        # Build new order: priority categories first, then remaining in user order
        new_order: list[WeatherCategory] = []
        for cat_str in priority_categories:
            cat = WeatherCategory.from_string(cat_str)
            if cat not in new_order:
                new_order.append(cat)

        for cat in base_order:
            if cat not in new_order:
                new_order.append(cat)

        return self._ensure_all_categories(new_order)

    def _ensure_all_categories(self, order: list[WeatherCategory]) -> list[WeatherCategory]:
        """Ensure all categories are present in the order."""
        all_cats = set(WeatherCategory)
        present = set(order)
        missing = all_cats - present
        return order + list(missing)

    def get_fields_for_category(self, category: WeatherCategory) -> list[str]:
        """Get the fields to display for a category based on verbosity."""
        cat_fields = CATEGORY_FIELDS.get(category.value, {})
        return cat_fields.get(self.verbosity_level, cat_fields.get("standard", []))

    def should_include_field(self, category: WeatherCategory, field: str) -> bool:
        """Check if a field should be included based on verbosity."""
        fields = self.get_fields_for_category(category)
        return field in fields
