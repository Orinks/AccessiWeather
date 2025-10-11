"""
Location handling for AccessiWeather.

This module handles location storage and retrieval.
"""

import json
import logging
import os

from accessiweather.config_utils import get_config_dir
from accessiweather.geocoding import GeocodingService

logger = logging.getLogger(__name__)

# Constants
NATIONWIDE_LOCATION_NAME = "Nationwide"
# Center of the contiguous US (approximate)
NATIONWIDE_LAT = 39.8283
NATIONWIDE_LON = -98.5795


class LocationManager:
    """Manager for handling saved locations."""

    def __init__(
        self,
        config_dir: str | None = None,
        show_nationwide: bool = True,
        data_source: str = "nws",
    ):
        """
        Initialize the location manager.

        Args:
        ----
            config_dir: Directory for config files, defaults to user's home directory
            show_nationwide: Whether to show the Nationwide location
            data_source: The data source to use ('nws' or 'auto')

        """
        self.config_dir = get_config_dir(config_dir)
        self.show_nationwide = show_nationwide
        self.data_source = data_source

        self.locations_file = os.path.join(self.config_dir, "locations.json")
        self.current_location: str | None = None
        self.saved_locations: dict[str, dict[str, float]] = {}

        # Initialize geocoding service for location validation
        self.geocoding_service = GeocodingService(
            user_agent="AccessiWeather-LocationManager", data_source=data_source
        )

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
        """Load saved locations from file and validate them."""
        try:
            if os.path.exists(self.locations_file):
                with open(self.locations_file) as f:
                    data = json.load(f)

                    # Get locations from file
                    locations = data.get("locations", {})

                    # Track invalid locations for reporting
                    invalid_locations = []

                    # Validate each location (except Nationwide which is always valid)
                    for name, loc_data in list(locations.items()):
                        # Skip validation for Nationwide location
                        if name == NATIONWIDE_LOCATION_NAME:
                            continue

                        lat = loc_data.get("lat")
                        lon = loc_data.get("lon")

                        # Validate coordinates
                        if lat is not None and lon is not None:
                            # Basic validation for all data sources
                            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                                logger.warning(
                                    f"Location '{name}' has coordinates ({lat}, {lon}) "
                                    f"outside valid range. Removing from saved locations."
                                )
                                invalid_locations.append(name)
                                del locations[name]
                            # Validate based on data source (us_only=None will use the data_source)
                            elif not self.geocoding_service.validate_coordinates(
                                lat, lon, us_only=None
                            ):
                                if self.data_source == "nws":
                                    logger.warning(
                                        f"Location '{name}' with coordinates ({lat}, {lon}) "
                                        f"is outside the US NWS coverage area. Removing from saved locations."
                                    )
                                else:
                                    logger.warning(
                                        f"Location '{name}' with coordinates ({lat}, {lon}) "
                                        f"is invalid for the current data source. Removing from saved locations."
                                    )
                                invalid_locations.append(name)
                                del locations[name]
                        else:
                            logger.warning(
                                f"Location '{name}' has invalid coordinates: lat={lat}, lon={lon}. "
                                f"Removing from saved locations."
                            )
                            invalid_locations.append(name)
                            del locations[name]

                    # If any locations were removed, log a summary
                    if invalid_locations:
                        if self.data_source == "nws":
                            logger.info(
                                f"Removed {len(invalid_locations)} location(s) outside the US NWS coverage area: "
                                f"{', '.join(invalid_locations)}"
                            )
                        else:
                            logger.info(
                                f"Removed {len(invalid_locations)} invalid location(s): "
                                f"{', '.join(invalid_locations)}"
                            )

                    # If show_nationwide is False, filter out the Nationwide location
                    if not self.show_nationwide and NATIONWIDE_LOCATION_NAME in locations:
                        del locations[NATIONWIDE_LOCATION_NAME]

                    self.saved_locations = locations

                    # Set current location if available
                    current = data.get("current")

                    # If current location was removed because it was invalid, reset it
                    if current in invalid_locations:
                        logger.info(
                            f"Current location '{current}' was outside the US NWS coverage area. "
                            f"Resetting current location."
                        )
                        current = None

                    if current and current in self.saved_locations:
                        self.current_location = current
                    elif not self.show_nationwide and current == NATIONWIDE_LOCATION_NAME:
                        # If current location was Nationwide but it's hidden now,
                        # try to set another location as current
                        non_nationwide = list(self.saved_locations.keys())
                        if non_nationwide:
                            self.current_location = non_nationwide[0]
                        else:
                            self.current_location = None
                    elif self.saved_locations:
                        # If current location is not valid or was removed, set to first available
                        if self.show_nationwide:
                            self.current_location = NATIONWIDE_LOCATION_NAME
                        else:
                            non_nationwide = [
                                loc
                                for loc in self.saved_locations
                                if loc != NATIONWIDE_LOCATION_NAME
                            ]
                            if non_nationwide:
                                self.current_location = non_nationwide[0]
                            else:
                                self.current_location = None

                    # Save the validated locations back to file
                    if invalid_locations:
                        self._save_locations()

        except Exception as e:
            logger.error(f"Failed to load locations: {str(e)}")
            self.saved_locations = {}
            self.current_location = None

    def _save_locations(self) -> None:
        """Save locations to file."""
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
        self, locations: dict[str, dict[str, float]], current: str | None = None
    ) -> None:
        """
        Set all locations and optionally the current location.

        This is used when initializing from saved config or in tests.

        Args:
        ----
            locations: Dictionary of location names to coordinate dictionaries
            current: Current location name (must be in locations dict)

        """
        # Start with provided locations
        new_locations = dict(locations)

        # Always ensure Nationwide exists in the saved data
        if NATIONWIDE_LOCATION_NAME not in new_locations:
            new_locations[NATIONWIDE_LOCATION_NAME] = {"lat": NATIONWIDE_LAT, "lon": NATIONWIDE_LON}

        # If show_nationwide is False, remove it from the working set
        if not self.show_nationwide and NATIONWIDE_LOCATION_NAME in new_locations:
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
                    loc for loc in self.saved_locations if loc != NATIONWIDE_LOCATION_NAME
                ]
                if non_nationwide:
                    self.current_location = non_nationwide[0]
                else:
                    self.current_location = None

        self._save_locations()

    def add_location(self, name: str, lat: float, lon: float) -> bool:
        """
        Add a new location. Cannot overwrite Nationwide location.

        Validates that the location is within the US NWS coverage area when using NWS data source.
        When using WeatherAPI, allows locations worldwide.

        Args:
        ----
            name: Location name
            lat: Latitude
            lon: Longitude

        Returns:
        -------
            True if location was added successfully, False otherwise

        """
        # Don't allow overwriting Nationwide location
        if name == NATIONWIDE_LOCATION_NAME:
            logger.warning(f"Cannot overwrite the {NATIONWIDE_LOCATION_NAME} location")
            return False

        # Validate coordinates based on data source (us_only=None will use the data_source)
        if not self.geocoding_service.validate_coordinates(lat, lon, us_only=None):
            if self.data_source == "nws":
                logger.warning(
                    f"Cannot add location '{name}' with coordinates ({lat}, {lon}): "
                    f"Location is outside the US NWS coverage area."
                )
            else:
                logger.warning(
                    f"Cannot add location '{name}' with coordinates ({lat}, {lon}): "
                    f"Coordinates are outside valid range."
                )
            return False

        # Add the validated location
        self.saved_locations[name] = {"lat": lat, "lon": lon}

        # If this is the first location (besides Nationwide), make it current
        if self.current_location is None or self.current_location == NATIONWIDE_LOCATION_NAME:
            self.current_location = name

        self._ensure_nationwide_location()
        self._save_locations()
        return True

    def remove_location(self, name: str) -> bool:
        """
        Remove a location. Cannot remove Nationwide location.

        Args:
        ----
            name: Location name to remove

        Returns:
        -------
            True if location was removed, False otherwise

        """
        # Prevent removing the Nationwide location
        if name == NATIONWIDE_LOCATION_NAME:
            logger.warning(f"Cannot remove the {NATIONWIDE_LOCATION_NAME} location")
            return False

        # Log the current state before removal
        logger.debug(f"remove_location: Current locations: {list(self.saved_locations.keys())}")
        logger.debug(f"remove_location: Current location: '{self.current_location}'")
        logger.debug(f"remove_location: Attempting to remove: '{name}'")

        if name in self.saved_locations:
            # Remove the location from saved_locations
            del self.saved_locations[name]
            logger.debug(f"remove_location: Location '{name}' removed from saved_locations")
            logger.debug(
                f"remove_location: Locations after removal: {list(self.saved_locations.keys())}"
            )

            # If we removed the current location, update it
            if self.current_location == name:
                logger.debug("remove_location: Removed current location, need to update it")
                # Try to set to another non-Nationwide location first
                non_nationwide = [
                    loc for loc in self.saved_locations if loc != NATIONWIDE_LOCATION_NAME
                ]
                logger.debug(
                    f"remove_location: Non-nationwide locations available: {non_nationwide}"
                )

                if non_nationwide:
                    self.current_location = non_nationwide[0]
                    logger.debug(f"remove_location: Set current location to '{non_nationwide[0]}'")
                else:
                    self.current_location = NATIONWIDE_LOCATION_NAME
                    logger.debug(
                        f"remove_location: Set current location to '{NATIONWIDE_LOCATION_NAME}'"
                    )

            # Ensure Nationwide location exists
            self._ensure_nationwide_location()

            # Save the updated locations to file
            self._save_locations()
            logger.debug("remove_location: Saved updated locations to file")
            logger.debug(f"remove_location: Final current location: '{self.current_location}'")

            return True
        logger.warning(f"remove_location: Location '{name}' not found in saved_locations")
        return False

    def set_current_location(self, name: str) -> bool:
        """
        Set the current location.

        Args:
        ----
            name: Location name

        Returns:
        -------
            True if successful, False if location doesn't exist

        """
        if name in self.saved_locations:
            self.current_location = name
            self._save_locations()
            return True

        return False

    def update_data_source(self, data_source: str) -> None:
        """
        Update the data source and reinitialize the geocoding service.

        Args:
        ----
            data_source: The new data source to use ('nws' or 'auto')

        """
        logger.info(
            f"Updating LocationManager data source from '{self.data_source}' to '{data_source}'"
        )
        self.data_source = data_source

        # Reinitialize the geocoding service with the new data source
        self.geocoding_service = GeocodingService(
            user_agent="AccessiWeather-LocationManager", data_source=data_source
        )

    def get_current_location(self) -> tuple[str, float, float] | None:
        """
        Get the current location.

        Returns
        -------
            Tuple of (name, lat, lon) if current location exists, None otherwise

        """
        if self.current_location and self.current_location in self.saved_locations:
            loc = self.saved_locations[self.current_location]
            return (self.current_location, loc["lat"], loc["lon"])

        return None

    def get_current_location_name(self) -> str | None:
        """
        Get the name of the current location.

        Returns
        -------
            Name of current location if it exists, None otherwise

        """
        return self.current_location if self.current_location in self.saved_locations else None

    def get_all_locations(self) -> list[str]:
        """
        Get all saved location names.

        Returns
        -------
            List of location names

        """
        if self.show_nationwide:
            return list(self.saved_locations.keys())
        return [loc for loc in self.saved_locations if loc != NATIONWIDE_LOCATION_NAME]

    def _ensure_nationwide_location(self) -> None:
        """Ensure the Nationwide location exists in saved locations."""
        if NATIONWIDE_LOCATION_NAME not in self.saved_locations:
            logger.info(f"Adding {NATIONWIDE_LOCATION_NAME} location")
            self.saved_locations[NATIONWIDE_LOCATION_NAME] = {
                "lat": NATIONWIDE_LAT,
                "lon": NATIONWIDE_LON,
            }
        # Never remove or overwrite Nationwide; do not save yet (callers will save)

    def is_nationwide_location(self, name: str) -> bool:
        """
        Check if a location is the Nationwide location.

        Args:
        ----
            name: Location name to check

        Returns:
        -------
            True if the location is the Nationwide location, False otherwise

        """
        return name == NATIONWIDE_LOCATION_NAME

    def set_show_nationwide(self, show: bool) -> None:
        """
        Set whether to show the Nationwide location.

        Args:
        ----
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
                    loc for loc in self.saved_locations if loc != NATIONWIDE_LOCATION_NAME
                ]
                if non_nationwide:
                    self.current_location = non_nationwide[0]
                else:
                    self.current_location = None
            # Don't actually remove Nationwide, just don't show it
            self._save_locations()
