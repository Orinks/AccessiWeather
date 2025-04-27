"""Tests for cache module."""

from unittest.mock import patch

import pytest

from accessiweather.cache import Cache

# --- Test Data ---

SAMPLE_KEY = "test_key"
SAMPLE_VALUE = "test_value"
SAMPLE_TTL = 60  # 1 minute
MOCK_TIME = 1000.0  # Base timestamp for tests

# --- Fixtures ---


@pytest.fixture
def cache():
    """Create a Cache instance with default TTL."""
    return Cache()


@pytest.fixture
def mock_time():
    """Mock time.time() to return a fixed timestamp."""
    with patch("time.time", return_value=MOCK_TIME) as mock:
        yield mock


# --- Tests ---


def test_init_default_ttl():
    """Test Cache initialization with default TTL."""
    cache = Cache()
    assert cache.default_ttl == 300  # 5 minutes


def test_init_custom_ttl():
    """Test Cache initialization with custom TTL."""
    cache = Cache(default_ttl=SAMPLE_TTL)
    assert cache.default_ttl == SAMPLE_TTL


def test_set_get_basic(cache, mock_time):
    """Test basic set and get operations."""
    cache.set(SAMPLE_KEY, SAMPLE_VALUE)
    assert cache.get(SAMPLE_KEY) == SAMPLE_VALUE


def test_get_nonexistent(cache):
    """Test getting a non-existent key."""
    assert cache.get("nonexistent") is None


def test_set_get_with_ttl(cache, mock_time):
    """Test set with custom TTL and get before expiry."""
    cache.set(SAMPLE_KEY, SAMPLE_VALUE, ttl=SAMPLE_TTL)

    # Get before expiry
    mock_time.return_value = MOCK_TIME + SAMPLE_TTL - 1
    assert cache.get(SAMPLE_KEY) == SAMPLE_VALUE


def test_get_expired(cache, mock_time):
    """Test getting an expired value."""
    cache.set(SAMPLE_KEY, SAMPLE_VALUE, ttl=SAMPLE_TTL)

    # Get after expiry
    mock_time.return_value = MOCK_TIME + SAMPLE_TTL + 1
    assert cache.get(SAMPLE_KEY) is None

    # Verify the expired entry was removed
    assert SAMPLE_KEY not in cache.data


def test_has_key_exists(cache, mock_time):
    """Test has_key with an existing non-expired key."""
    cache.set(SAMPLE_KEY, SAMPLE_VALUE)
    assert cache.has_key(SAMPLE_KEY) is True


def test_has_key_not_exists(cache):
    """Test has_key with a non-existent key."""
    assert cache.has_key("nonexistent") is False


def test_has_key_expired(cache, mock_time):
    """Test has_key with an expired key."""
    cache.set(SAMPLE_KEY, SAMPLE_VALUE, ttl=SAMPLE_TTL)

    # Check after expiry
    mock_time.return_value = MOCK_TIME + SAMPLE_TTL + 1
    assert cache.has_key(SAMPLE_KEY) is False

    # Verify the expired entry was removed
    assert SAMPLE_KEY not in cache.data


def test_invalidate(cache, mock_time):
    """Test invalidating a cache entry."""
    cache.set(SAMPLE_KEY, SAMPLE_VALUE)
    cache.invalidate(SAMPLE_KEY)
    assert cache.get(SAMPLE_KEY) is None
    assert SAMPLE_KEY not in cache.data


def test_invalidate_nonexistent(cache):
    """Test invalidating a non-existent key."""
    cache.invalidate("nonexistent")  # Should not raise any error


def test_clear(cache, mock_time):
    """Test clearing all cache entries."""
    # Set multiple entries
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")

    cache.clear()

    assert len(cache.data) == 0
    assert cache.get("key1") is None
    assert cache.get("key2") is None
    assert cache.get("key3") is None


def test_cleanup(cache, mock_time):
    """Test cleaning up expired entries."""
    # Set some entries with different expiration times
    cache.set("expired1", "value1", ttl=10)  # Will be expired
    cache.set("expired2", "value2", ttl=20)  # Will be expired
    cache.set("valid1", "value3", ttl=100)  # Will still be valid
    cache.set("valid2", "value4", ttl=200)  # Will still be valid

    # Move time forward past some expiration times
    mock_time.return_value = MOCK_TIME + 50

    # Clean up expired entries
    cache.cleanup()

    # Check results
    assert "expired1" not in cache.data
    assert "expired2" not in cache.data
    assert cache.get("valid1") == "value3"
    assert cache.get("valid2") == "value4"
    assert len(cache.data) == 2


def test_cleanup_no_expired(cache, mock_time):
    """Test cleanup with no expired entries."""
    # Set entries that won't be expired
    cache.set("valid1", "value1", ttl=100)
    cache.set("valid2", "value2", ttl=200)

    # Move time forward but not past expiration
    mock_time.return_value = MOCK_TIME + 50

    # Clean up
    cache.cleanup()

    # Verify nothing was removed
    assert len(cache.data) == 2
    assert cache.get("valid1") == "value1"
    assert cache.get("valid2") == "value2"


def test_cleanup_all_expired(cache, mock_time):
    """Test cleanup with all entries expired."""
    # Set entries that will all expire
    cache.set("expired1", "value1", ttl=10)
    cache.set("expired2", "value2", ttl=20)

    # Move time forward past all expiration times
    mock_time.return_value = MOCK_TIME + 30

    # Clean up
    cache.cleanup()

    # Verify all entries were removed
    assert len(cache.data) == 0
