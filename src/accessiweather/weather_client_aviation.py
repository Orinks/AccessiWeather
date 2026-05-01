"""Aviation enrichment helpers for :mod:`accessiweather.weather_client_base`."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from . import weather_client_nws as nws_client
from .api.avwx_client import AvwxApiError, fetch_avwx_taf, is_us_station
from .models import AviationData, Location, WeatherData
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
    if isinstance(value, list | tuple | set):
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


async def get_aviation_weather(
    client: WeatherClient,
    station_id: str,
    *,
    include_sigmets: bool = False,
    atsu: str | None = None,
    include_cwas: bool = False,
    cwsu_id: str | None = None,
) -> AviationData:
    """
    Fetch aviation weather products for a specific ICAO station identifier.

    US stations use the NWS / AviationWeather.gov path. International stations
    route through AVWX when an API key is configured, then fall back to the
    AviationWeather.gov global TAF feed if needed.
    """
    station = (station_id or "").strip().upper()
    if not station:
        raise ValueError("station_id must be a non-empty ICAO identifier.")

    http_client = client._get_http_client()
    avwx_key: str = getattr(client, "avwx_api_key", "") or ""
    if not is_us_station(station) and avwx_key:
        logger.debug("Routing international station %s through AVWX", station)
        try:
            return await fetch_avwx_taf(station, avwx_key, http_client=http_client)
        except AvwxApiError as exc:
            logger.warning("AVWX fetch failed for %s (%s); falling back to AWC path", station, exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Unexpected error fetching from AVWX for %s (%s); falling back", station, exc
            )

    aviation = AviationData(station_id=station, airport_name=station)
    station_metadata = await _fetch_station_metadata(client, station, http_client)
    metadata_props: dict[str, Any] = (station_metadata or {}).get("properties", {})
    airport_name = metadata_props.get("name")
    if airport_name:
        aviation.airport_name = airport_name

    await _populate_taf(client, aviation, station, http_client)
    tokens = _build_station_tokens(station, metadata_props, aviation.airport_name, cwsu_id)
    sigmet_atsu = _normalize_token(atsu) or _default_atsu(metadata_props)

    if include_sigmets:
        await _populate_sigmets(client, aviation, tokens, sigmet_atsu, http_client)
    if include_cwas:
        await _populate_cwas(client, aviation, tokens, metadata_props, cwsu_id, http_client)

    return aviation


async def _fetch_station_metadata(
    client: WeatherClient, station: str, http_client: Any
) -> dict[str, Any] | None:
    try:
        return await nws_client.get_nws_station_metadata(
            station, client.nws_base_url, client.user_agent, client.timeout, http_client
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to fetch station metadata for %s: %s", station, exc)
        return None


async def _populate_taf(
    client: WeatherClient, aviation: AviationData, station: str, http_client: Any
) -> None:
    try:
        raw_taf = await nws_client.get_nws_tafs(
            station, client.nws_base_url, client.user_agent, client.timeout, http_client
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch TAF for %s: %s", station, exc)
        raise

    if not raw_taf:
        return

    cleaned_taf = raw_taf.strip()
    if not cleaned_taf or _taf_indicates_no_data(cleaned_taf):
        aviation.raw_taf = None
        aviation.decoded_taf = None
        return

    decoded_taf = decode_taf_text(cleaned_taf)
    if decoded_taf and decoded_taf.lower().startswith("no taf available"):
        aviation.raw_taf = None
        aviation.decoded_taf = None
        return

    aviation.raw_taf = cleaned_taf
    aviation.decoded_taf = decoded_taf


def _build_station_tokens(
    station: str, metadata_props: dict[str, Any], airport_name: str | None, cwsu_id: str | None
) -> set[str]:
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

    if airport_name:
        for part in airport_name.replace("-", " ").split():
            normalized = _normalize_token(part)
            if normalized and len(normalized) > 2:
                tokens.add(normalized)
    return tokens


async def _populate_sigmets(
    client: WeatherClient,
    aviation: AviationData,
    tokens: set[str],
    sigmet_atsu: str | None,
    http_client: Any,
) -> None:
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
        logger.debug("Failed to fetch SIGMET data: %s", exc)


async def _populate_cwas(
    client: WeatherClient,
    aviation: AviationData,
    tokens: set[str],
    metadata_props: dict[str, Any],
    cwsu_id: str | None,
    http_client: Any,
) -> None:
    target_cwsu = _normalize_token(cwsu_id) or _normalize_token(metadata_props.get("cwa"))
    if not target_cwsu:
        aviation.active_cwas = []
        return

    try:
        cwas = await nws_client.get_nws_cwas(
            target_cwsu, client.nws_base_url, client.user_agent, client.timeout, http_client
        )
        aviation.active_cwas = _filter_advisories(cwas, tokens)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to fetch CWA data for %s: %s", target_cwsu, exc)


async def enrich_with_aviation_data(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Populate aviation data for US locations using NWS products."""
    if not client._is_us_location(location):
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
