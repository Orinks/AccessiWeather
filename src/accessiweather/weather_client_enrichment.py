"""Async enrichment helpers for :mod:`accessiweather.weather_client_base`."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from . import weather_client_nws as nws_client
from .api.avwx_client import AvwxApiError, fetch_avwx_taf, is_us_station
from .display.presentation.environmental import _get_uv_category
from .models import (
    AviationData,
    Location,
    MarineForecast,
    MarineForecastPeriod,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)
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


async def enrich_with_nws_discussion(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Enrich weather data with forecast discussion from NWS for US locations."""
    if not client._is_us_location(location):
        return

    try:
        logger.debug("Fetching forecast discussion from NWS for %s", location.name)
        _, discussion, discussion_issuance_time = await client._get_nws_forecast_and_discussion(
            location
        )
        if discussion:
            weather_data.discussion = discussion
            weather_data.discussion_issuance_time = discussion_issuance_time
            logger.info(
                "Updated forecast discussion from NWS (issued: %s)", discussion_issuance_time
            )
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
    """
    Fetch aviation weather products for a specific ICAO station identifier.

    Routing logic
    -------------
    * **US stations** (ICAO prefix ``K``, ``PA``, ``PH``, ``PG``, …) are
      handled by the existing NWS / AviationWeather.gov path which provides
      native US SIGMET and CWA data.
    * **International stations** are routed through the AVWX REST API when an
      API key is configured on the client.  AVWX returns TTS-ready speech
      strings, plain-English translations, and per-period flight rules — all
      significantly improving accessibility for non-US users.  If no AVWX key
      is configured (or the request fails) the function falls back to the
      AviationWeather.gov global TAF feed so that a raw TAF is still returned.
    """
    station = (station_id or "").strip().upper()
    if not station:
        raise ValueError("station_id must be a non-empty ICAO identifier.")

    http_client = client._get_http_client()

    # ------------------------------------------------------------------
    # Route international stations through AVWX when an API key is set
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # NWS / AviationWeather.gov path (US stations and AVWX fallback)
    # ------------------------------------------------------------------
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


_MARINE_HIGHLIGHT_PATTERN = re.compile(
    r"([^.;]*\b(?:wind|winds|gust|gusts|wave|waves|seas|swell|swells)\b[^.;]*)",
    re.IGNORECASE,
)


def _build_marine_highlights(periods: list[dict[str, Any]]) -> list[str]:
    """Extract concise wind and wave highlights from marine text periods."""
    highlights: list[str] = []
    seen: set[str] = set()
    for period in periods:
        for field in ("shortForecast", "detailedForecast"):
            text = str(period.get(field) or "").strip()
            if not text:
                continue
            for match in _MARINE_HIGHLIGHT_PATTERN.findall(text):
                candidate = " ".join(match.split()).strip(" .")
                if not candidate:
                    continue
                normalized = candidate.lower()
                if normalized in seen:
                    continue
                seen.add(normalized)
                highlights.append(candidate)
                if len(highlights) >= 4:
                    return highlights
    return highlights


