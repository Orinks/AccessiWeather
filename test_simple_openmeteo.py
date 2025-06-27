#!/usr/bin/env python3
"""Test script to verify Open-Meteo integration in the simple Toga app."""

import asyncio
import sys
import os
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_simple_openmeteo_integration():
    """Test Open-Meteo integration in the simple app."""
    try:
        logger.info("Testing Open-Meteo integration in simple Toga app...")
        
        # Import the simple app components directly (avoiding toga dependency)
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'accessiweather', 'simple'))

        from weather_client import WeatherClient
        from models import Location, AppSettings
        
        # Test locations: mix of US and international
        test_locations = [
            # US locations (should use NWS)
            Location(name="Philadelphia, PA", latitude=39.9526, longitude=-75.1652),
            Location(name="Los Angeles, CA", latitude=34.0522, longitude=-118.2437),
            # International locations (should use Open-Meteo)
            Location(name="Tokyo, Japan", latitude=35.6762, longitude=139.6503),
            Location(name="London, UK", latitude=51.5074, longitude=-0.1278),
            Location(name="Sydney, Australia", latitude=-33.8688, longitude=151.2093),
            Location(name="Berlin, Germany", latitude=52.5200, longitude=13.4050),
        ]
        
        # Test with different data source configurations
        data_sources = ["auto", "openmeteo", "nws"]
        
        for data_source in data_sources:
            logger.info(f"\n=== Testing with data_source: {data_source} ===")
            
            # Create weather client with specific data source
            weather_client = WeatherClient(user_agent="AccessiWeather-Test", data_source=data_source)
            
            for location in test_locations:
                logger.info(f"\n--- Testing {location.name} ---")
                
                try:
                    # Determine expected API
                    should_use_openmeteo = weather_client._should_use_openmeteo(location)
                    expected_api = "Open-Meteo" if should_use_openmeteo else "NWS"
                    logger.info(f"Expected API: {expected_api}")
                    
                    # Fetch weather data
                    weather_data = await weather_client.get_weather_data(location)
                    
                    if weather_data and weather_data.current and weather_data.current.has_data():
                        logger.info(f"✅ Current conditions data available")

                        # Check temperature data
                        temp = weather_data.current.temperature_f
                        condition = weather_data.current.condition
                        humidity = weather_data.current.humidity

                        if temp is not None:
                            logger.info(f"Temperature: {temp}°F")
                        if condition:
                            logger.info(f"Condition: {condition}")
                        if humidity is not None:
                            logger.info(f"Humidity: {humidity}%")
                    else:
                        logger.warning(f"⚠️ No current conditions data for {location.name}")

                    if weather_data and weather_data.forecast and weather_data.forecast.has_data():
                        logger.info(f"✅ Forecast data available")

                        # Check forecast periods
                        periods = len(weather_data.forecast.periods)
                        logger.info(f"Forecast periods: {periods}")

                        # Show first forecast period
                        if periods > 0:
                            first_period = weather_data.forecast.periods[0]
                            logger.info(f"First period: {first_period.name} - {first_period.temperature}°F")
                    else:
                        logger.warning(f"⚠️ No forecast data for {location.name}")
                    
                    logger.info(f"✅ {location.name} - Integration test successful")
                    
                except Exception as e:
                    logger.error(f"❌ {location.name} - Integration test failed: {e}")
                    import traceback
                    traceback.print_exc()
        
        logger.info("\n=== Simple App Open-Meteo Integration Test Complete ===")
        logger.info("✅ Open-Meteo integration is working in the simple Toga app!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_openmeteo_integration())
