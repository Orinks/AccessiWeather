"""
Unit tests for cache module.

Tests cover:
- In-memory cache with TTL support
- Cache expiration and cleanup
- Weather data persistence and loading
- Serialization and deserialization of weather data
"""

import json
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from accessiweather.cache import (
    Cache,
    CacheEntry,
    WeatherDataCache,
    _deserialize_current,
    _deserialize_datetime,
    _deserialize_forecast,
    _safe_location_key,
    _serialize_current,
    _serialize_datetime,
    _serialize_forecast,
)
from accessiweather.models.config import Location
from accessiweather.models.weather import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
)


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Should create cache entry with value and expiration."""
        value = "test_value"
        expiration = time.time() + 300
        entry = CacheEntry(value=value, expiration=expiration)

        assert entry.value == value
        assert entry.expiration == expiration


class TestCache:
    """Test in-memory Cache with TTL support."""

    def test_cache_initialization(self):
        """Should initialize cache with default TTL."""
        cache = Cache(default_ttl=600)
        assert cache.default_ttl == 600
        assert len(cache.data) == 0

    def test_set_and_get(self):
        """Should store and retrieve values from cache."""
        cache = Cache(default_ttl=300)
        cache.set("key1", "value1")

        result = cache.get("key1")
        assert result == "value1"

    def test_get_nonexistent_key(self):
        """Should return None for nonexistent key."""
        cache = Cache()
        result = cache.get("nonexistent")
        assert result is None

    def test_set_with_custom_ttl(self):
        """Should store value with custom TTL."""
        cache = Cache(default_ttl=300)
        cache.set("key1", "value1", ttl=10)

        # Value should exist immediately
        assert cache.get("key1") == "value1"

    def test_expired_entry(self):
        """Should return None for expired entries."""
        cache = Cache(default_ttl=1)
        cache.set("key1", "value1", ttl=0.1)  # Expire in 100ms

        time.sleep(0.2)  # Wait for expiration

        result = cache.get("key1")
        assert result is None
        assert "key1" not in cache.data  # Should be removed

    def test_has_key_exists(self):
        """Should return True for existing non-expired key."""
        cache = Cache()
        cache.set("key1", "value1")

        assert cache.has_key("key1") is True

    def test_has_key_not_exists(self):
        """Should return False for nonexistent key."""
        cache = Cache()
        assert cache.has_key("nonexistent") is False

    def test_has_key_expired(self):
        """Should return False for expired key."""
        cache = Cache()
        cache.set("key1", "value1", ttl=0.1)

        time.sleep(0.2)

        assert cache.has_key("key1") is False

    def test_invalidate(self):
        """Should remove specific cache entry."""
        cache = Cache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_invalidate_nonexistent(self):
        """Should handle invalidating nonexistent key gracefully."""
        cache = Cache()
        cache.invalidate("nonexistent")  # Should not raise error

    def test_clear(self):
        """Should remove all cache entries."""
        cache = Cache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert len(cache.data) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cleanup_expired_entries(self):
        """Should remove only expired entries."""
        cache = Cache()
        cache.set("key1", "value1", ttl=0.1)  # Expires soon
        cache.set("key2", "value2", ttl=100)  # Stays valid

        time.sleep(0.2)
        cache.cleanup()

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"


class TestSerializationHelpers:
    """Test datetime and model serialization helpers."""

    def test_serialize_datetime_with_timezone(self):
        """Should serialize datetime with timezone to dict format."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = _serialize_datetime(dt)

        assert result is not None
        assert isinstance(result, dict)
        assert "iso" in result
        assert "2025-01-01" in result["iso"]
        assert "12:00:00" in result["iso"]

    def test_serialize_datetime_without_timezone(self):
        """Should add UTC timezone when missing."""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        result = _serialize_datetime(dt)

        assert result is not None
        assert isinstance(result, dict)
        assert "iso" in result
        assert "2025-01-01" in result["iso"]

    def test_serialize_datetime_none(self):
        """Should return None for None input."""
        result = _serialize_datetime(None)
        assert result is None

    def test_deserialize_datetime_valid(self):
        """Should deserialize valid ISO datetime string."""
        dt_str = "2025-01-01T12:00:00+00:00"
        result = _deserialize_datetime(dt_str)

        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 1

    def test_deserialize_datetime_none(self):
        """Should return None for None input."""
        assert _deserialize_datetime(None) is None

    def test_deserialize_datetime_empty_string(self):
        """Should return None for empty string."""
        assert _deserialize_datetime("") is None
        assert _deserialize_datetime("   ") is None

    def test_deserialize_datetime_invalid(self):
        """Should return None for invalid datetime string."""
        assert _deserialize_datetime("not a date") is None
        assert _deserialize_datetime("2025-13-01") is None

    def test_safe_location_key(self):
        """Should create safe filename from location."""
        location = Location(name="New York, NY", latitude=40.7128, longitude=-74.0060)
        key = _safe_location_key(location)

        assert key is not None
        assert len(key) > 0
        # Should not contain special characters that are problematic in filenames
        assert "/" not in key
        assert "\\" not in key
        assert ":" not in key

    def test_safe_location_key_special_chars(self):
        """Should handle location names with special characters."""
        location = Location(name="São Paulo, Brazil!", latitude=-23.5505, longitude=-46.6333)
        key = _safe_location_key(location)

        assert key is not None
        assert len(key) > 0


