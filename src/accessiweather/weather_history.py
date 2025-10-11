"""
Weather history comparison functionality using Open-Meteo archive API.

This module provides functionality to compare current weather conditions with
historical data from Open-Meteo's archive endpoint. No local storage required.
Designed with accessibility in mind for screen reader users.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CurrentConditions, Location

logger = logging.getLogger(__name__)


@dataclass
class HistoricalWeatherData:
    """Historical weather data for a specific date."""

    date: date
    temperature_max: float
    temperature_min: float
    temperature_mean: float
    condition: str
    humidity: int | None
    wind_speed: float
    wind_direction: int | None
    pressure: float | None


@dataclass
class WeatherComparison:
    """Comparison between current weather and historical data."""

    temperature_difference: float
    temperature_description: str
    condition_changed: bool
    previous_condition: str
    condition_description: str | None
    days_ago: int

    @classmethod
    def compare(
        cls,
        current: CurrentConditions,
        historical: HistoricalWeatherData,
        days_ago: int,
    ) -> WeatherComparison:
        """
        Compare current conditions with historical data.

        Args:
            current: Current weather conditions
            historical: Historical weather data
            days_ago: Number of days in the past

        Returns:
            A WeatherComparison instance with comparison details

        """
        # Use mean temperature for comparison
        temp_diff = current.temperature - historical.temperature_mean

        # Generate temperature description
        if abs(temp_diff) < 1.0:
            temp_desc = "about the same temperature"
        elif temp_diff > 0:
            temp_desc = f"{abs(temp_diff):.1f} degrees warmer"
        else:
            temp_desc = f"{abs(temp_diff):.1f} degrees cooler"

        # Check condition change
        condition_changed = current.condition != historical.condition
        condition_desc = None
        if condition_changed:
            condition_desc = f"Changed from {historical.condition} to {current.condition}"

        return cls(
            temperature_difference=temp_diff,
            temperature_description=temp_desc,
            condition_changed=condition_changed,
            previous_condition=historical.condition,
            condition_description=condition_desc,
            days_ago=days_ago,
        )

    def get_accessible_summary(self) -> str:
        """
        Generate a screen-reader friendly summary of the comparison.

        Returns:
            A human-readable summary of weather changes

        """
        parts = []

        # Temperature summary
        if self.days_ago == 1:
            time_ref = "yesterday"
        elif self.days_ago == 7:
            time_ref = "last week"
        else:
            time_ref = f"{self.days_ago} days ago"

        parts.append(f"Compared to {time_ref}: {self.temperature_description}")

        # Condition summary
        if self.condition_changed and self.condition_description:
            parts.append(self.condition_description)

        return ". ".join(parts) + "."


class WeatherHistoryService:
    """Service for fetching historical weather data and making comparisons."""

    def __init__(self, openmeteo_client=None):
        """
        Initialize the weather history service.

        Args:
            openmeteo_client: Optional OpenMeteoApiClient instance. If not provided,
                            one will be created.

        """
        if openmeteo_client is None:
            from .openmeteo_client import OpenMeteoApiClient

            self.openmeteo_client = OpenMeteoApiClient(
                user_agent="AccessiWeather/2.0",
                timeout=30.0,
            )
        else:
            self.openmeteo_client = openmeteo_client

    def get_historical_weather(
        self,
        latitude: float,
        longitude: float,
        target_date: date,
        temperature_unit: str = "fahrenheit",
    ) -> HistoricalWeatherData | None:
        """
        Fetch historical weather data for a specific date.

        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
            target_date: Date to fetch historical data for
            temperature_unit: Temperature unit ("celsius" or "fahrenheit")

        Returns:
            HistoricalWeatherData if successful, None otherwise

        """
        try:
            # Use Open-Meteo archive endpoint for historical data
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": target_date.isoformat(),
                "end_date": target_date.isoformat(),
                "daily": [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "temperature_2m_mean",
                    "wind_speed_10m_max",
                    "wind_direction_10m_dominant",
                ],
                "temperature_unit": temperature_unit,
                "timezone": "auto",
            }

            # Call archive endpoint (different from forecast)
            response = self.openmeteo_client._make_request("archive", params)

            if not response or "daily" not in response:
                logger.warning(f"No historical data available for {target_date}")
                return None

            daily = response["daily"]

            # Extract data for the requested date
            if not daily.get("time") or len(daily["time"]) == 0:
                return None

            # Get weather description from code
            weather_code = daily.get("weather_code", [0])[0]
            condition = self.openmeteo_client.get_weather_description(weather_code)

            return HistoricalWeatherData(
                date=target_date,
                temperature_max=daily.get("temperature_2m_max", [0])[0],
                temperature_min=daily.get("temperature_2m_min", [0])[0],
                temperature_mean=daily.get("temperature_2m_mean", [0])[0],
                condition=condition,
                humidity=None,  # Not available in archive endpoint
                wind_speed=daily.get("wind_speed_10m_max", [0])[0],
                wind_direction=daily.get("wind_direction_10m_dominant", [None])[0],
                pressure=None,  # Not available in archive endpoint
            )

        except Exception as e:
            logger.error(f"Failed to fetch historical weather data: {e}")
            return None

    def compare_with_yesterday(
        self,
        location: Location,
        current_conditions: CurrentConditions,
        temperature_unit: str = "fahrenheit",
    ) -> WeatherComparison | None:
        """
        Compare current weather with yesterday's weather.

        Args:
            location: Location for the comparison
            current_conditions: Current weather conditions
            temperature_unit: Temperature unit for API request

        Returns:
            WeatherComparison if historical data is available, None otherwise

        """
        yesterday = (datetime.now() - timedelta(days=1)).date()
        historical = self.get_historical_weather(
            location.latitude, location.longitude, yesterday, temperature_unit
        )

        if historical is None:
            return None

        return WeatherComparison.compare(current_conditions, historical, days_ago=1)

    def compare_with_last_week(
        self,
        location: Location,
        current_conditions: CurrentConditions,
        temperature_unit: str = "fahrenheit",
    ) -> WeatherComparison | None:
        """
        Compare current weather with weather from one week ago.

        Args:
            location: Location for the comparison
            current_conditions: Current weather conditions
            temperature_unit: Temperature unit for API request

        Returns:
            WeatherComparison if historical data is available, None otherwise

        """
        last_week = (datetime.now() - timedelta(days=7)).date()
        historical = self.get_historical_weather(
            location.latitude, location.longitude, last_week, temperature_unit
        )

        if historical is None:
            return None

        return WeatherComparison.compare(current_conditions, historical, days_ago=7)

    def compare_with_date(
        self,
        location: Location,
        current_conditions: CurrentConditions,
        target_date: date,
        temperature_unit: str = "fahrenheit",
    ) -> WeatherComparison | None:
        """
        Compare current weather with weather from a specific date.

        Args:
            location: Location for the comparison
            current_conditions: Current weather conditions
            target_date: Date to compare with
            temperature_unit: Temperature unit for API request

        Returns:
            WeatherComparison if historical data is available, None otherwise

        """
        days_ago = (datetime.now().date() - target_date).days
        historical = self.get_historical_weather(
            location.latitude, location.longitude, target_date, temperature_unit
        )

        if historical is None:
            return None

        return WeatherComparison.compare(current_conditions, historical, days_ago=days_ago)
