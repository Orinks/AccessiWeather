#!/usr/bin/env python
"""
Example of integrating the NWS API client with the AccessiWeather application.

This script demonstrates how to:
1. Initialize the NWS API client
2. Create a wrapper class that integrates with the existing WeatherService
3. Implement caching and rate limiting
4. Handle errors gracefully
"""

import asyncio
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from weather_gov_api_client.api.default import (
    alerts_active,
    alerts_active_zone,
    obs_station,
    point,
    station_observation_latest,
)
from weather_gov_api_client.client import Client
from weather_gov_api_client.errors import UnexpectedStatus
from weather_gov_api_client.models.alert_collection_geo_json import AlertCollectionGeoJson
from weather_gov_api_client.models.observation_geo_json import ObservationGeoJson
from weather_gov_api_client.models.observation_station_geo_json import ObservationStationGeoJson
from weather_gov_api_client.models.point_geo_json import PointGeoJson


class NWSWeatherService:
    """A wrapper class for the NWS API client that integrates with AccessiWeather."""

    def __init__(self, app_name: str, app_version: str, app_url: str, contact_email: str):
        """Initialize the NWS API client.

        Args:
            app_name: The name of the application
            app_version: The version of the application
            app_url: The URL of the application
            contact_email: The contact email for the application
        """
        self.client = Client(
            base_url="https://api.weather.gov",
            headers={"User-Agent": f"{app_name}/{app_version} ({app_url}; {contact_email})"},
        )
        self.last_request_time = datetime.now() - timedelta(seconds=10)
        self.min_request_interval = 0.5  # seconds

    def _rate_limit(self):
        """Implement rate limiting to avoid overwhelming the API."""
        now = datetime.now()
        elapsed = (now - self.last_request_time).total_seconds()

        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)

        self.last_request_time = datetime.now()

    @lru_cache(maxsize=128)
    async def get_point_metadata(self, latitude: float, longitude: float) -> Optional[PointGeoJson]:
        """Get metadata for a specific latitude/longitude point.

        Args:
            latitude: The latitude of the point
            longitude: The longitude of the point

        Returns:
            The point metadata or None if an error occurred
        """
        self._rate_limit()
        try:
            point_str = f"{latitude},{longitude}"
            return await point.asyncio(point=point_str, client=self.client)
        except UnexpectedStatus as e:
            print(f"Error getting point metadata: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error getting point metadata: {e}")
            return None

    @lru_cache(maxsize=128)
    async def get_nearest_stations(
        self, latitude: float, longitude: float
    ) -> List[ObservationStationGeoJson]:
        """Get the nearest observation stations to a point.

        Args:
            latitude: The latitude of the point
            longitude: The longitude of the point

        Returns:
            A list of observation stations
        """
        self._rate_limit()
        try:
            point_metadata = await self.get_point_metadata(latitude, longitude)
            if not point_metadata:
                return []

            # Access observation_stations from additional_properties
            observation_stations = point_metadata.properties.additional_properties.get(
                "observation_stations", []
            )
            if not observation_stations:
                return []

            stations = []
            for station_url in observation_stations[:5]:  # Limit to 5 stations
                station_id = station_url.split("/")[-1]
                self._rate_limit()
                station = await obs_station.asyncio(station_id=station_id, client=self.client)
                if station:
                    stations.append(station)

            return stations
        except Exception as e:
            print(f"Error getting nearest stations: {e}")
            return []

    @lru_cache(maxsize=128)
    async def get_current_conditions(
        self, latitude: float, longitude: float
    ) -> Optional[ObservationGeoJson]:
        """Get the current weather conditions for a location.

        Args:
            latitude: The latitude of the point
            longitude: The longitude of the point

        Returns:
            The current weather conditions or None if an error occurred
        """
        self._rate_limit()
        try:
            stations = await self.get_nearest_stations(latitude, longitude)
            if not stations:
                return None

            # Use the first station
            # Access station_identifier from additional_properties
            station_id = stations[0].properties.additional_properties.get("station_identifier")
            if not station_id:
                return None
            self._rate_limit()
            return await station_observation_latest.asyncio(
                station_id=station_id, client=self.client
            )
        except Exception as e:
            print(f"Error getting current conditions: {e}")
            return None

    @lru_cache(maxsize=128)
    async def get_alerts(
        self, latitude: float, longitude: float
    ) -> Optional[AlertCollectionGeoJson]:
        """Get active weather alerts for a location.

        Args:
            latitude: The latitude of the point
            longitude: The longitude of the point

        Returns:
            The active alerts or None if an error occurred
        """
        self._rate_limit()
        try:
            point_metadata = await self.get_point_metadata(latitude, longitude)
            if not point_metadata:
                return None

            # Try to get county or zone information from additional_properties
            county = point_metadata.properties.additional_properties.get("county", None)
            if not county:
                # Try alternative property names
                county = point_metadata.properties.additional_properties.get("countyZone", None)
                if not county:
                    # If we can't find a county, try to use the forecast zone
                    county = point_metadata.properties.additional_properties.get(
                        "forecastZone", None
                    )
                    if not county:
                        # Fall back to getting all active alerts
                        self._rate_limit()
                        return await alerts_active.asyncio(client=self.client)

            # Extract the zone ID from the county URL
            zone_id = county.split("/")[-1]
            self._rate_limit()
            return await alerts_active_zone.asyncio(zone_id=zone_id, client=self.client)
        except Exception as e:
            print(f"Error getting alerts: {e}")
            # Fall back to getting all active alerts
            try:
                self._rate_limit()
                return await alerts_active.asyncio(client=self.client)
            except Exception as e2:
                print(f"Error getting all alerts: {e2}")
                return None


