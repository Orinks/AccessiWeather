"""Text formatters for AI weather tool responses."""

from __future__ import annotations

import json
from typing import Any


def format_current_weather(data: dict[str, Any], display_name: str = "") -> str:
    """
    Format current weather conditions data as readable text.

    Extracts key fields: temperature, feels like, conditions, humidity,
    wind, and pressure. Handles missing or None fields gracefully.

    Args:
        data: Weather data dict from WeatherService.get_current_conditions().
        display_name: Location display name for the header.

    Returns:
        A human-readable text summary of current conditions.

    """
    header = f"Current weather for {display_name}:" if display_name else "Current weather:"
    lines = [header]

    _append_field(lines, "Temperature", data.get("temperature"))
    _append_field(lines, "Feels Like", data.get("feels_like") or data.get("feelsLike"))
    _append_field(
        lines,
        "Conditions",
        data.get("description") or data.get("textDescription") or data.get("conditions"),
    )
    _append_field(lines, "Humidity", data.get("humidity"))
    _append_field(lines, "Wind", data.get("wind") or data.get("windSpeed"))
    _append_field(lines, "Pressure", data.get("pressure") or data.get("barometricPressure"))

    # Fallback: if no known fields matched, dump scalar values
    if len(lines) == 1:
        for key, value in data.items():
            if isinstance(value, str | int | float) and key not in ("lat", "lon"):
                lines.append(f"{key}: {value}")

    return "\n".join(lines)


def format_forecast(data: dict[str, Any], display_name: str = "") -> str:
    """
    Format forecast data as readable text with up to 7 periods.

    Each period includes name, temperature, and short forecast text.
    Handles missing or None fields gracefully.

    Args:
        data: Forecast data dict from WeatherService.get_forecast().
        display_name: Location display name for the header.

    Returns:
        A human-readable text summary of the forecast.

    """
    header = f"Forecast for {display_name}:" if display_name else "Forecast:"
    lines = [header]

    periods = data.get("periods", data.get("properties", {}).get("periods", []))
    if isinstance(periods, list):
        for period in periods[:7]:
            if not isinstance(period, dict):
                continue
            name = period.get("name") or "Unknown"
            temp = period.get("temperature")
            temp_unit = period.get("temperatureUnit", "")
            short = period.get("shortForecast") or period.get("detailedForecast") or ""

            parts = [name]
            if temp is not None:
                parts.append(f"{temp}°{temp_unit}" if temp_unit else str(temp))
            if short:
                parts.append(short)

            lines.append(" - ".join(parts))

    if len(lines) == 1:
        lines.append(json.dumps(data, indent=2, default=str)[:500])

    return "\n".join(lines)


def format_alerts(data: dict[str, Any], display_name: str = "") -> str:
    """
    Format weather alerts data as readable text.

    Shows event name, severity, headline, and description for each alert.
    Returns 'No active alerts' when the alert list is empty.
    Handles missing or None fields gracefully.

    Args:
        data: Alerts data dict from WeatherService.get_alerts().
        display_name: Location display name for the header.

    Returns:
        A human-readable text summary of weather alerts.

    """
    header = f"Weather alerts for {display_name}:" if display_name else "Weather alerts:"
    lines = [header]

    alerts = data.get("alerts", data.get("features", []))
    if isinstance(alerts, list) and len(alerts) > 0:
        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            props = alert.get("properties", alert)
            event = props.get("event") or "Unknown Alert"
            severity = props.get("severity")
            headline = props.get("headline")
            description = props.get("description")

            alert_line = f"- {event}"
            if severity:
                alert_line += f" (Severity: {severity})"
            lines.append(alert_line)
            if headline:
                lines.append(f"  {headline}")
            if description:
                lines.append(f"  {description[:300]}")
    else:
        lines.append("No active alerts.")

    return "\n".join(lines)


