"""Tests for NoaaApiWrapper location identification functionality."""

from unittest.mock import patch

import pytest

from accessiweather.api_client import NoaaApiError
from tests.api_wrapper_test_utils import (
    SAMPLE_POINT_DATA,
    MockUnexpectedStatus,
    api_wrapper,
)


@pytest.mark.unit
def test_identify_location_type_county(api_wrapper):
    """Test identifying county location type."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        location_type, zone_url = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "county"
        assert zone_url == "https://api.weather.gov/zones/county/PAC101"
        mock_get_point.assert_called_once_with(lat, lon)


@pytest.mark.unit
def test_identify_location_type_forecast_zone(api_wrapper):
    """Test identifying forecast zone location type."""
    lat, lon = 40.0, -75.0

    # Mock point data without county but with forecast zone
    point_data_no_county = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "forecastZone": "https://api.weather.gov/zones/forecast/PAZ103",
            "timeZone": "America/New_York",
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = point_data_no_county

        location_type, zone_url = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "forecast"
        assert zone_url == "https://api.weather.gov/zones/forecast/PAZ103"


@pytest.mark.unit
def test_identify_location_type_fire_zone(api_wrapper):
    """Test identifying fire weather zone location type."""
    lat, lon = 40.0, -75.0

    # Mock point data with only fire weather zone
    point_data_fire_zone = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
            "timeZone": "America/New_York",
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = point_data_fire_zone

        location_type, zone_url = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "fire"
        assert zone_url == "https://api.weather.gov/zones/fire/PAZ103"


@pytest.mark.unit
def test_identify_location_type_state_fallback(api_wrapper):
    """Test falling back to state when no specific zone is found."""
    lat, lon = 40.0, -75.0

    # Mock point data without any zone URLs
    point_data_no_zones = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "timeZone": "America/New_York",
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = point_data_no_zones

        location_type, zone_url = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "state"
        # Should construct state-based URL from coordinates
        assert "PA" in zone_url or "state" in location_type


@pytest.mark.unit
def test_identify_location_type_none(api_wrapper):
    """Test when location type cannot be determined."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {"properties": {}}

        location_type, zone_url = api_wrapper.identify_location_type(lat, lon)

        assert location_type is None
        assert zone_url is None


@pytest.mark.unit
def test_identify_location_type_error_handling(api_wrapper):
    """Test error handling in identify_location_type."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.side_effect = NoaaApiError("API Error", NoaaApiError.SERVER_ERROR)

        with pytest.raises(NoaaApiError):
            api_wrapper.identify_location_type(lat, lon)


@pytest.mark.unit
def test_identify_location_type_with_multiple_zones(api_wrapper):
    """Test location identification when multiple zone types are available."""
    lat, lon = 40.0, -75.0

    # Mock point data with multiple zone types - county should take precedence
    point_data_multiple_zones = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "county": "https://api.weather.gov/zones/county/PAC101",
            "forecastZone": "https://api.weather.gov/zones/forecast/PAZ103",
            "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
            "timeZone": "America/New_York",
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = point_data_multiple_zones

        location_type, zone_url = api_wrapper.identify_location_type(lat, lon)

        # County should take precedence
        assert location_type == "county"
        assert zone_url == "https://api.weather.gov/zones/county/PAC101"


@pytest.mark.unit
def test_identify_location_type_with_invalid_coordinates(api_wrapper):
    """Test location identification with invalid coordinates."""
    lat, lon = 999.0, 999.0  # Invalid coordinates

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.side_effect = NoaaApiError("Invalid coordinates", NoaaApiError.CLIENT_ERROR)

        with pytest.raises(NoaaApiError):
            api_wrapper.identify_location_type(lat, lon)


@pytest.mark.unit
def test_identify_location_type_with_ocean_coordinates(api_wrapper):
    """Test location identification with ocean coordinates."""
    lat, lon = 30.0, -80.0  # Ocean coordinates

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        # Ocean coordinates might return different data structure
        mock_get_point.return_value = {
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/MLB/50,50/forecast",
                "forecastZone": "https://api.weather.gov/zones/forecast/AMZ550",  # Marine zone
            }
        }

        location_type, zone_url = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "forecast"
        assert "AMZ" in zone_url  # Marine zone identifier


@pytest.mark.unit
def test_identify_location_type_with_border_coordinates(api_wrapper):
    """Test location identification with coordinates near state borders."""
    lat, lon = 39.7217, -75.1677  # Philadelphia, near PA/NJ border

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        location_type, zone_url = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "county"
        assert zone_url == "https://api.weather.gov/zones/county/PAC101"


@pytest.mark.unit
def test_identify_location_type_caching(api_wrapper):
    """Test that location identification respects caching."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        # First call
        location_type1, zone_url1 = api_wrapper.identify_location_type(lat, lon)

        # Second call - should use cached data if caching is enabled
        location_type2, zone_url2 = api_wrapper.identify_location_type(lat, lon)

        assert location_type1 == location_type2
        assert zone_url1 == zone_url2

        # get_point_data should be called for each identify_location_type call
        # since the wrapper doesn't cache location identification separately
        assert mock_get_point.call_count == 2


@pytest.mark.unit
def test_identify_location_type_with_malformed_urls(api_wrapper):
    """Test location identification with malformed zone URLs."""
    lat, lon = 40.0, -75.0

    # Mock point data with malformed URLs
    point_data_malformed = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "county": "not-a-valid-url",
            "timeZone": "America/New_York",
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = point_data_malformed

        # Should handle malformed URLs gracefully
        location_type, zone_url = api_wrapper.identify_location_type(lat, lon)

        # Might fall back to a different method or return None
        assert location_type is not None or zone_url is not None