class TestWeatherDataSerialization:
    """Test serialization of weather data models."""

    def test_serialize_current_conditions(self):
        """Should serialize CurrentConditions to dict."""
        current = CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Partly Cloudy",
            humidity=65,
            wind_speed_mph=10.0,
            wind_direction="NW",
        )

        result = _serialize_current(current)

        assert result is not None
        assert result["temperature_f"] == 72.0
        assert result["temperature_c"] == 22.2
        assert result["condition"] == "Partly Cloudy"
        assert result["humidity"] == 65

    def test_serialize_current_conditions_none(self):
        """Should return None for None input."""
        result = _serialize_current(None)
        assert result is None

    def test_deserialize_current_conditions(self):
        """Should deserialize dict to CurrentConditions."""
        data = {
            "temperature_f": 72.0,
            "temperature_c": 22.2,
            "condition": "Partly Cloudy",
            "humidity": 65,
        }

        result = _deserialize_current(data)

        assert result is not None
        assert result.temperature_f == 72.0
        assert result.temperature_c == 22.2
        assert result.condition == "Partly Cloudy"
        assert result.humidity == 65

    def test_deserialize_current_conditions_none(self):
        """Should return None for None input."""
        result = _deserialize_current(None)
        assert result is None

    def test_deserialize_current_conditions_invalid(self):
        """Should return None for invalid input."""
        result = _deserialize_current("not a dict")
        assert result is None

    def test_serialize_forecast(self):
        """Should serialize Forecast with periods."""
        period = ForecastPeriod(
            name="Tonight",
            temperature=55,
            temperature_unit="F",
            short_forecast="Clear",
        )
        forecast = Forecast(periods=[period], generated_at=datetime.now(UTC))

        result = _serialize_forecast(forecast)

        assert result is not None
        assert "periods" in result
        assert len(result["periods"]) == 1
        assert result["periods"][0]["name"] == "Tonight"

    def test_serialize_forecast_none(self):
        """Should return None for None input."""
        result = _serialize_forecast(None)
        assert result is None

    def test_deserialize_forecast(self):
        """Should deserialize dict to Forecast."""
        data = {
            "periods": [
                {
                    "name": "Tonight",
                    "temperature": 55,
                    "temperature_unit": "F",
                    "short_forecast": "Clear",
                }
            ],
            "generated_at": "2025-01-01T12:00:00+00:00",
        }

        result = _deserialize_forecast(data)

        assert result is not None
        assert len(result.periods) == 1
        assert result.periods[0].name == "Tonight"

    def test_deserialize_forecast_none(self):
        """Should return None for None input."""
        result = _deserialize_forecast(None)
        assert result is None


