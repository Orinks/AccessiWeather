"""Simple configuration management for AccessiWeather.

This module provides simple configuration loading and saving using Toga's paths API,
replacing the complex configuration system with straightforward JSON-based storage.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import toga

from .models import AppConfig, AppSettings, Location

logger = logging.getLogger(__name__)


class ConfigManager:
    """Simple configuration manager using Toga paths."""

    def __init__(self, app: toga.App):
        self.app = app
        self.config_file = self.app.paths.config / "accessiweather.json"
        self._config: AppConfig | None = None

        # Ensure config directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Config file path: {self.config_file}")

    def load_config(self) -> AppConfig:
        """Load configuration from file or create default."""
        if self._config is not None:
            return self._config

        try:
            if self.config_file.exists():
                logger.info(f"Loading config from {self.config_file}")
                with open(self.config_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self._config = AppConfig.from_dict(data)
                    logger.info("Configuration loaded successfully")
            else:
                logger.info("No config file found, creating default configuration")
                self._config = AppConfig.default()
                self.save_config()  # Save default config

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            logger.info("Using default configuration")
            self._config = AppConfig.default()

        return self._config

    def save_config(self) -> bool:
        """Save configuration to file."""
        if self._config is None:
            logger.warning("No config to save")
            return False

        try:
            logger.info(f"Saving config to {self.config_file}")
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info("Configuration saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def get_config(self) -> AppConfig:
        """Get current configuration."""
        if self._config is None:
            return self.load_config()
        return self._config

    def update_settings(self, **kwargs) -> bool:
        """Update application settings."""
        config = self.get_config()

        # Update settings attributes
        for key, value in kwargs.items():
            if hasattr(config.settings, key):
                setattr(config.settings, key, value)
                logger.info(f"Updated setting {key} = {value}")
            else:
                logger.warning(f"Unknown setting: {key}")

        return self.save_config()

    def add_location(self, name: str, latitude: float, longitude: float) -> bool:
        """Add a new location."""
        config = self.get_config()

        # Check if location already exists
        for existing_location in config.locations:
            if existing_location.name == name:
                logger.warning(f"Location {name} already exists")
                return False

        # Add new location
        new_location = Location(name=name, latitude=latitude, longitude=longitude)
        config.locations.append(new_location)

        # If this is the first location, make it current
        if config.current_location is None:
            config.current_location = new_location
            logger.info(f"Set {name} as current location (first location)")

        logger.info(f"Added location: {name} ({latitude}, {longitude})")
        return self.save_config()

    def remove_location(self, name: str) -> bool:
        """Remove a location."""
        config = self.get_config()

        # Find and remove location
        for i, location in enumerate(config.locations):
            if location.name == name:
                removed_location = config.locations.pop(i)

                # If this was the current location, clear it
                if config.current_location and config.current_location.name == name:
                    config.current_location = None
                    # Set first remaining location as current if any exist
                    if config.locations:
                        config.current_location = config.locations[0]
                        logger.info(f"Set {config.current_location.name} as new current location")

                logger.info(f"Removed location: {name}")
                return self.save_config()

        logger.warning(f"Location {name} not found")
        return False

    def set_current_location(self, name: str) -> bool:
        """Set the current location."""
        config = self.get_config()

        # Find location
        for location in config.locations:
            if location.name == name:
                config.current_location = location
                logger.info(f"Set current location: {name}")
                return self.save_config()

        logger.warning(f"Location {name} not found")
        return False

    def get_current_location(self) -> Location | None:
        """Get the current location."""
        config = self.get_config()
        return config.current_location

    def get_all_locations(self) -> list[Location]:
        """Get all saved locations."""
        config = self.get_config()
        return config.locations.copy()

    def get_location_names(self) -> list[str]:
        """Get names of all saved locations."""
        config = self.get_config()
        return [location.name for location in config.locations]

    def has_locations(self) -> bool:
        """Check if any locations are saved."""
        config = self.get_config()
        return len(config.locations) > 0

    def get_settings(self) -> AppSettings:
        """Get application settings."""
        config = self.get_config()
        return config.settings

    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults."""
        logger.info("Resetting configuration to defaults")
        self._config = AppConfig.default()
        return self.save_config()

    def backup_config(self, backup_path: Path | None = None) -> bool:
        """Create a backup of the current configuration."""
        if backup_path is None:
            backup_path = self.config_file.with_suffix(".json.backup")

        try:
            if self.config_file.exists():
                import shutil

                shutil.copy2(self.config_file, backup_path)
                logger.info(f"Config backed up to {backup_path}")
                return True
            logger.warning("No config file to backup")
            return False

        except Exception as e:
            logger.error(f"Failed to backup config: {e}")
            return False

    def restore_config(self, backup_path: Path) -> bool:
        """Restore configuration from backup."""
        try:
            if backup_path.exists():
                import shutil

                shutil.copy2(backup_path, self.config_file)
                self._config = None  # Force reload
                self.load_config()
                logger.info(f"Config restored from {backup_path}")
                return True
            logger.error(f"Backup file not found: {backup_path}")
            return False

        except Exception as e:
            logger.error(f"Failed to restore config: {e}")
            return False

    def export_locations(self, export_path: Path) -> bool:
        """Export locations to a separate file."""
        try:
            config = self.get_config()
            locations_data = {
                "locations": [
                    {
                        "name": loc.name,
                        "latitude": loc.latitude,
                        "longitude": loc.longitude,
                    }
                    for loc in config.locations
                ],
                "exported_at": str(datetime.now()),
            }

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(locations_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Locations exported to {export_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export locations: {e}")
            return False

    def import_locations(self, import_path: Path) -> bool:
        """Import locations from a file."""
        try:
            with open(import_path, encoding="utf-8") as f:
                data = json.load(f)

            config = self.get_config()
            imported_count = 0

            for loc_data in data.get("locations", []):
                name = loc_data["name"]
                latitude = loc_data["latitude"]
                longitude = loc_data["longitude"]

                # Check if location already exists
                exists = any(loc.name == name for loc in config.locations)
                if not exists:
                    config.locations.append(
                        Location(name=name, latitude=latitude, longitude=longitude)
                    )
                    imported_count += 1
                    logger.info(f"Imported location: {name}")
                else:
                    logger.info(f"Skipped existing location: {name}")

            if imported_count > 0:
                self.save_config()
                logger.info(f"Imported {imported_count} new locations")

            return True

        except Exception as e:
            logger.error(f"Failed to import locations: {e}")
            return False
