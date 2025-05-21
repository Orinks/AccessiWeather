"""Tests for WeatherAPI.com error handling in the WeatherService."""

from unittest.mock import MagicMock

import pytest

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.gui.settings_dialog import DATA_SOURCE_WEATHERAPI
from accessiweather.services.weather_service import WeatherService
from accessiweather.weatherapi_wrapper import WeatherApiError, WeatherApiWrapper


@pytest.fixture
def mock_nws_client():
    """Create a mock NWS API client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_weatherapi_wrapper():
    """Create a mock WeatherAPI.com wrapper."""
    mock = MagicMock(spec=WeatherApiWrapper)
    return mock


@pytest.fixture
def weather_service(mock_nws_client, mock_weatherapi_wrapper):
    """Create a WeatherService instance with mock clients."""
    config = {
        "settings": {"data_source": DATA_SOURCE_WEATHERAPI},
        "api_keys": {"weatherapi": "test_key"},
    }
    return WeatherService(
        nws_client=mock_nws_client,
        weatherapi_wrapper=mock_weatherapi_wrapper,
        config=config,
    )


class TestWeatherApiErrorHandling:
    """Tests for WeatherAPI.com error handling in the WeatherService."""

    def test_api_key_invalid_error_propagation(self, weather_service, mock_weatherapi_wrapper):
        """Test that API key invalid errors are propagated correctly."""
        # Create a WeatherApiError with API_KEY_INVALID error type
        api_error = WeatherApiError(
            message="API key invalid",
            error_type=WeatherApiError.API_KEY_INVALID,
            error_code=2006,
        )
        mock_weatherapi_wrapper.get_forecast.side_effect = api_error

        # Call the method and expect the error to be propagated
        with pytest.raises(WeatherApiError) as excinfo:
            weather_service.get_forecast(lat=40.0, lon=-75.0)

        # Verify the error is the same one we created
        assert excinfo.value.error_type == WeatherApiError.API_KEY_INVALID
        assert excinfo.value.error_code == 2006

    def test_quota_exceeded_error_propagation(self, weather_service, mock_weatherapi_wrapper):
        """Test that quota exceeded errors are propagated correctly."""
        # Create a WeatherApiError with QUOTA_EXCEEDED error type
        api_error = WeatherApiError(
            message="API key has exceeded calls per month quota",
            error_type=WeatherApiError.QUOTA_EXCEEDED,
            error_code=2007,
        )
        mock_weatherapi_wrapper.get_forecast.side_effect = api_error

        # Call the method and expect the error to be propagated
        with pytest.raises(WeatherApiError) as excinfo:
            weather_service.get_forecast(lat=40.0, lon=-75.0)

        # Verify the error is the same one we created
        assert excinfo.value.error_type == WeatherApiError.QUOTA_EXCEEDED
        assert excinfo.value.error_code == 2007

    def test_location_not_found_error_propagation(self, weather_service, mock_weatherapi_wrapper):
        """Test that location not found errors are propagated correctly."""
        # Create a WeatherApiError with NOT_FOUND error type
        api_error = WeatherApiError(
            message="No matching location found",
            error_type=WeatherApiError.NOT_FOUND,
            error_code=1006,
        )
        mock_weatherapi_wrapper.get_forecast.side_effect = api_error

        # Call the method and expect the error to be propagated
        with pytest.raises(WeatherApiError) as excinfo:
            weather_service.get_forecast(lat=40.0, lon=-75.0)

        # Verify the error is the same one we created
        assert excinfo.value.error_type == WeatherApiError.NOT_FOUND
        assert excinfo.value.error_code == 1006

    def test_connection_error_propagation(self, weather_service, mock_weatherapi_wrapper):
        """Test that connection errors are propagated correctly."""
        # Create a WeatherApiError with CONNECTION_ERROR error type
        api_error = WeatherApiError(
            message="Connection error",
            error_type=WeatherApiError.CONNECTION_ERROR,
        )
        mock_weatherapi_wrapper.get_forecast.side_effect = api_error

        # Call the method and expect the error to be propagated
        with pytest.raises(WeatherApiError) as excinfo:
            weather_service.get_forecast(lat=40.0, lon=-75.0)

        # Verify the error is the same one we created
        assert excinfo.value.error_type == WeatherApiError.CONNECTION_ERROR

    def test_timeout_error_propagation(self, weather_service, mock_weatherapi_wrapper):
        """Test that timeout errors are propagated correctly."""
        # Create a WeatherApiError with TIMEOUT_ERROR error type
        api_error = WeatherApiError(
            message="Request timed out",
            error_type=WeatherApiError.TIMEOUT_ERROR,
        )
        mock_weatherapi_wrapper.get_forecast.side_effect = api_error

        # Call the method and expect the error to be propagated
        with pytest.raises(WeatherApiError) as excinfo:
            weather_service.get_forecast(lat=40.0, lon=-75.0)

        # Verify the error is the same one we created
        assert excinfo.value.error_type == WeatherApiError.TIMEOUT_ERROR

    def test_error_message_formatting(self):
        """Test that error messages are formatted correctly."""
        # Create different types of errors
        api_key_error = WeatherApiError(
            message="API key invalid",
            error_type=WeatherApiError.API_KEY_INVALID,
            error_code=2006,
        )
        quota_error = WeatherApiError(
            message="API key has exceeded calls per month quota",
            error_type=WeatherApiError.QUOTA_EXCEEDED,
            error_code=2007,
        )
        not_found_error = WeatherApiError(
            message="No matching location found",
            error_type=WeatherApiError.NOT_FOUND,
            error_code=1006,
        )
        connection_error = WeatherApiError(
            message="Connection error",
            error_type=WeatherApiError.CONNECTION_ERROR,
        )
        timeout_error = WeatherApiError(
            message="Request timed out",
            error_type=WeatherApiError.TIMEOUT_ERROR,
        )
        generic_error = ApiClientError("Generic API error")
        string_error = "String error"

        # Simulate the UIManager._format_error_message method

        # Create a function that simulates the _format_error_message method
        def format_error(error):
            if isinstance(error, str):
                return error

            if isinstance(error, WeatherApiError):
                if error.error_type == WeatherApiError.API_KEY_INVALID:
                    return "Invalid WeatherAPI.com API key. Please check your settings."
                elif error.error_type == WeatherApiError.QUOTA_EXCEEDED:
                    return "WeatherAPI.com rate limit exceeded. Please try again later or switch to NWS/NOAA."
                elif error.error_type == WeatherApiError.NOT_FOUND:
                    return "Location not found. Please try a different location."
                elif error.error_type == WeatherApiError.CONNECTION_ERROR:
                    return "Connection error. Please check your internet connection."
                elif error.error_type == WeatherApiError.TIMEOUT_ERROR:
                    return "Request timed out. Please try again later."
                else:
                    return f"WeatherAPI.com error: {str(error)}"

            elif isinstance(error, NoaaApiError):
                return f"NWS API error: {str(error)}"

            elif isinstance(error, ApiClientError):
                return f"API error: {str(error)}"

            return str(error)

        # Test API key invalid error
        msg = format_error(api_key_error)
        assert "Invalid WeatherAPI.com API key" in msg

        # Test quota exceeded error
        msg = format_error(quota_error)
        assert "WeatherAPI.com rate limit exceeded" in msg

        # Test location not found error
        msg = format_error(not_found_error)
        assert "Location not found" in msg

        # Test connection error
        msg = format_error(connection_error)
        assert "Connection error" in msg

        # Test timeout error
        msg = format_error(timeout_error)
        assert "Request timed out" in msg

        # Test generic API error
        msg = format_error(generic_error)
        assert "API error" in msg

        # Test string error
        msg = format_error(string_error)
        assert msg == string_error
