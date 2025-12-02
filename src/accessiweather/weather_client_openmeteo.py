"""Open-Meteo API client methods for fetching and parsing weather data from the Open-Meteo service."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx

from .models import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
)
from .utils.retry_utils import (
    RETRYABLE_EXCEPTIONS,
    async_retry_with_backoff,
    is_retryable_http_error,
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


def _parse_iso_datetime(
    value: str | None, utc_offset_seconds: int | None = None
) -> datetime | None:
    """
    Parse an ISO 8601 datetime string, converting to location's local timezone.

    Open-Meteo returns ISO 8601 strings that may be timezone-aware or naive.
    When using timezone="auto", Open-Meteo typically returns naive datetimes in the
    location's local timezone, with utc_offset_seconds indicating the offset.

    If the timestamp is UTC-aware (ends with Z or +00:00), we convert it to the
    location's timezone using utc_offset_seconds.

    Args:
        value: ISO 8601 datetime string
        utc_offset_seconds: UTC offset in seconds (e.g., -28800 for PST/UTC-8)

    Returns:
        Timezone-aware datetime object in the location's timezone, or None if parsing fails

    """
    if not value:
        return None

    candidates = [value]
    if value.endswith("Z"):
        candidates.append(value[:-1] + "+00:00")

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)

            # Build the target timezone from offset
            local_tz = None
            if utc_offset_seconds is not None:
                local_tz = timezone(timedelta(seconds=utc_offset_seconds))

            if dt.tzinfo is None:
                # Naive datetime - assume it's already in local time, just label it
                dt = dt.replace(tzinfo=local_tz) if local_tz else dt.replace(tzinfo=UTC)
            elif local_tz and (
                dt.tzinfo == UTC or (dt.utcoffset() and dt.utcoffset().total_seconds() == 0)
            ):
                # UTC-aware datetime - convert to local timezone
                dt = dt.astimezone(local_tz)

            return dt
        except ValueError:
            continue

    logger.debug("Failed to parse ISO datetime value: %s", value)
    return None


async def _client_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    """Call AsyncClient.get allowing for mocked synchronous responses in tests."""
    response = client.get(url, params=params)
    if inspect.isawaitable(response):
        return await response
    return response


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=25.0)
async def get_openmeteo_all_data_parallel(
    location: Location,
    openmeteo_base_url: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> tuple[CurrentConditions | None, Forecast | None, HourlyForecast | None]:
    """
    Fetch all Open-Meteo data in parallel.

    Returns: (current, forecast, hourly_forecast)
    """
    try:
        # Fetch all data in parallel
        current_task = asyncio.create_task(
            get_openmeteo_current_conditions(location, openmeteo_base_url, timeout, client)
        )
        forecast_task = asyncio.create_task(
            get_openmeteo_forecast(location, openmeteo_base_url, timeout, client)
        )
        hourly_task = asyncio.create_task(
            get_openmeteo_hourly_forecast(location, openmeteo_base_url, timeout, client)
        )

        # Gather all results
        current = await current_task
        forecast = await forecast_task
        hourly_forecast = await hourly_task

        return current, forecast, hourly_forecast

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get Open-Meteo data in parallel: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None, None, None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_openmeteo_current_conditions(
    location: Location,
    openmeteo_base_url: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> CurrentConditions | None:
    """Fetch current conditions from the Open-Meteo API."""
    try:
        url = f"{openmeteo_base_url}/forecast"
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m,wind_direction_10m,pressure_msl"
            ),
            "daily": "sunrise,sunset,uv_index_max",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
            "forecast_days": 1,
        }

        # Use provided client or create a new one
        if client is not None:
            response = await _client_get(client, url, params=params)
            response.raise_for_status()
            data = response.json()

            current = parse_openmeteo_current_conditions(data)
            if isinstance(current.wind_direction, (int, float)):
                current.wind_direction = degrees_to_cardinal(current.wind_direction)
            return current
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            current = parse_openmeteo_current_conditions(data)
            if isinstance(current.wind_direction, (int, float)):
                current.wind_direction = degrees_to_cardinal(current.wind_direction)
            return current

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get OpenMeteo current conditions: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_openmeteo_forecast(
    location: Location,
    openmeteo_base_url: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> Forecast | None:
    """Fetch daily forecast from the Open-Meteo API."""
    try:
        url = f"{openmeteo_base_url}/forecast"
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "daily": (
                "temperature_2m_max,temperature_2m_min,weather_code,"
                "wind_speed_10m_max,wind_direction_10m_dominant"
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "auto",
            "forecast_days": 7,
        }

        # Use provided client or create a new one
        if client is not None:
            response = await _client_get(client, url, params=params)
            response.raise_for_status()
            data = response.json()
            return parse_openmeteo_forecast(data)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return parse_openmeteo_forecast(data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get OpenMeteo forecast: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_openmeteo_hourly_forecast(
    location: Location,
    openmeteo_base_url: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
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

        # Use provided client or create a new one
        if client is not None:
            response = await _client_get(client, url, params=params)
            response.raise_for_status()
            data = response.json()
            return parse_openmeteo_hourly_forecast(data)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return parse_openmeteo_hourly_forecast(data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get OpenMeteo hourly forecast: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None


def parse_openmeteo_current_conditions(data: dict) -> CurrentConditions:
    """Parse Open-Meteo current condition payload into a CurrentConditions model."""
    current = data.get("current", {})
    units = data.get("current_units", {})
    daily = data.get("daily", {})
    utc_offset_seconds = data.get("utc_offset_seconds")

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

    # Parse sunrise and sunset times from daily data (today's values)
    sunrise_time = None
    sunset_time = None
    if daily:
        sunrise_list = daily.get("sunrise", [])
        sunset_list = daily.get("sunset", [])
        if sunrise_list and len(sunrise_list) > 0:
            sunrise_time = _parse_iso_datetime(sunrise_list[0], utc_offset_seconds)
        if sunset_list and len(sunset_list) > 0:
            sunset_time = _parse_iso_datetime(sunset_list[0], utc_offset_seconds)

    uv_index = None
    if daily:
        uv_values = daily.get("uv_index_max") or []
        if uv_values:
            try:
                uv_index = float(uv_values[0]) if uv_values[0] is not None else None
            except (TypeError, ValueError):
                uv_index = None

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
        uv_index=uv_index,
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
    utc_offset_seconds = data.get("utc_offset_seconds")

    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    weather_codes = hourly.get("weather_code", [])
    wind_speeds = hourly.get("wind_speed_10m", [])
    wind_directions = hourly.get("wind_direction_10m", [])
    pressures = hourly.get("pressure_msl", [])

    for i, time_str in enumerate(times):
        start_time = _parse_iso_datetime(time_str, utc_offset_seconds) or datetime.now()

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
