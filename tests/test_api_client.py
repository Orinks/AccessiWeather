"""Tests for the NoaaApiClient class."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.exceptions import HTTPError, JSONDecodeError, RequestException

from accessiweather.api_client import (
    ApiClientError,
    NoaaApiClient,
    LOCATION_TYPE_COUNTY,
    LOCATION_TYPE_FORECAST,
    LOCATION_TYPE_FIRE,
    LOCATION_TYPE_STATE
)

# Sample test data
SAMPLE_POINT_DATA = {
    "@context": ["https://geojson.org/geojson-ld/geojson-context.jsonld"],
    "id": "https://api.weather.gov/points/40,-75",
    "type": "Feature",
    "geometry": {
        "type": "Point",
        "coordinates": [-75.0, 40.0]
    },
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
            "geometry": {
                "type": "Point",
                "coordinates": [-75.1, 40.1]
            },
            "properties": {
                "city": "Test City",
                "state": "PA"
            }
        },
        "forecastZone": "https://api.weather.gov/zones/forecast/PAZ106",
        "county": "https://api.weather.gov/zones/county/PAC091",
        "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ106"
    }
}

SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperatureUnit": "F",
                "shortForecast": "Sunny",
                "detailedForecast": "Sunny with a high near 75."
            }
        ]
    }
}

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "properties": {
                "headline": "Test Alert",
                "description": "Test Description",
                "instruction": "Test Instruction",
                "severity": "Moderate",
                "event": "Test Event"
            }
        }
    ]
}

SAMPLE_DISCUSSION_PRODUCTS = {
    "@graph": [
        {
            "id": "AFD-PHI-202401010000",
            "@type": "wx:TextProduct"
        }
    ]
}

SAMPLE_DISCUSSION_TEXT = {
    "productText": """
This is a sample forecast discussion.
Multiple lines of text.
With weather information.
"""
}

SAMPLE_NATIONAL_PRODUCT = {
    "@graph": [
        {
            "id": "FXUS01-KWNH-202401010000",
            "@type": "wx:TextProduct"
        }
    ]
}

SAMPLE_NATIONAL_PRODUCT_TEXT = {
    "productText": """
This is a sample national product text.
Multiple lines of text.
With weather information.
"""
}

# Fixture to create a NoaaApiClient instance
@pytest.fixture
def api_client():
    return NoaaApiClient(
        user_agent="TestClient",
        contact_info="test@example.com",
        enable_caching=False
    )

# Fixture to create a NoaaApiClient instance with caching enabled
@pytest.fixture
def cached_api_client():
    return NoaaApiClient(
        user_agent="TestClient",
        contact_info="test@example.com",
        enable_caching=True,
        cache_ttl=300
    )

def test_init_basic():
    """Test basic initialization without caching."""
    client = NoaaApiClient(user_agent="TestClient")

    assert client.user_agent == "TestClient"
    assert client.headers["User-Agent"] == "TestClient"
    assert client.cache is None

def test_init_with_contact():
    """Test initialization with contact info."""
    client = NoaaApiClient(user_agent="TestClient", contact_info="test@example.com")

    assert client.headers["User-Agent"] == "TestClient (test@example.com)"

def test_init_with_caching():
    """Test initialization with caching enabled."""
    client = NoaaApiClient(user_agent="TestClient", enable_caching=True, cache_ttl=300)

    assert client.cache is not None
    assert client.cache.default_ttl == 300

def test_get_point_data_success(api_client):
    """Test getting point data successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_point_data(lat, lon)

        assert result == SAMPLE_POINT_DATA
        mock_get.assert_called_once()
        assert f"points/{lat},{lon}" in mock_get.call_args[0][0]

def test_get_point_data_cached(cached_api_client):
    """Test that point data is cached."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        # First call should hit the API
        result1 = cached_api_client.get_point_data(lat, lon)
        # Second call should use cache
        result2 = cached_api_client.get_point_data(lat, lon)

        assert result1 == result2
        mock_get.assert_called_once()

def test_get_point_data_force_refresh(cached_api_client):
    """Test that force_refresh bypasses cache."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        # First call
        cached_api_client.get_point_data(lat, lon)
        # Second call with force_refresh
        cached_api_client.get_point_data(lat, lon, force_refresh=True)

        assert mock_get.call_count == 2

