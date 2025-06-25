"""Tests for the simplified AccessiWeather application.

This module provides comprehensive tests for the simplified AccessiWeather
implementation using BeeWare/Toga, following the BeeWare testing patterns.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import the simplified app components
from accessiweather.simple.app import AccessiWeatherApp
from accessiweather.simple.config import ConfigManager
from accessiweather.simple.display import WxStyleWeatherFormatter
from accessiweather.simple.location_manager import LocationManager
from accessiweather.simple.models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    Location,
    WeatherAlerts,
    WeatherData,
)
from accessiweather.simple.utils import (
    TemperatureUnit,
    format_temperature,
    format_wind_speed,
    convert_wind_direction_to_cardinal,
)
from accessiweather.simple.weather_client import WeatherClient


class TestSimpleAppComponents:
    """Test the core components of the simplified app."""

    def test_location_model(self):
        """Test the Location model."""
        location = Location("Philadelphia, PA", 39.9526, -75.1652)
        
        assert location.name == "Philadelphia, PA"
        assert location.latitude == 39.9526
        assert location.longitude == -75.1652
        assert str(location) == "Philadelphia, PA"

    def test_current_conditions_model(self):
        """Test the CurrentConditions model."""
        conditions = CurrentConditions(
            temperature_f=75.0,
            temperature_c=23.9,
            condition="Partly Cloudy",
            humidity=65,
            wind_speed_mph=10.0,
            wind_direction=270
        )
        
        assert conditions.has_data() is True
        assert conditions.temperature_f == 75.0
        assert conditions.condition == "Partly Cloudy"
        
        # Test empty conditions
        empty_conditions = CurrentConditions()
        assert empty_conditions.has_data() is False

    def test_forecast_model(self):
        """Test the Forecast model."""
        period = ForecastPeriod(
            name="Today",
            temperature=80.0,
            temperature_unit="F",
            short_forecast="Sunny"
        )
        
        forecast = Forecast(periods=[period])
        
        assert forecast.has_data() is True
        assert len(forecast.periods) == 1
        assert forecast.periods[0].name == "Today"
        
        # Test empty forecast
        empty_forecast = Forecast(periods=[])
        assert empty_forecast.has_data() is False

    def test_app_settings_model(self):
        """Test the AppSettings model."""
        settings = AppSettings()
        
        # Test defaults
        assert settings.temperature_unit == "both"
        assert settings.update_interval_minutes == 10
        assert settings.show_detailed_forecast is True
        
        # Test serialization
        settings_dict = settings.to_dict()
        assert "temperature_unit" in settings_dict
        assert settings_dict["temperature_unit"] == "both"
        
        # Test deserialization
        new_settings = AppSettings.from_dict(settings_dict)
        assert new_settings.temperature_unit == settings.temperature_unit


class TestUtilityFunctions:
    """Test the utility functions."""

    def test_temperature_formatting(self):
        """Test temperature formatting utilities."""
        # Test Fahrenheit only
        temp_f = format_temperature(75.0, TemperatureUnit.FAHRENHEIT)
        assert temp_f == "75°F"
        
        # Test Celsius only
        temp_c = format_temperature(75.0, TemperatureUnit.CELSIUS, temperature_c=23.9)
        assert temp_c == "24°C"
        
        # Test both units
        temp_both = format_temperature(75.0, TemperatureUnit.BOTH, temperature_c=23.9)
        assert temp_both == "75°F (24°C)"

    def test_wind_direction_conversion(self):
        """Test wind direction conversion."""
        # Test cardinal directions
        assert convert_wind_direction_to_cardinal(0) == "N"
        assert convert_wind_direction_to_cardinal(90) == "E"
        assert convert_wind_direction_to_cardinal(180) == "S"
        assert convert_wind_direction_to_cardinal(270) == "W"
        assert convert_wind_direction_to_cardinal(330) == "NNW"
        
        # Test None input
        assert convert_wind_direction_to_cardinal(None) == "N/A"

    def test_wind_speed_formatting(self):
        """Test wind speed formatting."""
        # Test mph only
        wind_mph = format_wind_speed(15.0, TemperatureUnit.FAHRENHEIT)
        assert wind_mph == "15.0 mph"
        
        # Test km/h only
        wind_kph = format_wind_speed(15.0, TemperatureUnit.CELSIUS, wind_speed_kph=24.1)
        assert wind_kph == "24.1 km/h"
        
        # Test both units
        wind_both = format_wind_speed(15.0, TemperatureUnit.BOTH, wind_speed_kph=24.1)
        assert wind_both == "15.0 mph (24.1 km/h)"


class TestWeatherFormatter:
    """Test the WX-style weather formatter."""

    def test_formatter_initialization(self):
        """Test formatter initialization."""
        settings = AppSettings()
        formatter = WxStyleWeatherFormatter(settings)
        
        assert formatter.settings == settings

    def test_current_conditions_formatting(self):
        """Test current conditions formatting."""
        settings = AppSettings()
        formatter = WxStyleWeatherFormatter(settings)
        
        location = Location("Test City", 40.0, -75.0)
        conditions = CurrentConditions(
            temperature_f=75.0,
            condition="Partly Cloudy",
            humidity=65,
            wind_speed_mph=10.0,
            wind_direction=270
        )
        
        formatted = formatter.format_current_conditions(conditions, location)
        
        assert "Test City" in formatted
        assert "Partly Cloudy" in formatted
        assert "75°F" in formatted
        assert "65%" in formatted
        assert "W at" in formatted  # Wind direction should be converted

    def test_forecast_formatting(self):
        """Test forecast formatting."""
        settings = AppSettings()
        formatter = WxStyleWeatherFormatter(settings)
        
        location = Location("Test City", 40.0, -75.0)
        period = ForecastPeriod(
            name="Today",
            temperature=80.0,
            temperature_unit="F",
            detailed_forecast="Sunny skies with light winds."
        )
        forecast = Forecast(periods=[period])
        
        formatted = formatter.format_forecast(forecast, location)
        
        assert "Test City" in formatted
        assert "Today" in formatted
        assert "80°F" in formatted
        assert "Sunny skies" in formatted

    def test_empty_data_formatting(self):
        """Test formatting with empty data."""
        settings = AppSettings()
        formatter = WxStyleWeatherFormatter(settings)
        
        location = Location("Test City", 40.0, -75.0)
        
        # Test empty current conditions
        formatted_current = formatter.format_current_conditions(None, location)
        assert "No current weather data available" in formatted_current
        
        # Test empty forecast
        formatted_forecast = formatter.format_forecast(None, location)
        assert "No forecast data available" in formatted_forecast
        
        # Test empty alerts
        formatted_alerts = formatter.format_alerts(None, location)
        assert "No active weather alerts" in formatted_alerts


class TestWeatherClient:
    """Test the weather client."""

    def test_weather_client_initialization(self):
        """Test weather client initialization."""
        client = WeatherClient(user_agent="Test/1.0")
        
        assert client.user_agent == "Test/1.0"
        assert client.nws_base_url == "https://api.weather.gov"
        assert client.openmeteo_base_url == "https://api.open-meteo.com/v1"
        assert client.timeout == 10.0

    @pytest.mark.asyncio
    async def test_weather_data_structure(self):
        """Test that weather data is structured correctly."""
        client = WeatherClient()
        location = Location("Test City", 40.0, -75.0)
        
        # Mock the HTTP responses
        with patch('httpx.AsyncClient') as mock_client:
            # Mock successful responses
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "properties": {
                    "temperature": {"value": 20.0},  # Celsius
                    "textDescription": "Clear",
                    "relativeHumidity": {"value": 60},
                    "windSpeed": {"value": 5.0},  # m/s
                    "windDirection": {"value": 270}
                }
            }
            
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.return_value = mock_response
            
            # This would normally make real API calls, but we're mocking them
            # Just test that the structure is correct
            weather_data = WeatherData(location=location)
            
            assert weather_data.location == location
            assert weather_data.current is None  # Initially None
            assert weather_data.forecast is None  # Initially None
            assert weather_data.alerts is None  # Initially None


class TestLocationManager:
    """Test the location manager."""

    def test_location_manager_initialization(self):
        """Test location manager initialization."""
        manager = LocationManager()
        
        assert manager.timeout == 10.0
        assert manager.geocoding_base_url == "https://nominatim.openstreetmap.org"

    def test_coordinate_validation(self):
        """Test coordinate validation."""
        manager = LocationManager()
        
        # Valid coordinates
        assert manager.validate_coordinates(40.0, -75.0) is True
        assert manager.validate_coordinates(-90.0, 180.0) is True
        
        # Invalid coordinates
        assert manager.validate_coordinates(91.0, 0.0) is False
        assert manager.validate_coordinates(0.0, 181.0) is False

    def test_distance_calculation(self):
        """Test distance calculation between locations."""
        manager = LocationManager()
        
        loc1 = Location("Philadelphia", 39.9526, -75.1652)
        loc2 = Location("New York", 40.7128, -74.0060)
        
        distance = manager.calculate_distance(loc1, loc2)
        
        # Distance should be approximately 80-100 miles
        assert 80 <= distance <= 100

    def test_common_locations(self):
        """Test getting common locations."""
        manager = LocationManager()
        
        common_locations = manager.get_common_locations()
        
        assert len(common_locations) > 0
        assert any(loc.name == "New York, NY" for loc in common_locations)
        assert any(loc.name == "Los Angeles, CA" for loc in common_locations)


# Integration test that would run with briefcase dev --test
def test_app_can_be_imported():
    """Test that the simplified app can be imported successfully."""
    try:
        from accessiweather.simple import main
        assert callable(main)
    except ImportError as e:
        pytest.fail(f"Failed to import simplified app: {e}")


def test_app_components_integration():
    """Test that all app components work together."""
    # Test that we can create all the main components
    settings = AppSettings()
    location = Location("Test City", 40.0, -75.0)
    
    # Test formatter with settings
    formatter = WxStyleWeatherFormatter(settings)
    assert formatter is not None
    
    # Test weather client
    client = WeatherClient()
    assert client is not None
    
    # Test location manager
    location_manager = LocationManager()
    assert location_manager is not None
    
    # Test that they can work with each other
    formatted_text = formatter.format_current_conditions(None, location)
    assert "Test City" in formatted_text


# This test would be run by briefcase dev --test
def test_simplified_app_main_function():
    """Test the main function of the simplified app."""
    from accessiweather.simple import main
    
    # Test that main returns an app instance
    app = main()
    assert app is not None
    assert isinstance(app, AccessiWeatherApp)
    assert app.formal_name == "AccessiWeather"
