"""
Visual Crossing Weather API client for AccessiWeather.

This module provides a client for the Visual Crossing Weather API,
implementing methods to fetch current conditions, forecast, and hourly data.
"""

import logging
from datetime import UTC, datetime

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
from .utils.retry_utils import async_retry_with_backoff
from .utils.temperature_utils import TemperatureUnit, calculate_dewpoint
from .weather_client_parsers import describe_moon_phase

logger = logging.getLogger(__name__)


class VisualCrossingApiError(Exception):
    """Exception raised for Visual Crossing API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize the instance."""
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class VisualCrossingClient:
    """Client for Visual Crossing Weather API."""

    def __init__(self, api_key: str, user_agent: str = "AccessiWeather/1.0"):
        """Initialize the instance."""
        self.api_key = api_key
        self.user_agent = user_agent
        self.base_url = (
            "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        )
        self.timeout = 15.0

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
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
            raise VisualCrossingApiError("Request timed out") from None
        except httpx.RequestError as e:
            logger.error(f"Visual Crossing API request failed: {e}")
            raise VisualCrossingApiError(f"Request failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to get Visual Crossing current conditions: {e}")
            raise VisualCrossingApiError(f"Unexpected error: {e}") from e

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
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
            raise VisualCrossingApiError("Request timed out") from None
        except httpx.RequestError as e:
            logger.error(f"Visual Crossing API request failed: {e}")
            raise VisualCrossingApiError(f"Request failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to get Visual Crossing forecast: {e}")
            raise VisualCrossingApiError(f"Unexpected error: {e}") from e

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
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
            raise VisualCrossingApiError("Request timed out") from None
        except httpx.RequestError as e:
            logger.error(f"Visual Crossing API request failed: {e}")
            raise VisualCrossingApiError(f"Request failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to get Visual Crossing hourly forecast: {e}")
            raise VisualCrossingApiError(f"Unexpected error: {e}") from e

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
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
            raise VisualCrossingApiError("Request timed out") from None
        except httpx.RequestError as e:
            logger.error(f"Visual Crossing API request failed: {e}")
            raise VisualCrossingApiError(f"Request failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to get Visual Crossing alerts: {e}")
            # Return empty alerts on error rather than raising
            return WeatherAlerts(alerts=[])

    def _parse_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse Visual Crossing current conditions data."""
        current = data.get("currentConditions", {})

        temp_f = current.get("temp")
        temp_c = self._convert_f_to_c(temp_f)

        humidity = current.get("humidity")
        humidity = round(humidity) if humidity is not None else None

        dewpoint_f = current.get("dew")
        dewpoint_c = self._convert_f_to_c(dewpoint_f) if dewpoint_f is not None else None
        if dewpoint_f is None and temp_f is not None and humidity is not None:
            dewpoint_f = calculate_dewpoint(temp_f, humidity, unit=TemperatureUnit.FAHRENHEIT)
            if dewpoint_f is not None:
                dewpoint_c = self._convert_f_to_c(dewpoint_f)

        wind_speed_mph = current.get("windspeed")
        wind_speed_kph = wind_speed_mph * 1.60934 if wind_speed_mph is not None else None

        wind_direction = current.get("winddir")

        pressure_in = current.get("pressure")
        pressure_mb = pressure_in * 33.8639 if pressure_in is not None else None

        visibility_miles = current.get("visibility")
        visibility_km = visibility_miles * 1.60934 if visibility_miles is not None else None

        feels_like_f = current.get("feelslike")
        feels_like_c = self._convert_f_to_c(feels_like_f)

        timestamp = current.get("datetimeEpoch")
        last_updated = None
        if timestamp is not None:
            try:
                last_updated = datetime.fromtimestamp(timestamp, tz=UTC)
            except (OSError, ValueError):
                logger.debug(f"Failed to parse Visual Crossing epoch: {timestamp}")
        elif current.get("datetime"):
            try:
                last_updated = datetime.fromisoformat(current["datetime"])
            except ValueError:
                logger.debug(f"Failed to parse Visual Crossing datetime: {current['datetime']}")

        sunrise_time = None
        sunset_time = None
        moonrise_time = None
        moonset_time = None
        moon_phase = None
        days = data.get("days", [])
        if days:
            day_data = days[0]

            sunrise_epoch = day_data.get("sunriseEpoch")
            if sunrise_epoch is not None:
                try:
                    sunrise_time = datetime.fromtimestamp(sunrise_epoch, tz=UTC)
                except (OSError, ValueError):
                    logger.debug(f"Failed to parse sunrise epoch: {sunrise_epoch}")
            if sunrise_time is None and day_data.get("sunrise"):
                try:
                    sunrise_time = datetime.fromisoformat(day_data["sunrise"])
                except ValueError:
                    logger.debug(f"Failed to parse sunrise time: {day_data['sunrise']}")

            sunset_epoch = day_data.get("sunsetEpoch")
            if sunset_epoch is not None:
                try:
                    sunset_time = datetime.fromtimestamp(sunset_epoch, tz=UTC)
                except (OSError, ValueError):
                    logger.debug(f"Failed to parse sunset epoch: {sunset_epoch}")
            if sunset_time is None and day_data.get("sunset"):
                try:
                    sunset_time = datetime.fromisoformat(day_data["sunset"])
                except ValueError:
                    logger.debug(f"Failed to parse sunset time: {day_data['sunset']}")

            moonrise_epoch = day_data.get("moonriseEpoch")
            if moonrise_epoch is not None:
                try:
                    moonrise_time = datetime.fromtimestamp(moonrise_epoch, tz=UTC)
                except (OSError, ValueError):
                    logger.debug(f"Failed to parse moonrise epoch: {moonrise_epoch}")
            if moonrise_time is None and day_data.get("moonrise"):
                try:
                    moonrise_time = datetime.fromisoformat(day_data["moonrise"])
                except ValueError:
                    logger.debug(f"Failed to parse moonrise time: {day_data['moonrise']}")

            moonset_epoch = day_data.get("moonsetEpoch")
            if moonset_epoch is not None:
                try:
                    moonset_time = datetime.fromtimestamp(moonset_epoch, tz=UTC)
                except (OSError, ValueError):
                    logger.debug(f"Failed to parse moonset epoch: {moonset_epoch}")
            if moonset_time is None and day_data.get("moonset"):
                try:
                    moonset_time = datetime.fromisoformat(day_data["moonset"])
                except ValueError:
                    logger.debug(f"Failed to parse moonset time: {day_data['moonset']}")

            moon_phase = describe_moon_phase(day_data.get("moonphase"))

        return CurrentConditions(
            temperature_f=temp_f,
            temperature_c=temp_c,
            condition=current.get("conditions"),
            humidity=humidity,
            dewpoint_f=dewpoint_f,
            dewpoint_c=dewpoint_c,
            wind_speed_mph=wind_speed_mph,
            wind_speed_kph=wind_speed_kph,
            wind_direction=wind_direction,
            pressure_in=pressure_in,
            pressure_mb=pressure_mb,
            feels_like_f=feels_like_f,
            feels_like_c=feels_like_c,
            visibility_miles=visibility_miles,
            visibility_km=visibility_km,
            sunrise_time=sunrise_time,
            sunset_time=sunset_time,
            moon_phase=moon_phase,
            moonrise_time=moonrise_time,
            moonset_time=moonset_time,
            last_updated=last_updated or datetime.now(),
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

        # Visual Crossing may return alerts in different structures
        # Check multiple possible locations for alert data
        alert_data_list = []

        # Check top-level alerts
        if "alerts" in data:
            alert_data_list.extend(data["alerts"])

        # Check if alerts are nested in days
        if "days" in data:
            for day in data["days"]:
                if "alerts" in day:
                    alert_data_list.extend(day["alerts"])

        # Check current conditions for alerts
        if "currentConditions" in data and "alerts" in data["currentConditions"]:
            alert_data_list.extend(data["currentConditions"]["alerts"])

        logger.debug(f"Found {len(alert_data_list)} alert(s) in Visual Crossing response")

        for i, alert_data in enumerate(alert_data_list):
            logger.debug(f"Processing alert {i + 1}: {alert_data}")

            # Extract alert information with fallbacks
            event = alert_data.get("event") or alert_data.get("type") or "Weather Alert"
            headline = (
                alert_data.get("headline")
                or alert_data.get("title")
                or alert_data.get("description", "")[:100]
            )
            description = alert_data.get("description") or alert_data.get("details") or headline

            # Map Visual Crossing severity to standard levels
            severity = self._map_visual_crossing_severity(alert_data.get("severity"))

            # Generate a unique ID for the alert
            alert_id = alert_data.get("id") or f"vc-{hash(f'{event}-{headline}')}"

            # Parse time fields
            onset = self._parse_alert_time(alert_data.get("onset") or alert_data.get("start"))
            expires = self._parse_alert_time(alert_data.get("expires") or alert_data.get("end"))

            # Extract affected areas
            areas = []
            if "areas" in alert_data:
                if isinstance(alert_data["areas"], list):
                    areas = alert_data["areas"]
                elif isinstance(alert_data["areas"], str):
                    areas = [alert_data["areas"]]
            elif "area" in alert_data:
                areas = [alert_data["area"]]

            alert = WeatherAlert(
                id=alert_id,
                title=headline,
                description=description,
                severity=severity,
                urgency=alert_data.get("urgency", "Unknown"),
                certainty=alert_data.get("certainty", "Possible"),
                event=event,
                headline=headline,
                instruction=alert_data.get("instruction") or alert_data.get("response"),
                areas=areas,
                onset=onset,
                expires=expires,
            )

            logger.debug(f"Created alert: {alert.event} - {alert.severity} - {alert.headline}")
            alerts.append(alert)

        logger.info(f"Parsed {len(alerts)} Visual Crossing alerts")
        return WeatherAlerts(alerts=alerts)

    def _map_visual_crossing_severity(self, vc_severity: str | None) -> str:
        """Map Visual Crossing severity to standard severity levels."""
        if not vc_severity:
            return "Unknown"

        vc_severity = vc_severity.lower()

        # Map Visual Crossing severity levels to standard ones
        severity_map = {
            "extreme": "Extreme",
            "severe": "Severe",
            "moderate": "Moderate",
            "minor": "Minor",
            "unknown": "Unknown",
            # Additional mappings for Visual Crossing specific terms
            "high": "Severe",
            "medium": "Moderate",
            "low": "Minor",
            "critical": "Extreme",
            "warning": "Severe",
            "watch": "Moderate",
            "advisory": "Minor",
        }

        return severity_map.get(vc_severity, "Unknown")

    def _parse_alert_time(self, time_str: str | None) -> datetime | None:
        """Parse Visual Crossing alert time string."""
        if not time_str:
            return None

        try:
            # Visual Crossing typically uses ISO format
            from dateutil.parser import parse

            return parse(time_str)
        except Exception as e:
            logger.warning(f"Failed to parse alert time '{time_str}': {e}")
            return None

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
