"""Tests for the automatic weather source selection feature."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.gui.settings_dialog import DATA_SOURCE_AUTO
from accessiweather.services.weather_service import ConfigurationError, WeatherService


class TestAutomaticWeatherSource:
    """Tests for the automatic weather source selection feature."""

    @pytest.fixture
    def mock_nws_client(self):
        """Create a mock NWS client."""
        mock = MagicMock()
        mock.get_forecast.return_value = {"forecast": "nws_data"}
        mock.get_hourly_forecast.return_value = {"hourly": "nws_hourly_data"}
        mock.get_current_conditions.return_value = {"current": "nws_current_data"}
        mock.get_alerts.return_value = {"alerts": ["nws_alert"]}
        return mock

    @pytest.fixture
    def mock_weatherapi_wrapper(self):
        """Create a mock WeatherAPI wrapper."""
        mock = MagicMock()
        mock.get_forecast.return_value = {
            "forecast": "weatherapi_data",
            "alerts": ["weatherapi_alert"],
        }
        mock.get_hourly_forecast.return_value = ["weatherapi_hourly_data"]
        mock.get_current_conditions.return_value = {"current": "weatherapi_current_data"}
        return mock

    def test_automatic_source_us_location(self, mock_nws_client, mock_weatherapi_wrapper):
        """Test automatic source selection for US location."""
        # Create a weather service with automatic data source
        config = {"settings": {"data_source": DATA_SOURCE_AUTO}}
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=mock_weatherapi_wrapper,
            config=config,
        )

        # Mock the _is_location_in_us method to return True (US location)
        with patch.object(service, "_is_location_in_us", return_value=True):
            # Get forecast for a US location
            forecast = service.get_forecast(40.0, -75.0)
            assert forecast == {"forecast": "nws_data"}
            mock_nws_client.get_forecast.assert_called_once_with(40.0, -75.0, force_refresh=False)
            mock_weatherapi_wrapper.get_forecast.assert_not_called()

            # Get hourly forecast for a US location
            hourly = service.get_hourly_forecast(40.0, -75.0)
            assert hourly == {"hourly": "nws_hourly_data"}
            mock_nws_client.get_hourly_forecast.assert_called_once_with(
                40.0, -75.0, force_refresh=False
            )
            mock_weatherapi_wrapper.get_hourly_forecast.assert_not_called()

            # Get current conditions for a US location
            current = service.get_current_conditions(40.0, -75.0)
            assert current == {"current": "nws_current_data"}
            mock_nws_client.get_current_conditions.assert_called_once_with(
                40.0, -75.0, force_refresh=False
            )
            mock_weatherapi_wrapper.get_current_conditions.assert_not_called()

            # Get alerts for a US location
            alerts = service.get_alerts(40.0, -75.0)
            assert alerts == {"alerts": ["nws_alert"]}
            mock_nws_client.get_alerts.assert_called_once()
            mock_weatherapi_wrapper.get_forecast.assert_not_called()

    def test_automatic_source_non_us_location(self, mock_nws_client, mock_weatherapi_wrapper):
        """Test automatic source selection for non-US location."""
        # Create a weather service with automatic data source
        config = {"settings": {"data_source": DATA_SOURCE_AUTO}}
        service = WeatherService(
            nws_client=mock_nws_client,
            weatherapi_wrapper=mock_weatherapi_wrapper,
            config=config,
        )

        # Mock the _is_location_in_us method to return False (non-US location)
        with patch.object(service, "_is_location_in_us", return_value=False):
            # Get forecast for a non-US location
            forecast = service.get_forecast(51.5, -0.1)  # London
            assert forecast == {
                "forecast": "weatherapi_data",
                "alerts": ["weatherapi_alert"],
            }
            mock_nws_client.get_forecast.assert_not_called()
            mock_weatherapi_wrapper.get_forecast.assert_called_once()

            # Reset mock for next test
            mock_weatherapi_wrapper.reset_mock()

            # Get hourly forecast for a non-US location
            hourly = service.get_hourly_forecast(51.5, -0.1)
            assert hourly == {"hourly": ["weatherapi_hourly_data"]}
            mock_nws_client.get_hourly_forecast.assert_not_called()
            mock_weatherapi_wrapper.get_hourly_forecast.assert_called_once()

            # Reset mock for next test
            mock_weatherapi_wrapper.reset_mock()

            # Get current conditions for a non-US location
            current = service.get_current_conditions(51.5, -0.1)
            assert current == {"current": "weatherapi_current_data"}
            mock_nws_client.get_current_conditions.assert_not_called()
            mock_weatherapi_wrapper.get_current_conditions.assert_called_once()

            # Reset mock for next test
            mock_weatherapi_wrapper.reset_mock()

            # Get alerts for a non-US location
            alerts = service.get_alerts(51.5, -0.1)
            assert "alerts" in alerts
            assert alerts["alerts"] == ["weatherapi_alert"]
            mock_nws_client.get_alerts.assert_not_called()
            mock_weatherapi_wrapper.get_forecast.assert_called_once()

    def test_automatic_source_non_us_location_no_weatherapi(self, mock_nws_client):
        """Test automatic source selection for non-US location without WeatherAPI wrapper."""
        # Create a weather service with automatic data source but no WeatherAPI wrapper
        config = {"settings": {"data_source": DATA_SOURCE_AUTO}}
        service = WeatherService(nws_client=mock_nws_client, config=config)

        # Mock the _is_location_in_us method to return False (non-US location)
        with patch.object(service, "_is_location_in_us", return_value=False):
            # Attempt to get forecast for a non-US location should raise ConfigurationError
            with pytest.raises(ConfigurationError) as excinfo:
                service.get_forecast(51.5, -0.1)  # London
            # Check that the error message mentions WeatherAPI.com and non-US locations in Automatic mode
            assert "WeatherAPI.com" in str(
                excinfo.value
            ) and "non-US locations in Automatic mode" in str(excinfo.value)

    def test_is_location_in_us_method(self):
        """Test the _is_location_in_us method directly."""
        # Create a weather service
        service = WeatherService(nws_client=MagicMock(), config={})

        # Mock the GeocodingService class
        with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
            # Set up the mock geocoding service
            mock_geocoding = MagicMock()
            mock_geocoding_class.return_value = mock_geocoding

            # Test with US coordinates (New York)
            mock_geocoding.validate_coordinates.return_value = True
            result = service._is_location_in_us(40.7128, -74.0060)
            assert result is True
            mock_geocoding.validate_coordinates.assert_called_with(40.7128, -74.0060, us_only=True)

            # Reset the mock
            mock_geocoding.reset_mock()

            # Test with non-US coordinates (London)
            mock_geocoding.validate_coordinates.return_value = False
            result = service._is_location_in_us(51.5074, -0.1278)
            assert result is False
            mock_geocoding.validate_coordinates.assert_called_with(51.5074, -0.1278, us_only=True)

            # Verify the GeocodingService was created with the correct parameters
            mock_geocoding_class.assert_called_with(
                user_agent="AccessiWeather-WeatherService", data_source="auto"
            )

    def test_is_location_in_us_integration(self):
        """Test the _is_location_in_us method with real geocoding service."""
        # Create a weather service
        service = WeatherService(nws_client=MagicMock(), config={})

        # Mock the validate_coordinates method to simulate real behavior
        with patch(
            "accessiweather.geocoding.GeocodingService.validate_coordinates"
        ) as mock_validate:
            # Set up the mock to return True for US coordinates and False for non-US
            def validate_side_effect(lat, lon, us_only=None):
                # Ignore us_only parameter for this test as we're simulating fixed responses
                # New York coordinates should return True
                if lat == 40.7128 and lon == -74.0060:
                    return True
                # London coordinates should return False
                elif lat == 51.5074 and lon == -0.1278:
                    return False
                # Default to False for unknown coordinates
                return False

            mock_validate.side_effect = validate_side_effect

            # Test with US coordinates (New York)
            result = service._is_location_in_us(40.7128, -74.0060)
            assert result is True

            # Test with non-US coordinates (London)
            result = service._is_location_in_us(51.5074, -0.1278)
            assert result is False
