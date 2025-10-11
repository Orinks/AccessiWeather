#!/usr/bin/env python3
"""Demo script for Weather History feature using Open-Meteo archive API.

This script demonstrates the weather history comparison functionality
using Open-Meteo's historical weather API.
"""

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "accessiweather"))


@dataclass
class Location:
    """Mock Location model for demo."""

    name: str
    latitude: float
    longitude: float
    timezone: str


@dataclass
class CurrentConditions:
    """Mock CurrentConditions model for demo."""

    temperature: float
    condition: str
    humidity: int
    wind_speed: float
    wind_direction: str
    pressure: float


# Mock the models module
class MockModels:
    Location = Location
    CurrentConditions = CurrentConditions


sys.modules["accessiweather.models"] = MockModels()

# Now import weather_history
from weather_history import WeatherHistoryService, HistoricalWeatherData, WeatherComparison


def create_mock_client():
    """Create a mock Open-Meteo client for demonstration."""
    mock_client = MagicMock()
    
    # Mock responses for different dates
    def mock_request(endpoint, params):
        target_date = params["start_date"]
        
        # Yesterday's weather (cooler, cloudy)
        if "2025-10-10" in target_date or (datetime.now() - timedelta(days=1)).date().isoformat() in target_date:
            return {
                "daily": {
                    "time": [target_date],
                    "weather_code": [3],
                    "temperature_2m_max": [72.0],
                    "temperature_2m_min": [62.0],
                    "temperature_2m_mean": [67.0],
                    "wind_speed_10m_max": [8.0],
                    "wind_direction_10m_dominant": [180],
                }
            }
        # Last week (rainy, cold)
        elif (datetime.now() - timedelta(days=7)).date().isoformat() in target_date:
            return {
                "daily": {
                    "time": [target_date],
                    "weather_code": [61],
                    "temperature_2m_max": [58.0],
                    "temperature_2m_min": [48.0],
                    "temperature_2m_mean": [53.0],
                    "wind_speed_10m_max": [15.0],
                    "wind_direction_10m_dominant": [90],
                }
            }
        # Default response
        return {
            "daily": {
                "time": [target_date],
                "weather_code": [2],
                "temperature_2m_max": [70.0],
                "temperature_2m_min": [60.0],
                "temperature_2m_mean": [65.0],
                "wind_speed_10m_max": [10.0],
                "wind_direction_10m_dominant": [270],
            }
        }
    
    def mock_weather_desc(code):
        descriptions = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            61: "Slight rain",
        }
        return descriptions.get(code, f"Weather code {code}")
    
    mock_client._make_request = MagicMock(side_effect=mock_request)
    mock_client.get_weather_description = MagicMock(side_effect=mock_weather_desc)
    
    return mock_client


def main():
    """Run the weather history demo."""
    print("=" * 70)
    print("Weather History Comparison Demo")
    print("Using Open-Meteo Archive API")
    print("=" * 70)
    print()

    # Create location
    print("1. Setting up location...")
    location = Location(
        name="New York City",
        latitude=40.7128,
        longitude=-74.0060,
        timezone="America/New_York",
    )
    print(f"   ✓ Location: {location.name}")
    print()

    # Initialize service with mock client
    print("2. Initializing Weather History Service...")
    mock_client = create_mock_client()
    service = WeatherHistoryService(openmeteo_client=mock_client)
    print("   ✓ Service created with Open-Meteo archive endpoint")
    print()

    # Simulate today's weather
    print("3. Today's Weather:")
    today_weather = CurrentConditions(
        temperature=78.0,
        condition="Sunny",
        humidity=55,
        wind_speed=5.0,
        wind_direction="W",
        pressure=30.2,
    )
    print(f"   Temperature: {today_weather.temperature}°F")
    print(f"   Condition: {today_weather.condition}")
    print(f"   Humidity: {today_weather.humidity}%")
    print(f"   Wind: {today_weather.wind_speed} mph {today_weather.wind_direction}")
    print()

    # Compare with yesterday
    print("4. Comparing with Yesterday:")
    print("   Fetching historical data from Open-Meteo archive API...")
    yesterday_comp = service.compare_with_yesterday(location, today_weather)
    
    if yesterday_comp:
        print(f"   ✓ Historical data retrieved")
        print(f"   Temperature difference: {yesterday_comp.temperature_difference:+.1f}°F")
        print(f"   Condition: {'Changed' if yesterday_comp.condition_changed else 'Same'}")
        if yesterday_comp.condition_changed:
            print(f"   Previous: {yesterday_comp.previous_condition}")
        print()
        print("   Accessible Summary:")
        print(f"   \"{yesterday_comp.get_accessible_summary()}\"")
    else:
        print("   ✗ No historical data available")
    print()

    # Compare with last week
    print("5. Comparing with Last Week:")
    print("   Fetching historical data from Open-Meteo archive API...")
    week_comp = service.compare_with_last_week(location, today_weather)
    
    if week_comp:
        print(f"   ✓ Historical data retrieved")
        print(f"   Temperature difference: {week_comp.temperature_difference:+.1f}°F")
        print(f"   Condition: {'Changed' if week_comp.condition_changed else 'Same'}")
        if week_comp.condition_changed:
            print(f"   Previous: {week_comp.previous_condition}")
        print()
        print("   Accessible Summary:")
        print(f"   \"{week_comp.get_accessible_summary()}\"")
    else:
        print("   ✗ No historical data available")
    print()

    # Custom date comparison
    print("6. Comparing with Custom Date (5 days ago):")
    print("   Fetching historical data from Open-Meteo archive API...")
    custom_date = (datetime.now() - timedelta(days=5)).date()
    custom_comp = service.compare_with_date(location, today_weather, custom_date)
    
    if custom_comp:
        print(f"   ✓ Historical data retrieved for {custom_date}")
        print(f"   Temperature difference: {custom_comp.temperature_difference:+.1f}°F")
        print()
        print("   Accessible Summary:")
        print(f"   \"{custom_comp.get_accessible_summary()}\"")
    else:
        print("   ✗ No historical data available")
    print()

    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print()
    print("Key Features Demonstrated:")
    print("  ✓ Fetching historical weather from Open-Meteo archive API")
    print("  ✓ No local storage required")
    print("  ✓ Comparing current weather with past days")
    print("  ✓ Generating accessible summaries")
    print("  ✓ Support for custom date comparisons")
    print()
    print("Advantages over local tracking:")
    print("  • Access to decades of historical data")
    print("  • No need for background recording")
    print("  • Works immediately for all users")
    print("  • No local storage management")
    print()


if __name__ == "__main__":
    main()
