"""Settings management for the GitHub update service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_FILENAME = "update_settings.json"
DEFAULT_OWNER = "orinks"
DEFAULT_REPO = "accessiweather"


@dataclass
class UpdateSettings:
    """Persisted update configuration."""

    channel: str = "stable"
    owner: str = DEFAULT_OWNER
    repo: str = DEFAULT_REPO


class SettingsManager:
    """Load, save, and migrate update settings."""

    def __init__(self, settings_path: Path) -> None:
        """Record where update settings are stored."""
        self.settings_path = settings_path

    def load_settings(self) -> UpdateSettings:
        """Load persisted settings or fall back to defaults."""
        if self.settings_path.exists():
            try:
                with open(self.settings_path, encoding="utf-8") as file:
                    data = json.load(file)

                if (
                    data.get("repo_owner") == "joshuakitchen"
                    or data.get("owner") == "joshuakitchen"
                ):
                    logger.info("Found old settings with incorrect owner, using defaults")
                    self.settings_path.unlink()
                    return UpdateSettings(channel="stable", owner=DEFAULT_OWNER, repo=DEFAULT_REPO)

                field_mapping = {
                    "channel": "channel",
                    "owner": "owner",
                    "repo_owner": "owner",
                    "repo": "repo",
                    "repo_name": "repo",
                }

                filtered_data: dict[str, str] = {}
                for old_key, value in data.items():
                    if old_key in field_mapping:
                        filtered_data[field_mapping[old_key]] = value

                return UpdateSettings(**filtered_data)
            except Exception as exc:  # noqa: BLE001 - log and recover gracefully
                logger.warning(f"Failed to load update settings: {exc}")
                try:
                    self.settings_path.unlink()
                    logger.info("Deleted corrupted update settings file")
                except Exception:  # noqa: BLE001 - best effort cleanup
                    pass
        return UpdateSettings(channel="stable", owner=DEFAULT_OWNER, repo=DEFAULT_REPO)

    def save_settings(self, settings: UpdateSettings) -> None:
        """Persist settings to disk."""
        try:
            with open(self.settings_path, "w", encoding="utf-8") as file:
                json.dump(settings.__dict__, file)
        except Exception as exc:  # noqa: BLE001 - log and keep running
            logger.warning(f"Failed to save update settings: {exc}")

    @staticmethod
    def get_settings_dict(settings: UpdateSettings) -> dict[str, str]:
        """Expose settings as a plain dictionary."""
        return settings.__dict__
