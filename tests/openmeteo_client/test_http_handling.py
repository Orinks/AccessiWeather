"""Tests for OpenMeteoApiClient HTTP handling and error management."""

from unittest.mock import patch

import httpx
import pytest

from accessiweather.openmeteo_client import OpenMeteoApiError, OpenMeteoNetworkError

from .conftest import SAMPLE_CURRENT_WEATHER_DATA


# Test _make_request method and error handling
@pytest.mark.unit
def test_make_request_success(openmeteo_client):
    """Test successful API request."""
    with patch.object(
        openmeteo_client, "_request_forecast", return_value=SAMPLE_CURRENT_WEATHER_DATA
    ) as mock_request:
        result = openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert result == SAMPLE_CURRENT_WEATHER_DATA
        mock_request.assert_called_once()


@pytest.mark.unit
def test_make_request_400_error(openmeteo_client):
    """Test handling of 400 Bad Request errors."""
    with patch.object(
        openmeteo_client,
        "_request_forecast",
        side_effect=OpenMeteoApiError("Invalid coordinates"),
    ):
        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 999, "longitude": 999})

        assert "Invalid coordinates" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_429_rate_limit(openmeteo_client):
    """Test handling of 429 Rate Limit errors."""
    with patch.object(
        openmeteo_client,
        "_request_forecast",
        side_effect=OpenMeteoApiError("Rate limit exceeded"),
    ):
        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "Rate limit exceeded" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_500_server_error(openmeteo_client):
    """Test handling of 500 Server Error."""
    with patch.object(
        openmeteo_client,
        "_request_forecast",
        side_effect=OpenMeteoApiError("Server error: 500"),
    ):
        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "Server error: 500" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_network_error(openmeteo_client):
    """Test handling of network errors."""
    with patch.object(
        openmeteo_client,
        "_request_forecast",
        side_effect=httpx.ConnectError("Connection failed"),
    ):
        with pytest.raises(OpenMeteoNetworkError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "Network error" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_timeout_error(openmeteo_client):
    """Test handling of timeout errors."""
    with patch.object(
        openmeteo_client,
        "_request_forecast",
        side_effect=httpx.TimeoutException("Request timed out"),
    ):
        with pytest.raises(OpenMeteoNetworkError) as exc_info:
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert "Request timed out" in str(exc_info.value)


@pytest.mark.unit
def test_make_request_retry_mechanism(openmeteo_client):
    """Test retry mechanism on network errors."""
    responses = [
        httpx.ConnectError("Connection failed"),
        httpx.ConnectError("Connection failed"),
        SAMPLE_CURRENT_WEATHER_DATA,
    ]

    def side_effect(*args, **kwargs):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with (
        patch.object(
            openmeteo_client, "_request_forecast", side_effect=side_effect
        ) as mock_request,
        patch("time.sleep"),
    ):
        result = openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

    assert result == SAMPLE_CURRENT_WEATHER_DATA
    assert mock_request.call_count == 3


@pytest.mark.unit
def test_make_request_max_retries_exceeded(openmeteo_client):
    """Test that max retries are respected."""
    with patch.object(
        openmeteo_client,
        "_request_forecast",
        side_effect=httpx.ConnectError("Connection failed"),
    ) as mock_request:
        with patch("time.sleep"), pytest.raises(OpenMeteoNetworkError):
            openmeteo_client._make_request("forecast", {"latitude": 40.0, "longitude": -75.0})

        assert mock_request.call_count == openmeteo_client.max_retries + 1
