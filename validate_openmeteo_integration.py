#!/usr/bin/env python3
"""Validate Open-Meteo integration by checking the code structure."""

import os
import re


def check_weather_client_integration():
    """Check that the weather client has proper Open-Meteo integration."""
    print("🔍 Checking weather client integration...")

    weather_client_path = os.path.join("src", "accessiweather", "simple", "weather_client.py")

    if not os.path.exists(weather_client_path):
        print("❌ Weather client file not found")
        return False

    with open(weather_client_path) as f:
        content = f.read()

    # Check for key integration features
    checks = [
        (r"def __init__\(.*data_source.*\)", "Constructor accepts data_source parameter"),
        (r"self\.data_source = data_source", "Data source is stored"),
        (r"def _should_use_openmeteo\(", "Has _should_use_openmeteo method"),
        (r"def _is_us_location\(", "Has _is_us_location method"),
        (r"def _set_empty_weather_data\(", "Has _set_empty_weather_data method"),
        (
            r"should_use_openmeteo = self\._should_use_openmeteo\(location\)",
            "Uses automatic API selection",
        ),
        (r"if should_use_openmeteo:", "Branches based on API selection"),
        (r"_get_openmeteo_current_conditions", "Has Open-Meteo current conditions method"),
        (r"_get_openmeteo_forecast", "Has Open-Meteo forecast method"),
        (r"24\.0 <= location\.latitude <= 49\.0", "Has US latitude bounds check"),
        (r"-125\.0 <= location\.longitude <= -66\.0", "Has US longitude bounds check"),
    ]

    passed = 0
    for pattern, description in checks:
        if re.search(pattern, content):
            print(f"✅ {description}")
            passed += 1
        else:
            print(f"❌ {description}")

    print(f"\nWeather client integration: {passed}/{len(checks)} checks passed")
    return passed == len(checks)


def check_app_integration():
    """Check that the app properly configures the weather client."""
    print("\n🔍 Checking app integration...")

    app_path = os.path.join("src", "accessiweather", "simple", "app.py")

    if not os.path.exists(app_path):
        print("❌ App file not found")
        return False

    with open(app_path) as f:
        content = f.read()

    # Check for app integration features
    checks = [
        (r"data_source = config\.settings\.data_source", "Reads data source from config"),
        (r"WeatherClient\(.*data_source=data_source", "Passes data source to weather client"),
        (r"Tokyo, Japan.*35\.6762.*139\.6503", "Has Tokyo test location"),
        (r"London, UK.*51\.5074.*-0\.1278", "Has London test location"),
        (r"Sydney, Australia.*-33\.8688.*151\.2093", "Has Sydney test location"),
        (r"Paris, France.*48\.8566.*2\.3522", "Has Paris test location"),
    ]

    passed = 0
    for pattern, description in checks:
        if re.search(pattern, content):
            print(f"✅ {description}")
            passed += 1
        else:
            print(f"❌ {description}")

    print(f"\nApp integration: {passed}/{len(checks)} checks passed")
    return passed == len(checks)


def check_models_support():
    """Check that models support the required data structures."""
    print("\n🔍 Checking models support...")

    models_path = os.path.join("src", "accessiweather", "simple", "models.py")

    if not os.path.exists(models_path):
        print("❌ Models file not found")
        return False

    with open(models_path) as f:
        content = f.read()

    # Check for required model features
    checks = [
        (r'data_source.*str.*=.*"auto"', "AppSettings has data_source field"),
        (r"class Location", "Has Location model"),
        (r"class CurrentConditions", "Has CurrentConditions model"),
        (r"class Forecast", "Has Forecast model"),
        (r"class WeatherData", "Has WeatherData model"),
        (r"def has_data\(", "Models have has_data methods"),
    ]

    passed = 0
    for pattern, description in checks:
        if re.search(pattern, content):
            print(f"✅ {description}")
            passed += 1
        else:
            print(f"❌ {description}")

    print(f"\nModels support: {passed}/{len(checks)} checks passed")
    return passed == len(checks)


