#!/usr/bin/env python3
"""Debug script to reproduce the Visual Crossing API issue in AccessiWeather.

This script will reproduce the exact issue that occurs when a user selects 
a location with Visual Crossing as the data source.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the src directory to the path so we can import AccessiWeather modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from accessiweather.simple.models import Location
from accessiweather.simple.weather_client import WeatherClient

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_API_KEY = "P6QSSQ2LR9AZ8XJQ9Q7RVKFLS"  # From the example
TEST_LOCATION = Location("Lumberton, NJ", 39.9643, -74.8079)


async def reproduce_visual_crossing_issue():
    """Reproduce the exact issue that occurs in AccessiWeather."""
    print("Reproducing Visual Crossing issue...")
    print(f"Location: {TEST_LOCATION.name} ({TEST_LOCATION.latitude}, {TEST_LOCATION.longitude})")
    print(f"Data source: visualcrossing")
    print(f"API Key: {TEST_API_KEY}")
    print()
    
    # Create weather client exactly as AccessiWeather does
    weather_client = WeatherClient(
        user_agent="AccessiWeather/2.0",
        data_source="visualcrossing",  # Force Visual Crossing
        visual_crossing_api_key=TEST_API_KEY
    )
    
    try:
        # This should reproduce the exact error that occurs in AccessiWeather
        print("Calling weather_client.get_weather_data()...")
        weather_data = await weather_client.get_weather_data(TEST_LOCATION)
        
        print("✅ Success! Weather data retrieved:")
        print(f"   Current: {weather_data.current}")
        print(f"   Forecast: {weather_data.forecast}")
        print(f"   Hourly: {weather_data.hourly_forecast}")
        print(f"   Alerts: {weather_data.alerts}")
        
        # Try to access the data that the UI would access
        if weather_data.current:
            print(f"   Current temp: {weather_data.current.temperature_f}°F")
            print(f"   Current condition: {weather_data.current.condition}")
        
        if weather_data.forecast and weather_data.forecast.periods:
            first_period = weather_data.forecast.periods[0]
            print(f"   First forecast: {first_period.name} - {first_period.temperature}°F")
            print(f"   Forecast condition: {first_period.short_forecast}")
        
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        print(f"   Error type: {type(e).__name__}")
        # Set a breakpoint here to examine the error
        import traceback
        traceback.print_exc()
        raise  # Re-raise to trigger debugger


def main():
    """Main entry point for debugging."""
    print("Visual Crossing Debug Session")
    print("=" * 40)
    
    # Run the async function
    asyncio.run(reproduce_visual_crossing_issue())


if __name__ == "__main__":
    main()
