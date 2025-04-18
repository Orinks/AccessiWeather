"""Location service for AccessiWeather.

This module provides a service layer for location-related operations,
separating business logic from UI concerns.
"""

import logging
from typing import Dict, List, Optional, Tuple

from accessiweather.location import LocationManager

logger = logging.getLogger(__name__)


class LocationService:
    """Service for location-related operations."""

    def __init__(self, location_manager: LocationManager):
        """Initialize the location service.

        Args:
            location_manager: The location manager to use for location operations.
        """
        self.location_manager = location_manager

    def get_current_location(self) -> Optional[Tuple[str, float, float]]:
        """Get the current location.

        Returns:
            Tuple of (name, lat, lon) or None if no current location.
        """
        return self.location_manager.get_current_location()

    def get_current_location_name(self) -> Optional[str]:
        """Get the name of the current location.

        Returns:
            Name of the current location or None if no current location.
        """
        return self.location_manager.get_current_location_name()

    def get_all_locations(self) -> List[str]:
        """Get all saved locations.

        Returns:
            List of location names.
        """
        return self.location_manager.get_all_locations()

    def add_location(self, name: str, lat: float, lon: float) -> None:
        """Add a new location.

        Args:
            name: Name of the location.
            lat: Latitude of the location.
            lon: Longitude of the location.
        """
        logger.info(f"Adding location: {name} ({lat}, {lon})")
        self.location_manager.add_location(name, lat, lon)

    def remove_location(self, name: str) -> None:
        """Remove a location.

        Args:
            name: Name of the location to remove.
        """
        logger.info(f"Removing location: {name}")
        self.location_manager.remove_location(name)

    def set_current_location(self, name: str) -> None:
        """Set the current location.

        Args:
            name: Name of the location to set as current.
        """
        logger.info(f"Setting current location: {name}")
        self.location_manager.set_current_location(name)

    def get_location_coordinates(self, name: str) -> Optional[Tuple[float, float]]:
        """Get the coordinates for a location.

        Args:
            name: Name of the location.

        Returns:
            Tuple of (lat, lon) or None if location not found.
        """
        # Get all locations from the location manager
        locations = self.location_manager.saved_locations
        if name in locations:
            loc = locations[name]
            return (loc["lat"], loc["lon"])
        return None

    def get_nationwide_location(self) -> tuple:
        """Return the Nationwide location's name and coordinates."""
        from accessiweather.location import NATIONWIDE_LOCATION_NAME, NATIONWIDE_LAT, NATIONWIDE_LON
        return (NATIONWIDE_LOCATION_NAME, NATIONWIDE_LAT, NATIONWIDE_LON)

    def is_nationwide_location(self, name: str) -> bool:
        """Check if a location is the Nationwide location.

        Args:
            name: Name of the location to check.

        Returns:
            True if the location is the Nationwide location, False otherwise.
        """
        return self.location_manager.is_nationwide_location(name)
