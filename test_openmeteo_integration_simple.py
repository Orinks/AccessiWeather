#!/usr/bin/env python3
"""Simple test for Open-Meteo integration without pytest dependencies."""

import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_api_selection():
    """Test automatic API selection logic."""
    print("Testing API selection logic...")

    # Import directly from the simple weather client
    import importlib.util

    # Load weather_client module
    weather_client_path = os.path.join("src", "accessiweather", "simple", "weather_client.py")
    spec = importlib.util.spec_from_file_location("weather_client", weather_client_path)
    weather_client_module = importlib.util.module_from_spec(spec)

    # Load models module
    models_path = os.path.join("src", "accessiweather", "simple", "models.py")
    spec = importlib.util.spec_from_file_location("models", models_path)
    models_module = importlib.util.module_from_spec(spec)

    # Execute the modules
    spec.loader.exec_module(models_module)

    # Inject models into weather_client namespace
    sys.modules["models"] = models_module
    weather_client_module.models = models_module
    weather_client_module.CurrentConditions = models_module.CurrentConditions
    weather_client_module.Forecast = models_module.Forecast
    weather_client_module.ForecastPeriod = models_module.ForecastPeriod
    weather_client_module.HourlyForecast = models_module.HourlyForecast
    weather_client_module.HourlyForecastPeriod = models_module.HourlyForecastPeriod
    weather_client_module.Location = models_module.Location
    weather_client_module.WeatherAlert = models_module.WeatherAlert
    weather_client_module.WeatherAlerts = models_module.WeatherAlerts
    weather_client_module.WeatherData = models_module.WeatherData

    # Now execute weather_client
    spec = importlib.util.spec_from_file_location("weather_client", weather_client_path)
    weather_client_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(weather_client_module)

    WeatherClient = weather_client_module.WeatherClient
    Location = models_module.Location

    # Test basic functionality
    client = WeatherClient(data_source="auto")
    us_location = Location("Philadelphia, PA", 39.9526, -75.1652)
    tokyo_location = Location("Tokyo, Japan", 35.6762, 139.6503)
    london_location = Location("London, UK", 51.5074, -0.1278)
    sydney_location = Location("Sydney, Australia", -33.8688, 151.2093)

    # Test automatic API selection
    print("✅ Auto mode - US locations should use NWS:")
    assert not client._should_use_openmeteo(us_location), "Philadelphia should use NWS"
    print(f"  Philadelphia, PA: NWS ✓")

    print("✅ Auto mode - International locations should use Open-Meteo:")
    assert client._should_use_openmeteo(tokyo_location), "Tokyo should use Open-Meteo"
    assert client._should_use_openmeteo(london_location), "London should use Open-Meteo"
    assert client._should_use_openmeteo(sydney_location), "Sydney should use Open-Meteo"
    print(f"  Tokyo, Japan: Open-Meteo ✓")
    print(f"  London, UK: Open-Meteo ✓")
    print(f"  Sydney, Australia: Open-Meteo ✓")

    # Test location detection
    print("✅ Location detection:")
    assert client._is_us_location(us_location), "Philadelphia should be detected as US"
    assert not client._is_us_location(tokyo_location), "Tokyo should not be detected as US"
    assert not client._is_us_location(london_location), "London should not be detected as US"
    assert not client._is_us_location(sydney_location), "Sydney should not be detected as US"
    print(f"  US detection working correctly ✓")

    # Test forced modes
    print("✅ Forced API modes:")
    client_openmeteo = WeatherClient(data_source="openmeteo")
    client_nws = WeatherClient(data_source="nws")

    # Force Open-Meteo mode
    assert client_openmeteo._should_use_openmeteo(us_location), (
        "Force Open-Meteo should work for US"
    )
    assert client_openmeteo._should_use_openmeteo(tokyo_location), (
        "Force Open-Meteo should work for international"
    )
    print(f"  Force Open-Meteo mode working ✓")

    # Force NWS mode
    assert not client_nws._should_use_openmeteo(us_location), "Force NWS should work for US"
    assert not client_nws._should_use_openmeteo(tokyo_location), (
        "Force NWS should work for international"
    )
    print(f"  Force NWS mode working ✓")

    print("\n🎉 All API selection tests passed!")
    return True


def test_utility_methods():
    """Test utility methods."""
    print("\nTesting utility methods...")

    # Import weather client
    import importlib.util

    weather_client_path = os.path.join("src", "accessiweather", "simple", "weather_client.py")
    spec = importlib.util.spec_from_file_location("weather_client", weather_client_path)
    weather_client_module = importlib.util.module_from_spec(spec)

    # Load models first
    models_path = os.path.join("src", "accessiweather", "simple", "models.py")
    spec = importlib.util.spec_from_file_location("models", models_path)
    models_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(models_module)

    # Inject models into weather_client namespace
    sys.modules["models"] = models_module
    weather_client_module.models = models_module
    for attr in dir(models_module):
        if not attr.startswith("_"):
            setattr(weather_client_module, attr, getattr(models_module, attr))

    # Execute weather_client
    spec = importlib.util.spec_from_file_location("weather_client", weather_client_path)
    weather_client_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(weather_client_module)

    WeatherClient = weather_client_module.WeatherClient
    client = WeatherClient()

    # Test temperature conversion
    assert abs(client._convert_f_to_c(32.0) - 0.0) < 0.01, "32F should be 0C"
    assert abs(client._convert_f_to_c(212.0) - 100.0) < 0.01, "212F should be 100C"
    print("✅ Temperature conversion working")

    # Test wind direction
    assert client._degrees_to_cardinal(0) == "N", "0 degrees should be N"
    assert client._degrees_to_cardinal(90) == "E", "90 degrees should be E"
    assert client._degrees_to_cardinal(180) == "S", "180 degrees should be S"
    assert client._degrees_to_cardinal(270) == "W", "270 degrees should be W"
    print("✅ Wind direction conversion working")

    # Test weather codes
    assert client._weather_code_to_description(0) == "Clear sky", "Code 0 should be Clear sky"
    assert client._weather_code_to_description(1) == "Mainly clear", "Code 1 should be Mainly clear"
    assert client._weather_code_to_description(61) == "Slight rain", "Code 61 should be Slight rain"
    print("✅ Weather code conversion working")

    print("🎉 All utility method tests passed!")
    return True


def main():
    """Run all tests."""
    print("🧪 Testing Open-Meteo Integration in Simple Toga App")
    print("=" * 60)

    try:
        test_api_selection()
        test_utility_methods()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! Open-Meteo integration is working correctly!")
        print("✅ Automatic API selection based on location")
        print("✅ Forced API mode selection")
        print("✅ US location detection")
        print("✅ Utility method conversions")
        print("✅ Ready for use in the simple Toga app!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
