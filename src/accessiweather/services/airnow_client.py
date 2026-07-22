"""Client for current U.S. Air Quality Index observations from AirNow."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from ..cache import Cache
from ..models import Location

logger = logging.getLogger(__name__)

_NO_OBSERVATION = object()


@dataclass(frozen=True, slots=True)
class AirNowObservation:
    """Highest current pollutant AQI returned for a location."""

    aqi: int
    category: str
    pollutant: str
    observed_at: datetime | None = None
    reporting_area: str | None = None


class AirNowClient:
    """Fetch and cache current AirNow observations by latitude and longitude."""

    ENDPOINT = "https://www.airnowapi.org/aq/observation/current/ziplatlong/"
    DEFAULT_CACHE_TTL_SECONDS = 60 * 60
    # Washington, DC: reliably inside AirNow coverage for key validation.
    VALIDATION_COORDINATES = (38.8977, -77.0365)

    _TIMEZONE_OFFSETS = {
        "UTC": 0,
        "GMT": 0,
        "AST": -4,
        "ADT": -3,
        "EST": -5,
        "EDT": -4,
        "CST": -6,
        "CDT": -5,
        "MST": -7,
        "MDT": -6,
        "PST": -8,
        "PDT": -7,
        "AKST": -9,
        "AKDT": -8,
        "HST": -10,
        "HAST": -10,
        "HADT": -9,
        "SST": -11,
        "CHST": 10,
    }

    def __init__(
        self,
        api_key: object,
        user_agent: str = "AccessiWeather/2.0",
        timeout: float = 10.0,
        *,
        distance: int = 25,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        """Initialize the client without resolving a lazy secure-storage key."""
        self._api_key = api_key
        self.user_agent = user_agent
        self.timeout = timeout
        self.distance = max(1, int(distance))
        self._cache = Cache(default_ttl=max(1, int(cache_ttl_seconds)))

    @property
    def api_key(self) -> str:
        """Resolve and trim the API key only when an AirNow request is needed."""
        if self._api_key is None or self._api_key == "":
            return ""
        return str(self._api_key).strip()

    async def fetch_current_air_quality(self, location: Location) -> AirNowObservation | None:
        """Return the highest valid current pollutant AQI near ``location``."""
        latitude, longitude = self._validated_coordinates(location)
        cache_key = self._cache_key(latitude, longitude)
        cached = self._cache.get(cache_key)
        if cached is _NO_OBSERVATION:
            return None
        if isinstance(cached, AirNowObservation):
            return cached

        api_key = self.api_key
        if not api_key:
            return None

        params = {
            "format": "application/json",
            "latitude": latitude,
            "longitude": longitude,
            "distance": self.distance,
            "API_KEY": api_key,
        }
        headers = {"User-Agent": self.user_agent}

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(self.ENDPOINT, params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001 - provider failure must allow fallback
            # Do not log the exception text: httpx errors may include the request URL,
            # whose query string contains the AirNow API key.
            logger.warning("AirNow current AQI request failed (%s)", type(exc).__name__)
            return None

        observation = self._parse_observations(payload)
        if observation is not None:
            self._cache.set(cache_key, observation)
        elif isinstance(payload, list):
            # A successful response with no usable nearby observation is still a
            # provider result. Cache it so routine refreshes do not retry hourly.
            self._cache.set(cache_key, _NO_OBSERVATION)
        return observation

    async def validate_api_key(self) -> tuple[bool, str | None]:
        """
        Check the configured API key against the live AirNow API.

        Returns ``(True, None)`` for a working key, otherwise ``(False, reason)``.
        The reason never includes the request URL, which carries the key.
        """
        api_key = self.api_key
        if not api_key:
            return False, "No API key provided"

        latitude, longitude = self.VALIDATION_COORDINATES
        params = {
            "format": "application/json",
            "latitude": latitude,
            "longitude": longitude,
            "distance": self.distance,
            "API_KEY": api_key,
        }
        headers = {"User-Agent": self.user_agent}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(self.ENDPOINT, params=params)
        except Exception as exc:  # noqa: BLE001 - reason must not leak the keyed URL
            return False, f"Could not reach AirNow ({type(exc).__name__})"

        if response.status_code in (401, 403):
            return False, "Invalid API key"
        if response.status_code == 429:
            return False, "Rate limit exceeded — but key appears valid"
        if response.status_code >= 400:
            return False, f"AirNow returned HTTP {response.status_code}"

        try:
            payload = response.json()
        except ValueError:
            return False, "Unexpected response from AirNow"
        if isinstance(payload, list):
            return True, None
        if isinstance(payload, dict) and "WebServiceError" in payload:
            # Some AirNow errors come back as HTTP 200 with an error body.
            return False, "Invalid API key"
        return False, "Unexpected response from AirNow"

    def clear_cache(self) -> None:
        """Clear cached observations, primarily when runtime settings change."""
        self._cache.clear()

    def _validated_coordinates(self, location: Location) -> tuple[float, float]:
        latitude = self._coerce_coordinate(getattr(location, "latitude", None), "latitude")
        longitude = self._coerce_coordinate(getattr(location, "longitude", None), "longitude")
        if not -90 <= latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
        return latitude, longitude

    @staticmethod
    def _coerce_coordinate(value: Any, name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be numeric")
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if not math.isfinite(result):
            raise ValueError(f"{name} must be finite")
        return result

    def _cache_key(self, latitude: float, longitude: float) -> str:
        return f"{latitude:.4f},{longitude:.4f},{self.distance}"

    @staticmethod
    def _field(item: dict[str, Any], *names: str) -> Any:
        """
        Return the first present field among documented and live API spellings.

        The documented AirNow schema uses PascalCase (``AQI``, ``ReportingArea``);
        the live API now returns camelCase with renamed fields (``nowcastAQI``,
        ``reportingAreaName``). Both must parse.
        """
        for name in names:
            if name in item:
                return item[name]
        return None

    def _parse_observations(self, payload: Any) -> AirNowObservation | None:
        if not isinstance(payload, list):
            return None

        selected: dict[str, Any] | None = None
        selected_aqi = -1
        for item in payload:
            if not isinstance(item, dict):
                continue
            aqi = self._coerce_aqi(self._field(item, "AQI", "nowcastAQI"))
            if aqi is None or aqi <= selected_aqi:
                continue
            selected = item
            selected_aqi = aqi

        if selected is None:
            return None

        category = self._category_name(self._field(selected, "Category", "aqiCategoryName"))
        pollutant = self._field(selected, "ParameterName", "parameterName")
        reporting_area = self._field(selected, "ReportingArea", "reportingAreaName")
        return AirNowObservation(
            aqi=selected_aqi,
            category=category or self._air_quality_category(selected_aqi),
            pollutant=(
                pollutant.strip() if isinstance(pollutant, str) and pollutant.strip() else "Unknown"
            ),
            observed_at=self._parse_observed_at(selected),
            reporting_area=(
                reporting_area.strip()
                if isinstance(reporting_area, str) and reporting_area.strip()
                else None
            ),
        )

    @staticmethod
    def _coerce_aqi(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric) or numeric < 0:
            return None
        return int(round(numeric))

    @staticmethod
    def _coerce_hour(value: Any) -> int | None:
        """Accept the documented integer hour or the live API's ``"HH:MM"`` string."""
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, str):
            value = value.strip().split(":", 1)[0]
        try:
            hour = int(value)
        except (TypeError, ValueError):
            return None
        return hour if 0 <= hour <= 23 else None

    @staticmethod
    def _category_name(value: Any) -> str | None:
        if isinstance(value, dict):
            value = value.get("Name")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _parse_observed_at(self, item: dict[str, Any]) -> datetime | None:
        date_value = self._field(item, "DateObserved", "dateObserved")
        hour_value = self._field(item, "HourObserved", "hourObserved")
        if not isinstance(date_value, str):
            return None

        parsed_date = None
        for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                parsed_date = datetime.strptime(date_value.strip(), date_format).date()
                break
            except ValueError:
                continue
        if parsed_date is None:
            return None

        hour = self._coerce_hour(hour_value)
        if hour is None:
            return None

        tzinfo = self._parse_timezone(self._field(item, "LocalTimeZone", "localTimeZone"))
        return datetime(
            parsed_date.year,
            parsed_date.month,
            parsed_date.day,
            hour,
            tzinfo=tzinfo,
        )

    def _parse_timezone(self, value: Any) -> tzinfo | None:
        if not isinstance(value, str) or not value.strip():
            return None
        name = value.strip()
        offset_hours = self._TIMEZONE_OFFSETS.get(name.upper())
        if offset_hours is not None:
            return timezone(timedelta(hours=offset_hours), name=name.upper())
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            return None

    @staticmethod
    def _air_quality_category(value: int) -> str:
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
