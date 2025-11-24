"""Example: Fetching and displaying hourly air quality forecast."""

import asyncio

from accessiweather.display.presentation.environmental import format_hourly_air_quality
from accessiweather.models import Location
from accessiweather.services.environmental_client import EnvironmentalDataClient


async def main():
    """Demonstrate hourly air quality forecast."""
    # Initialize client
    client = EnvironmentalDataClient()

    # Define location
    location = Location(name="Los Angeles", latitude=34.0522, longitude=-118.2437)

    print(f"Fetching hourly air quality forecast for {location.name}...\n")

    # Fetch environmental data with hourly forecast
    result = await client.fetch(
        location,
        include_air_quality=True,
        include_pollen=False,
        include_hourly_air_quality=True,
        hourly_hours=24,
    )

    if not result:
        print("No data available")
        return

    # Display current air quality
    if result.air_quality_index:
        print(f"Current AQI: {result.air_quality_index:.0f} ({result.air_quality_category})")
        if result.air_quality_pollutant:
            print(f"Dominant pollutant: {result.air_quality_pollutant}")
        print()

    # Display hourly forecast
    if result.hourly_air_quality:
        print(f"Hourly Forecast ({len(result.hourly_air_quality)} hours):")
        print("=" * 60)
        print(format_hourly_air_quality(result.hourly_air_quality))
        print()

        # Show detailed breakdown for first 6 hours
        print("\nDetailed Breakdown (Next 6 Hours):")
        print("=" * 60)
        for hour in result.hourly_air_quality[:6]:
            time_str = hour.timestamp.strftime("%I:%M %p").lstrip("0")
            print(f"\n{time_str}:")
            print(f"  AQI: {hour.aqi} ({hour.category})")
            if hour.pm2_5:
                print(f"  PM2.5: {hour.pm2_5} μg/m³")
            if hour.pm10:
                print(f"  PM10: {hour.pm10} μg/m³")
            if hour.ozone:
                print(f"  Ozone: {hour.ozone} μg/m³")
            if hour.nitrogen_dioxide:
                print(f"  NO2: {hour.nitrogen_dioxide} μg/m³")


if __name__ == "__main__":
    asyncio.run(main())
