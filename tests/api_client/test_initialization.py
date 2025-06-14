"""Tests for NoaaApiClient initialization."""

import pytest

from accessiweather.api_client import NoaaApiClient


@pytest.mark.unit
def test_init_basic():
    """Test basic initialization without caching."""
    client = NoaaApiClient(user_agent="TestClient")

    assert client.user_agent == "TestClient"
    assert client.headers["User-Agent"] == "TestClient (TestClient)"
    assert client.cache is None


@pytest.mark.unit
def test_init_with_contact():
    """Test initialization with contact info."""
    client = NoaaApiClient(user_agent="TestClient", contact_info="test@example.com")

    assert client.headers["User-Agent"] == "TestClient (test@example.com)"


@pytest.mark.unit
def test_init_with_caching():
    """Test initialization with caching enabled."""
    client = NoaaApiClient(user_agent="TestClient", enable_caching=True, cache_ttl=300)

    assert client.cache is not None
    assert client.cache.default_ttl == 300


@pytest.mark.unit
def test_init_with_custom_timeout():
    """Test initialization with custom timeout."""
    client = NoaaApiClient(user_agent="TestClient", timeout=30)

    assert client.timeout == 30


@pytest.mark.unit
def test_init_with_custom_rate_limit():
    """Test initialization with custom rate limit interval."""
    client = NoaaApiClient(user_agent="TestClient", min_request_interval=2.0)

    assert client.min_request_interval == 2.0


@pytest.mark.unit
def test_init_with_all_parameters():
    """Test initialization with all parameters."""
    client = NoaaApiClient(
        user_agent="TestClient",
        contact_info="test@example.com",
        enable_caching=True,
        cache_ttl=600,
        timeout=45,
        min_request_interval=1.5,
    )

    assert client.user_agent == "TestClient"
    assert client.headers["User-Agent"] == "TestClient (test@example.com)"
    assert client.cache is not None
    assert client.cache.default_ttl == 600
    assert client.timeout == 45
    assert client.min_request_interval == 1.5


@pytest.mark.unit
def test_init_default_values():
    """Test that default values are set correctly."""
    client = NoaaApiClient(user_agent="TestClient")

    # Check default values
    assert client.timeout == 30  # Default timeout
    assert client.min_request_interval == 1.0  # Default rate limit
    assert client.cache is None  # Caching disabled by default
    assert "User-Agent" in client.headers
    assert client.base_url == "https://api.weather.gov"


@pytest.mark.unit
def test_init_headers_format():
    """Test that headers are formatted correctly."""
    # Test with contact info
    client_with_contact = NoaaApiClient(
        user_agent="MyApp/1.0", contact_info="developer@example.com"
    )
    expected_ua = "MyApp/1.0 (developer@example.com)"
    assert client_with_contact.headers["User-Agent"] == expected_ua

    # Test without contact info
    client_without_contact = NoaaApiClient(user_agent="MyApp/1.0")
    expected_ua_no_contact = "MyApp/1.0 (MyApp/1.0)"
    assert client_without_contact.headers["User-Agent"] == expected_ua_no_contact


@pytest.mark.unit
def test_init_cache_configuration():
    """Test cache configuration options."""
    # Test with default cache TTL
    client_default_ttl = NoaaApiClient(user_agent="TestClient", enable_caching=True)
    assert client_default_ttl.cache is not None
    # Default TTL should be set (typically 300 seconds)
    assert hasattr(client_default_ttl.cache, "default_ttl")

    # Test with custom cache TTL
    custom_ttl = 1200
    client_custom_ttl = NoaaApiClient(
        user_agent="TestClient", enable_caching=True, cache_ttl=custom_ttl
    )
    assert client_custom_ttl.cache is not None
    assert client_custom_ttl.cache.default_ttl == custom_ttl


@pytest.mark.unit
def test_init_invalid_parameters():
    """Test initialization with invalid parameters."""
    # Test with negative timeout
    with pytest.raises(ValueError):
        NoaaApiClient(user_agent="TestClient", timeout=-1)

    # Test with negative rate limit interval
    with pytest.raises(ValueError):
        NoaaApiClient(user_agent="TestClient", min_request_interval=-1)

    # Test with negative cache TTL
    with pytest.raises(ValueError):
        NoaaApiClient(user_agent="TestClient", enable_caching=True, cache_ttl=-1)


@pytest.mark.unit
def test_init_empty_user_agent():
    """Test initialization with empty user agent."""
    with pytest.raises(ValueError):
        NoaaApiClient(user_agent="")


@pytest.mark.unit
def test_init_none_user_agent():
    """Test initialization with None user agent."""
    with pytest.raises(TypeError):
        NoaaApiClient(user_agent=None)


@pytest.mark.unit
def test_init_base_url_configuration():
    """Test that base URL is configured correctly."""
    client = NoaaApiClient(user_agent="TestClient")

    assert client.base_url == "https://api.weather.gov"
    assert client.base_url.endswith("weather.gov")
    assert client.base_url.startswith("https://")


@pytest.mark.unit
def test_init_session_configuration():
    """Test that client configuration is correct."""
    client = NoaaApiClient(user_agent="TestClient", timeout=25)

    # Client should have the correct timeout
    assert client.timeout == 25
    # Headers should be set correctly
    assert "User-Agent" in client.headers


@pytest.mark.unit
def test_init_multiple_instances():
    """Test that multiple client instances are independent."""
    client1 = NoaaApiClient(user_agent="Client1", timeout=30)
    client2 = NoaaApiClient(user_agent="Client2", timeout=60, enable_caching=True)

    # Instances should be independent
    assert client1.user_agent != client2.user_agent
    assert client1.timeout != client2.timeout
    assert client1.cache is None
    assert client2.cache is not None
    assert client1.headers["User-Agent"] != client2.headers["User-Agent"]
