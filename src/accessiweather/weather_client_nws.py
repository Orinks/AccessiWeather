"""NWS API client methods for fetching and parsing weather data from the National Weather Service."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

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
from .utils.retry_utils import (
    RETRYABLE_EXCEPTIONS,
    async_retry_with_backoff,
    is_retryable_http_error,
)
from .weather_client_parsers import (
    convert_pa_to_inches,
    convert_pa_to_mb,
    convert_wind_speed_to_mph_and_kph,
)

logger = logging.getLogger(__name__)

MAX_STATION_OBSERVATION_ATTEMPTS = 10
MAX_OBSERVATION_AGE = timedelta(hours=2)
VALID_QC_CODES = {"V", "C", None}


def _parse_iso_datetime(value: Any) -> datetime | None:
    """
    Parse ISO formatted timestamps, ensuring timezone awareness.

    NWS returns ISO 8601 strings that should be timezone-aware.
    This function ensures all parsed datetimes have timezone information to
    prevent display issues when mixing naive and timezone-aware datetimes.
    """
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        # Ensure timezone-aware datetime
        if dt.tzinfo is None:
            # If naive, assume UTC (NWS typically provides UTC timestamps)
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def _station_sort_key(feature: dict[str, Any]) -> tuple[int, float, str]:
    """Prefer ICAO stations (Kxxx) first, then other 4-letter, then everything else."""
    props = feature.get("properties", {}) or {}
    station_id = str(props.get("stationIdentifier") or "").upper()
    distance = props.get("distance", {}) or {}
    distance_value = distance.get("value")
    try:
        distance_value = float(distance_value)
    except (TypeError, ValueError):
        distance_value = float("inf")

    if len(station_id) == 4 and station_id.startswith("K"):
        priority = 0
    elif len(station_id) == 4:
        priority = 1
    else:
        priority = 2
    return (priority, distance_value, station_id)


def _scrub_measurements(properties: dict[str, Any]) -> None:
    """Set measurement values with failing QC codes to None so they are ignored downstream."""
    keys = (
        "temperature",
        "dewpoint",
        "windSpeed",
        "windGust",
        "barometricPressure",
        "seaLevelPressure",
        "visibility",
        "relativeHumidity",
        "windDirection",
        "windChill",
        "heatIndex",
    )
    for key in keys:
        measurement = properties.get(key)
        if isinstance(measurement, dict):
            qc = measurement.get("qualityControl")
            if qc not in VALID_QC_CODES:
                measurement["value"] = None


def _current_data_score(current: CurrentConditions) -> int:
    """Score how much usable data is present to compare fallbacks."""
    values = [
        current.temperature_f,
        current.temperature_c,
        current.condition if current.condition and current.condition.strip() else None,
        current.humidity,
        current.dewpoint_f,
        current.wind_speed_mph,
        current.pressure_in,
        current.visibility_miles,
        current.uv_index,
    ]
    return sum(1 for value in values if value not in (None, ""))


def _extract_scalar(value: Any) -> Any:
    """Recursively extract a scalar value from nested NWS response objects."""
    if isinstance(value, dict):
        if "value" in value:
            return _extract_scalar(value["value"])
        if "values" in value and isinstance(value["values"], list):
            for item in value["values"]:
                extracted = _extract_scalar(item)
                if extracted is not None:
                    return extracted
        return None
    if isinstance(value, list):
        for item in value:
            extracted = _extract_scalar(item)
            if extracted is not None:
                return extracted
        return None
    return value


def _extract_float(value: Any) -> float | None:
    """Extract a float from an NWS response value."""
    scalar = _extract_scalar(value)
    if isinstance(scalar, (int, float)):
        return float(scalar)
    if isinstance(scalar, str):
        try:
            return float(scalar)
        except ValueError:
            return None
    return None


def _format_unit(unit_code: str | None) -> str | None:
    """Return a human-readable suffix for WMO unit codes."""
    if not unit_code:
        return None
    unit = unit_code.split(":")[-1]
    replacements = {
        "km_h-1": " km/h",
        "m_s-1": " m/s",
        "mi_h-1": " mph",
        "kn": " kn",
        "kt": " kt",
    }
    return replacements.get(unit, f" {unit}")


def _format_wind_speed(value: Any) -> str | None:
    """Format NWS wind speed objects into a readable string."""
    if value is None:
        return None
    if isinstance(value, dict):
        unit_code = value.get("unitCode")
        numeric = _extract_float(value.get("value"))
        if numeric is None:
            # Quantized payloads sometimes expose only min/max values
            max_value = _extract_float(value.get("maxValue"))
            min_value = _extract_float(value.get("minValue"))
            if max_value is not None:
                numeric = max_value
            elif min_value is not None:
                numeric = min_value
        if numeric is None:
            return None
        mph, kph = convert_wind_speed_to_mph_and_kph(numeric, unit_code)
        if mph is not None and kph is not None:
            return f"{round(mph)} mph ({round(kph)} km/h)"
        if mph is not None:
            return f"{round(mph)} mph"
        if kph is not None:
            return f"{round(kph)} km/h"
        suffix = _format_unit(unit_code)
        return f"{numeric}{suffix}" if suffix else str(numeric)
    scalar = _extract_scalar(value)
    if scalar is None:
        return None
    if isinstance(scalar, (int, float)):
        return f"{scalar}"
    return str(scalar)


def _normalize_temperature_unit(unit: Any) -> str | None:
    """Normalize temperature unit hints to ``F`` or ``C``."""
    raw = _extract_scalar(unit)
    if not isinstance(raw, str):
        return None
    normalized = raw.strip().lower()
    if ":" in normalized:
        normalized = normalized.split(":", 1)[-1]
    normalized = normalized.replace("degree", "")
    normalized = normalized.replace("deg", "")
    normalized = normalized.replace("fahrenheit", "f")
    normalized = normalized.replace("celsius", "c")
    normalized = normalized.replace("wmounit", "")
    normalized = normalized.replace("°", "")
    normalized = normalized.replace("_", "")
    if normalized.endswith("f"):
        return "F"
    if normalized.endswith("c"):
        return "C"
    if normalized in {"f", "c"}:
        return normalized.upper()
    return None


def _extract_temperature(measurement: Any, unit_hint: Any = None) -> tuple[float | None, str]:
    """Extract and normalize a temperature measurement to Fahrenheit."""
    unit = _normalize_temperature_unit(unit_hint) or "F"

    numeric = None
    if isinstance(measurement, dict):
        numeric = _extract_float(measurement.get("value"))
        if numeric is None:
            numeric = _extract_float(measurement.get("maxValue"))
        if numeric is None:
            numeric = _extract_float(measurement.get("minValue"))
        measurement_unit = _normalize_temperature_unit(measurement.get("unitCode"))
        if measurement_unit is not None:
            unit = measurement_unit
    else:
        numeric = _extract_float(measurement)

    if numeric is None:
        return None, unit

    if unit == "C":
        numeric = (numeric * 9 / 5) + 32
        unit = "F"

    return numeric, unit


async def _client_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    """Call AsyncClient.get allowing for mocked synchronous responses in tests."""
    response = client.get(url, headers=headers, params=params)
    if inspect.isawaitable(response):
        return await response
    return response


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
    WeatherAlerts | None,
    HourlyForecast | None,
]:
    """
    Fetch all NWS data in parallel with optimized grid data caching.

    Returns: (current, forecast, discussion, alerts, hourly_forecast)
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
        forecast, discussion = await forecast_task
        alerts = await alerts_task
        hourly_forecast = await hourly_task

        return current, forecast, discussion, alerts, hourly_forecast

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS data in parallel: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None, None, None, None, None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_current_conditions(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> CurrentConditions | None:
    """Fetch current conditions from the NWS API for the given location."""
    try:
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
        headers = {"User-Agent": user_agent}

        async def _select_best_observation(
            features: list[dict[str, Any]],
            http_client: httpx.AsyncClient,
        ) -> CurrentConditions | None:
            """Return the first observation with meaningful data, keeping a fallback."""
            if not features:
                return None

            fallback: CurrentConditions | None = None
            fallback_rank: tuple[int, int, int] | None = None
            attempts = 0

            sorted_features = sorted(features, key=_station_sort_key)

            for feature in sorted_features:
                if attempts >= MAX_STATION_OBSERVATION_ATTEMPTS:
                    break

                props = feature.get("properties", {}) or {}
                station_id = props.get("stationIdentifier")
                if not station_id:
                    continue

                obs_url = f"{nws_base_url}/stations/{station_id}/observations/latest"
                attempts += 1

                try:
                    response = await _client_get(http_client, obs_url, headers=headers)
                    response.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to fetch observation for %s: %s", station_id, exc)
                    continue

                try:
                    obs_data = response.json()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Invalid observation payload for %s: %s", station_id, exc)
                    continue

                obs_props = obs_data.get("properties", {}) or {}
                timestamp = _parse_iso_datetime(obs_props.get("timestamp"))
                stale = False
                if timestamp is not None:
                    if timestamp.tzinfo is None:
                        timestamp_utc = timestamp.replace(tzinfo=UTC)
                    else:
                        timestamp_utc = timestamp.astimezone(UTC)
                    age = datetime.now(UTC) - timestamp_utc
                    if age > MAX_OBSERVATION_AGE:
                        stale = True
                else:
                    stale = True

                try:
                    _scrub_measurements(obs_props)
                    current = parse_nws_current_conditions(obs_data, location=location)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to parse observation for %s: %s", station_id, exc)
                    continue

                has_temperature = (
                    current.temperature_f is not None or current.temperature_c is not None
                )
                has_description = bool(current.condition and current.condition.strip())
                score = _current_data_score(current)

                if not stale and (has_temperature or has_description):
                    return current

                if score == 0:
                    continue

                rank = (1 if stale else 0, -score, attempts)
                if fallback_rank is None or rank < fallback_rank:
                    fallback = current
                    fallback_rank = rank

            return fallback

        # Use provided client or create a new one
        if client is not None:
            response = await _client_get(client, grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            # Extract timezone from grid data and update location
            if "properties" in grid_data and "timeZone" in grid_data["properties"]:
                location.timezone = grid_data["properties"]["timeZone"]

            stations_url = grid_data["properties"]["observationStations"]
            response = await _client_get(client, stations_url, headers=headers)
            response.raise_for_status()
            stations_data = response.json()

            if not stations_data["features"]:
                logger.warning("No observation stations found")
                return None

            current = await _select_best_observation(stations_data["features"], client)
            if current is None:
                logger.warning(
                    "No usable observations found for %s (lat=%s, lon=%s)",
                    location.name,
                    location.latitude,
                    location.longitude,
                )
            return current
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            # Extract timezone from grid data and update location
            if "properties" in grid_data and "timeZone" in grid_data["properties"]:
                location.timezone = grid_data["properties"]["timeZone"]

            stations_url = grid_data["properties"]["observationStations"]
            response = await new_client.get(stations_url, headers=headers)
            response.raise_for_status()
            stations_data = response.json()

            if not stations_data["features"]:
                logger.warning("No observation stations found")
                return None

            current = await _select_best_observation(stations_data["features"], new_client)
            if current is None:
                logger.warning(
                    "No usable observations found for %s (lat=%s, lon=%s)",
                    location.name,
                    location.latitude,
                    location.longitude,
                )
            return current

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS current conditions: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None


async def get_nws_primary_station_info(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> tuple[str | None, str | None]:
    """Return the primary observation station identifier and name for a location."""
    try:
        headers = {"User-Agent": user_agent}
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        if client is not None:
            response = await _client_get(client, grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()
            stations_url = grid_data.get("properties", {}).get("observationStations")
            if not stations_url:
                logger.debug("No observationStations URL in NWS grid data")
                return None, None

            response = await _client_get(client, stations_url, headers=headers)
            response.raise_for_status()
            stations_data = response.json()
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
                response = await new_client.get(grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()
                stations_url = grid_data.get("properties", {}).get("observationStations")
                if not stations_url:
                    logger.debug("No observationStations URL in NWS grid data")
                    return None, None

                response = await new_client.get(stations_url, headers=headers)
                response.raise_for_status()
                stations_data = response.json()

        features = stations_data.get("features", [])
        if not features:
            logger.debug("No observation station features returned")
            return None, None

        station_props = features[0].get("properties", {})
        station_id = station_props.get("stationIdentifier")
        station_name = station_props.get("name")
        return station_id, station_name
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to look up primary station info: {exc}")
        return None, None


async def get_nws_station_metadata(
    station_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Fetch metadata for a specific station."""
    if not station_id:
        return None

    headers = {"User-Agent": user_agent}
    station_url = f"{nws_base_url}/stations/{station_id}"

    try:
        if client is not None:
            response = await _client_get(client, station_url, headers=headers)
            response.raise_for_status()
            return response.json()

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(station_url, headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Failed to fetch station metadata for {station_id}: {exc}")
        return None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_forecast_and_discussion(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
    grid_data: dict[str, Any] | None = None,
) -> tuple[Forecast | None, str | None]:
    """Fetch forecast and discussion from the NWS API for the given location."""
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

            forecast_url = grid_data["properties"]["forecast"]
            response = await _client_get(client, forecast_url, headers=feature_headers)
            response.raise_for_status()
            forecast_data = response.json()

            discussion = await get_nws_discussion(client, headers, grid_data, nws_base_url)

            return parse_nws_forecast(forecast_data), discussion
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            forecast_url = grid_data["properties"]["forecast"]
            response = await new_client.get(forecast_url, headers=feature_headers)
            response.raise_for_status()
            forecast_data = response.json()

            discussion = await get_nws_discussion(new_client, headers, grid_data, nws_base_url)

            return parse_nws_forecast(forecast_data), discussion

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS forecast and discussion: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None, None


async def get_nws_discussion(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    grid_data: dict[str, Any],
    nws_base_url: str,
) -> str:
    """Fetch the NWS Area Forecast Discussion (AFD) for the given grid data."""
    try:
        forecast_url = grid_data.get("properties", {}).get("forecast")
        if not forecast_url:
            logger.warning("No forecast URL found in grid data")
            return "Forecast discussion not available."

        parts = forecast_url.split("/")
        if len(parts) < 6:
            logger.warning(f"Unexpected forecast URL format: {forecast_url}")
            return "Forecast discussion not available."

        office_id = parts[-3]
        logger.info(f"Fetching AFD for office: {office_id}")

        products_url = f"{nws_base_url}/products/types/AFD/locations/{office_id}"
        response = await _client_get(client, products_url, headers=headers)

        if response.status_code != 200:
            logger.warning(f"Failed to get AFD products: HTTP {response.status_code}")
            return "Forecast discussion not available."

        products_data = response.json()

        if not products_data.get("@graph"):
            logger.warning(f"No AFD products found for office {office_id}")
            return "Forecast discussion not available for this location."

        latest_product = products_data["@graph"][0]
        latest_product_id = latest_product.get("id")
        if not latest_product_id:
            logger.warning("No product ID found in latest AFD product")
            return "Forecast discussion not available."

        product_url = f"{nws_base_url}/products/{latest_product_id}"
        response = await _client_get(client, product_url, headers=headers)

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

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS discussion: {exc}")
        return "Forecast discussion not available due to error."


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_alerts(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> WeatherAlerts | None:
    """Fetch weather alerts from the NWS API."""
    try:
        alerts_url = f"{nws_base_url}/alerts/active"
        params = {
            "point": f"{location.latitude},{location.longitude}",
            "status": "actual",
            "message_type": "alert",
        }
        headers = {"User-Agent": user_agent}

        # Use provided client or create a new one
        if client is not None:
            response = await _client_get(client, alerts_url, headers=headers, params=params)
            response.raise_for_status()
            alerts_data = response.json()
            return parse_nws_alerts(alerts_data)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(alerts_url, params=params, headers=headers)
            response.raise_for_status()
            alerts_data = response.json()
            return parse_nws_alerts(alerts_data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS alerts: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return WeatherAlerts(alerts=[])


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

            return parse_nws_hourly_forecast(hourly_data)
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

            return parse_nws_hourly_forecast(hourly_data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS hourly forecast: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_tafs(
    station_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> str | None:
    """Fetch the most recent Terminal Aerodrome Forecast for a station."""
    del timeout  # The caller manages the async client lifecycle.

    taf_url = f"{nws_base_url}/stations/{station_id}/tafs"
    headers = {"User-Agent": user_agent}

    try:
        response = await _client_get(client, taf_url, headers=headers)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.debug("NWS TAF request failed for %s: %s", station_id, exc)
        response = None

    raw_taf: str | None = None
    if response is not None:
        try:
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to parse NWS TAF response for %s: %s", station_id, exc)
            data = None

        if isinstance(data, dict):
            features = data.get("features")
            if isinstance(features, list):
                for feature in features:
                    properties = feature.get("properties", {})
                    raw_message = properties.get("rawMessage") or properties.get("rawTAF")
                    if raw_message:
                        raw_taf = str(raw_message).strip()
                        if raw_taf:
                            return raw_taf

        logger.debug(
            "NWS TAF response for %s did not include a raw message. Falling back to AviationWeather.gov.",
            station_id,
        )

    # Fallback to the AviationWeather.gov JSON API which provides rawTAF fields.
    awc_url = "https://aviationweather.gov/api/data/taf"
    awc_headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }
    params = {"ids": station_id, "format": "json"}

    try:
        awc_response = await _client_get(client, awc_url, headers=awc_headers, params=params)
        awc_response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch TAF from AviationWeather for %s: %s", station_id, exc)
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None

    try:
        awc_data = awc_response.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to decode AviationWeather TAF JSON for %s: %s", station_id, exc)
        return None

    entries: list[dict[str, Any]] = []
    if isinstance(awc_data, list):
        entries = [entry for entry in awc_data if isinstance(entry, dict)]
    elif isinstance(awc_data, dict):
        raw_entries = awc_data.get("data") or awc_data.get("results") or awc_data.get("tafs")
        if isinstance(raw_entries, list):
            entries = [entry for entry in raw_entries if isinstance(entry, dict)]

    for entry in entries:
        raw_message = entry.get("rawTAF") or entry.get("raw_taf")
        if raw_message:
            cleaned = str(raw_message).strip()
            if cleaned:
                return cleaned

    logger.debug("AviationWeather API returned no usable TAF data for %s", station_id)
    return None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_sigmets(
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
    *,
    atsu: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch active SIGMET or AIRMET advisories."""
    del timeout

    sigmet_url = f"{nws_base_url}/aviation/sigmets"
    headers = {"User-Agent": user_agent}
    params: dict[str, Any] | None = {"atsu": atsu} if atsu else None

    try:
        response = await _client_get(client, sigmet_url, headers=headers, params=params)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to fetch SIGMET data: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return []

    data = response.json()
    features = data.get("features", [])
    return [feature.get("properties", feature) for feature in features]


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_cwas(
    cwsu_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    """Fetch Center Weather Advisories for a CWSU identifier."""
    del timeout

    cwa_url = f"{nws_base_url}/aviation/cwsus/{cwsu_id}/cwas"
    headers = {"User-Agent": user_agent}

    try:
        response = await _client_get(client, cwa_url, headers=headers)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to fetch CWA data for {cwsu_id}: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return []

    data = response.json()
    features = data.get("features", [])
    return [feature.get("properties", feature) for feature in features]


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_radar_profiler(
    station_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> dict[str, Any] | None:
    """Fetch metadata for a radar wind profiler station."""
    del timeout

    profiler_url = f"{nws_base_url}/radar/profilers/{station_id}"
    headers = {"User-Agent": user_agent}

    try:
        response = await _client_get(client, profiler_url, headers=headers)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to fetch radar profiler {station_id}: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None

    return response.json()


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_marine_forecast(
    zone_type: str,
    zone_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> dict[str, Any] | None:
    """Fetch a marine zone forecast."""
    del timeout

    marine_url = f"{nws_base_url}/zones/{zone_type}/{zone_id}/forecast"
    headers = {"User-Agent": user_agent}

    try:
        response = await _client_get(client, marine_url, headers=headers)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to fetch marine forecast for {zone_type}/{zone_id}: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None

    return response.json()


def parse_nws_current_conditions(
    data: dict,
    location: Location | None = None,
) -> CurrentConditions:
    """
    Parse NWS current conditions payload into a CurrentConditions model.

    Args:
    ----
        data: NWS API response payload
        location: Location object with timezone info. If provided, timestamps
                  will be converted to the location's local timezone.

    """
    props = data.get("properties", {})

    temp_c = props.get("temperature", {}).get("value")
    temp_f = (temp_c * 9 / 5) + 32 if temp_c is not None else None

    humidity = props.get("relativeHumidity", {}).get("value")
    humidity = round(humidity) if humidity is not None else None

    dewpoint_c = props.get("dewpoint", {}).get("value")
    dewpoint_f = (dewpoint_c * 9 / 5) + 32 if dewpoint_c is not None else None

    visibility_m = props.get("visibility", {}).get("value")
    visibility_miles = visibility_m / 1609.344 if visibility_m is not None else None
    visibility_km = visibility_m / 1000 if visibility_m is not None else None

    uv_index_value = props.get("uvIndex", {}).get("value")
    uv_index = None
    if uv_index_value is not None:
        try:
            uv_index = float(uv_index_value)
        except (TypeError, ValueError):
            uv_index = None

    wind_speed = props.get("windSpeed", {})
    wind_speed_value = wind_speed.get("value")
    wind_speed_unit = wind_speed.get("unitCode")
    wind_speed_mph, wind_speed_kph = convert_wind_speed_to_mph_and_kph(
        wind_speed_value, wind_speed_unit
    )

    wind_direction = props.get("windDirection", {}).get("value")

    pressure_pa = props.get("barometricPressure", {}).get("value")
    pressure_in = convert_pa_to_inches(pressure_pa)

    timestamp = props.get("timestamp")
    last_updated = None
    if isinstance(timestamp, str) and timestamp:
        try:
            last_updated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            # Convert UTC timestamp to location's timezone if available
            if last_updated and location:
                location_tz = None
                if location.timezone:
                    try:
                        location_tz = ZoneInfo(location.timezone)
                    except Exception as e:  # noqa: BLE001
                        logger.debug(f"Failed to load timezone '{location.timezone}': {e}")

                # If no timezone set, try to infer from coordinates using timezonefinder
                if not location_tz:
                    try:
                        from timezonefinder import TimezoneFinder

                        tf = TimezoneFinder()
                        tz_name = tf.timezone_at(lat=location.latitude, lng=location.longitude)
                        if tz_name:
                            location_tz = ZoneInfo(tz_name)
                            logger.info(
                                f"Inferred timezone '{tz_name}' for {location.name} "
                                f"from coordinates ({location.latitude}, {location.longitude})"
                            )
                        else:
                            logger.warning(
                                f"timezonefinder returned None for {location.name} "
                                f"at ({location.latitude}, {location.longitude})"
                            )
                    except ImportError:
                        logger.warning("timezonefinder not available, keeping times in UTC")
                    except Exception as e:  # noqa: BLE001
                        logger.error(f"Failed to infer timezone from coordinates: {e}")

                # Apply timezone conversion if we have a timezone
                if location_tz:
                    last_updated = last_updated.astimezone(location_tz)
                    logger.info(
                        f"Converted last_updated from UTC to {location_tz} for {location.name}: {last_updated}"
                    )
                else:
                    logger.warning(
                        f"No timezone available for {location.name}, keeping time in UTC"
                    )
        except ValueError:
            logger.debug(f"Failed to parse observation timestamp: {timestamp}")

    return CurrentConditions(
        temperature_f=temp_f,
        temperature_c=temp_c,
        condition=props.get("textDescription"),
        humidity=humidity,
        dewpoint_f=dewpoint_f,
        dewpoint_c=dewpoint_c,
        wind_speed_mph=wind_speed_mph,
        wind_speed_kph=wind_speed_kph,
        wind_direction=wind_direction,
        pressure_in=pressure_in,
        pressure_mb=convert_pa_to_mb(pressure_pa),
        feels_like_f=None,
        feels_like_c=None,
        visibility_miles=visibility_miles,
        visibility_km=visibility_km,
        uv_index=uv_index,
        last_updated=last_updated or datetime.now(),
    )


def parse_nws_forecast(data: dict) -> Forecast:
    """Parse NWS forecast payload into a Forecast model."""
    periods = []

    for period_data in data.get("properties", {}).get("periods", []):
        temperature, temperature_unit = _extract_temperature(
            period_data.get("temperature"), period_data.get("temperatureUnit")
        )

        wind_direction_value = _extract_scalar(period_data.get("windDirection"))
        wind_direction = str(wind_direction_value) if wind_direction_value is not None else None

        # Parse timestamps
        start_time = None
        end_time = None
        if period_data.get("startTime"):
            try:
                start_time = datetime.fromisoformat(period_data["startTime"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                logger.warning(f"Failed to parse startTime: {period_data.get('startTime')}")

        if period_data.get("endTime"):
            try:
                end_time = datetime.fromisoformat(period_data["endTime"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                logger.warning(f"Failed to parse endTime: {period_data.get('endTime')}")

        period = ForecastPeriod(
            name=period_data.get("name", ""),
            temperature=temperature,
            temperature_unit=str(temperature_unit),
            short_forecast=period_data.get("shortForecast"),
            detailed_forecast=period_data.get("detailedForecast"),
            wind_speed=_format_wind_speed(period_data.get("windSpeed")),
            wind_direction=wind_direction,
            icon=period_data.get("icon"),
            start_time=start_time,
            end_time=end_time,
        )
        periods.append(period)

    return Forecast(periods=periods, generated_at=datetime.now())


def parse_nws_alerts(data: dict) -> WeatherAlerts:
    """Parse NWS alerts payload into a WeatherAlerts collection."""
    alerts: list[WeatherAlert] = []

    for alert_data in data.get("features", []):
        props = alert_data.get("properties", {})

        alert_id = None
        if "id" in alert_data:
            alert_id = alert_data["id"]
        elif "identifier" in props:
            alert_id = props["identifier"]
        elif "@id" in props:
            alert_id = props["@id"]

        onset = None
        expires = None
        sent = None
        effective = None

        if props.get("onset"):
            try:
                onset = datetime.fromisoformat(props["onset"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse onset time: {props['onset']}")

        if props.get("expires"):
            try:
                expires = datetime.fromisoformat(props["expires"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse expires time: {props['expires']}")

        if props.get("sent"):
            try:
                sent = datetime.fromisoformat(props["sent"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse sent time: {props['sent']}")

        if props.get("effective"):
            try:
                effective = datetime.fromisoformat(props["effective"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse effective time: {props['effective']}")

        alert = WeatherAlert(
            title=props.get("headline", "Weather Alert"),
            description=props.get("description", ""),
            severity=props.get("severity", "Unknown"),
            urgency=props.get("urgency", "Unknown"),
            certainty=props.get("certainty", "Unknown"),
            event=props.get("event"),
            headline=props.get("headline"),
            instruction=props.get("instruction"),
            onset=onset,
            expires=expires,
            sent=sent,
            effective=effective,
            areas=props.get("areaDesc", "").split("; ") if props.get("areaDesc") else [],
            id=alert_id,
            source="NWS",
        )
        alerts.append(alert)

        if alert_id:
            logger.debug(f"Parsed alert with ID: {alert_id}")
        else:
            logger.debug("Parsed alert without ID, will generate unique ID")

    logger.info(f"Parsed {len(alerts)} alerts from NWS API")
    return WeatherAlerts(alerts=alerts)


def parse_nws_hourly_forecast(data: dict) -> HourlyForecast:
    """Parse NWS hourly forecast payload into an HourlyForecast model."""
    periods = []

    for period_data in data.get("properties", {}).get("periods", []):
        start_time_str = period_data.get("startTime")
        start_time = None
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse start time: {start_time_str}")

        end_time_str = period_data.get("endTime")
        end_time = None
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse end time: {end_time_str}")

        temperature, temperature_unit = _extract_temperature(
            period_data.get("temperature"), period_data.get("temperatureUnit")
        )

        wind_direction_value = _extract_scalar(period_data.get("windDirection"))
        wind_direction = str(wind_direction_value) if wind_direction_value is not None else None

        period = HourlyForecastPeriod(
            start_time=start_time or datetime.now(),
            end_time=end_time,
            temperature=temperature,
            temperature_unit=str(temperature_unit),
            short_forecast=period_data.get("shortForecast"),
            wind_speed=_format_wind_speed(period_data.get("windSpeed")),
            wind_direction=wind_direction,
            icon=period_data.get("icon"),
        )
        periods.append(period)

    return HourlyForecast(periods=periods, generated_at=datetime.now())
