"""Tests for the WeatherAPI error handling."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from accessiweather.weatherapi_wrapper import WeatherApiError, WeatherApiWrapper


@pytest.fixture
def api_wrapper():
    """Create a WeatherApiWrapper instance for testing."""
    return WeatherApiWrapper(
        api_key="test_key",
        enable_caching=False,
        max_retries=1,
        retry_initial_wait=0.01,  # Short wait for faster tests
    )


def test_api_error_from_api_error():
    """Test creating an error from API error response."""
    error_json = {"error": {"code": 1006, "message": "No matching location found."}}

    error = WeatherApiError.from_api_error(error_json, "https://api.weatherapi.com/v1/current.json")

    assert error.error_type == WeatherApiError.NOT_FOUND
    assert "API Error 1006" in str(error)
    assert error.error_code == 1006
    assert error.response == error_json


def test_validate_response_current_valid(api_wrapper):
    """Test validating a valid current response."""
    response = {"location": {"name": "London"}, "current": {"temp_c": 15}}

    # Should not raise an exception
    api_wrapper._validate_response("current.json", response)


def test_validate_response_current_invalid(api_wrapper):
    """Test validating an invalid current response."""
    response = {
        "location": {"name": "London"}
        # Missing 'current' field
    }

    with pytest.raises(WeatherApiError) as excinfo:
        api_wrapper._validate_response("current.json", response)

    assert excinfo.value.error_type == WeatherApiError.VALIDATION_ERROR
    assert "missing 'current' field" in str(excinfo.value)


def test_validate_response_forecast_valid(api_wrapper):
    """Test validating a valid forecast response."""
    response = {
        "location": {"name": "London"},
        "current": {"temp_c": 15},
        "forecast": {"forecastday": [{"date": "2023-01-01"}]},
    }

    # Should not raise an exception
    api_wrapper._validate_response("forecast.json", response)


def test_validate_response_forecast_invalid(api_wrapper):
    """Test validating an invalid forecast response."""
    response = {
        "location": {"name": "London"},
        "current": {"temp_c": 15},
        "forecast": {},  # Missing 'forecastday' field
    }

    with pytest.raises(WeatherApiError) as excinfo:
        api_wrapper._validate_response("forecast.json", response)

    assert excinfo.value.error_type == WeatherApiError.VALIDATION_ERROR
    assert "missing 'forecast.forecastday' field" in str(excinfo.value)


def test_validate_response_search_valid(api_wrapper):
    """Test validating a valid search response."""
    response = [{"name": "London", "country": "UK"}, {"name": "London", "country": "US"}]

    # Should not raise an exception
    api_wrapper._validate_response("search.json", response)


def test_validate_response_search_invalid(api_wrapper):
    """Test validating an invalid search response."""
    response = {"error": "Invalid response"}  # Not a list

    with pytest.raises(WeatherApiError) as excinfo:
        api_wrapper._validate_response("search.json", response)

    assert excinfo.value.error_type == WeatherApiError.VALIDATION_ERROR
    assert "expected a list of locations" in str(excinfo.value)


@patch("accessiweather.weatherapi_client.client.WeatherApiClient._request_sync")
def test_make_request_json_decode_error(mock_request, api_wrapper):
    """Test handling JSON decode errors."""
    mock_request.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

    with pytest.raises(WeatherApiError) as excinfo:
        api_wrapper._make_request("current.json", {"q": "London"})

    assert excinfo.value.error_type == WeatherApiError.VALIDATION_ERROR
    assert "Invalid JSON" in str(excinfo.value)


@patch("accessiweather.weatherapi_client.client.WeatherApiClient._request_sync")
def test_make_request_connection_error(mock_request, api_wrapper):
    """Test handling connection errors."""
    mock_request.side_effect = httpx.ConnectError("Connection failed")

    with pytest.raises(WeatherApiError) as excinfo:
        api_wrapper._make_request("current.json", {"q": "London"})

    assert excinfo.value.error_type == WeatherApiError.CONNECTION_ERROR
    assert "Connection error" in str(excinfo.value)


@patch("accessiweather.weatherapi_client.client.WeatherApiClient._request_sync")
def test_make_request_timeout_error(mock_request, api_wrapper):
    """Test handling timeout errors."""
    mock_request.side_effect = httpx.ReadTimeout("Request timed out")

    with pytest.raises(WeatherApiError) as excinfo:
        api_wrapper._make_request("current.json", {"q": "London"})

    assert excinfo.value.error_type == WeatherApiError.TIMEOUT_ERROR
    assert "Timeout error" in str(excinfo.value)


@patch("accessiweather.weatherapi_client.client.WeatherApiClient._request_sync")
def test_make_request_api_error(mock_request, api_wrapper):
    """Test handling API errors."""
    mock_request.return_value = {"error": {"code": 1006, "message": "No matching location found."}}

    with pytest.raises(WeatherApiError) as excinfo:
        api_wrapper._make_request("current.json", {"q": "NonexistentLocation"})

    assert excinfo.value.error_type == WeatherApiError.NOT_FOUND
    assert "API Error 1006" in str(excinfo.value)
    assert excinfo.value.error_code == 1006
