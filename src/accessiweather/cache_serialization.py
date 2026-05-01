"""Serialization helpers for persisted weather cache entries."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from .models import (
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    SourceAttribution,
    TrendInsight,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)

logger = logging.getLogger(__name__)


def _serialize_datetime(value: datetime | None) -> dict[str, Any] | str | None:
    """
    Serialize a datetime, preserving the original timezone.

    Returns a dict with 'iso' (UTC) and timezone info keys.
    For named timezones (ZoneInfo), stores 'original_tz'.
    For fixed offset timezones, stores 'utc_offset_seconds'.
    """
    if value is None:
        return None
    dt_utc = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)

    result: dict[str, Any] = {"iso": dt_utc.isoformat()}

    if value.tzinfo is not None and value.tzinfo != UTC:
        # Try to get named timezone (ZoneInfo or pytz)
        tz_name = getattr(value.tzinfo, "key", None)
        if tz_name is None:
            tz_name = getattr(value.tzinfo, "zone", None)

        if tz_name and tz_name != "UTC":
            result["original_tz"] = tz_name
        else:
            # Fixed offset timezone (datetime.timezone) - store the offset
            try:
                offset = value.utcoffset()
                if offset is not None:
                    result["utc_offset_seconds"] = int(offset.total_seconds())
            except Exception:  # noqa: BLE001
                pass

    return result


def _deserialize_datetime(value: Any) -> datetime | None:
    """
    Deserialize a datetime, restoring the original timezone if stored.

    Handles:
    - New format with 'original_tz' (named timezone via ZoneInfo)
    - New format with 'utc_offset_seconds' (fixed offset timezone)
    - Legacy format (plain ISO string)
    """
    if value is None:
        return None

    if isinstance(value, dict):
        iso_str = value.get("iso")
        if not isinstance(iso_str, str) or not iso_str.strip():
            return None
        try:
            dt = datetime.fromisoformat(iso_str.strip())
        except ValueError:
            return None

        # Try named timezone first
        original_tz = value.get("original_tz")
        if original_tz and isinstance(original_tz, str):
            try:
                from zoneinfo import ZoneInfo

                tz = ZoneInfo(original_tz)
                return dt.astimezone(tz)
            except (KeyError, ValueError, ImportError):
                pass

        # Try fixed offset timezone
        utc_offset = value.get("utc_offset_seconds")
        if utc_offset is not None:
            try:
                tz = timezone(timedelta(seconds=int(utc_offset)))
                return dt.astimezone(tz)
            except (ValueError, TypeError):
                pass

        return dt

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

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
    }


def _deserialize_current(data: dict | None) -> CurrentConditions | None:
    if not isinstance(data, dict):
        return None

    sunrise_raw = data.get("sunrise_time")
    sunset_raw = data.get("sunset_time")

    sunrise = _deserialize_datetime(sunrise_raw)
    sunset = _deserialize_datetime(sunset_raw)

    logger.debug(
        f"Deserializing current conditions from cache - "
        f"sunrise: {sunrise_raw} -> {sunrise}, "
        f"sunset: {sunset_raw} -> {sunset}"
    )

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
        sunrise_time=sunrise,
        sunset_time=sunset,
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
        "humidity": period.humidity,
        "dewpoint_f": period.dewpoint_f,
        "dewpoint_c": period.dewpoint_c,
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
        humidity=data.get("humidity"),
        dewpoint_f=data.get("dewpoint_f"),
        dewpoint_c=data.get("dewpoint_c"),
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
    payload: dict = {
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
    # Only include ``affected_zones`` when populated — legacy cache entries
    # never carried the key and we keep the shape stable for the common case.
    if alert.affected_zones:
        payload["affected_zones"] = list(alert.affected_zones)
    return payload


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
        affected_zones=list(data.get("affected_zones", [])),
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


def _serialize_source_attribution(attribution: SourceAttribution | None) -> dict | None:
    """Serialize source attribution for cache storage."""
    if attribution is None:
        return None
    return {
        "contributing_sources": list(attribution.contributing_sources),
        "failed_sources": list(attribution.failed_sources),
        "field_sources": attribution.field_sources,
    }


def _deserialize_source_attribution(data: dict | None) -> SourceAttribution | None:
    """Deserialize source attribution from cache storage."""
    if not isinstance(data, dict):
        return None
    return SourceAttribution(
        contributing_sources=set(data.get("contributing_sources", [])),
        failed_sources=set(data.get("failed_sources", [])),
        field_sources=data.get("field_sources", {}),
    )


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
        "environmental": _serialize_environmental(weather.environmental),
        "trend_insights": _serialize_trends(weather.trend_insights),
        "source_attribution": _serialize_source_attribution(weather.source_attribution),
        "incomplete_sections": list(weather.incomplete_sections),
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
        discussion_issuance_time=_deserialize_datetime(data.get("discussion_issuance_time")),
        alerts=_deserialize_alerts(data.get("alerts")),
        environmental=_deserialize_environmental(data.get("environmental")),
        trend_insights=_deserialize_trends(data.get("trend_insights")),
        source_attribution=_deserialize_source_attribution(data.get("source_attribution")),
        incomplete_sections=set(data.get("incomplete_sections", [])),
    )
    weather.stale = bool(data.get("stale", False))
    weather.stale_since = _deserialize_datetime(data.get("stale_since"))
    weather.stale_reason = data.get("stale_reason")
    return weather


def _safe_location_key(location: Location) -> str:
    raw = f"{location.name}-{location.latitude}-{location.longitude}"
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", raw).strip("_") or "location"
