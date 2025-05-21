"""Tests for the WeatherService class."""

from unittest.mock import MagicMock

import pytest

from accessiweather.api_client import NoaaApiClient
from accessiweather.gui.settings_dialog import DATA_SOURCE_NWS, DATA_SOURCE_WEATHERAPI
from accessiweather.services.weather_service import ConfigurationError, WeatherService
from accessiweather.weatherapi_wrapper import WeatherApiWrapper


@pytest.fixture
def mock_nws_client():
    """Create a mock NWS API client."""
    mock = MagicMock(spec=NoaaApiClient)
    return mock


@pytest.fixture
def mock_weatherapi_wrapper():
    """Create a mock WeatherAPI.com wrapper."""
    mock = MagicMock(spec=WeatherApiWrapper)
    return mock


@pytest.fixture
def weather_service(mock_nws_client, mock_weatherapi_wrapper):
    """Create a WeatherService instance with mock clients."""
    config = {
        "settings": {"data_source": DATA_SOURCE_NWS},
        "api_keys": {"weatherapi": "test_key"},
    }
    return WeatherService(
        nws_client=mock_nws_client,
        weatherapi_wrapper=mock_weatherapi_wrapper,
        config=config,
    )


class TestWeatherService:
    """Tests for the WeatherService class."""

    def test_init(self, mock_nws_client, mock_weatherapi_wrapper):
        """Test initialization of WeatherService."""
        config = {
            "settings": {"data_source": DATA_SOURCE_NWS},
            "api_keys": {"weatherapi": "test_key"},
        }
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=mock_weatherapi_wrapper,
            config=config,
        )
        assert service.nws_client == mock_nws_client
        assert service.weatherapi_wrapper == mock_weatherapi_wrapper
        assert service.config == config

    def test_get_data_source_default(self, mock_nws_client, mock_weatherapi_wrapper):
        """Test get_data_source returns default value when not in config."""
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=mock_weatherapi_wrapper,
            config={},
        )
        assert service._get_data_source() == DATA_SOURCE_NWS

    def test_get_data_source_from_config(self, mock_nws_client, mock_weatherapi_wrapper):
        """Test get_data_source returns value from config."""
        config = {"settings": {"data_source": DATA_SOURCE_WEATHERAPI}}
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=mock_weatherapi_wrapper,
            config=config,
        )
        assert service._get_data_source() == DATA_SOURCE_WEATHERAPI

    def test_check_weatherapi_key_missing(self, mock_nws_client, mock_weatherapi_wrapper):
        """Test check_weatherapi_key raises error when key is missing."""
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=mock_weatherapi_wrapper,
            config={},
        )
        with pytest.raises(ConfigurationError):
            service._check_weatherapi_key()

    def test_check_weatherapi_key_present(self, mock_nws_client, mock_weatherapi_wrapper):
        """Test check_weatherapi_key returns key when present."""
        config = {"api_keys": {"weatherapi": "test_key"}}
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=mock_weatherapi_wrapper,
            config=config,
        )
        assert service._check_weatherapi_key() == "test_key"

    def test_get_forecast_nws(self, weather_service, mock_nws_client):
        """Test get_forecast uses NWS client when data source is NWS."""
        # Set up mock return value
        mock_nws_client.get_forecast.return_value = {"forecast": "data"}

        # Call the method
        result = weather_service.get_forecast(lat=40.0, lon=-75.0)

        # Verify the result
        assert result == {"forecast": "data"}
        mock_nws_client.get_forecast.assert_called_once_with(40.0, -75.0, force_refresh=False)

    def test_get_forecast_weatherapi(self, mock_nws_client, mock_weatherapi_wrapper):
        """Test get_forecast uses WeatherAPI wrapper when data source is WeatherAPI."""
        # Set up config and mock return value
        config = {
            "settings": {"data_source": DATA_SOURCE_WEATHERAPI},
            "api_keys": {"weatherapi": "test_key"},
        }
        mock_weatherapi_wrapper.get_forecast.return_value = {"forecast": "data"}

        # Create service with WeatherAPI data source
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=mock_weatherapi_wrapper,
            config=config,
        )

        # Call the method
        result = service.get_forecast(lat=40.0, lon=-75.0)

        # Verify the result
        assert result == {"forecast": "data"}
        mock_weatherapi_wrapper.get_forecast.assert_called_once_with(
            "40.0,-75.0", days=7, alerts=True, force_refresh=False
        )

    def test_get_forecast_weatherapi_missing_wrapper(self, mock_nws_client):
        """Test get_forecast raises error when WeatherAPI is selected but wrapper is None."""
        # Set up config
        config = {
            "settings": {"data_source": DATA_SOURCE_WEATHERAPI},
            "api_keys": {"weatherapi": "test_key"},
        }

        # Create service with WeatherAPI data source but no wrapper
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=None,
            config=config,
        )

        # Call the method and expect error
        with pytest.raises(ConfigurationError):
            service.get_forecast(lat=40.0, lon=-75.0)

    def test_get_alerts_nws(self, weather_service, mock_nws_client):
        """Test get_alerts uses NWS client when data source is NWS."""
        # Set up mock return value
        mock_nws_client.get_alerts.return_value = {"alerts": []}

        # Call the method
        result = weather_service.get_alerts(lat=40.0, lon=-75.0, radius=25, precise_location=True)

        # Verify the result
        assert result == {"alerts": []}
        mock_nws_client.get_alerts.assert_called_once_with(
            40.0, -75.0, radius=25, precise_location=True, force_refresh=False
        )

    def test_get_alerts_weatherapi(self, mock_nws_client, mock_weatherapi_wrapper):
        """Test get_alerts uses WeatherAPI wrapper when data source is WeatherAPI."""
        # Set up config and mock return value
        config = {
            "settings": {"data_source": DATA_SOURCE_WEATHERAPI},
            "api_keys": {"weatherapi": "test_key"},
        }
        mock_weatherapi_wrapper.get_forecast.return_value = {"alerts": ["alert1"]}

        # Create service with WeatherAPI data source
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=mock_weatherapi_wrapper,
            config=config,
        )

        # Call the method
        result = service.get_alerts(lat=40.0, lon=-75.0)

        # Verify the result
        assert result == {"alerts": ["alert1"]}
        mock_weatherapi_wrapper.get_forecast.assert_called_once_with(
            "40.0,-75.0", days=1, alerts=True, force_refresh=False
        )
