"""GitHub App configuration helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..constants import (
    GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER,
    GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER,
    GITHUB_APP_PRIVATE_KEY_FOOTER,
    GITHUB_APP_PRIVATE_KEY_HEADER,
)

if TYPE_CHECKING:
    from .config_manager import ConfigManager

logger = logging.getLogger("accessiweather.config")


class GitHubConfigOperations:
    """Encapsulate GitHub App configuration management."""

    def __init__(self, manager: ConfigManager) -> None:
        """Store manager reference for delegated GitHub operations."""
        self._manager = manager

    @property
    def logger(self) -> logging.Logger:
        return self._manager._get_logger()

    def validate_github_app_config(self) -> tuple[bool, str]:
        """Validate the GitHub App configuration fields."""
        settings = self._manager.get_config().settings

        if not settings.github_app_id:
            return False, "No GitHub App ID configured"

        if not settings.github_app_private_key:
            return False, "No GitHub App private key configured"

        if not settings.github_app_installation_id:
            return False, "No GitHub App installation ID configured"

        if not settings.github_app_id.strip().isdigit():
            return False, "GitHub App ID must be numeric"

        private_key = settings.github_app_private_key.strip()
        valid_pem = (
            private_key.startswith(GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER)
            and private_key.endswith(GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER)
        ) or (
            private_key.startswith(GITHUB_APP_PRIVATE_KEY_HEADER)
            and private_key.endswith(GITHUB_APP_PRIVATE_KEY_FOOTER)
        )
        if not valid_pem:
            has_pkcs8_header = private_key.startswith(GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER)
            has_pkcs8_footer = private_key.endswith(GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER)
            has_pkcs1_header = private_key.startswith(GITHUB_APP_PRIVATE_KEY_HEADER)
            has_pkcs1_footer = private_key.endswith(GITHUB_APP_PRIVATE_KEY_FOOTER)

            if not (has_pkcs8_header or has_pkcs1_header):
                return (
                    False,
                    "GitHub App private key missing PEM header. Expected '-----BEGIN PRIVATE KEY-----' (PKCS#8) or '-----BEGIN RSA PRIVATE KEY-----' (PKCS#1). Please use the .pem file downloaded from GitHub.",
                )
            if not (has_pkcs8_footer or has_pkcs1_footer):
                return (
                    False,
                    "GitHub App private key missing PEM footer. Expected '-----END PRIVATE KEY-----' (PKCS#8) or '-----END RSA PRIVATE KEY-----' (PKCS#1). Please use the .pem file downloaded from GitHub.",
                )
            return (
                False,
                "GitHub App private key has mismatched PEM headers/footers. Please use the .pem file downloaded from GitHub.",
            )

        if not settings.github_app_installation_id.strip().isdigit():
            return False, "GitHub App installation ID must be numeric"

        return True, "GitHub App configuration is valid"

    def set_github_app_config(self, app_id: str, private_key: str, installation_id: str) -> bool:
        """Set the GitHub App configuration in the settings."""
        try:
            return self._manager.update_settings(
                github_app_id=app_id.strip(),
                github_app_private_key=private_key.strip(),
                github_app_installation_id=installation_id.strip(),
            )
        except Exception as exc:
            self.logger.error(f"Failed to set GitHub App configuration: {exc}")
            return False

    def get_github_app_config(self) -> tuple[str, str, str]:
        """Return the stored GitHub App configuration values."""
        try:
            settings = self._manager.get_config().settings
            return (
                settings.github_app_id,
                settings.github_app_private_key,
                settings.github_app_installation_id,
            )
        except Exception as exc:
            self.logger.error(f"Failed to get GitHub App configuration: {exc}")
            return "", "", ""

    def clear_github_app_config(self) -> bool:
        """Clear all GitHub App configuration values."""
        return self.set_github_app_config("", "", "")

    def has_github_app_config(self) -> bool:
        """Determine whether GitHub submission is available."""
        try:
            url = (self.get_github_backend_url() or "").strip()
        except Exception:
            url = ""
        return bool(url)

    def get_github_backend_url(self) -> str:
        """Return the configured GitHub backend URL or the default."""
        config = self._manager.get_config()
        backend_url = config.settings.github_backend_url.strip()
        if backend_url:
            return backend_url
        return "https://soundpack-backend.fly.dev"

    def set_github_backend_url(self, backend_url: str) -> bool:
        """Persist the GitHub backend URL."""
        try:
            config = self._manager.get_config()
            config.settings.github_backend_url = backend_url.strip()
            return self._manager.save_config()
        except Exception as exc:
            self.logger.error(f"Failed to set GitHub backend URL: {exc}")
            return False
