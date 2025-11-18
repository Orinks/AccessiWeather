"""Async enrichment helpers for :mod:`accessiweather.weather_client_base`."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from . import weather_client_nws as nws_client
from .models import AviationData, Location, WeatherAlert, WeatherAlerts, WeatherData
from .utils import decode_taf_text

if TYPE_CHECKING:
    from .weather_client_base import WeatherClient

logger = logging.getLogger(__name__)


def _normalize_token(value: Any) -> str | None:
    if value is None:
        return None
    token = str(value).strip().upper()
    return token or None


def _taf_indicates_no_data(raw_taf: str) -> bool:
    """
    Determine whether the provided raw TAF string represents a NIL/no-data report.

    The NWS TAF feed uses the token ``NIL`` (and occasionally phrases such as
    ``NO TAF`` or ``NO DATA``) to indicate that no forecast is available. We
    strip common header prefixes and examine the remaining tokens to detect this.
    """
    if not raw_taf:
        return True

    tokens = [token.rstrip("=").upper() for token in raw_taf.split()]
    index = 0

    while index < len(tokens) and tokens[index] in {"TAF", "AMD", "COR"}:
        index += 1

    if index < len(tokens) and len(tokens[index]) == 4 and tokens[index].isalpha():
        index += 1

    if index < len(tokens) and tokens[index].endswith("Z") and len(tokens[index]) == 7:
        index += 1

    if index < len(tokens) and tokens[index].count("/") == 1:
        index += 1

    if index < len(tokens) and tokens[index] == "NIL":
        return True

    remaining = " ".join(tokens[index:])
    return "NO TAF" in remaining or "NO DATA" in remaining


def _extract_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        normalized = value.strip().upper()
        return [normalized] if normalized else []
    if isinstance(value, (list, tuple, set)):
        strings: list[str] = []
        for item in value:
            strings.extend(_extract_strings(item))
        return strings
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_extract_strings(item))
        return strings
    try:
        return _extract_strings(str(value))
    except Exception:  # noqa: BLE001
        return []


def _filter_advisories(entries: list[dict[str, Any]], tokens: set[str]) -> list[dict[str, Any]]:
    if not entries:
        return []
    normalized_tokens = {token for token in tokens if token}
    if not normalized_tokens:
        return entries

    keys = (
        "fir",
        "area",
        "regions",
        "airspace",
        "name",
        "event",
        "hazard",
        "description",
        "summary",
        "text",
        "issuingOffice",
        "cwsu",
        "cwsuId",
        "stationId",
        "stations",
    )

    filtered: list[dict[str, Any]] = []
    for entry in entries:
        candidates: list[str] = []
        for key in keys:
            candidates.extend(_extract_strings(entry.get(key)))
        if not candidates:
            candidates = _extract_strings(entry)

        matches = any(
            token in candidate
            for token in normalized_tokens
            for candidate in candidates
            if candidate
        )
        if matches:
            filtered.append(entry)

    return filtered


def _default_atsu(props: dict[str, Any]) -> str | None:
    country = _normalize_token(props.get("country"))
    if country in {"US", "USA"}:
        return "KKCI"
    return None


async def enrich_with_nws_discussion(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Enrich weather data with forecast discussion from NWS for US locations."""
    if not client._is_us_location(location):
        return

    if weather_data.discussion and not weather_data.discussion.startswith(
        "Forecast discussion not available"
    ):
        return

    try:
        logger.debug("Fetching forecast discussion from NWS for %s", location.name)
        _, discussion = await client._get_nws_forecast_and_discussion(location)
        if discussion:
            weather_data.discussion = discussion
            logger.info("Added forecast discussion from NWS")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to fetch NWS discussion: %s", exc)


