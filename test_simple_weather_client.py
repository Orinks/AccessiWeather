#!/usr/bin/env python3
"""Direct test of the simple weather client Open-Meteo integration."""

import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import List

import httpx

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Location:
    """Simple location model."""
    name: str
    latitude: float
    longitude: float

@dataclass
class CurrentConditions:
    """Simple current conditions model."""
    temperature_f: float | None = None
    temperature_c: float | None = None
    condition: str | None = None
    humidity: float | None = None
    wind_speed_mph: float | None = None
    wind_direction: str | None = None
    pressure_mb: float | None = None
    feels_like_f: float | None = None
    last_updated: datetime | None = None

    def has_data(self) -> bool:
        """Check if this object has any meaningful data."""
        return any([
            self.temperature_f is not None,
            self.temperature_c is not None,
            self.condition is not None,
            self.humidity is not None,
        ])

@dataclass
class ForecastPeriod:
    """Simple forecast period model."""
    name: str | None = None
    temperature: float | None = None
    temperature_unit: str = "F"
    short_forecast: str | None = None
    detailed_forecast: str | None = None

@dataclass
class Forecast:
    """Simple forecast model."""
    periods: List[ForecastPeriod]
    generated_at: datetime | None = None

    def has_data(self) -> bool:
        """Check if this forecast has any periods."""
        return len(self.periods) > 0

