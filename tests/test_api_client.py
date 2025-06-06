"""Tests for the NoaaApiClient class."""

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

SAMPLE_DISCUSSION_PRODUCTS = {"@graph": [{"id": "AFD-PHI-202401010000", "@type": "wx:TextProduct"}]}

SAMPLE_DISCUSSION_TEXT = {
    "productText": """
This is a sample forecast discussion.
Multiple lines of text.
With weather information.
"""
}

SAMPLE_NATIONAL_PRODUCT = {
    "@graph": [{"id": "FXUS01-KWNH-202401010000", "@type": "wx:TextProduct"}]
}

SAMPLE_NATIONAL_PRODUCT_TEXT = {
    "productText": """
This is a sample national product text.
Multiple lines of text.
With weather information.
"""
}

# Sample station data
SAMPLE_STATIONS_DATA = {
    "features": [
        {
            "id": "https://api.weather.gov/stations/KXYZ",
            "properties": {
                "@id": "https://api.weather.gov/stations/KXYZ",
                "@type": "wx:ObservationStation",
                "elevation": {"unitCode": "wmoUnit:m", "value": 123.4},
                "name": "Test Station",
                "stationIdentifier": "KXYZ",
                "timeZone": "America/New_York",
            },
        },
        {
            "id": "https://api.weather.gov/stations/KABC",
            "properties": {
                "@id": "https://api.weather.gov/stations/KABC",
                "@type": "wx:ObservationStation",
                "elevation": {"unitCode": "wmoUnit:m", "value": 234.5},
                "name": "Another Test Station",
                "stationIdentifier": "KABC",
                "timeZone": "America/New_York",
            },
        },
    ]
}

# Sample current observation data
SAMPLE_OBSERVATION_DATA = {
    "properties": {
        "@id": "https://api.weather.gov/stations/KXYZ/observations/2023-01-01T12:00:00Z",
        "temperature": {"unitCode": "wmoUnit:degC", "value": 22.8, "qualityControl": "qc:V"},
        "dewpoint": {"unitCode": "wmoUnit:degC", "value": 15.6, "qualityControl": "qc:V"},
        "windDirection": {
            "unitCode": "wmoUnit:degree_(angle)",
            "value": 180,
            "qualityControl": "qc:V",
        },
        "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 15.0, "qualityControl": "qc:V"},
        "barometricPressure": {"unitCode": "wmoUnit:Pa", "value": 101325, "qualityControl": "qc:V"},
        "seaLevelPressure": {"unitCode": "wmoUnit:Pa", "value": 101325, "qualityControl": "qc:V"},
        "visibility": {"unitCode": "wmoUnit:km", "value": 16.09, "qualityControl": "qc:V"},
        "relativeHumidity": {"unitCode": "wmoUnit:percent", "value": 65, "qualityControl": "qc:V"},
        "textDescription": "Partly Cloudy",
        "icon": "https://api.weather.gov/icons/land/day/sct?size=medium",
    }
}

# Sample hourly forecast data
SAMPLE_HOURLY_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "number": 1,
                "name": "This Hour",
                "startTime": "2023-01-01T12:00:00-05:00",
                "endTime": "2023-01-01T13:00:00-05:00",
                "isDaytime": True,
                "temperature": 72,
                "temperatureUnit": "F",
                "temperatureTrend": None,
                "windSpeed": "10 mph",
                "windDirection": "S",
                "icon": "https://api.weather.gov/icons/land/day/sct?size=small",
                "shortForecast": "Partly Sunny",
                "detailedForecast": "",
            },
            {
                "number": 2,
                "name": "Next Hour",
                "startTime": "2023-01-01T13:00:00-05:00",
                "endTime": "2023-01-01T14:00:00-05:00",
                "isDaytime": True,
                "temperature": 73,
                "temperatureUnit": "F",
                "temperatureTrend": "rising",
                "windSpeed": "12 mph",
                "windDirection": "S",
                "icon": "https://api.weather.gov/icons/land/day/sct?size=small",
                "shortForecast": "Partly Sunny",
                "detailedForecast": "",
            },
        ]
    }
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


def test_get_forecast_success(api_client):
    """Test getting forecast data successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # First call for point data
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,  # First call returns point data
            SAMPLE_FORECAST_DATA,  # Second call returns forecast data
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
        properties: dict = {}
        # Copy all properties except 'forecast'
        # Use a type-safe approach by accessing the dictionary directly
        properties_dict = SAMPLE_POINT_DATA.get("properties", {})
        if isinstance(properties_dict, dict):
            for key in list(properties_dict.keys()):
                if key != "forecast":
                    properties[key] = properties_dict[key]
        bad_point_data["properties"] = properties
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
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, SAMPLE_ALERTS_DATA]
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
        properties: dict = {}
        # Copy all properties except the ones we want to exclude
        # Use a type-safe approach by accessing the dictionary directly
        properties_dict = SAMPLE_POINT_DATA.get("properties", {})
        if isinstance(properties_dict, dict):
            for key in list(properties_dict.keys()):
                if key not in ["county", "forecastZone", "fireWeatherZone"]:
                    properties[key] = properties_dict[key]

        # Create a deep copy of the relativeLocation in a type-safe way
        rel_location = {}
        rel_properties = {"state": "PA"}

        # Copy other properties if they exist
        if isinstance(properties_dict, dict) and "relativeLocation" in properties_dict:
            rel_location_orig = properties_dict.get("relativeLocation", {})
            if isinstance(rel_location_orig, dict):
                for key in list(rel_location_orig.keys()):
                    if key != "properties":
                        rel_location[key] = rel_location_orig[key]

                rel_props_orig = rel_location_orig.get("properties", {})
                if isinstance(rel_props_orig, dict):
                    for key in list(rel_props_orig.keys()):
                        rel_properties[key] = rel_props_orig[key]

        rel_location["properties"] = rel_properties

        properties["relativeLocation"] = rel_location
        modified_point_data["properties"] = properties

        mock_get.return_value.json.side_effect = [modified_point_data, SAMPLE_ALERTS_DATA]
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
            SAMPLE_DISCUSSION_TEXT,
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
            SAMPLE_NATIONAL_PRODUCT_TEXT,
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


def test_http_error_handling_404(api_client):
    """Test handling of 404 Not Found errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create a proper mock response with status_code
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        # Create a proper HTTPError with a response attribute
        http_error = HTTPError("404 Client Error")
        http_error.response = mock_response
        mock_get.return_value.raise_for_status.side_effect = http_error

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Resource not found" in str(error)
        assert error.status_code == 404
        assert error.error_type == NoaaApiError.CLIENT_ERROR


