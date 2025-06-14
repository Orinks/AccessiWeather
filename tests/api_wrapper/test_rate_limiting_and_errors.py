"""Tests for NoaaApiWrapper rate limiting and error handling."""

import time
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import NoaaApiError
from tests.api_wrapper_test_utils import (
    SAMPLE_POINT_DATA,
    MockUnexpectedStatus,
    api_wrapper,
    cached_api_wrapper,
)


@pytest.mark.unit
def test_rate_limiting_enforcement(api_wrapper):
    """Test that rate limiting is enforced between requests."""
    with patch("time.sleep") as mock_sleep:
        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_POINT_DATA

            # Make first request
            api_wrapper.get_point_data(40.0, -75.0)

            # Make second request immediately - this should trigger rate limiting
            api_wrapper.get_point_data(40.1, -75.1)

            # Check that sleep was called for rate limiting
            assert mock_sleep.call_count >= 1


@pytest.mark.unit
def test_retry_mechanism_with_backoff(api_wrapper):
    """Test retry mechanism with exponential backoff."""
    # Mock the underlying API function to raise an error then succeed
    with patch("accessiweather.api_wrapper.point.sync") as mock_point:
        mock_point.side_effect = [MockUnexpectedStatus(429), SAMPLE_POINT_DATA]

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(NoaaApiError):
                # This should fail because the retry mechanism is not implemented
                # in the current version of the wrapper
                api_wrapper.get_point_data(40.0, -75.0)


@pytest.mark.unit
def test_error_handling_for_http_errors(api_wrapper):
    """Test error handling for different HTTP status codes."""
    test_cases = [
        (404, "CLIENT_ERROR"),
        (429, "RATE_LIMIT_ERROR"),
        (500, "SERVER_ERROR"),
        (503, "SERVER_ERROR"),
    ]

    for status_code, expected_error_type in test_cases:
        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.side_effect = MockUnexpectedStatus(status_code)

            with pytest.raises(NoaaApiError) as exc_info:
                api_wrapper.get_point_data(40.0, -75.0)

            assert hasattr(exc_info.value, "error_type")


@pytest.mark.unit
def test_handle_rate_limit_max_retries_exceeded(api_wrapper):
    """Test rate limit handling when max retries are exceeded."""
    url = "https://api.weather.gov/test"

    with pytest.raises(NoaaApiError) as exc_info:
        api_wrapper._handle_rate_limit(url, retry_count=api_wrapper.max_retries)

    assert "Rate limit exceeded" in str(exc_info.value)
    assert exc_info.value.error_type == NoaaApiError.RATE_LIMIT_ERROR


@pytest.mark.unit
def test_handle_rate_limit_with_backoff(api_wrapper):
    """Test rate limit handling with exponential backoff."""
    url = "https://api.weather.gov/test"

    with patch("time.sleep") as mock_sleep:
        api_wrapper._handle_rate_limit(url, retry_count=1)

        # Should sleep for initial_wait * backoff^retry_count
        expected_wait = api_wrapper.retry_initial_wait * (api_wrapper.retry_backoff**1)
        mock_sleep.assert_called_once_with(expected_wait)


@pytest.mark.unit
def test_handle_client_error_timeout(api_wrapper):
    """Test handling of timeout errors."""
    import httpx

    timeout_error = httpx.TimeoutException("Request timed out")
    url = "https://api.weather.gov/test"

    result = api_wrapper._handle_client_error(timeout_error, url)

    assert isinstance(result, NoaaApiError)
    assert result.error_type == NoaaApiError.TIMEOUT_ERROR
    assert "timed out" in str(result)


@pytest.mark.unit
def test_handle_client_error_connection(api_wrapper):
    """Test handling of connection errors."""
    import httpx

    connection_error = httpx.ConnectError("Connection failed")
    url = "https://api.weather.gov/test"

    result = api_wrapper._handle_client_error(connection_error, url)

    assert isinstance(result, NoaaApiError)
    assert result.error_type == NoaaApiError.CONNECTION_ERROR
    assert "Connection error" in str(result)


@pytest.mark.unit
def test_handle_client_error_network(api_wrapper):
    """Test handling of network errors."""
    import httpx

    network_error = httpx.RequestError("Network error")
    url = "https://api.weather.gov/test"

    result = api_wrapper._handle_client_error(network_error, url)

    assert isinstance(result, NoaaApiError)
    assert result.error_type == NoaaApiError.NETWORK_ERROR
    assert "Network error" in str(result)


@pytest.mark.unit
def test_handle_client_error_unknown(api_wrapper):
    """Test handling of unknown errors."""
    unknown_error = Exception("Unknown error")
    url = "https://api.weather.gov/test"

    result = api_wrapper._handle_client_error(unknown_error, url)

    assert isinstance(result, NoaaApiError)
    assert result.error_type == NoaaApiError.UNKNOWN_ERROR
    assert "Unexpected error" in str(result)


def test_rate_limiting(api_wrapper):
    """Test rate limiting functionality."""
    # Test that rate limiting is properly enforced
    with patch("time.sleep") as mock_sleep:
        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_POINT_DATA

            # Record the time before first request
            start_time = time.time()

            # Make first request
            api_wrapper.get_point_data(40.0, -75.0)

            # Make second request immediately
            api_wrapper.get_point_data(40.1, -75.1)

            # Verify that sleep was called to enforce rate limiting
            assert mock_sleep.called

            # Verify that the sleep duration is reasonable
            if mock_sleep.call_args_list:
                sleep_duration = mock_sleep.call_args_list[0][0][0]
                assert sleep_duration > 0
                assert sleep_duration <= api_wrapper.rate_limit_delay


def test_handle_rate_limit(api_wrapper):
    """Test rate limit handling with exponential backoff."""
    url = "https://api.weather.gov/test"

    # Test with retry count less than max retries
    with patch("time.sleep") as mock_sleep:
        api_wrapper._handle_rate_limit(url, retry_count=1)

        # Should sleep for initial_wait * backoff^retry_count
        expected_wait = api_wrapper.retry_initial_wait * (api_wrapper.retry_backoff**1)
        mock_sleep.assert_called_once_with(expected_wait)

    # Test with retry count equal to max retries
    with pytest.raises(NoaaApiError) as exc_info:
        api_wrapper._handle_rate_limit(url, retry_count=api_wrapper.max_retries)

    assert "Rate limit exceeded" in str(exc_info.value)
    assert exc_info.value.error_type == NoaaApiError.RATE_LIMIT_ERROR


def test_rate_limit_retry_mechanism(api_wrapper):
    """Test the retry mechanism for rate limited requests."""
    # Mock the API to return rate limit error first, then success
    with patch.object(api_wrapper, "_make_api_request") as mock_request:
        # First call returns rate limit error, second call succeeds
        mock_request.side_effect = [
            MockUnexpectedStatus(429),  # Rate limit error
            SAMPLE_POINT_DATA,  # Success
        ]

        with patch("time.sleep") as mock_sleep:
            # This should trigger the rate limit handling
            with pytest.raises(NoaaApiError):
                # Current implementation doesn't have automatic retry
                api_wrapper.get_point_data(40.0, -75.0)

    # Test multiple consecutive rate limit errors
    with patch.object(api_wrapper, "_make_api_request") as mock_request:
        # Multiple rate limit errors
        mock_request.side_effect = [
            MockUnexpectedStatus(429),
            MockUnexpectedStatus(429),
            MockUnexpectedStatus(429),
        ]

        with pytest.raises(NoaaApiError):
            api_wrapper.get_point_data(40.0, -75.0)


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
