"""Shared AI explanation generation helpers for the wx dialogs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from ...ai_explainer import ExplanationStyle

logger = logging.getLogger(__name__)


def resolve_ai_model(settings: Any) -> str:
    """Return the configured AI model name."""
    if settings.ai_model_preference == "auto":
        return "openrouter/auto"
    return settings.ai_model_preference


def resolve_explanation_style(settings: Any) -> ExplanationStyle:
    """Return the configured explanation style enum."""
    style_map = {
        "brief": ExplanationStyle.BRIEF,
        "standard": ExplanationStyle.STANDARD,
        "detailed": ExplanationStyle.DETAILED,
    }
    return style_map.get(settings.ai_explanation_style, ExplanationStyle.STANDARD)


def build_current_weather_payload(weather_data: Any) -> dict[str, Any]:
    """Build the AI explainer payload from current app weather data."""
    current = weather_data.current
    weather_dict: dict[str, Any] = {
        "temperature": current.temperature_f,
        "temperature_unit": "F",
        "conditions": current.condition,
        "humidity": current.humidity,
        "wind_speed": current.wind_speed_mph,
        "wind_direction": current.wind_direction,
        "visibility": current.visibility_miles,
        "pressure": current.pressure_in,
        "alerts": [],
        "forecast_periods": [],
    }

    if weather_data.alerts and weather_data.alerts.alerts:
        weather_dict["alerts"] = [
            {"title": alert.title, "severity": alert.severity}
            for alert in weather_data.alerts.alerts
        ]

    if weather_data.forecast and weather_data.forecast.periods:
        weather_dict["forecast_periods"] = [
            {
                "name": period.name,
                "temperature": period.temperature,
                "temperature_unit": period.temperature_unit,
                "short_forecast": period.short_forecast,
                "wind_speed": period.wind_speed,
                "wind_direction": period.wind_direction,
            }
            for period in weather_data.forecast.periods[:6]
        ]

    return weather_dict


def add_location_time_context(weather_dict: dict[str, Any], location: Any) -> None:
    """Add UTC and local time context for the selected weather location."""
    now_utc = datetime.now(UTC)
    weather_dict["utc_time"] = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    location_tz = getattr(location, "timezone", None)
    if not location_tz:
        return

    try:
        local_tz = ZoneInfo(location_tz)
        local_time = now_utc.astimezone(local_tz)
        weather_dict["local_time"] = local_time.strftime("%Y-%m-%d %H:%M")
        weather_dict["timezone"] = location_tz
        weather_dict["time_of_day"] = _time_of_day(local_time.hour)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Could not determine local time for {location_tz}: {exc}")


def _time_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"
