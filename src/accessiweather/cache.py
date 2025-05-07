"""Cache module for AccessiWeather.

This module provides caching functionality to reduce API calls and improve performance.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cache entry with value and expiration time."""

    value: Any
    expiration: float  # Expiration time as Unix timestamp


class Cache:
    """A simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 300):
        """Initialize the cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 5 minutes)
        """
        self.data: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        logger.debug(f"Initialized cache with default TTL of {default_ttl} seconds")

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found or expired
        """
        if key not in self.data:
            return None

        entry = self.data[key]
        current_time = time.time()

        # Check if the entry has expired
        if entry.expiration < current_time:
            logger.debug(f"Cache entry for '{key}' has expired")
            # Remove the expired entry
            del self.data[key]
            return None

        logger.debug(f"Cache hit for '{key}'")
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds (uses default_ttl if None)
        """
        if ttl is None:
            ttl = self.default_ttl

        expiration = time.time() + ttl
        self.data[key] = CacheEntry(value=value, expiration=expiration)
        logger.debug(f"Cached value for '{key}' with TTL of {ttl} seconds")

    def has_key(self, key: str) -> bool:
        """Check if a key exists in the cache and is not expired.

        Args:
            key: The cache key

        Returns:
            True if the key exists and is not expired, False otherwise
        """
        if key not in self.data:
            return False

        entry = self.data[key]
        current_time = time.time()

        # Check if the entry has expired
        if entry.expiration < current_time:
            # Remove the expired entry
            del self.data[key]
            return False

        return True

    def invalidate(self, key: str) -> None:
        """Invalidate a specific cache entry.

        Args:
            key: The cache key to invalidate
        """
        if key in self.data:
            del self.data[key]
            logger.debug(f"Invalidated cache entry for '{key}'")

    def clear(self) -> None:
        """Clear all cache entries."""
        self.data.clear()
        logger.debug("Cleared all cache entries")

    def cleanup(self) -> None:
        """Remove all expired entries from the cache."""
        current_time = time.time()
        expired_keys = [key for key, entry in self.data.items() if entry.expiration < current_time]

        for key in expired_keys:
            del self.data[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
