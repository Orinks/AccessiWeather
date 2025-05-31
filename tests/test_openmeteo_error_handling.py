"""Error handling tests for Open-Meteo integration."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from accessiweather.openmeteo_client import (
    OpenMeteoApiClient,
    OpenMeteoApiError,
    OpenMeteoNetworkError,
)
from accessiweather.openmeteo_mapper import OpenMeteoMapper
from accessiweather.services.weather_service import WeatherService


@pytest.fixture
def openmeteo_client():
    """Create an OpenMeteoApiClient for testing."""
    return OpenMeteoApiClient(timeout=5.0, max_retries=2)


@pytest.fixture
def mapper():
    """Create an OpenMeteoMapper for testing."""
    return OpenMeteoMapper()


@pytest.fixture
def weather_service():
    """Create a WeatherService with mocked clients."""
    mock_nws = MagicMock()
    mock_openmeteo = MagicMock(spec=OpenMeteoApiClient)
    config = {"settings": {"data_source": "auto"}}
    return WeatherService(nws_client=mock_nws, openmeteo_client=mock_openmeteo, config=config)


# Network and connectivity error tests
@pytest.mark.unit
def test_connection_error_handling(openmeteo_client):
    """Test handling of connection errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(OpenMeteoNetworkError) as exc_info:
            openmeteo_client.get_current_weather(40.0, -75.0)

        assert "Network error" in str(exc_info.value)
        assert "Connection refused" in str(exc_info.value)


@pytest.mark.unit
def test_timeout_error_handling(openmeteo_client):
    """Test handling of timeout errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(OpenMeteoNetworkError) as exc_info:
            openmeteo_client.get_current_weather(40.0, -75.0)

        assert "Request timed out" in str(exc_info.value)


@pytest.mark.unit
def test_dns_resolution_error(openmeteo_client):
    """Test handling of DNS resolution errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Name resolution failed")

        with pytest.raises(OpenMeteoNetworkError):
            openmeteo_client.get_current_weather(40.0, -75.0)


# API response error tests
@pytest.mark.unit
def test_400_bad_request_error(openmeteo_client):
    """Test handling of 400 Bad Request errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"reason": "Invalid latitude"}'
        mock_response.json.return_value = {"reason": "Invalid latitude"}
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client.get_current_weather(999, -75.0)

        assert "Invalid latitude" in str(exc_info.value)


@pytest.mark.unit
def test_429_rate_limit_error(openmeteo_client):
    """Test handling of 429 Rate Limit errors."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.content = b""
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client.get_current_weather(40.0, -75.0)

        assert "Rate limit exceeded" in str(exc_info.value)


@pytest.mark.unit
def test_500_server_error(openmeteo_client):
    """Test handling of 500 Internal Server Error."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b""
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client.get_current_weather(40.0, -75.0)

        assert "Server error: 500" in str(exc_info.value)


@pytest.mark.unit
def test_503_service_unavailable(openmeteo_client):
    """Test handling of 503 Service Unavailable."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.content = b""
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client.get_current_weather(40.0, -75.0)

        assert "Server error: 503" in str(exc_info.value)


# Malformed response tests
@pytest.mark.unit
def test_invalid_json_response(openmeteo_client):
    """Test handling of invalid JSON responses."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError) as exc_info:
            openmeteo_client.get_current_weather(40.0, -75.0)

        assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.unit
def test_empty_response_body(openmeteo_client):
    """Test handling of empty response body."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        # Should not raise an error, but return empty data
        result = openmeteo_client.get_current_weather(40.0, -75.0)
        assert result == {}


# Data mapping error tests
@pytest.mark.unit
def test_mapper_invalid_data_structure(mapper):
    """Test mapper handling of invalid data structures."""
    invalid_data = {"invalid": "structure"}

    # The mapper should handle gracefully and return a basic structure
    result = mapper.map_current_conditions(invalid_data)
    assert "properties" in result


@pytest.mark.unit
def test_mapper_missing_required_fields(mapper):
    """Test mapper handling of missing required fields."""
    incomplete_data = {"current": {}, "current_units": {}}  # Empty current data

    # Should not raise an error, but handle gracefully
    result = mapper.map_current_conditions(incomplete_data)
    assert "properties" in result


