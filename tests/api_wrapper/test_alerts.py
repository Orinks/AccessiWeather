"""Tests for NoaaApiWrapper alerts functionality."""

from unittest.mock import patch

import pytest

from accessiweather.api_client import NoaaApiError
from tests.api_wrapper_test_utils import (
    SAMPLE_ALERTS_DATA,
    SAMPLE_POINT_DATA,
    api_wrapper,
    cached_api_wrapper,
)


@pytest.mark.unit
def test_get_alerts_direct_success(api_wrapper):
    """Test successful direct alerts retrieval."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    with patch.object(api_wrapper, "_make_api_request") as mock_request:
        mock_request.return_value = SAMPLE_ALERTS_DATA

        result = api_wrapper.get_alerts_direct(lat, lon, radius_miles)

        assert result == SAMPLE_ALERTS_DATA
        mock_request.assert_called_once()

        # Verify the correct alerts URL was used
        call_args = mock_request.call_args[0]
        assert "alerts" in call_args[0]
        assert f"point={lat},{lon}" in call_args[0]


@pytest.mark.unit
def test_get_alerts_direct_with_caching(cached_api_wrapper):
    """Test direct alerts retrieval with caching."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    with patch.object(cached_api_wrapper, "_make_api_request") as mock_request:
        mock_request.return_value = SAMPLE_ALERTS_DATA

        # First call should make API request
        result1 = cached_api_wrapper.get_alerts_direct(lat, lon, radius_miles)
        assert result1 == SAMPLE_ALERTS_DATA
        assert mock_request.call_count == 1

        # Second call should use cache
        result2 = cached_api_wrapper.get_alerts_direct(lat, lon, radius_miles)
        assert result2 == SAMPLE_ALERTS_DATA
        assert mock_request.call_count == 1  # No additional calls


@pytest.mark.unit
def test_get_alerts_direct_error_handling(api_wrapper):
    """Test error handling in get_alerts_direct."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    with patch.object(api_wrapper, "_make_api_request") as mock_request:
        mock_request.side_effect = NoaaApiError("Alerts error", NoaaApiError.SERVER_ERROR)

        with pytest.raises(NoaaApiError):
            api_wrapper.get_alerts_direct(lat, lon, radius_miles)


@pytest.mark.unit
def test_get_alerts_with_county_zone(api_wrapper):
    """Test get_alerts with county zone identification."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        mock_identify.return_value = ("county", "https://api.weather.gov/zones/county/PAC101")

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_ALERTS_DATA

            result = api_wrapper.get_alerts(lat, lon, radius_miles, precise_location=True)

            assert result == SAMPLE_ALERTS_DATA
            mock_identify.assert_called_once_with(lat, lon)
            mock_request.assert_called_once()

            # Verify zone-based alerts URL was used
            call_args = mock_request.call_args[0]
            assert "alerts" in call_args[0]
            assert "zone=PAC101" in call_args[0]


@pytest.mark.unit
def test_get_alerts_with_state_fallback(api_wrapper):
    """Test get_alerts with state fallback when precise_location=False."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        mock_identify.return_value = ("state", "PA")

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_ALERTS_DATA

            result = api_wrapper.get_alerts(lat, lon, radius_miles, precise_location=False)

            assert result == SAMPLE_ALERTS_DATA
            mock_identify.assert_called_once_with(lat, lon)
            mock_request.assert_called_once()

            # Verify state-based alerts URL was used
            call_args = mock_request.call_args[0]
            assert "alerts" in call_args[0]
            assert "area=PA" in call_args[0]


@pytest.mark.unit
def test_get_alerts_with_point_radius_fallback(api_wrapper):
    """Test get_alerts with point-radius fallback when location cannot be determined."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        mock_identify.return_value = (None, None)

        with patch.object(api_wrapper, "get_alerts_direct") as mock_direct:
            mock_direct.return_value = SAMPLE_ALERTS_DATA

            result = api_wrapper.get_alerts(lat, lon, radius_miles, precise_location=True)

            assert result == SAMPLE_ALERTS_DATA
            mock_identify.assert_called_once_with(lat, lon)
            mock_direct.assert_called_once_with(lat, lon, radius_miles)


