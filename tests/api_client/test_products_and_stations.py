"""Tests for NoaaApiClient products and stations functionality."""

from unittest.mock import patch

import pytest

from tests.api_client_test_utils import (
    SAMPLE_POINT_DATA,
    SAMPLE_DISCUSSION_PRODUCTS,
    SAMPLE_DISCUSSION_TEXT,
    SAMPLE_NATIONAL_PRODUCT,
    SAMPLE_NATIONAL_PRODUCT_TEXT,
    SAMPLE_STATIONS_DATA,
    SAMPLE_OBSERVATION_DATA,
    api_client,
)


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


def test_get_stations_success(api_client):
    """Test getting observation stations successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, SAMPLE_STATIONS_DATA]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_stations(lat, lon)

        assert result == SAMPLE_STATIONS_DATA
        assert mock_get.call_count == 2


def test_get_stations_no_url(api_client):
    """Test getting stations when point data doesn't contain stations URL."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create point data without stations URL
        bad_point_data = dict(SAMPLE_POINT_DATA)
        properties = {}
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
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_STATIONS_DATA,
            SAMPLE_OBSERVATION_DATA,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_current_conditions(lat, lon)

        assert result == SAMPLE_OBSERVATION_DATA
        assert mock_get.call_count == 3


def test_get_current_conditions_no_stations(api_client):
    """Test getting current conditions when no stations are available."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        empty_stations = {"features": []}
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, empty_stations]
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError) as exc_info:
            api_client.get_current_conditions(lat, lon)

        assert "No observation stations found" in str(exc_info.value)


@pytest.mark.unit
def test_get_discussion_url_construction(api_client):
    """Test that discussion URLs are constructed correctly."""
    lat, lon = 40.0, -75.0
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_DISCUSSION_PRODUCTS,
            SAMPLE_DISCUSSION_TEXT,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_discussion(lat, lon)

        # Verify the correct sequence of calls
        assert mock_get.call_count == 3
        
        # First call should be for point data
        point_call = mock_get.call_args_list[0]
        assert "points" in point_call[0][0]
        
        # Second call should be for discussion products
        products_call = mock_get.call_args_list[1]
        assert "products" in products_call[0][0]
        
        # Third call should be for specific discussion text
        text_call = mock_get.call_args_list[2]
        assert "AFD-PHI-202401010000" in text_call[0][0]


@pytest.mark.unit
def test_get_national_product_url_construction(api_client):
    """Test that national product URLs are constructed correctly."""
    product_type = "FXUS01"
    location = "KWNH"
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_NATIONAL_PRODUCT,
            SAMPLE_NATIONAL_PRODUCT_TEXT,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_national_product(product_type, location)

        # Verify the correct sequence of calls
        assert mock_get.call_count == 2
        
        # First call should be for product list
        products_call = mock_get.call_args_list[0]
        products_url = products_call[0][0]
        assert "products" in products_url
        assert product_type in products_url
        assert location in products_url
        
        # Second call should be for specific product text
        text_call = mock_get.call_args_list[1]
        assert "FXUS01-KWNH-202401010000" in text_call[0][0]


@pytest.mark.unit
def test_get_stations_url_extraction(api_client):
    """Test that stations URL is extracted correctly from point data."""
    lat, lon = 40.0, -75.0
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, SAMPLE_STATIONS_DATA]
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_stations(lat, lon)

        # Verify the stations URL was used correctly
        assert mock_get.call_count == 2
        stations_call = mock_get.call_args_list[1]
        stations_url = stations_call[0][0]
        expected_url = SAMPLE_POINT_DATA["properties"]["observationStations"]
        assert stations_url == expected_url


@pytest.mark.unit
def test_get_current_conditions_station_selection(api_client):
    """Test that the first available station is selected for current conditions."""
    lat, lon = 40.0, -75.0
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_STATIONS_DATA,
            SAMPLE_OBSERVATION_DATA,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_current_conditions(lat, lon)

        # Verify the correct station was used
        assert mock_get.call_count == 3
        observation_call = mock_get.call_args_list[2]
        observation_url = observation_call[0][0]
        
        # Should use the first station from SAMPLE_STATIONS_DATA
        first_station_id = SAMPLE_STATIONS_DATA["features"][0]["properties"]["stationIdentifier"]
        assert first_station_id in observation_url
        assert "observations/latest" in observation_url


@pytest.mark.unit
def test_get_discussion_with_missing_products(api_client):
    """Test discussion retrieval when no products are found."""
    lat, lon = 40.0, -75.0
    
    with patch("requests.get") as mock_get:
        empty_products = {"@graph": []}
        mock_get.return_value.json.side_effect = [SAMPLE_POINT_DATA, empty_products]
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError) as exc_info:
            api_client.get_discussion(lat, lon)

        assert "No discussion products found" in str(exc_info.value)


@pytest.mark.unit
def test_get_national_product_with_missing_products(api_client):
    """Test national product retrieval when no products are found."""
    product_type = "FXUS01"
    location = "KWNH"
    
    with patch("requests.get") as mock_get:
        empty_products = {"@graph": []}
        mock_get.return_value.json.return_value = empty_products
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError) as exc_info:
            api_client.get_national_product(product_type, location)

        assert "No products found" in str(exc_info.value)


@pytest.mark.unit
def test_get_current_conditions_with_observation_error(api_client):
    """Test current conditions when observation request fails."""
    lat, lon = 40.0, -75.0
    
    with patch("requests.get") as mock_get:
        from requests.exceptions import HTTPError
        from unittest.mock import MagicMock
        
        def side_effect(*args, **kwargs):
            if "points" in args[0]:
                resp = MagicMock()
                resp.json.return_value = SAMPLE_POINT_DATA
                resp.raise_for_status.return_value = None
                return resp
            elif "stations" in args[0]:
                resp = MagicMock()
                resp.json.return_value = SAMPLE_STATIONS_DATA
                resp.raise_for_status.return_value = None
                return resp
            else:
                # Observation request fails
                mock_response = MagicMock()
                mock_response.status_code = 404
                http_error = HTTPError("404 Not Found")
                http_error.response = mock_response
                raise http_error
        
        mock_get.side_effect = side_effect

        from accessiweather.api_client import NoaaApiError
        with pytest.raises(NoaaApiError):
            api_client.get_current_conditions(lat, lon)


@pytest.mark.unit
def test_product_text_extraction(api_client):
    """Test that product text is extracted correctly from responses."""
    # Test discussion text extraction
    lat, lon = 40.0, -75.0
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_DISCUSSION_PRODUCTS,
            SAMPLE_DISCUSSION_TEXT,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_discussion(lat, lon)

        # Should extract and clean the product text
        expected_text = SAMPLE_DISCUSSION_TEXT["productText"].strip()
        assert result.strip() == expected_text
        
    # Test national product text extraction
    product_type = "FXUS01"
    location = "KWNH"
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_NATIONAL_PRODUCT,
            SAMPLE_NATIONAL_PRODUCT_TEXT,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_national_product(product_type, location)

        # Should return the raw product text
        assert result == SAMPLE_NATIONAL_PRODUCT_TEXT["productText"]
