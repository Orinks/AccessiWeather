"""Seasonal metric helpers for current conditions presentation."""

from __future__ import annotations

from ...models import CurrentConditions
from ...utils import TemperatureUnit
from .models import Metric


def _build_seasonal_metrics(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: int,
) -> list[Metric]:
    """Build seasonal weather metrics (snow depth, wind chill, heat index, etc.)."""
    metrics: list[Metric] = []

    if current.snow_depth_in is not None and current.snow_depth_in > 0:
        if unit_pref == TemperatureUnit.CELSIUS:
            snow_depth_cm = current.snow_depth_cm or current.snow_depth_in * 2.54
            metrics.append(Metric("Snow on ground", f"{snow_depth_cm:.{precision}f} cm"))
        elif unit_pref == TemperatureUnit.FAHRENHEIT:
            metrics.append(Metric("Snow on ground", f"{current.snow_depth_in:.{precision}f} in"))
        else:
            snow_depth_cm = current.snow_depth_cm or current.snow_depth_in * 2.54
            metrics.append(
                Metric(
                    "Snow on ground",
                    f"{current.snow_depth_in:.{precision}f} in ({snow_depth_cm:.{precision}f} cm)",
                )
            )

    if current.wind_chill_f is not None:
        temp_f = current.temperature_f
        if temp_f is None or abs(current.wind_chill_f - temp_f) >= 3:
            wind_chill_c = current.wind_chill_c
            if wind_chill_c is None and current.wind_chill_f is not None:
                wind_chill_c = (current.wind_chill_f - 32) * 5 / 9
            wc_str = format_temperature_value(
                current.wind_chill_f, wind_chill_c, unit_pref, precision
            )
            if wc_str:
                metrics.append(Metric("Wind chill", wc_str))

    if current.freezing_level_ft is not None:
        if unit_pref == TemperatureUnit.CELSIUS:
            freezing_m = current.freezing_level_m or current.freezing_level_ft * 0.3048
            metrics.append(Metric("Freezing level", f"{freezing_m:.0f} m"))
        elif unit_pref == TemperatureUnit.FAHRENHEIT:
            metrics.append(Metric("Freezing level", f"{current.freezing_level_ft:.0f} ft"))
        else:
            freezing_m = current.freezing_level_m or current.freezing_level_ft * 0.3048
            metrics.append(
                Metric("Freezing level", f"{current.freezing_level_ft:.0f} ft ({freezing_m:.0f} m)")
            )

    if current.heat_index_f is not None:
        temp_f = current.temperature_f
        if temp_f is None or abs(current.heat_index_f - temp_f) >= 3:
            heat_index_c = current.heat_index_c
            if heat_index_c is None and current.heat_index_f is not None:
                heat_index_c = (current.heat_index_f - 32) * 5 / 9
            hi_str = format_temperature_value(
                current.heat_index_f, heat_index_c, unit_pref, precision
            )
            if hi_str:
                metrics.append(Metric("Heat index", hi_str))

    if current.frost_risk is not None and current.frost_risk.lower() != "none":
        metrics.append(Metric("Frost risk", current.frost_risk))

    has_active_precip = False
    if current.precipitation_type and len(current.precipitation_type) > 0:
        condition_lower = (current.condition or "").lower()
        precip_keywords = ["rain", "snow", "drizzle", "shower", "storm", "sleet", "hail", "precip"]
        has_active_precip = any(keyword in condition_lower for keyword in precip_keywords)

    if has_active_precip and current.precipitation_type:
        precip_types = ", ".join(current.precipitation_type)
        metrics.append(Metric("Precipitation type", precip_types.title()))

    if current.severe_weather_risk is not None and current.severe_weather_risk > 0:
        risk_level = _get_severe_risk_description(current.severe_weather_risk)
        metrics.append(
            Metric("Severe weather risk", f"{current.severe_weather_risk}% ({risk_level})")
        )

    return metrics


def format_temperature_value(
    temp_f: float | None,
    temp_c: float | None,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Format a temperature value based on unit preference."""
    if temp_f is None and temp_c is None:
        return None

    if unit_pref == TemperatureUnit.FAHRENHEIT:
        if temp_f is not None:
            return f"{temp_f:.{precision}f}°F"
        return None
    if unit_pref == TemperatureUnit.CELSIUS:
        if temp_c is not None:
            return f"{temp_c:.{precision}f}°C"
        if temp_f is not None:
            temp_c = (temp_f - 32) * 5 / 9
            return f"{temp_c:.{precision}f}°C"
        return None
    if temp_f is not None:
        if temp_c is None:
            temp_c = (temp_f - 32) * 5 / 9
        return f"{temp_f:.{precision}f}°F ({temp_c:.{precision}f}°C)"
    return None


def _get_severe_risk_description(risk: int) -> str:
    """Get a description for severe weather risk percentage."""
    if risk >= 80:
        return "Extreme"
    if risk >= 60:
        return "High"
    if risk >= 40:
        return "Moderate"
    if risk >= 20:
        return "Low"
    return "Minimal"
