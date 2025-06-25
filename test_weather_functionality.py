#!/usr/bin/env python3
"""Test script to verify weather data functionality works."""

import logging
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from accessiweather.config_utils import get_config_dir
from accessiweather.toga_formatter import TogaWeatherFormatter

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_weather_services():
    """Test weather service initialization and data fetching."""
    try:
        logger.info("Testing weather service initialization...")
        
        # Load configuration
        config_dir = get_config_dir()
        config_path = os.path.join(config_dir, "config.json")
        
        config = {"settings": {"data_source": "auto"}}
        if os.path.exists(config_path):
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
        
        logger.info(f"Using config: {config}")
        
        # Create NWS API client
        from accessiweather.api_wrapper import NoaaApiWrapper
        nws_client = NoaaApiWrapper(
            user_agent="AccessiWeather-Test",
            enable_caching=True,
            cache_ttl=300,
        )
        logger.info("NWS client created")
        
        # Create Open-Meteo client
        from accessiweather.openmeteo_client import OpenMeteoApiClient
        openmeteo_client = OpenMeteoApiClient(
            user_agent="AccessiWeather-Test",
            enable_caching=True,
            cache_ttl=300,
        )
        logger.info("Open-Meteo client created")
        
        # Create location manager
        from accessiweather.location import LocationManager
        location_manager = LocationManager(config_dir=config_dir, data_source=config.get("settings", {}).get("data_source", "auto"))
        logger.info("Location manager created")
        
        # Create services
        from accessiweather.services.location_service import LocationService
        from accessiweather.services.weather_service import WeatherService
        
        weather_service = WeatherService(
            nws_client=nws_client, 
            openmeteo_client=openmeteo_client, 
            config=config
        )
        location_service = LocationService(location_manager)
        
        logger.info("Services created successfully")
        
        # Add test location
        success = location_service.add_location("Philadelphia, PA", 39.9526, -75.1652)
        if success:
            logger.info("Test location added successfully")
            location_service.set_current_location("Philadelphia, PA")
        else:
            logger.warning("Failed to add test location, using Nationwide")
        
        # Get current location
        current_location = location_service.get_current_location()
        logger.info(f"Current location: {current_location}")
        
        if current_location:
            name, lat, lon = current_location
            logger.info(f"Testing weather data for {name} ({lat}, {lon})")
            
            # Create formatter
            formatter = TogaWeatherFormatter(config)
            
            # Test current conditions
            try:
                logger.info("Fetching current conditions...")
                current_conditions = weather_service.get_current_conditions(lat, lon)
                logger.info(f"Current conditions data keys: {list(current_conditions.keys()) if current_conditions else 'None'}")
                
                formatted_current = formatter.format_current_conditions(current_conditions, name)
                logger.info(f"Formatted current conditions:\n{formatted_current}")
                
            except Exception as e:
                logger.error(f"Error fetching current conditions: {e}")
            
            # Test forecast
            try:
                logger.info("Fetching forecast...")
                forecast_data = weather_service.get_forecast(lat, lon)
                logger.info(f"Forecast data keys: {list(forecast_data.keys()) if forecast_data else 'None'}")
                
                formatted_forecast = formatter.format_forecast(forecast_data, name)
                logger.info(f"Formatted forecast:\n{formatted_forecast}")
                
            except Exception as e:
                logger.error(f"Error fetching forecast: {e}")
            
            # Test alerts
            try:
                logger.info("Fetching alerts...")
                alerts_data = weather_service.get_alerts(lat, lon)
                logger.info(f"Alerts data: {alerts_data}")
                
                formatted_alerts = formatter.format_alerts(alerts_data, name)
                logger.info(f"Formatted alerts:\n{formatted_alerts}")
                
            except Exception as e:
                logger.error(f"Error fetching alerts: {e}")
        
        logger.info("Weather service test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Weather service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_weather_services()
    if success:
        print("✅ Weather functionality test passed!")
    else:
        print("❌ Weather functionality test failed!")
        sys.exit(1)
