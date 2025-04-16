"""Tests for the cache module."""

import time

from accessiweather.cache import Cache


class TestCache:
    """Test suite for the Cache class."""

    def test_init(self):
        """Test cache initialization."""
        cache = Cache()
        assert cache.data == {}
        assert cache.default_ttl == 300  # Default TTL should be 5 minutes

        # Test with custom TTL
        cache = Cache(default_ttl=600)
        assert cache.default_ttl == 600

    def test_get_nonexistent_key(self):
        """Test getting a nonexistent key."""
        cache = Cache()
        assert cache.get("nonexistent") is None

    def test_set_and_get(self):
        """Test setting and getting a value."""
        cache = Cache()
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

    def test_set_with_ttl(self):
        """Test setting a value with a specific TTL."""
        cache = Cache()
        cache.set("test_key", "test_value", ttl=10)
        assert cache.get("test_key") == "test_value"

    def test_expired_entry(self):
        """Test that expired entries are not returned."""
        cache = Cache()
        # Set with a very short TTL
        cache.set("test_key", "test_value", ttl=0.1)
        # Wait for the entry to expire
        time.sleep(0.2)
        assert cache.get("test_key") is None

    def test_has_key(self):
        """Test checking if a key exists."""
        cache = Cache()
        assert not cache.has_key("test_key")
        cache.set("test_key", "test_value")
        assert cache.has_key("test_key")

    def test_has_key_expired(self):
        """Test that has_key returns False for expired entries."""
        cache = Cache()
        cache.set("test_key", "test_value", ttl=0.1)
        time.sleep(0.2)
        assert not cache.has_key("test_key")

    def test_invalidate(self):
        """Test invalidating a specific key."""
        cache = Cache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.invalidate("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_clear(self):
        """Test clearing the entire cache."""
        cache = Cache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.data == {}

    def test_cleanup(self):
        """Test that cleanup removes expired entries."""
        cache = Cache()
        cache.set("key1", "value1", ttl=0.1)
        cache.set("key2", "value2")
        time.sleep(0.2)
        # Before cleanup, the expired entry is still in the data dict
        assert "key1" in cache.data
        cache.cleanup()
        # After cleanup, the expired entry should be removed
        assert "key1" not in cache.data
        assert "key2" in cache.data
