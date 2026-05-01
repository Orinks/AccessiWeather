"""
Cache module for AccessiWeather.

This module provides caching functionality to reduce API calls and improve performance.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .cache_serialization import (
    _deserialize_alert,  # noqa: F401 - compatibility re-export for existing tests/callers
    _deserialize_datetime,
    _deserialize_weather_data,
    _safe_location_key,
    _serialize_alert,  # noqa: F401 - compatibility re-export for existing tests/callers
    _serialize_datetime,
    _serialize_weather_data,
)
from .models import Location, WeatherData

logger = logging.getLogger(__name__)

# Cache schema version - increment this when cache data structure changes
# This is independent of app version and allows test builds to invalidate old cache
CACHE_SCHEMA_VERSION = 6


@dataclass
class CacheEntry:
    """A cache entry with value and expiration time."""

    value: Any
    expiration: float  # Expiration time as Unix timestamp


class Cache:
    """A simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 300):
        """
        Initialize the cache.

        Args:
        ----
            default_ttl: Default time-to-live in seconds (default: 5 minutes)

        """
        self.data: dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        logger.debug(f"Initialized cache with default TTL of {default_ttl} seconds")

    def get(self, key: str) -> Any | None:
        """
        Get a value from the cache.

        Args:
        ----
            key: The cache key

        Returns:
        -------
            The cached value or None if not found or expired

        """
        if key not in self.data:
            logger.debug(f"Cache miss for '{key}'")
            return None

        entry = self.data[key]
        current_time = time.time()

        # Check if the entry has expired
        if entry.expiration < current_time:
            logger.debug(f"Cache entry for '{key}' has expired")
            # Remove the expired entry
            del self.data[key]
            return None

        logger.debug(f"Cache hit for '{key}' (expires in {int(entry.expiration - current_time)}s)")
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """
        Set a value in the cache.

        Args:
        ----
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
        """
        Check if a key exists in the cache and is not expired.

        Args:
        ----
            key: The cache key

        Returns:
        -------
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
        """
        Invalidate a specific cache entry.

        Args:
        ----
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


class WeatherDataCache:
    """Persist the latest weather data per location for offline fallback."""

    def __init__(self, cache_dir: str | Path, max_age_minutes: int = 180):
        """
        Initialize the cache.

        Args:
        ----
            cache_dir: Directory where cache files are stored.
            max_age_minutes: Age threshold before cached entries expire.

        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age = timedelta(minutes=max_age_minutes)

    def store(self, location: Location, weather: WeatherData) -> None:
        try:
            payload = {
                "schema_version": CACHE_SCHEMA_VERSION,
                "saved_at": _serialize_datetime(datetime.now(UTC)),
                "location": {
                    "name": location.name,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    **({"country_code": location.country_code} if location.country_code else {}),
                },
                "weather": _serialize_weather_data(weather),
            }
            path = self._path_for_location(location)
            with path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to persist weather cache: {exc}")

    def load(self, location: Location, *, allow_stale: bool = True) -> WeatherData | None:
        path = self._path_for_location(location)
        if not path.exists():
            return None

        try:
            with path.open(encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to read cached weather data: {exc}")
            return None

        # Validate cache schema version
        cached_schema_version = payload.get("schema_version", 1)
        if cached_schema_version != CACHE_SCHEMA_VERSION:
            logger.debug(
                f"Cache schema version mismatch for {location.name}: "
                f"cached={cached_schema_version}, current={CACHE_SCHEMA_VERSION}. "
                f"Invalidating cache."
            )
            path.unlink(missing_ok=True)
            return None

        saved_at = _deserialize_datetime(payload.get("saved_at")) or datetime.now(UTC)
        age = datetime.now(UTC) - saved_at
        if not allow_stale and age > self.max_age:
            return None

        location_data = payload.get("location") or {}
        loc_name = location_data.get("name", location.name)
        loc_lat = location_data.get("latitude", location.latitude)
        loc_lon = location_data.get("longitude", location.longitude)
        normalized_location = Location(
            name=loc_name,
            latitude=loc_lat,
            longitude=loc_lon,
            country_code=location_data.get("country_code"),
        )

        weather_payload = payload.get("weather")
        if not isinstance(weather_payload, dict):
            return None

        weather = _deserialize_weather_data(weather_payload, normalized_location)
        weather.stale = age > self.max_age
        weather.stale_since = saved_at
        weather.stale_reason = "Cached data"
        return weather

    def purge_expired(self) -> None:
        now = datetime.now(UTC)
        for path in self.cache_dir.glob("*.json"):
            try:
                with path.open(encoding="utf-8") as fh:
                    payload = json.load(fh)
                saved_at = _deserialize_datetime(payload.get("saved_at")) or now
                if now - saved_at > self.max_age * 2:
                    path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                path.unlink(missing_ok=True)

    def invalidate(self, location: Location) -> None:
        """
        Invalidate cache entry for a specific location.

        Args:
        ----
            location: The location to invalidate cache for

        """
        path = self._path_for_location(location)
        if path.exists():
            path.unlink(missing_ok=True)
            logger.debug(f"Invalidated cache for location '{location.name}'")

    def _path_for_location(self, location: Location) -> Path:
        filename = f"{_safe_location_key(location)}.json"
        return self.cache_dir / filename
