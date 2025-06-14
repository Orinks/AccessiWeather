"""API mocking fixtures for comprehensive testing."""

from unittest.mock import MagicMock, patch

import pytest

from .shared_data import (
    MOCK_NWS_ALERTS_DATA,
    MOCK_NWS_CURRENT_CONDITIONS,
    MOCK_NWS_FORECAST_DATA,
    MOCK_NWS_POINT_DATA,
    MOCK_OPENMETEO_CURRENT_WEATHER,
    MOCK_OPENMETEO_FORECAST,
)


@pytest.fixture
def mock_weather_apis():
    """Mock all weather API calls for unit tests with comprehensive responses."""
    with (
        patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
        patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
        patch("accessiweather.api_client.NoaaApiClient") as mock_nws_client,
    ):
        # Configure NWS wrapper mock
        nws_instance = MagicMock()
        mock_nws.return_value = nws_instance

        # Configure NWS client mock
        nws_client_instance = MagicMock()
        mock_nws_client.return_value = nws_client_instance

        # Configure Open-Meteo mock
        openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = openmeteo_instance

        # Set up comprehensive NWS responses using mock data
        nws_instance.get_current_conditions.return_value = MOCK_NWS_CURRENT_CONDITIONS
        nws_instance.get_forecast.return_value = MOCK_NWS_FORECAST_DATA
        nws_instance.get_alerts.return_value = MOCK_NWS_ALERTS_DATA
        nws_instance.get_point_data.return_value = MOCK_NWS_POINT_DATA

        # Set up NWS client responses
        nws_client_instance.get_current_conditions.return_value = MOCK_NWS_CURRENT_CONDITIONS
        nws_client_instance.get_forecast.return_value = MOCK_NWS_FORECAST_DATA
        nws_client_instance.get_alerts.return_value = MOCK_NWS_ALERTS_DATA
        nws_client_instance.get_point_data.return_value = MOCK_NWS_POINT_DATA

        # Set up comprehensive Open-Meteo responses using mock data
        openmeteo_instance.get_current_weather.return_value = MOCK_OPENMETEO_CURRENT_WEATHER
        openmeteo_instance.get_forecast.return_value = MOCK_OPENMETEO_FORECAST

        yield {
            "nws": nws_instance,
            "nws_client": nws_client_instance,
            "openmeteo": openmeteo_instance,
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
def mock_weather_apis_error():
    """Mock weather APIs to simulate error conditions."""
    with (
        patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
        patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
    ):
        # Configure NWS mock to raise errors
        nws_instance = MagicMock()
        mock_nws.return_value = nws_instance
        nws_instance.get_current_conditions.side_effect = Exception("NWS API Error")
        nws_instance.get_forecast.side_effect = Exception("NWS API Error")
        nws_instance.get_alerts.side_effect = Exception("NWS API Error")

        # Configure Open-Meteo mock to raise errors
        openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = openmeteo_instance
        openmeteo_instance.get_current_weather.side_effect = Exception("Open-Meteo API Error")
        openmeteo_instance.get_forecast.side_effect = Exception("Open-Meteo API Error")

        yield {"nws": nws_instance, "openmeteo": openmeteo_instance}


@pytest.fixture
def mock_weather_apis_timeout():
    """Mock weather APIs to simulate timeout conditions."""
    with (
        patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
        patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
    ):
        from requests.exceptions import Timeout

        from accessiweather.openmeteo_client import OpenMeteoNetworkError

        # Configure NWS mock to raise timeout
        nws_instance = MagicMock()
        mock_nws.return_value = nws_instance
        nws_instance.get_current_conditions.side_effect = Timeout("Request timed out")
        nws_instance.get_forecast.side_effect = Timeout("Request timed out")
        nws_instance.get_alerts.side_effect = Timeout("Request timed out")

        # Configure Open-Meteo mock to raise timeout
        openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = openmeteo_instance
        openmeteo_instance.get_current_weather.side_effect = OpenMeteoNetworkError(
            "Request timed out"
        )
        openmeteo_instance.get_forecast.side_effect = OpenMeteoNetworkError("Request timed out")

        yield {"nws": nws_instance, "openmeteo": openmeteo_instance}


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
