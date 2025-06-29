"""Test configuration and fixtures for AccessiWeather Toga app tests."""

# Import only Toga-compatible fixtures
from unittest.mock import MagicMock, patch

import pytest

# Import only basic fixtures and Toga helpers, skip wx-specific ones
from tests.fixtures.basic_fixtures import *  # noqa: F401, F403
from tests.fixtures.sample_responses import *  # noqa: F401, F403
from tests.toga_test_helpers import *  # noqa: F401, F403

# Skip gui_fixtures and mock_clients as they contain wx/geocoding dependencies


@pytest.fixture
def mock_simple_weather_apis():
    """Mock weather APIs for simple Toga app testing."""
    with (
        patch("httpx.AsyncClient") as mock_httpx_client,
    ):
        # Set up httpx client mock for simple weather client
        mock_client_instance = MagicMock()
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        # Mock Open-Meteo API responses
        mock_openmeteo_current = {
            "current": {
                "temperature_2m": 75.0,
                "weather_code": 1,
                "relative_humidity_2m": 65,
                "wind_speed_10m": 8.5,
                "wind_direction_10m": 180,
                "pressure_msl": 1013.2,
                "apparent_temperature": 78.0,
            }
        }

        mock_openmeteo_forecast = {
            "daily": {
                "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "weather_code": [1, 2, 3],
                "temperature_2m_max": [75.0, 78.0, 72.0],
                "temperature_2m_min": [55.0, 58.0, 52.0],
            }
        }

        # Configure mock responses
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = [mock_openmeteo_current, mock_openmeteo_forecast]
        mock_client_instance.get.return_value = mock_response

        yield {
            "httpx_client": mock_client_instance,
            "openmeteo_current": mock_openmeteo_current,
            "openmeteo_forecast": mock_openmeteo_forecast,
        }


@pytest.fixture
def mock_web_scraping():
    """Mock web scraping for national discussion data."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Mock weather discussion</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_simple_weather_apis_error():
    """Mock weather APIs to simulate error conditions for simple app."""
    with patch("httpx.AsyncClient") as mock_httpx_client:
        # Configure httpx client mock to raise errors
        mock_client_instance = MagicMock()
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.side_effect = Exception("API Error")

        yield {"httpx_client": mock_client_instance}


@pytest.fixture
def mock_simple_weather_apis_timeout():
    """Mock weather APIs to simulate timeout conditions for simple app."""
    with patch("httpx.AsyncClient") as mock_httpx_client:
        import httpx

        # Configure httpx client mock to raise timeout
        mock_client_instance = MagicMock()
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.side_effect = httpx.TimeoutException("Request timed out")

        yield {"httpx_client": mock_client_instance}


@pytest.fixture
def verify_no_real_api_calls():
    """Verify that no real API calls are made during tests."""
    with (
        patch("requests.get") as mock_requests_get,
        patch("httpx.get") as mock_httpx_get,
        patch("httpx.Client.get") as mock_httpx_client_get,
    ):
        # Configure mocks to raise if called
        mock_requests_get.side_effect = AssertionError("Real requests.get call detected!")
        mock_httpx_get.side_effect = AssertionError("Real httpx.get call detected!")
        mock_httpx_client_get.side_effect = AssertionError("Real httpx.Client.get call detected!")

        yield {
            "requests_get": mock_requests_get,
            "httpx_get": mock_httpx_get,
            "httpx_client_get": mock_httpx_client_get,
        }
