"""Hourly forecast helpers for the NWS weather client."""
# ruff: noqa: F403, F405

from __future__ import annotations

from .weather_client_nws_common import *  # noqa: F403
from .weather_client_nws_parsers import (
    apply_nws_gridpoint_pressure,
    parse_nws_gridpoint_pressure,
    parse_nws_hourly_forecast,
)


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_hourly_forecast(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
    grid_data: dict[str, Any] | None = None,
) -> HourlyForecast | None:
    """Fetch hourly forecast from the NWS API."""
    try:
        headers = {"User-Agent": user_agent}
        feature_headers = headers.copy()
        feature_headers["Feature-Flags"] = "forecast_temperature_qv, forecast_wind_speed_qv"

        # Use provided client or create a new one
        if client is not None:
            # Fetch grid data if not provided
            if grid_data is None:
                grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
                response = await _client_get(client, grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

            hourly_forecast_url = grid_data.get("properties", {}).get("forecastHourly")
            if not hourly_forecast_url:
                logger.warning("No hourly forecast URL found in grid data")
                return None

            response = await _client_get(client, hourly_forecast_url, headers=feature_headers)
            response.raise_for_status()
            hourly_data = response.json()

            hourly = parse_nws_hourly_forecast(hourly_data, location)
            pressure_data = await _fetch_nws_gridpoint_pressure(
                grid_data,
                client,
                headers,
            )
            return apply_nws_gridpoint_pressure(hourly, pressure_data)
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            hourly_forecast_url = grid_data.get("properties", {}).get("forecastHourly")
            if not hourly_forecast_url:
                logger.warning("No hourly forecast URL found in grid data")
                return None

            response = await new_client.get(hourly_forecast_url, headers=feature_headers)
            response.raise_for_status()
            hourly_data = response.json()

            hourly = parse_nws_hourly_forecast(hourly_data, location)
            pressure_data = await _fetch_nws_gridpoint_pressure(
                grid_data,
                new_client,
                headers,
            )
            return apply_nws_gridpoint_pressure(hourly, pressure_data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS hourly forecast: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None


async def _fetch_nws_gridpoint_pressure(
    point_data: dict[str, Any],
    client: httpx.AsyncClient,
    headers: dict[str, str],
) -> dict[datetime, tuple[float | None, float | None]]:
    """Fetch and parse the NWS gridpoint pressure layer for hourly pressure outlooks."""
    gridpoint_url = point_data.get("properties", {}).get("forecastGridData")
    if not gridpoint_url:
        return {}

    try:
        response = await _client_get(client, gridpoint_url, headers=headers)
        response.raise_for_status()
        return parse_nws_gridpoint_pressure(response.json())
    except Exception as exc:  # noqa: BLE001
        logger.debug("NWS gridpoint pressure fetch failed: %s", exc)
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return {}
