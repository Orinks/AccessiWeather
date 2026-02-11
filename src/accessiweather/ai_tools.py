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


class WeatherToolExecutor:
    """Executes weather tool calls using WeatherService and geocoding."""

    def __init__(
        self,
        weather_service: WeatherService,
        geocoding_service: GeocodingService,
    ) -> None:
        """
        Initialize the weather tool executor.

        Args:
            weather_service: The weather service for fetching weather data.
            geocoding_service: The geocoding service for resolving locations.

        """
        self.weather_service = weather_service
        self.geocoding_service = geocoding_service
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
            A formatted string with the tool's results.

        Raises:
            ValueError: If the tool name is not recognized.

        """
        handler = self._tool_handlers.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        return handler(arguments)

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
        result = self.geocoding_service.geocode_address(location)
        if result is None:
            raise ValueError(f"Could not resolve location: {location}")
        return result

    def _get_current_weather(self, arguments: dict[str, Any]) -> str:
        """Get current weather conditions."""
        location = arguments["location"]
        lat, lon, display_name = self._resolve_location(location)
        data = self.weather_service.get_current_conditions(lat, lon)
        return _format_current_conditions(data, display_name)

    def _get_forecast(self, arguments: dict[str, Any]) -> str:
        """Get weather forecast."""
        location = arguments["location"]
        lat, lon, display_name = self._resolve_location(location)
        data = self.weather_service.get_forecast(lat, lon)
        return _format_forecast(data, display_name)

    def _get_alerts(self, arguments: dict[str, Any]) -> str:
        """Get weather alerts."""
        location = arguments["location"]
        lat, lon, display_name = self._resolve_location(location)
        data = self.weather_service.get_alerts(lat, lon)
        return _format_alerts(data, display_name)


def _format_current_conditions(data: dict[str, Any], display_name: str) -> str:
    """Format current conditions data as a human-readable string."""
    lines = [f"Current weather for {display_name}:"]

    if "temperature" in data:
        lines.append(f"Temperature: {data['temperature']}")
    if "humidity" in data:
        lines.append(f"Humidity: {data['humidity']}")
    if "wind" in data:
        lines.append(f"Wind: {data['wind']}")
    if "description" in data:
        lines.append(f"Conditions: {data['description']}")
    if "textDescription" in data:
        lines.append(f"Conditions: {data['textDescription']}")

    # If we didn't extract specific fields, dump a summary
    if len(lines) == 1:
        # Try to provide something useful from the raw data
        for key, value in data.items():
            if isinstance(value, (str, int, float)) and key not in ("lat", "lon"):
                lines.append(f"{key}: {value}")

    return "\n".join(lines)


def _format_forecast(data: dict[str, Any], display_name: str) -> str:
    """Format forecast data as a human-readable string."""
    lines = [f"Forecast for {display_name}:"]

    periods = data.get("periods", data.get("properties", {}).get("periods", []))
    if isinstance(periods, list):
        for period in periods[:6]:  # Show up to 6 periods
            if isinstance(period, dict):
                name = period.get("name", "Unknown")
                detail = period.get("detailedForecast", period.get("shortForecast", ""))
                temp = period.get("temperature", "")
                temp_unit = period.get("temperatureUnit", "")
                if detail:
                    lines.append(f"{name}: {detail}")
                elif temp:
                    lines.append(f"{name}: {temp}°{temp_unit}")

    if len(lines) == 1:
        lines.append(json.dumps(data, indent=2, default=str)[:500])

    return "\n".join(lines)


def _format_alerts(data: dict[str, Any], display_name: str) -> str:
    """Format alerts data as a human-readable string."""
    lines = [f"Weather alerts for {display_name}:"]

    alerts = data.get("alerts", data.get("features", []))
    if isinstance(alerts, list) and len(alerts) > 0:
        for alert in alerts:
            if isinstance(alert, dict):
                props = alert.get("properties", alert)
                event = props.get("event", "Unknown Alert")
                headline = props.get("headline", "")
                description = props.get("description", "")
                if headline:
                    lines.append(f"- {event}: {headline}")
                elif description:
                    lines.append(f"- {event}: {description[:200]}")
                else:
                    lines.append(f"- {event}")
    else:
        lines.append("No active alerts.")

    return "\n".join(lines)
