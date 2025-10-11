"""Weather history tracking and comparison functionality.

This module provides functionality to track weather history over time,
allowing users to compare current weather conditions with past observations.
Designed with accessibility in mind for screen reader users.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CurrentConditions, Location

logger = logging.getLogger(__name__)


@dataclass
class WeatherHistoryEntry:
    """A single weather history entry for a specific time and location."""

    location_name: str
    temperature: float
    condition: str
    humidity: int
    wind_speed: float
    wind_direction: str
    pressure: float
    timestamp: datetime

    @classmethod
    def from_current_conditions(
        cls,
        location: Location,
        conditions: CurrentConditions,
        timestamp: datetime | None = None,
    ) -> WeatherHistoryEntry:
        """Create a history entry from current conditions.

        Args:
            location: The location for this entry
            conditions: Current weather conditions
            timestamp: Optional timestamp (defaults to now)

        Returns:
            A new WeatherHistoryEntry instance

        """
        if timestamp is None:
            timestamp = datetime.now()

        return cls(
            location_name=location.name,
            temperature=conditions.temperature,
            condition=conditions.condition,
            humidity=conditions.humidity,
            wind_speed=conditions.wind_speed,
            wind_direction=conditions.wind_direction,
            pressure=conditions.pressure,
            timestamp=timestamp,
        )

    def to_dict(self) -> dict:
        """Convert entry to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the entry

        """
        data = asdict(self)
        # Convert datetime to ISO format string
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> WeatherHistoryEntry:
        """Create entry from dictionary.

        Args:
            data: Dictionary containing entry data

        Returns:
            A new WeatherHistoryEntry instance

        """
        # Parse timestamp from ISO format
        timestamp_str = data.get("timestamp", "")
        if isinstance(timestamp_str, str):
            timestamp = datetime.fromisoformat(timestamp_str)
        else:
            timestamp = datetime.now()

        return cls(
            location_name=data.get("location_name", ""),
            temperature=float(data.get("temperature", 0.0)),
            condition=data.get("condition", ""),
            humidity=int(data.get("humidity", 0)),
            wind_speed=float(data.get("wind_speed", 0.0)),
            wind_direction=data.get("wind_direction", ""),
            pressure=float(data.get("pressure", 0.0)),
            timestamp=timestamp,
        )


@dataclass
class WeatherComparison:
    """Comparison between current weather and a historical entry."""

    temperature_difference: float
    temperature_description: str
    condition_changed: bool
    previous_condition: str
    condition_description: str | None
    humidity_difference: int
    wind_speed_difference: float
    days_ago: int

    @classmethod
    def compare(
        cls,
        current: CurrentConditions,
        previous: WeatherHistoryEntry,
    ) -> WeatherComparison:
        """Compare current conditions with a historical entry.

        Args:
            current: Current weather conditions
            previous: Historical weather entry to compare against

        Returns:
            A WeatherComparison instance with comparison details

        """
        # Calculate temperature difference
        temp_diff = current.temperature - previous.temperature

        # Generate temperature description
        if abs(temp_diff) < 1.0:
            temp_desc = "about the same temperature"
        elif temp_diff > 0:
            temp_desc = f"{abs(temp_diff):.1f} degrees warmer"
        else:
            temp_desc = f"{abs(temp_diff):.1f} degrees cooler"

        # Check condition change
        condition_changed = current.condition != previous.condition
        condition_desc = None
        if condition_changed:
            condition_desc = f"Changed from {previous.condition} to {current.condition}"

        # Calculate other differences
        humidity_diff = current.humidity - previous.humidity
        wind_diff = current.wind_speed - previous.wind_speed

        # Calculate days ago
        days_ago = (datetime.now() - previous.timestamp).days

        return cls(
            temperature_difference=temp_diff,
            temperature_description=temp_desc,
            condition_changed=condition_changed,
            previous_condition=previous.condition,
            condition_description=condition_desc,
            humidity_difference=humidity_diff,
            wind_speed_difference=wind_diff,
            days_ago=days_ago,
        )

    def get_accessible_summary(self) -> str:
        """Generate a screen-reader friendly summary of the comparison.

        Returns:
            A human-readable summary of weather changes

        """
        parts = []

        # Temperature summary
        if self.days_ago == 1:
            time_ref = "yesterday"
        elif self.days_ago == 7:
            time_ref = "last week"
        else:
            time_ref = f"{self.days_ago} days ago"

        parts.append(f"Compared to {time_ref}: {self.temperature_description}")

        # Condition summary
        if self.condition_changed and self.condition_description:
            parts.append(self.condition_description)

        # Humidity change if significant
        if abs(self.humidity_difference) >= 10:
            if self.humidity_difference > 0:
                parts.append(f"Humidity increased by {self.humidity_difference} percent")
            else:
                parts.append(f"Humidity decreased by {abs(self.humidity_difference)} percent")

        # Wind change if significant
        if abs(self.wind_speed_difference) >= 5.0:
            if self.wind_speed_difference > 0:
                parts.append(
                    f"Wind speed increased by {self.wind_speed_difference:.1f} miles per hour"
                )
            else:
                parts.append(
                    f"Wind speed decreased by {abs(self.wind_speed_difference):.1f} miles per hour"
                )

        return ". ".join(parts) + "."


class WeatherHistoryTracker:
    """Tracks and manages weather history over time."""

    def __init__(self, history_file: str, max_days: int = 30):
        """Initialize the weather history tracker.

        Args:
            history_file: Path to the JSON file for storing history
            max_days: Maximum number of days to retain history (default: 30)

        """
        self.history_file = history_file
        self.max_days = max_days
        self.history: list[WeatherHistoryEntry] = []

        # Try to load existing history
        self.load()

    def add_entry(
        self,
        location: Location,
        conditions: CurrentConditions,
        timestamp: datetime | None = None,
    ) -> None:
        """Add a new weather history entry.

        Args:
            location: Location for this entry
            conditions: Current weather conditions
            timestamp: Optional timestamp (defaults to now)

        """
        entry = WeatherHistoryEntry.from_current_conditions(
            location=location,
            conditions=conditions,
            timestamp=timestamp,
        )

        self.history.append(entry)
        logger.debug(f"Added weather history entry for {location.name} at {entry.timestamp}")

    def save(self) -> None:
        """Save weather history to file."""
        try:
            # Ensure directory exists
            path = Path(self.history_file)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Convert entries to dictionaries
            data = {
                "version": "1.0",
                "entries": [entry.to_dict() for entry in self.history],
            }

            # Write to file
            with open(self.history_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self.history)} weather history entries")

        except Exception as e:
            logger.error(f"Failed to save weather history: {e}")

    def load(self) -> None:
        """Load weather history from file."""
        try:
            if not Path(self.history_file).exists():
                logger.debug("No existing weather history file found")
                return

            with open(self.history_file) as f:
                data = json.load(f)

            # Load entries
            entries = data.get("entries", [])
            self.history = [WeatherHistoryEntry.from_dict(entry) for entry in entries]

            logger.info(f"Loaded {len(self.history)} weather history entries")

            # Cleanup old entries after loading
            self.cleanup_old_entries()

        except Exception as e:
            logger.error(f"Failed to load weather history: {e}")
            self.history = []

    def get_entry_for_location_and_day(
        self,
        location_name: str,
        target_date: date,
    ) -> WeatherHistoryEntry | None:
        """Get the most recent entry for a location on a specific day.

        Args:
            location_name: Name of the location
            target_date: Target date to search for

        Returns:
            The most recent entry for that day, or None if not found

        """
        matching_entries = [
            entry
            for entry in self.history
            if entry.location_name == location_name and entry.timestamp.date() == target_date
        ]

        if not matching_entries:
            return None

        # Return the most recent entry from that day
        return max(matching_entries, key=lambda e: e.timestamp)

    def cleanup_old_entries(self) -> None:
        """Remove entries older than max_days."""
        cutoff_date = datetime.now() - timedelta(days=self.max_days)

        initial_count = len(self.history)
        self.history = [entry for entry in self.history if entry.timestamp >= cutoff_date]

        removed_count = initial_count - len(self.history)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} old weather history entries")

    def get_comparison_for_yesterday(
        self,
        location_name: str,
        current_conditions: CurrentConditions,
    ) -> WeatherComparison | None:
        """Get comparison with yesterday's weather.

        Args:
            location_name: Name of the location
            current_conditions: Current weather conditions

        Returns:
            WeatherComparison if yesterday's data exists, None otherwise

        """
        yesterday = (datetime.now() - timedelta(days=1)).date()
        yesterday_entry = self.get_entry_for_location_and_day(location_name, yesterday)

        if yesterday_entry is None:
            return None

        return WeatherComparison.compare(current_conditions, yesterday_entry)

    def get_comparison_for_last_week(
        self,
        location_name: str,
        current_conditions: CurrentConditions,
    ) -> WeatherComparison | None:
        """Get comparison with weather from one week ago.

        Args:
            location_name: Name of the location
            current_conditions: Current weather conditions

        Returns:
            WeatherComparison if last week's data exists, None otherwise

        """
        last_week = (datetime.now() - timedelta(days=7)).date()
        last_week_entry = self.get_entry_for_location_and_day(location_name, last_week)

        if last_week_entry is None:
            return None

        return WeatherComparison.compare(current_conditions, last_week_entry)