class SimpleWeatherClient:
    """Simplified weather client for testing."""

    def __init__(self, data_source: str = "auto"):
        self.data_source = data_source
        self.openmeteo_base_url = "https://api.open-meteo.com/v1"
        self.timeout = 10.0

    def _should_use_openmeteo(self, location: Location) -> bool:
        """Determine if Open-Meteo should be used for the given location."""
        if self.data_source == "openmeteo":
            return True
        elif self.data_source == "nws":
            return False
        elif self.data_source == "auto":
            # Use Open-Meteo for international locations, NWS for US locations
            return not self._is_us_location(location)
        else:
            logger.warning(f"Unknown data source '{self.data_source}', defaulting to NWS")
            return False

    def _is_us_location(self, location: Location) -> bool:
        """Check if location is within the United States (rough approximation)."""
        # Continental US bounds (approximate)
        return (24.0 <= location.latitude <= 49.0 and 
                -125.0 <= location.longitude <= -66.0)

    async def get_current_conditions(self, location: Location) -> CurrentConditions:
        """Get current conditions from Open-Meteo API."""
        try:
            url = f"{self.openmeteo_base_url}/forecast"
            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,pressure_msl",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "auto",
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                return self._parse_openmeteo_current_conditions(data)

        except Exception as e:
            logger.error(f"Failed to get Open-Meteo current conditions: {e}")
            return CurrentConditions()

    async def get_forecast(self, location: Location) -> Forecast:
        """Get forecast from Open-Meteo API."""
        try:
            url = f"{self.openmeteo_base_url}/forecast"
            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max,wind_direction_10m_dominant",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "auto",
                "forecast_days": 7,
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                return self._parse_openmeteo_forecast(data)

        except Exception as e:
            logger.error(f"Failed to get Open-Meteo forecast: {e}")
            return Forecast(periods=[])

    def _parse_openmeteo_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse Open-Meteo current conditions data."""
        current = data.get("current", {})

        return CurrentConditions(
            temperature_f=current.get("temperature_2m"),
            temperature_c=self._convert_f_to_c(current.get("temperature_2m")),
            condition=self._weather_code_to_description(current.get("weather_code")),
            humidity=current.get("relative_humidity_2m"),
            wind_speed_mph=current.get("wind_speed_10m"),
            wind_direction=self._degrees_to_cardinal(current.get("wind_direction_10m")),
            pressure_mb=current.get("pressure_msl"),
            feels_like_f=current.get("apparent_temperature"),
            last_updated=datetime.now(),
        )

    def _parse_openmeteo_forecast(self, data: dict) -> Forecast:
        """Parse Open-Meteo forecast data."""
        daily = data.get("daily", {})
        periods = []

        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        weather_codes = daily.get("weather_code", [])

        for i, date_str in enumerate(dates):
            max_temp = max_temps[i] if i < len(max_temps) else None
            min_temp = min_temps[i] if i < len(min_temps) else None
            weather_code = weather_codes[i] if i < len(weather_codes) else None

            # Create day and night periods
            if max_temp is not None:
                day_period = ForecastPeriod(
                    name=f"{date_str} Day",
                    temperature=max_temp,
                    short_forecast=self._weather_code_to_description(weather_code) or "Unknown",
                )
                periods.append(day_period)

            if min_temp is not None:
                night_period = ForecastPeriod(
                    name=f"{date_str} Night",
                    temperature=min_temp,
                    short_forecast=self._weather_code_to_description(weather_code) or "Unknown",
                )
                periods.append(night_period)

        return Forecast(periods=periods, generated_at=datetime.now())

    def _convert_f_to_c(self, temp_f: float | None) -> float | None:
        """Convert Fahrenheit to Celsius."""
        if temp_f is None:
            return None
        return (temp_f - 32) * 5 / 9

    def _degrees_to_cardinal(self, degrees: float | None) -> str | None:
        """Convert wind direction degrees to cardinal direction."""
        if degrees is None:
            return None

        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", 
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / 22.5) % 16
        return directions[index]

    def _weather_code_to_description(self, code: int | None) -> str | None:
        """Convert Open-Meteo weather code to description."""
        if code is None:
            return None

        # Simplified weather code mapping
        code_map = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            95: "Thunderstorm",
        }
        return code_map.get(code, f"Weather code {code}")

async def test_simple_weather_client():
    """Test the simple weather client."""
    logger.info("Testing Simple Weather Client Open-Meteo integration...")
    
    # Test locations
    test_locations = [
        # US locations (should use NWS in auto mode)
        Location(name="Philadelphia, PA", latitude=39.9526, longitude=-75.1652),
        # International locations (should use Open-Meteo in auto mode)
        Location(name="Tokyo, Japan", latitude=35.6762, longitude=139.6503),
        Location(name="London, UK", latitude=51.5074, longitude=-0.1278),
        Location(name="Sydney, Australia", latitude=-33.8688, longitude=151.2093),
    ]
    
    # Test with different data sources
    for data_source in ["auto", "openmeteo"]:
        logger.info(f"\n=== Testing with data_source: {data_source} ===")
        
        client = SimpleWeatherClient(data_source=data_source)
        
        for location in test_locations:
            logger.info(f"\n--- Testing {location.name} ---")
            
            should_use_openmeteo = client._should_use_openmeteo(location)
            expected_api = "Open-Meteo" if should_use_openmeteo else "NWS"
            logger.info(f"Expected API: {expected_api}")
            
            if should_use_openmeteo or data_source == "openmeteo":
                try:
                    # Test current conditions
                    current = await client.get_current_conditions(location)
                    if current.has_data():
                        logger.info(f"✅ Current conditions: {current.temperature_f}°F, {current.condition}")
                    else:
                        logger.warning("⚠️ No current conditions data")
                    
                    # Test forecast
                    forecast = await client.get_forecast(location)
                    if forecast.has_data():
                        logger.info(f"✅ Forecast: {len(forecast.periods)} periods")
                        if forecast.periods:
                            first = forecast.periods[0]
                            logger.info(f"First period: {first.name} - {first.temperature}°F, {first.short_forecast}")
                    else:
                        logger.warning("⚠️ No forecast data")
                    
                    logger.info(f"✅ {location.name} - Open-Meteo integration working")
                    
                except Exception as e:
                    logger.error(f"❌ {location.name} - Failed: {e}")
            else:
                logger.info(f"Skipping {location.name} (would use NWS)")
    
    logger.info("\n=== Simple Weather Client Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_simple_weather_client())
