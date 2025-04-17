"""Location handling for AccessiWeather

This module handles location storage and retrieval.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from accessiweather.config_utils import get_config_dir

logger = logging.getLogger(__name__)

# Constants
NATIONWIDE_LOCATION_NAME = "Nationwide"
# Center of the contiguous US (approximate)
NATIONWIDE_LAT = 39.8283
NATIONWIDE_LON = -98.5795


class LocationManager:
    """Manager for handling saved locations"""

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the location manager

        Args:
            config_dir: Directory for config files, defaults to user's home directory
        """
        self.config_dir = get_config_dir(config_dir)

        self.locations_file = os.path.join(self.config_dir, "locations.json")
        self.current_location: Optional[str] = None
        self.saved_locations: Dict[str, Dict[str, float]] = {}

        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)

        # Load saved locations
        self._load_locations()

        # Ensure Nationwide location exists
        self._ensure_nationwide_location()

    def _load_locations(self) -> None:
        """Load saved locations from file"""
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
        """Save locations to file"""
        try:
            data = {"locations": self.saved_locations, "current": self.current_location}

            with open(self.locations_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save locations: {str(e)}")

    def add_location(self, name: str, lat: float, lon: float) -> None:
        """Add a new location. Cannot overwrite Nationwide location.

        Args:
            name: Location name
            lat: Latitude
            lon: Longitude
        """
        if name == NATIONWIDE_LOCATION_NAME:
            # Do not allow overwriting Nationwide location
            return
        self.saved_locations[name] = {"lat": lat, "lon": lon}

        # If this is the first location (besides Nationwide), make it current
        if self.current_location is None or self.current_location == NATIONWIDE_LOCATION_NAME:
            self.current_location = name

        self._ensure_nationwide_location()
        self._save_locations()

    def remove_location(self, name: str) -> bool:
        """Remove a location. Cannot remove Nationwide location.

        Args:
            name: Location name to remove

        Returns:
            True if location was removed, False otherwise
        """
        # Prevent removing the Nationwide location
        if name == NATIONWIDE_LOCATION_NAME:
            logger.warning(f"Cannot remove the {NATIONWIDE_LOCATION_NAME} location")
            return False

        if name in self.saved_locations:
            del self.saved_locations[name]

            # If we removed the current location, update it
            if self.current_location == name:
                # Pick a non-Nationwide location if possible
                non_nationwide = [loc for loc in self.saved_locations if loc != NATIONWIDE_LOCATION_NAME]
                if non_nationwide:
                    self.current_location = non_nationwide[0]
                elif NATIONWIDE_LOCATION_NAME in self.saved_locations:
                    self.current_location = NATIONWIDE_LOCATION_NAME
                else:
                    self.current_location = None

            self._ensure_nationwide_location()
            self._save_locations()
            return True

        return False

    def set_current_location(self, name: str) -> bool:
        """Set the current location

        Args:
            name: Location name

        Returns:
            True if successful, False if location doesn't exist
        """
        if name in self.saved_locations:
            self.current_location = name
            self._save_locations()
            return True

        return False

    def get_current_location(self) -> Optional[Tuple[str, float, float]]:
        """Get the current location

        Returns:
            Tuple of (name, lat, lon) if current location exists, None otherwise
        """
        if self.current_location and self.current_location in self.saved_locations:
            loc = self.saved_locations[self.current_location]
            return (self.current_location, loc["lat"], loc["lon"])

        return None

    def get_current_location_name(self) -> Optional[str]:
        """Get the name of the current location

        Returns:
            Name of current location if it exists, None otherwise
        """
        return self.current_location if self.current_location in self.saved_locations else None

    def get_all_locations(self) -> List[str]:
        """Get all saved location names

        Returns:
            List of location names
        """
        return list(self.saved_locations.keys())

    def set_locations(
        self, locations: Dict[str, Dict[str, float]], current: Optional[str] = None
    ) -> None:
        """Set all locations and optionally the current location. Nationwide is always present.

        This is used when initializing from saved config or in tests.

        Args:
            locations: Dictionary of location names to coordinate dictionaries
            current: Current location name (must be in locations dict)
        """
        # Never allow setting locations without Nationwide
        new_locations = dict(locations)
        new_locations[NATIONWIDE_LOCATION_NAME] = {
            "lat": NATIONWIDE_LAT,
            "lon": NATIONWIDE_LON
        }
        self.saved_locations = new_locations

        if current and current in self.saved_locations:
            self.current_location = current
        elif self.saved_locations and not self.current_location:
            # If no current location set but we have locations, set the first non-Nationwide
            non_nationwide = [loc for loc in self.saved_locations if loc != NATIONWIDE_LOCATION_NAME]
            if non_nationwide:
                self.current_location = non_nationwide[0]
            else:
                self.current_location = NATIONWIDE_LOCATION_NAME

        self._ensure_nationwide_location()
        self._save_locations()

    def _ensure_nationwide_location(self) -> None:
        """Ensure the Nationwide location exists in saved locations"""
        if NATIONWIDE_LOCATION_NAME not in self.saved_locations:
            logger.info(f"Adding {NATIONWIDE_LOCATION_NAME} location")
            self.saved_locations[NATIONWIDE_LOCATION_NAME] = {
                "lat": NATIONWIDE_LAT,
                "lon": NATIONWIDE_LON
            }
        # Never remove or overwrite Nationwide; do not save yet (callers will save)

    def is_nationwide_location(self, name: str) -> bool:
        """Check if a location is the Nationwide location

        Args:
            name: Location name to check

        Returns:
            True if the location is the Nationwide location, False otherwise
        """
        return name == NATIONWIDE_LOCATION_NAME
