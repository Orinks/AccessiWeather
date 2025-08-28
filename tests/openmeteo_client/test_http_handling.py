"""Tests for OpenMeteoApiClient HTTP handling and error management."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from accessiweather.openmeteo_client import OpenMeteoApiError, OpenMeteoNetworkError

from .conftest import SAMPLE_CURRENT_WEATHER_DATA


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
        mock_response.json.return_value = {"reason": "Invalid coordinates"}
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

        with patch("time.sleep"), pytest.raises(OpenMeteoNetworkError):
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        # Should try max_retries + 1 times (initial + retries)
        assert mock_get.call_count == openmeteo_client.max_retries + 1
