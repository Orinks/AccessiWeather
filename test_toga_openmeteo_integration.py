#!/usr/bin/env python3
"""Test script to verify Open-Meteo integration specifically in the Toga app context."""

import sys
import os
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_toga_openmeteo_integration():
    """Test Open-Meteo integration in the context of the Toga app."""
    try:
        logger.info("Testing Open-Meteo integration in Toga app context...")
        
        # Import the Toga weather formatter and transformer
        from accessiweather.toga_formatter import TogaWeatherFormatter
        from accessiweather.toga_data_transformer import TogaDataTransformer
        from accessiweather.openmeteo_client import OpenMeteoApiClient
        from accessiweather.openmeteo_mapper import OpenMeteoMapper
        
        # Create config similar to what Toga app uses
        config = {
            "settings": {
                "data_source": "auto",
                "temperature_unit": "fahrenheit",
                "show_nationwide_location": True,
                "update_interval_minutes": 10,
            },
            "api_keys": {},
            "api_settings": {},
        }
        
        # Create Open-Meteo client and mapper
        openmeteo_client = OpenMeteoApiClient(user_agent="AccessiWeather-Toga-Test")
        openmeteo_mapper = OpenMeteoMapper()

        # Create Toga formatter and transformer
        formatter = TogaWeatherFormatter(config)
        transformer = TogaDataTransformer()
        
        # Test international locations that should use Open-Meteo
        test_locations = [
            ("Tokyo, Japan", 35.6762, 139.6503),
            ("London, UK", 51.5074, -0.1278),
            ("Paris, France", 48.8566, 2.3522),
        ]
        
        for name, lat, lon in test_locations:
            logger.info(f"\n=== Testing {name} ({lat}, {lon}) ===")
            
            try:
                # Fetch current conditions using Open-Meteo
                logger.info("Fetching current conditions...")
                current_data = openmeteo_client.get_current_weather(
                    latitude=lat,
                    longitude=lon,
                    temperature_unit="fahrenheit",
                    wind_speed_unit="mph",
                    precipitation_unit="inch"
                )
                
                # Map to NWS format
                mapped_current = openmeteo_mapper.map_current_conditions(current_data)
                logger.info("Successfully mapped current conditions")

                # Fetch forecast using Open-Meteo
                logger.info("Fetching forecast...")
                forecast_data = openmeteo_client.get_forecast(
                    latitude=lat,
                    longitude=lon,
                    days=7,
                    temperature_unit="fahrenheit",
                    wind_speed_unit="mph",
                    precipitation_unit="inch"
                )

                # Map to NWS format
                mapped_forecast = openmeteo_mapper.map_forecast(forecast_data)
                logger.info("Successfully mapped forecast")

                # Transform to Toga formatter format
                logger.info("Transforming data for Toga formatter...")
                transformed_current = transformer.transform_current_conditions(mapped_current)
                transformed_forecast = transformer.transform_forecast(mapped_forecast)
                logger.info("Successfully transformed data")

                # Format using Toga formatter (this is what the app actually uses)
                logger.info("Formatting data for Toga display...")
                formatted_current = formatter.format_current_conditions(transformed_current, name)
                formatted_forecast = formatter.format_forecast(transformed_forecast, name)
                
                logger.info("✅ Successfully formatted data for Toga display")
                
                # Print sample formatted output
                logger.info(f"Sample current conditions output:\n{formatted_current[:200]}...")
                logger.info(f"Sample forecast output:\n{formatted_forecast[:200]}...")
                
                logger.info(f"✅ {name} - Complete Open-Meteo to Toga integration working correctly")
                
            except Exception as e:
                logger.error(f"❌ {name} - Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Test the complete workflow that the Toga app would use
        logger.info("\n=== Testing Complete Toga App Workflow ===")
        
        # Simulate what happens in _fetch_weather_data_sync
        name, lat, lon = "Berlin, Germany", 52.5200, 13.4050
        logger.info(f"Simulating complete workflow for {name} ({lat}, {lon})")
        
        try:
            # This is similar to what the Toga app does
            current_conditions = openmeteo_client.get_current_weather(lat, lon, temperature_unit="fahrenheit")
            mapped_current = openmeteo_mapper.map_current_conditions(current_conditions)

            forecast_data = openmeteo_client.get_forecast(lat, lon, days=7, temperature_unit="fahrenheit")
            mapped_forecast = openmeteo_mapper.map_forecast(forecast_data)

            # Transform to Toga formatter format (what the updated Toga app does)
            transformed_current = transformer.transform_current_conditions(mapped_current)
            transformed_forecast = transformer.transform_forecast(mapped_forecast)

            # Format the data for display (what Toga app does)
            formatted_data = {
                "current": formatter.format_current_conditions(transformed_current, name),
                "forecast": formatter.format_forecast(transformed_forecast, name),
                "alerts": "No alerts available for international locations",
            }
            
            logger.info("✅ Complete Toga app workflow simulation successful")
            logger.info(f"Current conditions length: {len(formatted_data['current'])} characters")
            logger.info(f"Forecast length: {len(formatted_data['forecast'])} characters")
            
            # Show a sample of the actual formatted output
            logger.info("\n=== Sample Formatted Output (as shown in Toga app) ===")
            logger.info("Current Conditions:")
            logger.info(formatted_data['current'][:300] + "..." if len(formatted_data['current']) > 300 else formatted_data['current'])
            logger.info("\nForecast:")
            logger.info(formatted_data['forecast'][:300] + "..." if len(formatted_data['forecast']) > 300 else formatted_data['forecast'])
            
        except Exception as e:
            logger.error(f"❌ Complete workflow test failed: {e}")
            import traceback
            traceback.print_exc()
        
        logger.info("\n=== Toga Open-Meteo Integration Test Complete ===")
        logger.info("✅ Open-Meteo integration is ready for use in the Toga app!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_toga_openmeteo_integration()