def _parse_marine_issued_at(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def enrich_with_marine_data(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Populate marine essentials for coastal locations when marine mode is enabled."""
    if not getattr(location, "marine_mode", False) or not client._is_us_location(location):
        return

    try:
        http_client = client._get_http_client()
        headers = {"User-Agent": client.user_agent}
        marine_zone_response = await nws_client._client_get(
            http_client,
            f"{client.nws_base_url}/zones",
            headers=headers,
            params={"type": "marine", "point": f"{location.latitude},{location.longitude}"},
        )
        marine_zone_response.raise_for_status()
        marine_zone_data = marine_zone_response.json()
        features = marine_zone_data.get("features") or []
        if not features:
            return

        marine_feature = features[0]
        marine_properties = marine_feature.get("properties", {})
        zone_id = marine_properties.get("id") or marine_feature.get("id")
        if not zone_id:
            return

        marine_forecast_data = await nws_client.get_nws_marine_forecast(
            "marine",
            zone_id,
            client.nws_base_url,
            client.user_agent,
            client.timeout,
            http_client,
        )
        if not marine_forecast_data:
            return

        forecast_properties = marine_forecast_data.get("properties", {})
        forecast_periods = forecast_properties.get("periods") or []
        periods = [
            MarineForecastPeriod(
                name=str(period.get("name") or "Marine period"),
                summary=str(
                    period.get("detailedForecast") or period.get("shortForecast") or ""
                ).strip(),
            )
            for period in forecast_periods[:3]
            if (period.get("detailedForecast") or period.get("shortForecast"))
        ]
        marine = MarineForecast(
            zone_id=zone_id,
            zone_name=forecast_properties.get("name") or marine_properties.get("name"),
            forecast_summary=(
                str(
                    forecast_periods[0].get("detailedForecast")
                    or forecast_periods[0].get("shortForecast")
                )
                if forecast_periods
                else None
            ),
            issued_at=_parse_marine_issued_at(forecast_properties.get("updateTime")),
            periods=periods,
            highlights=_build_marine_highlights(forecast_periods[:4]),
        )
        if marine.has_data():
            weather_data.marine = marine

        marine_alerts_response = await nws_client._client_get(
            http_client,
            f"{client.nws_base_url}/alerts/active",
            headers=headers,
            params={"zone": zone_id, "status": "actual"},
        )
        marine_alerts_response.raise_for_status()
        marine_alerts = nws_client.parse_nws_alerts(marine_alerts_response.json())
        if marine_alerts and marine_alerts.alerts:
            existing = weather_data.alerts.alerts if weather_data.alerts else []
            merged: dict[str, WeatherAlert] = {alert.get_unique_id(): alert for alert in existing}
            for alert in marine_alerts.alerts:
                alert.source = "NWS Marine"
                merged.setdefault(alert.get_unique_id(), alert)
            weather_data.alerts = WeatherAlerts(alerts=list(merged.values()))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to fetch marine essentials for %s: %s", location.name, exc)


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


async def enrich_with_visual_crossing_alerts(
    client: WeatherClient,
    weather_data: WeatherData,
    location: Location,
    skip_notifications: bool = False,
) -> None:
    """
    Enrich weather data with alerts from Visual Crossing if available.

    For US locations, this is skipped since NWS is the authoritative source
    and Visual Crossing just mirrors the same alerts without severity metadata.

    Args:
        client: The weather client instance
        weather_data: The weather data to enrich
        location: The location for alerts
        skip_notifications: If True, skip triggering alert notifications (used for pre-warming)

    """
    if not client.visual_crossing_client:
        return

    # Skip VC alerts for US locations - NWS is authoritative and VC lacks metadata
    if client._is_us_location(location):
        logger.debug("Skipping Visual Crossing alerts for US location %s", location.name)
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

            # Only process for notifications if not skipped (e.g., for pre-warming)
            if not skip_notifications:
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

    # Fallback: populate AQ from Visual Crossing if Open-Meteo didn't provide it
    if environmental.air_quality_index is None and client.visual_crossing_client:
        try:
            vc_aq = await client.visual_crossing_client.get_air_quality(location)
            client.environmental_client.populate_from_visual_crossing(vc_aq, environmental)
        except Exception as exc:  # noqa: BLE001
            logger.debug("VC air quality fallback failed: %s", exc)

    # Copy UV index from current conditions to environmental conditions
    if weather_data.current and weather_data.current.uv_index is not None:
        weather_data.environmental.uv_index = weather_data.current.uv_index
        weather_data.environmental.uv_category = _get_uv_category(weather_data.current.uv_index)
        logger.debug(
            "Copied UV index from current conditions: %s (category: %s)",
            weather_data.current.uv_index,
            weather_data.environmental.uv_category,
        )


async def enrich_with_visual_crossing_moon_data(
    client: WeatherClient, weather_data: WeatherData, location: Location
) -> None:
    """Enrich weather data with moon phase info from Visual Crossing if configured."""
    if not client.visual_crossing_client:
        return

    # Skip if we already have moon phase data
    if weather_data.current and weather_data.current.moon_phase:
        return

    try:
        logger.debug("Fetching moon data from Visual Crossing for %s", location.name)
        vc_current = await client.visual_crossing_client.get_current_conditions(location)

        if vc_current and weather_data.current:
            # Update moon fields if present in VC response
            if vc_current.moon_phase:
                weather_data.current.moon_phase = vc_current.moon_phase
                logger.info("Updated moon phase from Visual Crossing: %s", vc_current.moon_phase)

            if vc_current.moonrise_time:
                weather_data.current.moonrise_time = vc_current.moonrise_time

            if vc_current.moonset_time:
                weather_data.current.moonset_time = vc_current.moonset_time

    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to fetch moon data from Visual Crossing: %s", exc)
