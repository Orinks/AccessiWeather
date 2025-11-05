"""
Cache module for AccessiWeather.

This module provides caching functionality to reduce API calls and improve performance.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .models import (
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cache entry with value and expiration time."""

    value: Any
    expiration: float  # Expiration time as Unix timestamp


class Cache:
    """A simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 300):
        """
        Initialize the cache.

        Args:
        ----
            default_ttl: Default time-to-live in seconds (default: 5 minutes)

        """
        self.data: dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        logger.debug(f"Initialized cache with default TTL of {default_ttl} seconds")

    def get(self, key: str) -> Any | None:
        """
        Get a value from the cache.

        Args:
        ----
            key: The cache key

        Returns:
        -------
            The cached value or None if not found or expired

        """
        if key not in self.data:
            return None

        entry = self.data[key]
        current_time = time.time()

        # Check if the entry has expired
        if entry.expiration < current_time:
            logger.debug(f"Cache entry for '{key}' has expired")
            # Remove the expired entry
            del self.data[key]
            return None

        logger.debug(f"Cache hit for '{key}'")
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """
        Set a value in the cache.

        Args:
        ----
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds (uses default_ttl if None)

        """
        if ttl is None:
            ttl = self.default_ttl

        expiration = time.time() + ttl
        self.data[key] = CacheEntry(value=value, expiration=expiration)
        logger.debug(f"Cached value for '{key}' with TTL of {ttl} seconds")

    def has_key(self, key: str) -> bool:
        """
        Check if a key exists in the cache and is not expired.

        Args:
        ----
            key: The cache key

        Returns:
        -------
            True if the key exists and is not expired, False otherwise

        """
        if key not in self.data:
            return False

        entry = self.data[key]
        current_time = time.time()

        # Check if the entry has expired
        if entry.expiration < current_time:
            # Remove the expired entry
            del self.data[key]
            return False

        return True

    def invalidate(self, key: str) -> None:
        """
        Invalidate a specific cache entry.

        Args:
        ----
            key: The cache key to invalidate

        """
        if key in self.data:
            del self.data[key]
            logger.debug(f"Invalidated cache entry for '{key}'")

    def clear(self) -> None:
        """Clear all cache entries."""
        self.data.clear()
        logger.debug("Cleared all cache entries")

    def cleanup(self) -> None:
        """Remove all expired entries from the cache."""
        current_time = time.time()
        expired_keys = [key for key, entry in self.data.items() if entry.expiration < current_time]

        for key in expired_keys:
            del self.data[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    dt = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    return dt.isoformat()


def _deserialize_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _serialize_current(current: CurrentConditions | None) -> dict | None:
    if current is None:
        return None
    return {
        "temperature_f": current.temperature_f,
        "temperature_c": current.temperature_c,
        "condition": current.condition,
        "humidity": current.humidity,
        "dewpoint_f": current.dewpoint_f,
        "dewpoint_c": current.dewpoint_c,
        "wind_speed_mph": current.wind_speed_mph,
        "wind_speed_kph": current.wind_speed_kph,
        "wind_direction": current.wind_direction,
        "pressure_in": current.pressure_in,
        "pressure_mb": current.pressure_mb,
        "feels_like_f": current.feels_like_f,
        "feels_like_c": current.feels_like_c,
        "visibility_miles": current.visibility_miles,
        "visibility_km": current.visibility_km,
        "uv_index": current.uv_index,
        "sunrise_time": _serialize_datetime(current.sunrise_time),
        "sunset_time": _serialize_datetime(current.sunset_time),
        "last_updated": _serialize_datetime(current.last_updated),
    }


def _deserialize_current(data: dict | None) -> CurrentConditions | None:
    if not isinstance(data, dict):
        return None
    return CurrentConditions(
        temperature_f=data.get("temperature_f"),
        temperature_c=data.get("temperature_c"),
        condition=data.get("condition"),
        humidity=data.get("humidity"),
        dewpoint_f=data.get("dewpoint_f"),
        dewpoint_c=data.get("dewpoint_c"),
        wind_speed_mph=data.get("wind_speed_mph"),
        wind_speed_kph=data.get("wind_speed_kph"),
        wind_direction=data.get("wind_direction"),
        pressure_in=data.get("pressure_in"),
        pressure_mb=data.get("pressure_mb"),
        feels_like_f=data.get("feels_like_f"),
        feels_like_c=data.get("feels_like_c"),
        visibility_miles=data.get("visibility_miles"),
        visibility_km=data.get("visibility_km"),
        uv_index=data.get("uv_index"),
        sunrise_time=_deserialize_datetime(data.get("sunrise_time")),
        sunset_time=_deserialize_datetime(data.get("sunset_time")),
        last_updated=_deserialize_datetime(data.get("last_updated")),
    )


def _serialize_forecast_period(period: ForecastPeriod) -> dict:
    return {
        "name": period.name,
        "temperature": period.temperature,
        "temperature_unit": period.temperature_unit,
        "short_forecast": period.short_forecast,
        "detailed_forecast": period.detailed_forecast,
        "wind_speed": period.wind_speed,
        "wind_direction": period.wind_direction,
        "icon": period.icon,
        "start_time": _serialize_datetime(period.start_time),
        "end_time": _serialize_datetime(period.end_time),
    }


def _deserialize_forecast_period(data: dict) -> ForecastPeriod:
    return ForecastPeriod(
        name=data.get("name", ""),
        temperature=data.get("temperature"),
        temperature_unit=data.get("temperature_unit", "F"),
        short_forecast=data.get("short_forecast"),
        detailed_forecast=data.get("detailed_forecast"),
        wind_speed=data.get("wind_speed"),
        wind_direction=data.get("wind_direction"),
        icon=data.get("icon"),
        start_time=_deserialize_datetime(data.get("start_time")),
        end_time=_deserialize_datetime(data.get("end_time")),
    )


def _serialize_forecast(forecast: Forecast | None) -> dict | None:
    if forecast is None:
        return None
    return {
        "periods": [_serialize_forecast_period(p) for p in forecast.periods],
        "generated_at": _serialize_datetime(forecast.generated_at),
    }


def _deserialize_forecast(data: dict | None) -> Forecast | None:
    if not isinstance(data, dict):
        return None
    periods_data = data.get("periods") or []
    periods = [_deserialize_forecast_period(p) for p in periods_data if isinstance(p, dict)]
    return Forecast(periods=periods, generated_at=_deserialize_datetime(data.get("generated_at")))


def _serialize_hourly_period(period: HourlyForecastPeriod) -> dict:
    return {
        "start_time": _serialize_datetime(period.start_time),
        "end_time": _serialize_datetime(period.end_time),
        "temperature": period.temperature,
        "temperature_unit": period.temperature_unit,
        "short_forecast": period.short_forecast,
        "wind_speed": period.wind_speed,
        "wind_direction": period.wind_direction,
        "icon": period.icon,
        "pressure_mb": period.pressure_mb,
        "pressure_in": period.pressure_in,
    }


def _deserialize_hourly_period(data: dict) -> HourlyForecastPeriod:
    start_time = _deserialize_datetime(data.get("start_time")) or datetime.now()
    return HourlyForecastPeriod(
        start_time=start_time,
        end_time=_deserialize_datetime(data.get("end_time")),
        temperature=data.get("temperature"),
        temperature_unit=data.get("temperature_unit", "F"),
        short_forecast=data.get("short_forecast"),
        wind_speed=data.get("wind_speed"),
        wind_direction=data.get("wind_direction"),
        icon=data.get("icon"),
        pressure_mb=data.get("pressure_mb"),
        pressure_in=data.get("pressure_in"),
    )


def _serialize_hourly(hourly: HourlyForecast | None) -> dict | None:
    if hourly is None:
        return None
    return {
        "periods": [_serialize_hourly_period(p) for p in hourly.periods],
        "generated_at": _serialize_datetime(hourly.generated_at),
    }


def _deserialize_hourly(data: dict | None) -> HourlyForecast | None:
    if not isinstance(data, dict):
        return None
    periods_data = data.get("periods") or []
    periods = [_deserialize_hourly_period(p) for p in periods_data if isinstance(p, dict)]
    return HourlyForecast(
        periods=periods, generated_at=_deserialize_datetime(data.get("generated_at"))
    )


def _serialize_alert(alert: WeatherAlert) -> dict:
    return {
        "title": alert.title,
        "description": alert.description,
        "severity": alert.severity,
        "urgency": alert.urgency,
        "certainty": alert.certainty,
        "event": alert.event,
        "headline": alert.headline,
        "instruction": alert.instruction,
        "onset": _serialize_datetime(alert.onset),
        "expires": _serialize_datetime(alert.expires),
        "areas": alert.areas,
        "id": alert.id,
        "source": alert.source,
    }


def _deserialize_alert(data: dict) -> WeatherAlert:
    return WeatherAlert(
        title=data.get("title", "Weather Alert"),
        description=data.get("description", ""),
        severity=data.get("severity", "Unknown"),
        urgency=data.get("urgency", "Unknown"),
        certainty=data.get("certainty", "Unknown"),
        event=data.get("event"),
        headline=data.get("headline"),
        instruction=data.get("instruction"),
        onset=_deserialize_datetime(data.get("onset")),
        expires=_deserialize_datetime(data.get("expires")),
        areas=list(data.get("areas", [])),
        id=data.get("id"),
        source=data.get("source"),
    )


def _serialize_alerts(alerts: WeatherAlerts | None) -> dict | None:
    if alerts is None:
        return None
    return {"alerts": [_serialize_alert(a) for a in alerts.alerts]}


def _deserialize_alerts(data: dict | None) -> WeatherAlerts | None:
    if not isinstance(data, dict):
        return None
    alerts = [_deserialize_alert(a) for a in data.get("alerts", []) if isinstance(a, dict)]
    return WeatherAlerts(alerts=alerts)


def _serialize_environmental(env: EnvironmentalConditions | None) -> dict | None:
    if env is None:
        return None
    return {
        "air_quality_index": env.air_quality_index,
        "air_quality_category": env.air_quality_category,
        "air_quality_pollutant": env.air_quality_pollutant,
        "pollen_index": env.pollen_index,
        "pollen_category": env.pollen_category,
        "pollen_tree_index": env.pollen_tree_index,
        "pollen_grass_index": env.pollen_grass_index,
        "pollen_weed_index": env.pollen_weed_index,
        "pollen_primary_allergen": env.pollen_primary_allergen,
        "updated_at": _serialize_datetime(env.updated_at),
        "sources": env.sources,
    }


def _deserialize_environmental(data: dict | None) -> EnvironmentalConditions | None:
    if not isinstance(data, dict):
        return None
    env = EnvironmentalConditions(
        air_quality_index=data.get("air_quality_index"),
        air_quality_category=data.get("air_quality_category"),
        air_quality_pollutant=data.get("air_quality_pollutant"),
        pollen_index=data.get("pollen_index"),
        pollen_category=data.get("pollen_category"),
        pollen_tree_index=data.get("pollen_tree_index"),
        pollen_grass_index=data.get("pollen_grass_index"),
        pollen_weed_index=data.get("pollen_weed_index"),
        pollen_primary_allergen=data.get("pollen_primary_allergen"),
        updated_at=_deserialize_datetime(data.get("updated_at")),
        sources=list(data.get("sources", [])),
    )
    return env if env.has_data() else None


def _serialize_trends(trends: list[TrendInsight]) -> list[dict]:
    return [
        {
            "metric": trend.metric,
            "direction": trend.direction,
            "change": trend.change,
            "unit": trend.unit,
            "timeframe_hours": trend.timeframe_hours,
            "summary": trend.summary,
            "sparkline": trend.sparkline,
        }
        for trend in trends
    ]


def _deserialize_trends(data: list | None) -> list[TrendInsight]:
    if not isinstance(data, list):
        return []
    trends: list[TrendInsight] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        trends.append(
            TrendInsight(
                metric=entry.get("metric", ""),
                direction=entry.get("direction", "steady"),
                change=entry.get("change"),
                unit=entry.get("unit"),
                timeframe_hours=int(entry.get("timeframe_hours", 24)),
                summary=entry.get("summary"),
                sparkline=entry.get("sparkline"),
            )
        )
    return trends


def _serialize_weather_data(weather: WeatherData) -> dict:
    return {
        "current": _serialize_current(weather.current),
        "forecast": _serialize_forecast(weather.forecast),
        "hourly_forecast": _serialize_hourly(weather.hourly_forecast),
        "discussion": weather.discussion,
        "alerts": _serialize_alerts(weather.alerts),
        "last_updated": _serialize_datetime(weather.last_updated),
        "environmental": _serialize_environmental(weather.environmental),
        "trend_insights": _serialize_trends(weather.trend_insights),
        "stale": weather.stale,
        "stale_since": _serialize_datetime(weather.stale_since),
        "stale_reason": weather.stale_reason,
    }


def _deserialize_weather_data(data: dict, location: Location) -> WeatherData:
    weather = WeatherData(
        location=location,
        current=_deserialize_current(data.get("current")),
        forecast=_deserialize_forecast(data.get("forecast")),
        hourly_forecast=_deserialize_hourly(data.get("hourly_forecast")),
        discussion=data.get("discussion"),
        alerts=_deserialize_alerts(data.get("alerts")),
        last_updated=_deserialize_datetime(data.get("last_updated")),
        environmental=_deserialize_environmental(data.get("environmental")),
        trend_insights=_deserialize_trends(data.get("trend_insights")),
    )
    weather.stale = bool(data.get("stale", False))
    weather.stale_since = _deserialize_datetime(data.get("stale_since"))
    weather.stale_reason = data.get("stale_reason")
    return weather


def _safe_location_key(location: Location) -> str:
    raw = f"{location.name}-{location.latitude}-{location.longitude}"
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", raw).strip("_") or "location"


class WeatherDataCache:
    """Persist the latest weather data per location for offline fallback."""

    def __init__(self, cache_dir: str | Path, max_age_minutes: int = 180):
        """
        Initialize the cache.

        Args:
        ----
            cache_dir: Directory where cache files are stored.
            max_age_minutes: Age threshold before cached entries expire.

        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age = timedelta(minutes=max_age_minutes)

    def store(self, location: Location, weather: WeatherData) -> None:
        try:
            payload = {
                "version": 1,
                "saved_at": _serialize_datetime(datetime.now(UTC)),
                "location": {
                    "name": location.name,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    **({"country_code": location.country_code} if location.country_code else {}),
                },
                "weather": _serialize_weather_data(weather),
            }
            path = self._path_for_location(location)
            with path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to persist weather cache: {exc}")

    def load(self, location: Location, *, allow_stale: bool = True) -> WeatherData | None:
        path = self._path_for_location(location)
        if not path.exists():
            return None

        try:
            with path.open(encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Failed to read cached weather data: {exc}")
            return None

        saved_at = _deserialize_datetime(payload.get("saved_at")) or datetime.now(UTC)
        age = datetime.now(UTC) - saved_at
        if not allow_stale and age > self.max_age:
            return None

        location_data = payload.get("location") or {}
        loc_name = location_data.get("name", location.name)
        loc_lat = location_data.get("latitude", location.latitude)
        loc_lon = location_data.get("longitude", location.longitude)
        normalized_location = Location(
            name=loc_name,
            latitude=loc_lat,
            longitude=loc_lon,
            country_code=location_data.get("country_code"),
        )

        weather_payload = payload.get("weather")
        if not isinstance(weather_payload, dict):
            return None

        weather = _deserialize_weather_data(weather_payload, normalized_location)
        weather.stale = age > self.max_age
        weather.stale_since = saved_at
        weather.stale_reason = "Cached data"
        return weather

    def purge_expired(self) -> None:
        now = datetime.now(UTC)
        for path in self.cache_dir.glob("*.json"):
            try:
                with path.open(encoding="utf-8") as fh:
                    payload = json.load(fh)
                saved_at = _deserialize_datetime(payload.get("saved_at")) or now
                if now - saved_at > self.max_age * 2:
                    path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                path.unlink(missing_ok=True)

    def invalidate(self, location: Location) -> None:
        """
        Invalidate cache entry for a specific location.

        Args:
        ----
            location: The location to invalidate cache for

        """
        path = self._path_for_location(location)
        if path.exists():
            path.unlink(missing_ok=True)
            logger.debug(f"Invalidated cache for location '{location.name}'")

    def _path_for_location(self, location: Location) -> Path:
        filename = f"{_safe_location_key(location)}.json"
        return self.cache_dir / filename
