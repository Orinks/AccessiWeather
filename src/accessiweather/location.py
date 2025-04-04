"""Location management for AccessiWeather.

This module handles location data storage and retrieval.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Location:
    """A class representing a weather location."""

    def __init__(self, name: str, lat: float, lon: float):
        """Initialize a location.

        Args:
            name: Location name
            lat: Latitude
            lon: Longitude
        """
        self.name = name
        self.lat = lat
        self.lon = lon

    def to_dict(self) -> Dict[str, Any]:
        """Convert location to dictionary.

        Returns:
            Dictionary representation of location
        """
        return {"name": self.name, "lat": self.lat, "lon": self.lon}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Location":
        """Create location from dictionary.

        Args:
            data: Dictionary containing location data

        Returns:
            Location instance
        """
        return cls(data["name"], data["lat"], data["lon"])


class LocationManager:
    """Manages saved weather locations."""

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize location manager.

        Args:
            config_dir: Optional configuration directory path
        """
        self.config_dir: str
        """Initialize the location manager

        Args:
            config_dir: Directory for config files, defaults to user's home
                directory
        """
        if config_dir is None:
            self.config_dir = os.path.expanduser("~/.accessiweather")
        else:
            self.config_dir = config_dir

        self.locations_file = os.path.join(self.config_dir, "locations.json")
        self.current_location: Optional[str] = None
        self.saved_locations: Dict[str, Dict[str, float]] = {}

        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)

        # Load saved locations
        self._load_locations()

    def _load_locations(self) -> None:
        """Load saved locations from file."""
        try:
            if os.path.exists(self.locations_file):
                with open(self.locations_file, "r") as f:
                    data = json.load(f)
                    self.saved_locations = data.get("locations", {})

                    # Set current location if available
                    current = data.get("current")
                    if current and current in self.saved_locations:
                        self.current_location = current
        except Exception as e:
            logger.error(f"Failed to load locations: {str(e)}")
            self.saved_locations = {}
            self.current_location = None

    def _save_locations(self) -> None:
        """Save locations to file."""
        try:
            data = {
                "locations": self.saved_locations,
                "current": self.current_location,
            }

            with open(self.locations_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save locations: {str(e)}")

    def add_location(self, name: str, lat: float, lon: float) -> None:
        """Add a new location.

        Args:
            name: Location name
            lat: Latitude
            lon: Longitude
        """
        self.saved_locations[name] = {"lat": lat, "lon": lon}

        # If this is the first location, make it current
        if self.current_location is None:
            self.current_location = name

        self._save_locations()

    def remove_location(self, name: str) -> None:
        """Remove a location.

        Args:
            name: Location name
        """
        if name in self.saved_locations:
            del self.saved_locations[name]

            # If we removed the current location, update it
            if self.current_location == name:
                # Get the first key if locations exist, otherwise None
                self.current_location = next(iter(self.saved_locations), None)

            self._save_locations()

    def get_location(self, name: str) -> Optional[Location]:
        """Get a location by name.

        Args:
            name: Location name

        Returns:
            Location if found, None otherwise
        """
        if name in self.saved_locations:
            loc = self.saved_locations[name]
            return Location(name, loc["lat"], loc["lon"])

        return None

    def get_locations(self) -> List[Location]:
        """Get all saved locations.

        Returns:
            List of locations
        """
        return [
            Location(name, loc["lat"], loc["lon"]) for name, loc in self.saved_locations.items()
        ]

    def get_location_names(self) -> List[str]:
        """Get names of all saved locations.

        Returns:
            List of location names
        """
        return list(self.saved_locations.keys())

    def save_locations(self) -> None:
        """Save locations to disk."""
        self._save_locations()

    def load_locations(self) -> None:
        """Load locations from disk."""
        self._load_locations()
