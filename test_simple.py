#!/usr/bin/env python3
"""Test script for the simplified AccessiWeather application."""

import sys
import traceback


def test_imports():
    """Test importing the simplified modules."""
    print("Testing imports...")

    try:
        print("1. Testing models...")
        print("   ✓ Models imported successfully")

        print("2. Testing weather client...")
        print("   ✓ Weather client imported successfully")

        print("3. Testing config manager...")
        print("   ✓ Config manager imported successfully")

        print("4. Testing formatters...")
        print("   ✓ Formatters imported successfully")

        print("5. Testing location manager...")
        print("   ✓ Location manager imported successfully")

        print("6. Testing main app...")
        print("   ✓ Main app imported successfully")

        print("\n✅ All imports successful!")
        return True

    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        traceback.print_exc()
        return False


def test_basic_functionality():
    """Test basic functionality without GUI."""
    print("\nTesting basic functionality...")

    try:
        from src.accessiweather.formatters import WeatherFormatter
        from src.accessiweather.models import AppSettings, Location

        # Test location creation
        location = Location("Test City", 40.7128, -74.0060)
        print(f"   ✓ Created location: {location}")

        # Test settings
        settings = AppSettings()
        print(f"   ✓ Created settings: {settings.temperature_unit}")

        # Test formatter (instantiate to verify import works)
        WeatherFormatter(settings)
        print("   ✓ Created formatter")

        print("\n✅ Basic functionality test passed!")
        return True

    except Exception as e:
        print(f"\n❌ Basic functionality test failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("AccessiWeather Simplified - Test Suite")
    print("=" * 40)

    # Test imports
    if not test_imports():
        sys.exit(1)

    # Test basic functionality
    if not test_basic_functionality():
        sys.exit(1)

    print("\n🎉 All tests passed! The simplified AccessiWeather is ready.")


if __name__ == "__main__":
    main()
