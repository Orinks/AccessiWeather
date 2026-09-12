"""Text formatters for AI weather tool responses."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .ai_weather_time import (
    current_or_future,
    mapping,
    measurement,
    provenance,
    series_lines,
    timestamp,
)


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

    if isinstance(data.get("current"), dict):
        current = data["current"]
        units = mapping(data.get("current_units"))
        lines.extend(provenance(data, "Open-Meteo"))
        lines.append(f"Observation time: {current.get('time') or 'not supplied'}")
        count = len(lines)
        for key, value in current.items():
            if key not in ("time", "interval"):
                _append_field(lines, key, measurement(value, units.get(key, "")))
    else:
        current = mapping(data.get("properties")) if "properties" in data else data
        lines.extend(provenance(data, "NWS" if "properties" in data else "weather service"))
        lines.append(
            f"Observation time: {current.get('timestamp') or current.get('time') or 'not supplied'}"
        )
        count = len(lines)
        for label, keys in (
            ("Temperature", ("temperature",)),
            ("Feels Like", ("feels_like", "feelsLike", "heatIndex", "windChill")),
            ("Conditions", ("description", "textDescription", "conditions")),
            ("Humidity", ("humidity", "relativeHumidity")),
            ("Wind", ("wind", "windSpeed")),
            ("Wind direction", ("windDirection",)),
            ("Pressure", ("pressure", "barometricPressure")),
            ("Visibility", ("visibility",)),
        ):
            for key in keys:
                text = measurement(current.get(key))
                if text is not None:
                    _append_field(lines, label, text)
                    break
    if len(lines) == count:
        lines.append("No current weather data available.")

    return "\n".join(lines)


def format_forecast(data: dict[str, Any], display_name: str = "", *, forecast_days: int = 7) -> str:
    """
    Format forecast data as readable text with up to 7 periods.

    Each period includes name, temperature, and short forecast text.
    Handles missing or None fields gracefully.

    Args:
        data: Forecast data dict from WeatherService.get_forecast().
        display_name: Location display name for the header.
        forecast_days: Maximum daily rows to show.

    Returns:
        A human-readable text summary of the forecast.

    """
    header = f"Forecast for {display_name}:" if display_name else "Forecast:"
    lines = [header]

    if "daily" in data:
        lines.extend(provenance(data, "Open-Meteo"))
        rows = series_lines(data, "daily", max(1, min(forecast_days, 16)))
        lines.extend(rows or ["No forecast data available."])
        return "\n".join(lines)
    lines.extend(provenance(data, "NWS" if "properties" in data else "weather service"))
    count = len(lines)
    periods = data.get("periods", mapping(data.get("properties")).get("periods", []))
    if isinstance(periods, list):
        days = max(1, min(forecast_days, 16))
        first_time = next(
            (
                timestamp(p.get("startTime"), data)
                for p in periods
                if isinstance(p, dict) and timestamp(p.get("startTime"), data)
            ),
            None,
        )
        boundary = first_time + timedelta(days=days) if first_time else None
        for period in periods[: 2 * days]:
            if not isinstance(period, dict):
                continue
            start = timestamp(period.get("startTime"), data)
            if boundary and start and start.tzinfo == boundary.tzinfo and start >= boundary:
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

            if period.get("startTime"):
                parts.append(f"Valid from {period['startTime']}")
            lines.append(" - ".join(parts))

    if len(lines) == count:
        lines.append("No forecast data available.")

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
    lines.append("Source: NWS" if "features" in data else "Source: weather service")
    if isinstance(alerts, list) and len(alerts) > 0:
        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            props = mapping(alert.get("properties", alert))
            event = props.get("event") or "Unknown Alert"
            severity = props.get("severity")
            headline = props.get("headline")
            description = props.get("description")

            alert_line = f"- {event}"
            if severity:
                alert_line += f" (Severity: {severity})"
            lines.append(alert_line)
            for label, key in (
                ("Sender", "senderName"),
                ("Effective", "effective"),
                ("Onset", "onset"),
                ("Expires", "expires"),
                ("Ends", "ends"),
            ):
                value = props.get(key)
                if key == "senderName" and not value:
                    value = props.get("sender")
                lines.append(
                    f"  {label}: {value if isinstance(value, str) and value else 'unknown'}"
                )
            if headline:
                lines.append(f"  {headline}")
            if description:
                lines.append(f"  {description[:300]}")
    else:
        lines.append("No active alerts.")

    return "\n".join(lines)


def format_hourly_forecast(
    data: dict[str, Any], display_name: str = "", *, now: datetime | None = None
) -> str:
    """
    Format hourly forecast data as readable text with up to 12 periods.

    Args:
        data: Hourly forecast data dict from WeatherService.get_hourly_forecast().
        now: Reference time, defaulting to the current UTC time.
        display_name: Location display name for the header.

    Returns:
        A human-readable text summary of the hourly forecast.

    """
    header = f"Hourly forecast for {display_name}:" if display_name else "Hourly forecast:"
    lines = [header]

    if "hourly" in data:
        lines.extend(provenance(data, "Open-Meteo"))
        rows = series_lines(data, "hourly", 12, now)
        lines.extend(rows or ["No hourly forecast data available."])
        return "\n".join(lines)
    lines.extend(provenance(data, "NWS" if "properties" in data else "weather service"))
    count = len(lines)
    periods = data.get("periods", mapping(data.get("properties")).get("periods", []))
    if isinstance(periods, list):
        periods = [
            p
            for p in periods
            if isinstance(p, dict)
            and current_or_future(p.get("startTime"), data, now, p.get("endTime"))
        ]
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

            if period.get("startTime"):
                parts.append(f"Valid from {period['startTime']}")
            lines.append(" - ".join(parts))

    if len(lines) == count:
        lines.append("No hourly forecast data available.")

    return "\n".join(lines)


def format_open_meteo_response(
    data: dict[str, Any], display_name: str = "", *, now: datetime | None = None
) -> str:
    """Format raw current and forecast sections, retaining their valid times."""
    lines = [f"Open-Meteo data for {display_name}:" if display_name else "Open-Meteo data:"]
    lines.extend(provenance(data, "Open-Meteo"))
    if isinstance(data.get("current"), dict):
        current_lines = format_current_weather(data).splitlines()
        lines.extend(
            line for line in current_lines if not line.startswith(("Source:", "Timezone:"))
        )
    found = isinstance(data.get("current"), dict)
    for section, limit, label in (("hourly", 24, "periods"), ("daily", 16, "days")):
        rows = series_lines(data, section, limit, now)
        if rows:
            found = True
            lines.append(f"\n{section.title()} ({len(rows)} {label}):")
            lines.extend(rows)
    if not found:
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
