"""Mock client fixtures for API testing."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import NoaaApiClient
from accessiweather.api_wrapper import NoaaApiWrapper
from accessiweather.geocoding import GeocodingService
from accessiweather.location import LocationManager
from accessiweather.notifications import WeatherNotifier
from accessiweather.openmeteo_client import OpenMeteoApiClient
from accessiweather.services.weather_service import WeatherService


@pytest.fixture
def mock_nws_client():
    """Mock NWS API client."""
    return MagicMock(spec=NoaaApiClient)


@pytest.fixture
def mock_nws_wrapper():
    """Mock NWS API wrapper."""
    return MagicMock(spec=NoaaApiWrapper)


@pytest.fixture
def mock_openmeteo_client():
    """Mock Open-Meteo API client."""
    return MagicMock(spec=OpenMeteoApiClient)


@pytest.fixture
def mock_geocoding_service():
    """Mock geocoding service."""
    mock_service = MagicMock(spec=GeocodingService)

    # Mock geocode method to return sample location
    mock_service.geocode.return_value = {
        "name": "New York, NY, USA",
        "lat": 40.7128,
        "lon": -74.0060,
        "country_code": "us",
    }

    # Mock reverse_geocode method
    mock_service.reverse_geocode.return_value = {"name": "New York, NY, USA", "country_code": "us"}

    # Mock suggest_locations to return sample suggestions
    mock_service.suggest_locations.return_value = [
        "New York, NY, USA",
        "Newark, NJ, USA",
        "New Haven, CT, USA",
    ]

    # Mock utility methods
    mock_service.is_zip_code.return_value = False
    mock_service.format_zip_code.return_value = "12345, USA"

    return mock_service


@pytest.fixture
def mock_nominatim():
    """Mock Nominatim geocoder for direct usage."""
    mock_nominatim = MagicMock()

    # Create a mock location for geocode responses
    mock_location = MagicMock()
    mock_location.latitude = 40.7128
    mock_location.longitude = -74.0060
    mock_location.address = "New York, NY, USA"
    mock_location.raw = {"address": {"country_code": "us"}}

    mock_nominatim.geocode.return_value = mock_location
    mock_nominatim.reverse.return_value = mock_location

    return mock_nominatim


@pytest.fixture(autouse=True)
def mock_all_geocoding():
    """Automatically mock all geocoding API calls across all tests."""
    with patch("accessiweather.geocoding.Nominatim") as mock_nominatim_class:
        # Create mock instance
        mock_nominatim_instance = MagicMock()
        mock_nominatim_class.return_value = mock_nominatim_instance

        # Create mock location response
        mock_location = MagicMock()
        mock_location.latitude = 40.7128
        mock_location.longitude = -74.0060
        mock_location.address = "New York, NY, USA"
        mock_location.raw = {"address": {"country_code": "us"}}

        # Configure geocode method
        mock_nominatim_instance.geocode.return_value = mock_location

        # Configure reverse method for coordinate validation
        def reverse_side_effect(coords, **kwargs):
            lat, lon = coords
            # Return US location for US coordinates, non-US for others
            if 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0:
                mock_us_location = MagicMock()
                mock_us_location.raw = {"address": {"country_code": "us"}}
                return mock_us_location
            mock_intl_location = MagicMock()
            mock_intl_location.raw = {"address": {"country_code": "gb"}}
            return mock_intl_location

        mock_nominatim_instance.reverse.side_effect = reverse_side_effect

        yield mock_nominatim_instance


@pytest.fixture
def location_manager(temp_config_dir):
    """Create a LocationManager with temp config directory and mocked geocoding."""
    # The geocoding is already mocked by the autouse fixture
    return LocationManager(config_dir=temp_config_dir)


@pytest.fixture
def weather_notifier(temp_config_dir):
    """Create a WeatherNotifier with temp config directory."""
    return WeatherNotifier(config_dir=temp_config_dir, enable_persistence=True)


@pytest.fixture
def weather_service(mock_nws_wrapper, mock_openmeteo_client, sample_config):
    """Create a WeatherService with mocked clients."""
    return WeatherService(
        nws_client=mock_nws_wrapper, openmeteo_client=mock_openmeteo_client, config=sample_config
    )
