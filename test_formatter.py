#!/usr/bin/env python3
"""Test script for the weather formatter."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_formatter():
    """Test the weather formatter with real data."""
    try:
        from accessiweather.formatters import WeatherFormatter
        from accessiweather.models import AppSettings, Location
        from accessiweather.weather_client import WeatherClient

        # Create test location
        test_location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Get real weather data
        client = WeatherClient(user_agent="AccessiWeather-Test/1.0")
        weather_data = await client.get_weather_data(test_location)

        print(f"Got weather data: {weather_data.has_any_data()}")

        # Create formatter
        settings = AppSettings()
        formatter = WeatherFormatter(settings)

        # Test formatting
        print("=" * 60)
        print("CURRENT CONDITIONS:")
        print("=" * 60)
        current_text = formatter.format_current_conditions(
            weather_data.current, weather_data.location
        )
        print(current_text)

        print("\n" + "=" * 60)
        print("FORECAST:")
        print("=" * 60)
        forecast_text = formatter.format_forecast(weather_data.forecast, weather_data.location)
        print(forecast_text)

        print("\n" + "=" * 60)
        print("ALERTS:")
        print("=" * 60)
        alerts_text = formatter.format_alerts(weather_data.alerts, weather_data.location)
        print(alerts_text)

        print("\n" + "=" * 60)
        print("SUMMARY:")
        print("=" * 60)
        summary_text = formatter.format_weather_summary(weather_data)
        print(summary_text)

        return True

    except Exception as e:
        print(f"Formatter test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_formatter())
    if result:
        print("\n✅ Formatter test passed!")
    else:
        print("\n❌ Formatter test failed!")
        sys.exit(1)
