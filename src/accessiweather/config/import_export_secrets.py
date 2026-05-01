"""Encrypted API key import/export helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .portable_secrets import PortableSecretsError


class EncryptedApiKeyImportExportMixin:
    """Provide encrypted portable API key bundle operations."""

    def export_encrypted_api_keys(self, export_path: Path, passphrase: str) -> bool:
        """
        Export API keys to an encrypted portable bundle file.

        Checks in-memory settings first (covers portable mode where keys are
        not in keyring), then falls back to keyring (covers installed mode).
        LazySecureStorage values are resolved via ``str()``.
        """
        try:
            secrets = self._collect_api_key_secrets()
            if not secrets:
                self.logger.warning("No API keys available in secure storage to export")
                return False

            envelope = self._encrypt_secret_bundle(secrets, passphrase)
            with open(export_path, "w", encoding="utf-8") as outfile:
                json.dump(envelope, outfile, indent=2, ensure_ascii=False)

            self.logger.info(f"Encrypted API keys exported to {export_path}")
            return True
        except PortableSecretsError as exc:
            self.logger.error(f"Failed to export encrypted API keys: {exc}")
            return False
        except Exception as exc:
            self.logger.error(f"Failed to export encrypted API keys: {exc}")
            return False

    def import_encrypted_api_keys(self, import_path: Path, passphrase: str) -> bool:
        """Import encrypted API keys bundle into current machine keyring."""
        try:
            with open(import_path, encoding="utf-8") as infile:
                envelope = json.load(infile)

            if not isinstance(envelope, dict):
                self.logger.error("Invalid encrypted API key bundle format")
                return False

            secrets = self._decrypt_secret_bundle(envelope, passphrase)
            imported, failed = self._write_api_key_secrets(secrets)

            if imported == 0 and not failed:
                self.logger.warning("Encrypted API key bundle did not contain supported keys")
                return False

            self.logger.info("Imported %d API keys into secure storage", imported)
            self._activate_imported_api_keys(secrets)
            return not failed
        except PortableSecretsError as exc:
            self.logger.error(f"Failed to import encrypted API keys: {exc}")
            return False
        except Exception as exc:
            self.logger.error(f"Failed to import encrypted API keys: {exc}")
            return False

    def _collect_api_key_secrets(self) -> dict[str, str]:
        """Collect supported API keys from memory first, then secure storage."""
        secrets: dict[str, str] = {}
        for key_name in self._portable_api_secret_keys:
            value: str | None = None
            if self._manager._config is not None:
                raw = getattr(self._manager._config.settings, key_name, None)
                if raw is not None:
                    resolved = str(raw)
                    if resolved:
                        value = resolved
            if not value:
                value = self._secure_storage_cls.get_password(key_name)
            if value:
                secrets[key_name] = value
        return secrets

    def _write_api_key_secrets(self, secrets: dict[str, str]) -> tuple[int, list[str]]:
        """Write supported API keys into secure storage."""
        imported = 0
        failed = []
        for key_name in self._portable_api_secret_keys:
            value = secrets.get(key_name)
            if not value:
                continue
            if not self._secure_storage_cls.set_password(key_name, value):
                self.logger.error(f"Failed to import API key into secure storage: {key_name}")
                failed.append(key_name)
            else:
                imported += 1
        return imported, failed

    def _activate_imported_api_keys(self, secrets: dict[str, str]) -> None:
        """Refresh imported keys into the active config or portable settings."""
        is_portable = getattr(self._manager, "app", None) and getattr(
            self._manager.app, "_portable_mode", False
        )
        if is_portable and self._manager._config is not None:
            for key_name in self._portable_api_secret_keys:
                value = secrets.get(key_name)
                if value:
                    setattr(self._manager._config.settings, key_name, value)
                    self.logger.debug(f"Set in-memory key for portable mode: {key_name}")
        else:
            self._manager._load_secure_keys()
