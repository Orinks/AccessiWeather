#!/usr/bin/env python3
"""Debug script for the simplified AccessiWeather weather client."""

import asyncio
import logging
import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


async def test_weather_client():
    """Test the weather client with detailed debugging."""
    try:
        from accessiweather.simple.models import Location
        from accessiweather.simple.weather_client import WeatherClient
        
        # Create test location (Philadelphia, PA)
        test_location = Location("Philadelphia, PA", 39.9526, -75.1652)
        logger.info(f"Testing with location: {test_location}")
        
        # Create weather client
        client = WeatherClient(user_agent="AccessiWeather-Debug/1.0")
        logger.info("Weather client created")
        
        # Test NWS grid point lookup first
        await test_nws_grid_point(client, test_location)
        
        # Test full weather data fetch
        logger.info("=" * 50)
        logger.info("Testing full weather data fetch...")
        
        weather_data = await client.get_weather_data(test_location)
        
        logger.info(f"Weather data retrieved: {weather_data}")
        logger.info(f"Has current data: {weather_data.current and weather_data.current.has_data()}")
        logger.info(f"Has forecast data: {weather_data.forecast and weather_data.forecast.has_data()}")
        logger.info(f"Has alerts: {weather_data.alerts and weather_data.alerts.has_alerts()}")
        
        # Print detailed results
        if weather_data.current:
            logger.info(f"Current temperature: {weather_data.current.temperature_f}°F")
            logger.info(f"Current condition: {weather_data.current.condition}")
        
        if weather_data.forecast and weather_data.forecast.periods:
            logger.info(f"Forecast periods: {len(weather_data.forecast.periods)}")
            for i, period in enumerate(weather_data.forecast.periods[:3]):
                logger.info(f"  Period {i+1}: {period.name} - {period.temperature}°{period.temperature_unit} - {period.short_forecast}")
        
        return True
        
    except Exception as e:
        logger.error(f"Weather client test failed: {e}")
        traceback.print_exc()
        return False


async def test_nws_grid_point(client, location):
    """Test NWS grid point lookup specifically."""
    try:
        import httpx
        
        logger.info("Testing NWS grid point lookup...")
        grid_url = f"{client.nws_base_url}/points/{location.latitude},{location.longitude}"
        logger.info(f"Grid URL: {grid_url}")
        
        async with httpx.AsyncClient(timeout=client.timeout) as http_client:
            headers = {"User-Agent": client.user_agent}
            logger.info(f"Headers: {headers}")
            
            response = await http_client.get(grid_url, headers=headers)
            logger.info(f"Grid response status: {response.status_code}")
            
            if response.status_code == 200:
                grid_data = response.json()
                logger.info(f"Grid data keys: {list(grid_data.keys())}")
                
                if "properties" in grid_data:
                    props = grid_data["properties"]
                    logger.info(f"Grid properties keys: {list(props.keys())}")
                    
                    if "observationStations" in props:
                        stations_url = props["observationStations"]
                        logger.info(f"Observation stations URL: {stations_url}")
                        
                        # Test stations lookup
                        stations_response = await http_client.get(stations_url, headers=headers)
                        logger.info(f"Stations response status: {stations_response.status_code}")
                        
                        if stations_response.status_code == 200:
                            stations_data = stations_response.json()
                            features = stations_data.get("features", [])
                            logger.info(f"Found {len(features)} observation stations")
                            
                            if features:
                                station = features[0]
                                station_id = station["properties"]["stationIdentifier"]
                                logger.info(f"First station ID: {station_id}")
                                
                                # Test latest observation
                                obs_url = f"{client.nws_base_url}/stations/{station_id}/observations/latest"
                                logger.info(f"Observation URL: {obs_url}")
                                
                                obs_response = await http_client.get(obs_url, headers=headers)
                                logger.info(f"Observation response status: {obs_response.status_code}")
                                
                                if obs_response.status_code == 200:
                                    obs_data = obs_response.json()
                                    logger.info(f"Observation data keys: {list(obs_data.keys())}")
                                    
                                    if "properties" in obs_data:
                                        obs_props = obs_data["properties"]
                                        logger.info(f"Observation properties keys: {list(obs_props.keys())}")
                                        
                                        # Check temperature data
                                        temp_data = obs_props.get("temperature", {})
                                        logger.info(f"Temperature data: {temp_data}")
                                        
                                        text_desc = obs_props.get("textDescription")
                                        logger.info(f"Text description: {text_desc}")
                                else:
                                    logger.error(f"Observation request failed: {obs_response.text}")
                            else:
                                logger.warning("No observation stations found")
                        else:
                            logger.error(f"Stations request failed: {stations_response.text}")
                    else:
                        logger.error("No observationStations in grid properties")
                else:
                    logger.error("No properties in grid data")
            else:
                logger.error(f"Grid request failed: {response.text}")
                
    except Exception as e:
        logger.error(f"NWS grid point test failed: {e}")
        traceback.print_exc()


async def test_openmeteo_fallback():
    """Test OpenMeteo API as fallback."""
    try:
        from accessiweather.simple.models import Location
        from accessiweather.simple.weather_client import WeatherClient
        
        logger.info("=" * 50)
        logger.info("Testing OpenMeteo API fallback...")
        
        test_location = Location("Test Location", 39.9526, -75.1652)
        client = WeatherClient(user_agent="AccessiWeather-Debug/1.0")
        
        # Test OpenMeteo current conditions
        current = await client._get_openmeteo_current_conditions(test_location)
        logger.info(f"OpenMeteo current conditions: {current}")
        
        # Test OpenMeteo forecast
        forecast = await client._get_openmeteo_forecast(test_location)
        logger.info(f"OpenMeteo forecast: {forecast}")
        
        return True
        
    except Exception as e:
        logger.error(f"OpenMeteo test failed: {e}")
        traceback.print_exc()
        return False


async def test_location_coordinates():
    """Test different location coordinates."""
    try:
        from accessiweather.simple.models import Location
        from accessiweather.simple.weather_client import WeatherClient
        
        logger.info("=" * 50)
        logger.info("Testing different location coordinates...")
        
        # Test locations
        test_locations = [
            Location("Philadelphia, PA", 39.9526, -75.1652),
            Location("New York, NY", 40.7128, -74.0060),
            Location("Los Angeles, CA", 34.0522, -118.2437),
        ]
        
        client = WeatherClient(user_agent="AccessiWeather-Debug/1.0")
        
        for location in test_locations:
            logger.info(f"Testing location: {location.name} ({location.latitude}, {location.longitude})")
            
            try:
                weather_data = await client.get_weather_data(location)
                has_data = weather_data.has_any_data()
                logger.info(f"  Result: {'✓' if has_data else '✗'} Has data: {has_data}")
                
            except Exception as e:
                logger.error(f"  Error for {location.name}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Location coordinates test failed: {e}")
        traceback.print_exc()
        return False


async def main():
    """Run all debug tests."""
    logger.info("AccessiWeather Weather Client Debug Suite")
    logger.info("=" * 60)
    
    tests = [
        ("Weather Client Test", test_weather_client),
        ("OpenMeteo Fallback Test", test_openmeteo_fallback),
        ("Location Coordinates Test", test_location_coordinates),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running {test_name}...")
        try:
            result = await test_func()
            results.append((test_name, result))
            logger.info(f"{'✅' if result else '❌'} {test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            logger.error(f"❌ {test_name}: CRASHED - {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        logger.info(f"  {'✅' if result else '❌'} {test_name}")
    
    logger.info(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
    else:
        logger.info("⚠️  Some tests failed. Check logs above for details.")


if __name__ == "__main__":
    asyncio.run(main())
