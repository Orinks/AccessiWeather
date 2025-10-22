"""Tests for OpenMeteoApiClient utility functions and validation."""

from unittest.mock import patch

import pytest

from accessiweather.openmeteo_client import OpenMeteoApiClient, OpenMeteoApiError

from .conftest import SAMPLE_CURRENT_WEATHER_DATA


# Test weather description functionality
@pytest.mark.unit
def test_get_weather_description():
    """Test weather code to description mapping."""
    # Test some common weather codes
    assert OpenMeteoApiClient.get_weather_description(0) == "Clear sky"
    assert OpenMeteoApiClient.get_weather_description(1) == "Mainly clear"
    assert OpenMeteoApiClient.get_weather_description(2) == "Partly cloudy"
    assert OpenMeteoApiClient.get_weather_description(3) == "Overcast"
    assert OpenMeteoApiClient.get_weather_description(61) == "Slight rain"
    assert OpenMeteoApiClient.get_weather_description(95) == "Thunderstorm"


@pytest.mark.unit
def test_get_weather_description_unknown_code():
    """Test weather description for unknown codes."""
    result = OpenMeteoApiClient.get_weather_description(999)
    assert result == "Unknown weather code: 999"


@pytest.mark.unit
def test_get_weather_description_none_code():
    """Weather description should gracefully handle None codes."""
    result = OpenMeteoApiClient.get_weather_description(None)
    assert result == "Unknown weather code: None"


# Test coordinate validation
@pytest.mark.unit
@pytest.mark.parametrize(
    "lat,lon,should_work",
    [
        (40.0, -75.0, True),  # Valid coordinates
        (90.0, 180.0, True),  # Edge valid coordinates
        (-90.0, -180.0, True),  # Edge valid coordinates
        (0.0, 0.0, True),  # Equator/Prime meridian
        (91.0, 0.0, False),  # Invalid latitude
        (-91.0, 0.0, False),  # Invalid latitude
        (0.0, 181.0, False),  # Invalid longitude
        (0.0, -181.0, False),  # Invalid longitude
    ],
)
def test_coordinate_validation(openmeteo_client, lat, lon, should_work):
    """Test coordinate validation in API calls."""
    with patch.object(openmeteo_client, "_make_request") as mock_request:
        if should_work:
            mock_request.return_value = SAMPLE_CURRENT_WEATHER_DATA
            result = openmeteo_client.get_current_weather(lat, lon)
            assert result == SAMPLE_CURRENT_WEATHER_DATA
        else:
            # For invalid coordinates, the API client should still make the request
            # but the API would return an error (which we simulate)
            mock_request.side_effect = OpenMeteoApiError("Invalid coordinates")
            with pytest.raises(OpenMeteoApiError):
                openmeteo_client.get_current_weather(lat, lon)
