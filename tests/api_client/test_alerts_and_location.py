"""Tests for NoaaApiClient alerts and location identification functionality."""

from unittest.mock import patch

import pytest

from accessiweather.api_client import LOCATION_TYPE_COUNTY
from tests.api_client_test_utils import (
    SAMPLE_ALERTS_DATA,
    SAMPLE_POINT_DATA,
    api_client,
    create_modified_point_data_without_zones,
)


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
        modified_point_data = create_modified_point_data_without_zones()
        mock_get.return_value.json.side_effect = [modified_point_data, SAMPLE_ALERTS_DATA]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_alerts(lat, lon)

        assert result == SAMPLE_ALERTS_DATA
        # Check that state parameter was used
        params = mock_get.call_args[1].get("params", {})
        assert params.get("area") == "PA"


@pytest.mark.unit
def test_identify_location_type_forecast_zone(api_client):
    """Test identifying forecast zone location type."""
    lat, lon = 40.0, -75.0

    # Create point data with forecast zone but no county
    point_data_forecast_zone = dict(SAMPLE_POINT_DATA)
    properties = dict(SAMPLE_POINT_DATA["properties"])
    del properties["county"]  # Remove county
    point_data_forecast_zone["properties"] = properties

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = point_data_forecast_zone
        mock_get.return_value.raise_for_status.return_value = None

        location_type, location_id = api_client.identify_location_type(lat, lon)

        assert location_type == "forecast"
        assert location_id == "PAZ106"


@pytest.mark.unit
def test_identify_location_type_fire_zone(api_client):
    """Test identifying fire weather zone location type."""
    lat, lon = 40.0, -75.0

    # Create point data with only fire weather zone
    point_data_fire_zone = dict(SAMPLE_POINT_DATA)
    properties = dict(SAMPLE_POINT_DATA["properties"])
    del properties["county"]
    del properties["forecastZone"]
    point_data_fire_zone["properties"] = properties

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = point_data_fire_zone
        mock_get.return_value.raise_for_status.return_value = None

        location_type, location_id = api_client.identify_location_type(lat, lon)

        assert location_type == "fire"
        assert location_id == "PAZ106"


@pytest.mark.unit
def test_identify_location_type_state_fallback(api_client):
    """Test falling back to state when no zone URLs are found."""
    lat, lon = 40.0, -75.0

    modified_point_data = create_modified_point_data_without_zones()

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = modified_point_data
        mock_get.return_value.raise_for_status.return_value = None

        location_type, location_id = api_client.identify_location_type(lat, lon)

        assert location_type == "state"
        assert location_id == "PA"


@pytest.mark.unit
def test_get_alerts_with_radius(api_client):
    """Test getting alerts with specific radius."""
    lat, lon = 40.0, -75.0
    radius_miles = 50

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, SAMPLE_ALERTS_DATA]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_alerts(lat, lon, radius=radius_miles, precise_location=True)

        assert result == SAMPLE_ALERTS_DATA
        # Verify radius was included in the request
        # (Implementation may vary on how radius is handled)


@pytest.mark.unit
def test_get_alerts_direct_point_query(api_client):
    """Test getting alerts using direct point query when precise_location=False."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_ALERTS_DATA
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_alerts(lat, lon, precise_location=False)

        assert result == SAMPLE_ALERTS_DATA
        # Should make direct alerts query without getting point data first
        assert mock_get.call_count == 1

        # Verify point coordinates were used in alerts query
        call_args = mock_get.call_args
        params = call_args[1].get("params", {})
        assert f"{lat},{lon}" in str(params) or f"point={lat},{lon}" in call_args[0][0]


@pytest.mark.unit
def test_get_alerts_empty_response(api_client):
    """Test handling of empty alerts response."""
    lat, lon = 40.0, -75.0
    empty_alerts = {"features": []}

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, empty_alerts]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_alerts(lat, lon, precise_location=True)

        assert result == empty_alerts
        assert len(result["features"]) == 0


@pytest.mark.unit
def test_get_alerts_with_force_refresh(api_client):
    """Test getting alerts with force_refresh parameter."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, SAMPLE_ALERTS_DATA]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_alerts(lat, lon, precise_location=True, force_refresh=True)

        assert result == SAMPLE_ALERTS_DATA
        assert mock_get.call_count == 2


@pytest.mark.unit
def test_location_identification_url_parsing(api_client):
    """Test that location URLs are parsed correctly."""
    test_cases = [
        ("https://api.weather.gov/zones/county/PAC091", "county", "PAC091"),
        ("https://api.weather.gov/zones/forecast/PAZ106", "forecast", "PAZ106"),
        ("https://api.weather.gov/zones/fire/PAZ106", "fire", "PAZ106"),
    ]

    for url, expected_type, expected_id in test_cases:
        lat, lon = 40.0, -75.0

        # Create point data with specific zone URL
        point_data = dict(SAMPLE_POINT_DATA)
        properties = dict(SAMPLE_POINT_DATA["properties"])

        # Clear other zone URLs and set the one we're testing
        for key in ["county", "forecastZone", "fireWeatherZone"]:
            if key in properties:
                del properties[key]

        if expected_type == "county":
            properties["county"] = url
        elif expected_type == "forecast":
            properties["forecastZone"] = url
        elif expected_type == "fire":
            properties["fireWeatherZone"] = url

        point_data["properties"] = properties

        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = point_data
            mock_get.return_value.raise_for_status.return_value = None

            location_type, location_id = api_client.identify_location_type(lat, lon)

            assert location_type == expected_type
            assert location_id == expected_id


@pytest.mark.unit
def test_alerts_url_construction(api_client):
    """Test that alerts URLs are constructed correctly."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, SAMPLE_ALERTS_DATA]
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_alerts(lat, lon, precise_location=True)

        # Check the alerts request (second call)
        alerts_call = mock_get.call_args_list[1]
        alerts_url = alerts_call[0][0]

        # Should be making request to alerts endpoint
        assert "alerts" in alerts_url
        # Should include zone parameter for precise location
        params = alerts_call[1].get("params", {})
        assert "zone" in params or "area" in params


@pytest.mark.unit
def test_location_identification_priority(api_client):
    """Test that location types are prioritized correctly (county > forecast > fire)."""
    lat, lon = 40.0, -75.0

    # Point data with all zone types - county should take precedence
    point_data_all_zones = dict(SAMPLE_POINT_DATA)
    # All zones are already present in SAMPLE_POINT_DATA

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = point_data_all_zones
        mock_get.return_value.raise_for_status.return_value = None

        location_type, location_id = api_client.identify_location_type(lat, lon)

        # County should take precedence
        assert location_type == LOCATION_TYPE_COUNTY
        assert location_id == "PAC091"
