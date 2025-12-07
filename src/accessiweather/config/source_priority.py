"""Source priority configuration for smart auto source feature."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class SourcePriorityConfig:
    """
    Configuration for data fusion priorities.

    Defines the priority order for selecting data from multiple weather sources
    when merging data in auto mode.
    """

    # Default priorities by location type
    us_default: list[str] = field(default_factory=lambda: ["nws", "openmeteo", "visualcrossing"])
    international_default: list[str] = field(
        default_factory=lambda: ["openmeteo", "visualcrossing"]
    )

    # Per-field overrides (field_name -> priority list)
    field_priorities: dict[str, list[str]] = field(default_factory=dict)

    # Conflict threshold for temperature (°F)
    temperature_conflict_threshold: float = 5.0

    def get_priority(self, field_name: str, is_us: bool) -> list[str]:
        """
        Get priority order for a field.

        Args:
            field_name: The name of the field to get priority for
            is_us: Whether the location is in the US

        Returns:
            List of source names in priority order

        """
        if field_name in self.field_priorities:
            return self.field_priorities[field_name]
        return self.us_default if is_us else self.international_default

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(
            {
                "us_default": self.us_default,
                "international_default": self.international_default,
                "field_priorities": self.field_priorities,
                "temperature_conflict_threshold": self.temperature_conflict_threshold,
            },
            indent=2,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "us_default": self.us_default,
            "international_default": self.international_default,
            "field_priorities": self.field_priorities,
            "temperature_conflict_threshold": self.temperature_conflict_threshold,
        }

    @classmethod
    def from_json(cls, json_str: str) -> SourcePriorityConfig:
        """
        Deserialize from JSON string.

        Args:
            json_str: JSON string representation of the config

        Returns:
            SourcePriorityConfig instance

        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> SourcePriorityConfig:
        """
        Create from dictionary.

        Args:
            data: Dictionary with config values

        Returns:
            SourcePriorityConfig instance

        """
        return cls(
            us_default=data.get("us_default", ["nws", "openmeteo", "visualcrossing"]),
            international_default=data.get(
                "international_default", ["openmeteo", "visualcrossing"]
            ),
            field_priorities=data.get("field_priorities", {}),
            temperature_conflict_threshold=data.get("temperature_conflict_threshold", 5.0),
        )
