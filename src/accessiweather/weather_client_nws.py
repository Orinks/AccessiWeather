"""NWS API client methods for fetching and parsing weather data from the National Weather Service."""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx

from .models import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TextProduct,
    WeatherAlert,
    WeatherAlerts,
)
from .services.zone_enrichment_service import (
    _extract_zone_fields,
    diff_zone_fields,
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

# wxPython is an optional runtime dep. Import lazily via a module-level handle
# so tests (and headless CI) can patch or stub it without importing the full
# wx package. When wx is unavailable, CallAfter becomes a best-effort direct
# call — acceptable since the drift hook is a no-op under those conditions
# (no sink is registered in non-GUI test contexts).
try:
    import wx  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - handled at runtime
    wx = None  # type: ignore[assignment]

# Registered drift-correction sink. Wired up by app initialization to point at
# the application's ``LocationOperations`` instance. Unit tests register their
# own sink directly. The hook is a silent no-op until a sink is installed.
_ZONE_DRIFT_SINK: Any = None

logger = logging.getLogger(__name__)


def set_zone_drift_sink(sink: Any) -> None:
    """
    Register (or clear) the object used to persist drift-corrected zone fields.

    The ``sink`` must expose an ``update_zone_metadata(location_name, fields)``
    callable — typically a :class:`accessiweather.config.locations.LocationOperations`
    instance. Pass ``None`` to clear.

    This is intentionally a module-global registration: weather-client HTTP
    helpers are shared across the app and cannot easily thread an extra
    dependency through every signature. Wiring is performed once during app
    startup; tests install/clear the sink as needed.
    """
    global _ZONE_DRIFT_SINK
    _ZONE_DRIFT_SINK = sink


def _apply_zone_drift_correction(location: Location, point_data: dict[str, Any] | None) -> None:
    """
    Diff fresh ``/points`` properties against ``location`` and persist drift.

    Called from the weather-refresh thread after each successful ``/points``
    fetch. Never raises: a drift bug must never cascade into breaking the
    weather refresh flow.

    Persistence is funneled through ``wx.CallAfter`` so that the main thread
    performs the actual config write — ``ConfigManager.save_config`` has no
    in-process lock, and main-thread bounce is the smallest correct fix.
    """
    sink = _ZONE_DRIFT_SINK
    if sink is None:
        return
    try:
        if not isinstance(point_data, dict):
            return
        properties = point_data.get("properties")
        if not isinstance(properties, dict):
            return

        fresh_fields = _extract_zone_fields(properties)
        changes = diff_zone_fields(location, fresh_fields)
        if not changes:
            return

        persist = getattr(sink, "update_zone_metadata", None)
        if persist is None:
            return

        call_after = getattr(wx, "CallAfter", None) if wx is not None else None
        if call_after is None:
            # No wx event loop available — skip silently rather than writing
            # from a background thread unprotected.
            logger.debug("Zone drift: wx.CallAfter unavailable, skipping persist")
            return

        call_after(persist, location.name, changes)
        logger.debug(
            "Zone drift: scheduled update for %s: %s",
            location.name,
            sorted(changes.keys()),
        )
    except Exception as exc:  # noqa: BLE001 - must never break refresh
        logger.debug("Zone drift correction raised (suppressed): %s", exc)


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
                logger.debug(
                    "Scrubbed measurement %r due to invalid QC code %r (valid: %s)",
                    key,
                    qc,
                    VALID_QC_CODES,
                )


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
    if isinstance(scalar, int | float):
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
    if isinstance(scalar, int | float):
        return f"{scalar}"
    return str(scalar)


def _extract_wind_speed_mph(value: Any) -> float | None:
    """Extract numeric mph from a NWS windSpeed value (dict or string)."""
    if value is None:
        return None
    if isinstance(value, dict):
        unit_code = value.get("unitCode")
        numeric = _extract_float(value.get("value"))
        if numeric is None:
            numeric = _extract_float(value.get("maxValue"))
        if numeric is None:
            numeric = _extract_float(value.get("minValue"))
        if numeric is None:
            return None
        mph, _ = convert_wind_speed_to_mph_and_kph(numeric, unit_code)
        return mph
    scalar = _extract_scalar(value)
    if not isinstance(scalar, str):
        return None
    # Handles "15 mph", "5 to 15 mph" — use the last (highest) number before "mph"
    mph_matches = re.findall(r"(\d+(?:\.\d+)?)\s*mph", scalar, re.IGNORECASE)
    if mph_matches:
        return float(mph_matches[-1])
    # Handles km/h strings — convert to mph
    kmh_matches = re.findall(r"(\d+(?:\.\d+)?)\s*km/h", scalar, re.IGNORECASE)
    if kmh_matches:
        kph = float(kmh_matches[-1])
        mph, _ = convert_wind_speed_to_mph_and_kph(kph, "wmoUnit:km_h-1")
        return mph
    return None


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
) -> tuple[Forecast | None, str | None, datetime | None]:
    """
    Fetch forecast and discussion from the NWS API for the given location.

    Forecast and discussion fetches are independent: if the forecast fetch fails,
    the discussion is still returned (and vice versa).

    Returns:
        Tuple of (forecast, discussion_text, discussion_issuance_time)

    """
    try:
        headers = {"User-Agent": user_agent}
        feature_headers = headers.copy()
        feature_headers["Feature-Flags"] = "forecast_temperature_qv, forecast_wind_speed_qv"

        # Use provided client or create a new one
        if client is not None:
            # Fetch grid data if not provided (needed by both forecast and discussion)
            if grid_data is None:
                grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
                response = await _client_get(client, grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

            # Fetch forecast independently so a failure doesn't kill the discussion
            parsed_forecast: Forecast | None = None
            try:
                forecast_url = grid_data["properties"]["forecast"]
                response = await _client_get(client, forecast_url, headers=feature_headers)
                response.raise_for_status()
                parsed_forecast = parse_nws_forecast(response.json())
            except Exception as forecast_exc:  # noqa: BLE001
                logger.warning(
                    "Forecast fetch failed (discussion will still be returned): %s", forecast_exc
                )

            discussion, discussion_issuance_time = await get_nws_discussion(
                client, headers, grid_data, nws_base_url
            )
            logger.debug(
                "get_nws_forecast_and_discussion: forecast=%s discussion_len=%s issuance=%s",
                "ok" if parsed_forecast else "None",
                len(discussion) if discussion else 0,
                discussion_issuance_time,
            )

            return parsed_forecast, discussion, discussion_issuance_time

        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            # Fetch forecast independently so a failure doesn't kill the discussion
            parsed_forecast = None
            try:
                forecast_url = grid_data["properties"]["forecast"]
                response = await new_client.get(forecast_url, headers=feature_headers)
                response.raise_for_status()
                parsed_forecast = parse_nws_forecast(response.json())
            except Exception as forecast_exc:  # noqa: BLE001
                logger.warning(
                    "Forecast fetch failed (discussion will still be returned): %s", forecast_exc
                )

            discussion, discussion_issuance_time = await get_nws_discussion(
                new_client, headers, grid_data, nws_base_url
            )
            logger.debug(
                "get_nws_forecast_and_discussion: forecast=%s discussion_len=%s issuance=%s",
                "ok" if parsed_forecast else "None",
                len(discussion) if discussion else 0,
                discussion_issuance_time,
            )

            return parsed_forecast, discussion, discussion_issuance_time

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS forecast and discussion: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None, None, None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_discussion_only(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> tuple[str | None, datetime | None]:
    """
    Fetch only the NWS Area Forecast Discussion for a location.

    Lighter-weight than get_nws_forecast_and_discussion — skips the forecast
    fetch entirely.  Used by the notification event path so that a transient
    forecast API error never silently suppresses AFD update notifications.

    Returns:
        Tuple of (discussion_text, discussion_issuance_time).
        Returns (None, None) on unrecoverable error.

    """
    try:
        headers = {"User-Agent": user_agent}
        logger.debug(
            "get_nws_discussion_only: fetching grid data for %s,%s",
            location.latitude,
            location.longitude,
        )

        if client is not None:
            grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
            response = await _client_get(client, grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()
            discussion, issuance_time = await get_nws_discussion(
                client, headers, grid_data, nws_base_url
            )
            logger.debug(
                "get_nws_discussion_only: discussion_len=%s issuance=%s",
                len(discussion) if discussion else 0,
                issuance_time,
            )
            return discussion, issuance_time

        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()
            discussion, issuance_time = await get_nws_discussion(
                new_client, headers, grid_data, nws_base_url
            )
            logger.debug(
                "get_nws_discussion_only: discussion_len=%s issuance=%s",
                len(discussion) if discussion else 0,
                issuance_time,
            )
            return discussion, issuance_time

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch NWS discussion only: %s", exc)
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None, None


class TextProductFetchError(Exception):
    """
    Network, timeout, or non-200 response from the NWS /products endpoint.

    Distinct from the "empty @graph" case, which returns ``None`` (AFD/HWO) or
    ``[]`` (SPS) rather than raising.
    """


async def _fetch_text_product_by_id(
    client: httpx.AsyncClient,
    nws_base_url: str,
    headers: dict[str, str],
    product_type: Literal["AFD", "HWO", "SPS"],
    cwa_office: str,
    entry: dict[str, Any],
) -> TextProduct | None:
    """
    Fetch a single /products/{id} and return a TextProduct.

    Returns None for individual product fetches whose id is missing or whose
    response is missing productText — these are treated as best-effort skips
    rather than hard errors.
    """
    product_id = entry.get("id")
    if not product_id:
        logger.warning("No product ID in %s @graph entry for office %s", product_type, cwa_office)
        return None

    issuance_time = _parse_iso_datetime(entry.get("issuanceTime"))

    product_url = f"{nws_base_url}/products/{product_id}"
    response = await _client_get(client, product_url, headers=headers)
    if response.status_code != 200:
        logger.warning(
            "Failed to get %s product text (%s): HTTP %s",
            product_type,
            product_id,
            response.status_code,
        )
        raise TextProductFetchError(
            f"HTTP {response.status_code} fetching {product_type} product {product_id}"
        )

    product_data = response.json()
    product_text = product_data.get("productText")
    if not product_text:
        logger.warning("No productText in %s product %s", product_type, product_id)
        return None

    # Prefer product-level issuanceTime over @graph metadata when present.
    body_issuance = _parse_iso_datetime(product_data.get("issuanceTime"))
    if body_issuance is not None:
        issuance_time = body_issuance

    headline = product_data.get("headline") or entry.get("headline")
    if headline is not None and not isinstance(headline, str):
        headline = str(headline)

    return TextProduct(
        product_type=product_type,
        product_id=str(product_id),
        cwa_office=cwa_office,
        issuance_time=issuance_time,
        product_text=product_text,
        headline=headline,
    )


async def get_nws_text_product(
    product_type: Literal["AFD", "HWO", "SPS"],
    cwa_office: str | None,
    *,
    nws_base_url: str = "https://api.weather.gov",
    client: httpx.AsyncClient | None = None,
    timeout: float = 10.0,
    user_agent: str = "AccessiWeather (github.com/orinks/accessiweather)",
) -> TextProduct | list[TextProduct] | None:
    """
    Fetch an NWS text product (AFD / HWO / SPS) for a CWA office.

    Endpoint: ``/products/types/{product_type}/locations/{cwa_office}`` returns
    an ``@graph`` of product stubs; each is fetched individually via
    ``/products/{id}`` to get ``productText`` and metadata.

    Return convention:
        - ``cwa_office`` falsy -> ``None`` (no HTTP call).
        - AFD or HWO, empty ``@graph`` -> ``None``.
        - AFD or HWO, products present -> single ``TextProduct`` (newest @graph entry).
        - SPS -> ``list[TextProduct]`` (possibly empty), sorted newest-first.

    Raises:
        TextProductFetchError on network failure, timeout, or non-200 response
        from the NWS /products endpoints. Empty @graph is NOT an error.

    """
    if not cwa_office:
        return None

    headers = {"User-Agent": user_agent}
    products_url = f"{nws_base_url}/products/types/{product_type}/locations/{cwa_office}"

    async def _run(http_client: httpx.AsyncClient) -> TextProduct | list[TextProduct] | None:
        try:
            listing_response = await _client_get(http_client, products_url, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise TextProductFetchError(
                f"Request failed fetching {product_type} listing for {cwa_office}: {exc}"
            ) from exc

        if listing_response.status_code != 200:
            raise TextProductFetchError(
                f"HTTP {listing_response.status_code} fetching {product_type} "
                f"listing for {cwa_office}"
            )

        graph = listing_response.json().get("@graph") or []

        if product_type == "SPS":
            products: list[TextProduct] = []
            try:
                for entry in graph:
                    if not isinstance(entry, dict):
                        continue
                    tp = await _fetch_text_product_by_id(
                        http_client, nws_base_url, headers, product_type, cwa_office, entry
                    )
                    if tp is not None:
                        products.append(tp)
            except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
                raise TextProductFetchError(
                    f"Request failed fetching SPS product for {cwa_office}: {exc}"
                ) from exc

            products.sort(
                key=lambda p: p.issuance_time or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )
            return products

        # AFD or HWO: newest @graph entry only, or None if empty.
        if not graph:
            return None

        latest = graph[0]
        if not isinstance(latest, dict):
            return None

        try:
            return await _fetch_text_product_by_id(
                http_client, nws_base_url, headers, product_type, cwa_office, latest
            )
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise TextProductFetchError(
                f"Request failed fetching {product_type} product for {cwa_office}: {exc}"
            ) from exc

    if client is not None:
        return await _run(client)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


async def get_nws_discussion(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    grid_data: dict[str, Any],
    nws_base_url: str,
) -> tuple[str, datetime | None]:
    """
    Fetch the NWS Area Forecast Discussion (AFD) for the given grid data.

    Thin backward-compat wrapper around :func:`get_nws_text_product` for the AFD
    product type. Preserves the pre-existing ``(discussion_text, issuance_time)``
    tuple contract so existing internal callers continue to work unchanged.

    Returns:
        Tuple of (discussion_text, issuance_time). The issuance_time is parsed from
        the NWS API's issuanceTime field and can be used to detect when the AFD
        has been updated without comparing content.

    """
    try:
        forecast_url = grid_data.get("properties", {}).get("forecast")
        if not forecast_url:
            logger.warning("No forecast URL found in grid data")
            return "Forecast discussion not available.", None

        parts = forecast_url.split("/")
        if len(parts) < 6:
            logger.warning(f"Unexpected forecast URL format: {forecast_url}")
            return "Forecast discussion not available.", None

        office_id = parts[-3]
        logger.info(f"Fetching AFD for office: {office_id}")

        # Preserve existing User-Agent behavior by reusing caller-supplied headers.
        user_agent = headers.get("User-Agent", "AccessiWeather")

        try:
            product = await get_nws_text_product(
                "AFD",
                office_id,
                nws_base_url=nws_base_url,
                client=client,
                user_agent=user_agent,
            )
        except TextProductFetchError as exc:
            logger.warning("Failed to fetch AFD via text-product path: %s", exc)
            return "Forecast discussion not available.", None

        if product is None:
            logger.warning(f"No AFD products found for office {office_id}")
            return "Forecast discussion not available for this location.", None

        assert isinstance(product, TextProduct)  # AFD path never returns a list
        logger.info(f"Successfully fetched AFD for office {office_id}")
        return product.product_text, product.issuance_time

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS discussion: {exc}")
        return "Forecast discussion not available due to error.", None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_alerts(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
    alert_radius_type: str = "county",
) -> WeatherAlerts | None:
    """
    Fetch weather alerts from the NWS API.

    Args:
        location: The location to fetch alerts for
        nws_base_url: Base URL for NWS API
        user_agent: User agent string
        timeout: Request timeout
        client: Optional HTTP client to reuse
        alert_radius_type: "county", "point" (exact location), "zone" (forecast zone), or "state"

    """
    try:
        alerts_url = f"{nws_base_url}/alerts/active"
        headers = {"User-Agent": user_agent}

        # Build params based on alert_radius_type
        if alert_radius_type == "county":
            # Prefer the stored county_zone_id (populated by zone enrichment and
            # kept fresh by drift correction). This skips a redundant /points
            # round-trip on each refresh. Fall back to /points resolution when
            # the stored field is absent.
            if location.county_zone_id:
                params = {"zone": location.county_zone_id, "status": "actual"}
            else:
                # Get county zone from point data
                point_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
                if client is not None:
                    point_response = await _client_get(client, point_url, headers=headers)
                else:
                    async with httpx.AsyncClient(
                        timeout=timeout, follow_redirects=True
                    ) as new_client:
                        point_response = await new_client.get(point_url, headers=headers)
                point_response.raise_for_status()
                point_data = point_response.json()

                county_url = point_data.get("properties", {}).get("county")
                if county_url and "/county/" in county_url:
                    zone_id = county_url.split("/county/")[1]
                    params = {"zone": zone_id, "status": "actual"}
                else:
                    logger.warning("Could not determine county zone, falling back to point query")
                    params = {
                        "point": f"{location.latitude},{location.longitude}",
                        "status": "actual",
                    }

        elif alert_radius_type == "state":
            # Get state from location - need to fetch point data first
            point_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
            if client is not None:
                point_response = await _client_get(client, point_url, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
                    point_response = await new_client.get(point_url, headers=headers)
            point_response.raise_for_status()
            point_data = point_response.json()
            state = (
                point_data.get("properties", {})
                .get("relativeLocation", {})
                .get("properties", {})
                .get("state")
            )
            if state:
                params = {"area": state, "status": "actual"}
            else:
                # Fall back to point query if state not found
                logger.warning("Could not determine state, falling back to point query")
                params = {"point": f"{location.latitude},{location.longitude}", "status": "actual"}

        elif alert_radius_type == "zone":
            # Prefer the stored forecast_zone_id (populated by zone enrichment
            # and kept fresh by drift correction). This skips a redundant
            # /points round-trip on each refresh. Fall back to /points
            # resolution when the stored field is absent.
            if location.forecast_zone_id:
                params = {"zone": location.forecast_zone_id, "status": "actual"}
            else:
                # Get zone from point data
                point_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
                if client is not None:
                    point_response = await _client_get(client, point_url, headers=headers)
                else:
                    async with httpx.AsyncClient(
                        timeout=timeout, follow_redirects=True
                    ) as new_client:
                        point_response = await new_client.get(point_url, headers=headers)
                point_response.raise_for_status()
                point_data = point_response.json()

                # Try to get zone ID (prefer county, then forecast zone)
                zone_id = None
                county_url = point_data.get("properties", {}).get("county")
                if county_url and "/county/" in county_url:
                    zone_id = county_url.split("/county/")[1]
                if not zone_id:
                    forecast_zone_url = point_data.get("properties", {}).get("forecastZone")
                    if forecast_zone_url and "/forecast/" in forecast_zone_url:
                        zone_id = forecast_zone_url.split("/forecast/")[1]

                if zone_id:
                    params = {"zone": zone_id, "status": "actual"}
                else:
                    # Fall back to point query if zone not found
                    logger.warning("Could not determine zone, falling back to point query")
                    params = {
                        "point": f"{location.latitude},{location.longitude}",
                        "status": "actual",
                    }

        else:  # "point" (default) - most precise
            params = {
                "point": f"{location.latitude},{location.longitude}",
                "status": "actual",
            }

        # Note: Don't filter by message_type - we want Alert, Update, and Cancel
        # message_type=alert would exclude updated warnings (messageType: "Update")

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


async def fetch_nws_cancel_references(
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    lookback_minutes: int = 15,
    client: httpx.AsyncClient | None = None,
) -> set[str]:
    """
    Fetch recent NWS Cancel messages and return the set of alert IDs they reference.

    Queries GET /alerts?message_type=cancel&start=<lookback ago>&end=<now>.
    Returns set of all referenced alert IDs (from properties.references[].identifier or @id).
    On any failure, returns empty set (safe default: caller suppresses ambiguous cancels).
    """
    try:
        now = datetime.now(UTC)
        start = now - timedelta(minutes=lookback_minutes)
        start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{nws_base_url}/alerts"
        params = {"message_type": "cancel", "start": start_str, "end": end_str}
        headers = {"User-Agent": user_agent}
        if client is not None:
            response = await _client_get(client, url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
                response = await new_client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        referenced_ids: set[str] = set()
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            for ref in props.get("references", []):
                ref_id = ref.get("identifier") or ref.get("@id") or ref.get("id")
                if ref_id:
                    referenced_ids.add(ref_id)
        logger.debug(f"Fetched {len(referenced_ids)} NWS cancel references")
        return referenced_ids
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to fetch NWS cancel references: {exc}")
        return set()


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

    # Check for empty response before trying to parse JSON
    if not awc_response.text or not awc_response.text.strip():
        logger.debug("AviationWeather returned empty response for %s", station_id)
        return None

    try:
        awc_data = awc_response.json()
    except Exception as exc:  # noqa: BLE001
        # Log first few chars of response to help debug what was returned
        response_preview = awc_response.text[:200] if awc_response.text else "(empty)"
        logger.error(
            "Failed to decode AviationWeather TAF JSON for %s: %s. Response preview: %s",
            station_id,
            exc,
            response_preview,
        )
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

    # Seasonal fields - wind chill and heat index
    wind_chill_c = props.get("windChill", {}).get("value")
    wind_chill_f = (wind_chill_c * 9 / 5) + 32 if wind_chill_c is not None else None

    heat_index_c = props.get("heatIndex", {}).get("value")
    heat_index_f = (heat_index_c * 9 / 5) + 32 if heat_index_c is not None else None

    # Determine feels_like based on wind chill or heat index
    feels_like_f = None
    feels_like_c = None
    if wind_chill_f is not None and (temp_f is None or wind_chill_f < temp_f):
        feels_like_f = wind_chill_f
        feels_like_c = wind_chill_c
    elif heat_index_f is not None and (temp_f is None or heat_index_f > temp_f):
        feels_like_f = heat_index_f
        feels_like_c = heat_index_c

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
        feels_like_f=feels_like_f,
        feels_like_c=feels_like_c,
        visibility_miles=visibility_miles,
        visibility_km=visibility_km,
        uv_index=uv_index,
        # Seasonal fields
        wind_chill_f=wind_chill_f,
        wind_chill_c=wind_chill_c,
        heat_index_f=heat_index_f,
        heat_index_c=heat_index_c,
    )


def parse_nws_forecast(data: dict) -> Forecast:
    """Parse NWS forecast payload into a Forecast model."""
    periods = []

    raw_periods = data.get("properties", {}).get("periods", [])

    for period_data in raw_periods:
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
            wind_speed_mph=_extract_wind_speed_mph(period_data.get("windSpeed")),
            wind_direction=wind_direction,
            icon=period_data.get("icon"),
            start_time=start_time,
            end_time=end_time,
        )
        periods.append(period)

    # Pair daytime/nighttime periods to populate high/low temperatures.
    # NWS returns alternating day/night periods (isDaytime flag). Set the
    # nighttime temperature as temperature_low on the preceding daytime period.
    for i, period_data in enumerate(raw_periods):
        if period_data.get("isDaytime") and i + 1 < len(raw_periods):
            next_data = raw_periods[i + 1]
            if not next_data.get("isDaytime"):
                night_temp, _ = _extract_temperature(
                    next_data.get("temperature"), next_data.get("temperatureUnit")
                )
                if night_temp is not None:
                    periods[i].temperature_low = night_temp

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

        references = []
        for ref in props.get("references", []):
            ref_id = ref.get("identifier") or ref.get("@id") or ref.get("id")
            if ref_id:
                references.append(ref_id)

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
            references=references,
            id=alert_id,
            source="NWS",
            message_type=props.get("messageType"),
        )
        alerts.append(alert)

        if alert_id:
            logger.debug(f"Parsed alert with ID: {alert_id}")
        else:
            logger.debug("Parsed alert without ID, will generate unique ID")

    # Deduplicate by alert ID, keeping first occurrence
    seen_ids: set[str] = set()
    deduped: list[WeatherAlert] = []
    for alert in alerts:
        if alert.id and alert.id in seen_ids:
            logger.debug(f"Skipping duplicate alert ID: {alert.id}")
            continue
        if alert.id:
            seen_ids.add(alert.id)
        deduped.append(alert)
    alerts = deduped

    logger.info(f"Parsed {len(alerts)} alerts from NWS API")
    return WeatherAlerts(alerts=alerts)


def parse_nws_hourly_forecast(data: dict, location: Location | None = None) -> HourlyForecast:
    """Parse NWS hourly forecast payload into an HourlyForecast model."""
    from zoneinfo import ZoneInfo

    periods = []

    # Get location timezone if available
    location_tz = None
    if location and location.timezone:
        try:
            location_tz = ZoneInfo(location.timezone)
        except Exception:
            logger.warning(f"Failed to load timezone: {location.timezone}")

    for period_data in data.get("properties", {}).get("periods", []):
        start_time_str = period_data.get("startTime")
        start_time = None
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                # Convert to location's timezone if available
                if location_tz and start_time:
                    start_time = start_time.astimezone(location_tz)
            except ValueError:
                logger.warning(f"Failed to parse start time: {start_time_str}")

        end_time_str = period_data.get("endTime")
        end_time = None
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                # Convert to location's timezone if available
                if location_tz and end_time:
                    end_time = end_time.astimezone(location_tz)
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


def parse_nws_gridpoint_pressure(data: dict) -> dict[datetime, tuple[float | None, float | None]]:
    """Parse NWS gridpoint pressure values keyed by valid-time start."""
    pressure = data.get("properties", {}).get("pressure", {})
    values = pressure.get("values", []) if isinstance(pressure, dict) else []
    pressure_by_time: dict[datetime, tuple[float | None, float | None]] = {}

    for item in values:
        if not isinstance(item, dict):
            continue
        start_time = _parse_valid_time_start(item.get("validTime"))
        pressure_pa = item.get("value")
        if start_time is None or pressure_pa is None:
            continue
        pressure_by_time[start_time] = (
            convert_pa_to_inches(pressure_pa),
            convert_pa_to_mb(pressure_pa),
        )

    return pressure_by_time


def apply_nws_gridpoint_pressure(
    hourly: HourlyForecast,
    pressure_by_time: dict[datetime, tuple[float | None, float | None]],
) -> HourlyForecast:
    """Populate NWS hourly periods with pressure from the gridpoint pressure layer."""
    if not pressure_by_time:
        return hourly

    updated_periods: list[HourlyForecastPeriod] = []
    changed = False
    for period in hourly.periods:
        if period.pressure_in is not None or period.pressure_mb is not None:
            updated_periods.append(period)
            continue

        pressure_pair = _nearest_pressure_pair(period.start_time, pressure_by_time)
        if pressure_pair is None:
            updated_periods.append(period)
            continue

        updated_periods.append(
            replace(
                period,
                pressure_in=pressure_pair[0],
                pressure_mb=pressure_pair[1],
            )
        )
        changed = True

    if not changed:
        return hourly
    return HourlyForecast(
        periods=updated_periods,
        generated_at=hourly.generated_at,
        summary=hourly.summary,
    )


def _nearest_pressure_pair(
    start_time: datetime,
    pressure_by_time: dict[datetime, tuple[float | None, float | None]],
) -> tuple[float | None, float | None] | None:
    """Return pressure from the closest gridpoint valid time within 90 minutes."""
    target_ts = _timestamp_utc(start_time)
    best_pair = None
    best_delta = None
    for valid_time, pressure_pair in pressure_by_time.items():
        delta = abs(_timestamp_utc(valid_time) - target_ts)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_pair = pressure_pair

    if best_delta is None or best_delta > 90 * 60:
        return None
    return best_pair


def _parse_valid_time_start(valid_time: str | None) -> datetime | None:
    """Parse the start timestamp from an NWS ISO interval validTime value."""
    if not valid_time:
        return None
    start = valid_time.split("/", 1)[0]
    try:
        return datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        logger.debug("Failed to parse NWS gridpoint validTime: %s", valid_time)
        return None


def _timestamp_utc(value: datetime) -> float:
    """Normalize aware and naive datetimes to UTC timestamps."""
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.timestamp()