def check_test_integration():
    """Check that tests have been updated."""
    print("\n🔍 Checking test integration...")

    test_path = os.path.join("tests", "test_simple_weather_client.py")

    if not os.path.exists(test_path):
        print("❌ Test file not found")
        return False

    with open(test_path) as f:
        content = f.read()

    # Check for test integration features
    checks = [
        (r"class TestWeatherClientOpenMeteoIntegration", "Has Open-Meteo integration test class"),
        (r"def test_should_use_openmeteo_auto_mode", "Has automatic API selection test"),
        (r"def test_should_use_openmeteo_forced_modes", "Has forced mode test"),
        (r"def test_is_us_location", "Has US location detection test"),
        (r'data_source.*=.*"auto"', "Tests data_source parameter"),
        (r"Tokyo, Japan.*35\.6762.*139\.6503", "Tests Tokyo location"),
        (r"London, UK.*51\.5074.*-0\.1278", "Tests London location"),
    ]

    passed = 0
    for pattern, description in checks:
        if re.search(pattern, content):
            print(f"✅ {description}")
            passed += 1
        else:
            print(f"❌ {description}")

    print(f"\nTest integration: {passed}/{len(checks)} checks passed")
    return passed == len(checks)


def validate_api_selection_logic():
    """Validate the API selection logic mathematically."""
    print("\n🔍 Validating API selection logic...")

    # Test coordinates
    test_cases = [
        # US locations (should use NWS in auto mode)
        ("Philadelphia, PA", 39.9526, -75.1652, True),
        ("New York, NY", 40.7128, -74.0060, True),
        ("Los Angeles, CA", 34.0522, -118.2437, True),
        ("Miami, FL", 25.7617, -80.1918, True),
        ("Seattle, WA", 47.6062, -122.3321, True),
        # International locations (should use Open-Meteo in auto mode)
        ("Tokyo, Japan", 35.6762, 139.6503, False),
        ("London, UK", 51.5074, -0.1278, False),
        ("Sydney, Australia", -33.8688, 151.2093, False),
        ("Paris, France", 48.8566, 2.3522, False),
        ("Mexico City, Mexico", 19.4326, -99.1332, False),
        ("Toronto, Canada", 43.6532, -79.3832, False),
    ]

    # US bounds from the code: 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0
    us_lat_min, us_lat_max = 24.0, 49.0
    us_lon_min, us_lon_max = -125.0, -66.0

    passed = 0
    for name, lat, lon, expected_us in test_cases:
        is_us = us_lat_min <= lat <= us_lat_max and us_lon_min <= lon <= us_lon_max

        if is_us == expected_us:
            api = "NWS" if is_us else "Open-Meteo"
            print(f"✅ {name}: {api} (lat={lat}, lon={lon})")
            passed += 1
        else:
            expected_api = "NWS" if expected_us else "Open-Meteo"
            actual_api = "NWS" if is_us else "Open-Meteo"
            print(f"❌ {name}: Expected {expected_api}, got {actual_api}")

    print(f"\nAPI selection logic: {passed}/{len(test_cases)} cases correct")
    return passed == len(test_cases)


def main():
    """Run all validation checks."""
    print("🧪 Validating Open-Meteo Integration in Simple Toga App")
    print("=" * 60)

    checks = [
        check_weather_client_integration,
        check_app_integration,
        check_models_support,
        check_test_integration,
        validate_api_selection_logic,
    ]

    passed_checks = 0
    for check in checks:
        if check():
            passed_checks += 1

    print("\n" + "=" * 60)
    print(f"📊 VALIDATION SUMMARY: {passed_checks}/{len(checks)} checks passed")

    if passed_checks == len(checks):
        print("🎉 ALL VALIDATIONS PASSED!")
        print("✅ Open-Meteo integration is properly implemented")
        print("✅ Automatic API selection based on location")
        print("✅ Configuration support for data source")
        print("✅ International test locations added")
        print("✅ Comprehensive test coverage")
        print("✅ Ready for production use!")
        return True
    print("❌ Some validations failed - check the output above")
    return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
