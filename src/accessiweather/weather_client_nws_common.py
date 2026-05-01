"""Shared helpers for the NWS weather client."""
# ruff: noqa: F401

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

try:
    import wx  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - handled at runtime
    wx = None  # type: ignore[assignment]

_ZONE_DRIFT_SINK: Any = None

logger = logging.getLogger("accessiweather.weather_client_nws")

MAX_STATION_OBSERVATION_ATTEMPTS = 10
MAX_OBSERVATION_AGE = timedelta(hours=2)
VALID_QC_CODES = {"V", "C", None}

__all__ = [
    "Any",
    "CurrentConditions",
    "Forecast",
    "ForecastPeriod",
    "HourlyForecast",
    "HourlyForecastPeriod",
    "Literal",
    "Location",
    "MAX_OBSERVATION_AGE",
    "MAX_STATION_OBSERVATION_ATTEMPTS",
    "RETRYABLE_EXCEPTIONS",
    "TextProduct",
    "UTC",
    "VALID_QC_CODES",
    "WeatherAlert",
    "WeatherAlerts",
    "_apply_zone_drift_correction",
    "_client_get",
    "_current_data_score",
    "_extract_float",
    "_extract_scalar",
    "_extract_temperature",
    "_extract_wind_speed_mph",
    "_format_unit",
    "_format_wind_speed",
    "_normalize_temperature_unit",
    "_parse_iso_datetime",
    "_scrub_measurements",
    "_station_sort_key",
    "async_retry_with_backoff",
    "convert_pa_to_inches",
    "convert_pa_to_mb",
    "convert_wind_speed_to_mph_and_kph",
    "datetime",
    "httpx",
    "inspect",
    "is_retryable_http_error",
    "logger",
    "re",
    "replace",
    "set_zone_drift_sink",
    "timedelta",
    "wx",
]


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
