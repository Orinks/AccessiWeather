"""Location import/export helpers for configuration operations."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class LocationImportExportMixin:
    """Provide location export and import operations."""

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
                result = self._coerce_location_entry(entry)
                if result is None:
                    skipped_invalid += 1
                    self.logger.warning("Skipped invalid location entry: %s", entry)
                    continue

                name, latitude_value, longitude_value, country_code = result
                if any(location.name == name for location in config.locations):
                    self.logger.info(f"Skipped existing location: {name}")
                    continue

                kwargs = {
                    "name": name,
                    "latitude": latitude_value,
                    "longitude": longitude_value,
                }
                if country_code is not None:
                    kwargs["country_code"] = country_code
                config.locations.append(self._location_cls(**kwargs))
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
            self.logger.error(f"Failed to parse locations file (invalid JSON): {exc}")
            return False
        except Exception as exc:
            self.logger.error(f"Failed to import locations: {exc}")
            return False

    def _coerce_location_entry(self, entry: object) -> tuple[str, float, float, str | None] | None:
        """Validate and coerce a JSON location entry."""
        if not isinstance(entry, dict):
            return None

        name = entry.get("name")
        latitude = entry.get("latitude")
        longitude = entry.get("longitude")
        if not name or latitude is None or longitude is None:
            return None

        try:
            latitude_value = float(latitude)
            longitude_value = float(longitude)
        except (TypeError, ValueError):
            return None

        country_code = entry.get("country_code")
        return str(name), latitude_value, longitude_value, country_code
