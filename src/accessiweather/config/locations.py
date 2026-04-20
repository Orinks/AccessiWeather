"""Location-related helpers for configuration management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models import Location

if TYPE_CHECKING:
    from ..services.zone_enrichment_service import ZoneEnrichmentService
    from .config_manager import ConfigManager

logger = logging.getLogger("accessiweather.config")


class LocationOperations:
    """Encapsulate location CRUD operations for the configuration manager."""

    def __init__(
        self,
        manager: ConfigManager,
        *,
        zone_enrichment_service: ZoneEnrichmentService | None = None,
    ) -> None:
        """
        Keep a handle to the orchestrating configuration manager.

        Args:
            manager: The owning :class:`ConfigManager` instance.
            zone_enrichment_service: Optional pre-built enrichment service for
                NWS zone metadata. When ``None``, the service is lazily
                constructed on first use of
                :meth:`add_location_with_enrichment`.

        """
        self._manager = manager
        self._zone_enrichment_service = zone_enrichment_service

    @property
    def logger(self) -> logging.Logger:
        return self._manager._get_logger()

    def add_location(
        self,
        name: str,
        latitude: float,
        longitude: float,
        country_code: str | None = None,
        marine_mode: bool = False,
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
            marine_mode=marine_mode,
        )
        config.locations.append(new_location)

        if config.current_location is None:
            config.current_location = new_location
            self.logger.info(f"Set {name} as current location (first location)")

        self.logger.info(f"Added location: {name} ({latitude}, {longitude})")
        return self._manager.save_config()

    async def add_location_with_enrichment(
        self,
        name: str,
        latitude: float,
        longitude: float,
        country_code: str | None = None,
        marine_mode: bool = False,
    ) -> bool:
        """
        Add a new location, enriching it with NWS zone metadata first.

        For US locations, this fetches ``/points`` once and populates the
        ``timezone``, ``cwa_office``, ``forecast_zone_id``, ``county_zone_id``,
        ``fire_zone_id``, and ``radar_station`` fields before persisting.

        Non-US locations and ``/points`` failures never block the save: in
        those cases the zone fields remain null and the location is still
        saved.
        """
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
            marine_mode=marine_mode,
        )

        try:
            service = self._get_zone_enrichment_service()
            new_location = await service.enrich_location(new_location)
        except Exception as exc:  # noqa: BLE001 - never block save on enrichment
            self.logger.debug("Zone enrichment raised unexpectedly for %s: %s", name, exc)

        config.locations.append(new_location)

        if config.current_location is None:
            config.current_location = new_location
            self.logger.info(f"Set {name} as current location (first location)")

        self.logger.info(f"Added location: {name} ({latitude}, {longitude})")
        return self._manager.save_config()

    def _get_zone_enrichment_service(self) -> ZoneEnrichmentService:
        """Return the injected enrichment service, lazily constructing one."""
        if self._zone_enrichment_service is None:
            from ..services.zone_enrichment_service import ZoneEnrichmentService

            self._zone_enrichment_service = ZoneEnrichmentService()
        return self._zone_enrichment_service

    def update_location_marine_mode(self, name: str, marine_mode: bool) -> bool:
        """Update marine_mode on an existing location and persist it."""
        config = self._manager.get_config()

        for location in config.locations:
            if location.name == name:
                location.marine_mode = marine_mode
                self.logger.info(f"Set marine_mode={marine_mode} on location: {name}")
                return self._manager.save_config()

        self.logger.warning(f"Location {name} not found")
        return False

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

        # Handle Nationwide (injected dynamically, not in config.locations)
        if name == "Nationwide":
            config.current_location = Location(
                name="Nationwide", latitude=39.8283, longitude=-98.5795
            )
            self.logger.info("Set current location: Nationwide")
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
        data_source = getattr(settings, "data_source", "auto")
        # Nationwide only works with NWS-compatible sources
        nationwide_available = show_nationwide and data_source in ("auto", "nws")

        has_nationwide = any(loc.name == "Nationwide" for loc in locations)

        if nationwide_available and not has_nationwide:
            locations.insert(0, Location(name="Nationwide", latitude=39.8283, longitude=-98.5795))
        elif not nationwide_available and has_nationwide:
            locations = [loc for loc in locations if loc.name != "Nationwide"]

        return locations

    def get_location_names(self) -> list[str]:
        """Return the list of configured location names."""
        return [location.name for location in self._manager.get_config().locations]

    def has_locations(self) -> bool:
        """Return True when any locations are configured."""
        return bool(self._manager.get_config().locations)
