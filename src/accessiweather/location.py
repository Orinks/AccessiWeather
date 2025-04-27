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

    def __init__(self, config_dir: Optional[str] = None, show_nationwide: bool = True):
        """Initialize the location manager

        Args:
            config_dir: Directory for config files, defaults to user's home directory
            show_nationwide: Whether to show the Nationwide location
        """
        self.config_dir = get_config_dir(config_dir)
        self.show_nationwide = show_nationwide

        self.locations_file = os.path.join(self.config_dir, "locations.json")
        self.current_location: Optional[str] = None
        self.saved_locations: Dict[str, Dict[str, float]] = {}

        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)

        # Load saved locations
        self._load_locations()

        # Ensure Nationwide location exists if enabled
        if self.show_nationwide:
            self._ensure_nationwide_location()
            # Only save locations if the file already exists
            # This prevents creating a locations file with just Nationwide on first run
            if os.path.exists(self.locations_file):
                self._save_locations()

    def _load_locations(self) -> None:
        """Load saved locations from file"""
        try:
            if os.path.exists(self.locations_file):
                with open(self.locations_file, "r") as f:
                    data = json.load(f)

                    # If show_nationwide is False, filter out the Nationwide location
                    locations = data.get("locations", {})
                    if not self.show_nationwide and NATIONWIDE_LOCATION_NAME in locations:
                        del locations[NATIONWIDE_LOCATION_NAME]

                    self.saved_locations = locations

                    # Set current location if available
                    current = data.get("current")
                    if current and current in self.saved_locations:
                        self.current_location = current
                    elif not self.show_nationwide and current == NATIONWIDE_LOCATION_NAME:
                        # If current location was Nationwide but it's hidden now,
                        # try to set another location as current
                        non_nationwide = [loc for loc in self.saved_locations.keys()]
                        if non_nationwide:
                            self.current_location = non_nationwide[0]
                        else:
                            self.current_location = None
        except Exception as e:
            logger.error(f"Failed to load locations: {str(e)}")
            self.saved_locations = {}
            self.current_location = None

    def _save_locations(self) -> None:
        """Save locations to file"""
        try:
            # When saving, always include Nationwide location
            locations_to_save = dict(self.saved_locations)
            if NATIONWIDE_LOCATION_NAME not in locations_to_save:
                locations_to_save[NATIONWIDE_LOCATION_NAME] = {
                    "lat": NATIONWIDE_LAT,
                    "lon": NATIONWIDE_LON,
                }

            data = {"locations": locations_to_save, "current": self.current_location}

            # Only save if we have more than just the Nationwide location
            # or if the file already exists
            if len(locations_to_save) > 1 or os.path.exists(self.locations_file):
                with open(self.locations_file, "w") as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save locations: {str(e)}")

    def set_locations(
        self, locations: Dict[str, Dict[str, float]], current: Optional[str] = None
    ) -> None:
        """Set all locations and optionally the current location.

        This is used when initializing from saved config or in tests.

        Args:
            locations: Dictionary of location names to coordinate dictionaries
            current: Current location name (must be in locations dict)
        """
        # Start with provided locations
        new_locations = dict(locations)

        # Always ensure Nationwide exists in the saved data
        if NATIONWIDE_LOCATION_NAME not in new_locations:
            new_locations[NATIONWIDE_LOCATION_NAME] = {"lat": NATIONWIDE_LAT, "lon": NATIONWIDE_LON}

        # If show_nationwide is False, remove it from the working set
        if not self.show_nationwide:
            if NATIONWIDE_LOCATION_NAME in new_locations:
                del new_locations[NATIONWIDE_LOCATION_NAME]

        self.saved_locations = new_locations

        # Handle current location setting
        if current and current in self.saved_locations:
            self.current_location = current
        elif self.saved_locations and not self.current_location:
            # If no current location set but we have locations, set appropriately
            if self.show_nationwide:
                self.current_location = NATIONWIDE_LOCATION_NAME
            else:
                non_nationwide = [
                    loc for loc in self.saved_locations.keys() if loc != NATIONWIDE_LOCATION_NAME
                ]
                if non_nationwide:
                    self.current_location = non_nationwide[0]
                else:
                    self.current_location = None

        self._save_locations()

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
                # Try to set to another non-Nationwide location first
                non_nationwide = [
                    loc for loc in self.saved_locations if loc != NATIONWIDE_LOCATION_NAME
                ]
                if non_nationwide:
                    self.current_location = non_nationwide[0]
                else:
                    self.current_location = NATIONWIDE_LOCATION_NAME

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
        if self.show_nationwide:
            return list(self.saved_locations.keys())
        else:
            return [loc for loc in self.saved_locations.keys() if loc != NATIONWIDE_LOCATION_NAME]

    def _ensure_nationwide_location(self) -> None:
        """Ensure the Nationwide location exists in saved locations"""
        if NATIONWIDE_LOCATION_NAME not in self.saved_locations:
            logger.info(f"Adding {NATIONWIDE_LOCATION_NAME} location")
            self.saved_locations[NATIONWIDE_LOCATION_NAME] = {
                "lat": NATIONWIDE_LAT,
                "lon": NATIONWIDE_LON,
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

    def set_show_nationwide(self, show: bool) -> None:
        """Set whether to show the Nationwide location

        Args:
            show: Whether to show the Nationwide location
        """
        self.show_nationwide = show
        if show:
            self._ensure_nationwide_location()
            self._save_locations()
        elif NATIONWIDE_LOCATION_NAME in self.saved_locations:
            # If current location is Nationwide, switch to another location
            if self.current_location == NATIONWIDE_LOCATION_NAME:
                non_nationwide = [
                    loc for loc in self.saved_locations.keys() if loc != NATIONWIDE_LOCATION_NAME
                ]
                if non_nationwide:
                    self.current_location = non_nationwide[0]
                else:
                    self.current_location = None
            # Don't actually remove Nationwide, just don't show it
            self._save_locations()
