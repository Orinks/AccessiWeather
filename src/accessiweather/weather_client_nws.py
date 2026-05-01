"""NWS API compatibility surface for weather data helpers."""
# ruff: noqa: F401

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from . import weather_client_nws_common as _common
from .models import CurrentConditions, Forecast, HourlyForecast, Location, WeatherAlerts
from .utils.retry_utils import (
    RETRYABLE_EXCEPTIONS,
    async_retry_with_backoff,
    is_retryable_http_error,
)
from .weather_client_nws_alerts import fetch_nws_cancel_references, get_nws_alerts
from .weather_client_nws_aviation import (
    get_nws_cwas,
    get_nws_marine_forecast,
    get_nws_radar_profiler,
    get_nws_sigmets,
    get_nws_tafs,
)
from .weather_client_nws_common import _client_get, _extract_wind_speed_mph, logger
from .weather_client_nws_current import (
    get_nws_current_conditions,
    get_nws_primary_station_info,
    get_nws_station_metadata,
)
from .weather_client_nws_forecast import (
    TextProductFetchError,
    get_nws_discussion,
    get_nws_discussion_only,
    get_nws_forecast_and_discussion,
    get_nws_text_product,
)
from .weather_client_nws_hourly import _fetch_nws_gridpoint_pressure, get_nws_hourly_forecast
from .weather_client_nws_parsers import (
    apply_nws_gridpoint_pressure,
    parse_nws_alerts,
    parse_nws_current_conditions,
    parse_nws_forecast,
    parse_nws_gridpoint_pressure,
    parse_nws_hourly_forecast,
)

wx = _common.wx


def set_zone_drift_sink(sink):
    """Register the zone drift sink on the shared NWS implementation."""
    _common.set_zone_drift_sink(sink)


def _apply_zone_drift_correction(location: Location, point_data: dict | None) -> None:
    """Compatibility wrapper that honors patches to weather_client_nws.wx."""
    _common.wx = wx
    _common._apply_zone_drift_correction(location, point_data)


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=30.0)
async def get_nws_all_data_parallel(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> tuple[
    CurrentConditions | None,
    Forecast | None,
    str | None,
    datetime | None,
    WeatherAlerts | None,
    HourlyForecast | None,
]:
    """
    Fetch all NWS data in parallel with optimized grid data caching.

    Returns: (current, forecast, discussion, discussion_issuance_time, alerts, hourly_forecast)
    """
    try:
        # First, fetch grid data once
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
        headers = {"User-Agent": user_agent}
        feature_headers = headers.copy()
        feature_headers["Feature-Flags"] = "forecast_temperature_qv, forecast_wind_speed_qv"

        response = await _client_get(client, grid_url, headers=headers)
        response.raise_for_status()
        grid_data = response.json()

        # Opportunistic zone-metadata drift correction. Never raises.
        _apply_zone_drift_correction(location, grid_data)

        # Now fetch all other data in parallel, reusing grid_data
        current_task = asyncio.create_task(
            get_nws_current_conditions(location, nws_base_url, user_agent, timeout, client)
        )
        forecast_task = asyncio.create_task(
            get_nws_forecast_and_discussion(
                location, nws_base_url, user_agent, timeout, client, grid_data
            )
        )
        alerts_task = asyncio.create_task(
            get_nws_alerts(location, nws_base_url, user_agent, timeout, client)
        )
        hourly_task = asyncio.create_task(
            get_nws_hourly_forecast(location, nws_base_url, user_agent, timeout, client, grid_data)
        )

        # Gather all results
        current = await current_task
        forecast, discussion, discussion_issuance_time = await forecast_task
        alerts = await alerts_task
        hourly_forecast = await hourly_task

        return current, forecast, discussion, discussion_issuance_time, alerts, hourly_forecast

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS data in parallel: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None, None, None, None, None, None
