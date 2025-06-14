"""Tests for NoaaApiWrapper API request functionality."""

from unittest.mock import patch

import pytest

from accessiweather.api_client import NoaaApiError
from tests.api_wrapper_test_utils import SAMPLE_POINT_DATA, MockUnexpectedStatus, api_wrapper


def test_make_api_request_success(api_wrapper):
    """Test successful API request using _make_api_request."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.return_value = SAMPLE_POINT_DATA

        result = api_wrapper._make_api_request("points/40.0,-75.0")

        assert result == SAMPLE_POINT_DATA
        mock_point.assert_called_once()


def test_make_api_request_unexpected_status(api_wrapper):
    """Test handling of UnexpectedStatus exceptions in _make_api_request."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = MockUnexpectedStatus(404)

        with pytest.raises(NoaaApiError) as exc_info:
            api_wrapper._make_api_request("points/40.0,-75.0")

        assert exc_info.value.error_type == NoaaApiError.CLIENT_ERROR


def test_make_api_request_rate_limit(api_wrapper):
    """Test handling of rate limit (429) errors in _make_api_request."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = MockUnexpectedStatus(429)

        with pytest.raises(NoaaApiError) as exc_info:
            api_wrapper._make_api_request("points/40.0,-75.0")

        assert exc_info.value.error_type == NoaaApiError.RATE_LIMIT_ERROR


def test_make_api_request_server_error(api_wrapper):
    """Test handling of server errors in _make_api_request."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = MockUnexpectedStatus(500)

        with pytest.raises(NoaaApiError) as exc_info:
            api_wrapper._make_api_request("points/40.0,-75.0")

        assert exc_info.value.error_type == NoaaApiError.SERVER_ERROR


def test_make_api_request_network_error(api_wrapper):
    """Test handling of network errors in _make_api_request."""
    import httpx

    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = httpx.RequestError("Network error")

        with pytest.raises(NoaaApiError) as exc_info:
            api_wrapper._make_api_request("points/40.0,-75.0")

        assert exc_info.value.error_type == NoaaApiError.NETWORK_ERROR


def test_make_api_request_timeout(api_wrapper):
    """Test handling of timeout errors in _make_api_request."""
    import httpx

    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(NoaaApiError) as exc_info:
            api_wrapper._make_api_request("points/40.0,-75.0")

        assert exc_info.value.error_type == NoaaApiError.TIMEOUT_ERROR


@pytest.mark.unit
def test_api_request_with_custom_headers(api_wrapper):
    """Test API requests include custom headers."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.return_value = SAMPLE_POINT_DATA

        # Make a request
        api_wrapper._make_api_request("points/40.0,-75.0")

        # Verify the client was called with the correct headers
        mock_point.assert_called_once()
        # The client should have been initialized with proper headers
        assert "User-Agent" in api_wrapper.client._headers


@pytest.mark.unit
def test_api_request_with_parameters(api_wrapper):
    """Test API requests with query parameters."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.return_value = SAMPLE_POINT_DATA

        # Make a request with parameters
        result = api_wrapper._make_api_request("points/40.0,-75.0", {"units": "us"})

        assert result == SAMPLE_POINT_DATA
        mock_point.assert_called_once()


@pytest.mark.unit
def test_api_request_retry_on_failure(api_wrapper):
    """Test API request retry behavior on transient failures."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        # First call fails with server error, second succeeds
        mock_point.side_effect = [MockUnexpectedStatus(503), SAMPLE_POINT_DATA]

        # Current implementation doesn't have automatic retry
        with pytest.raises(NoaaApiError):
            api_wrapper._make_api_request("points/40.0,-75.0")


@pytest.mark.unit
def test_api_request_with_invalid_endpoint(api_wrapper):
    """Test API request with invalid endpoint."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = MockUnexpectedStatus(404)

        with pytest.raises(NoaaApiError) as exc_info:
            api_wrapper._make_api_request("invalid/endpoint")

        assert exc_info.value.error_type == NoaaApiError.CLIENT_ERROR


@pytest.mark.unit
def test_api_request_connection_timeout(api_wrapper):
    """Test API request with connection timeout."""
    import httpx

    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = httpx.ConnectTimeout("Connection timed out")

        with pytest.raises(NoaaApiError) as exc_info:
            api_wrapper._make_api_request("points/40.0,-75.0")

        assert exc_info.value.error_type == NoaaApiError.TIMEOUT_ERROR


@pytest.mark.unit
def test_api_request_read_timeout(api_wrapper):
    """Test API request with read timeout."""
    import httpx

    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = httpx.ReadTimeout("Read timed out")

        with pytest.raises(NoaaApiError) as exc_info:
            api_wrapper._make_api_request("points/40.0,-75.0")

        assert exc_info.value.error_type == NoaaApiError.TIMEOUT_ERROR


@pytest.mark.unit
def test_api_request_with_malformed_response(api_wrapper):
    """Test API request with malformed response data."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        # Return malformed data
        mock_point.return_value = "invalid json response"

        # Should handle malformed response gracefully
        result = api_wrapper._make_api_request("points/40.0,-75.0")
        assert result == "invalid json response"


@pytest.mark.unit
def test_api_request_with_empty_response(api_wrapper):
    """Test API request with empty response."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.return_value = None

        result = api_wrapper._make_api_request("points/40.0,-75.0")
        assert result is None


@pytest.mark.unit
def test_api_request_with_large_response(api_wrapper):
    """Test API request with large response data."""
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        # Create a large response
        large_response = {
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
                "data": ["item"] * 10000,  # Large array
            }
        }
        mock_point.return_value = large_response

        result = api_wrapper._make_api_request("points/40.0,-75.0")
        assert result == large_response
        assert len(result["properties"]["data"]) == 10000


@pytest.mark.unit
def test_api_request_concurrent_requests(api_wrapper):
    """Test handling of concurrent API requests."""
    import threading
    import time

    results = []
    errors = []

    def make_request(lat, lon):
        try:
            with patch("accessiweather.api_wrapper.point.sync") as mock_point:
                mock_point.return_value = SAMPLE_POINT_DATA
                result = api_wrapper._make_api_request(f"points/{lat},{lon}")
                results.append(result)
        except Exception as e:
            errors.append(e)

    # Create multiple threads to make concurrent requests
    threads = []
    for i in range(5):
        thread = threading.Thread(target=make_request, args=(40.0 + i * 0.1, -75.0))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # All requests should succeed
    assert len(errors) == 0
    assert len(results) == 5
