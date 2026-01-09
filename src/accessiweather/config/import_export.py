"""Import/export and backup helpers for configuration management."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import Location

if TYPE_CHECKING:
    from .config_manager import ConfigManager

logger = logging.getLogger("accessiweather.config")


class ImportExportOperations:
    """Encapsulate config persistence utilities beyond the main file."""

    def __init__(self, manager: ConfigManager) -> None:
        """Store manager reference for backup and import/export helpers."""
        self._manager = manager

    @property
    def logger(self) -> logging.Logger:
        return self._manager._get_logger()

    def backup_config(self, backup_path: Path | None = None) -> bool:
        """Create a backup copy of the current configuration file."""
        backup_target = backup_path or self._manager.config_file.with_suffix(".json.backup")

        try:
            if not self._manager.config_file.exists():
                self.logger.warning("No config file to backup")
                return False

            shutil.copy2(self._manager.config_file, backup_target)
            self.logger.info(f"Config backed up to {backup_target}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to backup config: {exc}")
            return False

    def restore_config(self, backup_path: Path) -> bool:
        """Restore configuration from the provided backup file."""
        try:
            if not backup_path.exists():
                self.logger.error(f"Backup file not found: {backup_path}")
                return False

            shutil.copy2(backup_path, self._manager.config_file)
            self._manager._config = None
            self._manager.load_config()
            self.logger.info(f"Config restored from {backup_path}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to restore config: {exc}")
            return False

    def export_settings(self, export_path: Path) -> bool:
        """Export application settings to a standalone JSON file.

        Note: Secure keys (API keys, GitHub credentials) are NOT exported.
        These are stored in the system keyring and must be configured separately.
        """
        try:
            config = self._manager.get_config()
            settings_data = {
                "settings": config.settings.to_dict(),
                "exported_at": str(datetime.now()),
            }

            with open(export_path, "w", encoding="utf-8") as outfile:
                json.dump(settings_data, outfile, indent=2, ensure_ascii=False)

            self.logger.info(f"Settings exported to {export_path}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to export settings: {exc}")
            return False

    def export_locations(self, export_path: Path) -> bool:
        """Export configured locations to a standalone JSON file."""
        try:
            config = self._manager.get_config()
            locations_data = {
                "locations": [
                    {
                        "name": location.name,
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                    }
                    for location in config.locations
                ],
                "exported_at": str(datetime.now()),
            }

            with open(export_path, "w", encoding="utf-8") as outfile:
                json.dump(locations_data, outfile, indent=2, ensure_ascii=False)

            self.logger.info(f"Locations exported to {export_path}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to export locations: {exc}")
            return False

    def import_locations(self, import_path: Path) -> bool:
        """Import locations from an exported JSON file."""
        try:
            with open(import_path, encoding="utf-8") as infile:
                data = json.load(infile)

            config = self._manager.get_config()
            imported_count = 0
            skipped_invalid = 0

            for entry in data.get("locations", []):
                if not isinstance(entry, dict):
                    skipped_invalid += 1
                    self.logger.warning("Skipped invalid location entry (not a mapping): %s", entry)
                    continue

                name = entry.get("name")
                latitude = entry.get("latitude")
                longitude = entry.get("longitude")

                if not name or latitude is None or longitude is None:
                    skipped_invalid += 1
                    self.logger.warning(
                        "Skipped invalid location entry (missing fields): %s", entry
                    )
                    continue

                try:
                    latitude_value = float(latitude)
                    longitude_value = float(longitude)
                except (TypeError, ValueError):
                    skipped_invalid += 1
                    self.logger.warning(
                        "Skipped invalid location entry (non-numeric coordinates): %s", entry
                    )
                    continue

                if any(location.name == name for location in config.locations):
                    self.logger.info(f"Skipped existing location: {name}")
                    continue

                config.locations.append(
                    Location(name=name, latitude=latitude_value, longitude=longitude_value)
                )
                imported_count += 1
                self.logger.info(f"Imported location: {name}")

            success = True
            if imported_count > 0:
                self._manager.save_config()
            elif skipped_invalid > 0:
                success = False

            self.logger.info(
                "Imported %d new locations; skipped %d invalid entries",
                imported_count,
                skipped_invalid,
            )

            return success
        except Exception as exc:
            self.logger.error(f"Failed to import locations: {exc}")
            return False

    def import_settings(self, import_path: Path) -> bool:
        """Import application settings from an exported JSON file.

        Note: Secure keys (API keys, GitHub credentials) are NOT imported from files.
        These must be configured separately through the settings dialog, as they are
        stored in the system keyring.

        The import merges settings without affecting locations. Invalid or unknown
        settings keys are skipped gracefully, and validation warnings are logged.

        Args:
            import_path: Path to the JSON file containing exported settings

        Returns:
            True if settings were imported successfully, False otherwise
        """
        try:
            if not import_path.exists():
                self.logger.error(f"Import file not found: {import_path}")
                return False

            with open(import_path, encoding="utf-8") as infile:
                data = json.load(infile)

            # Validate JSON structure
            if not isinstance(data, dict):
                self.logger.error("Invalid settings file: root element must be a JSON object")
                return False

            settings_data = data.get("settings")
            if not isinstance(settings_data, dict):
                self.logger.error(
                    "Invalid settings file: missing or invalid 'settings' key (expected object)"
                )
                return False

            # Validate data_source if present
            valid_sources = ["auto", "nws", "openmeteo", "visualcrossing"]
            data_source = settings_data.get("data_source")
            if data_source is not None and data_source not in valid_sources:
                self.logger.warning(
                    f"Invalid data_source '{data_source}' in imported settings, "
                    f"will use 'auto'. Valid values: {', '.join(valid_sources)}"
                )
                settings_data["data_source"] = "auto"

            # Import settings using from_dict() which handles defaults and validation
            try:
                from ..models import AppSettings

                imported_settings = AppSettings.from_dict(settings_data)
            except Exception as exc:
                self.logger.error(f"Failed to deserialize settings: {exc}")
                return False

            # Merge imported settings with current config (preserving locations)
            config = self._manager.get_config()
            config.settings = imported_settings

            # Save the updated configuration
            if not self._manager.save_config():
                self.logger.error("Failed to save imported settings")
                return False

            # Count imported settings for logging
            imported_count = len(settings_data)
            self.logger.info(f"Successfully imported {imported_count} settings")

            # Log if imported from older export (missing newer fields)
            current_settings_dict = imported_settings.to_dict()
            missing_fields = []
            for key in current_settings_dict:
                if key not in settings_data:
                    missing_fields.append(key)

            if missing_fields:
                self.logger.info(
                    f"Used defaults for {len(missing_fields)} fields not present in import: "
                    f"{', '.join(missing_fields[:5])}"
                    + ("..." if len(missing_fields) > 5 else "")
                )

            return True

        except json.JSONDecodeError as exc:
            self.logger.error(f"Failed to parse settings file (invalid JSON): {exc}")
            return False
        except Exception as exc:
            self.logger.error(f"Failed to import settings: {exc}")
            return False
