"""Tests for NoaaApiWrapper alerts management functionality."""

from unittest.mock import patch

import pytest

from .conftest import SAMPLE_ALERTS_DATA, TEST_LAT, TEST_LON


@pytest.mark.unit
def test_get_alerts_success(api_wrapper):
    """Test successful alerts retrieval."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_alerts") as mock_get_alerts:
        mock_get_alerts.return_value = SAMPLE_ALERTS_DATA

        result = api_wrapper.get_alerts(lat, lon)

        assert result == SAMPLE_ALERTS_DATA
        mock_get_alerts.assert_called_once_with(
            lat, lon, radius=50, precise_location=True, force_refresh=False
        )


@pytest.mark.unit
def test_get_alerts_with_county_zone(api_wrapper):
    """Test get_alerts with county zone identification."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "identify_location_type") as mock_identify:
        with patch.object(api_wrapper.nws_wrapper, "_make_api_request") as mock_request:
            mock_identify.return_value = ("county", "PAC101")
            mock_request.return_value = SAMPLE_ALERTS_DATA

            result = api_wrapper.get_alerts(lat, lon, precise_location=True)

            assert result == SAMPLE_ALERTS_DATA
            mock_identify.assert_called_once_with(lat, lon, force_refresh=False)
            mock_request.assert_called_once()


@pytest.mark.unit
def test_get_alerts_with_state_fallback(api_wrapper):
    """Test get_alerts with state fallback when precise_location=False."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "identify_location_type") as mock_identify:
        with patch.object(api_wrapper.nws_wrapper, "_fetch_url") as mock_fetch:
            mock_identify.return_value = ("state", "PA")
            mock_fetch.return_value = SAMPLE_ALERTS_DATA

            result = api_wrapper.get_alerts(lat, lon, precise_location=False)

            assert result == SAMPLE_ALERTS_DATA
            mock_identify.assert_called_once_with(lat, lon, force_refresh=False)
            expected_url = f"{api_wrapper.nws_wrapper.BASE_URL}/alerts/active?area=PA"
            mock_fetch.assert_called_once_with(expected_url)


@pytest.mark.unit
def test_get_alerts_with_point_radius_fallback(api_wrapper):
    """Test get_alerts with point-radius fallback when location cannot be determined."""
    lat, lon = TEST_LAT, TEST_LON
    radius = 50

    with patch.object(api_wrapper.nws_wrapper, "identify_location_type") as mock_identify:
        with patch.object(api_wrapper.nws_wrapper, "_fetch_url") as mock_fetch:
            mock_identify.return_value = (None, None)
            mock_fetch.return_value = SAMPLE_ALERTS_DATA

            result = api_wrapper.get_alerts(lat, lon, radius=radius)

            assert result == SAMPLE_ALERTS_DATA
            mock_identify.assert_called_once_with(lat, lon, force_refresh=False)
            expected_url = f"{api_wrapper.nws_wrapper.BASE_URL}/alerts/active?point={lat},{lon}&radius={radius}"
            mock_fetch.assert_called_once_with(expected_url)