async def get_aviation_weather(
    client: WeatherClient,
    station_id: str,
    *,
    include_sigmets: bool = False,
    atsu: str | None = None,
    include_cwas: bool = False,
    cwsu_id: str | None = None,
) -> AviationData:
    """Fetch aviation weather products for a specific ICAO station identifier."""
    station = (station_id or "").strip().upper()
    if not station:
        raise ValueError("station_id must be a non-empty ICAO identifier.")

    http_client = client._get_http_client()
    aviation = AviationData(station_id=station, airport_name=station)

    station_metadata: dict[str, Any] | None = None
    try:
        station_metadata = await nws_client.get_nws_station_metadata(
            station, client.nws_base_url, client.user_agent, client.timeout, http_client
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to fetch station metadata for %s: %s", station, exc)

    metadata_props: dict[str, Any] = (station_metadata or {}).get("properties", {})
    airport_name = metadata_props.get("name")
    if airport_name:
        aviation.airport_name = airport_name

    raw_taf: str | None
    try:
        raw_taf = await nws_client.get_nws_tafs(
            station, client.nws_base_url, client.user_agent, client.timeout, http_client
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch TAF for %s: %s", station, exc)
        raise

    if raw_taf:
        cleaned_taf = raw_taf.strip()
        if not cleaned_taf or _taf_indicates_no_data(cleaned_taf):
            aviation.raw_taf = None
            aviation.decoded_taf = None
        else:
            decoded_taf = decode_taf_text(cleaned_taf)
            if decoded_taf and decoded_taf.lower().startswith("no taf available"):
                aviation.raw_taf = None
                aviation.decoded_taf = None
            else:
                aviation.raw_taf = cleaned_taf
                aviation.decoded_taf = decoded_taf

    tokens: set[str] = {station}

    derived_cwsu = _normalize_token(cwsu_id) or _normalize_token(metadata_props.get("cwa"))
    if derived_cwsu:
        tokens.add(derived_cwsu)

    tokens.update(
        token
        for token in (
            _normalize_token(metadata_props.get("wfo")),
            _normalize_token(metadata_props.get("state")),
        )
        if token
    )

    if aviation.airport_name:
        for part in aviation.airport_name.replace("-", " ").split():
            normalized = _normalize_token(part)
            if normalized and len(normalized) > 2:
                tokens.add(normalized)

    sigmet_atsu = _normalize_token(atsu) or _default_atsu(metadata_props)

    if include_sigmets:
        try:
            sigmets = await nws_client.get_nws_sigmets(
                client.nws_base_url,
                client.user_agent,
                client.timeout,
                http_client,
                atsu=sigmet_atsu,
            )
            aviation.active_sigmets = _filter_advisories(sigmets, tokens)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch SIGMET data for %s: %s", station, exc)

    if include_cwas:
        target_cwsu = derived_cwsu
        if target_cwsu:
            try:
                cwas = await nws_client.get_nws_cwas(
                    target_cwsu, client.nws_base_url, client.user_agent, client.timeout, http_client
                )
                aviation.active_cwas = _filter_advisories(cwas, tokens)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to fetch CWA data for %s: %s", target_cwsu, exc)
        else:
            aviation.active_cwas = []

    return aviation


async def enrich_with_aviation_data(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Populate aviation data for US locations using NWS products."""
    if not client._is_us_location(location):
        return
    if weather_data.aviation and weather_data.aviation.has_taf():
        return

    try:
        http_client = client._get_http_client()
        station_id, station_name = await nws_client.get_nws_primary_station_info(
            location, client.nws_base_url, client.user_agent, client.timeout, http_client
        )
        if not station_id:
            return

        aviation = await get_aviation_weather(client, station_id)
        if station_name:
            aviation.airport_name = station_name

        weather_data.aviation = aviation
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to fetch aviation data: %s", exc)


async def enrich_with_visual_crossing_alerts(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Enrich weather data with alerts from Visual Crossing if available."""
    if not client.visual_crossing_client:
        return

    try:
        logger.debug("Fetching alerts from Visual Crossing for %s", location.name)
        vc_alerts_data = await client.visual_crossing_client.get_alerts(location)

        if vc_alerts_data and vc_alerts_data.has_alerts():
            logger.info("Adding %d alerts from Visual Crossing", len(vc_alerts_data.alerts))

            existing = weather_data.alerts.alerts if weather_data.alerts else []
            combined: dict[str, WeatherAlert] = {alert.get_unique_id(): alert for alert in existing}

            for alert in vc_alerts_data.alerts:
                combined.setdefault(alert.get_unique_id(), alert)

            weather_data.alerts = WeatherAlerts(alerts=list(combined.values()))

            await client._process_visual_crossing_alerts(vc_alerts_data, location)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to fetch alerts from Visual Crossing: %s", exc)


async def enrich_with_sunrise_sunset(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Enrich weather data with sunrise/sunset from Open-Meteo, always updating with fresh values."""
    if not weather_data.current:
        return

    try:
        logger.debug("Fetching sunrise/sunset from Open-Meteo for %s", location.name)
        openmeteo_current = await client._get_openmeteo_current_conditions(location)

        if not openmeteo_current:
            return

        if openmeteo_current.sunrise_time:
            weather_data.current.sunrise_time = openmeteo_current.sunrise_time
            logger.info(
                "Updated sunrise time from Open-Meteo: %s",
                openmeteo_current.sunrise_time,
            )

        if openmeteo_current.sunset_time:
            weather_data.current.sunset_time = openmeteo_current.sunset_time
            logger.info(
                "Updated sunset time from Open-Meteo: %s",
                openmeteo_current.sunset_time,
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to fetch sunrise/sunset from Open-Meteo: %s", exc)


async def populate_environmental_metrics(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Populate air-quality and pollen data if configured."""
    if not client.environmental_client:
        return
    if not (client.air_quality_enabled or client.pollen_enabled):
        return

    try:
        environmental = await client.environmental_client.fetch(
            location,
            include_air_quality=client.air_quality_enabled,
            include_pollen=client.pollen_enabled,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Environmental metrics failed: %s", exc)
        return

    if not environmental:
        return

    weather_data.environmental = environmental
    if (
        client.air_quality_notify_threshold
        and environmental.air_quality_index is not None
        and environmental.air_quality_index >= client.air_quality_notify_threshold
    ):
        client._maybe_generate_air_quality_alert(weather_data, environmental)


async def merge_international_alerts(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Merge MeteoAlarm alerts into existing alert set for international locations."""
    if not client.international_alerts_enabled:
        return
    if client._is_us_location(location):
        return
    if not client.meteoalarm_client:
        return

    try:
        alerts = await client.meteoalarm_client.fetch_alerts(location)
    except Exception as exc:  # noqa: BLE001
        logger.debug("MeteoAlarm fetch failed: %s", exc)
        return

    if not alerts or not alerts.has_alerts():
        return

    existing = weather_data.alerts.alerts if weather_data.alerts else []
    combined: dict[str, WeatherAlert] = {alert.get_unique_id(): alert for alert in existing}
    for alert in alerts.alerts:
        combined.setdefault(alert.get_unique_id(), alert)
    weather_data.alerts = WeatherAlerts(alerts=list(combined.values()))
