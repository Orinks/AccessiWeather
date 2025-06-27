"""Simplified weather API client for AccessiWeather.

This module provides a direct, async weather API client that fetches data
from NWS and OpenMeteo APIs without complex service layer abstractions.
"""

import logging
from datetime import datetime

import httpx

from .models import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)

logger = logging.getLogger(__name__)


class WeatherClient:
    """Simple async weather API client."""

    def __init__(self, user_agent: str = "AccessiWeather/1.0"):
        self.user_agent = user_agent
        self.nws_base_url = "https://api.weather.gov"
        self.openmeteo_base_url = "https://api.open-meteo.com/v1"
        self.timeout = 10.0

    async def get_weather_data(self, location: Location) -> WeatherData:
        """Get complete weather data for a location."""
        logger.info(f"Fetching weather data for {location.name}")

        # Try NWS first for US locations, then fallback to OpenMeteo
        weather_data = WeatherData(location=location, last_updated=datetime.now())

        try:
            # Try NWS API first
            current = await self._get_nws_current_conditions(location)
            forecast, discussion = await self._get_nws_forecast_and_discussion(location)
            alerts = await self._get_nws_alerts(location)

            weather_data.current = current
            weather_data.forecast = forecast
            weather_data.discussion = discussion
            weather_data.alerts = alerts

            logger.info(f"Successfully fetched NWS data for {location.name}")

        except Exception as e:
            logger.warning(f"NWS API failed for {location.name}: {e}")

            try:
                # Fallback to OpenMeteo
                current = await self._get_openmeteo_current_conditions(location)
                forecast = await self._get_openmeteo_forecast(location)

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.discussion = "Forecast discussion not available from OpenMeteo."
                weather_data.alerts = WeatherAlerts(alerts=[])  # OpenMeteo doesn't provide alerts

                logger.info(f"Successfully fetched OpenMeteo data for {location.name}")

            except Exception as e2:
                logger.error(f"Both APIs failed for {location.name}: NWS={e}, OpenMeteo={e2}")
                # Return empty weather data
                weather_data.current = CurrentConditions()
                weather_data.forecast = Forecast(periods=[])
                weather_data.discussion = "Forecast discussion not available."
                weather_data.alerts = WeatherAlerts(alerts=[])

        return weather_data

    async def _get_nws_current_conditions(self, location: Location) -> CurrentConditions | None:
        """Get current conditions from NWS API."""
        try:
            # Get grid point for location
            grid_url = f"{self.nws_base_url}/points/{location.latitude},{location.longitude}"

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}

                # Get grid point
                response = await client.get(grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

                # Get observation stations
                stations_url = grid_data["properties"]["observationStations"]
                response = await client.get(stations_url, headers=headers)
                response.raise_for_status()
                stations_data = response.json()

                if not stations_data["features"]:
                    logger.warning("No observation stations found")
                    return None

                # Get latest observation from first station
                station_id = stations_data["features"][0]["properties"]["stationIdentifier"]
                obs_url = f"{self.nws_base_url}/stations/{station_id}/observations/latest"

                response = await client.get(obs_url, headers=headers)
                response.raise_for_status()
                obs_data = response.json()

                return self._parse_nws_current_conditions(obs_data)

        except Exception as e:
            logger.error(f"Failed to get NWS current conditions: {e}")
            return None

    async def _get_nws_forecast_and_discussion(
        self, location: Location
    ) -> (Forecast | None, str | None):
        """Get forecast and discussion from NWS API."""
        try:
            # Get grid point for location
            grid_url = f"{self.nws_base_url}/points/{location.latitude},{location.longitude}"

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}

                # Get grid point
                response = await client.get(grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

                # Get forecast
                forecast_url = grid_data["properties"]["forecast"]
                response = await client.get(forecast_url, headers=headers)
                response.raise_for_status()
                forecast_data = response.json()

                # Get forecast discussion (AFD)
                discussion = await self._get_nws_discussion(client, headers, grid_data)

                return self._parse_nws_forecast(forecast_data), discussion

        except Exception as e:
            logger.error(f"Failed to get NWS forecast and discussion: {e}")
            return None, None

    async def _get_nws_discussion(self, client, headers, grid_data) -> str:
        """Get NWS Area Forecast Discussion (AFD) for the location."""
        try:
            # Get forecast URL to extract office ID
            forecast_url = grid_data.get("properties", {}).get("forecast")
            if not forecast_url:
                logger.warning("No forecast URL found in grid data")
                return "Forecast discussion not available."

            # Extract office ID from forecast URL
            # URL format: https://api.weather.gov/gridpoints/PHI/49,75/forecast
            parts = forecast_url.split("/")
            if len(parts) < 6:
                logger.warning(f"Unexpected forecast URL format: {forecast_url}")
                return "Forecast discussion not available."

            office_id = parts[-3]  # Extract office ID (e.g., "PHI")
            logger.info(f"Fetching AFD for office: {office_id}")

            # Get AFD products for this office
            products_url = f"{self.nws_base_url}/products/types/AFD/locations/{office_id}"
            response = await client.get(products_url, headers=headers)

            if response.status_code != 200:
                logger.warning(f"Failed to get AFD products: HTTP {response.status_code}")
                return "Forecast discussion not available."

            products_data = response.json()

            # Check if we have any AFD products
            if not products_data.get("@graph") or not products_data["@graph"]:
                logger.warning(f"No AFD products found for office {office_id}")
                return "Forecast discussion not available for this location."

            # Get the latest AFD product
            latest_product = products_data["@graph"][0]
            latest_product_id = latest_product.get("id")

            if not latest_product_id:
                logger.warning("No product ID found in latest AFD product")
                return "Forecast discussion not available."

            # Fetch the actual AFD text
            product_url = f"{self.nws_base_url}/products/{latest_product_id}"
            response = await client.get(product_url, headers=headers)

            if response.status_code != 200:
                logger.warning(f"Failed to get AFD product text: HTTP {response.status_code}")
                return "Forecast discussion not available."

            product_data = response.json()
            product_text = product_data.get("productText")

            if not product_text:
                logger.warning("No product text found in AFD product")
                return "Forecast discussion not available."

            logger.info(f"Successfully fetched AFD for office {office_id}")
            return product_text

        except Exception as e:
            logger.error(f"Failed to get NWS discussion: {e}")
            return "Forecast discussion not available due to error."

    async def _get_nws_alerts(self, location: Location) -> WeatherAlerts | None:
        """Get weather alerts from NWS API."""
        try:
            alerts_url = f"{self.nws_base_url}/alerts/active"
            params = {
                "point": f"{location.latitude},{location.longitude}",
                "status": "actual",
                "message_type": "alert",
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(alerts_url, params=params, headers=headers)
                response.raise_for_status()
                alerts_data = response.json()

                return self._parse_nws_alerts(alerts_data)

        except Exception as e:
            logger.error(f"Failed to get NWS alerts: {e}")
            return WeatherAlerts(alerts=[])

    async def _get_openmeteo_current_conditions(
        self, location: Location
    ) -> CurrentConditions | None:
        """Get current conditions from OpenMeteo API."""
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
            logger.error(f"Failed to get OpenMeteo current conditions: {e}")
            return None

    async def _get_openmeteo_forecast(self, location: Location) -> Forecast | None:
        """Get forecast from OpenMeteo API."""
        try:
            url = f"{self.openmeteo_base_url}/forecast"
            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max,wind_direction_10m_dominant",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
                "forecast_days": 7,
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                return self._parse_openmeteo_forecast(data)

        except Exception as e:
            logger.error(f"Failed to get OpenMeteo forecast: {e}")
            return None

    def _parse_nws_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse NWS current conditions data."""
        props = data.get("properties", {})

        # Convert Celsius to Fahrenheit if needed
        temp_c = props.get("temperature", {}).get("value")
        temp_f = None
        if temp_c is not None:
            temp_f = (temp_c * 9 / 5) + 32

        return CurrentConditions(
            temperature_f=temp_f,
            temperature_c=temp_c,
            condition=props.get("textDescription"),
            humidity=props.get("relativeHumidity", {}).get("value"),
            wind_speed_mph=self._convert_mps_to_mph(props.get("windSpeed", {}).get("value")),
            wind_direction=props.get("windDirection", {}).get("value"),
            pressure_in=self._convert_pa_to_inches(
                props.get("barometricPressure", {}).get("value")
            ),
            last_updated=datetime.now(),
        )

    def _parse_nws_forecast(self, data: dict) -> Forecast:
        """Parse NWS forecast data."""
        periods = []

        for period_data in data.get("properties", {}).get("periods", []):
            period = ForecastPeriod(
                name=period_data.get("name", ""),
                temperature=period_data.get("temperature"),
                temperature_unit=period_data.get("temperatureUnit", "F"),
                short_forecast=period_data.get("shortForecast"),
                detailed_forecast=period_data.get("detailedForecast"),
                wind_speed=period_data.get("windSpeed"),
                wind_direction=period_data.get("windDirection"),
                icon=period_data.get("icon"),
            )
            periods.append(period)

        return Forecast(periods=periods, generated_at=datetime.now())

    def _parse_nws_alerts(self, data: dict) -> WeatherAlerts:
        """Parse NWS alerts data."""
        alerts = []

        for alert_data in data.get("features", []):
            props = alert_data.get("properties", {})
            alert = WeatherAlert(
                title=props.get("headline", "Weather Alert"),
                description=props.get("description", ""),
                severity=props.get("severity", "Unknown"),
                urgency=props.get("urgency", "Unknown"),
                certainty=props.get("certainty", "Unknown"),
                event=props.get("event"),
                headline=props.get("headline"),
                instruction=props.get("instruction"),
                areas=props.get("areaDesc", "").split("; ") if props.get("areaDesc") else [],
            )
            alerts.append(alert)

        return WeatherAlerts(alerts=alerts)

    def _parse_openmeteo_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse OpenMeteo current conditions data."""
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
        """Parse OpenMeteo forecast data."""
        daily = data.get("daily", {})
        periods = []

        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        weather_codes = daily.get("weather_code", [])

        for i, date in enumerate(dates):
            if i < len(max_temps) and i < len(weather_codes):
                period = ForecastPeriod(
                    name=self._format_date_name(date, i),
                    temperature=max_temps[i],
                    temperature_unit="F",
                    short_forecast=self._weather_code_to_description(weather_codes[i]),
                )
                periods.append(period)

        return Forecast(periods=periods, generated_at=datetime.now())

    # Utility methods
    def _convert_mps_to_mph(self, mps: float | None) -> float | None:
        """Convert meters per second to miles per hour."""
        return mps * 2.237 if mps is not None else None

    def _convert_pa_to_inches(self, pa: float | None) -> float | None:
        """Convert pascals to inches of mercury."""
        return pa * 0.0002953 if pa is not None else None

    def _convert_f_to_c(self, fahrenheit: float | None) -> float | None:
        """Convert Fahrenheit to Celsius."""
        return (fahrenheit - 32) * 5 / 9 if fahrenheit is not None else None

    def _degrees_to_cardinal(self, degrees: float | None) -> str | None:
        """Convert wind direction degrees to cardinal direction."""
        if degrees is None:
            return None

        directions = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
        index = round(degrees / 22.5) % 16
        return directions[index]

    def _weather_code_to_description(self, code: int | None) -> str | None:
        """Convert OpenMeteo weather code to description."""
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

    def _format_date_name(self, date_str: str, index: int) -> str:
        """Format date string to readable name."""
        if index == 0:
            return "Today"
        if index == 1:
            return "Tomorrow"
        # Parse date and format as day name
        try:
            date_obj = datetime.fromisoformat(date_str)
            return date_obj.strftime("%A")
        except:
            return f"Day {index + 1}"
