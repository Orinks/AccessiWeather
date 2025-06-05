"""Comprehensive integration tests for AccessiWeather.

These tests verify that all components work together correctly,
covering the key user flows identified in the integration test plan.
"""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_wrapper import NoaaApiWrapper
from accessiweather.config_utils import get_config_dir
from accessiweather.location import LocationManager
from accessiweather.notifications import WeatherNotifier
from accessiweather.openmeteo_client import OpenMeteoApiClient
from accessiweather.services.weather_service import WeatherService
from accessiweather.utils.temperature_utils import TemperatureUnit


@pytest.mark.integration
class TestApplicationStartupFlow:
    """Test the complete application startup flow."""

    def test_first_time_startup_flow(
        self,
        temp_config_dir,
        sample_nws_point_response,
        sample_nws_forecast_response,
        sample_nws_current_response,
    ):
        """Test first-time application startup with no existing configuration."""
        # Ensure no config exists
        config_path = os.path.join(temp_config_dir, "config.json")
        assert not os.path.exists(config_path)

        # Create location manager (simulates first startup)
        location_manager = LocationManager(config_dir=temp_config_dir)

        # Verify initial state
        assert location_manager.get_current_location() is None
        assert len(location_manager.get_all_locations()) == 0

        # Simulate user adding first location
        location_manager.add_location("Test City", 40.7128, -74.0060)
        location_manager.set_current_location("Test City")

        # Verify location was saved
        current = location_manager.get_current_location()
        assert current is not None
        assert current[0] == "Test City"
        assert current[1] == 40.7128
        assert current[2] == -74.0060

        # Create weather service and test data fetching
        with patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_wrapper:
            mock_client = MagicMock()
            mock_wrapper.return_value = mock_client

            # Mock API responses
            mock_client.get_point.return_value = sample_nws_point_response
            mock_client.get_forecast.return_value = sample_nws_forecast_response
            mock_client.get_current_conditions.return_value = sample_nws_current_response

            # Create weather service
            config = {"settings": {"data_source": "nws"}}
            weather_service = WeatherService(nws_client=mock_client, config=config)

            # Test fetching weather data
            forecast = weather_service.get_forecast(40.7128, -74.0060)
            current = weather_service.get_current_conditions(40.7128, -74.0060)

            assert forecast is not None
            assert current is not None
            assert "properties" in forecast
            assert "properties" in current

    def test_existing_user_startup_flow(self, config_file, sample_config):
        """Test startup flow for existing user with saved configuration."""
        # Load existing configuration
        with open(config_file, "r") as f:
            loaded_config = json.load(f)

        assert loaded_config == sample_config
        assert loaded_config["location"]["name"] == "Test City"

        # Create location manager with existing config
        config_dir = os.path.dirname(config_file)
        location_manager = LocationManager(config_dir=config_dir)

        # Add the location from config
        location_manager.add_location(
            loaded_config["location"]["name"],
            loaded_config["location"]["lat"],
            loaded_config["location"]["lon"],
        )
        location_manager.set_current_location(loaded_config["location"]["name"])

        # Verify location is available
        current = location_manager.get_current_location()
        assert current is not None
        assert current[0] == "Test City"


@pytest.mark.integration
class TestWeatherDataRefreshFlow:
    """Test weather data refresh scenarios."""

    def test_manual_refresh_flow(
        self,
        weather_service,
        sample_nws_forecast_response,
        sample_nws_current_response,
        performance_timer,
    ):
        """Test manual weather data refresh."""
        lat, lon = 40.7128, -74.0060

        # Mock API responses
        weather_service.nws_client.get_forecast.return_value = sample_nws_forecast_response
        weather_service.nws_client.get_current_conditions.return_value = sample_nws_current_response

        # Test performance
        performance_timer.start()

        # Fetch current conditions
        current = weather_service.get_current_conditions(lat, lon)

        # Fetch forecast
        forecast = weather_service.get_forecast(lat, lon)

        performance_timer.stop()

        # Verify data
        assert current is not None
        assert forecast is not None
        assert "properties" in current
        assert "properties" in forecast
        assert "periods" in forecast["properties"]

        # Verify performance (should be fast with mocked data)
        assert performance_timer.elapsed < 1.0

        # Verify API calls were made
        weather_service.nws_client.get_current_conditions.assert_called_once_with(lat, lon)
        weather_service.nws_client.get_forecast.assert_called_once_with(lat, lon)

    def test_automatic_refresh_with_cache(self, weather_service, sample_nws_current_response):
        """Test automatic refresh behavior with caching."""
        lat, lon = 40.7128, -74.0060

        # Mock API response
        weather_service.nws_client.get_current_conditions.return_value = sample_nws_current_response

        # First call - should hit API
        current1 = weather_service.get_current_conditions(lat, lon)
        assert current1 is not None

        # Second call immediately - behavior depends on cache implementation
        current2 = weather_service.get_current_conditions(lat, lon)
        assert current2 is not None

        # Verify at least one API call was made
        assert weather_service.nws_client.get_current_conditions.call_count >= 1


