"""Environmental metrics client for air quality and pollen data."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx

from ..models import EnvironmentalConditions, HourlyAirQuality, HourlyUVIndex, Location
from ..utils.retry_utils import async_retry_with_backoff

logger = logging.getLogger(__name__)


class EnvironmentalDataClient:
    """Fetch supplemental environmental metrics from Open-Meteo services."""

    AIR_QUALITY_ENDPOINT = "https://air-quality-api.open-meteo.com/v1/air-quality"
    POLLEN_ENDPOINT = "https://pollen-api.open-meteo.com/v1/pollen"

    def __init__(self, user_agent: str = "AccessiWeather/2.0", timeout: float = 10.0):
        """
        Initialize the client.

        Args:
            user_agent: HTTP User-Agent header value.
            timeout: Request timeout in seconds.

        """
        self.user_agent = user_agent
        self.timeout = timeout

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=15.0)
    async def fetch_hourly_air_quality(
        self,
        location: Location,
        hours: int = 48,
    ) -> list[dict[str, Any]] | None:
        """
        Fetch hourly air quality forecast.

        Args:
            location: Location to fetch air quality for.
            hours: Number of hours to forecast (max 120).

        Returns:
            List of hourly air quality data dictionaries, or None on error.
            Each dict contains: timestamp, aqi, category, and pollutant levels.

        """
        try:
            headers = {"User-Agent": self.user_agent}
            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "hourly": "us_aqi,pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide",
                "timezone": "auto",
            }

            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(self.AIR_QUALITY_ENDPOINT, params=params)
                response.raise_for_status()

            payload = response.json()
            hourly = payload.get("hourly") if isinstance(payload, dict) else None
            if not isinstance(hourly, dict):
                return None

            times = hourly.get("time")
            aqi_values = hourly.get("us_aqi")

            if not self._is_sequence(times) or not self._is_sequence(aqi_values):
                return None

            # Open-Meteo returns hourly data starting at local midnight and spanning
            # several days. Anchor the forecast to the current hour so that entry[0]
            # represents "now" rather than an earlier hour from earlier today.
            offset = payload.get("utc_offset_seconds")
            start = self._current_hour_index(times, offset)

            # Build hourly forecast list
            result = []
            for count, i in enumerate(range(start, len(times))):
                if count >= hours:
                    break
                if i >= len(aqi_values):
                    break

                time_str = times[i]
                aqi = aqi_values[i]

                timestamp = self._parse_local_aware(time_str, offset)
                aqi_float = self._coerce_float(aqi)

                if timestamp is None or aqi_float is None:
                    continue

                entry = {
                    "timestamp": timestamp,
                    "aqi": int(round(aqi_float)),
                    "category": self._air_quality_category(aqi_float),
                }

                # Add pollutant data if available
                if self._is_sequence(hourly.get("pm2_5")):
                    pm25 = self._coerce_float(hourly["pm2_5"][i])
                    if pm25 is not None:
                        entry["pm2_5"] = round(pm25, 1)

                if self._is_sequence(hourly.get("pm10")):
                    pm10 = self._coerce_float(hourly["pm10"][i])
                    if pm10 is not None:
                        entry["pm10"] = round(pm10, 1)

                if self._is_sequence(hourly.get("ozone")):
                    ozone = self._coerce_float(hourly["ozone"][i])
                    if ozone is not None:
                        entry["ozone"] = round(ozone, 1)

                if self._is_sequence(hourly.get("nitrogen_dioxide")):
                    no2 = self._coerce_float(hourly["nitrogen_dioxide"][i])
                    if no2 is not None:
                        entry["nitrogen_dioxide"] = round(no2, 1)

                if self._is_sequence(hourly.get("sulphur_dioxide")):
                    so2 = self._coerce_float(hourly["sulphur_dioxide"][i])
                    if so2 is not None:
                        entry["sulphur_dioxide"] = round(so2, 1)

                if self._is_sequence(hourly.get("carbon_monoxide")):
                    co = self._coerce_float(hourly["carbon_monoxide"][i])
                    if co is not None:
                        entry["carbon_monoxide"] = round(co, 1)

                result.append(entry)

            return result if result else None

        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Hourly air quality request failed: {exc}")
            return None

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=15.0)
    async def fetch_hourly_uv_index(
        self,
        location: Location,
        hours: int = 48,
    ) -> list[HourlyUVIndex] | None:
        """
        Fetch hourly UV index forecast from Open-Meteo.

        Args:
            location: Location to fetch UV forecast for.
            hours: Number of hours to forecast (max 120).

        Returns:
            List of HourlyUVIndex objects, or None on error.

        """
        try:
            # Import the mapper
            from ..openmeteo_mapper import OpenMeteoMapper

            headers = {"User-Agent": self.user_agent}
            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "hourly": "uv_index",
                "timezone": "auto",
                "forecast_days": min(7, (hours // 24) + 1),  # OpenMeteo supports up to 16 days
            }

            # Use the forecast endpoint (not air quality or pollen)
            forecast_endpoint = "https://api.open-meteo.com/v1/forecast"

            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(forecast_endpoint, params=params)
                response.raise_for_status()

            payload = response.json()

            # Use the existing mapper to parse the response
            mapper = OpenMeteoMapper()
            hourly_uv_list = mapper.map_hourly_uv_index(payload)

            # The mapper returns entries from local midnight onward. Drop past
            # hours so entry[0] is the current hour, not the start of the day.
            hourly_uv_list = self._drop_past_hours(hourly_uv_list)

            # Limit to requested hours
            if hourly_uv_list and hours < len(hourly_uv_list):
                hourly_uv_list = hourly_uv_list[:hours]

            return hourly_uv_list if hourly_uv_list else None

        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Hourly UV index request failed: {exc}")
            return None

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=15.0)
    async def fetch(
        self,
        location: Location,
        *,
        include_air_quality: bool = True,
        include_pollen: bool = True,
        include_hourly_air_quality: bool = True,
        include_hourly_uv: bool = True,
        hourly_hours: int = 48,
    ) -> EnvironmentalConditions | None:
        if (
            not include_air_quality
            and not include_pollen
            and not include_hourly_air_quality
            and not include_hourly_uv
        ):
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

        # Fetch hourly air quality separately if requested
        if include_hourly_air_quality:
            hourly_data = await self.fetch_hourly_air_quality(location, hours=hourly_hours)
            if hourly_data:
                environmental.hourly_air_quality = [
                    HourlyAirQuality(
                        timestamp=entry["timestamp"],
                        aqi=entry["aqi"],
                        category=entry["category"],
                        pm2_5=entry.get("pm2_5"),
                        pm10=entry.get("pm10"),
                        ozone=entry.get("ozone"),
                        nitrogen_dioxide=entry.get("nitrogen_dioxide"),
                        sulphur_dioxide=entry.get("sulphur_dioxide"),
                        carbon_monoxide=entry.get("carbon_monoxide"),
                    )
                    for entry in hourly_data
                ]

        # Fetch hourly UV index separately if requested
        if include_hourly_uv:
            hourly_uv_data = await self.fetch_hourly_uv_index(location, hours=hourly_hours)
            if hourly_uv_data:
                environmental.hourly_uv_index = hourly_uv_data
                logger.debug(f"Added {len(hourly_uv_data)} hourly UV index entries")

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

        # The series covers midnight-to-forecast-horizon; read the current hour
        # so the reported AQI reflects "now" rather than a far-future forecast.
        offset = payload.get("utc_offset_seconds")
        current = self._current_hour_index(times, offset)
        index = self._value_near(aqi_values, current)
        if index is None:
            return

        environmental.air_quality_index = index
        environmental.air_quality_category = self._air_quality_category(index)
        environmental.updated_at = (
            self._parse_local_aware(times[current], offset) or environmental.updated_at
        )
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
            value = self._value_near(series, current)
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
        if not self._is_sequence(times):
            return

        # Read the current hour rather than the furthest-future forecast entry.
        offset = payload.get("utc_offset_seconds")
        current = self._current_hour_index(times, offset)
        timestamp = self._parse_local_aware(times[current], offset)
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
            value = self._value_near(series, current)
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

    def _current_hour_index(self, times: Any, utc_offset_seconds: Any) -> int:
        """
        Return the index into ``times`` representing the current local hour.

        Open-Meteo hourly series begin at local midnight and extend several days
        into the future. The entry that represents "now" is the last one whose
        local timestamp is at or before the current local time — not the final,
        furthest-future entry. When the current time precedes the whole series
        (unexpected), fall back to the first entry.
        """
        if not self._is_sequence(times):
            return 0

        offset = utc_offset_seconds if isinstance(utc_offset_seconds, int | float) else 0
        now_local = (datetime.now(UTC) + timedelta(seconds=offset)).replace(tzinfo=None)

        best_index = 0
        found = False
        for i, time_str in enumerate(times):
            parsed = self._parse_naive(time_str)
            if parsed is None:
                continue
            if parsed <= now_local:
                best_index = i
                found = True
            else:
                # times are sorted ascending; everything after this is future
                break

        return best_index if found else 0

    def _drop_past_hours(self, entries: list[Any]) -> list[Any]:
        """
        Trim leading entries older than the current hour.

        Keeps entries whose ``timestamp`` is at or after the start of the current
        UTC hour so the forecast begins at "now". Falls back to the original list
        if every entry is in the past (stale data) or timestamps are unusable.
        """
        if not entries:
            return entries

        now_hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

        def _at_or_after_now(entry: Any) -> bool:
            timestamp = getattr(entry, "timestamp", None)
            if not isinstance(timestamp, datetime):
                return True  # keep entries we can't evaluate
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            return timestamp >= now_hour

        upcoming = [entry for entry in entries if _at_or_after_now(entry)]
        return upcoming if upcoming else entries

    def _value_near(self, series: Any, index: int) -> float | None:
        """
        Return the value at ``index``, or the nearest non-null value around it.

        Guards against sparse tails/gaps in the forecast where the exact current
        hour may be missing, scanning outward so a usable reading is still shown.
        """
        if not self._is_sequence(series):
            return None

        length = len(series)
        if length == 0:
            return None

        index = max(0, min(index, length - 1))
        direct = self._coerce_float(series[index])
        if direct is not None:
            return direct

        for step in range(1, length):
            ahead = index + step
            if ahead < length:
                value = self._coerce_float(series[ahead])
                if value is not None:
                    return value
            behind = index - step
            if behind >= 0:
                value = self._coerce_float(series[behind])
                if value is not None:
                    return value
        return None

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
        return isinstance(value, list | tuple) and len(value) > 0

    def _parse_local_aware(self, value: Any, utc_offset_seconds: Any) -> datetime | None:
        """
        Parse an Open-Meteo local timestamp into a timezone-aware datetime.

        With ``timezone=auto`` Open-Meteo returns naive wall-clock strings in the
        location's local time. Rather than mislabelling those as UTC, attach the
        location's real offset so the value represents the correct instant: it
        renders as local wall-clock via ``strftime`` and converts to true UTC via
        ``astimezone(UTC)``. This matches the location-local convention used for
        sunrise/sunset times.
        """
        dt = self._parse_naive(value)
        if dt is None:
            return None
        offset = utc_offset_seconds if isinstance(utc_offset_seconds, int | float) else 0
        return dt.replace(tzinfo=timezone(timedelta(seconds=offset)))

    def _parse_naive(self, value: Any) -> datetime | None:
        """
        Parse an Open-Meteo local timestamp as a naive (tz-free) datetime.

        Open-Meteo returns local wall-clock times when ``timezone=auto``. These
        are compared against a locally-offset "now" to locate the current hour,
        so they must stay naive rather than being coerced to UTC.
        """
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1]
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        return dt.replace(tzinfo=None)

    def _coerce_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
