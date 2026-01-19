"""
Tests for the cache module.

Tests the in-memory Cache and file-based WeatherDataCache classes.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from accessiweather.cache import Cache, WeatherDataCache
from accessiweather.models import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    Location,
    WeatherAlerts,
    WeatherData,
)


class TestCache:
    """Tests for the in-memory Cache class."""

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = Cache(default_ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key_returns_none(self):
        """Test that getting a missing key returns None."""
        cache = Cache()
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        """Test that expired entries return None."""
        cache = Cache(default_ttl=0.01)  # 10ms TTL
        cache.set("key", "value")
        time.sleep(0.02)  # Wait for expiration
        assert cache.get("key") is None

    def test_custom_ttl(self):
        """Test setting a custom TTL."""
        cache = Cache(default_ttl=60)
        cache.set("key", "value", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("key") is None

    def test_has_key(self):
        """Test has_key method."""
        cache = Cache()
        cache.set("exists", "value")
        assert cache.has_key("exists") is True
        assert cache.has_key("missing") is False

    def test_invalidate(self):
        """Test invalidating a specific key."""
        cache = Cache()
        cache.set("key", "value")
        cache.invalidate("key")
        assert cache.get("key") is None

    def test_clear(self):
        """Test clearing all entries."""
        cache = Cache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cleanup_removes_expired(self):
        """Test cleanup removes expired entries."""
        cache = Cache(default_ttl=0.01)
        cache.set("key1", "value1")
        cache.set("key2", "value2", ttl=60)  # Long TTL
        time.sleep(0.02)
        cache.cleanup()
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"


class TestWeatherDataCache:
    """Tests for the file-based WeatherDataCache class."""

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create a temporary cache directory."""
        return tmp_path / "weather_cache"

    @pytest.fixture
    def cache(self, cache_dir):
        """Create a WeatherDataCache instance."""
        return WeatherDataCache(cache_dir, max_age_minutes=60)

    @pytest.fixture
    def location(self):
        """Create a test location."""
        return Location(name="Test City", latitude=40.0, longitude=-74.0)

    @pytest.fixture
    def weather_data(self, location):
        """Create test weather data."""
        return WeatherData(
            location=location,
            current=CurrentConditions(
                temperature_f=72.0,
                temperature_c=22.2,
                condition="Sunny",
            ),
            forecast=Forecast(
                periods=[
                    ForecastPeriod(
                        name="Today",
                        temperature=75,
                        temperature_unit="F",
                        short_forecast="Sunny",
                    )
                ],
                generated_at=datetime.now(UTC),
            ),
            alerts=WeatherAlerts(alerts=[]),
        )

    def test_store_and_load(self, cache, location, weather_data):
        """Test storing and loading weather data."""
        cache.store(location, weather_data)
        loaded = cache.load(location)

        assert loaded is not None
        assert loaded.current.temperature_f == 72.0
        assert loaded.current.condition == "Sunny"

    def test_load_missing_returns_none(self, cache, location):
        """Test loading non-existent data returns None."""
        result = cache.load(location)
        assert result is None

    def test_invalidate(self, cache, location, weather_data):
        """Test invalidating a cache entry."""
        cache.store(location, weather_data)
        cache.invalidate(location)
        assert cache.load(location) is None

    def test_stale_data_marked(self, cache, location, weather_data):
        """Test that old data is marked as stale."""
        # Use a very short max age
        short_cache = WeatherDataCache(cache.cache_dir, max_age_minutes=0)
        short_cache.store(location, weather_data)
        time.sleep(0.1)  # Let some time pass

        loaded = short_cache.load(location, allow_stale=True)
        assert loaded is not None
        assert loaded.stale is True

    def test_strict_load_rejects_stale(self, cache, location, weather_data):
        """Test that strict load rejects stale data."""
        short_cache = WeatherDataCache(cache.cache_dir, max_age_minutes=0)
        short_cache.store(location, weather_data)
        time.sleep(0.1)

        loaded = short_cache.load(location, allow_stale=False)
        assert loaded is None

    def test_purge_expired(self, tmp_path, location, weather_data):
        """Test purging expired cache entries."""
        cache = WeatherDataCache(tmp_path / "cache", max_age_minutes=0)
        cache.store(location, weather_data)
        time.sleep(0.1)
        cache.purge_expired()
        # File should be deleted after purge
        assert cache.load(location, allow_stale=True) is None
