"""Tests for WeatherService location detection functionality."""

from unittest.mock import patch

import pytest

from tests.services.weather_service_test_utils import weather_service


@pytest.mark.unit
def test_should_use_openmeteo_us_location(weather_service):
    """Test that NWS is preferred for US locations."""
    # Set the data source to auto for this test
    weather_service.config = {"settings": {"data_source": "auto"}}

    # US coordinates (New York)
    lat, lon = 40.7128, -74.0060

    # Mock the geocoding service to return True for US location
    with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
        mock_geocoding_instance = mock_geocoding_class.return_value
        mock_geocoding_instance.validate_coordinates.return_value = True

        result = weather_service._should_use_openmeteo(lat, lon)

    assert result is False


@pytest.mark.unit
def test_should_use_openmeteo_non_us_location(weather_service):
    """Test that Open-Meteo is used for non-US locations."""
    # Set the data source to auto for this test
    weather_service.config = {"settings": {"data_source": "auto"}}

    # London coordinates
    lat, lon = 51.5074, -0.1278

    # Mock the geocoding service to return False for non-US location
    with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
        mock_geocoding_instance = mock_geocoding_class.return_value
        mock_geocoding_instance.validate_coordinates.return_value = False

        result = weather_service._should_use_openmeteo(lat, lon)

    assert result is True


@pytest.mark.unit
def test_should_use_openmeteo_edge_cases(weather_service):
    """Test edge cases for location detection."""
    # Set the data source to auto for this test
    weather_service.config = {"settings": {"data_source": "auto"}}

    # Test coordinates at US borders
    test_cases = [
        (49.0, -125.0, True),  # Canada (north of US)
        (25.0, -80.0, False),  # Florida (US)
        (32.0, -117.0, False),  # California (US)
        (19.0, -155.0, False),  # Hawaii (US)
        (64.0, -153.0, False),  # Alaska (US)
    ]

    # Mock the geocoding service to return appropriate values
    with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
        mock_geocoding_instance = mock_geocoding_class.return_value

        for lat, lon, expected in test_cases:
            # Set the mock to return False for non-US (expected=True) and True for US (expected=False)
            mock_geocoding_instance.validate_coordinates.return_value = not expected

            result = weather_service._should_use_openmeteo(lat, lon)
            assert result == expected, f"Failed for coordinates ({lat}, {lon})"
