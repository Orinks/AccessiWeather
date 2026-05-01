"""Prompt and context helpers for the Weather Assistant dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp


def build_weather_context(app: AccessiWeatherApp) -> str:
    """Build a weather context string from the app's current data."""
    weather = app.current_weather_data
    if not weather:
        return "No weather data currently loaded."

    parts: list[str] = []
    loc = weather.location
    parts.append(f"Location: {loc.name} ({loc.latitude}, {loc.longitude})")

    cur = weather.current
    if cur:
        if cur.temperature_f is not None:
            parts.append(f"Temperature: {cur.temperature_f:.0f}°F")
        if cur.feels_like_f is not None:
            parts.append(f"Feels like: {cur.feels_like_f:.0f}°F")
        if cur.condition:
            parts.append(f"Conditions: {cur.condition}")
        if cur.humidity is not None:
            parts.append(f"Humidity: {cur.humidity}%")
        if cur.wind_speed_mph is not None:
            wind = f"Wind: {cur.wind_speed_mph:.0f} mph"
            if cur.wind_direction:
                wind += f" from {cur.wind_direction}"
            parts.append(wind)
        if cur.pressure_in is not None:
            parts.append(f"Pressure: {cur.pressure_in:.2f} inHg")
        if cur.visibility_miles is not None:
            parts.append(f"Visibility: {cur.visibility_miles:.1f} miles")
        if cur.uv_index is not None:
            parts.append(f"UV Index: {cur.uv_index}")

    forecast = weather.forecast
    if forecast and forecast.periods:
        parts.append("\nForecast:")
        for period in forecast.periods[:6]:
            line = f"  {period.name}: {period.temperature}°{period.temperature_unit}"
            if period.short_forecast:
                line += f", {period.short_forecast}"
            parts.append(line)

    if weather.alerts and weather.alerts.has_alerts():
        parts.append("\nActive Alerts:")
        for alert in weather.alerts.alerts[:5]:
            title = getattr(alert, "event", None) or getattr(alert, "title", "Alert")
            severity = getattr(alert, "severity", "Unknown")
            parts.append(f"  - {title} (Severity: {severity})")

    if weather.trend_insights:
        parts.append("\nTrend Insights:")
        for insight in weather.trend_insights[:3]:
            text = insight.summary or f"{insight.metric}: {insight.direction}"
            if insight.change is not None and insight.unit:
                text += f" ({insight.change:+.1f}{insight.unit})"
            parts.append(f"  - {text}")

    return "\n".join(parts)
