"""Aviation and specialty-product helpers for the NWS weather client."""
# ruff: noqa: F403, F405

from __future__ import annotations

from .weather_client_nws_common import *  # noqa: F403


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
