#!/usr/bin/env python3
"""Test runner for the simplified AccessiWeather application.

This script demonstrates how to run tests for the simplified AccessiWeather
application using the BeeWare testing approach with briefcase dev --test.
"""

import sys
from pathlib import Path


def run_beeware_tests():
    """Run tests using the BeeWare testing approach."""
    print("=" * 60)
    print("AccessiWeather Simplified - BeeWare Test Suite")
    print("=" * 60)

    print("\n🧪 Running tests with briefcase dev --test...")
    print("This will run the tests in the BeeWare development environment.")
    print("\nNote: Make sure beeware-venv is activated before running this!")

    # Show the command that should be run
    print("\n📋 Command to run (first time - installs test requirements):")
    print("   briefcase dev --test -r")
    print("\n📋 Command to run (subsequent times):")
    print("   briefcase dev --test")

    print("\n📋 To run specific test files:")
    print("   briefcase dev --test -- tests/test_simple_app.py")
    print("   briefcase dev --test -- tests/test_simple_weather_fetching.py")

    print("\n📋 To run tests with verbose output:")
    print("   briefcase dev --test -- -v")

    print("\n📋 To run tests and see coverage:")
    print("   briefcase dev --test -- --cov=accessiweather.simple")

    print("\n" + "=" * 60)
    print("Test Files Created:")
    print("=" * 60)

    test_files = ["tests/test_simple_app.py", "tests/test_simple_weather_fetching.py"]

    for test_file in test_files:
        if Path(test_file).exists():
            print(f"✅ {test_file}")
        else:
            print(f"❌ {test_file} (not found)")

    print("\n" + "=" * 60)
    print("What These Tests Cover:")
    print("=" * 60)

    test_coverage = [
        "✅ Core data models (Location, CurrentConditions, Forecast, etc.)",
        "✅ Utility functions (temperature formatting, wind direction conversion)",
        "✅ WX-style weather formatter (exact copy of wx version formatting)",
        "✅ Weather client API integration (NWS and OpenMeteo)",
        "✅ Location manager functionality",
        "✅ Configuration management",
        "✅ Wind direction formatting bug fix verification",
        "✅ Error handling and fallback mechanisms",
        "✅ App component integration",
        "✅ Import and initialization tests",
    ]

    for item in test_coverage:
        print(f"  {item}")

    print("\n" + "=" * 60)
    print("BeeWare Testing Best Practices:")
    print("=" * 60)

    best_practices = [
        "🔧 Use 'briefcase dev --test' for development testing",
        "📦 Use 'briefcase run --test' for packaged app testing",
        "🎯 Test both individual components and integration",
        "🔄 Use async/await for testing async functionality",
        "🛡️ Mock external API calls for reliable testing",
        "📊 Test error handling and edge cases",
        "🧩 Test that components work together",
        "📝 Follow pytest conventions for test naming",
        "🏷️ Use descriptive test names and docstrings",
        "⚡ Keep tests fast and focused",
    ]

    for item in best_practices:
        print(f"  {item}")

    print("\n" + "=" * 60)
    print("Example Test Commands:")
    print("=" * 60)

    commands = [
        ("Run all tests", "briefcase dev --test"),
        ("Run with requirements update", "briefcase dev --test -r"),
        ("Run specific test file", "briefcase dev --test -- tests/test_simple_app.py"),
        ("Run with verbose output", "briefcase dev --test -- -v"),
        (
            "Run specific test method",
            "briefcase dev --test -- tests/test_simple_app.py::TestSimpleAppComponents::test_location_model",
        ),
        ("Run tests matching pattern", "briefcase dev --test -- -k 'weather_fetching'"),
        ("Run in packaged app", "briefcase run --test"),
    ]

    for description, command in commands:
        print(f"  {description}:")
        print(f"    {command}")
        print()

    print("=" * 60)
    print("Ready to test! 🚀")
    print("=" * 60)

    return True


def check_test_environment():
    """Check if the test environment is properly set up."""
    print("🔍 Checking test environment...")

    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("❌ pyproject.toml not found. Make sure you're in the project root.")
        return False

    # Check if tests directory exists
    if not Path("tests").exists():
        print("❌ tests directory not found.")
        return False

    # Check if simplified app exists
    if not Path("src/accessiweather/simple").exists():
        print("❌ Simplified app directory not found.")
        return False

    print("✅ Test environment looks good!")
    return True


def main():
    """Main function."""
    print("AccessiWeather Simplified - Test Runner")
    print("Using BeeWare Testing Approach")

    if not check_test_environment():
        print("\n❌ Environment check failed. Please fix the issues above.")
        return 1

    run_beeware_tests()

    print("\n💡 Pro tip: Activate beeware-venv first, then run:")
    print("   briefcase dev --test -r  # First time (installs test requirements)")
    print("   briefcase dev --test     # Subsequent runs")

    return 0


if __name__ == "__main__":
    sys.exit(main())
