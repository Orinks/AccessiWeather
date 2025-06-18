"""Tests for NoaaApiWrapper location identification functionality."""

import pytest

from .conftest import TEST_LAT, TEST_LON


@pytest.mark.unit
def test_identify_location_type_county(api_wrapper):
    """Test identifying county location type."""
    lat, lon = TEST_LAT, TEST_LON

    # Configure the mock to return the expected tuple for this specific test
    api_wrapper.nws_wrapper.identify_location_type.return_value = ("county", "PAC101")

    location_type, location_id = api_wrapper.identify_location_type(lat, lon)

    assert location_type == "county"
    assert location_id == "PAC101"
    api_wrapper.nws_wrapper.identify_location_type.assert_called_once_with(
        lat, lon, force_refresh=False
    )


@pytest.mark.unit
def test_identify_location_type_forecast_zone(api_wrapper):
    """Test identifying forecast zone location type."""
    lat, lon = TEST_LAT, TEST_LON

    # Configure the mock to return the expected tuple for this specific test
    api_wrapper.nws_wrapper.identify_location_type.return_value = ("forecast", "PAZ103")

    location_type, location_id = api_wrapper.identify_location_type(lat, lon)

    assert location_type == "forecast"
    assert location_id == "PAZ103"


@pytest.mark.unit
def test_identify_location_type_fire_zone(api_wrapper):
    """Test identifying fire weather zone location type."""
    lat, lon = TEST_LAT, TEST_LON

    # Configure the mock to return the expected tuple for this specific test
    api_wrapper.nws_wrapper.identify_location_type.return_value = ("fire", "PAZ103")

    location_type, location_id = api_wrapper.identify_location_type(lat, lon)

    assert location_type == "fire"
    assert location_id == "PAZ103"


@pytest.mark.unit
def test_identify_location_type_state_fallback(api_wrapper):
    """Test falling back to state when no specific zone is found."""
    lat, lon = TEST_LAT, TEST_LON

    # Configure the mock to return the expected tuple for this specific test
    api_wrapper.nws_wrapper.identify_location_type.return_value = ("state", "PA")

    location_type, location_id = api_wrapper.identify_location_type(lat, lon)

    assert location_type == "state"
    assert location_id == "PA"


@pytest.mark.unit
def test_identify_location_type_none(api_wrapper):
    """Test when location type cannot be determined."""
    lat, lon = TEST_LAT, TEST_LON

    # Configure the mock to return None values for this specific test
    api_wrapper.nws_wrapper.identify_location_type.return_value = (None, None)

    location_type, location_id = api_wrapper.identify_location_type(lat, lon)

    assert location_type is None
    assert location_id is None


@pytest.mark.unit
def test_identify_location_type_error_handling(api_wrapper):
    """Test error handling in identify_location_type."""
    lat, lon = TEST_LAT, TEST_LON

    # Configure the mock to return None values when an error occurs
    api_wrapper.nws_wrapper.identify_location_type.return_value = (None, None)

    location_type, location_id = api_wrapper.identify_location_type(lat, lon)

    assert location_type is None
    assert location_id is None
