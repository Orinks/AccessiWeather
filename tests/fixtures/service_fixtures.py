"""Service-related test fixtures."""

import pytest

from accessiweather.location import LocationManager
from accessiweather.notifications import WeatherNotifier
from accessiweather.services.weather_service import WeatherService


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
