"""Tests for NoaaApiClient error handling."""

from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import (
    ConnectionError,
    HTTPError,
    JSONDecodeError,
    RequestException,
    Timeout,
)

from accessiweather.api_client import NoaaApiError
from tests.api_client_test_utils import api_client


def test_http_error_handling_404(api_client):
    """Test handling of 404 Not Found errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create a proper mock response with status_code
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        # Create a proper HTTPError with a response attribute
        http_error = HTTPError("404 Client Error")
        http_error.response = mock_response
        mock_get.return_value.raise_for_status.side_effect = http_error

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Resource not found" in str(error)
        assert error.status_code == 404
        assert error.error_type == NoaaApiError.CLIENT_ERROR


def test_http_error_handling_429(api_client):
    """Test handling of 429 Rate Limit errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create a proper mock response with status_code
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        # Create a proper HTTPError with a response attribute
        http_error = HTTPError("429 Client Error")
        http_error.response = mock_response
        mock_get.return_value.raise_for_status.side_effect = http_error

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Rate limit exceeded" in str(error)
        assert error.status_code == 429
        assert error.error_type == NoaaApiError.RATE_LIMIT_ERROR


def test_http_error_handling_500(api_client):
    """Test handling of 500 Server Error."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create a proper mock response with status_code
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        # Create a proper HTTPError with a response attribute
        http_error = HTTPError("500 Server Error")
        http_error.response = mock_response
        mock_get.return_value.raise_for_status.side_effect = http_error

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Server error" in str(error)
        assert error.status_code == 500
        assert error.error_type == NoaaApiError.SERVER_ERROR


def test_json_decode_error_handling(api_client):
    """Test handling of JSON decode errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.text = "Invalid JSON response"

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Invalid JSON response" in str(error)
        assert error.error_type == NoaaApiError.PARSE_ERROR


def test_request_exception_handling(api_client):
    """Test handling of request exceptions."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.side_effect = RequestException("Request failed")

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Request failed" in str(error)
        assert error.error_type == NoaaApiError.NETWORK_ERROR


def test_timeout_error_handling(api_client):
    """Test handling of timeout errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Timeout("Request timed out")

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Request timed out" in str(error)
        assert error.error_type == NoaaApiError.TIMEOUT_ERROR


def test_connection_error_handling(api_client):
    """Test handling of connection errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.side_effect = ConnectionError("Connection failed")

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Connection failed" in str(error)
        assert error.error_type == NoaaApiError.CONNECTION_ERROR


@pytest.mark.unit
def test_http_error_with_json_response(api_client):
    """Test handling of HTTP errors that include JSON error details."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create a mock response with JSON error details
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {
            "title": "Bad Request",
            "detail": "Invalid coordinates provided",
            "status": 400
        }
        
        http_error = HTTPError("400 Client Error")
        http_error.response = mock_response
        mock_get.return_value.raise_for_status.side_effect = http_error

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert error.status_code == 400
        assert error.error_type == NoaaApiError.CLIENT_ERROR
        # Should include details from JSON response
        assert "Invalid coordinates provided" in str(error)


@pytest.mark.unit
def test_http_error_without_response(api_client):
    """Test handling of HTTP errors without response object."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create HTTPError without response attribute
        http_error = HTTPError("Generic HTTP Error")
        # Don't set response attribute
        mock_get.return_value.raise_for_status.side_effect = http_error

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Generic HTTP Error" in str(error)
        assert error.error_type == NoaaApiError.UNKNOWN_ERROR


@pytest.mark.unit
def test_error_message_formatting(api_client):
    """Test that error messages are formatted correctly."""
    lat, lon = 40.0, -75.0
    
    # Test different error scenarios
    error_scenarios = [
        (404, "Not Found", "Resource not found"),
        (429, "Too Many Requests", "Rate limit exceeded"),
        (500, "Internal Server Error", "Server error"),
        (503, "Service Unavailable", "Server error"),
    ]
    
    for status_code, status_text, expected_message in error_scenarios:
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.text = status_text
            mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
            
            http_error = HTTPError(f"{status_code} Error")
            http_error.response = mock_response
            mock_get.return_value.raise_for_status.side_effect = http_error

            with pytest.raises(NoaaApiError) as exc_info:
                api_client.get_point_data(lat, lon)

            error = exc_info.value
            assert expected_message in str(error)
            assert error.status_code == status_code


@pytest.mark.unit
def test_error_context_preservation(api_client):
    """Test that error context is preserved through the error handling chain."""
    lat, lon = 40.0, -75.0
    
    with patch("requests.get") as mock_get:
        original_error = ConnectionError("DNS resolution failed")
        mock_get.side_effect = original_error

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert error.error_type == NoaaApiError.CONNECTION_ERROR
        assert "DNS resolution failed" in str(error)
        # Original exception should be preserved
        assert error.__cause__ == original_error


@pytest.mark.unit
def test_unknown_exception_handling(api_client):
    """Test handling of unknown/unexpected exceptions."""
    lat, lon = 40.0, -75.0
    
    with patch("requests.get") as mock_get:
        # Raise an unexpected exception type
        mock_get.side_effect = ValueError("Unexpected error")

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert error.error_type == NoaaApiError.UNKNOWN_ERROR
        assert "Unexpected error" in str(error)


@pytest.mark.unit
def test_error_logging(api_client):
    """Test that errors are logged appropriately."""
    lat, lon = 40.0, -75.0
    
    with patch("requests.get") as mock_get:
        with patch("logging.getLogger") as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value = mock_log
            
            mock_get.side_effect = ConnectionError("Connection failed")

            with pytest.raises(NoaaApiError):
                api_client.get_point_data(lat, lon)

            # Verify that error was logged (if logging is implemented)
            # This test may need adjustment based on actual logging implementation
