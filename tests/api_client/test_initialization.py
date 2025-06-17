"""Tests for NoaaApiClient initialization and basic functionality."""

import time
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import (
    ConnectionError,
    HTTPError,
    JSONDecodeError,
    RequestException,
    Timeout,
)

from accessiweather.api_client import LOCATION_TYPE_COUNTY, NoaaApiClient, NoaaApiError

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

SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperatureUnit": "F",
                "shortForecast": "Sunny",
                "detailedForecast": "Sunny with a high near 75.",
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
                "event": "Test Event",
            }
        }
    ]
}


# Fixture to create a NoaaApiClient instance
@pytest.fixture
def api_client():
    return NoaaApiClient(
        user_agent="TestClient", contact_info="test@example.com", enable_caching=False
    )


# Fixture to create a NoaaApiClient instance with caching enabled
@pytest.fixture
def cached_api_client():
    return NoaaApiClient(
        user_agent="TestClient", contact_info="test@example.com", enable_caching=True, cache_ttl=300
    )


@pytest.mark.unit
def test_init_basic():
    """Test basic initialization without caching."""
    client = NoaaApiClient(user_agent="TestClient")

    assert client.user_agent == "TestClient"
    assert client.headers["User-Agent"] == "TestClient (TestClient)"
    assert client.cache is None


@pytest.mark.unit
def test_init_with_contact():
    """Test initialization with contact info."""
    client = NoaaApiClient(user_agent="TestClient", contact_info="test@example.com")

    assert client.headers["User-Agent"] == "TestClient (test@example.com)"


@pytest.mark.unit
def test_init_with_caching():
    """Test initialization with caching enabled."""
    client = NoaaApiClient(user_agent="TestClient", enable_caching=True, cache_ttl=300)

    assert client.cache is not None
    assert client.cache.default_ttl == 300


@pytest.mark.unit
@pytest.mark.api
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


@pytest.mark.unit
@pytest.mark.api
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


def test_identify_location_type_county(api_client):
    """Test identifying county location type."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        location_type, location_id = api_client.identify_location_type(lat, lon)

        assert location_type == LOCATION_TYPE_COUNTY
        assert location_id == "PAC091"


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


def test_rate_limiting_multiple_endpoints(api_client):
    """Test that requests to multiple endpoints are rate limited."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get, patch("time.sleep") as mock_sleep:
        # Set up the mock response
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        # Make multiple requests to the same endpoint
        api_client.get_point_data(lat, lon)
        api_client.get_point_data(lat, lon)

        # Verify that sleep was called at least once for rate limiting
        assert mock_sleep.call_count > 0
