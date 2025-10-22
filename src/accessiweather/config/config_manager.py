"""
Simple configuration management for AccessiWeather.

This module provides simple configuration loading and saving using Toga's paths API,
replacing the complex configuration system with straightforward JSON-based storage.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import toga

from accessiweather.models import AppConfig, AppSettings, Location
from accessiweather.services import StartupManager

from .github_config import GitHubConfigOperations
from .import_export import ImportExportOperations
from .locations import LocationOperations
from .settings import SettingsOperations

logger = logging.getLogger("accessiweather.config")


class ConfigManager:
    """Simple configuration manager using Toga paths."""

    def __init__(self, app: toga.App):
        """Initialize the configuration manager with a Toga app instance."""
        self.app = app
        self.config_file = self.app.paths.config / "accessiweather.json"
        self.config_dir = self.app.paths.config  # Add config_dir property
        self._config: AppConfig | None = None
        self._startup_manager = StartupManager()
        self._locations = LocationOperations(self)
        self._settings = SettingsOperations(self)
        self._github = GitHubConfigOperations(self)
        self._import_export = ImportExportOperations(self)

        # Ensure config directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Config file path: {self.config_file}")

    def _get_logger(self) -> logging.Logger:
        """Return the module-level logger for helper delegates."""
        package = sys.modules.get("accessiweather.config")
        if package and hasattr(package, "logger"):
            return package.logger  # type: ignore[return-value]
        return logger

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

                    # Validate and fix configuration
                    self._settings._validate_and_fix_config()

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
        return self._settings.update_settings(**kwargs)

    def add_location(
        self, name: str, latitude: float, longitude: float, country_code: str | None = None
    ) -> bool:
        """Add a new location."""
        return self._locations.add_location(name, latitude, longitude, country_code)

    def remove_location(self, name: str) -> bool:
        """Remove a location."""
        return self._locations.remove_location(name)

    def set_current_location(self, name: str) -> bool:
        """Set the current location."""
        return self._locations.set_current_location(name)

    def get_current_location(self) -> Location | None:
        """Get the current location."""
        return self._locations.get_current_location()

    def get_all_locations(self) -> list[Location]:
        """Get all saved locations."""
        return self._locations.get_all_locations()

    def get_location_names(self) -> list[str]:
        """Get names of all saved locations."""
        return self._locations.get_location_names()

    def has_locations(self) -> bool:
        """Check if any locations are saved."""
        return self._locations.has_locations()

    def get_settings(self) -> AppSettings:
        """Get application settings."""
        return self._settings.get_settings()

    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults."""
        return self._settings.reset_to_defaults()

    def reset_all_data(self) -> bool:
        """Reset all application data (settings, locations, caches, state)."""
        return self._settings.reset_all_data()

    def backup_config(self, backup_path: Path | None = None) -> bool:
        """Create a backup of the current configuration."""
        return self._import_export.backup_config(backup_path)

    def restore_config(self, backup_path: Path) -> bool:
        """Restore configuration from backup."""
        return self._import_export.restore_config(backup_path)

    def export_locations(self, export_path: Path) -> bool:
        """Export locations to a separate file."""
        return self._import_export.export_locations(export_path)

    def import_locations(self, import_path: Path) -> bool:
        """Import locations from a file."""
        return self._import_export.import_locations(import_path)

    def enable_startup(self) -> tuple[bool, str]:
        """
        Enable application startup on boot.

        Returns
        -------
            Tuple of (success, message) where message contains error details if failed

        """
        try:
            success = self._startup_manager.enable_startup()
            if success:
                logger.info("Application startup enabled successfully")
                return True, "Startup enabled successfully"
            logger.warning("Failed to enable application startup")
            return False, "Failed to enable startup. Check permissions and try again."
        except Exception as e:
            logger.error(f"Error enabling startup: {e}")
            return False, f"Error enabling startup: {str(e)}"

    def disable_startup(self) -> tuple[bool, str]:
        """
        Disable application startup on boot.

        Returns
        -------
            Tuple of (success, message) where message contains error details if failed

        """
        try:
            success = self._startup_manager.disable_startup()
            if success:
                logger.info("Application startup disabled successfully")
                return True, "Startup disabled successfully"
            logger.warning("Failed to disable application startup")
            return False, "Failed to disable startup. Check permissions and try again."
        except Exception as e:
            logger.error(f"Error disabling startup: {e}")
            return False, f"Error disabling startup: {str(e)}"

    def is_startup_enabled(self) -> bool:
        """
        Check if application startup is currently enabled.

        Returns
        -------
            True if startup is enabled, False otherwise

        """
        try:
            return self._startup_manager.is_startup_enabled()
        except Exception as e:
            logger.error(f"Error checking startup status: {e}")
            return False

    def sync_startup_setting(self) -> bool:
        """
        Synchronize the startup_enabled setting with actual startup state.

        This checks the real startup status and updates the setting if needed.

        Returns
        -------
            True if successful, False otherwise

        """
        try:
            actual_startup_enabled = self.is_startup_enabled()
            current_setting = self.get_settings().startup_enabled

            if actual_startup_enabled != current_setting:
                logger.info(
                    f"Syncing startup setting: actual={actual_startup_enabled}, setting={current_setting}"
                )
                return self.update_settings(startup_enabled=actual_startup_enabled)

            return True
        except Exception as e:
            logger.error(f"Error syncing startup setting: {e}")
            return False

    def validate_github_app_config(self) -> tuple[bool, str]:
        """Validate the GitHub App configuration fields."""
        return self._github.validate_github_app_config()

    def set_github_app_config(self, app_id: str, private_key: str, installation_id: str) -> bool:
        """Set the GitHub App configuration in the settings."""
        return self._github.set_github_app_config(app_id, private_key, installation_id)

    def get_github_app_config(self) -> tuple[str, str, str]:
        """Get the GitHub App configuration from the settings."""
        return self._github.get_github_app_config()

    def clear_github_app_config(self) -> bool:
        """Clear the GitHub App configuration from the settings."""
        return self._github.clear_github_app_config()

    def has_github_app_config(self) -> bool:
        """Check if GitHub submission is available."""
        return self._github.has_github_app_config()

    def get_github_backend_url(self) -> str:
        """Get the GitHub backend service URL."""
        return self._github.get_github_backend_url()

    def set_github_backend_url(self, backend_url: str) -> bool:
        """Set the GitHub backend service URL."""
        return self._github.set_github_backend_url(backend_url)
