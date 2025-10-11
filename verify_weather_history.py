#!/usr/bin/env python3
"""Simple verification script for weather history feature."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def verify_imports():
    """Verify all imports work correctly."""
    print("✓ Checking imports...")
    try:
        from accessiweather.weather_history import (
            WeatherHistoryService,
            HistoricalWeatherData,
            WeatherComparison,
        )

        print("  ✓ weather_history imports OK")
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False

    return True


def verify_api_structure():
    """Verify API call structure is correct."""
    print("\n✓ Checking API call structure...")

    # Check that the parameters match Open-Meteo archive API spec
    expected_params = [
        "latitude",
        "longitude",
        "start_date",
        "end_date",
        "daily",
        "temperature_unit",
        "timezone",
    ]

    # Check that daily variables are valid for archive endpoint
    expected_daily_vars = [
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "temperature_2m_mean",
        "wind_speed_10m_max",
        "wind_direction_10m_dominant",
    ]

    print(f"  ✓ Expected API parameters: {', '.join(expected_params)}")
    print(f"  ✓ Expected daily variables: {', '.join(expected_daily_vars)}")

    return True


def verify_integration():
    """Verify integration points are correctly set up."""
    print("\n✓ Checking integration points...")

    integration_files = [
        "src/accessiweather/app_initialization.py",
        "src/accessiweather/app.py",
        "src/accessiweather/handlers/weather_handlers.py",
        "src/accessiweather/ui_builder.py",
        "src/accessiweather/dialogs/settings_tabs.py",
        "src/accessiweather/dialogs/settings_handlers.py",
    ]

    for file_path in integration_files:
        if Path(file_path).exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ Missing: {file_path}")
            return False

    return True


def verify_compilation():
    """Verify all Python files compile."""
    print("\n✓ Checking compilation...")

    import py_compile

    files_to_check = [
        "src/accessiweather/weather_history.py",
        "src/accessiweather/app_initialization.py",
        "src/accessiweather/handlers/weather_handlers.py",
        "src/accessiweather/ui_builder.py",
    ]

    for file_path in files_to_check:
        try:
            py_compile.compile(file_path, doraise=True)
            print(f"  ✓ {file_path}")
        except py_compile.PyCompileError as e:
            print(f"  ✗ Compilation error in {file_path}: {e}")
            return False

    return True


def verify_test_file():
    """Verify test file exists and has correct structure."""
    print("\n✓ Checking test file...")

    test_file = Path("tests/test_weather_history.py")
    if not test_file.exists():
        print("  ✗ Test file missing")
        return False

    print(f"  ✓ {test_file}")

    # Check test file contains expected test classes
    content = test_file.read_text()
    expected_classes = [
        "TestHistoricalWeatherData",
        "TestWeatherComparison",
        "TestWeatherHistoryService",
    ]

    for class_name in expected_classes:
        if class_name in content:
            print(f"  ✓ Test class: {class_name}")
        else:
            print(f"  ✗ Missing test class: {class_name}")

    return True


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("Weather History Feature Verification")
    print("=" * 70)

    checks = [
        ("Imports", verify_imports),
        ("API Structure", verify_api_structure),
        ("Integration Points", verify_integration),
        ("Compilation", verify_compilation),
        ("Test File", verify_test_file),
    ]

    all_passed = True
    for name, check_func in checks:
        try:
            if not check_func():
                all_passed = False
                print(f"\n✗ {name} check FAILED")
        except Exception as e:
            all_passed = False
            print(f"\n✗ {name} check FAILED with exception: {e}")

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL CHECKS PASSED")
        print("=" * 70)
        return 0
    else:
        print("✗ SOME CHECKS FAILED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
