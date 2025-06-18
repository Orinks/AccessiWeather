"""Tests for NoaaApiWrapper alerts management functionality."""

import pytest

from .conftest import SAMPLE_ALERTS_DATA, TEST_LAT, TEST_LON


@pytest.mark.unit
def test_get_alerts_success(api_wrapper):
    """Test successful alerts retrieval."""
    lat, lon = TEST_LAT, TEST_LON

    # The mock is already configured in conftest.py to return SAMPLE_ALERTS_DATA
    result = api_wrapper.get_alerts(lat, lon)

    assert result == SAMPLE_ALERTS_DATA
    api_wrapper.nws_wrapper.get_alerts.assert_called_once_with(
        lat, lon, radius=50, precise_location=True, force_refresh=False
    )


@pytest.mark.unit
def test_get_alerts_with_county_zone(api_wrapper):
    """Test get_alerts with county zone identification."""
    lat, lon = TEST_LAT, TEST_LON

    # The mock is already configured in conftest.py to return SAMPLE_ALERTS_DATA
    result = api_wrapper.get_alerts(lat, lon, precise_location=True)

    assert result == SAMPLE_ALERTS_DATA
    api_wrapper.nws_wrapper.get_alerts.assert_called_once_with(
        lat, lon, radius=50, precise_location=True, force_refresh=False
    )


@pytest.mark.unit
def test_get_alerts_with_state_fallback(api_wrapper):
    """Test get_alerts with state fallback when precise_location=False."""
    lat, lon = TEST_LAT, TEST_LON

    # The mock is already configured in conftest.py to return SAMPLE_ALERTS_DATA
    result = api_wrapper.get_alerts(lat, lon, precise_location=False)

    assert result == SAMPLE_ALERTS_DATA
    api_wrapper.nws_wrapper.get_alerts.assert_called_once_with(
        lat, lon, radius=50, precise_location=False, force_refresh=False
    )


@pytest.mark.unit
def test_get_alerts_with_point_radius_fallback(api_wrapper):
    """Test get_alerts with point-radius fallback when location cannot be determined."""
    lat, lon = TEST_LAT, TEST_LON
    radius = 50

    # The mock is already configured in conftest.py to return SAMPLE_ALERTS_DATA
    result = api_wrapper.get_alerts(lat, lon, radius=radius)

    assert result == SAMPLE_ALERTS_DATA
    api_wrapper.nws_wrapper.get_alerts.assert_called_once_with(
        lat, lon, radius=radius, precise_location=True, force_refresh=False
    )
