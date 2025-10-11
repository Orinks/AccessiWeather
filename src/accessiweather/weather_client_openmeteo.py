"""Open-Meteo API client methods for fetching and parsing weather data from the Open-Meteo service."""

from __future__ import annotations

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
)
from .utils.temperature_utils import TemperatureUnit, calculate_dewpoint
from .weather_client_parsers import (
    convert_f_to_c,
    convert_wind_speed_to_mph_and_kph,
    degrees_to_cardinal,
    format_date_name,
    normalize_pressure,
    normalize_temperature,
    weather_code_to_description,
)

logger = logging.getLogger(__name__)


async def get_openmeteo_current_conditions(
    location: Location,
    openmeteo_base_url: str,
    timeout: float,
) -> CurrentConditions | None:
    """Fetch current conditions from the Open-Meteo API."""
    try:
        url = f"{openmeteo_base_url}/forecast"
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,pressure_msl",
            "daily": "sunrise,sunset",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
            "forecast_days": 1,
        }

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            current = parse_openmeteo_current_conditions(data)
            if isinstance(current.wind_direction, (int, float)):
                current.wind_direction = degrees_to_cardinal(current.wind_direction)
            return current

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get OpenMeteo current conditions: {exc}")
        return None


async def get_openmeteo_forecast(
    location: Location,
    openmeteo_base_url: str,
    timeout: float,
) -> Forecast | None:
    """Fetch daily forecast from the Open-Meteo API."""
    try:
        url = f"{openmeteo_base_url}/forecast"
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "daily": "temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max,wind_direction_10m_dominant",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "auto",
            "forecast_days": 7,
        }

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            return parse_openmeteo_forecast(data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get OpenMeteo forecast: {exc}")
        return None


async def get_openmeteo_hourly_forecast(
    location: Location,
    openmeteo_base_url: str,
    timeout: float,
) -> HourlyForecast | None:
    """Fetch hourly forecast from the Open-Meteo API."""
    try:
        url = f"{openmeteo_base_url}/forecast"
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "hourly": "temperature_2m,weather_code,wind_speed_10m,wind_direction_10m,pressure_msl",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "auto",
            "forecast_days": 2,
        }

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            return parse_openmeteo_hourly_forecast(data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get OpenMeteo hourly forecast: {exc}")
        return None


def parse_openmeteo_current_conditions(data: dict) -> CurrentConditions:
    """Parse Open-Meteo current condition payload into a CurrentConditions model."""
    current = data.get("current", {})
    units = data.get("current_units", {})
    daily = data.get("daily", {})

    temp_f, temp_c = normalize_temperature(
        current.get("temperature_2m"), units.get("temperature_2m")
    )

    humidity = current.get("relative_humidity_2m")
    humidity = round(humidity) if humidity is not None else None

    dewpoint_f = None
    dewpoint_c = None
    if temp_f is not None and humidity is not None:
        dewpoint_f = calculate_dewpoint(temp_f, humidity, unit=TemperatureUnit.FAHRENHEIT)
        if dewpoint_f is not None:
            dewpoint_c = convert_f_to_c(dewpoint_f)

    wind_speed_mph, wind_speed_kph = convert_wind_speed_to_mph_and_kph(
        current.get("wind_speed_10m"), units.get("wind_speed_10m")
    )

    pressure_in, pressure_mb = normalize_pressure(
        current.get("pressure_msl"), units.get("pressure_msl")
    )

    feels_like_f, feels_like_c = normalize_temperature(
        current.get("apparent_temperature"), units.get("apparent_temperature")
    )

    timestamp = current.get("time")
    last_updated = None
    if timestamp:
        try:
            last_updated = datetime.fromisoformat(timestamp)
        except ValueError:
            logger.debug(f"Failed to parse OpenMeteo timestamp: {timestamp}")

    # Parse sunrise and sunset times from daily data (today's values)
    sunrise_time = None
    sunset_time = None
    if daily:
        sunrise_list = daily.get("sunrise", [])
        sunset_list = daily.get("sunset", [])
        if sunrise_list and len(sunrise_list) > 0:
            try:
                sunrise_time = datetime.fromisoformat(sunrise_list[0])
            except (ValueError, TypeError):
                logger.debug(f"Failed to parse sunrise time: {sunrise_list[0]}")
        if sunset_list and len(sunset_list) > 0:
            try:
                sunset_time = datetime.fromisoformat(sunset_list[0])
            except (ValueError, TypeError):
                logger.debug(f"Failed to parse sunset time: {sunset_list[0]}")

    return CurrentConditions(
        temperature_f=temp_f,
        temperature_c=temp_c,
        condition=weather_code_to_description(current.get("weather_code")),
        humidity=humidity,
        dewpoint_f=dewpoint_f,
        dewpoint_c=dewpoint_c,
        wind_speed_mph=wind_speed_mph,
        wind_speed_kph=wind_speed_kph,
        wind_direction=current.get("wind_direction_10m"),
        pressure_in=pressure_in,
        pressure_mb=pressure_mb,
        feels_like_f=feels_like_f,
        feels_like_c=feels_like_c,
        sunrise_time=sunrise_time,
        sunset_time=sunset_time,
        last_updated=last_updated or datetime.now(),
    )


def parse_openmeteo_forecast(data: dict) -> Forecast:
    """Parse Open-Meteo daily forecast payload into a Forecast model."""
    daily = data.get("daily", {})
    periods = []

    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    weather_codes = daily.get("weather_code", [])

    for i, date in enumerate(dates):
        if i < len(max_temps) and i < len(weather_codes):
            period = ForecastPeriod(
                name=format_date_name(date, i),
                temperature=max_temps[i],
                temperature_unit="F",
                short_forecast=weather_code_to_description(weather_codes[i]),
            )
            periods.append(period)

    return Forecast(periods=periods, generated_at=datetime.now())


def parse_openmeteo_hourly_forecast(data: dict) -> HourlyForecast:
    """Parse Open-Meteo hourly forecast payload into an HourlyForecast model."""
    periods: list[HourlyForecastPeriod] = []
    hourly = data.get("hourly", {})

    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    weather_codes = hourly.get("weather_code", [])
    wind_speeds = hourly.get("wind_speed_10m", [])
    wind_directions = hourly.get("wind_direction_10m", [])
    pressures = hourly.get("pressure_msl", [])

    for i, time_str in enumerate(times):
        start_time = None
        if time_str:
            try:
                start_time = datetime.fromisoformat(time_str)
            except ValueError:
                logger.warning(f"Failed to parse OpenMeteo time: {time_str}")
                start_time = datetime.now()

        temperature = temperatures[i] if i < len(temperatures) else None
        weather_code = weather_codes[i] if i < len(weather_codes) else None
        wind_speed = wind_speeds[i] if i < len(wind_speeds) else None
        wind_direction = wind_directions[i] if i < len(wind_directions) else None
        pressure_mb = pressures[i] if i < len(pressures) else None
        pressure_in = pressure_mb * 0.0295299830714 if pressure_mb is not None else None

        period = HourlyForecastPeriod(
            start_time=start_time or datetime.now(),
            temperature=temperature,
            temperature_unit="F",
            short_forecast=weather_code_to_description(weather_code),
            wind_speed=f"{wind_speed} mph" if wind_speed is not None else None,
            wind_direction=degrees_to_cardinal(wind_direction),
            pressure_mb=pressure_mb,
            pressure_in=pressure_in,
        )
        periods.append(period)

    return HourlyForecast(periods=periods, generated_at=datetime.now())
