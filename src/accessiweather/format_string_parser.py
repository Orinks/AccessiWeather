"""
Format string parser for customizable text display.

This module provides functionality to parse format strings with placeholders
and substitute them with actual values.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class FormatStringParser:
    """
    Parser for format strings with placeholders.

    This class provides functionality to parse format strings with placeholders
    enclosed in curly braces (e.g., {temp}) and substitute them with actual values.
    """

    # Define the supported placeholders and their descriptions
    SUPPORTED_PLACEHOLDERS = {
        "temp": "Current temperature (respects unit preference)",
        "temp_f": "Current temperature in Fahrenheit",
        "temp_c": "Current temperature in Celsius",
        "condition": "Current weather condition (e.g., 'Partly Cloudy')",
        "humidity": "Current humidity percentage",
        "wind": "Wind speed and direction (e.g., 'NW at 5 mph')",
        "wind_speed": "Wind speed (respects unit preference)",
        "wind_dir": "Wind direction (e.g., 'NW')",
        "pressure": "Barometric pressure (respects unit preference)",
        "location": "Current location name",
        "feels_like": "Feels like temperature (respects unit preference)",
        "uv": "UV index",
        "visibility": "Visibility (respects unit preference)",
        "high": "Today's high temperature (respects unit preference)",
        "low": "Today's low temperature (respects unit preference)",
        "precip": "Precipitation amount (respects unit preference)",
        "precip_chance": "Chance of precipitation percentage",
    }

    def __init__(self):
        """Initialize the FormatStringParser."""
        # Compile a regex pattern to find placeholders in format strings
        self.placeholder_pattern = re.compile(r"\{([a-zA-Z_]+)\}")

    def get_placeholders(self, format_string: str) -> list[str]:
        """
        Extract placeholders from a format string.

        Args:
        ----
            format_string: The format string to parse.

        Returns:
        -------
            List of placeholder names found in the format string.

        """
        if not format_string:
            return []

        # Find all matches of the placeholder pattern
        return self.placeholder_pattern.findall(format_string)

    def validate_format_string(self, format_string: str) -> tuple[bool, str | None]:
        """
        Validate a format string.

        Args:
        ----
            format_string: The format string to validate.

        Returns:
        -------
            Tuple of (is_valid, error_message). If the format string is valid,
            is_valid will be True and error_message will be None. Otherwise,
            is_valid will be False and error_message will contain a description
            of the error.

        """
        if not format_string:
            return True, None  # Empty string is valid (will use default)

        # Check for unbalanced braces
        if format_string.count("{") != format_string.count("}"):
            return False, "Unbalanced braces in format string"

        # Check for unsupported placeholders
        placeholders = self.get_placeholders(format_string)
        unsupported = [p for p in placeholders if p not in self.SUPPORTED_PLACEHOLDERS]

        if unsupported:
            return (
                False,
                f"Unsupported placeholder(s): {', '.join(unsupported)}. "
                f"Supported placeholders are: {', '.join(self.SUPPORTED_PLACEHOLDERS.keys())}",
            )

        return True, None

    def format_string(self, format_string: str, data: dict[str, Any]) -> str:
        """
        Format a string by substituting placeholders with values from data.

        Args:
        ----
            format_string: The format string with placeholders.
            data: Dictionary containing values to substitute for placeholders.

        Returns:
        -------
            The formatted string with placeholders replaced by values.

        """
        if not format_string:
            return ""

        # Check for unbalanced braces
        if format_string.count("{") != format_string.count("}"):
            logger.error("Unbalanced braces in format string")
            return "Error: Unbalanced braces in format string"

        # Get all placeholders in the format string
        placeholders = self.get_placeholders(format_string)

        # Create a result string by replacing each placeholder with its value
        result = format_string
        for placeholder in placeholders:
            # Get the value for this placeholder from the data dictionary
            value = data.get(placeholder, f"{{{placeholder}}}")

            # Replace the placeholder with its value
            result = result.replace(f"{{{placeholder}}}", str(value))

        return result

    @classmethod
    def get_supported_placeholders_help(cls) -> str:
        """
        Get a help string describing all supported placeholders.

        Returns
        -------
            A formatted string with all supported placeholders and their descriptions.

        """
        help_text = "Supported Placeholders:\n\n"
        for placeholder, description in cls.SUPPORTED_PLACEHOLDERS.items():
            help_text += f"{{{placeholder}}}: {description}\n"
        return help_text
