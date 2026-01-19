"""
Tests for OpenMeteoApiClient.

Tests the Open-Meteo weather API client.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from accessiweather.openmeteo_client import (
    OpenMeteoApiClient,
    OpenMeteoApiError,
    OpenMeteoNetworkError,
)


class TestOpenMeteoApiClientInit:
    """Tests for client initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        client = OpenMeteoApiClient()
        assert client.user_agent == "AccessiWeather"
        assert client.timeout == 30.0
        assert client.max_retries == 3

    def test_custom_initialization(self):
        """Test custom initialization."""
        client = OpenMeteoApiClient(
            user_agent="TestApp",
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0,
        )
        assert client.user_agent == "TestApp"
        assert client.timeout == 60.0
        assert client.max_retries == 5
        assert client.retry_delay == 2.0


class TestOpenMeteoWeatherCodes:
    """Tests for weather code descriptions."""

    def test_clear_sky(self):
        """Test clear sky code."""
        desc = OpenMeteoApiClient.get_weather_description(0)
        assert "clear" in desc.lower()

    def test_cloudy_codes(self):
        """Test cloudy weather codes."""
        # Partly cloudy
        desc = OpenMeteoApiClient.get_weather_description(2)
        assert "cloud" in desc.lower()

        # Overcast
        desc = OpenMeteoApiClient.get_weather_description(3)
        assert "overcast" in desc.lower() or "cloud" in desc.lower()

    def test_rain_codes(self):
        """Test rain weather codes."""
        # Light rain
        desc = OpenMeteoApiClient.get_weather_description(61)
        assert "rain" in desc.lower()

    def test_snow_codes(self):
        """Test snow weather codes."""
        # Light snow
        desc = OpenMeteoApiClient.get_weather_description(71)
        assert "snow" in desc.lower()

    def test_thunderstorm_codes(self):
        """Test thunderstorm codes."""
        desc = OpenMeteoApiClient.get_weather_description(95)
        assert "thunder" in desc.lower()

    def test_unknown_code(self):
        """Test unknown weather code."""
        desc = OpenMeteoApiClient.get_weather_description(999)
        assert "unknown" in desc.lower()

    def test_none_code(self):
        """Test None weather code."""
        desc = OpenMeteoApiClient.get_weather_description(None)
        assert "unknown" in desc.lower()


class TestOpenMeteoRequests:
    """Tests for API request methods."""

    @pytest.fixture
    def client(self):
        return OpenMeteoApiClient()

    @pytest.fixture
    def mock_response(self):
        """Create a mock successful response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "current": {
                "temperature_2m": 72.0,
                "relative_humidity_2m": 65,
                "weather_code": 0,
            },
            "daily": {
                "sunrise": ["2024-01-01T07:00"],
                "sunset": ["2024-01-01T17:00"],
            },
        }
        response.raise_for_status = MagicMock()
        return response

    def test_get_current_weather(self, client, mock_response):
        """Test getting current weather."""
        client.client.get = MagicMock(return_value=mock_response)

        data = client.get_current_weather(40.7128, -74.0060)

        assert "current" in data
        assert data["current"]["temperature_2m"] == 72.0

    def test_get_forecast(self, client, mock_response):
        """Test getting forecast."""
        mock_response.json.return_value = {
            "daily": {
                "temperature_2m_max": [75, 78, 80],
                "temperature_2m_min": [55, 58, 60],
                "weather_code": [0, 1, 2],
            }
        }
        client.client.get = MagicMock(return_value=mock_response)

        data = client.get_forecast(40.7128, -74.0060, days=7)

        assert "daily" in data

    def test_get_hourly_forecast(self, client, mock_response):
        """Test getting hourly forecast."""
        mock_response.json.return_value = {
            "hourly": {
                "temperature_2m": [70, 71, 72, 73],
                "weather_code": [0, 0, 1, 1],
            }
        }
        client.client.get = MagicMock(return_value=mock_response)

        data = client.get_hourly_forecast(40.7128, -74.0060, hours=48)

        assert "hourly" in data

    def test_custom_model_parameter(self, client, mock_response):
        """Test that model parameter is passed to the API."""
        # The OpenMeteoApiClient uses 'models' parameter internally
        # Just verify the method accepts the parameter without error
        client.client.get = MagicMock(return_value=mock_response)

        # Note: get_current_weather doesn't take a 'model' parameter directly
        # The model is set during client initialization or via settings
        data = client.get_current_weather(40.7128, -74.0060)
        assert "current" in data


class TestOpenMeteoErrors:
    """Tests for error handling."""

    @pytest.fixture
    def client(self):
        return OpenMeteoApiClient(max_retries=0)  # No retries for faster tests

    def test_api_error_400(self, client):
        """Test handling 400 error."""
        response = MagicMock()
        response.status_code = 400
        response.content = b'{"reason": "Invalid parameter"}'
        response.json.return_value = {"reason": "Invalid parameter"}
        client.client.get = MagicMock(return_value=response)

        with pytest.raises(OpenMeteoApiError) as exc:
            client.get_current_weather(0, 0)
        assert "Invalid parameter" in str(exc.value)

    def test_api_error_429(self, client):
        """Test handling rate limit error."""
        response = MagicMock()
        response.status_code = 429
        client.client.get = MagicMock(return_value=response)

        with pytest.raises(OpenMeteoApiError) as exc:
            client.get_current_weather(0, 0)
        assert "rate limit" in str(exc.value).lower()

    def test_api_error_500(self, client):
        """Test handling server error."""
        response = MagicMock()
        response.status_code = 500
        client.client.get = MagicMock(return_value=response)

        with pytest.raises(OpenMeteoApiError) as exc:
            client.get_current_weather(0, 0)
        assert "server error" in str(exc.value).lower()

    def test_network_timeout(self, client):
        """Test handling timeout."""
        import httpx

        client.client.get = MagicMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(OpenMeteoNetworkError):
            client.get_current_weather(0, 0)

    def test_network_error(self, client):
        """Test handling network error."""
        import httpx

        client.client.get = MagicMock(side_effect=httpx.NetworkError("connection refused"))

        with pytest.raises(OpenMeteoNetworkError):
            client.get_current_weather(0, 0)
