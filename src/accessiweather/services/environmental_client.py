"""Environmental metrics client for air quality and pollen data."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import httpx

from ..models import EnvironmentalConditions, Location
from ..utils.retry_utils import async_retry_with_backoff

logger = logging.getLogger(__name__)


class EnvironmentalDataClient:
    """Fetch supplemental environmental metrics from Open-Meteo services."""

    AIR_QUALITY_ENDPOINT = "https://air-quality-api.open-meteo.com/v1/air-quality"
    POLLEN_ENDPOINT = "https://pollen-api.open-meteo.com/v1/pollen"

    def __init__(self, user_agent: str = "AccessiWeather/2.0", timeout: float = 10.0):
        """Initialize the client.

        Args:
            user_agent: HTTP User-Agent header value.
            timeout: Request timeout in seconds.

        """
        self.user_agent = user_agent
        self.timeout = timeout

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=15.0)
    async def fetch(
        self,
        location: Location,
        *,
        include_air_quality: bool = True,
        include_pollen: bool = True,
    ) -> EnvironmentalConditions | None:
        if not include_air_quality and not include_pollen:
            return None

        headers = {"User-Agent": self.user_agent}
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": "auto",
        }

        environmental = EnvironmentalConditions()

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            if include_air_quality:
                await self._populate_air_quality(client, params, environmental)
            if include_pollen:
                await self._populate_pollen(client, params, environmental)

        if environmental.has_data():
            return environmental
        return None

    async def _populate_air_quality(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
        environmental: EnvironmentalConditions,
    ) -> None:
        try:
            response = await client.get(
                self.AIR_QUALITY_ENDPOINT,
                params={**params, "hourly": "us_aqi,us_aqi_pm2_5,us_aqi_pm10"},
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Air quality request failed: {exc}")
            return

        payload = response.json()
        hourly = payload.get("hourly") if isinstance(payload, dict) else None
        if not isinstance(hourly, dict):
            return

        times = hourly.get("time")
        aqi_values = hourly.get("us_aqi")
        if not self._is_sequence(times) or not self._is_sequence(aqi_values):
            return

        index, timestamp = self._latest_with_timestamp(times, aqi_values)
        if index is None:
            return

        environmental.air_quality_index = index
        environmental.air_quality_category = self._air_quality_category(index)
        environmental.updated_at = timestamp or environmental.updated_at
        environmental.sources.append("Open-Meteo Air Quality")

        pollutant_candidates = {
            "pm2_5": hourly.get("us_aqi_pm2_5"),
            "pm10": hourly.get("us_aqi_pm10"),
        }
        dominant = None
        dominant_value = -1.0
        for name, series in pollutant_candidates.items():
            if not self._is_sequence(series):
                continue
            value, _ = self._latest_with_timestamp(times, series)
            if value is None:
                continue
            if value > dominant_value:
                dominant_value = value
                dominant = name
        if dominant:
            environmental.air_quality_pollutant = dominant.upper()

    async def _populate_pollen(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
        environmental: EnvironmentalConditions,
    ) -> None:
        try:
            response = await client.get(
                self.POLLEN_ENDPOINT,
                params={**params, "hourly": "tree_pollen,grass_pollen,weed_pollen"},
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Pollen request failed: {exc}")
            return

        payload = response.json()
        hourly = payload.get("hourly") if isinstance(payload, dict) else None
        if not isinstance(hourly, dict):
            return

        times = hourly.get("time")
        pollen_types = {
            "Tree": hourly.get("tree_pollen"),
            "Grass": hourly.get("grass_pollen"),
            "Weed": hourly.get("weed_pollen"),
        }

        primary_allergen = None
        primary_value = -1.0

        for label, series in pollen_types.items():
            if not self._is_sequence(series):
                continue
            value, timestamp = self._latest_with_timestamp(times, series)
            if value is None:
                continue
            if label == "Tree":
                environmental.pollen_tree_index = value
            elif label == "Grass":
                environmental.pollen_grass_index = value
            elif label == "Weed":
                environmental.pollen_weed_index = value

            if timestamp and (
                environmental.updated_at is None or timestamp > environmental.updated_at
            ):
                environmental.updated_at = timestamp

            if value > primary_value:
                primary_value = value
                primary_allergen = label

        if primary_value >= 0:
            environmental.pollen_index = primary_value
            environmental.pollen_category = self._pollen_category(primary_value)
            environmental.pollen_primary_allergen = primary_allergen
            environmental.sources.append("Open-Meteo Pollen")

    def _latest_with_timestamp(
        self,
        times: Iterable[Any],
        series: Iterable[Any],
    ) -> tuple[float | None, datetime | None]:
        latest_value: float | None = None
        latest_timestamp: datetime | None = None

        for time_str, raw_value in zip(times, series, strict=False):
            value = self._coerce_float(raw_value)
            timestamp = self._parse_iso(time_str)
            if value is None:
                continue
            if latest_timestamp is None or (timestamp and timestamp > latest_timestamp):
                latest_value = value
                latest_timestamp = timestamp

        return latest_value, latest_timestamp

    def _air_quality_category(self, value: float) -> str:
        if value <= 50:
            return "Good"
        if value <= 100:
            return "Moderate"
        if value <= 150:
            return "Unhealthy for Sensitive Groups"
        if value <= 200:
            return "Unhealthy"
        if value <= 300:
            return "Very Unhealthy"
        return "Hazardous"

    def _pollen_category(self, value: float) -> str:
        if value < 30:
            return "Low"
        if value < 60:
            return "Moderate"
        if value < 120:
            return "High"
        return "Very High"

    def _is_sequence(self, value: Any) -> bool:
        return isinstance(value, (list, tuple)) and len(value) > 0

    def _parse_iso(self, value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _coerce_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
