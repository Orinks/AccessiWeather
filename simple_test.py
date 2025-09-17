#!/usr/bin/env python3
"""Simple test for imports."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    print("Testing imports...")

    from accessiweather.models import AppSettings

    print("✓ Models imported")

    from accessiweather.formatters import WeatherFormatter

    print("✓ Formatter imported")

    # Test basic functionality
    settings = AppSettings()
    formatter = WeatherFormatter(settings)
    print("✓ Formatter created")

    # Test wind formatting with numeric direction
    wind_text = formatter._format_wind(15.0, None, 330)
    print(f"✓ Wind formatting test: '{wind_text}'")

    print("\n🎉 All tests passed!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
