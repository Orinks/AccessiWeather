"""Shared AI explanation generation helpers for the wx dialogs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from ...ai_explainer import ExplanationStyle
from ...units import resolve_display_unit_system, resolve_temperature_unit_preference
from ...utils.temperature_utils import TemperatureUnit, format_temperature
from ...utils.unit_utils import format_pressure, format_visibility, format_wind_speed

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


def build_current_weather_payload(
    weather_data: Any,
    *,
    temperature_unit_preference: str | None = "both",
    location: Any | None = None,
) -> dict[str, Any]:
    """Build the AI explainer payload from current app weather data."""
    current = weather_data.current
    unit_pref = resolve_temperature_unit_preference(temperature_unit_preference, location)
    unit_system = resolve_display_unit_system(temperature_unit_preference, location)

    temperature, temperature_unit = _resolve_temperature_for_prompt(current, unit_pref)
    weather_dict: dict[str, Any] = {
        "temperature": temperature,
        "temperature_unit": temperature_unit,
        "temperature_text": _formatted_or_none(
            format_temperature(
                current.temperature_f,
                unit=unit_pref,
                temperature_c=current.temperature_c,
            )
        ),
        "conditions": current.condition,
        "humidity": current.humidity,
        "wind_speed": _resolve_wind_speed_for_prompt(current, unit_pref, unit_system),
        "wind_speed_unit": _resolve_wind_speed_unit_label(unit_pref, unit_system),
        "wind_text": _formatted_or_none(
            format_wind_speed(
                current.wind_speed_mph,
                unit=unit_pref,
                wind_speed_kph=current.wind_speed_kph,
                unit_system=unit_system,
            )
        ),
        "wind_direction": current.wind_direction,
        "visibility": _resolve_visibility_for_prompt(current, unit_pref, unit_system),
        "visibility_unit": _resolve_visibility_unit_label(unit_pref, unit_system),
        "visibility_text": _formatted_or_none(
            format_visibility(
                current.visibility_miles,
                unit=unit_pref,
                visibility_km=current.visibility_km,
                unit_system=unit_system,
            )
        ),
        "pressure": _resolve_pressure_for_prompt(current, unit_pref, unit_system),
        "pressure_unit": _resolve_pressure_unit_label(unit_pref, unit_system),
        "pressure_text": _formatted_or_none(
            format_pressure(
                current.pressure_in,
                unit=unit_pref,
                pressure_mb=current.pressure_mb,
                unit_system=unit_system,
            )
        ),
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


def _formatted_or_none(value: str) -> str | None:
    return None if value == "N/A" else value


def _resolve_temperature_for_prompt(
    current: Any, unit_pref: TemperatureUnit
) -> tuple[float | None, str]:
    if current.temperature_f is None and current.temperature_c is not None:
        temperature_f = (current.temperature_c * 9 / 5) + 32
    else:
        temperature_f = current.temperature_f

    if current.temperature_c is None and current.temperature_f is not None:
        temperature_c = (current.temperature_f - 32) * 5 / 9
    else:
        temperature_c = current.temperature_c

    if unit_pref == TemperatureUnit.CELSIUS:
        return temperature_c, "C"
    if unit_pref == TemperatureUnit.BOTH:
        return temperature_f, "F"
    return temperature_f, "F"


def _resolve_wind_speed_for_prompt(
    current: Any, unit_pref: TemperatureUnit, unit_system: Any | None
) -> float | None:
    wind_speed_mph = current.wind_speed_mph
    wind_speed_kph = current.wind_speed_kph
    if wind_speed_mph is None and wind_speed_kph is not None:
        wind_speed_mph = wind_speed_kph * 0.621371
    elif wind_speed_kph is None and wind_speed_mph is not None:
        wind_speed_kph = wind_speed_mph * 1.60934

    normalized_system = getattr(unit_system, "value", unit_system)
    if normalized_system == "ca":
        return wind_speed_kph
    if normalized_system == "si":
        return wind_speed_kph / 3.6 if wind_speed_kph is not None else None
    if normalized_system in {"us", "uk"}:
        return wind_speed_mph
    if unit_pref == TemperatureUnit.CELSIUS:
        return wind_speed_kph
    return wind_speed_mph


def _resolve_wind_speed_unit_label(unit_pref: TemperatureUnit, unit_system: Any | None) -> str:
    normalized_system = getattr(unit_system, "value", unit_system)
    if normalized_system in {"us", "uk"}:
        return "mph"
    if normalized_system == "ca":
        return "km/h"
    if normalized_system == "si":
        return "m/s"
    if unit_pref == TemperatureUnit.CELSIUS:
        return "km/h"
    if unit_pref == TemperatureUnit.BOTH:
        return "mph (km/h)"
    return "mph"


def _resolve_visibility_for_prompt(
    current: Any, unit_pref: TemperatureUnit, unit_system: Any | None
) -> float | None:
    visibility_miles = current.visibility_miles
    visibility_km = current.visibility_km
    if visibility_miles is None and visibility_km is not None:
        visibility_miles = visibility_km * 0.621371
    elif visibility_km is None and visibility_miles is not None:
        visibility_km = visibility_miles * 1.60934

    normalized_system = getattr(unit_system, "value", unit_system)
    if normalized_system in {"us", "uk"}:
        return visibility_miles
    if normalized_system in {"ca", "si"}:
        return visibility_km
    if unit_pref == TemperatureUnit.CELSIUS:
        return visibility_km
    return visibility_miles


def _resolve_visibility_unit_label(unit_pref: TemperatureUnit, unit_system: Any | None) -> str:
    normalized_system = getattr(unit_system, "value", unit_system)
    if normalized_system in {"us", "uk"}:
        return "mi"
    if normalized_system in {"ca", "si"}:
        return "km"
    if unit_pref == TemperatureUnit.CELSIUS:
        return "km"
    if unit_pref == TemperatureUnit.BOTH:
        return "mi (km)"
    return "mi"


def _resolve_pressure_for_prompt(
    current: Any, unit_pref: TemperatureUnit, unit_system: Any | None
) -> float | None:
    pressure_in = current.pressure_in
    pressure_mb = current.pressure_mb
    if pressure_in is None and pressure_mb is not None:
        pressure_in = pressure_mb / 33.8639
    elif pressure_mb is None and pressure_in is not None:
        pressure_mb = pressure_in * 33.8639

    normalized_system = getattr(unit_system, "value", unit_system)
    if normalized_system == "ca":
        return pressure_mb / 10 if pressure_mb is not None else None
    if normalized_system in {"uk", "si"}:
        return pressure_mb
    if unit_pref == TemperatureUnit.CELSIUS:
        return pressure_mb
    return pressure_in


def _resolve_pressure_unit_label(unit_pref: TemperatureUnit, unit_system: Any | None) -> str:
    normalized_system = getattr(unit_system, "value", unit_system)
    if normalized_system == "ca":
        return "kPa"
    if normalized_system in {"uk", "si"}:
        return "hPa"
    if unit_pref == TemperatureUnit.CELSIUS:
        return "hPa"
    if unit_pref == TemperatureUnit.BOTH:
        return "inHg (hPa)"
    return "inHg"


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
