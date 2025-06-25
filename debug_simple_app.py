#!/usr/bin/env python3
"""Debug script to test the simple app weather data flow."""

import asyncio
import logging
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from accessiweather.simple.weather_client import WeatherClient
from accessiweather.simple.models import Location
from accessiweather.simple.display import WxStyleWeatherFormatter
from accessiweather.simple.config import ConfigManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MockApp:
    """Mock app for testing config manager."""
    def __init__(self):
        self.paths = MockPaths()


class MockPaths:
    """Mock paths for testing."""
    def __init__(self):
        self.config = Path.cwd() / "test_config"
        self.config.mkdir(exist_ok=True)


async def test_simple_app_flow():
    """Test the complete simple app weather data flow."""
    logger.info("Testing simple app weather data flow")
    
    # Test location
    test_location = Location(
        name="Philadelphia, PA",
        latitude=39.9526,
        longitude=-75.1652
    )
    
    try:
        # 1. Test weather client
        logger.info("Step 1: Testing weather client")
        client = WeatherClient(user_agent="AccessiWeather-Debug/1.0")
        weather_data = await client.get_weather_data(test_location)
        
        logger.info(f"Weather data has_any_data: {weather_data.has_any_data()}")
        if weather_data.current:
            logger.info(f"Current conditions has_data: {weather_data.current.has_data()}")
        if weather_data.forecast:
            logger.info(f"Forecast has_data: {weather_data.forecast.has_data()}")
        if weather_data.alerts:
            logger.info(f"Alerts has_alerts: {weather_data.alerts.has_alerts()}")
        
        # 2. Test config manager
        logger.info("Step 2: Testing config manager")
        mock_app = MockApp()
        config_manager = ConfigManager(mock_app)
        config = config_manager.get_config()
        logger.info(f"Config loaded: {config}")
        
        # Add test location
        config_manager.add_location(test_location.name, test_location.latitude, test_location.longitude)
        current_location = config_manager.get_current_location()
        logger.info(f"Current location: {current_location}")
        
        # 3. Test formatter
        logger.info("Step 3: Testing formatter")
        formatter = WxStyleWeatherFormatter(config.settings)
        
        # Format current conditions
        current_text = formatter.format_current_conditions(weather_data.current, weather_data.location)
        logger.info(f"Current conditions formatted: {len(current_text)} characters")
        logger.info(f"Current conditions preview: {current_text[:200]}...")
        
        # Format forecast
        forecast_text = formatter.format_forecast(weather_data.forecast, weather_data.location)
        logger.info(f"Forecast formatted: {len(forecast_text)} characters")
        logger.info(f"Forecast preview: {forecast_text[:200]}...")
        
        # 4. Test the has_any_data logic
        logger.info("Step 4: Testing data validation logic")
        logger.info(f"WeatherData.has_any_data(): {weather_data.has_any_data()}")
        
        if weather_data.current:
            logger.info(f"Current conditions details:")
            logger.info(f"  temperature_f: {weather_data.current.temperature_f}")
            logger.info(f"  temperature_c: {weather_data.current.temperature_c}")
            logger.info(f"  condition: {weather_data.current.condition}")
            logger.info(f"  has_data(): {weather_data.current.has_data()}")
        
        if weather_data.forecast:
            logger.info(f"Forecast details:")
            logger.info(f"  periods count: {len(weather_data.forecast.periods)}")
            logger.info(f"  has_data(): {weather_data.forecast.has_data()}")
            if weather_data.forecast.periods:
                first_period = weather_data.forecast.periods[0]
                logger.info(f"  first period: {first_period.name}, {first_period.temperature}°{first_period.temperature_unit}")
        
        # 5. Test what would happen in the UI
        logger.info("Step 5: Testing UI logic simulation")
        
        # Simulate the _update_weather_displays method
        if weather_data.has_any_data():
            logger.info("✓ Weather data would be displayed in UI")
        else:
            logger.error("✗ Weather data would show 'No weather data available' - THIS IS THE PROBLEM!")
            
            # Debug why has_any_data is False
            logger.info("Debugging has_any_data logic:")
            current_has_data = weather_data.current and weather_data.current.has_data()
            forecast_has_data = weather_data.forecast and weather_data.forecast.has_data()
            alerts_has_data = weather_data.alerts and weather_data.alerts.has_alerts()
            
            logger.info(f"  current_has_data: {current_has_data}")
            logger.info(f"  forecast_has_data: {forecast_has_data}")
            logger.info(f"  alerts_has_data: {alerts_has_data}")
            logger.info(f"  any([{current_has_data}, {forecast_has_data}, {alerts_has_data}]): {any([current_has_data, forecast_has_data, alerts_has_data])}")
        
        logger.info("✓ Simple app flow test completed successfully")
        
    except Exception as e:
        logger.error(f"Error in simple app flow test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_simple_app_flow())
