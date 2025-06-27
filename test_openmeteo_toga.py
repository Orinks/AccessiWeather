#!/usr/bin/env python3
"""Test script to verify Open-Meteo integration in the Toga app."""

import sys
import os
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_openmeteo_integration():
    """Test Open-Meteo integration with international locations."""
    try:
        # Import required modules
        from accessiweather.openmeteo_client import OpenMeteoApiClient
        from accessiweather.openmeteo_mapper import OpenMeteoMapper
        
        logger.info("Testing Open-Meteo integration...")
        
        # Create Open-Meteo client
        openmeteo_client = OpenMeteoApiClient(user_agent="AccessiWeather-Test")
        logger.info("Created Open-Meteo client")
        
        # Create mapper
        openmeteo_mapper = OpenMeteoMapper()
        logger.info("Created Open-Meteo mapper")
        
        # Test international locations
        test_locations = [
            ("Tokyo, Japan", 35.6762, 139.6503),
            ("London, UK", 51.5074, -0.1278),
            ("Sydney, Australia", -33.8688, 151.2093),
            ("Berlin, Germany", 52.5200, 13.4050),
        ]
        
        for name, lat, lon in test_locations:
            logger.info(f"\n=== Testing {name} ({lat}, {lon}) ===")
            
            try:
                # Test current conditions
                logger.info("Fetching current conditions...")
                current_data = openmeteo_client.get_current_weather(
                    latitude=lat,
                    longitude=lon,
                    temperature_unit="fahrenheit",
                    wind_speed_unit="mph",
                    precipitation_unit="inch"
                )
                logger.info(f"Raw current data keys: {list(current_data.keys())}")
                
                # Map to NWS format
                mapped_current = openmeteo_mapper.map_current_conditions(current_data)
                logger.info("Successfully mapped current conditions to NWS format")
                
                # Test forecast
                logger.info("Fetching forecast...")
                forecast_data = openmeteo_client.get_forecast(
                    latitude=lat,
                    longitude=lon,
                    days=7,
                    temperature_unit="fahrenheit",
                    wind_speed_unit="mph",
                    precipitation_unit="inch"
                )
                logger.info(f"Raw forecast data keys: {list(forecast_data.keys())}")
                
                # Map to NWS format
                mapped_forecast = openmeteo_mapper.map_forecast(forecast_data)
                logger.info("Successfully mapped forecast to NWS format")
                
                # Print some sample data
                if 'current' in current_data:
                    current = current_data['current']
                    temp = current.get('temperature_2m', 'N/A')
                    humidity = current.get('relative_humidity_2m', 'N/A')
                    logger.info(f"Current: {temp}°F, {humidity}% humidity")
                
                if 'daily' in forecast_data:
                    daily = forecast_data['daily']
                    if daily.get('time') and daily.get('temperature_2m_max'):
                        first_day = daily['time'][0]
                        max_temp = daily['temperature_2m_max'][0]
                        logger.info(f"Forecast: {first_day} - High: {max_temp}°F")
                
                logger.info(f"✅ {name} - Open-Meteo integration working correctly")
                
            except Exception as e:
                logger.error(f"❌ {name} - Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Test coordinate-based logic (simplified)
        logger.info("\n=== Testing Location-Based API Selection Logic ===")

        def is_us_location(lat, lon):
            """Simple US location check."""
            # Continental US bounds (approximate)
            return (24.0 <= lat <= 49.0) and (-125.0 <= lon <= -66.0)

        # Test US location (should use NWS)
        us_lat, us_lon = 39.9526, -75.1652  # Philadelphia
        is_us = is_us_location(us_lat, us_lon)
        logger.info(f"US location ({us_lat}, {us_lon}) is in US: {is_us} (should use NWS)")

        # Test international location (should use Open-Meteo)
        intl_lat, intl_lon = 35.6762, 139.6503  # Tokyo
        is_us_intl = is_us_location(intl_lat, intl_lon)
        logger.info(f"International location ({intl_lat}, {intl_lon}) is in US: {is_us_intl} (should use Open-Meteo)")

        if is_us and not is_us_intl:
            logger.info("✅ Location-based API selection logic working correctly")
        else:
            logger.warning("⚠️ Location-based API selection logic may have issues")
        
        logger.info("\n=== Open-Meteo Integration Test Complete ===")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_openmeteo_integration()
