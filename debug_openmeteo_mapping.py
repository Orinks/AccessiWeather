#!/usr/bin/env python3
"""Debug script to investigate Open-Meteo data mapping issues."""

import sys
import os
import logging
import json

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_openmeteo_mapping():
    """Debug Open-Meteo data mapping to understand the issue."""
    try:
        from accessiweather.openmeteo_client import OpenMeteoApiClient
        from accessiweather.openmeteo_mapper import OpenMeteoMapper
        from accessiweather.toga_formatter import TogaWeatherFormatter
        
        # Create clients
        openmeteo_client = OpenMeteoApiClient(user_agent="AccessiWeather-Debug")
        openmeteo_mapper = OpenMeteoMapper()
        
        # Test with Tokyo
        lat, lon = 35.6762, 139.6503
        logger.info(f"Testing data mapping for Tokyo ({lat}, {lon})")
        
        # Get raw data from Open-Meteo
        logger.info("=== Fetching raw current conditions ===")
        raw_current = openmeteo_client.get_current_weather(
            latitude=lat,
            longitude=lon,
            temperature_unit="fahrenheit",
            wind_speed_unit="mph",
            precipitation_unit="inch"
        )
        logger.info(f"Raw current data: {json.dumps(raw_current, indent=2)}")
        
        # Map to NWS format
        logger.info("=== Mapping current conditions ===")
        mapped_current = openmeteo_mapper.map_current_conditions(raw_current)
        logger.info(f"Mapped current data: {json.dumps(mapped_current, indent=2)}")
        
        # Get raw forecast data
        logger.info("=== Fetching raw forecast ===")
        raw_forecast = openmeteo_client.get_forecast(
            latitude=lat,
            longitude=lon,
            days=7,
            temperature_unit="fahrenheit",
            wind_speed_unit="mph",
            precipitation_unit="inch"
        )
        logger.info(f"Raw forecast data: {json.dumps(raw_forecast, indent=2)}")
        
        # Map forecast
        logger.info("=== Mapping forecast ===")
        mapped_forecast = openmeteo_mapper.map_forecast(raw_forecast)
        logger.info(f"Mapped forecast data: {json.dumps(mapped_forecast, indent=2)}")
        
        # Test formatter expectations
        logger.info("=== Testing formatter expectations ===")
        config = {"settings": {"temperature_unit": "fahrenheit"}}
        formatter = TogaWeatherFormatter(config)
        
        # Check what the formatter expects vs what we're providing
        logger.info("Checking current conditions format...")
        formatted_current = formatter.format_current_conditions(mapped_current, "Tokyo, Japan")
        logger.info(f"Formatted current: {formatted_current}")
        
        logger.info("Checking forecast format...")
        formatted_forecast = formatter.format_forecast(mapped_forecast, "Tokyo, Japan")
        logger.info(f"Formatted forecast: {formatted_forecast}")
        
        # Let's also check what the wx version expects
        logger.info("=== Checking expected data format ===")
        
        # Create a sample of what the formatter expects
        expected_current = {
            "temperature": 75.0,
            "temperature_c": 24.0,
            "condition": "Partly cloudy",
            "humidity": 65,
            "wind_speed": 8,
            "wind_direction": "SW",
            "pressure": 30.15,
            "feelslike": 78,
            "feelslike_c": 26,
        }
        
        logger.info("Testing with expected format...")
        formatted_expected = formatter.format_current_conditions(expected_current, "Tokyo, Japan")
        logger.info(f"Formatted expected: {formatted_expected}")
        
    except Exception as e:
        logger.error(f"Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_openmeteo_mapping()