async def demo():
    """Demonstrate the NWS Weather Service wrapper."""
    # Initialize the service
    service = NWSWeatherService(
        app_name="AccessiWeather",
        app_version="0.9.2",
        app_url="github.com/Orinks/AccessiWeather",
        contact_email="orin8722@gmail.com",
    )

    # Example coordinates (New York City)
    latitude = 40.7128
    longitude = -74.0060

    # Get point metadata
    print("\nGetting point metadata...")
    metadata = await service.get_point_metadata(latitude, longitude)
    if metadata:
        print(f"Raw metadata properties: {dir(metadata.properties)}")
        print(f"Additional properties: {metadata.properties.additional_properties}")

        # Access properties safely with getattr or from additional_properties
        forecast_office = metadata.properties.additional_properties.get("cwa", "Unknown")
        grid_x = metadata.properties.additional_properties.get("gridX", "Unknown")
        grid_y = metadata.properties.additional_properties.get("gridY", "Unknown")

        print(f"Forecast Office: {forecast_office}")
        print(f"Grid: {grid_x}, {grid_y}")

    # Get current conditions
    print("\nGetting current conditions...")
    conditions = await service.get_current_conditions(latitude, longitude)
    if conditions:
        print(f"Raw conditions properties: {dir(conditions.properties)}")
        print(f"Additional properties: {conditions.properties.additional_properties}")

        # Access properties from additional_properties
        temp = conditions.properties.additional_properties.get("temperature", {})
        if temp:
            print(f"Temperature: {temp.get('value', 'Unknown')}°C")

        desc = conditions.properties.additional_properties.get("textDescription", "Unknown")
        print(f"Weather: {desc}")

        wind = conditions.properties.additional_properties.get("windSpeed", {})
        if wind:
            print(f"Wind: {wind.get('value', 'Unknown')} {wind.get('unitCode', '')}")

        humidity = conditions.properties.additional_properties.get("relativeHumidity", {})
        if humidity:
            print(f"Humidity: {humidity.get('value', 'Unknown')}%")

    # Get alerts
    print("\nGetting alerts...")
    alerts = await service.get_alerts(latitude, longitude)
    if alerts and alerts.features:
        print(f"Found {len(alerts.features)} alerts:")
        for alert in alerts.features:
            if hasattr(alert, "properties"):
                print(f"Alert additional properties: {alert.properties.additional_properties}")
                event = alert.properties.additional_properties.get("event", "Unknown Event")
                headline = alert.properties.additional_properties.get(
                    "headline", "No headline available"
                )
                print(f"- {event}: {headline}")
    else:
        print("No active alerts")


if __name__ == "__main__":
    asyncio.run(demo())
