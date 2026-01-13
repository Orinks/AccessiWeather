"""Secure storage management using system keyring."""

from __future__ import annotations

import logging
from typing import Final

try:
    import keyring
except ImportError:
    keyring = None

logger = logging.getLogger("accessiweather.config.secure")

SERVICE_NAME: Final = "accessiweather"


class SecureStorage:
    """Wrapper around system keyring for secure credential storage."""

    @staticmethod
    def set_password(username: str, password: str) -> bool:
        """
        Set a password in the secure keyring.

        Args:
            username: The key/username to store the password under
            password: The value/password to store

        Returns:
            True if successful, False otherwise

        """
        if keyring is None:
            logger.warning(f"Keyring not available, cannot store credential for {username}")
            return False

        try:
            if not password:
                # storing empty password often fails or is ambiguous, so we delete instead
                return SecureStorage.delete_password(username)

            keyring.set_password(SERVICE_NAME, username, password)
            logger.info(f"Securely stored credential for {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to store credential for {username}: {e}")
            return False

    @staticmethod
    def get_password(username: str) -> str | None:
        """
        Retrieve a password from the secure keyring.

        Args:
            username: The key/username to retrieve

        Returns:
            The password string if found, None otherwise

        """
        if keyring is None:
            logger.warning(f"Keyring not available, cannot retrieve credential for {username}")
            return None

        try:
            return keyring.get_password(SERVICE_NAME, username)
        except Exception as e:
            logger.error(f"Failed to retrieve credential for {username}: {e}")
            return None

    @staticmethod
    def delete_password(username: str) -> bool:
        """
        Delete a password from the secure keyring.

        Args:
            username: The key/username to delete

        Returns:
            True if successful (or didn't exist), False on error

        """
        if keyring is None:
            return True  # Treat as success since we can't delete what we can't access

        try:
            # Check if it exists first to avoid errors in some backends
            if keyring.get_password(SERVICE_NAME, username) is not None:
                keyring.delete_password(SERVICE_NAME, username)
                logger.info(f"Securely deleted credential for {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete credential for {username}: {e}")
            return False


class LazySecureStorage:
    """Lazy accessor for secure storage - only accesses keyring on first use.

    This class defers keyring access until the value is actually needed,
    improving startup performance by avoiding synchronous I/O during initialization.
    """

    def __init__(self, key_name: str) -> None:
        """
        Initialize lazy storage accessor.

        Args:
            key_name: The key/username to retrieve from the keyring when accessed

        """
        self._key_name = key_name
        self._value: str | None = None
        self._loaded: bool = False

    @property
    def value(self) -> str:
        """
        Get the stored value, loading from keyring on first access.

        Returns:
            The password string if found, empty string otherwise

        """
        if not self._loaded:
            self._value = SecureStorage.get_password(self._key_name)
            self._loaded = True
            logger.debug(f"Lazy-loaded credential for {self._key_name}")
        return self._value or ""

    def __str__(self) -> str:
        """Return the value when converted to string."""
        return self.value

    def __bool__(self) -> bool:
        """Return True if the value is non-empty."""
        return bool(self.value)

    def reset(self) -> None:
        """Reset the lazy loader to fetch fresh value on next access."""
        self._value = None
        self._loaded = False
