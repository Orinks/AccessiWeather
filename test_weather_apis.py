#!/usr/bin/env python3
"""Test script to check weather API endpoints directly."""

import asyncio
import logging
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from accessiweather.models import Location
from accessiweather.weather_client import WeatherClient

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_weather_apis():
    """Test weather APIs with a sample location."""
    # Test location: Philadelphia, PA
    test_location = Location(name="Philadelphia, PA", latitude=39.9526, longitude=-75.1652)

    logger.info(f"Testing weather APIs for {test_location.name}")

    # Create weather client
    client = WeatherClient(user_agent="AccessiWeather-Test/1.0")

    try:
        # Test getting weather data
        logger.info("Fetching weather data...")
        weather_data = await client.get_weather_data(test_location)

        logger.info(f"Weather data retrieved: {weather_data}")

        # Check if we have any data
        if weather_data.has_any_data():
            logger.info("✓ Weather data is available!")

            # Check current conditions
            if weather_data.current and weather_data.current.has_data():
                logger.info(
                    f"✓ Current conditions: {weather_data.current.temperature_f}°F, {weather_data.current.condition}"
                )
            else:
                logger.warning("✗ No current conditions data")

            # Check forecast
            if weather_data.forecast and weather_data.forecast.has_data():
                logger.info(f"✓ Forecast: {len(weather_data.forecast.periods)} periods")
                for i, period in enumerate(
                    weather_data.forecast.periods[:3]
                ):  # Show first 3 periods
                    logger.info(
                        f"  {period.name}: {period.temperature}°{period.temperature_unit}, {period.short_forecast}"
                    )
            else:
                logger.warning("✗ No forecast data")

            # Check alerts
            if weather_data.alerts and weather_data.alerts.has_alerts():
                logger.info(f"✓ Alerts: {len(weather_data.alerts.alerts)} alerts")
                for alert in weather_data.alerts.alerts[:3]:  # Show first 3 alerts
                    logger.info(f"  {alert.event}: {alert.headline}")
            else:
                logger.info("ℹ No weather alerts")

        else:
            logger.error("✗ No weather data available - this is the problem!")

            # Debug the individual components
            logger.info("Debugging individual components:")
            logger.info(f"Current conditions: {weather_data.current}")
            logger.info(f"Forecast: {weather_data.forecast}")
            logger.info(f"Alerts: {weather_data.alerts}")

    except Exception as e:
        logger.error(f"Error testing weather APIs: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_weather_apis())
