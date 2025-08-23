"""Simple configuration management for AccessiWeather.

This module provides simple configuration loading and saving using Toga's paths API,
replacing the complex configuration system with straightforward JSON-based storage.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import toga

from .models import AppConfig, AppSettings, Location

logger = logging.getLogger(__name__)


class ConfigManager:
    """Simple configuration manager using Toga paths."""

    def __init__(self, app: toga.App):
        """Initialize the configuration manager with a Toga app instance."""
        self.app = app
        self.config_file = self.app.paths.config / "accessiweather.json"
        self.config_dir = self.app.paths.config  # Add config_dir property
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

                    # Handle legacy configs containing github_token
                    if isinstance(data, dict):
                        legacy_token = (data.get("settings") or {}).get("github_token")
                        if legacy_token:
                            logger.info(
                                "Detected legacy 'github_token' in config. User tokens are no longer supported and will be ignored."
                            )
                            # Remove legacy token from config data
                            if "github_token" in data.get("settings", {}):
                                del data["settings"]["github_token"]

                    self._config = AppConfig.from_dict(data)

                    # If we removed legacy token, save the cleaned config
                    if isinstance(data, dict) and legacy_token:
                        self.save_config()

                    # Validate and fix configuration
                    self._validate_and_fix_config()
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

    def _validate_and_fix_config(self) -> None:
        """Validate and fix configuration settings."""
        if self._config is None:
            return

        settings = self._config.settings
        config_changed = False

        # Validate data_source
        valid_sources = ["auto", "nws", "openmeteo", "visualcrossing"]
        if settings.data_source not in valid_sources:
            logger.warning(f"Invalid data_source '{settings.data_source}', resetting to 'auto'")
            settings.data_source = "auto"
            config_changed = True

        # Validate Visual Crossing configuration
        if settings.data_source == "visualcrossing":
            if not settings.visual_crossing_api_key:
                logger.warning(
                    "Visual Crossing selected but no API key provided, switching to 'auto'"
                )
                settings.data_source = "auto"
                config_changed = True
        else:
            # Clear Visual Crossing API key if not using Visual Crossing
            if settings.visual_crossing_api_key:
                logger.info(
                    f"Clearing Visual Crossing API key for data_source '{settings.data_source}'"
                )
                settings.visual_crossing_api_key = ""
                config_changed = True

        # Validate GitHub App configuration
        if settings.github_app_id:
            app_id = settings.github_app_id.strip()
            if not app_id:
                logger.warning("Empty GitHub App ID found, clearing")
                settings.github_app_id = ""
                config_changed = True
            elif not app_id.isdigit() or len(app_id) < 1:
                logger.warning("GitHub App ID appears invalid (should be numeric)")
                # Don't automatically clear - let user decide

        if settings.github_app_private_key:
            private_key = settings.github_app_private_key.strip()
            if not private_key:
                logger.warning("Empty GitHub App private key found, clearing")
                settings.github_app_private_key = ""
                config_changed = True
            else:
                from .constants import (
                    GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER,
                    GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER,
                    GITHUB_APP_PRIVATE_KEY_FOOTER,
                    GITHUB_APP_PRIVATE_KEY_HEADER,
                )

                pk = private_key.strip()
                valid_pem = (
                    pk.startswith(GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER)
                    and pk.endswith(GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER)
                ) or (
                    pk.startswith(GITHUB_APP_PRIVATE_KEY_HEADER)
                    and pk.endswith(GITHUB_APP_PRIVATE_KEY_FOOTER)
                )
                if not valid_pem:
                    logger.warning(
                        "GitHub App private key appears invalid (should be PEM formatted)"
                    )

        if settings.github_app_installation_id:
            installation_id = settings.github_app_installation_id.strip()
            if not installation_id:
                logger.warning("Empty GitHub App installation ID found, clearing")
                settings.github_app_installation_id = ""
                config_changed = True
            elif not installation_id.isdigit() or len(installation_id) < 1:
                logger.warning("GitHub App installation ID appears invalid (should be numeric)")
                # Don't automatically clear - let user decide

        # Save config if changes were made
        if config_changed:
            logger.info("Configuration was corrected, saving changes")
            self.save_config()

    def save_config(self) -> bool:
        """Save configuration to file."""
        if self._config is None:
            logger.warning("No config to save")
            return False

        try:
            logger.info(f"Saving config to {self.config_file}")
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)

            # Restrict permissions on POSIX systems
            try:
                if os.name != "nt":
                    os.chmod(self.config_file, 0o600)
            except Exception:
                logger.debug("Could not set strict permissions on config file", exc_info=True)

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

        # Define sensitive keys that should be redacted in logs
        secret_keys = {"github_app_private_key", "visual_crossing_api_key"}

        # Update settings attributes
        for key, value in kwargs.items():
            if key == "github_token":
                logger.info("'github_token' is deprecated and ignored.")
                continue

            if hasattr(config.settings, key):
                setattr(config.settings, key, value)
                # Redact sensitive values in logs
                log_value = "***redacted***" if key in secret_keys else value
                logger.info(f"Updated setting {key} = {log_value}")
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
                config.locations.pop(i)

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

    def validate_github_app_config(self) -> tuple[bool, str]:
        """Validate the GitHub App configuration fields.

        Returns:
            Tuple of (is_valid, message) where message contains validation details

        """
        config = self.get_config()
        settings = config.settings

        if not settings.github_app_id:
            return False, "No GitHub App ID configured"

        if not settings.github_app_private_key:
            return False, "No GitHub App private key configured"

        if not settings.github_app_installation_id:
            return False, "No GitHub App installation ID configured"

        # Validate app_id is numeric
        if not settings.github_app_id.strip().isdigit():
            return False, "GitHub App ID must be numeric"

        # Validate private key has PEM format using constants
        from .constants import (
            GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER,
            GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER,
            GITHUB_APP_PRIVATE_KEY_FOOTER,
            GITHUB_APP_PRIVATE_KEY_HEADER,
        )

        private_key = settings.github_app_private_key.strip()
        valid_pem = (
            private_key.startswith(GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER)
            and private_key.endswith(GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER)
        ) or (
            private_key.startswith(GITHUB_APP_PRIVATE_KEY_HEADER)
            and private_key.endswith(GITHUB_APP_PRIVATE_KEY_FOOTER)
        )
        if not valid_pem:
            return False, "GitHub App private key must be PEM formatted"

        # Validate installation_id is numeric
        if not settings.github_app_installation_id.strip().isdigit():
            return False, "GitHub App installation ID must be numeric"

        return True, "GitHub App configuration is valid"

    def set_github_app_config(self, app_id: str, private_key: str, installation_id: str) -> bool:
        """Set the GitHub App configuration in the settings.

        Args:
            app_id: The GitHub App ID
            private_key: The PEM-encoded private key
            installation_id: The installation ID

        Returns:
            True if successful, False otherwise

        """
        try:
            config = self.get_config()
            config.settings.github_app_id = app_id.strip()
            config.settings.github_app_private_key = private_key.strip()
            config.settings.github_app_installation_id = installation_id.strip()
            return self.save_config()
        except Exception as e:
            logger.error(f"Failed to set GitHub App configuration: {e}")
            return False

    def get_github_app_config(self) -> tuple[str, str, str]:
        """Get the GitHub App configuration from the settings.

        Returns:
            Tuple of (app_id, private_key, installation_id), empty strings if not set

        """
        try:
            settings = self.get_config().settings
            return (
                settings.github_app_id,
                settings.github_app_private_key,
                settings.github_app_installation_id,
            )
        except Exception as e:
            logger.error(f"Failed to get GitHub App configuration: {e}")
            return ("", "", "")

    def clear_github_app_config(self) -> bool:
        """Clear the GitHub App configuration from the settings.

        Returns:
            True if successful, False otherwise

        """
        return self.set_github_app_config("", "", "")

    def has_github_app_config(self) -> bool:
        """Check if all required GitHub App configuration fields are present.

        Returns:
            True if all fields are configured, False otherwise

        """
        app_id, private_key, installation_id = self.get_github_app_config()
        return bool(app_id and private_key and installation_id)