@pytest.mark.unit
def test_get_alerts_with_force_refresh(api_wrapper):
    """Test get_alerts with force_refresh parameter."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        mock_identify.return_value = ("county", "https://api.weather.gov/zones/county/PAC101")

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_ALERTS_DATA

            result = api_wrapper.get_alerts(lat, lon, radius_miles, force_refresh=True)

            assert result == SAMPLE_ALERTS_DATA
            # force_refresh should be passed to identify_location_type if it accepts it


@pytest.mark.unit
def test_get_alerts_with_different_radius_values(api_wrapper):
    """Test get_alerts with different radius values."""
    lat, lon = 40.0, -75.0

    test_radii = [10, 25, 50, 100]

    for radius in test_radii:
        with patch.object(api_wrapper, "get_alerts_direct") as mock_direct:
            mock_direct.return_value = SAMPLE_ALERTS_DATA

            with patch.object(api_wrapper, "identify_location_type") as mock_identify:
                mock_identify.return_value = (None, None)  # Force fallback to direct

                result = api_wrapper.get_alerts(lat, lon, radius, precise_location=True)

                assert result == SAMPLE_ALERTS_DATA
                mock_direct.assert_called_once_with(lat, lon, radius)


@pytest.mark.unit
def test_get_alerts_with_invalid_coordinates(api_wrapper):
    """Test get_alerts with invalid coordinates."""
    lat, lon = 999.0, 999.0
    radius_miles = 25

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        mock_identify.side_effect = NoaaApiError("Invalid coordinates", NoaaApiError.CLIENT_ERROR)

        with pytest.raises(NoaaApiError):
            api_wrapper.get_alerts(lat, lon, radius_miles)


@pytest.mark.unit
def test_get_alerts_with_empty_response(api_wrapper):
    """Test get_alerts with empty alerts response."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    empty_alerts = {"features": []}

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        mock_identify.return_value = ("county", "https://api.weather.gov/zones/county/PAC101")

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = empty_alerts

            result = api_wrapper.get_alerts(lat, lon, radius_miles)

            assert result == empty_alerts
            assert len(result["features"]) == 0


@pytest.mark.unit
def test_get_alerts_with_multiple_zones(api_wrapper):
    """Test get_alerts when location has multiple zone types."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    # Test with forecast zone when county is not available
    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        mock_identify.return_value = ("forecast", "https://api.weather.gov/zones/forecast/PAZ103")

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_ALERTS_DATA

            result = api_wrapper.get_alerts(lat, lon, radius_miles, precise_location=True)

            assert result == SAMPLE_ALERTS_DATA
            call_args = mock_request.call_args[0]
            assert "zone=PAZ103" in call_args[0]


@pytest.mark.unit
def test_get_alerts_url_construction(api_wrapper):
    """Test proper construction of alerts URLs."""
    lat, lon = 40.0, -75.0
    radius_miles = 25

    # Test direct alerts URL
    with patch.object(api_wrapper, "_make_api_request") as mock_request:
        mock_request.return_value = SAMPLE_ALERTS_DATA

        api_wrapper.get_alerts_direct(lat, lon, radius_miles)

        call_args = mock_request.call_args[0]
        url = call_args[0]

        # Verify URL components
        assert "alerts" in url
        assert f"point={lat},{lon}" in url
        # Radius might be converted to different units or format


@pytest.mark.unit
def test_get_alerts_with_marine_zones(api_wrapper):
    """Test get_alerts with marine zone identification."""
    lat, lon = 30.0, -80.0  # Ocean coordinates
    radius_miles = 25

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        mock_identify.return_value = ("forecast", "https://api.weather.gov/zones/forecast/AMZ550")

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_ALERTS_DATA

            result = api_wrapper.get_alerts(lat, lon, radius_miles, precise_location=True)

            assert result == SAMPLE_ALERTS_DATA
            call_args = mock_request.call_args[0]
            assert "zone=AMZ550" in call_args[0]  # Marine zone
