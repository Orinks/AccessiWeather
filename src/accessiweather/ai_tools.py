"""
AI tool schemas and execution registry for weather function calling.

This module defines OpenAI function-calling tool schemas and a registry
that maps tool names to executor functions using the app's WeatherService.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from accessiweather.geocoding import GeocodingService
from accessiweather.services.weather_service.weather_service import WeatherService

logger = logging.getLogger(__name__)

WEATHER_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get current weather conditions for a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location to get weather for, e.g. 'New York, NY' or '10001'.",
                    }
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_forecast",
            "description": "Get the weather forecast for a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location to get the forecast for, e.g. 'New York, NY' or '10001'.",
                    }
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_alerts",
            "description": "Get active weather alerts for a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location to get weather alerts for, e.g. 'New York, NY' or '10001'.",
                    }
                },
                "required": ["location"],
            },
        },
    },
]


class LocationResolver:
    """
    Resolves location strings to (lat, lon) coordinates.

    Uses the app's current location as a shortcut when the query matches
    the default location name (case-insensitive), otherwise falls back to
    the GeocodingService.
    """

    def __init__(
        self,
        geocoding_service: GeocodingService,
        default_lat: float | None = None,
        default_lon: float | None = None,
        default_name: str | None = None,
    ) -> None:
        """
        Initialize the location resolver.

        Args:
            geocoding_service: The geocoding service for resolving locations.
            default_lat: Latitude of the app's current/default location.
            default_lon: Longitude of the app's current/default location.
            default_name: Display name of the app's current/default location.

        """
        self.geocoding_service = geocoding_service
        self.default_lat = default_lat
        self.default_lon = default_lon
        self.default_name = default_name

    def _matches_default(self, location_str: str) -> bool:
        """Check if a location string matches the default location name."""
        if self.default_name is None or self.default_lat is None or self.default_lon is None:
            return False
        return location_str.strip().lower() == self.default_name.strip().lower()

    def resolve(self, location_str: str) -> tuple[float, float, str]:
        """
        Resolve a location string to (lat, lon, display_name).

        If the string matches the default location name (case-insensitive),
        the default coordinates are returned without an API call. Otherwise
        the GeocodingService is used.

        Args:
            location_str: The location to resolve (e.g. 'Paris' or 'New York, NY').

        Returns:
            A (latitude, longitude, display_name) tuple.

        Raises:
            ValueError: If the location cannot be resolved.

        """
        if self._matches_default(location_str):
            logger.debug(
                "Location '%s' matches default location '%s', using cached coordinates",
                location_str,
                self.default_name,
            )
            return (self.default_lat, self.default_lon, self.default_name)  # type: ignore[return-value]

        result = self.geocoding_service.geocode_address(location_str)
        if result is None:
            raise ValueError(f"Could not resolve location: {location_str}")
        return result


class WeatherToolExecutor:
    """Executes weather tool calls using WeatherService and geocoding."""

    def __init__(
        self,
        weather_service: WeatherService,
        geocoding_service: GeocodingService,
        default_lat: float | None = None,
        default_lon: float | None = None,
        default_name: str | None = None,
    ) -> None:
        """
        Initialize the weather tool executor.

        Args:
            weather_service: The weather service for fetching weather data.
            geocoding_service: The geocoding service for resolving locations.
            default_lat: Latitude of the app's current/default location.
            default_lon: Longitude of the app's current/default location.
            default_name: Display name of the app's current/default location.

        """
        self.weather_service = weather_service
        self.geocoding_service = geocoding_service
        self.location_resolver = LocationResolver(
            geocoding_service=geocoding_service,
            default_lat=default_lat,
            default_lon=default_lon,
            default_name=default_name,
        )
        self._tool_handlers = {
            "get_current_weather": self._get_current_weather,
            "get_forecast": self._get_forecast,
            "get_alerts": self._get_alerts,
        }

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        Execute a weather tool by name.

        Args:
            tool_name: The name of the tool to execute.
            arguments: The arguments for the tool call.

        Returns:
            A formatted string with the tool's results, or an error
            message string if location resolution or data fetching fails.

        Raises:
            ValueError: If the tool name is not recognized.

        """
        handler = self._tool_handlers.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        try:
            return handler(arguments)
        except ValueError as e:
            logger.warning("Tool execution failed for %s: %s", tool_name, e)
            return f"Error: {e}"
        except Exception as e:
            logger.error("Unexpected error executing tool %s: %s", tool_name, e)
            return f"Error fetching weather data: {e}"

    def _resolve_location(self, location: str) -> tuple[float, float, str]:
        """
        Resolve a location string to coordinates.

        Args:
            location: Location string to geocode.

        Returns:
            Tuple of (lat, lon, display_name).

        Raises:
            ValueError: If the location cannot be resolved.

        """
        return self.location_resolver.resolve(location)

    def _get_current_weather(self, arguments: dict[str, Any]) -> str:
        """Get current weather conditions."""
        location = arguments["location"]
        lat, lon, display_name = self._resolve_location(location)
        data = self.weather_service.get_current_conditions(lat, lon)
        return format_current_weather(data, display_name)

    def _get_forecast(self, arguments: dict[str, Any]) -> str:
        """Get weather forecast."""
        location = arguments["location"]
        lat, lon, display_name = self._resolve_location(location)
        data = self.weather_service.get_forecast(lat, lon)
        return format_forecast(data, display_name)

    def _get_alerts(self, arguments: dict[str, Any]) -> str:
        """Get weather alerts."""
        location = arguments["location"]
        lat, lon, display_name = self._resolve_location(location)
        data = self.weather_service.get_alerts(lat, lon)
        return format_alerts(data, display_name)


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
            if isinstance(value, (str, int, float)) and key not in ("lat", "lon"):
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


def _append_field(lines: list[str], label: str, value: Any) -> None:
    """Append a labeled field to lines if the value is not None/empty."""
    if value is not None and value != "":
        lines.append(f"{label}: {value}")


# Keep backward-compatible private aliases
_format_current_conditions = format_current_weather
_format_forecast = format_forecast
_format_alerts = format_alerts
