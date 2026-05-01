"""AI weather tool execution registry."""

from __future__ import annotations

import logging
from typing import Any

from accessiweather.ai_tool_formatters import (
    format_alerts,
    format_current_weather,
    format_forecast,
    format_hourly_forecast,
    format_location_search,
    format_open_meteo_response,
)
from accessiweather.ai_tool_schemas import (
    CORE_TOOLS,
    DISCUSSION_TOOLS,
    EXTENDED_TOOLS,
    WEATHER_TOOLS,
    get_tools_for_message,
)
from accessiweather.geocoding import GeocodingService
from accessiweather.services.weather_service.weather_service import WeatherService

logger = logging.getLogger(__name__)

__all__ = [
    "CORE_TOOLS",
    "DISCUSSION_TOOLS",
    "EXTENDED_TOOLS",
    "WEATHER_TOOLS",
    "LocationResolver",
    "WeatherToolExecutor",
    "format_alerts",
    "format_current_weather",
    "format_forecast",
    "format_hourly_forecast",
    "format_location_search",
    "format_open_meteo_response",
    "get_tools_for_message",
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
        config_manager: Any = None,
        default_lat: float | None = None,
        default_lon: float | None = None,
        default_name: str | None = None,
    ) -> None:
        """
        Initialize the weather tool executor.

        Args:
            weather_service: The weather service for fetching weather data.
            geocoding_service: The geocoding service for resolving locations.
            config_manager: The config manager for saving locations (optional).
            default_lat: Latitude of the app's current/default location.
            default_lon: Longitude of the app's current/default location.
            default_name: Display name of the app's current/default location.

        """
        self.weather_service = weather_service
        self.geocoding_service = geocoding_service
        self.config_manager = config_manager
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
            "get_hourly_forecast": self._get_hourly_forecast,
            "search_location": self._search_location,
            "add_location": self._add_location,
            "list_locations": self._list_locations,
            "query_open_meteo": self._query_open_meteo,
            "get_area_forecast_discussion": self._get_afd,
            "get_wpc_discussion": self._get_wpc_discussion,
            "get_spc_outlook": self._get_spc_outlook,
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

    def _get_hourly_forecast(self, arguments: dict[str, Any]) -> str:
        """Get hourly weather forecast."""
        location = arguments["location"]
        lat, lon, display_name = self._resolve_location(location)
        data = self.weather_service.get_hourly_forecast(lat, lon)
        return format_hourly_forecast(data, display_name)

    def _search_location(self, arguments: dict[str, Any]) -> str:
        """Search for a location by name or ZIP code."""
        query = arguments["query"]
        suggestions = self.geocoding_service.suggest_locations(query, limit=5)
        return format_location_search(suggestions, query)

    def _add_location(self, arguments: dict[str, Any]) -> str:
        """Add a location to saved locations."""
        if self.config_manager is None:
            return "Error: Cannot save locations (config manager unavailable)."
        name = arguments["name"]
        lat = arguments["latitude"]
        lon = arguments["longitude"]
        # Check if already saved
        existing = self.config_manager.get_location_names()
        if name in existing:
            return f"'{name}' is already in your saved locations."
        success = self.config_manager.add_location(name, lat, lon)
        if success:
            self.config_manager.save_config()
            return f"Added '{name}' to your saved locations."
        return f"Failed to add '{name}'. It may already exist under a similar name."

    def _query_open_meteo(self, arguments: dict[str, Any]) -> str:
        """Query Open-Meteo API with custom parameters."""
        location = arguments["location"]
        lat, lon, display_name = self._resolve_location(location)

        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "timezone": arguments.get("timezone", "auto"),
        }

        if "current" in arguments:
            params["current"] = ",".join(arguments["current"])
        if "hourly" in arguments:
            params["hourly"] = ",".join(arguments["hourly"])
        if "daily" in arguments:
            params["daily"] = ",".join(arguments["daily"])
        if "forecast_days" in arguments:
            params["forecast_days"] = arguments["forecast_days"]

        # Need at least one data group
        if not any(k in params for k in ("current", "hourly", "daily")):
            return "Error: specify at least one of current, hourly, or daily variables."

        try:
            from accessiweather.openmeteo_client import OpenMeteoApiClient

            client = OpenMeteoApiClient()
            try:
                data = client._make_request("forecast", params)
            finally:
                client.close()

            return format_open_meteo_response(data, display_name)
        except Exception as e:
            logger.warning("Open-Meteo query failed: %s", e)
            return f"Error querying Open-Meteo: {e}"

    def _get_afd(self, arguments: dict[str, Any]) -> str:
        """Get Area Forecast Discussion for a location."""
        location = arguments["location"]
        lat, lon, display_name = self._resolve_location(location)
        try:
            text = self.weather_service.get_discussion(lat, lon)
            if text:
                # Truncate if very long to fit in context
                if len(text) > 3000:
                    text = text[:3000] + "\n\n[Truncated — full discussion is longer]"
                return f"Area Forecast Discussion for {display_name}:\n\n{text}"
            return f"No Area Forecast Discussion available for {display_name}."
        except Exception as e:
            logger.warning("AFD fetch failed: %s", e)
            return f"Error fetching AFD: {e}"

    def _get_wpc_discussion(self, arguments: dict[str, Any]) -> str:
        """Get WPC Short Range Forecast Discussion."""
        try:
            from accessiweather.services.national_discussion_scraper import (
                NationalDiscussionScraper,
            )

            scraper = NationalDiscussionScraper(request_delay=1.0, max_retries=2, timeout=15)
            result = scraper.fetch_wpc_discussion()
            text = result.get("full", "")
            if text:
                if len(text) > 3000:
                    text = text[:3000] + "\n\n[Truncated — full discussion is longer]"
                return f"WPC Short Range Forecast Discussion:\n\n{text}"
            return "WPC discussion unavailable."
        except Exception as e:
            logger.warning("WPC discussion fetch failed: %s", e)
            return f"Error fetching WPC discussion: {e}"

    def _get_spc_outlook(self, arguments: dict[str, Any]) -> str:
        """Get SPC Day 1 Convective Outlook."""
        try:
            from accessiweather.services.national_discussion_scraper import (
                NationalDiscussionScraper,
            )

            scraper = NationalDiscussionScraper(request_delay=1.0, max_retries=2, timeout=15)
            result = scraper.fetch_spc_discussion()
            text = result.get("full", "")
            if text:
                if len(text) > 3000:
                    text = text[:3000] + "\n\n[Truncated — full discussion is longer]"
                return f"SPC Day 1 Convective Outlook:\n\n{text}"
            return "SPC outlook unavailable."
        except Exception as e:
            logger.warning("SPC outlook fetch failed: %s", e)
            return f"Error fetching SPC outlook: {e}"

    def _list_locations(self, arguments: dict[str, Any]) -> str:
        """List all saved locations."""
        if self.config_manager is None:
            return "Error: Cannot access locations (config manager unavailable)."
        locations = self.config_manager.get_all_locations()
        if not locations:
            return "No saved locations."
        current = self.config_manager.get_current_location()
        current_name = current.name if current else None
        lines = ["Your saved locations:"]
        for loc in locations:
            marker = " (current)" if loc.name == current_name else ""
            lines.append(f"- {loc.name} ({loc.latitude:.2f}, {loc.longitude:.2f}){marker}")
        return "\n".join(lines)


# Keep backward-compatible private aliases
_format_current_conditions = format_current_weather
_format_forecast = format_forecast
_format_alerts = format_alerts
