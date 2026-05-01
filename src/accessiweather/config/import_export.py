"""Import/export and backup helpers for configuration management."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ..models import Location
from .import_export_backup import BackupRestoreMixin
from .import_export_locations import LocationImportExportMixin
from .import_export_secrets import EncryptedApiKeyImportExportMixin
from .import_export_settings import SettingsImportExportMixin
from .portable_secrets import decrypt_secret_bundle, encrypt_secret_bundle
from .secure_storage import SecureStorage

if TYPE_CHECKING:
    from .config_manager import ConfigManager

logger = logging.getLogger("accessiweather.config")

PORTABLE_API_SECRET_KEYS: Final[tuple[str, ...]] = (
    "pirate_weather_api_key",
    "openrouter_api_key",
    "avwx_api_key",
)


class ImportExportOperations(
    BackupRestoreMixin,
    EncryptedApiKeyImportExportMixin,
    LocationImportExportMixin,
    SettingsImportExportMixin,
):
    """
    Encapsulate config persistence utilities beyond the main file.

    Security-sensitive dependencies remain surfaced from this module for
    compatibility with existing tests and callers that patch this facade.
    """

    def __init__(self, manager: ConfigManager) -> None:
        """Initialize import/export operations with a config manager."""
        self._manager = manager

    @property
    def logger(self) -> logging.Logger:
        """Access the configuration manager's logger instance."""
        return self._manager._get_logger()

    @property
    def _location_cls(self):
        return Location

    @property
    def _secure_storage_cls(self):
        return SecureStorage

    @property
    def _portable_api_secret_keys(self) -> tuple[str, ...]:
        return PORTABLE_API_SECRET_KEYS

    def _copy_file(self, source: Path, target: Path) -> None:
        shutil.copy2(source, target)

    def _encrypt_secret_bundle(self, secrets: dict[str, str], passphrase: str) -> dict:
        return encrypt_secret_bundle(secrets, passphrase)

    def _decrypt_secret_bundle(self, envelope: dict, passphrase: str) -> dict[str, str]:
        return decrypt_secret_bundle(envelope, passphrase)