class TestWeatherDataCache:
    """Test persistent weather data cache."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary directory for cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_location(self):
        """Create sample location."""
        return Location(name="Test City", latitude=40.7128, longitude=-74.0060)

    @pytest.fixture
    def sample_weather_data(self, sample_location):
        """Create sample weather data."""
        from accessiweather.models import WeatherData

        current = CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Partly Cloudy",
            humidity=65,
        )

        return WeatherData(location=sample_location, current=current)

    def test_cache_initialization(self, temp_cache_dir):
        """Should initialize cache directory."""
        cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=180)

        assert cache.cache_dir == temp_cache_dir
        assert cache.cache_dir.exists()
        assert cache.max_age == timedelta(minutes=180)

    def test_cache_initialization_creates_dir(self):
        """Should create cache directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "subdir" / "cache"
            cache = WeatherDataCache(cache_dir=cache_path)

            assert cache.cache_dir.exists()

    def test_store_weather_data(self, temp_cache_dir, sample_location, sample_weather_data):
        """Should persist weather data to file."""
        cache = WeatherDataCache(cache_dir=temp_cache_dir)
        cache.store(sample_location, sample_weather_data)

        # Verify file was created
        cache_files = list(temp_cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        # Verify content
        with cache_files[0].open() as f:
            data = json.load(f)
            assert data["schema_version"] == 5
            assert "saved_at" in data
            assert data["location"]["name"] == "Test City"

    def test_load_weather_data(self, temp_cache_dir, sample_location, sample_weather_data):
        """Should load persisted weather data."""
        cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=180)

        # Store data first
        cache.store(sample_location, sample_weather_data)

        # Load it back
        loaded = cache.load(sample_location, allow_stale=False)

        assert loaded is not None
        assert loaded.location.name == "Test City"
        assert loaded.current is not None
        assert loaded.current.temperature_f == 72.0

    def test_load_nonexistent_location(self, temp_cache_dir, sample_location):
        """Should return None for nonexistent cache file."""
        cache = WeatherDataCache(cache_dir=temp_cache_dir)
        loaded = cache.load(sample_location)

        assert loaded is None

    def test_load_expired_data_allow_stale(
        self, temp_cache_dir, sample_location, sample_weather_data
    ):
        """Should load expired data when allow_stale=True."""
        cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=0)

        # Store data
        cache.store(sample_location, sample_weather_data)

        time.sleep(0.1)  # Make data "old"

        # Load with allow_stale=True
        loaded = cache.load(sample_location, allow_stale=True)

        assert loaded is not None
        assert loaded.stale is True

    def test_load_expired_data_disallow_stale(
        self, temp_cache_dir, sample_location, sample_weather_data
    ):
        """Should not load expired data when allow_stale=False."""
        cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=0)

        # Store data
        cache.store(sample_location, sample_weather_data)

        time.sleep(0.1)  # Make data "old"

        # Load with allow_stale=False
        loaded = cache.load(sample_location, allow_stale=False)

        assert loaded is None

    def test_purge_expired(self, temp_cache_dir, sample_location):
        """Should remove expired cache files."""
        cache = WeatherDataCache(cache_dir=temp_cache_dir, max_age_minutes=0)

        # Create an old cache file manually
        from accessiweather.models import WeatherData

        weather = WeatherData(location=sample_location)
        cache.store(sample_location, weather)

        time.sleep(0.1)

        # Purge expired
        cache.purge_expired()

        # Verify file was removed
        cache_files = list(temp_cache_dir.glob("*.json"))
        assert len(cache_files) == 0

    def test_store_with_exception_handling(self, temp_cache_dir):
        """Should handle exceptions gracefully when storing."""
        cache = WeatherDataCache(cache_dir=temp_cache_dir)

        # Create invalid data that might cause serialization issues
        from accessiweather.models import WeatherData

        location = Location(name="Test", latitude=0, longitude=0)
        weather = WeatherData(location=location)

        # Should not raise exception
        cache.store(location, weather)


class TestCacheEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_cache_with_zero_ttl(self):
        """Should handle zero TTL correctly."""
        cache = Cache(default_ttl=0)
        cache.set("key1", "value1")

        # Should expire immediately
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_cache_with_very_large_ttl(self):
        """Should handle very large TTL values."""
        cache = Cache(default_ttl=31536000)  # 1 year
        cache.set("key1", "value1")

        assert cache.get("key1") == "value1"

    def test_cache_multiple_operations(self):
        """Should handle multiple operations correctly."""
        cache = Cache()

        # Set multiple values
        for i in range(100):
            cache.set(f"key{i}", f"value{i}")

        # Verify all values
        for i in range(100):
            assert cache.get(f"key{i}") == f"value{i}"

        # Clear and verify
        cache.clear()
        assert len(cache.data) == 0

    def test_cache_overwrite_value(self):
        """Should overwrite existing values correctly."""
        cache = Cache()
        cache.set("key1", "value1")
        cache.set("key1", "value2")

        assert cache.get("key1") == "value2"
