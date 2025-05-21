#!/usr/bin/env python
"""
Test script to verify the generated NWS API client works.
"""

import asyncio
import sys
from datetime import datetime

from weather_gov_api_client.api.default import alerts_active, obs_station, point
from weather_gov_api_client.client import Client
from weather_gov_api_client.errors import UnexpectedStatus

# Test parameters
TEST_POINT = "39.7456,-97.0892"  # Example coordinates
TEST_STATION = "KBOS"  # Boston Logan Airport
TEST_OFFICE = "BOX"  # Boston, MA Weather Forecast Office


async def test_client():
    """Test the NWS API client."""
    print("Testing NWS API client...")

    # Initialize the client
    client = Client(
        base_url="https://api.weather.gov",
        headers={
            "User-Agent": "AccessiWeather/0.9.2 (github.com/Orinks/AccessiWeather; orin8722@gmail.com) Testing"
        },
    )

    # Test points endpoint
    print("\nTesting points endpoint...")
    try:
        start_time = datetime.now()
        point_response = await point.asyncio(point=TEST_POINT, client=client)
        end_time = datetime.now()

        print(f"Points endpoint test successful")
        print(f"Response time: {(end_time - start_time).total_seconds():.2f}s")
        print(f"Data sample: {str(point_response)[:200]}...")
    except UnexpectedStatus as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    # Test stations endpoint
    print("\nTesting stations endpoint...")
    try:
        start_time = datetime.now()
        station_response = await obs_station.asyncio(station_id=TEST_STATION, client=client)
        end_time = datetime.now()

        print(f"Stations endpoint test successful")
        print(f"Response time: {(end_time - start_time).total_seconds():.2f}s")
        print(f"Data sample: {str(station_response)[:200]}...")
    except UnexpectedStatus as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    # Test alerts endpoint
    print("\nTesting alerts endpoint...")
    try:
        start_time = datetime.now()
        alerts_response = await alerts_active.asyncio(client=client)
        end_time = datetime.now()

        print(f"Alerts endpoint test successful")
        print(f"Response time: {(end_time - start_time).total_seconds():.2f}s")
        print(f"Data sample: {str(alerts_response)[:200]}...")
    except UnexpectedStatus as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def main():
    """Main function."""
    asyncio.run(test_client())
    return 0


if __name__ == "__main__":
    sys.exit(main())
