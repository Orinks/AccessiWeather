"""Open-Meteo API client methods for fetching and parsing weather data from the Open-Meteo service."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import UTC, datetime
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
from .weather_client_openmeteo_current import (
    parse_iso_datetime as _parse_iso_datetime,
    parse_openmeteo_current_conditions as parse_openmeteo_current_conditions,
    pick_precipitation_type,
    resolve_current_condition_description,
)
from .weather_client_parsers import (
    degrees_to_cardinal,
    format_date_name,
    weather_code_to_description,
)

logger = logging.getLogger(__name__)


def _pick_precipitation_type(rain_in: float, snow_in: float) -> list[str] | None:
    """Compatibility wrapper for Open-Meteo precipitation-type inference."""
    return pick_precipitation_type(rain_in, snow_in)


def _resolve_current_condition_description(current: dict[str, Any]) -> str | None:
    """Compatibility wrapper for Open-Meteo current condition text."""
    return resolve_current_condition_description(current)


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
    forecast_days: int = 7,
    model: str = "best_match",
    hourly_hours: int = 48,
) -> tuple[CurrentConditions | None, Forecast | None, HourlyForecast | None]:
    """
    Fetch all Open-Meteo data in parallel.

    Returns: (current, forecast, hourly_forecast)
    """
    try:
        # Fetch all data in parallel
        current_task = asyncio.create_task(
            get_openmeteo_current_conditions(location, openmeteo_base_url, timeout, client, model)
        )
        forecast_task = asyncio.create_task(
            get_openmeteo_forecast(
                location,
                openmeteo_base_url,
                timeout,
                client,
                days=forecast_days,
                model=model,
            )
        )
        hourly_task = asyncio.create_task(
            get_openmeteo_hourly_forecast(
                location,
                openmeteo_base_url,
                timeout,
                client,
                model,
                hours=hourly_hours,
            )
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
    model: str = "best_match",
) -> CurrentConditions | None:
    """Fetch current conditions from the Open-Meteo API."""
    try:
        url = f"{openmeteo_base_url}/forecast"
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m,wind_direction_10m,pressure_msl,"
                "precipitation,rain,showers,snowfall,snow_depth,visibility,uv_index"
            ),
            "daily": "sunrise,sunset,uv_index_max",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
            "forecast_days": 1,
        }

        # Add model parameter if not using default
        if model and model != "best_match":
            params["models"] = model

        # Use provided client or create a new one
        if client is not None:
            response = await _client_get(client, url, params=params)
            response.raise_for_status()
            data = response.json()

            current = parse_openmeteo_current_conditions(data)
            if isinstance(current.wind_direction, int | float):
                current.wind_direction = degrees_to_cardinal(current.wind_direction)
            return current
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            current = parse_openmeteo_current_conditions(data)
            if isinstance(current.wind_direction, int | float):
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
    days: int = 7,
    model: str = "best_match",
) -> Forecast | None:
    """Fetch daily forecast from the Open-Meteo API."""
    try:
        url = f"{openmeteo_base_url}/forecast"
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "daily": (
                "temperature_2m_max,temperature_2m_min,weather_code,"
                "wind_speed_10m_max,wind_direction_10m_dominant,"
                "precipitation_probability_max,snowfall_sum,uv_index_max"
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
            "forecast_days": min(max(days, 1), 16),
        }

        # Add model parameter if not using default
        if model and model != "best_match":
            params["models"] = model

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
    model: str = "best_match",
    hours: int = 48,
) -> HourlyForecast | None:
    """Fetch hourly forecast from the Open-Meteo API."""
    try:
        url = f"{openmeteo_base_url}/forecast"
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "hourly": (
                "temperature_2m,relative_humidity_2m,dew_point_2m,weather_code,"
                "wind_speed_10m,wind_direction_10m,pressure_msl,"
                "precipitation_probability,snowfall,uv_index,snow_depth,freezing_level_height,"
                "visibility,apparent_temperature"
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
            "forecast_hours": min(max(hours, 1), 384),
        }

        # Add model parameter if not using default
        if model and model != "best_match":
            params["models"] = model

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


def parse_openmeteo_forecast(data: dict) -> Forecast:
    """Parse Open-Meteo daily forecast payload into a Forecast model."""
    daily = data.get("daily", {})
    utc_offset_seconds = data.get("utc_offset_seconds")
    periods = []

    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    weather_codes = daily.get("weather_code", [])
    precip_probs = daily.get("precipitation_probability_max", [])
    snowfall_sums = daily.get("snowfall_sum", [])
    uv_indices = daily.get("uv_index_max", [])

    for i, date in enumerate(dates):
        if i < len(max_temps) and i < len(weather_codes):
            precip_prob = precip_probs[i] if i < len(precip_probs) else None
            snowfall = snowfall_sums[i] if i < len(snowfall_sums) else None
            uv_index = uv_indices[i] if i < len(uv_indices) else None
            # Pass utc_offset_seconds so the noon timestamp is tagged with the
            # location's local timezone, not UTC.  Without this, for offsets ≥ 12 h
            # the UTC .date() can land on the wrong calendar day.
            start_time = _parse_iso_datetime(
                f"{date}T12:00:00", utc_offset_seconds
            ) or datetime.now(UTC)
            period = ForecastPeriod(
                name=format_date_name(date, i),
                temperature=max_temps[i],
                temperature_unit="F",
                short_forecast=weather_code_to_description(weather_codes[i]),
                start_time=start_time,
                precipitation_probability=precip_prob,
                snowfall=snowfall,
                uv_index=uv_index,
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
    humidities = hourly.get("relative_humidity_2m", [])
    dew_points = hourly.get("dew_point_2m", [])
    weather_codes = hourly.get("weather_code", [])
    wind_speeds = hourly.get("wind_speed_10m", [])
    wind_directions = hourly.get("wind_direction_10m", [])
    pressures = hourly.get("pressure_msl", [])
    precip_probs = hourly.get("precipitation_probability", [])
    snowfalls = hourly.get("snowfall", [])
    uv_indices = hourly.get("uv_index", [])
    # Seasonal fields
    snow_depths = hourly.get("snow_depth", [])
    freezing_levels = hourly.get("freezing_level_height", [])
    visibilities = hourly.get("visibility", [])
    apparent_temps = hourly.get("apparent_temperature", [])

    for i, time_str in enumerate(times):
        start_time = _parse_iso_datetime(time_str, utc_offset_seconds) or datetime.now()

        temperature = temperatures[i] if i < len(temperatures) else None
        humidity = humidities[i] if i < len(humidities) else None
        dewpoint = dew_points[i] if i < len(dew_points) else None
        weather_code = weather_codes[i] if i < len(weather_codes) else None
        wind_speed = wind_speeds[i] if i < len(wind_speeds) else None
        wind_direction = wind_directions[i] if i < len(wind_directions) else None
        pressure_mb = pressures[i] if i < len(pressures) else None
        pressure_in = pressure_mb * 0.0295299830714 if pressure_mb is not None else None
        precip_prob = precip_probs[i] if i < len(precip_probs) else None
        snowfall = snowfalls[i] if i < len(snowfalls) else None
        uv_index = uv_indices[i] if i < len(uv_indices) else None

        # Seasonal fields
        # With precipitation_unit=inch, snow_depth is returned in feet
        snow_depth_ft = snow_depths[i] if i < len(snow_depths) else None
        snow_depth_in = snow_depth_ft * 12 if snow_depth_ft is not None else None

        freezing_level_m = freezing_levels[i] if i < len(freezing_levels) else None
        freezing_level_ft = freezing_level_m * 3.28084 if freezing_level_m is not None else None

        visibility_m = visibilities[i] if i < len(visibilities) else None
        # Cap at 10 statute miles — Open-Meteo model visibility is unreliable above this
        if visibility_m is not None:
            visibility_m = min(visibility_m, 16093.4)
        visibility_miles = visibility_m / 1609.344 if visibility_m is not None else None

        apparent_temp = apparent_temps[i] if i < len(apparent_temps) else None
        dewpoint_f = dewpoint
        dewpoint_c = (dewpoint_f - 32) * 5 / 9 if dewpoint_f is not None else None
        if dewpoint_f is None and temperature is not None and humidity is not None:
            dewpoint_f = calculate_dewpoint(
                temperature,
                humidity,
                unit=TemperatureUnit.FAHRENHEIT,
            )
            dewpoint_c = (dewpoint_f - 32) * 5 / 9 if dewpoint_f is not None else None

        # Determine wind chill vs heat index from apparent temperature
        wind_chill_f = None
        heat_index_f = None
        if apparent_temp is not None and temperature is not None:
            if apparent_temp < temperature:
                wind_chill_f = apparent_temp
            elif apparent_temp > temperature:
                heat_index_f = apparent_temp

        period = HourlyForecastPeriod(
            start_time=start_time or datetime.now(),
            temperature=temperature,
            temperature_unit="F",
            short_forecast=weather_code_to_description(weather_code),
            wind_speed=f"{wind_speed} mph" if wind_speed is not None else None,
            wind_direction=degrees_to_cardinal(wind_direction),
            humidity=humidity,
            dewpoint_f=dewpoint_f,
            dewpoint_c=dewpoint_c,
            pressure_mb=pressure_mb,
            pressure_in=pressure_in,
            precipitation_probability=precip_prob,
            snowfall=snowfall,
            uv_index=uv_index,
            # Seasonal fields
            snow_depth=snow_depth_in,
            freezing_level_ft=freezing_level_ft,
            visibility_miles=visibility_miles,
            feels_like=apparent_temp,
            wind_chill_f=wind_chill_f,
            heat_index_f=heat_index_f,
        )
        periods.append(period)

    return HourlyForecast(periods=periods, generated_at=datetime.now())