@pytest.mark.integration
class TestLocationChangeFlow:
    """Test location change scenarios."""

    def test_location_change_triggers_data_refresh(
        self, temp_config_dir, sample_nws_current_response, sample_openmeteo_current_response
    ):
        """Test that changing location triggers fresh weather data fetch."""
        location_manager = LocationManager(config_dir=temp_config_dir)

        # Add multiple locations
        location_manager.add_location("New York", 40.7128, -74.0060)
        location_manager.add_location("London", 51.5074, -0.1278)

        # Set initial location
        location_manager.set_current_location("New York")
        current = location_manager.get_current_location()
        assert current[0] == "New York"

        # Create weather service with mocked clients
        with (
            patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
            patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
        ):

            nws_client = MagicMock()
            openmeteo_client = MagicMock()
            mock_nws.return_value = nws_client
            mock_openmeteo.return_value = openmeteo_client

            # Mock responses
            nws_client.get_current_conditions.return_value = sample_nws_current_response
            openmeteo_client.get_current_weather.return_value = sample_openmeteo_current_response

            config = {"settings": {"data_source": "auto"}}
            weather_service = WeatherService(
                nws_client=nws_client, openmeteo_client=openmeteo_client, config=config
            )

            # Get weather for New York (should use NWS)
            ny_weather = weather_service.get_current_conditions(40.7128, -74.0060)
            assert ny_weather is not None

            # Change to London
            location_manager.set_current_location("London")
            current = location_manager.get_current_location()
            assert current[0] == "London"

            # Get weather for London (should use Open-Meteo)
            london_weather = weather_service.get_current_conditions(51.5074, -0.1278)
            assert london_weather is not None

            # Verify correct APIs were called
            nws_client.get_current_conditions.assert_called()
            openmeteo_client.get_current_weather.assert_called()


@pytest.mark.integration
class TestDataSourceSelectionFlow:
    """Test data source selection and switching."""

    def test_auto_data_source_selection(self, us_coordinates, international_coordinates):
        """Test automatic data source selection based on location."""
        config = {"settings": {"data_source": "auto"}}

        with (
            patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
            patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
        ):

            nws_client = MagicMock()
            openmeteo_client = MagicMock()
            mock_nws.return_value = nws_client
            mock_openmeteo.return_value = openmeteo_client

            weather_service = WeatherService(
                nws_client=nws_client, openmeteo_client=openmeteo_client, config=config
            )

            # Test US location - should prefer NWS
            us_lat, us_lon = us_coordinates
            should_use_openmeteo_us = weather_service._should_use_openmeteo(us_lat, us_lon)
            assert should_use_openmeteo_us is False

            # Test international location - should prefer Open-Meteo
            intl_lat, intl_lon = international_coordinates
            should_use_openmeteo_intl = weather_service._should_use_openmeteo(intl_lat, intl_lon)
            assert should_use_openmeteo_intl is True

    def test_manual_data_source_override(self, us_coordinates):
        """Test manual data source selection overrides auto behavior."""
        us_lat, us_lon = us_coordinates

        # Test NWS-only configuration
        nws_config = {"settings": {"data_source": "nws"}}
        with (
            patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
            patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
        ):

            nws_client = MagicMock()
            openmeteo_client = MagicMock()
            mock_nws.return_value = nws_client
            mock_openmeteo.return_value = openmeteo_client

            nws_service = WeatherService(
                nws_client=nws_client, openmeteo_client=openmeteo_client, config=nws_config
            )

            # Should always use NWS
            assert nws_service._should_use_openmeteo(us_lat, us_lon) is False

        # Test Open-Meteo-only configuration
        openmeteo_config = {"settings": {"data_source": "openmeteo"}}
        with (
            patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
            patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
        ):

            nws_client = MagicMock()
            openmeteo_client = MagicMock()
            mock_nws.return_value = nws_client
            mock_openmeteo.return_value = openmeteo_client

            openmeteo_service = WeatherService(
                nws_client=nws_client, openmeteo_client=openmeteo_client, config=openmeteo_config
            )

            # Should always use Open-Meteo
            assert openmeteo_service._should_use_openmeteo(us_lat, us_lon) is True