@pytest.mark.unit
def test_mapper_corrupted_data_types(mapper):
    """Test mapper handling of corrupted data types."""
    corrupted_data = {
        "current": {
            "temperature_2m": "not_a_number",
            "time": 12345,  # Should be string
            "weather_code": "invalid",
        },
        "current_units": {"temperature_2m": "°F"},
    }

    # Should handle gracefully without crashing
    result = mapper.map_current_conditions(corrupted_data)
    assert "properties" in result


# WeatherService error handling tests
@pytest.mark.unit
def test_weather_service_openmeteo_fallback_on_error(weather_service):
    """Test WeatherService fallback when Open-Meteo fails."""
    lat, lon = 40.7128, -74.0060  # New York (US location for fallback)

    # Mock Open-Meteo failure
    weather_service.openmeteo_client.get_current_weather.side_effect = OpenMeteoApiError(
        "API Error"
    )

    # Mock NWS success (fallback)
    weather_service.nws_client.get_current_conditions.return_value = {"properties": {"temp": 20}}

    with patch.object(weather_service, "_should_use_openmeteo", return_value=True):
        result = weather_service.get_current_conditions(lat, lon)

        # Should have fallen back to NWS
        assert result is not None
        weather_service.nws_client.get_current_conditions.assert_called_once()


@pytest.mark.unit
def test_weather_service_both_apis_fail(weather_service):
    """Test WeatherService when both APIs fail."""
    lat, lon = 40.7128, -74.0060  # New York (US location for fallback)

    # Mock both APIs failing
    weather_service.openmeteo_client.get_current_weather.side_effect = OpenMeteoApiError(
        "API Error"
    )
    weather_service.nws_client.get_current_conditions.side_effect = Exception("NWS Error")

    with patch.object(weather_service, "_should_use_openmeteo", return_value=True):
        with pytest.raises(Exception):  # Should raise exception when both fail
            weather_service.get_current_conditions(lat, lon)


@pytest.mark.unit
def test_weather_service_error_logging(weather_service):
    """Test that errors are properly logged."""
    lat, lon = 40.7128, -74.0060  # New York (US location)

    # Mock Open-Meteo failure
    weather_service.openmeteo_client.get_current_weather.side_effect = OpenMeteoApiError(
        "Test error"
    )

    # Mock NWS success for fallback
    weather_service.nws_client.get_current_conditions.return_value = {"properties": {"temp": 20}}

    with patch.object(weather_service, "_should_use_openmeteo", return_value=True):
        with patch("accessiweather.services.weather_service.logger") as mock_logger:
            result = weather_service.get_current_conditions(lat, lon)

            # Should log the error and succeed with fallback
            mock_logger.warning.assert_called()
            assert result is not None


# Retry mechanism tests
@pytest.mark.unit
def test_retry_mechanism_eventual_success(openmeteo_client):
    """Test that retry mechanism eventually succeeds."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        # First call fails, second succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"current": {"temperature_2m": 20}}

        mock_get.side_effect = [httpx.ConnectError("Connection failed"), mock_response]

        with patch("time.sleep"):  # Speed up test
            result = openmeteo_client.get_current_weather(40.0, -75.0)

        assert result is not None
        assert mock_get.call_count == 2


@pytest.mark.unit
def test_retry_mechanism_max_retries(openmeteo_client):
    """Test that retry mechanism respects max retries."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        with patch("time.sleep"):  # Speed up test
            with pytest.raises(OpenMeteoNetworkError):
                openmeteo_client.get_current_weather(40.0, -75.0)

        # Should try max_retries + 1 times
        expected_calls = openmeteo_client.max_retries + 1
        assert mock_get.call_count == expected_calls


# Edge case error tests
@pytest.mark.unit
def test_extreme_coordinates_error(openmeteo_client):
    """Test error handling with extreme coordinates."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"reason": "Latitude out of range"}'
        mock_response.json.return_value = {"reason": "Latitude out of range"}
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError):
            openmeteo_client.get_current_weather(999, 999)


@pytest.mark.unit
def test_unicode_error_handling(openmeteo_client):
    """Test handling of unicode errors in responses."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = UnicodeDecodeError(
            "utf-8", b"", 0, 1, "invalid start byte"
        )
        mock_get.return_value = mock_response

        with pytest.raises(OpenMeteoApiError):
            openmeteo_client.get_current_weather(40.0, -75.0)
