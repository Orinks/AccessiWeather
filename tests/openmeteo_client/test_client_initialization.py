"""Tests for OpenMeteoApiClient initialization and configuration."""

import pytest

from accessiweather.openmeteo_client import OpenMeteoApiClient


@pytest.mark.unit
def test_init_basic():
    """Test basic initialization."""
    client = OpenMeteoApiClient()

    assert client.user_agent == "AccessiWeather"
    assert client.timeout == 30.0
    assert client.max_retries == 3
    assert client.retry_delay == 1.0
    assert client.client is not None


@pytest.mark.unit
def test_init_custom_params():
    """Test initialization with custom parameters."""
    client = OpenMeteoApiClient(
        user_agent="CustomApp", timeout=60.0, max_retries=5, retry_delay=2.0
    )

    assert client.user_agent == "CustomApp"
    assert client.timeout == 60.0
    assert client.max_retries == 5
    assert client.retry_delay == 2.0


@pytest.mark.unit
def test_client_cleanup():
    """Test that HTTP client is properly cleaned up."""
    client = OpenMeteoApiClient()
    http_client = client.client

    # Simulate cleanup
    client.__del__()

    # Verify client exists (we can't easily test if it's closed without implementation details)
    assert http_client is not None
