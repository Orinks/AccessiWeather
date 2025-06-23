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


@pytest.mark.unit
def test_get_alerts_point_based_vs_zone_based(api_wrapper):
    """Test that point-based alerts (precise_location=True) vs zone-based alerts (precise_location=False) call different logic."""
    lat, lon = TEST_LAT, TEST_LON

    # Test point-based alerts (precise_location=True)
    api_wrapper.get_alerts(lat, lon, precise_location=True)
    api_wrapper.nws_wrapper.get_alerts.assert_called_with(
        lat, lon, radius=50, precise_location=True, force_refresh=False
    )

    # Reset mock
    api_wrapper.nws_wrapper.get_alerts.reset_mock()

    # Test zone-based alerts (precise_location=False)
    api_wrapper.get_alerts(lat, lon, precise_location=False)
    api_wrapper.nws_wrapper.get_alerts.assert_called_with(
        lat, lon, radius=50, precise_location=False, force_refresh=False
    )


@pytest.mark.unit
def test_get_alerts_lumberton_coordinates(api_wrapper):
    """Test alerts retrieval with actual Lumberton Township coordinates."""
    # Lumberton Township, NJ coordinates
    lat, lon = 39.9659459, -74.8051628

    # Test point-based alerts for Lumberton
    result = api_wrapper.get_alerts(lat, lon, precise_location=True)

    assert result == SAMPLE_ALERTS_DATA
    api_wrapper.nws_wrapper.get_alerts.assert_called_once_with(
        lat, lon, radius=50, precise_location=True, force_refresh=False
    )


@pytest.mark.unit
def test_get_alerts_default_precise_location_setting(api_wrapper):
    """Test that the default precise_location setting is used correctly."""
    lat, lon = TEST_LAT, TEST_LON

    # Test with default parameters (should use precise_location=True by default)
    api_wrapper.get_alerts(lat, lon)

    api_wrapper.nws_wrapper.get_alerts.assert_called_once_with(
        lat, lon, radius=50, precise_location=True, force_refresh=False
    )