def format_hourly_forecast(data: dict[str, Any], display_name: str = "") -> str:
    """
    Format hourly forecast data as readable text with up to 12 periods.

    Args:
        data: Hourly forecast data dict from WeatherService.get_hourly_forecast().
        display_name: Location display name for the header.

    Returns:
        A human-readable text summary of the hourly forecast.

    """
    header = f"Hourly forecast for {display_name}:" if display_name else "Hourly forecast:"
    lines = [header]

    periods = data.get("periods", data.get("properties", {}).get("periods", []))
    if isinstance(periods, list):
        for period in periods[:12]:
            if not isinstance(period, dict):
                continue
            name = period.get("name") or period.get("startTime", "")
            temp = period.get("temperature")
            temp_unit = period.get("temperatureUnit", "")
            short = period.get("shortForecast") or ""
            wind = period.get("windSpeed") or ""

            parts = [str(name)]
            if temp is not None:
                parts.append(f"{temp}°{temp_unit}" if temp_unit else str(temp))
            if short:
                parts.append(short)
            if wind:
                parts.append(f"Wind: {wind}")

            lines.append(" - ".join(parts))

    if len(lines) == 1:
        lines.append("No hourly forecast data available.")

    return "\n".join(lines)


def format_open_meteo_response(data: dict[str, Any], display_name: str = "") -> str:
    """
    Format an Open-Meteo API response as readable text.

    Handles current, hourly, and daily data sections. Limits output
    to avoid overwhelming the AI context window.

    Args:
        data: Raw Open-Meteo API response dict.
        display_name: Location display name for the header.

    Returns:
        A human-readable text summary of the queried data.

    """
    header = f"Open-Meteo data for {display_name}:" if display_name else "Open-Meteo data:"
    lines = [header]

    # Current data
    current = data.get("current")
    if isinstance(current, dict):
        units = data.get("current_units", {})
        lines.append("\nCurrent:")
        for key, value in current.items():
            if key in ("time", "interval"):
                continue
            unit = units.get(key, "")
            lines.append(f"  {key}: {value}{unit}")

    # Hourly data (limit to 24 periods)
    hourly = data.get("hourly")
    if isinstance(hourly, dict):
        units = data.get("hourly_units", {})
        times = hourly.get("time", [])[:24]
        lines.append(f"\nHourly ({len(times)} periods):")
        for i, t in enumerate(times):
            parts = [t]
            for key, values in hourly.items():
                if key == "time" or not isinstance(values, list):
                    continue
                if i < len(values):
                    unit = units.get(key, "")
                    parts.append(f"{key}: {values[i]}{unit}")
            lines.append("  " + " | ".join(parts))

    # Daily data
    daily = data.get("daily")
    if isinstance(daily, dict):
        units = data.get("daily_units", {})
        times = daily.get("time", [])
        lines.append(f"\nDaily ({len(times)} days):")
        for i, t in enumerate(times):
            parts = [t]
            for key, values in daily.items():
                if key == "time" or not isinstance(values, list):
                    continue
                if i < len(values):
                    unit = units.get(key, "")
                    parts.append(f"{key}: {values[i]}{unit}")
            lines.append("  " + " | ".join(parts))

    if len(lines) == 1:
        lines.append("No data returned.")

    return "\n".join(lines)


def format_location_search(suggestions: list[str], query: str = "") -> str:
    """
    Format location search results as readable text.

    Args:
        suggestions: List of location suggestion strings.
        query: Original search query for context.

    Returns:
        A human-readable list of matching locations.

    """
    if not suggestions:
        return f"No locations found matching '{query}'."

    lines = [f"Locations matching '{query}':"]
    for i, suggestion in enumerate(suggestions, 1):
        lines.append(f"{i}. {suggestion}")

    return "\n".join(lines)


def _append_field(lines: list[str], label: str, value: Any) -> None:
    """Append a labeled field to lines if the value is not None/empty."""
    if value is not None and value != "":
        lines.append(f"{label}: {value}")
