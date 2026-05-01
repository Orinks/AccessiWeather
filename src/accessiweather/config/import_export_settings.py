"""Settings import/export helpers for configuration operations."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class SettingsImportExportMixin:
    """Provide settings import and export operations."""

    def export_settings(self, export_path: Path) -> bool:
        """Export application settings to a standalone JSON file."""
        try:
            config = self._manager.get_config()
            settings_data = {
                "settings": config.settings.to_dict(),
                "locations": [
                    {
                        "name": location.name,
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        **(
                            {"country_code": location.country_code} if location.country_code else {}
                        ),
                    }
                    for location in config.locations
                ],
                "exported_at": str(datetime.now()),
            }

            with open(export_path, "w", encoding="utf-8") as outfile:
                json.dump(settings_data, outfile, indent=2, ensure_ascii=False)

            self.logger.info(f"Settings exported to {export_path}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to export settings: {exc}")
            return False

    def import_settings(self, import_path: Path) -> bool:
        """Import application settings from an exported JSON file."""
        try:
            if not import_path.exists():
                self.logger.error(f"Import file not found: {import_path}")
                return False

            with open(import_path, encoding="utf-8") as infile:
                data = json.load(infile)

            if not isinstance(data, dict):
                self.logger.error("Invalid settings file: root element must be a JSON object")
                return False

            settings_data = data.get("settings")
            if not isinstance(settings_data, dict):
                self.logger.error(
                    "Invalid settings file: missing or invalid 'settings' key (expected object)"
                )
                return False

            self._normalize_imported_settings(settings_data)
            imported_settings = self._deserialize_imported_settings(settings_data)
            if imported_settings is None:
                return False

            config = self._manager.get_config()
            config.settings = imported_settings
            locations_imported = self._import_settings_locations(data, config.locations)
            if locations_imported:
                self.logger.info("Imported %d locations from settings file", locations_imported)

            if not self._manager.save_config():
                self.logger.error("Failed to save imported settings")
                return False

            self.logger.info(f"Successfully imported {len(settings_data)} settings")
            self._log_missing_import_fields(imported_settings, settings_data)
            return True
        except json.JSONDecodeError as exc:
            self.logger.error(f"Failed to parse settings file (invalid JSON): {exc}")
            return False
        except Exception as exc:
            self.logger.error(f"Failed to import settings: {exc}")
            return False

    def _normalize_imported_settings(self, settings_data: dict) -> None:
        """Normalize imported settings before deserialization."""
        valid_sources = ["auto", "nws", "openmeteo", "visualcrossing"]
        data_source = settings_data.get("data_source")
        if data_source is not None and data_source not in valid_sources:
            self.logger.warning(
                f"Invalid data_source '{data_source}' in imported settings, "
                f"will use 'auto'. Valid values: {', '.join(valid_sources)}"
            )
            settings_data["data_source"] = "auto"

    def _deserialize_imported_settings(self, settings_data: dict):
        """Deserialize imported settings through AppSettings validation."""
        try:
            from ..models import AppSettings

            return AppSettings.from_dict(settings_data)
        except Exception as exc:
            self.logger.error(f"Failed to deserialize settings: {exc}")
            return None

    def _import_settings_locations(self, data: dict, locations: list) -> int:
        """Import optional locations included with settings exports."""
        locations_imported = 0
        for entry in data.get("locations", []):
            result = self._coerce_location_entry(entry)
            if result is None:
                continue

            name, latitude_value, longitude_value, country_code = result
            if any(location.name == name for location in locations):
                self.logger.info(f"Skipped existing location: {name}")
                continue

            locations.append(
                self._location_cls(
                    name=name,
                    latitude=latitude_value,
                    longitude=longitude_value,
                    country_code=country_code,
                )
            )
            locations_imported += 1
            self.logger.info(f"Imported location: {name}")
        return locations_imported

    def _log_missing_import_fields(self, imported_settings, settings_data: dict) -> None:
        """Log defaulted fields that were absent from an older export."""
        missing_fields = [key for key in imported_settings.to_dict() if key not in settings_data]
        if missing_fields:
            self.logger.info(
                f"Used defaults for {len(missing_fields)} fields not present in import: "
                f"{', '.join(missing_fields[:5])}" + ("..." if len(missing_fields) > 5 else "")
            )
