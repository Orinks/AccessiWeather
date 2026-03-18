"""
Pirate Weather API client for AccessiWeather.

This module provides a client for the Pirate Weather API
(https://pirateweather.net), which is an open-source Dark Sky API replacement.
It provides current conditions, hourly/daily forecasts, minutely precipitation,
and global WMO weather alerts.

API endpoint: https://api.pirateweather.net/forecast/{apikey}/{lat},{lon}
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, timezone

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
from .weather_client_parsers import convert_f_to_c, degrees_to_cardinal

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.pirateweather.net/forecast"


class PirateWeatherApiError(Exception):
    """Exception raised for Pirate Weather API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize the instance."""
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# Pirate Weather icon -> human-readable condition mapping
_ICON_TO_CONDITION: dict[str, str] = {
    "clear-day": "Clear",
    "clear-night": "Clear",
    "rain": "Rain",
    "snow": "Snow",
    "sleet": "Sleet",
    "wind": "Windy",
    "fog": "Fog",
    "cloudy": "Cloudy",
    "partly-cloudy-day": "Partly Cloudy",
    "partly-cloudy-night": "Partly Cloudy",
    "thunderstorm": "Thunderstorm",
    "hail": "Hail",
    "tornado": "Tornado",
}


def _icon_to_condition(icon: str | None) -> str | None:
    """Map a Pirate Weather icon string to a human-readable condition."""
    if not icon:
        return None
    return _ICON_TO_CONDITION.get(icon, icon.replace("-", " ").title())


class PirateWeatherClient:
    """Client for the Pirate Weather API."""

    def __init__(
        self,
        api_key: str,
        user_agent: str = "AccessiWeather/1.0",
        units: str = "us",
    ):
        """
        Initialize the Pirate Weather client.

        Args:
            api_key: Pirate Weather API key.
            user_agent: HTTP User-Agent header value.
            units: Unit system – "us" (°F, mph, in), "si" (°C, m/s, mm),
                   "ca" (°C, km/h, mm), or "uk2" (°C, mph, mm).

        """
        self.api_key = api_key
        self.user_agent = user_agent
        self.units = units
        self.timeout = 15.0

    def _build_url(self, lat: float, lon: float) -> str:
        return f"{_BASE_URL}/{self.api_key}/{lat},{lon}"

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
    async def get_forecast_data(self, location: Location) -> dict | None:
        """
        Fetch the full forecast payload from Pirate Weather.

        Returns the raw API response dict (with ``currently``, ``hourly``,
        ``daily``, ``minutely``, ``alerts`` keys) or ``None`` on error.
        """
        url = self._build_url(location.latitude, location.longitude)
        params = {
            "units": self.units,
            "extend": "hourly",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 400:
                    raise PirateWeatherApiError(
                        "Bad request – check API key and coordinates",
                        response.status_code,
                    )
                if response.status_code == 401:
                    raise PirateWeatherApiError("Invalid API key", response.status_code)
                if response.status_code == 429:
                    raise PirateWeatherApiError("API rate limit exceeded", response.status_code)
                if response.status_code != 200:
                    raise PirateWeatherApiError(
                        f"API request failed: HTTP {response.status_code}",
                        response.status_code,
                    )

                return response.json()

        except httpx.TimeoutException:
            logger.error("Pirate Weather API request timed out")
            raise PirateWeatherApiError("Request timed out") from None
        except httpx.RequestError as e:
            logger.error(f"Pirate Weather API request failed: {e}")
            raise PirateWeatherApiError(f"Request failed: {e}") from e
        except PirateWeatherApiError:
            raise
        except Exception as e:
            logger.error(f"Unexpected Pirate Weather error: {e}")
            raise PirateWeatherApiError(f"Unexpected error: {e}") from e

    async def get_current_conditions(self, location: Location) -> CurrentConditions | None:
        """Get current weather conditions."""
        data = await self.get_forecast_data(location)
        if data is None:
            return None
        return self._parse_current_conditions(data)

    async def get_forecast(self, location: Location, days: int = 7) -> Forecast | None:
        """Get daily weather forecast."""
        data = await self.get_forecast_data(location)
        if data is None:
            return None
        return self._parse_forecast(data, days=days)

    async def get_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Get hourly weather forecast."""
        data = await self.get_forecast_data(location)
        if data is None:
            return None
        return self._parse_hourly_forecast(data)

    async def get_alerts(self, location: Location) -> WeatherAlerts:
        """Get weather alerts."""
        try:
            data = await self.get_forecast_data(location)
            if data is None:
                return WeatherAlerts(alerts=[])
            return self._parse_alerts(data)
        except Exception:
            logger.debug("Pirate Weather alerts request failed", exc_info=True)
            return WeatherAlerts(alerts=[])

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse Pirate Weather ``currently`` block into CurrentConditions."""
        current = data.get("currently", {})

        # Temperature (PW returns °F in "us" units, °C otherwise)
        temp = current.get("temperature")
        using_us = self.units == "us"

        if using_us:
            temp_f = float(temp) if temp is not None else None
            temp_c = convert_f_to_c(temp_f)
        else:
            temp_c = float(temp) if temp is not None else None
            temp_f = (temp_c * 9 / 5 + 32) if temp_c is not None else None

        # Humidity (0-1 in PW → 0-100)
        humidity_raw = current.get("humidity")
        humidity = round(humidity_raw * 100) if humidity_raw is not None else None

        # Dew point
        dewpoint = current.get("dewPoint")
        if using_us:
            dewpoint_f = float(dewpoint) if dewpoint is not None else None
            dewpoint_c = convert_f_to_c(dewpoint_f)
            if dewpoint_f is None and temp_f is not None and humidity is not None:
                dewpoint_f = calculate_dewpoint(temp_f, humidity, unit=TemperatureUnit.FAHRENHEIT)
                dewpoint_c = convert_f_to_c(dewpoint_f)
        else:
            dewpoint_c = float(dewpoint) if dewpoint is not None else None
            dewpoint_f = (dewpoint_c * 9 / 5 + 32) if dewpoint_c is not None else None

        # Wind – PW "us" = mph, "si" = m/s, "ca" = km/h, "uk2" = mph
        wind_speed_raw = current.get("windSpeed")
        if using_us or self.units == "uk2":
            wind_speed_mph = float(wind_speed_raw) if wind_speed_raw is not None else None
            wind_speed_kph = wind_speed_mph * 1.60934 if wind_speed_mph is not None else None
        elif self.units == "ca":
            wind_speed_kph = float(wind_speed_raw) if wind_speed_raw is not None else None
            wind_speed_mph = wind_speed_kph / 1.60934 if wind_speed_kph is not None else None
        else:  # si: m/s
            wind_mps = float(wind_speed_raw) if wind_speed_raw is not None else None
            wind_speed_mph = wind_mps * 2.23694 if wind_mps is not None else None
            wind_speed_kph = wind_mps * 3.6 if wind_mps is not None else None

        wind_direction = current.get("windBearing")  # degrees

        # Pressure – PW returns mb in all unit groups
        pressure_mb = current.get("pressure")
        pressure_in = pressure_mb / 33.8639 if pressure_mb is not None else None

        # Visibility – PW "us" = miles, others = km
        visibility_raw = current.get("visibility")
        if using_us or self.units == "uk2":
            visibility_miles = float(visibility_raw) if visibility_raw is not None else None
            visibility_km = visibility_miles * 1.60934 if visibility_miles is not None else None
        else:
            visibility_km = float(visibility_raw) if visibility_raw is not None else None
            visibility_miles = visibility_km / 1.60934 if visibility_km is not None else None

        # Feels like (apparent temperature)
        apparent = current.get("apparentTemperature")
        if using_us:
            feels_like_f = float(apparent) if apparent is not None else None
            feels_like_c = convert_f_to_c(feels_like_f)
        else:
            feels_like_c = float(apparent) if apparent is not None else None
            feels_like_f = (feels_like_c * 9 / 5 + 32) if feels_like_c is not None else None

        # Wind gust
        wind_gust_raw = current.get("windGust")
        if using_us or self.units == "uk2":
            wind_gust_mph = float(wind_gust_raw) if wind_gust_raw is not None else None
            wind_gust_kph = wind_gust_mph * 1.60934 if wind_gust_mph is not None else None
        elif self.units == "ca":
            wind_gust_kph = float(wind_gust_raw) if wind_gust_raw is not None else None
            wind_gust_mph = wind_gust_kph / 1.60934 if wind_gust_kph is not None else None
        else:
            wind_gust_mps = float(wind_gust_raw) if wind_gust_raw is not None else None
            wind_gust_mph = wind_gust_mps * 2.23694 if wind_gust_mps is not None else None
            wind_gust_kph = wind_gust_mps * 3.6 if wind_gust_mps is not None else None

        # Precipitation intensity – PW "us" = in/hr, others = mm/hr
        precip_intensity = current.get("precipIntensity")
        if using_us:
            precip_in = float(precip_intensity) if precip_intensity is not None else None
            precip_mm = precip_in * 25.4 if precip_in is not None else None
        else:
            precip_mm = float(precip_intensity) if precip_intensity is not None else None
            precip_in = precip_mm / 25.4 if precip_mm is not None else None

        cloud_cover_raw = current.get("cloudCover")
        cloud_cover = round(cloud_cover_raw * 100) if cloud_cover_raw is not None else None

        uv_index = current.get("uvIndex")

        # Sunrise/sunset come from the first daily entry
        sunrise_time = None
        sunset_time = None
        daily_data = data.get("daily", {}).get("data", [])
        if daily_data:
            today = daily_data[0]
            tz_offset = data.get("offset", 0)
            location_tz = timezone(timedelta(hours=tz_offset))
            sr = today.get("sunriseTime")
            ss = today.get("sunsetTime")
            if sr:
                sunrise_time = datetime.fromtimestamp(sr, tz=location_tz)
            if ss:
                sunset_time = datetime.fromtimestamp(ss, tz=location_tz)

        condition_str = current.get("summary") or _icon_to_condition(current.get("icon"))

        return CurrentConditions(
            temperature_f=temp_f,
            temperature_c=temp_c,
            condition=condition_str,
            humidity=humidity,
            dewpoint_f=dewpoint_f,
            dewpoint_c=dewpoint_c,
            wind_speed_mph=wind_speed_mph,
            wind_speed_kph=wind_speed_kph,
            wind_direction=degrees_to_cardinal(wind_direction),
            pressure_in=pressure_in,
            pressure_mb=pressure_mb,
            feels_like_f=feels_like_f,
            feels_like_c=feels_like_c,
            visibility_miles=visibility_miles,
            visibility_km=visibility_km,
            uv_index=uv_index,
            cloud_cover=cloud_cover,
            wind_gust_mph=wind_gust_mph,
            wind_gust_kph=wind_gust_kph,
            precipitation_in=precip_in,
            precipitation_mm=precip_mm,
            sunrise_time=sunrise_time,
            sunset_time=sunset_time,
        )

    def _parse_forecast(self, data: dict, days: int = 7) -> Forecast:
        """Parse Pirate Weather ``daily`` block into a Forecast."""
        daily_data = data.get("daily", {}).get("data", [])
        tz_offset = data.get("offset", 0)
        location_tz = timezone(timedelta(hours=tz_offset))
        using_us = self.units == "us"

        periods: list[ForecastPeriod] = []
        for i, day in enumerate(daily_data[:days]):
            time_val = day.get("time")
            if time_val:
                dt = datetime.fromtimestamp(time_val, tz=location_tz)
                if i == 0:
                    name = "Today"
                elif i == 1:
                    name = "Tomorrow"
                else:
                    name = dt.strftime("%A")
            else:
                name = f"Day {i + 1}"

            temp_high = day.get("temperatureHigh") if using_us else day.get("temperatureMax")
            temp_low = day.get("temperatureLow") if using_us else day.get("temperatureMin")

            # Wind speed formatting
            wind_raw = day.get("windSpeed")
            if wind_raw is not None:
                if using_us or self.units == "uk2":
                    wind_str = f"{wind_raw} mph"
                elif self.units == "ca":
                    wind_str = f"{wind_raw} km/h"
                else:
                    wind_str = f"{wind_raw} m/s"
            else:
                wind_str = None

            wind_gust_raw = day.get("windGust")
            if wind_gust_raw is not None:
                if using_us or self.units == "uk2":
                    wind_gust_str = f"{wind_gust_raw} mph"
                elif self.units == "ca":
                    wind_gust_str = f"{wind_gust_raw} km/h"
                else:
                    wind_gust_str = f"{wind_gust_raw} m/s"
            else:
                wind_gust_str = None

            precip_prob_raw = day.get("precipProbability")
            precip_prob = round(precip_prob_raw * 100) if precip_prob_raw is not None else None

            precip_intensity = day.get("precipIntensity")
            if precip_intensity is not None:
                precip_amount = precip_intensity if using_us else precip_intensity / 25.4
            else:
                precip_amount = None

            cloud_cover_raw = day.get("cloudCover")
            cloud_cover = round(cloud_cover_raw * 100) if cloud_cover_raw is not None else None

            uv_index = day.get("uvIndex")

            condition = day.get("summary") or _icon_to_condition(day.get("icon"))

            start_time = datetime.fromtimestamp(time_val, tz=location_tz) if time_val else None

            period = ForecastPeriod(
                name=name,
                temperature=temp_high,
                temperature_low=temp_low,
                temperature_unit="F" if using_us else "C",
                short_forecast=condition,
                detailed_forecast=condition,
                wind_speed=wind_str,
                wind_direction=degrees_to_cardinal(day.get("windBearing")),
                precipitation_probability=precip_prob,
                uv_index=uv_index,
                cloud_cover=cloud_cover,
                wind_gust=wind_gust_str,
                precipitation_amount=precip_amount,
                start_time=start_time,
            )
            periods.append(period)

        return Forecast(periods=periods, generated_at=datetime.now(UTC))

    def _parse_hourly_forecast(self, data: dict) -> HourlyForecast:
        """Parse Pirate Weather ``hourly`` block into an HourlyForecast."""
        hourly_items = data.get("hourly", {}).get("data", [])
        tz_offset = data.get("offset", 0)
        location_tz = timezone(timedelta(hours=tz_offset))
        using_us = self.units == "us"

        periods: list[HourlyForecastPeriod] = []
        for hour in hourly_items:
            time_val = hour.get("time")
            if time_val:
                start_time = datetime.fromtimestamp(time_val, tz=location_tz)
            else:
                start_time = datetime.now(UTC)

            temp = hour.get("temperature")
            if using_us:
                temp_f = float(temp) if temp is not None else None
            else:
                temp_c = float(temp) if temp is not None else None
                temp_f = (temp_c * 9 / 5 + 32) if temp_c is not None else temp_c

            # Pressure in mb (all unit groups)
            pressure_mb = hour.get("pressure")
            pressure_in = pressure_mb / 33.8639 if pressure_mb is not None else None

            wind_raw = hour.get("windSpeed")
            if wind_raw is not None:
                if using_us or self.units == "uk2":
                    wind_str = f"{wind_raw} mph"
                elif self.units == "ca":
                    wind_str = f"{wind_raw} km/h"
                else:
                    wind_str = f"{wind_raw} m/s"
            else:
                wind_str = None

            wind_gust_raw = hour.get("windGust")
            wind_gust_mph: float | None = None
            if wind_gust_raw is not None:
                if using_us or self.units == "uk2":
                    wind_gust_mph = float(wind_gust_raw)
                elif self.units == "ca":
                    wind_gust_mph = float(wind_gust_raw) / 1.60934
                else:
                    wind_gust_mph = float(wind_gust_raw) * 2.23694

            precip_prob_raw = hour.get("precipProbability")
            precip_prob = round(precip_prob_raw * 100) if precip_prob_raw is not None else None

            precip_intensity = hour.get("precipIntensity")
            if precip_intensity is not None:
                precip_amount = precip_intensity if using_us else precip_intensity / 25.4
            else:
                precip_amount = None

            cloud_cover_raw = hour.get("cloudCover")
            cloud_cover = round(cloud_cover_raw * 100) if cloud_cover_raw is not None else None

            uv_index = hour.get("uvIndex")

            visibility_raw = hour.get("visibility")
            if visibility_raw is not None:
                if using_us or self.units == "uk2":
                    visibility_miles = float(visibility_raw)
                    visibility_km = visibility_miles * 1.60934
                else:
                    visibility_km = float(visibility_raw)
                    visibility_miles = visibility_km / 1.60934
            else:
                visibility_miles = None
                visibility_km = None

            apparent = hour.get("apparentTemperature")
            if using_us:
                feels_like_f = float(apparent) if apparent is not None else None
            else:
                feels_like_c = float(apparent) if apparent is not None else None
                feels_like_f = (feels_like_c * 9 / 5 + 32) if feels_like_c is not None else None

            condition = hour.get("summary") or _icon_to_condition(hour.get("icon"))

            period = HourlyForecastPeriod(
                start_time=start_time,
                temperature=temp_f,
                temperature_unit="F",
                short_forecast=condition,
                wind_speed=wind_str,
                wind_direction=degrees_to_cardinal(hour.get("windBearing")),
                pressure_mb=pressure_mb,
                pressure_in=pressure_in,
                precipitation_probability=precip_prob,
                uv_index=uv_index,
                cloud_cover=cloud_cover,
                wind_gust_mph=wind_gust_mph,
                precipitation_amount=precip_amount,
                feels_like=feels_like_f,
                visibility_miles=visibility_miles,
                visibility_km=visibility_km,
            )
            periods.append(period)

        return HourlyForecast(periods=periods, generated_at=datetime.now(UTC))

    def _parse_alerts(self, data: dict) -> WeatherAlerts:
        """Parse Pirate Weather ``alerts`` list into WeatherAlerts."""
        raw_alerts = data.get("alerts", [])
        alerts: list[WeatherAlert] = []

        tz_offset = data.get("offset", 0)
        location_tz = timezone(timedelta(hours=tz_offset))

        for _i, alert_data in enumerate(raw_alerts):
            title = alert_data.get("title") or "Weather Alert"
            description = alert_data.get("description") or title
            severity = self._map_severity(alert_data.get("severity"))
            uri = alert_data.get("uri") or ""

            # Use stable ID based on title + expires so it doesn't change on minor
            # text updates to the description
            expires_raw = alert_data.get("expires")
            _id_str = f"pw-{hash(f'{title}-{expires_raw}')}"
            alert_id = uri or _id_str

            onset_raw = alert_data.get("time")
            expires_raw_val = alert_data.get("expires")

            onset = datetime.fromtimestamp(onset_raw, tz=location_tz) if onset_raw else None
            expires = (
                datetime.fromtimestamp(expires_raw_val, tz=location_tz) if expires_raw_val else None
            )

            regions = alert_data.get("regions", [])
            areas: list[str] = regions if isinstance(regions, list) else []

            alert = WeatherAlert(
                id=alert_id,
                title=title,
                description=description,
                severity=severity,
                urgency="Unknown",
                certainty="Possible",
                event=title,
                headline=title,
                instruction=None,
                areas=areas,
                onset=onset,
                expires=expires,
                sent=onset,
                effective=onset,
                source="PirateWeather",
            )
            alerts.append(alert)

        logger.info(f"Parsed {len(alerts)} Pirate Weather alerts")
        return WeatherAlerts(alerts=alerts)

    def _map_severity(self, severity: str | None) -> str:
        """Map Pirate Weather severity string to standard levels."""
        if not severity:
            return "Unknown"
        mapping = {
            "extreme": "Extreme",
            "severe": "Severe",
            "moderate": "Moderate",
            "minor": "Minor",
            "advisory": "Minor",
            "watch": "Moderate",
            "warning": "Severe",
        }
        return mapping.get(severity.lower(), "Unknown")
