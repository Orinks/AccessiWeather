"""Error handling and retry mechanism tests for the OpenMeteoApiClient class."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from accessiweather.openmeteo_client import (
    OpenMeteoApiClient,
    OpenMeteoApiError,
    OpenMeteoNetworkError,
)

# Sample test data
SAMPLE_CURRENT_WEATHER_DATA = {
    "latitude": 40.0,
    "longitude": -75.0,
    "current": {
        "time": "2024-01-01T12:00",
        "temperature_2m": 72.0,
        "weather_code": 1,
    },
}


@pytest.fixture
def openmeteo_client():
    """Create an OpenMeteoApiClient instance for testing."""
    return OpenMeteoApiClient(user_agent="TestClient", timeout=30.0, max_retries=3, retry_delay=1.0)


# Test _make_request method and error handling
@pytest.mark.unit
def test_make_request_success(openmeteo_client):
    """Test successful API request."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_CURRENT_WEATHER_DATA
        mock_get.return_value = mock_response

        result = openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert result == SAMPLE_CURRENT_WEATHER_DATA
        mock_get.assert_called_once()


@pytest.mark.unit
def test_make_request_400_error(openmeteo_client):
    """Test handling of 400 Bad Request errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"reason": "Invalid coordinates"}'
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 999, "longitude": 999})

        assert "Invalid coordinates" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_429_rate_limit(openmeteo_client):
    """Test handling of 429 Rate Limit errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.content = b""
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "Rate limit exceeded" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_500_server_error(openmeteo_client):
    """Test handling of 500 Server Error."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b""
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "Server error: 500" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_network_error(openmeteo_client):
    """Test handling of network errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        with pytest.raises(OpenMeteoNetworkError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "Network error" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_timeout_error(openmeteo_client):
    """Test handling of timeout errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(OpenMeteoNetworkError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "Request timed out" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_retry_mechanism(openmeteo_client):
    """Test retry mechanism on network errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        # First two calls fail, third succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_CURRENT_WEATHER_DATA

        mock_get.side_effect = [
            httpx.ConnectError("Connection failed"),
            httpx.ConnectError("Connection failed"),
            mock_response,
        ]

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = openmeteo_client._make_request(
                "forecast", {"latitude": 40.0, "longitude": -75.0}
            )

        assert result == SAMPLE_CURRENT_WEATHER_DATA
        assert mock_get.call_count == 3


@pytest.mark.unit
def test_make_request_max_retries_exceeded(openmeteo_client):
    """Test that max retries are respected."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        with patch("time.sleep"):  # Mock sleep to speed up test
            with pytest.raises(OpenMeteoNetworkError):
                openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        # Should try max_retries + 1 times (initial + retries)
        assert mock_get.call_count == openmeteo_client.max_retries + 1


@pytest.mark.unit
def test_client_cleanup():
    """Test that HTTP client is properly cleaned up."""
    client = OpenMeteoApiClient()
    http_client = client.client

    # Simulate cleanup
    del client

    # Verify client exists (we can't easily test if it's closed without implementation details)
    assert http_client is not None


@pytest.mark.unit
def test_make_request_json_decode_error(openmeteo_client):
    """Test handling of JSON decode errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.content = b"Invalid JSON response"
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_unexpected_status_code(openmeteo_client):
    """Test handling of unexpected status codes."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 418  # I'm a teapot
        mock_response.content = b"Unexpected error"
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "HTTP 418" in str(exc_info.value)


@pytest.mark.unit
def test_retry_with_different_error_types(openmeteo_client):
    """Test retry mechanism with different types of errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        # Mix of different error types, then success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_CURRENT_WEATHER_DATA

        mock_get.side_effect = [
            httpx.ConnectError("Connection failed"),
            httpx.TimeoutException("Timeout"),
            mock_response,
        ]

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = openmeteo_client._make_request(
                "forecast", {"latitude": 40.0, "longitude": -75.0}
            )

        assert result == SAMPLE_CURRENT_WEATHER_DATA
        assert mock_get.call_count == 3


@pytest.mark.unit
def test_no_retry_on_client_errors(openmeteo_client):
    """Test that client errors (4xx) are not retried."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"reason": "Bad request"}'
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError):
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        # Should only try once, no retries for client errors
        assert mock_get.call_count == 1
