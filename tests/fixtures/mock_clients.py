"""Mock client fixtures for API testing."""

from unittest.mock import MagicMock, patch

import pytest

# Import only simple app components to avoid wx dependencies
try:
    from accessiweather.simple.weather_client import WeatherClient
    from accessiweather.simple.location_manager import LocationManager as SimpleLocationManager
    from accessiweather.simple.models import Location, WeatherData, CurrentConditions, Forecast
except ImportError:
    # Fallback for when simple components aren't available
    WeatherClient = None
    SimpleLocationManager = None
    Location = None
    WeatherData = None
    CurrentConditions = None
    Forecast = None


@pytest.fixture
def mock_simple_weather_client():
    """Mock simple weather client for Toga app."""
    if WeatherClient is None:
        return MagicMock()
    return MagicMock(spec=WeatherClient)


@pytest.fixture
def mock_simple_location_manager():
    """Mock simple location manager for Toga app."""
    if SimpleLocationManager is None:
        return MagicMock()
    return MagicMock(spec=SimpleLocationManager)


@pytest.fixture
def mock_simple_location():
    """Mock simple location for Toga app."""
    if Location is None:
        mock_location = MagicMock()
        mock_location.name = "New York, NY"
        mock_location.latitude = 40.7128
        mock_location.longitude = -74.0060
        return mock_location

    return Location(name="New York, NY", latitude=40.7128, longitude=-74.0060)


@pytest.fixture
def mock_simple_weather_data():
    """Mock simple weather data for Toga app."""
    if WeatherData is None or CurrentConditions is None or Forecast is None:
        return MagicMock()

    from datetime import datetime
    location = Location(name="Test City", latitude=40.7128, longitude=-74.0060)
    current = CurrentConditions(temperature_f=75.0, condition="Sunny")
    forecast = Forecast(periods=[])

    return WeatherData(
        location=location,
        current=current,
        forecast=forecast,
        last_updated=datetime.now()
    )


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
def simple_location_manager():
    """Create a simple LocationManager for Toga app."""
    if SimpleLocationManager is None:
        return MagicMock()
    return SimpleLocationManager()


@pytest.fixture
def simple_weather_client():
    """Create a simple WeatherClient for Toga app."""
    if WeatherClient is None:
        return MagicMock()
    return WeatherClient(data_source="auto")
