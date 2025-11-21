"""Settings-related helpers for configuration management."""

from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING

from ..constants import (
    GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER,
    GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER,
    GITHUB_APP_PRIVATE_KEY_FOOTER,
    GITHUB_APP_PRIVATE_KEY_HEADER,
)
from ..models import AppConfig, AppSettings
from .secure_storage import SecureStorage

if TYPE_CHECKING:
    from .config_manager import ConfigManager

logger = logging.getLogger("accessiweather.config")


class SettingsOperations:
    """Encapsulate settings management and validation logic."""

    def __init__(self, manager: ConfigManager) -> None:
        """Persist manager reference for settings validation and updates."""
        self._manager = manager

    @property
    def logger(self) -> logging.Logger:
        return self._manager._get_logger()

    def _validate_and_fix_config(self) -> None:
        """Validate and correct configuration values in-place when possible."""
        config = self._manager._config
        if config is None:
            return

        settings = config.settings
        config_changed = False

        valid_sources = ["auto", "nws", "openmeteo", "visualcrossing"]
        if settings.data_source not in valid_sources:
            self.logger.warning(
                f"Invalid data_source '{settings.data_source}', resetting to 'auto'"
            )
            settings.data_source = "auto"
            config_changed = True

        if settings.data_source == "visualcrossing":
            if not settings.visual_crossing_api_key:
                self.logger.warning(
                    "Visual Crossing selected but no API key provided, switching to 'auto'"
                )
                settings.data_source = "auto"
                config_changed = True
        else:
            if settings.visual_crossing_api_key:
                self.logger.info(
                    f"Clearing Visual Crossing API key for data_source '{settings.data_source}'"
                )
                settings.visual_crossing_api_key = ""
                config_changed = True

        app_id = getattr(settings, "github_app_id", "")
        if app_id:
            app_id = app_id.strip()
            if not app_id:
                self.logger.warning("Empty GitHub App ID found, clearing")
                settings.github_app_id = ""
                config_changed = True
            elif not app_id.isdigit() or len(app_id) < 1:
                self.logger.warning("GitHub App ID appears invalid (should be numeric)")

        private_key = getattr(settings, "github_app_private_key", "")
        if private_key:
            private_key = private_key.strip()
            if not private_key:
                self.logger.warning("Empty GitHub App private key found, clearing")
                settings.github_app_private_key = ""
                config_changed = True
            else:
                pk = private_key.strip()
                valid_pem = (
                    pk.startswith(GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER)
                    and pk.endswith(GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER)
                ) or (
                    pk.startswith(GITHUB_APP_PRIVATE_KEY_HEADER)
                    and pk.endswith(GITHUB_APP_PRIVATE_KEY_FOOTER)
                )
                if not valid_pem:
                    has_pkcs8_header = pk.startswith(GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER)
                    has_pkcs8_footer = pk.endswith(GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER)
                    has_pkcs1_header = pk.startswith(GITHUB_APP_PRIVATE_KEY_HEADER)
                    has_pkcs1_footer = pk.endswith(GITHUB_APP_PRIVATE_KEY_FOOTER)

                    if not (has_pkcs8_header or has_pkcs1_header):
                        self.logger.warning(
                            "GitHub App private key missing PEM header. Expected '-----BEGIN PRIVATE KEY-----' (PKCS#8) or '-----BEGIN RSA PRIVATE KEY-----' (PKCS#1). Please use the .pem file downloaded from GitHub."
                        )
                    elif not (has_pkcs8_footer or has_pkcs1_footer):
                        self.logger.warning(
                            "GitHub App private key missing PEM footer. Expected '-----END PRIVATE KEY-----' (PKCS#8) or '-----END RSA PRIVATE KEY-----' (PKCS#1). Please use the .pem file downloaded from GitHub."
                        )
                    else:
                        self.logger.warning(
                            "GitHub App private key has mismatched PEM headers/footers. Please use the .pem file downloaded from GitHub."
                        )

        installation_id = getattr(settings, "github_app_installation_id", "")
        if installation_id:
            installation_id = installation_id.strip()
            if not installation_id:
                self.logger.warning("Empty GitHub App installation ID found, clearing")
                settings.github_app_installation_id = ""
                config_changed = True
            elif not installation_id.isdigit() or len(installation_id) < 1:
                self.logger.warning(
                    "GitHub App installation ID appears invalid (should be numeric)"
                )

        if config_changed:
            self.logger.info("Configuration was corrected, saving changes")
            self._manager.save_config()

    def update_settings(self, **kwargs) -> bool:
        """Update settings values on the current configuration."""
        config = self._manager.get_config()
        # These keys should be stored in SecureStorage
        secure_keys = {
            "visual_crossing_api_key",
            "github_app_id",
            "github_app_private_key",
            "github_app_installation_id",
        }
        # These keys should be redacted in logs
        redacted_keys = {"github_app_private_key", "visual_crossing_api_key"}

        for key, value in kwargs.items():
            if hasattr(config.settings, key):
                setattr(config.settings, key, value)

                if key in secure_keys and not SecureStorage.set_password(key, value):
                    self.logger.error(f"Failed to save {key} to secure storage")

                log_value = "***redacted***" if key in redacted_keys else value
                self.logger.info(f"Updated setting {key} = {log_value}")
            else:
                self.logger.warning(f"Unknown setting: {key}")

        return self._manager.save_config()

    def get_settings(self) -> AppSettings:
        """Return the current AppSettings instance."""
        return self._manager.get_config().settings

    def reset_to_defaults(self) -> bool:
        """Reset the in-memory configuration to defaults and persist it."""
        self.logger.info("Resetting configuration to defaults")
        self._manager._config = AppConfig.default()
        return self._manager.save_config()

    def reset_all_data(self) -> bool:
        """Remove all configuration files and recreate defaults."""
        try:
            config_dir = self._manager.config_dir

            for item in config_dir.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                except Exception:
                    self.logger.warning(f"Failed to remove {item}", exc_info=True)

            self._manager._config = AppConfig.default()
            config_dir.mkdir(parents=True, exist_ok=True)
            return self._manager.save_config()
        except Exception as exc:
            self.logger.error(f"Failed to reset all data: {exc}")
            return False
