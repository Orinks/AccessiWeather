"""Tests for NoaaApiClient error handling functionality."""

from unittest.mock import patch

import pytest
from requests.exceptions import (
    ConnectionError,
    JSONDecodeError,
    RequestException,
    Timeout,
)

from accessiweather.api_client import NoaaApiClient, NoaaApiError

# Sample test data
SAMPLE_POINT_DATA = {
    "@context": ["https://geojson.org/geojson-ld/geojson-context.jsonld"],
    "id": "https://api.weather.gov/points/40,-75",
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-75.0, 40.0]},
    "properties": {
        "@id": "https://api.weather.gov/points/40,-75",
        "gridId": "PHI",
        "gridX": 50,
        "gridY": 75,
        "forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/50,75/forecast/hourly",
        "forecastGridData": "https://api.weather.gov/gridpoints/PHI/50,75",
        "observationStations": "https://api.weather.gov/gridpoints/PHI/50,75/stations",
        "relativeLocation": {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-75.1, 40.1]},
            "properties": {"city": "Test City", "state": "PA"},
        },
        "forecastZone": "https://api.weather.gov/zones/forecast/PAZ106",
        "county": "https://api.weather.gov/zones/county/PAC091",
        "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ106",
    },
}


@pytest.fixture
def api_client():
    return NoaaApiClient(
        user_agent="TestClient", contact_info="test@example.com", enable_caching=False
    )


def test_http_error_handling_404(api_client, mock_http_response):
    """Test handling of 404 Not Found errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_http_response(status_code=404, text_data="Not Found")

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Resource not found" in str(error)
        assert error.status_code == 404
        assert error.error_type == NoaaApiError.CLIENT_ERROR


def test_http_error_handling_429(api_client, mock_http_response):
    """Test handling of 429 Rate Limit errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_http_response(status_code=429, text_data="Too Many Requests")

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Rate limit exceeded" in str(error)
        assert error.status_code == 429
        assert error.error_type == NoaaApiError.RATE_LIMIT_ERROR


def test_http_error_handling_500(api_client, mock_http_response):
    """Test handling of 500 Server Error."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_http_response(
            status_code=500, text_data="Internal Server Error"
        )

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Server error" in str(error)
        assert error.status_code == 500
        assert error.error_type == NoaaApiError.SERVER_ERROR


def test_json_decode_error_handling(api_client, mock_http_response):
    """Test handling of JSON decode errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create a response that returns invalid JSON
        mock_response = mock_http_response(status_code=200, text_data="Invalid JSON response")
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Failed to parse JSON response" in str(error)
        assert error.status_code == 200
        assert error.error_type == NoaaApiError.PARSE_ERROR


def test_request_exception_handling(api_client):
    """Test handling of request exceptions."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.side_effect = RequestException("Connection error")

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Network error during API request" in str(error)
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
        mock_get.side_effect = ConnectionError("Connection refused")

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Connection error" in str(error)
        assert error.error_type == NoaaApiError.CONNECTION_ERROR