def test_get_forecast_success(api_client):
    """Test getting forecast data successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # First call for point data
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,  # First call returns point data
            SAMPLE_FORECAST_DATA  # Second call returns forecast data
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_forecast(lat, lon)

        assert result == SAMPLE_FORECAST_DATA
        assert mock_get.call_count == 2

def test_get_forecast_no_url(api_client):
    """Test getting forecast when point data doesn't contain forecast URL."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        bad_point_data = dict(SAMPLE_POINT_DATA)
        bad_point_data["properties"].pop("forecast")
        mock_get.return_value.json.return_value = bad_point_data
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError) as exc_info:
            api_client.get_forecast(lat, lon)

        assert "Could not find forecast URL" in str(exc_info.value)

def test_identify_location_type_county(api_client):
    """Test identifying county location type."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        location_type, location_id = api_client.identify_location_type(lat, lon)

        assert location_type == LOCATION_TYPE_COUNTY
        assert location_id == "PAC091"

def test_get_alerts_precise_location(api_client):
    """Test getting alerts for precise location."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Mock point data and alerts response
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_ALERTS_DATA
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_alerts(lat, lon, precise_location=True)

        assert result == SAMPLE_ALERTS_DATA
        assert mock_get.call_count == 2

def test_get_alerts_state_fallback(api_client):
    """Test getting alerts falls back to state when precise location not found."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Remove all zone URLs from point data to force state fallback
        modified_point_data = dict(SAMPLE_POINT_DATA)
        modified_point_data["properties"].pop("county", None)
        modified_point_data["properties"].pop("forecastZone", None)
        modified_point_data["properties"].pop("fireWeatherZone", None)
        # Ensure state is present in relativeLocation
        modified_point_data["properties"]["relativeLocation"]["properties"]["state"] = "PA"

        mock_get.return_value.json.side_effect = [
            modified_point_data,
            SAMPLE_ALERTS_DATA
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_alerts(lat, lon)

        assert result == SAMPLE_ALERTS_DATA
        # Check that state parameter was used
        params = mock_get.call_args[1].get("params", {})
        assert params.get("area") == "PA"

def test_get_discussion_success(api_client):
    """Test getting discussion data successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_DISCUSSION_PRODUCTS,
            SAMPLE_DISCUSSION_TEXT
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_discussion(lat, lon)

        # Strip all whitespace from both strings for comparison
        expected = SAMPLE_DISCUSSION_TEXT["productText"].strip()
        assert result.strip() == expected
        assert mock_get.call_count == 3

def test_get_national_product_success(api_client):
    """Test getting national product successfully."""
    product_type = "FXUS01"
    location = "KWNH"
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_NATIONAL_PRODUCT,
            SAMPLE_NATIONAL_PRODUCT_TEXT
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_national_product(product_type, location)

        assert result == SAMPLE_NATIONAL_PRODUCT_TEXT["productText"]
        assert mock_get.call_count == 2

def test_rate_limiting(api_client):
    """Test that requests are rate limited."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        start_time = time.time()
        api_client.get_point_data(lat, lon)
        api_client.get_point_data(lat, lon)
        end_time = time.time()

        # Should have waited at least min_request_interval
        assert end_time - start_time >= api_client.min_request_interval

def test_http_error_handling(api_client):
    """Test handling of HTTP errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create a proper mock response with status_code
        mock_response = MagicMock()
        mock_response.status_code = 404
        # Create a proper HTTPError with a response attribute
        http_error = HTTPError("404 Client Error")
        http_error.response = mock_response
        mock_get.return_value.raise_for_status.side_effect = http_error

        with pytest.raises(ApiClientError) as exc_info:
            api_client.get_point_data(lat, lon)

        assert "API HTTP error: 404" in str(exc_info.value)

def test_json_decode_error_handling(api_client):
    """Test handling of JSON decode errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value.text = "Invalid JSON response"
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ApiClientError) as exc_info:
            api_client.get_point_data(lat, lon)

        assert "Failed to decode JSON response" in str(exc_info.value)

def test_request_exception_handling(api_client):
    """Test handling of request exceptions."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.side_effect = RequestException("Connection error")

        with pytest.raises(ApiClientError) as exc_info:
            api_client.get_point_data(lat, lon)

        assert "Network error during API request" in str(exc_info.value)

def test_thread_safety(api_client):
    """Test thread safety of request handling."""
    import threading

    results = []
    errors = []

    def make_request():
        try:
            result = api_client.get_point_data(40.0, -75.0)
            results.append(result)
        except Exception as e:
            errors.append(e)

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        # Create multiple threads making concurrent requests
        threads = [threading.Thread(target=make_request) for _ in range(5)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0
        assert all(result == SAMPLE_POINT_DATA for result in results)
        # Each request should have been made with proper rate limiting
        assert mock_get.call_count == 5