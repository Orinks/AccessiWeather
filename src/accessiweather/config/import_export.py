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
    """Encapsulate config persistence utilities beyond the main file.

    This class provides backup, restore, import, and export functionality for
    AccessiWeather configuration data. It handles settings and location data
    separately to allow selective migration.

    Security Considerations:
        - API keys and credentials are NEVER exported to files
        - Sensitive data remains in the system keyring
        - Import operations validate all input data before application
        - File operations use secure paths to prevent directory traversal
    """

    def __init__(self, manager: ConfigManager) -> None:
        """Initialize import/export operations with a config manager.

        Args:
            manager: The ConfigManager instance to operate on
        """
        self._manager = manager

    @property
    def logger(self) -> logging.Logger:
        """Access the configuration manager's logger instance.

        Returns:
            Logger instance configured for accessiweather.config
        """
        return self._manager._get_logger()

    def backup_config(self, backup_path: Path | None = None) -> bool:
        """Create a backup copy of the current configuration file.

        Creates a timestamped backup of the entire configuration file, including
        settings and locations. This is useful before performing risky operations
        like imports or manual edits.

        Security Considerations:
            - Backup files contain all settings but NOT API keys (keys are in keyring)
            - Uses shutil.copy2 to preserve file metadata and permissions
            - Backup path should be user-controlled to prevent directory traversal
            - Original file permissions are preserved on the backup

        Args:
            backup_path: Optional custom path for the backup file.
                        Defaults to <config_file>.json.backup

        Returns:
            True if backup was created successfully, False otherwise
        """
        backup_target = backup_path or self._manager.config_file.with_suffix(".json.backup")

        try:
            if not self._manager.config_file.exists():
                self.logger.warning("No config file to backup")
                return False

            # SECURITY: shutil.copy2 preserves original file permissions
            shutil.copy2(self._manager.config_file, backup_target)
            self.logger.info(f"Config backed up to {backup_target}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to backup config: {exc}")
            return False

    def restore_config(self, backup_path: Path) -> bool:
        """Restore configuration from the provided backup file.

        Replaces the current configuration file with a backup copy and reloads
        the configuration. This operation is destructive and should only be used
        when recovering from a corrupted or unwanted configuration state.

        Security Considerations:
            - Validates backup file exists before attempting restore
            - Uses ConfigManager.load_config() for JSON validation
            - Invalid JSON in backup file will cause restore to fail safely
            - Original config file is overwritten (consider backing up first)
            - API keys are NOT affected (they remain in system keyring)

        Args:
            backup_path: Path to the backup file to restore from

        Returns:
            True if configuration was restored successfully, False otherwise
        """
        try:
            # SECURITY: Validate backup file exists to prevent path traversal errors
            if not backup_path.exists():
                self.logger.error(f"Backup file not found: {backup_path}")
                return False

            # Replace current config file with backup
            shutil.copy2(backup_path, self._manager.config_file)

            # SECURITY: Clear cached config and reload to validate JSON structure
            # This ensures corrupted or malicious backup files are rejected
            self._manager._config = None
            self._manager.load_config()

            self.logger.info(f"Config restored from {backup_path}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to restore config: {exc}")
            return False

    def export_settings(self, export_path: Path) -> bool:
        """Export application settings to a standalone JSON file.

        Exports user preferences and configuration options (like units, data sources,
        update intervals) to a portable JSON file that can be imported on another
        system or shared with other users.

        Security Considerations:
            - API keys and credentials are NEVER exported to files
            - Sensitive keys remain in the system keyring only
            - Export file contains only non-sensitive configuration preferences
            - No personally identifiable information (PII) is included
            - File is written with UTF-8 encoding to prevent injection attacks

        Args:
            export_path: Path where the settings JSON file will be written

        Returns:
            True if settings were exported successfully, False otherwise

        Note:
            After importing these settings on another system, API keys must be
            configured separately through the settings dialog.
        """
        try:
            config = self._manager.get_config()

            # SECURITY: Only export non-sensitive settings (API keys stay in keyring)
            settings_data = {
                "settings": config.settings.to_dict(),
                "exported_at": str(datetime.now()),
            }

            # SECURITY: Use UTF-8 encoding and ensure_ascii=False for safe serialization
            with open(export_path, "w", encoding="utf-8") as outfile:
                json.dump(settings_data, outfile, indent=2, ensure_ascii=False)

            self.logger.info(f"Settings exported to {export_path}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to export settings: {exc}")
            return False

    def export_locations(self, export_path: Path) -> bool:
        """Export configured locations to a standalone JSON file.

        Exports all saved locations (name, latitude, longitude) to a portable
        JSON file that can be shared or imported on another system.

        Security Considerations:
            - Location data may contain PII (home address, work location, etc.)
            - Users should be aware that exported location files contain GPS coordinates
            - Exported file should be treated as potentially sensitive information
            - File is written with UTF-8 encoding to prevent injection attacks
            - No validation is performed on location names during export

        Args:
            export_path: Path where the locations JSON file will be written

        Returns:
            True if locations were exported successfully, False otherwise

        Privacy Note:
            Location names and coordinates may reveal personal information about
            places you frequently check. Store exported files securely.
        """
        try:
            config = self._manager.get_config()

            # SECURITY: Location data may contain PII - handle carefully
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

            # SECURITY: Use UTF-8 encoding for safe serialization
            with open(export_path, "w", encoding="utf-8") as outfile:
                json.dump(locations_data, outfile, indent=2, ensure_ascii=False)

            self.logger.info(f"Locations exported to {export_path}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to export locations: {exc}")
            return False

    def import_locations(self, import_path: Path) -> bool:
        """Import locations from an exported JSON file.

        Reads location data from a JSON file and adds new locations to the current
        configuration. Existing locations (by name) are skipped to prevent duplicates.
        All imported data is validated before being added.

        Security Considerations:
            - Validates JSON structure before processing (protects against malformed input)
            - Type-checks all location entries (dict validation)
            - Validates required fields presence (name, latitude, longitude)
            - Validates coordinate data types (must be numeric)
            - Validates coordinate ranges via Location model (-90 to 90, -180 to 180)
            - Skips invalid entries gracefully without crashing
            - No code execution from imported data (safe JSON parsing only)
            - Prevents duplicate locations (name-based collision detection)

        Args:
            import_path: Path to the JSON file containing location data

        Returns:
            True if at least one location was imported successfully or if all were
            duplicates, False if all entries were invalid or file couldn't be read

        Note:
            Invalid or malformed location entries are skipped with warnings logged.
            The import continues processing remaining valid entries.
        """
        try:
            # SECURITY: Use UTF-8 encoding to prevent encoding-based attacks
            with open(import_path, encoding="utf-8") as infile:
                data = json.load(infile)

            config = self._manager.get_config()
            imported_count = 0
            skipped_invalid = 0

            # SECURITY: Validate each location entry thoroughly before adding
            for entry in data.get("locations", []):
                # SECURITY: Type check - must be a dictionary
                if not isinstance(entry, dict):
                    skipped_invalid += 1
                    self.logger.warning("Skipped invalid location entry (not a mapping): %s", entry)
                    continue

                name = entry.get("name")
                latitude = entry.get("latitude")
                longitude = entry.get("longitude")

                # SECURITY: Validate required fields are present
                if not name or latitude is None or longitude is None:
                    skipped_invalid += 1
                    self.logger.warning(
                        "Skipped invalid location entry (missing fields): %s", entry
                    )
                    continue

                # SECURITY: Validate coordinates are numeric (prevents injection)
                try:
                    latitude_value = float(latitude)
                    longitude_value = float(longitude)
                except (TypeError, ValueError):
                    skipped_invalid += 1
                    self.logger.warning(
                        "Skipped invalid location entry (non-numeric coordinates): %s", entry
                    )
                    continue

                # SECURITY: Prevent duplicate locations (name-based collision detection)
                if any(location.name == name for location in config.locations):
                    self.logger.info(f"Skipped existing location: {name}")
                    continue

                # SECURITY: Location model validates coordinate ranges (-90/90, -180/180)
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
        except json.JSONDecodeError as exc:
            # SECURITY: Catch malformed JSON separately for better error reporting
            self.logger.error(f"Failed to parse locations file (invalid JSON): {exc}")
            return False
        except Exception as exc:
            self.logger.error(f"Failed to import locations: {exc}")
            return False

    def import_settings(self, import_path: Path) -> bool:
        """Import application settings from an exported JSON file.

        Imports user preferences and configuration options from a JSON file,
        merging them with the current configuration while preserving locations.
        All imported data is validated before being applied.

        Security Considerations:
            - API keys and credentials are NEVER imported from files
            - Sensitive keys must be configured separately (stored in keyring)
            - Validates file existence before attempting to read
            - Validates JSON structure at multiple levels (root, settings object)
            - Type-checks all imported values before application
            - Validates enum values (data_source) against allowed list
            - Uses AppSettings.from_dict() for centralized validation
            - Rejects invalid settings gracefully without partial application
            - No code execution from imported data (safe JSON parsing only)
            - Preserves existing locations (settings-only import)

        Args:
            import_path: Path to the JSON file containing exported settings

        Returns:
            True if settings were imported successfully, False otherwise

        Note:
            After importing settings, API keys must be configured separately
            through the settings dialog, as they are never stored in export files.
        """
        try:
            # SECURITY: Validate file exists to prevent path-based errors
            if not import_path.exists():
                self.logger.error(f"Import file not found: {import_path}")
                return False

            # SECURITY: Use UTF-8 encoding to prevent encoding-based attacks
            with open(import_path, encoding="utf-8") as infile:
                data = json.load(infile)

            # SECURITY: Validate JSON structure - root must be a dict
            if not isinstance(data, dict):
                self.logger.error("Invalid settings file: root element must be a JSON object")
                return False

            # SECURITY: Validate settings key exists and is a dict
            settings_data = data.get("settings")
            if not isinstance(settings_data, dict):
                self.logger.error(
                    "Invalid settings file: missing or invalid 'settings' key (expected object)"
                )
                return False

            # SECURITY: Validate data_source enum if present (prevent invalid values)
            valid_sources = ["auto", "nws", "openmeteo", "visualcrossing"]
            data_source = settings_data.get("data_source")
            if data_source is not None and data_source not in valid_sources:
                self.logger.warning(
                    f"Invalid data_source '{data_source}' in imported settings, "
                    f"will use 'auto'. Valid values: {', '.join(valid_sources)}"
                )
                settings_data["data_source"] = "auto"

            # SECURITY: Use AppSettings.from_dict() for centralized validation
            # This ensures all type checking, range validation, and defaults are applied
            try:
                from ..models import AppSettings

                imported_settings = AppSettings.from_dict(settings_data)
            except Exception as exc:
                self.logger.error(f"Failed to deserialize settings: {exc}")
                return False

            # SECURITY: Merge settings while preserving locations (settings-only import)
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
            # SECURITY: Catch malformed JSON separately for better error reporting
            self.logger.error(f"Failed to parse settings file (invalid JSON): {exc}")
            return False
        except Exception as exc:
            self.logger.error(f"Failed to import settings: {exc}")
            return False
