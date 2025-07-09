"""Visual Crossing Weather API client for AccessiWeather.

This module provides a client for the Visual Crossing Weather API,
implementing methods to fetch current conditions, forecast, and hourly data.
"""

import logging
from datetime import datetime

import httpx

from .models import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    WeatherAlert,
    WeatherAlerts,
)

logger = logging.getLogger(__name__)


class VisualCrossingApiError(Exception):
    """Exception raised for Visual Crossing API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class VisualCrossingClient:
    """Client for Visual Crossing Weather API."""

    def __init__(self, api_key: str, user_agent: str = "AccessiWeather/1.0"):
        self.api_key = api_key
        self.user_agent = user_agent
        self.base_url = (
            "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        )
        self.timeout = 15.0

    async def get_current_conditions(self, location: Location) -> CurrentConditions | None:
        """Get current weather conditions from Visual Crossing API."""
        try:
            # Use current time for specific current conditions
            url = f"{self.base_url}/{location.latitude},{location.longitude}"
            params = {
                "key": self.api_key,
                "include": "current",
                "unitGroup": "us",  # Use US units (Fahrenheit, mph, inches)
                "elements": "temp,feelslike,humidity,windspeed,winddir,pressure,conditions,datetime",
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 401:
                    raise VisualCrossingApiError("Invalid API key", response.status_code)
                if response.status_code == 429:
                    raise VisualCrossingApiError("API rate limit exceeded", response.status_code)
                if response.status_code != 200:
                    raise VisualCrossingApiError(
                        f"API request failed: HTTP {response.status_code}", response.status_code
                    )

                data = response.json()
                return self._parse_current_conditions(data)

        except httpx.TimeoutException:
            logger.error("Visual Crossing API request timed out")
            raise VisualCrossingApiError("Request timed out")
        except httpx.RequestError as e:
            logger.error(f"Visual Crossing API request failed: {e}")
            raise VisualCrossingApiError(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Failed to get Visual Crossing current conditions: {e}")
            raise VisualCrossingApiError(f"Unexpected error: {e}")

    async def get_forecast(self, location: Location) -> Forecast | None:
        """Get weather forecast from Visual Crossing API."""
        try:
            url = f"{self.base_url}/{location.latitude},{location.longitude}"
            params = {
                "key": self.api_key,
                "include": "days",
                "unitGroup": "us",
                "elements": "datetime,tempmax,tempmin,temp,conditions,description,windspeed,winddir,icon",
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 401:
                    raise VisualCrossingApiError("Invalid API key", response.status_code)
                if response.status_code == 429:
                    raise VisualCrossingApiError("API rate limit exceeded", response.status_code)
                if response.status_code != 200:
                    raise VisualCrossingApiError(
                        f"API request failed: HTTP {response.status_code}", response.status_code
                    )

                data = response.json()
                return self._parse_forecast(data)

        except httpx.TimeoutException:
            logger.error("Visual Crossing API request timed out")
            raise VisualCrossingApiError("Request timed out")
        except httpx.RequestError as e:
            logger.error(f"Visual Crossing API request failed: {e}")
            raise VisualCrossingApiError(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Failed to get Visual Crossing forecast: {e}")
            raise VisualCrossingApiError(f"Unexpected error: {e}")

    async def get_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Get hourly weather forecast from Visual Crossing API."""
        try:
            url = f"{self.base_url}/{location.latitude},{location.longitude}"
            params = {
                "key": self.api_key,
                "include": "hours",
                "unitGroup": "us",
                "elements": "datetime,temp,conditions,windspeed,winddir,icon",
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 401:
                    raise VisualCrossingApiError("Invalid API key", response.status_code)
                if response.status_code == 429:
                    raise VisualCrossingApiError("API rate limit exceeded", response.status_code)
                if response.status_code != 200:
                    raise VisualCrossingApiError(
                        f"API request failed: HTTP {response.status_code}", response.status_code
                    )

                data = response.json()
                return self._parse_hourly_forecast(data)

        except httpx.TimeoutException:
            logger.error("Visual Crossing API request timed out")
            raise VisualCrossingApiError("Request timed out")
        except httpx.RequestError as e:
            logger.error(f"Visual Crossing API request failed: {e}")
            raise VisualCrossingApiError(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Failed to get Visual Crossing hourly forecast: {e}")
            raise VisualCrossingApiError(f"Unexpected error: {e}")

    async def get_alerts(self, location: Location) -> WeatherAlerts:
        """Get weather alerts from Visual Crossing API."""
        try:
            url = f"{self.base_url}/{location.latitude},{location.longitude}"
            params = {
                "key": self.api_key,
                "include": "alerts",
                "unitGroup": "us",
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 401:
                    raise VisualCrossingApiError("Invalid API key", response.status_code)
                if response.status_code == 429:
                    raise VisualCrossingApiError("API rate limit exceeded", response.status_code)
                if response.status_code != 200:
                    raise VisualCrossingApiError(
                        f"API request failed: HTTP {response.status_code}", response.status_code
                    )

                data = response.json()
                return self._parse_alerts(data)

        except httpx.TimeoutException:
            logger.error("Visual Crossing API request timed out")
            raise VisualCrossingApiError("Request timed out")
        except httpx.RequestError as e:
            logger.error(f"Visual Crossing API request failed: {e}")
            raise VisualCrossingApiError(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Failed to get Visual Crossing alerts: {e}")
            # Return empty alerts on error rather than raising
            return WeatherAlerts(alerts=[])

    def _parse_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse Visual Crossing current conditions data."""
        current = data.get("currentConditions", {})

        temp_f = current.get("temp")

        return CurrentConditions(
            temperature_f=temp_f,
            temperature_c=self._convert_f_to_c(temp_f),
            condition=current.get("conditions"),
            humidity=current.get("humidity"),
            wind_speed_mph=current.get("windspeed"),
            wind_direction=self._degrees_to_cardinal(current.get("winddir")),
            pressure_mb=current.get("pressure"),
            feels_like_f=current.get("feelslike"),
            feels_like_c=self._convert_f_to_c(current.get("feelslike")),
            last_updated=datetime.now(),
        )

    def _parse_forecast(self, data: dict) -> Forecast:
        """Parse Visual Crossing forecast data."""
        periods = []
        days = data.get("days", [])

        for i, day_data in enumerate(days):
            # Format period name
            date_str = day_data.get("datetime", "")
            if i == 0:
                name = "Today"
            elif i == 1:
                name = "Tomorrow"
            else:
                try:
                    date_obj = datetime.fromisoformat(date_str)
                    name = date_obj.strftime("%A")
                except (ValueError, TypeError):
                    name = f"Day {i + 1}"

            period = ForecastPeriod(
                name=name,
                temperature=day_data.get("tempmax"),  # Use max temp for daily forecast
                temperature_unit="F",
                short_forecast=day_data.get("conditions"),
                detailed_forecast=day_data.get("description"),
                wind_speed=f"{day_data.get('windspeed', 0)} mph"
                if day_data.get("windspeed")
                else None,
                wind_direction=self._degrees_to_cardinal(day_data.get("winddir")),
                icon=day_data.get("icon"),
            )
            periods.append(period)

        return Forecast(periods=periods, generated_at=datetime.now())

    def _parse_hourly_forecast(self, data: dict) -> HourlyForecast:
        """Parse Visual Crossing hourly forecast data."""
        periods = []
        days = data.get("days", [])

        # Extract hourly data from all days
        for day_data in days:
            hours = day_data.get("hours", [])
            for hour_data in hours:
                # Parse datetime
                datetime_str = hour_data.get("datetime")
                start_time = None
                if datetime_str:
                    try:
                        # Visual Crossing format: "HH:MM:SS"
                        date_str = day_data.get("datetime", "")
                        full_datetime_str = f"{date_str}T{datetime_str}"
                        start_time = datetime.fromisoformat(full_datetime_str)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Failed to parse Visual Crossing datetime: {full_datetime_str}"
                        )
                        start_time = datetime.now()

                period = HourlyForecastPeriod(
                    start_time=start_time or datetime.now(),
                    temperature=hour_data.get("temp"),
                    temperature_unit="F",
                    short_forecast=hour_data.get("conditions"),
                    wind_speed=f"{hour_data.get('windspeed', 0)} mph"
                    if hour_data.get("windspeed")
                    else None,
                    wind_direction=self._degrees_to_cardinal(hour_data.get("winddir")),
                    icon=hour_data.get("icon"),
                )
                periods.append(period)

        return HourlyForecast(periods=periods, generated_at=datetime.now())

    def _parse_alerts(self, data: dict) -> WeatherAlerts:
        """Parse Visual Crossing alerts data."""
        alerts = []
        alert_data_list = data.get("alerts", [])

        for alert_data in alert_data_list:
            alert = WeatherAlert(
                title=alert_data.get("headline", "Weather Alert"),
                description=alert_data.get("description", ""),
                severity=alert_data.get("severity", "Unknown"),
                urgency=alert_data.get("urgency", "Unknown"),
                certainty=alert_data.get("certainty", "Unknown"),
                event=alert_data.get("event"),
                headline=alert_data.get("headline"),
                instruction=alert_data.get("instruction"),
                areas=alert_data.get("areas", [])
                if isinstance(alert_data.get("areas"), list)
                else [],
            )
            alerts.append(alert)

        return WeatherAlerts(alerts=alerts)

    # Utility methods
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