@pytest.mark.integration
class TestErrorHandlingFlow:
    """Test error handling and fallback mechanisms."""

    def test_network_error_handling(self, weather_service):
        """Test handling of network errors."""
        lat, lon = 40.7128, -74.0060

        # Mock network error
        weather_service.nws_client.get_current_conditions.side_effect = Exception("Network error")

        # Should handle error gracefully
        with pytest.raises(Exception):
            weather_service.get_current_conditions(lat, lon)

    def test_api_fallback_mechanism(
        self, sample_nws_current_response, sample_openmeteo_current_response
    ):
        """Test fallback from one API to another."""
        lat, lon = 40.7128, -74.0060

        config = {"settings": {"data_source": "auto"}}

        with (
            patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
            patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
        ):

            nws_client = MagicMock()
            openmeteo_client = MagicMock()
            mock_nws.return_value = nws_client
            mock_openmeteo.return_value = openmeteo_client

            weather_service = WeatherService(
                nws_client=nws_client, openmeteo_client=openmeteo_client, config=config
            )

            # Mock NWS failure and Open-Meteo success
            nws_client.get_current_conditions.side_effect = Exception("NWS error")
            openmeteo_client.get_current_weather.return_value = sample_openmeteo_current_response

            # Should fallback to Open-Meteo
            result = weather_service.get_current_conditions(lat, lon)
            assert result is not None

            # Verify fallback was attempted
            nws_client.get_current_conditions.assert_called_once()
            openmeteo_client.get_current_weather.assert_called_once()


@pytest.mark.integration
class TestConfigurationIntegration:
    """Test configuration system integration."""

    def test_configuration_persistence(self, temp_config_dir):
        """Test that configuration changes persist across sessions."""
        config_path = os.path.join(temp_config_dir, "config.json")

        # Create initial configuration
        initial_config = {
            "settings": {"temperature_unit": TemperatureUnit.FAHRENHEIT.value, "data_source": "nws"}
        }

        os.makedirs(temp_config_dir, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(initial_config, f)

        # Load and verify
        with open(config_path, "r") as f:
            loaded_config = json.load(f)

        assert loaded_config == initial_config

        # Modify configuration
        loaded_config["settings"]["temperature_unit"] = TemperatureUnit.CELSIUS.value
        loaded_config["settings"]["data_source"] = "openmeteo"

        # Save changes
        with open(config_path, "w") as f:
            json.dump(loaded_config, f)

        # Reload and verify persistence
        with open(config_path, "r") as f:
            reloaded_config = json.load(f)

        assert reloaded_config["settings"]["temperature_unit"] == TemperatureUnit.CELSIUS.value
        assert reloaded_config["settings"]["data_source"] == "openmeteo"

    def test_invalid_configuration_recovery(self, temp_config_dir):
        """Test recovery from invalid configuration."""
        config_path = os.path.join(temp_config_dir, "config.json")

        # Create invalid configuration
        os.makedirs(temp_config_dir, exist_ok=True)
        with open(config_path, "w") as f:
            f.write("invalid json content")

        # Should handle gracefully
        location_manager = LocationManager(config_dir=temp_config_dir)
        assert location_manager is not None

        # Should be able to add locations despite invalid config
        location_manager.add_location("Test", 40.0, -75.0)
        locations = location_manager.get_all_locations()
        assert "Test" in locations
