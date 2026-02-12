"""Location-related helpers for configuration management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models import Location

if TYPE_CHECKING:
    from .config_manager import ConfigManager

logger = logging.getLogger("accessiweather.config")


class LocationOperations:
    """Encapsulate location CRUD operations for the configuration manager."""

    def __init__(self, manager: ConfigManager) -> None:
        """Keep a handle to the orchestrating configuration manager."""
        self._manager = manager

    @property
    def logger(self) -> logging.Logger:
        return self._manager._get_logger()

    def add_location(
        self,
        name: str,
        latitude: float,
        longitude: float,
        country_code: str | None = None,
    ) -> bool:
        """Add a new location if it doesn't already exist."""
        config = self._manager.get_config()

        for existing_location in config.locations:
            if existing_location.name == name:
                self.logger.warning(f"Location {name} already exists")
                return False

        new_location = Location(
            name=name,
            latitude=latitude,
            longitude=longitude,
            country_code=country_code,
        )
        config.locations.append(new_location)

        if config.current_location is None:
            config.current_location = new_location
            self.logger.info(f"Set {name} as current location (first location)")

        self.logger.info(f"Added location: {name} ({latitude}, {longitude})")
        return self._manager.save_config()

    def remove_location(self, name: str) -> bool:
        """Remove a location by name."""
        config = self._manager.get_config()

        for index, location in enumerate(config.locations):
            if location.name == name:
                config.locations.pop(index)

                if config.current_location and config.current_location.name == name:
                    config.current_location = None
                    if config.locations:
                        config.current_location = config.locations[0]
                        self.logger.info(
                            f"Set {config.current_location.name} as new current location"
                        )

                self.logger.info(f"Removed location: {name}")
                return self._manager.save_config()

        self.logger.warning(f"Location {name} not found")
        return False

    def set_current_location(self, name: str) -> bool:
        """Set the current location by name."""
        config = self._manager.get_config()

        for location in config.locations:
            if location.name == name:
                config.current_location = location
                self.logger.info(f"Set current location: {name}")
                return self._manager.save_config()

        self.logger.warning(f"Location {name} not found")
        return False

    def get_current_location(self) -> Location | None:
        """Return the current location if one is set."""
        return self._manager.get_config().current_location

    def get_all_locations(self) -> list[Location]:
        """
        Return a shallow copy of all configured locations.

        If show_nationwide_location is enabled in settings, ensures the
        Nationwide location is included. If disabled, filters it out.
        """
        locations = self._manager.get_config().locations.copy()
        settings = self._manager.get_config().settings
        show_nationwide = getattr(settings, "show_nationwide_location", True)

        has_nationwide = any(loc.name == "Nationwide" for loc in locations)

        if show_nationwide and not has_nationwide:
            locations.insert(0, Location(name="Nationwide", latitude=39.8283, longitude=-98.5795))
        elif not show_nationwide and has_nationwide:
            locations = [loc for loc in locations if loc.name != "Nationwide"]

        return locations

    def get_location_names(self) -> list[str]:
        """Return the list of configured location names."""
        return [location.name for location in self._manager.get_config().locations]

    def has_locations(self) -> bool:
        """Return True when any locations are configured."""
        return bool(self._manager.get_config().locations)
