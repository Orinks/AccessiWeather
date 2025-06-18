"""Test configuration and fixtures for AccessiWeather tests."""

# Import all fixtures from fixture modules
# Import additional fixtures that need to remain in conftest.py
from unittest.mock import MagicMock, patch

import pytest

from tests.fixtures.basic_fixtures import *  # noqa: F401, F403
from tests.fixtures.gui_fixtures import *  # noqa: F401, F403
from tests.fixtures.mock_clients import *  # noqa: F401, F403
from tests.fixtures.sample_responses import *  # noqa: F401, F403


@pytest.fixture
def mock_weather_apis():
    """Mock all weather APIs with comprehensive responses."""
    with (
        patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
        patch("accessiweather.api_client.NoaaApiClient") as mock_nws_client,
        patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
    ):
        # Set up NWS wrapper mock
        nws_instance = MagicMock()
        mock_nws.return_value = nws_instance
        nws_instance.get_current_conditions.return_value = {
            "properties": {
                "temperature": {"value": 20.0, "unitCode": "wmoUnit:degC"},
                "textDescription": "Partly Cloudy",
                "relativeHumidity": {"value": 65},
                "windSpeed": {"value": 10, "unitCode": "wmoUnit:km_h-1"},
                "windDirection": {"value": 180},
                "barometricPressure": {"value": 101325, "unitCode": "wmoUnit:Pa"},
            }
        }
        nws_instance.get_forecast.return_value = {
            "properties": {
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 75,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                        "detailedForecast": "Sunny with a high near 75.",
                        "windSpeed": "10 mph",
                        "windDirection": "SW",
                    }
                ]
            }
        }
        nws_instance.get_alerts.return_value = {
            "features": [
                {
                    "properties": {
                        "headline": "Heat Advisory",
                        "description": "Dangerous heat conditions expected.",
                        "instruction": "Stay hydrated and avoid prolonged sun exposure.",
                        "severity": "Moderate",
                        "event": "Heat Advisory",
                        "urgency": "Expected",
                        "certainty": "Likely",
                    }
                }
            ]
        }
        nws_instance.get_point_data.return_value = {
            "properties": {
                "gridId": "PHI",
                "gridX": 50,
                "gridY": 75,
                "forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast",
                "county": "https://api.weather.gov/zones/county/PAC091",
            }
        }

        # Set up NWS client mock
        nws_client_instance = MagicMock()
        mock_nws_client.return_value = nws_client_instance
        nws_client_instance.get_current_conditions.return_value = (
            nws_instance.get_current_conditions.return_value
        )
        nws_client_instance.get_forecast.return_value = nws_instance.get_forecast.return_value
        nws_client_instance.get_alerts.return_value = nws_instance.get_alerts.return_value
        nws_client_instance.get_point_data.return_value = nws_instance.get_point_data.return_value

        # Set up Open-Meteo mock
        openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = openmeteo_instance
        openmeteo_instance.get_current_weather.return_value = {
            "current": {
                "temperature_2m": 68.0,
                "weather_code": 2,
                "relative_humidity_2m": 65,
                "wind_speed_10m": 8.5,
                "wind_direction_10m": 180,
                "pressure_msl": 1013.2,
            }
        }
        openmeteo_instance.get_forecast.return_value = {
            "daily": {
                "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "weather_code": [1, 2, 3],
                "temperature_2m_max": [75.0, 78.0, 72.0],
                "temperature_2m_min": [55.0, 58.0, 52.0],
            }
        }

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
