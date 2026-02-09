"""
Visual Crossing Weather API client for AccessiWeather.

This module provides a client for the Visual Crossing Weather API,
implementing methods to fetch current conditions, forecast, and hourly data.
"""

import logging
from datetime import datetime, timedelta, timezone

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
                "include": "current,days",
                "numDays": 1,
                "unitGroup": "us",  # Use US units (Fahrenheit, mph, inches)
                "elements": "temp,feelslike,humidity,windspeed,winddir,pressure,conditions,datetime,sunrise,sunset,moonrise,moonset,moonphase,sunriseEpoch,sunsetEpoch,moonriseEpoch,moonsetEpoch,snowdepth,preciptype,windchill,heatindex,severerisk,visibility",
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
                "elements": "datetime,tempmax,tempmin,temp,conditions,description,windspeed,winddir,icon,precipprob,snow,uvindex,snowdepth,preciptype,windchill,heatindex,severerisk,visibility,feelslikemax,feelslikemin",
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
                "elements": "datetime,temp,conditions,windspeed,winddir,icon,precipprob,snow,uvindex,snowdepth,preciptype,windchill,heatindex,visibility,feelslike",
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

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
    async def get_history(
        self, location: Location, start_date: datetime, end_date: datetime
    ) -> Forecast | None:
        """Get historical weather data from Visual Crossing API."""
        try:
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            url = f"{self.base_url}/{location.latitude},{location.longitude}/{start_str}/{end_str}"
            params = {
                "key": self.api_key,
                "include": "days",
                "unitGroup": "us",
                "elements": "datetime,tempmax,tempmin,temp,conditions,description,windspeed,winddir,icon,precipprob,snow,uvindex",
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
            logger.error(f"Failed to get Visual Crossing history: {e}")
            raise VisualCrossingApiError(f"Unexpected error: {e}") from e

    def _parse_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse Visual Crossing current conditions data."""
        current = data.get("currentConditions", {})

        # Get timezone offset from API response for creating timezone-aware datetimes
        # Visual Crossing returns tzoffset as hours (e.g., -5.0 for EST)
        tz_offset_hours = data.get("tzoffset", 0)
        location_tz = timezone(timedelta(hours=tz_offset_hours))

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

        # VC returns pressure in millibars even with unitGroup=us
        pressure_mb = current.get("pressure")
        pressure_in = pressure_mb / 33.8639 if pressure_mb is not None else None

        visibility_miles = current.get("visibility")
        visibility_km = visibility_miles * 1.60934 if visibility_miles is not None else None

        feels_like_f = current.get("feelslike")
        feels_like_c = self._convert_f_to_c(feels_like_f)

        sunrise_time = None
        sunset_time = None
        moonrise_time = None
        moonset_time = None
        moon_phase = None
        days = data.get("days", [])
        if days:
            day_data = days[0]
            # Get the date for combining with time strings
            date_str = day_data.get("datetime", "")

            # Parse sun/moon times from string format (already in local time)
            # Visual Crossing returns times like "07:08:45" in the location's timezone
            sunrise_time = self._parse_vc_time_string(
                date_str, day_data.get("sunrise"), location_tz
            )
            sunset_time = self._parse_vc_time_string(date_str, day_data.get("sunset"), location_tz)
            moonrise_time = self._parse_vc_time_string(
                date_str, day_data.get("moonrise"), location_tz
            )
            moonset_time = self._parse_vc_time_string(
                date_str, day_data.get("moonset"), location_tz
            )

            moon_phase = describe_moon_phase(day_data.get("moonphase"))

        # Seasonal fields
        snow_depth_in = current.get("snowdepth")
        snow_depth_cm = snow_depth_in * 2.54 if snow_depth_in is not None else None

        wind_chill_f = current.get("windchill")
        wind_chill_c = self._convert_f_to_c(wind_chill_f)

        heat_index_f = current.get("heatindex")
        heat_index_c = self._convert_f_to_c(heat_index_f)

        precip_type = current.get("preciptype")
        precipitation_type = precip_type if isinstance(precip_type, list) else None

        severe_weather_risk = current.get("severerisk")

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
            # Seasonal fields
            snow_depth_in=snow_depth_in,
            snow_depth_cm=snow_depth_cm,
            wind_chill_f=wind_chill_f,
            wind_chill_c=wind_chill_c,
            heat_index_f=heat_index_f,
            heat_index_c=heat_index_c,
            precipitation_type=precipitation_type,
            severe_weather_risk=severe_weather_risk,
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

            # Seasonal fields
            precip_type = day_data.get("preciptype")
            precipitation_type = precip_type if isinstance(precip_type, list) else None

            period = ForecastPeriod(
                name=name,
                temperature=day_data.get("tempmax"),
                temperature_unit="F",
                short_forecast=day_data.get("conditions"),
                detailed_forecast=day_data.get("description"),
                wind_speed=f"{day_data.get('windspeed', 0)} mph"
                if day_data.get("windspeed")
                else None,
                wind_direction=self._degrees_to_cardinal(day_data.get("winddir")),
                icon=day_data.get("icon"),
                precipitation_probability=day_data.get("precipprob"),
                snowfall=day_data.get("snow"),
                uv_index=day_data.get("uvindex"),
                # Seasonal fields
                snow_depth=day_data.get("snowdepth"),
                severe_weather_risk=day_data.get("severerisk"),
                precipitation_type=precipitation_type,
                feels_like_high=day_data.get("feelslikemax"),
                feels_like_low=day_data.get("feelslikemin"),
            )
            periods.append(period)

        return Forecast(periods=periods, generated_at=datetime.now())

    def _parse_hourly_forecast(self, data: dict) -> HourlyForecast:
        """Parse Visual Crossing hourly forecast data."""
        from zoneinfo import ZoneInfo

        periods = []
        days = data.get("days", [])

        # Get timezone info from the response
        # Visual Crossing returns timezone name (e.g., "America/New_York")
        location_tz = None
        timezone_str = data.get("timezone")
        if timezone_str:
            try:
                location_tz = ZoneInfo(timezone_str)
            except Exception:
                logger.warning(f"Failed to load timezone: {timezone_str}")

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
                        # Times are in the location's local timezone
                        date_str = day_data.get("datetime", "")
                        full_datetime_str = f"{date_str}T{datetime_str}"
                        start_time = datetime.fromisoformat(full_datetime_str)
                        # Add timezone info if available
                        if location_tz and start_time:
                            start_time = start_time.replace(tzinfo=location_tz)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Failed to parse Visual Crossing datetime: {full_datetime_str}"
                        )
                        start_time = datetime.now()

                # Seasonal fields
                precip_type = hour_data.get("preciptype")
                precipitation_type = precip_type if isinstance(precip_type, list) else None

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
                    precipitation_probability=hour_data.get("precipprob"),
                    snowfall=hour_data.get("snow"),
                    uv_index=hour_data.get("uvindex"),
                    # Seasonal fields
                    snow_depth=hour_data.get("snowdepth"),
                    wind_chill_f=hour_data.get("windchill"),
                    heat_index_f=hour_data.get("heatindex"),
                    feels_like=hour_data.get("feelslike"),
                    visibility_miles=hour_data.get("visibility"),
                    precipitation_type=precipitation_type,
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
            sent = self._parse_alert_time(alert_data.get("sent"))
            effective = self._parse_alert_time(alert_data.get("effective")) or onset

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
                sent=sent,
                effective=effective,
                source="VisualCrossing",
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
    def _parse_vc_time_string(
        self, date_str: str, time_str: str | None, tz: timezone
    ) -> datetime | None:
        """
        Parse Visual Crossing time string into a timezone-aware datetime.

        Visual Crossing returns times like "07:08:45" which are already in the
        location's local timezone. We combine with the date and attach the timezone.

        Args:
            date_str: Date string like "2025-12-08"
            time_str: Time string like "07:08:45" or None
            tz: Timezone to attach (from tzoffset in API response)

        Returns:
            Timezone-aware datetime or None if parsing fails

        """
        if not time_str or not date_str:
            return None

        try:
            # Combine date and time, then attach timezone
            # The time is already in local time, so we just label it with the timezone
            full_str = f"{date_str}T{time_str}"
            dt = datetime.fromisoformat(full_str)
            return dt.replace(tzinfo=tz)
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse VC time '{date_str}T{time_str}': {e}")
            return None

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
