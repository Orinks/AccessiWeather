"""Tests for NoaaApiWrapper location identification functionality."""

from unittest.mock import patch

import pytest

from .conftest import TEST_LAT, TEST_LON


@pytest.mark.unit
def test_identify_location_type_county(api_wrapper):
    """Test identifying county location type."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {
            "properties": {
                "county": "https://api.weather.gov/zones/county/PAC101",
                "forecastZone": "https://api.weather.gov/zones/forecast/PAZ103",
                "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
            }
        }

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "county"
        assert location_id == "PAC101"
        mock_get_point.assert_called_once_with(lat, lon, force_refresh=False)


@pytest.mark.unit
def test_identify_location_type_forecast_zone(api_wrapper):
    """Test identifying forecast zone location type."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {
            "properties": {
                "forecastZone": "https://api.weather.gov/zones/forecast/PAZ103",
                "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
            }
        }

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "forecast"
        assert location_id == "PAZ103"


@pytest.mark.unit
def test_identify_location_type_fire_zone(api_wrapper):
    """Test identifying fire weather zone location type."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {
            "properties": {
                "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
            }
        }

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "fire"
        assert location_id == "PAZ103"


@pytest.mark.unit
def test_identify_location_type_state_fallback(api_wrapper):
    """Test falling back to state when no specific zone is found."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {
            "properties": {"relativeLocation": {"properties": {"state": "PA"}}}
        }

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "state"
        assert location_id == "PA"


@pytest.mark.unit
def test_identify_location_type_none(api_wrapper):
    """Test when location type cannot be determined."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {"properties": {}}

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type is None
        assert location_id is None


@pytest.mark.unit
def test_identify_location_type_error_handling(api_wrapper):
    """Test error handling in identify_location_type."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.side_effect = Exception("API error")

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type is None
        assert location_id is None