def test_http_error_handling_429(api_client):
    """Test handling of 429 Rate Limit errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create a proper mock response with status_code
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        # Create a proper HTTPError with a response attribute
        http_error = HTTPError("429 Client Error")
        http_error.response = mock_response
        mock_get.return_value.raise_for_status.side_effect = http_error

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Rate limit exceeded" in str(error)
        assert error.status_code == 429
        assert error.error_type == NoaaApiError.RATE_LIMIT_ERROR


def test_http_error_handling_500(api_client):
    """Test handling of 500 Server Error."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create a proper mock response with status_code
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        # Create a proper HTTPError with a response attribute
        http_error = HTTPError("500 Server Error")
        http_error.response = mock_response
        mock_get.return_value.raise_for_status.side_effect = http_error

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Server error" in str(error)
        assert error.status_code == 500
        assert error.error_type == NoaaApiError.SERVER_ERROR


def test_json_decode_error_handling(api_client):
    """Test handling of JSON decode errors."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value.text = "Invalid JSON response"
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_point_data(lat, lon)

        error = exc_info.value
        assert "Failed to decode JSON response" in str(error)
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


def test_get_stations_success(api_client):
    """Test getting observation stations successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # First call for point data, second for stations
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, SAMPLE_STATIONS_DATA]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_stations(lat, lon)

        assert result == SAMPLE_STATIONS_DATA
        assert mock_get.call_count == 2
        # Check that the second call used the stations URL from point data
        assert "stations" in mock_get.call_args_list[1][0][0]


def test_get_stations_no_url(api_client):
    """Test getting stations when point data doesn't contain stations URL."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        bad_point_data = dict(SAMPLE_POINT_DATA)
        # Remove the observationStations URL
        properties: dict = {}
        # Copy all properties except observationStations
        # Use a type-safe approach by accessing the dictionary directly
        properties_dict = SAMPLE_POINT_DATA.get("properties", {})
        if isinstance(properties_dict, dict):
            for key in list(properties_dict.keys()):
                if key != "observationStations":
                    properties[key] = properties_dict[key]
        bad_point_data["properties"] = properties
        mock_get.return_value.json.return_value = bad_point_data
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError) as exc_info:
            api_client.get_stations(lat, lon)

        assert "Could not find observation stations URL" in str(exc_info.value)


def test_get_current_conditions_success(api_client):
    """Test getting current conditions successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # First call for point data, second for stations, third for observations
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_STATIONS_DATA,
            SAMPLE_OBSERVATION_DATA,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_current_conditions(lat, lon)

        assert result == SAMPLE_OBSERVATION_DATA
        assert mock_get.call_count == 3
        # Check that the third call used the first station's observations URL
        assert "stations/KXYZ/observations/latest" in mock_get.call_args_list[2][0][0]


def test_get_current_conditions_no_stations(api_client):
    """Test getting current conditions when no stations are available."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Return point data but empty stations list
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            {"features": []},  # Empty stations list
        ]
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError) as exc_info:
            api_client.get_current_conditions(lat, lon)

        assert "No observation stations found" in str(exc_info.value)


def test_get_hourly_forecast_success(api_client):
    """Test getting hourly forecast data successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # First call for point data, second for hourly forecast
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, SAMPLE_HOURLY_FORECAST_DATA]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_hourly_forecast(lat, lon)

        assert result == SAMPLE_HOURLY_FORECAST_DATA
        assert mock_get.call_count == 2
        # Check that the second call used the hourly forecast URL from point data
        assert "forecast/hourly" in mock_get.call_args_list[1][0][0]


def test_get_hourly_forecast_no_url(api_client):
    """Test getting hourly forecast when point data doesn't contain hourly forecast URL."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        bad_point_data = dict(SAMPLE_POINT_DATA)
        # Remove the forecastHourly URL
        properties: dict = {}
        # Copy all properties except forecastHourly
        # Use a type-safe approach by accessing the dictionary directly
        properties_dict = SAMPLE_POINT_DATA.get("properties", {})
        if isinstance(properties_dict, dict):
            for key in list(properties_dict.keys()):
                if key != "forecastHourly":
                    properties[key] = properties_dict[key]
        bad_point_data["properties"] = properties
        mock_get.return_value.json.return_value = bad_point_data
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError) as exc_info:
            api_client.get_hourly_forecast(lat, lon)

        assert "Could not find hourly forecast URL" in str(exc_info.value)


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
