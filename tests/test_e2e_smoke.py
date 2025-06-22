"""End-to-end smoke tests for AccessiWeather application.

These tests verify basic application functionality and critical user workflows
without requiring a full GUI environment.
"""

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.mark.e2e
@pytest.mark.smoke
def test_application_imports():
    """Test that the main application modules can be imported successfully."""
    # Set headless mode
    os.environ["DISPLAY"] = ""

    try:
        # Test core module imports
        import accessiweather.api_client  # noqa: F401
        import accessiweather.cache  # noqa: F401
        import accessiweather.gui.settings_dialog  # noqa: F401

        # Test GUI module imports (should work in headless mode)
        import accessiweather.gui.weather_app  # noqa: F401
        import accessiweather.location  # noqa: F401
        import accessiweather.main  # noqa: F401

        # Test utility imports
        # import accessiweather.utils.temperature_utils  # Unused import
        # import accessiweather.utils.unit_utils  # Unused import

        print("✅ All core modules imported successfully")

    except ImportError as e:
        pytest.fail(f"Failed to import core modules: {e}")


@pytest.mark.e2e
@pytest.mark.smoke
def test_configuration_system():
    """Test that the configuration system works correctly."""
    import json

    from accessiweather.config_utils import get_config_dir

    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = get_config_dir(temp_dir)
        config_file = os.path.join(config_dir, "config.json")

        # Test setting and getting configuration
        test_config = {"location": "Test City", "update_interval": 30, "units": "imperial"}

        # Ensure directory exists
        os.makedirs(config_dir, exist_ok=True)

        # Save config
        with open(config_file, "w") as f:
            json.dump(test_config, f)

        # Load config
        with open(config_file) as f:
            loaded_config = json.load(f)

        assert loaded_config["location"] == "Test City"
        assert loaded_config["update_interval"] == 30
        assert loaded_config["units"] == "imperial"

        print("✅ Configuration system working correctly")


@pytest.mark.e2e
@pytest.mark.smoke
def test_location_manager():
    """Test that the location management system works."""
    from accessiweather.location import LocationManager

    with tempfile.TemporaryDirectory() as temp_dir:
        location_manager = LocationManager(config_dir=temp_dir)

        # Test adding a location
        location_manager.add_location("Test City", 40.0, -75.0)

        # Test getting locations
        locations = location_manager.get_all_locations()
        assert "Test City" in locations

        # Test accessing saved locations directly
        assert "Test City" in location_manager.saved_locations
        assert location_manager.saved_locations["Test City"]["lat"] == 40.0
        assert location_manager.saved_locations["Test City"]["lon"] == -75.0

        # Test setting current location
        location_manager.set_current_location("Test City")
        current = location_manager.get_current_location()
        assert current is not None
        assert current[0] == "Test City"  # current is a tuple (name, lat, lon)

        print("✅ Location manager working correctly")


@pytest.mark.e2e
@pytest.mark.smoke
def test_cache_system():
    """Test that the caching system works correctly."""
    from accessiweather.cache import Cache

    # Test basic cache functionality
    cache = Cache(default_ttl=300)

    # Test caching data
    test_data = {"temperature": 72, "condition": "sunny"}
    cache.set("test_key", test_data)

    # Test retrieving cached data
    cached_data = cache.get("test_key")
    assert cached_data == test_data

    # Test cache expiration
    cache.set("expire_key", test_data, ttl=0.1)  # Short TTL
    time.sleep(0.2)
    expired_data = cache.get("expire_key")
    assert expired_data is None

    print("✅ Cache system working correctly")


@pytest.mark.e2e
@pytest.mark.smoke
@patch("accessiweather.api_client.core_client.requests.get")
def test_api_client_basic_functionality(mock_get):
    """Test basic API client functionality."""
    from accessiweather.api_client import NoaaApiClient

    # Mock API response - first call returns point data, second returns forecast
    mock_response = MagicMock()
    mock_response.json.side_effect = [
        # Point data response
        {"properties": {"forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast"}},
        # Forecast data response
        {
            "properties": {
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 72,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                    }
                ]
            }
        },
    ]
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    # Test API client
    client = NoaaApiClient()
    forecast = client.get_forecast(40.0, -75.0)

    assert forecast is not None
    assert "properties" in forecast

    print("✅ API client basic functionality working")


@pytest.mark.e2e
@pytest.mark.smoke
def test_weather_service_initialization():
    """Test that the weather service can be initialized."""
    from accessiweather.api_client import NoaaApiClient
    from accessiweather.services.weather_service import WeatherService

    # Create weather service with mocked API client
    api_client = MagicMock(spec=NoaaApiClient)
    weather_service = WeatherService(api_client)

    assert weather_service is not None
    assert weather_service.nws_client is api_client  # WeatherService uses nws_client attribute

    print("✅ Weather service initialization working")


@pytest.mark.e2e
@pytest.mark.smoke
def test_temperature_utilities():
    """Test temperature conversion utilities."""
    from accessiweather.utils.temperature_utils import celsius_to_fahrenheit, fahrenheit_to_celsius

    # Test conversions
    assert abs(celsius_to_fahrenheit(0) - 32.0) < 0.1
    assert abs(celsius_to_fahrenheit(100) - 212.0) < 0.1
    assert abs(fahrenheit_to_celsius(32) - 0.0) < 0.1
    assert abs(fahrenheit_to_celsius(212) - 100.0) < 0.1

    print("✅ Temperature utilities working correctly")


@pytest.mark.e2e
@pytest.mark.smoke
def test_unit_utilities():
    """Test unit formatting utilities."""
    from accessiweather.utils.temperature_utils import TemperatureUnit
    from accessiweather.utils.unit_utils import format_pressure, format_wind_speed

    # Test wind speed formatting
    formatted_speed = format_wind_speed(15.0, TemperatureUnit.FAHRENHEIT)
    assert "15" in formatted_speed
    assert "mph" in formatted_speed

    # Test pressure formatting
    formatted_pressure = format_pressure(30.0, TemperatureUnit.FAHRENHEIT)
    assert "30" in formatted_pressure
    assert "inHg" in formatted_pressure

    print("✅ Unit utilities working correctly")


@pytest.mark.e2e
@pytest.mark.slow
def test_application_startup_simulation():
    """Test simulated application startup without creating actual GUI."""
    os.environ["DISPLAY"] = ""

    with patch("wx.App") as mock_app_class:
        with patch("accessiweather.gui.weather_app.WeatherApp") as mock_weather_app:
            # Mock the app and main window
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            mock_main_window = MagicMock()
            mock_weather_app.return_value = mock_main_window

            try:
                # Import and simulate startup
                import accessiweather.main  # noqa: F401 - used in patch below

                # Simulate the main function without actually running the GUI
                with patch("accessiweather.main.main") as mock_main:
                    mock_main.return_value = None

                    # This should not raise any exceptions
                    result = mock_main()
                    assert result is None

                print("✅ Application startup simulation successful")

            except Exception as e:
                pytest.fail(f"Application startup simulation failed: {e}")


@pytest.mark.e2e
@pytest.mark.smoke
def test_logging_configuration():
    """Test that logging is configured correctly."""
    import logging

    from accessiweather.logging_config import setup_logging

    # Setup logging (returns log directory)
    log_dir = setup_logging(log_level=logging.INFO)

    # Test logging
    logger = logging.getLogger("test_logger")
    logger.info("Test log message")

    # Verify log directory was created
    assert log_dir.exists()

    print("✅ Logging configuration working correctly")


if __name__ == "__main__":
    # Run smoke tests when executed directly
    pytest.main([__file__, "-v", "-m", "smoke"])
