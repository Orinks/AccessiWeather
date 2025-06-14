"""Tests for NoaaApiClient point data functionality."""

from unittest.mock import patch

import pytest

from tests.api_client_test_utils import SAMPLE_POINT_DATA, api_client, cached_api_client


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


@pytest.mark.unit
def test_get_point_data_with_different_coordinates(api_client):
    """Test getting point data with different coordinate formats."""
    test_cases = [
        (40.0, -75.0),
        (40.123456, -75.654321),
        (25.7617, -80.1918),  # Miami
        (47.6062, -122.3321),  # Seattle
    ]

    for lat, lon in test_cases:
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
            mock_get.return_value.raise_for_status.return_value = None

            result = api_client.get_point_data(lat, lon)

            assert result == SAMPLE_POINT_DATA
            # Verify the correct coordinates were used in the URL
            assert f"points/{lat},{lon}" in mock_get.call_args[0][0]


@pytest.mark.unit
def test_get_point_data_with_invalid_coordinates(api_client):
    """Test getting point data with invalid coordinates."""
    invalid_coordinates = [
        (91.0, -75.0),  # Latitude too high
        (-91.0, -75.0),  # Latitude too low
        (40.0, 181.0),  # Longitude too high
        (40.0, -181.0),  # Longitude too low
    ]

    for lat, lon in invalid_coordinates:
        with patch("requests.get") as mock_get:
            from unittest.mock import MagicMock

            from requests.exceptions import HTTPError

            # Mock a 400 Bad Request response
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            http_error = HTTPError("400 Client Error")
            http_error.response = mock_response
            mock_get.return_value.raise_for_status.side_effect = http_error

            from accessiweather.api_client import NoaaApiError

            with pytest.raises(NoaaApiError) as exc_info:
                api_client.get_point_data(lat, lon)

            assert exc_info.value.error_type == NoaaApiError.CLIENT_ERROR


@pytest.mark.unit
def test_get_point_data_url_construction(api_client):
    """Test that point data URLs are constructed correctly."""
    lat, lon = 40.123, -75.456

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_point_data(lat, lon)

        # Verify the URL was constructed correctly
        called_url = mock_get.call_args[0][0]
        assert called_url.startswith("https://api.weather.gov/")
        assert f"points/{lat},{lon}" in called_url


@pytest.mark.unit
def test_get_point_data_headers(api_client):
    """Test that correct headers are sent with point data requests."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_point_data(lat, lon)

        # Verify headers were passed
        call_kwargs = mock_get.call_args[1]
        assert "headers" in call_kwargs
        headers = call_kwargs["headers"]
        assert "User-Agent" in headers
        assert "TestClient" in headers["User-Agent"]


@pytest.mark.unit
def test_get_point_data_timeout(api_client):
    """Test that timeout is applied to point data requests."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_point_data(lat, lon)

        # Verify timeout was passed
        call_kwargs = mock_get.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == api_client.timeout


@pytest.mark.unit
def test_get_point_data_response_structure(api_client):
    """Test that point data response has expected structure."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_point_data(lat, lon)

        # Verify response structure
        assert isinstance(result, dict)
        assert "properties" in result
        assert "geometry" in result
        assert "type" in result

        properties = result["properties"]
        assert "gridId" in properties
        assert "gridX" in properties
        assert "gridY" in properties
        assert "forecast" in properties
        assert "forecastHourly" in properties


@pytest.mark.unit
def test_get_point_data_cache_key_generation(cached_api_client):
    """Test that cache keys are generated correctly for point data."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        # Make the same request twice
        result1 = cached_api_client.get_point_data(lat, lon)
        result2 = cached_api_client.get_point_data(lat, lon)

        # Should be the same result from cache
        assert result1 == result2
        # Should only make one API call
        assert mock_get.call_count == 1

        # Different coordinates should not use cache
        result3 = cached_api_client.get_point_data(lat + 0.1, lon + 0.1)
        assert mock_get.call_count == 2


@pytest.mark.unit
def test_get_point_data_with_precision(api_client):
    """Test point data requests with high precision coordinates."""
    # Test with high precision coordinates
    lat, lon = 40.123456789, -75.987654321

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_point_data(lat, lon)

        assert result == SAMPLE_POINT_DATA
        # Verify precision is maintained in URL
        called_url = mock_get.call_args[0][0]
        assert str(lat) in called_url
        assert str(lon) in called_url


@pytest.mark.unit
def test_get_point_data_edge_coordinates(api_client):
    """Test point data requests with edge case coordinates."""
    edge_cases = [
        (0.0, 0.0),  # Equator and Prime Meridian
        (90.0, 180.0),  # North Pole area
        (-90.0, -180.0),  # South Pole area
        (49.0, -125.0),  # Northern US border
        (25.0, -80.0),  # Southern US
    ]

    for lat, lon in edge_cases:
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
            mock_get.return_value.raise_for_status.return_value = None

            result = api_client.get_point_data(lat, lon)

            assert result == SAMPLE_POINT_DATA
            assert f"points/{lat},{lon}" in mock_get.call_args[0][0]
