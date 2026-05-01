"""AI tool schemas and message-based tool selection."""

from __future__ import annotations

from typing import Any


def get_tools_for_message(message: str) -> list[dict[str, Any]]:
    """
    Select which tools to send based on the user's message.

    Always includes core tools (current weather, forecast, alerts).
    Adds extended tools only when keywords suggest they're needed,
    saving tokens on simple weather questions.

    Args:
        message: The user's message text.

    Returns:
        List of tool schemas to send to the API.

    """
    tools = list(CORE_TOOLS)
    msg_lower = message.lower()

    # Keywords that trigger extended tools
    extended_triggers = (
        "hour",
        "tonight",
        "this afternoon",
        "this morning",
        "at ",
        " pm",
        " am",
        "soil",
        "uv",
        "cloud",
        "dew",
        "snow depth",
        "visibility",
        "pressure",
        "sunrise",
        "sunset",
        "cape",
        "custom",
        "add",
        "save",
        "location",
        "list",
        "my locations",
        "search",
        "find",
        "where is",
        "zip",
    )
    if any(trigger in msg_lower for trigger in extended_triggers):
        tools.extend(EXTENDED_TOOLS)

    # Keywords that trigger discussion tools
    discussion_triggers = (
        "discussion",
        "afd",
        "forecast discussion",
        "wpc",
        "spc",
        "storm prediction",
        "weather prediction center",
        "convective",
        "outlook",
        "severe",
        "tornado",
        "supercell",
        "explain the forecast",
        "why is",
        "reasoning",
        "meteorolog",
        "synoptic",
        "national",
    )
    if any(trigger in msg_lower for trigger in discussion_triggers):
        tools.extend(DISCUSSION_TOOLS)

    return tools


CORE_TOOLS: list[dict[str, Any]] = [
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

DISCUSSION_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_area_forecast_discussion",
            "description": (
                "Get the Area Forecast Discussion (AFD) for a location. "
                "This is a detailed technical forecast discussion written by local NWS forecasters. "
                "Great for understanding the reasoning behind the forecast."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location to get the AFD for, e.g. 'New York, NY'.",
                    }
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_wpc_discussion",
            "description": (
                "Get the Weather Prediction Center (WPC) Short Range Forecast Discussion. "
                "A nationwide weather discussion covering the next 1-3 days. Covers major "
                "weather systems, precipitation patterns, and significant weather events "
                "across the US."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spc_outlook",
            "description": (
                "Get the Storm Prediction Center (SPC) Day 1 Convective Outlook discussion. "
                "Covers severe weather risks including tornadoes, large hail, and damaging winds. "
                "Explains the meteorological reasoning behind severe weather risk areas."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]

EXTENDED_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_hourly_forecast",
            "description": "Get an hourly weather forecast for a location. Useful for questions like 'will it rain at 3pm?' or 'what's the temperature tonight?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location to get the hourly forecast for, e.g. 'New York, NY' or '10001'.",
                    }
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_location",
            "description": "Search for a location by name or ZIP code to find its full name and coordinates. Useful when the user mentions an ambiguous place name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Location name or ZIP code to search for, e.g. 'Paris' or '90210'.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_open_meteo",
            "description": (
                "Query the Open-Meteo API with custom parameters. Use this for weather "
                "questions not covered by other tools, such as soil temperature, cloud cover, "
                "dew point, snow depth, precipitation probability, UV index, visibility, "
                "surface pressure, cape, and more. Open-Meteo has global coverage and is free.\n\n"
                "Common hourly variables: temperature_2m, relative_humidity_2m, dew_point_2m, "
                "apparent_temperature, precipitation_probability, precipitation, rain, showers, "
                "snowfall, snow_depth, weather_code, pressure_msl, surface_pressure, "
                "cloud_cover, cloud_cover_low, cloud_cover_mid, cloud_cover_high, visibility, "
                "wind_speed_10m, wind_direction_10m, wind_gusts_10m, uv_index, "
                "soil_temperature_0cm, soil_temperature_6cm, soil_moisture_0_to_1cm\n\n"
                "Common daily variables: temperature_2m_max, temperature_2m_min, "
                "apparent_temperature_max, apparent_temperature_min, sunrise, sunset, "
                "uv_index_max, precipitation_sum, rain_sum, showers_sum, snowfall_sum, "
                "precipitation_hours, precipitation_probability_max, wind_speed_10m_max, "
                "wind_gusts_10m_max, wind_direction_10m_dominant\n\n"
                "Common current variables: temperature_2m, relative_humidity_2m, "
                "apparent_temperature, is_day, precipitation, rain, showers, snowfall, "
                "weather_code, cloud_cover, pressure_msl, surface_pressure, "
                "wind_speed_10m, wind_direction_10m, wind_gusts_10m"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location name or coordinates, e.g. 'Paris, France'.",
                    },
                    "hourly": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of hourly variables to fetch.",
                    },
                    "daily": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of daily variables to fetch.",
                    },
                    "current": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of current variables to fetch.",
                    },
                    "forecast_days": {
                        "type": "integer",
                        "description": "Number of forecast days (1-16, default 7).",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Timezone for results, e.g. 'America/New_York'. Default: auto.",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_location",
            "description": "Add a location to the user's saved locations list. Use after confirming with the user which location they want to add.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Display name for the location, e.g. 'New York, NY' or 'Paris, France'.",
                    },
                    "latitude": {
                        "type": "number",
                        "description": "Latitude of the location.",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude of the location.",
                    },
                },
                "required": ["name", "latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_locations",
            "description": "List all saved locations and show which one is currently selected.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]

# Complete list for backward compatibility
WEATHER_TOOLS = CORE_TOOLS + EXTENDED_TOOLS + DISCUSSION_TOOLS
