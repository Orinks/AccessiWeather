"""Async enrichment helpers for :mod:`accessiweather.weather_client_base`."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from . import weather_client_nws as nws_client
from .display.presentation.environmental import _get_uv_category
from .models import (
    Location,
    MarineForecast,
    MarineForecastPeriod,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)
from .weather_client_aviation import (
    enrich_with_aviation_data as enrich_with_aviation_data,
    get_aviation_weather as get_aviation_weather,
)

if TYPE_CHECKING:
    from .weather_client_base import WeatherClient

logger = logging.getLogger(__name__)


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

    # Copy UV index from current conditions to environmental conditions
    if weather_data.current and weather_data.current.uv_index is not None:
        weather_data.environmental.uv_index = weather_data.current.uv_index
        weather_data.environmental.uv_category = _get_uv_category(weather_data.current.uv_index)
        logger.debug(
            "Copied UV index from current conditions: %s (category: %s)",
            weather_data.current.uv_index,
            weather_data.environmental.uv_category,
        )
