"""
Unit tests for format_string_parser module.

Tests cover:
- Placeholder extraction from format strings
- Format string validation
- String formatting with data substitution
- Error handling for invalid format strings
- Edge cases and boundary conditions
"""

# Direct import to avoid __init__.py importing toga
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accessiweather.format_string_parser import FormatStringParser


class TestFormatStringParser:
    """Test FormatStringParser class."""

    @pytest.fixture
    def parser(self):
        """Create FormatStringParser instance."""
        return FormatStringParser()

    def test_initialization(self, parser):
        """Should initialize with compiled regex pattern."""
        assert parser.placeholder_pattern is not None
        assert hasattr(parser, "SUPPORTED_PLACEHOLDERS")

    def test_get_placeholders_single(self, parser):
        """Should extract single placeholder from format string."""
        format_str = "Temperature: {temp}"
        placeholders = parser.get_placeholders(format_str)

        assert placeholders == ["temp"]

    def test_get_placeholders_multiple(self, parser):
        """Should extract multiple placeholders from format string."""
        format_str = "{location}: {temp} {condition}, Humidity: {humidity}%"
        placeholders = parser.get_placeholders(format_str)

        assert len(placeholders) == 4
        assert "location" in placeholders
        assert "temp" in placeholders
        assert "condition" in placeholders
        assert "humidity" in placeholders

    def test_get_placeholders_empty_string(self, parser):
        """Should return empty list for empty format string."""
        placeholders = parser.get_placeholders("")
        assert placeholders == []

    def test_get_placeholders_none(self, parser):
        """Should return empty list for None input."""
        placeholders = parser.get_placeholders(None)
        assert placeholders == []

    def test_get_placeholders_no_placeholders(self, parser):
        """Should return empty list when no placeholders found."""
        format_str = "Just plain text with no placeholders"
        placeholders = parser.get_placeholders(format_str)

        assert placeholders == []

    def test_get_placeholders_duplicate(self, parser):
        """Should return duplicate placeholders if they appear multiple times."""
        format_str = "{temp} and {temp} again"
        placeholders = parser.get_placeholders(format_str)

        assert len(placeholders) == 2
        assert placeholders == ["temp", "temp"]

    def test_get_placeholders_with_underscores(self, parser):
        """Should extract placeholders with underscores."""
        format_str = "{temp_f} and {wind_speed}"
        placeholders = parser.get_placeholders(format_str)

        assert "temp_f" in placeholders
        assert "wind_speed" in placeholders

    def test_validate_format_string_valid(self, parser):
        """Should validate correct format string."""
        format_str = "{location}: {temp} {condition}"
        is_valid, error = parser.validate_format_string(format_str)

        assert is_valid is True
        assert error is None

    def test_validate_format_string_empty(self, parser):
        """Should validate empty string as valid."""
        is_valid, error = parser.validate_format_string("")

        assert is_valid is True
        assert error is None

    def test_validate_format_string_unbalanced_braces_open(self, parser):
        """Should reject format string with unclosed braces."""
        format_str = "{temp is broken"
        is_valid, error = parser.validate_format_string(format_str)

        assert is_valid is False
        assert error is not None
        assert "Unbalanced braces" in error

    def test_validate_format_string_unbalanced_braces_close(self, parser):
        """Should reject format string with extra closing braces."""
        format_str = "temp} is broken"
        is_valid, error = parser.validate_format_string(format_str)

        assert is_valid is False
        assert "Unbalanced braces" in error

    def test_validate_format_string_unsupported_placeholder(self, parser):
        """Should reject format string with unsupported placeholder."""
        format_str = "{temp} and {invalid_placeholder}"
        is_valid, error = parser.validate_format_string(format_str)

        assert is_valid is False
        assert error is not None
        assert "Unsupported placeholder" in error
        assert "invalid_placeholder" in error

    def test_validate_format_string_multiple_unsupported(self, parser):
        """Should reject format string with multiple unsupported placeholders."""
        format_str = "{invalid_one} and {invalid_two}"
        is_valid, error = parser.validate_format_string(format_str)

        assert is_valid is False
        assert "invalid_one" in error
        assert "invalid_two" in error

    def test_format_string_simple(self, parser):
        """Should format simple string with single placeholder."""
        format_str = "Temperature: {temp}"
        data = {"temp": "72°F"}

        result = parser.format_string(format_str, data)

        assert result == "Temperature: 72°F"

    def test_format_string_multiple_placeholders(self, parser):
        """Should format string with multiple placeholders."""
        format_str = "{location}: {temp}, {condition}"
        data = {
            "location": "New York",
            "temp": "72°F",
            "condition": "Partly Cloudy",
        }

        result = parser.format_string(format_str, data)

        assert result == "New York: 72°F, Partly Cloudy"

    def test_format_string_missing_data(self, parser):
        """Should keep placeholder when data is missing."""
        format_str = "Temperature: {temp}"
        data = {}

        result = parser.format_string(format_str, data)

        assert result == "Temperature: {temp}"

    def test_format_string_empty(self, parser):
        """Should return empty string for empty format string."""
        result = parser.format_string("", {"temp": "72°F"})

        assert result == ""

    def test_format_string_unbalanced_braces(self, parser):
        """Should return error message for unbalanced braces."""
        format_str = "{temp is broken"
        data = {"temp": "72°F"}

        result = parser.format_string(format_str, data)

        assert "Error" in result
        assert "Unbalanced braces" in result

    def test_format_string_no_placeholders(self, parser):
        """Should return original string when no placeholders."""
        format_str = "Just plain text"
        data = {"temp": "72°F"}

        result = parser.format_string(format_str, data)

        assert result == "Just plain text"

    def test_format_string_numeric_values(self, parser):
        """Should convert numeric values to strings."""
        format_str = "Temp: {temp}, Humidity: {humidity}%"
        data = {"temp": 72, "humidity": 65}

        result = parser.format_string(format_str, data)

        assert result == "Temp: 72, Humidity: 65%"

    def test_format_string_none_values(self, parser):
        """Should handle None values by converting to string."""
        format_str = "Value: {value}"
        data = {"value": None}

        result = parser.format_string(format_str, data)

        assert result == "Value: None"

    def test_format_string_duplicate_placeholders(self, parser):
        """Should replace all occurrences of duplicate placeholders."""
        format_str = "{temp} morning, {temp} evening"
        data = {"temp": "72°F"}

        result = parser.format_string(format_str, data)

        assert result == "72°F morning, 72°F evening"

    def test_format_string_special_characters(self, parser):
        """Should handle special characters in data values."""
        format_str = "Location: {location}"
        data = {"location": "São Paulo, Brazil!"}

        result = parser.format_string(format_str, data)

        assert result == "Location: São Paulo, Brazil!"

    def test_get_supported_placeholders_help(self):
        """Should return help text with all supported placeholders."""
        help_text = FormatStringParser.get_supported_placeholders_help()

        assert help_text is not None
        assert "Supported Placeholders" in help_text
        assert "{temp}" in help_text
        assert "{condition}" in help_text
        assert "{location}" in help_text

    def test_supported_placeholders_completeness(self):
        """Should have all expected placeholders defined."""
        expected_placeholders = [
            "temp",
            "temp_f",
            "temp_c",
            "condition",
            "humidity",
            "wind",
            "wind_speed",
            "wind_dir",
            "pressure",
            "location",
            "feels_like",
            "uv",
            "visibility",
            "high",
            "low",
            "precip",
            "precip_chance",
        ]

        for placeholder in expected_placeholders:
            assert placeholder in FormatStringParser.SUPPORTED_PLACEHOLDERS


class TestFormatStringParserEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def parser(self):
        """Create FormatStringParser instance."""
        return FormatStringParser()

    def test_format_string_very_long(self, parser):
        """Should handle very long format strings."""
        format_str = " ".join(["{temp}"] * 100)
        data = {"temp": "72°F"}

        result = parser.format_string(format_str, data)

        assert result.count("72°F") == 100

    def test_format_string_nested_braces(self, parser):
        """Should handle double braces as escape sequences."""
        format_str = "Range: {{min}} to {{max}}"
        data = {"min": "50", "max": "75"}

        # Double braces allow literal braces with substitution
        # {{min}} -> {50} (outer braces are literals, inner {min} gets replaced)
        result = parser.format_string(format_str, data)

        # Should successfully format with one level of braces remaining
        assert result == "Range: {50} to {75}"

    def test_validate_with_only_braces(self, parser):
        """Should validate string with only braces."""
        is_valid, error = parser.validate_format_string("{}")

        # Empty placeholder name won't match pattern, so no placeholders found
        assert is_valid is True

    def test_format_string_with_newlines(self, parser):
        """Should handle format strings with newlines."""
        format_str = "{location}\nTemp: {temp}\nCondition: {condition}"
        data = {
            "location": "New York",
            "temp": "72°F",
            "condition": "Sunny",
        }

        result = parser.format_string(format_str, data)

        assert "New York" in result
        assert "\n" in result
        assert "Sunny" in result

    def test_format_string_with_tabs(self, parser):
        """Should handle format strings with tabs."""
        format_str = "{location}\t{temp}\t{condition}"
        data = {
            "location": "New York",
            "temp": "72°F",
            "condition": "Sunny",
        }

        result = parser.format_string(format_str, data)

        assert "\t" in result

    def test_placeholder_extraction_case_sensitive(self, parser):
        """Should extract placeholders case-sensitively."""
        format_str = "{Temp} and {TEMP} and {temp}"
        placeholders = parser.get_placeholders(format_str)

        # Pattern only matches lowercase letters and underscores
        # So TEMP won't match
        assert "temp" in placeholders

    def test_format_with_boolean_values(self, parser):
        """Should handle boolean values in data."""
        format_str = "Status: {condition}"
        data = {"condition": True}

        result = parser.format_string(format_str, data)

        assert result == "Status: True"

    def test_format_with_list_values(self, parser):
        """Should handle list values by converting to string."""
        format_str = "Values: {condition}"
        data = {"condition": ["sunny", "warm"]}

        result = parser.format_string(format_str, data)

        assert "sunny" in result
        assert "warm" in result

    def test_placeholder_with_numbers(self, parser):
        """Should not extract placeholders with numbers."""
        format_str = "{temp123}"
        placeholders = parser.get_placeholders(format_str)

        # Pattern only matches [a-zA-Z_]+, so numbers won't match
        assert placeholders == []

    def test_format_string_adjacent_placeholders(self, parser):
        """Should handle adjacent placeholders without separator."""
        format_str = "{temp}{condition}"
        data = {"temp": "72", "condition": "Sunny"}

        result = parser.format_string(format_str, data)

        assert result == "72Sunny"

    def test_format_string_with_unicode(self, parser):
        """Should handle Unicode characters in format strings."""
        format_str = "🌡️ {temp} - {condition} ☀️"
        data = {"temp": "72°F", "condition": "Sunny"}

        result = parser.format_string(format_str, data)

        assert "🌡️" in result
        assert "☀️" in result
        assert "72°F" in result
