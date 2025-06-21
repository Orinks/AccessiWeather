"""Tests for the format string parser."""

import unittest

from accessiweather.format_string_parser import FormatStringParser


class TestFormatStringParser(unittest.TestCase):
    """Test cases for the FormatStringParser class."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = FormatStringParser()
        self.test_data = {
            "temp": 72.5,
            "temp_f": 72.5,
            "temp_c": 22.5,
            "condition": "Partly Cloudy",
            "humidity": 45,
            "wind_speed": 10,
            "wind_dir": "NW",
            "pressure": 29.92,
            "location": "New York",
            "feels_like": 70,
            "uv": 5,
            "visibility": 10,
            "high": 75,
            "low": 65,
            "precip": 0.1,
            "precip_chance": 20,
        }

    def test_get_placeholders(self):
        """Test extracting placeholders from a format string."""
        format_string = "Temperature: {temp}°F, Condition: {condition}"
        placeholders = self.parser.get_placeholders(format_string)
        self.assertEqual(placeholders, ["temp", "condition"])

    def test_get_placeholders_empty_string(self):
        """Test extracting placeholders from an empty string."""
        format_string = ""
        placeholders = self.parser.get_placeholders(format_string)
        self.assertEqual(placeholders, [])

    def test_get_placeholders_no_placeholders(self):
        """Test extracting placeholders from a string with no placeholders."""
        format_string = "Temperature: 72°F, Condition: Partly Cloudy"
        placeholders = self.parser.get_placeholders(format_string)
        self.assertEqual(placeholders, [])

    def test_validate_format_string_valid(self):
        """Test validating a valid format string."""
        format_string = "Temperature: {temp}°F, Condition: {condition}"
        is_valid, error = self.parser.validate_format_string(format_string)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_format_string_empty(self):
        """Test validating an empty format string."""
        format_string = ""
        is_valid, error = self.parser.validate_format_string(format_string)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_format_string_unbalanced_braces(self):
        """Test validating a format string with unbalanced braces."""
        format_string = "Temperature: {temp°F, Condition: {condition}"
        is_valid, error = self.parser.validate_format_string(format_string)
        self.assertFalse(is_valid)
        self.assertEqual(error, "Unbalanced braces in format string")

    def test_validate_format_string_unsupported_placeholder(self):
        """Test validating a format string with an unsupported placeholder."""
        format_string = "Temperature: {temp}°F, Condition: {unknown}"
        is_valid, error = self.parser.validate_format_string(format_string)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        assert error is not None  # Type hint for mypy
        self.assertTrue("Unsupported placeholder(s): unknown" in error)

    def test_format_string(self):
        """Test formatting a string with placeholders."""
        format_string = "Temperature: {temp}°F, Condition: {condition}"
        formatted = self.parser.format_string(format_string, self.test_data)
        self.assertEqual(formatted, "Temperature: 72.5°F, Condition: Partly Cloudy")

    def test_format_string_empty(self):
        """Test formatting an empty string."""
        format_string = ""
        formatted = self.parser.format_string(format_string, self.test_data)
        self.assertEqual(formatted, "")

    def test_format_string_no_placeholders(self):
        """Test formatting a string with no placeholders."""
        format_string = "Temperature: 72°F, Condition: Partly Cloudy"
        formatted = self.parser.format_string(format_string, self.test_data)
        self.assertEqual(formatted, "Temperature: 72°F, Condition: Partly Cloudy")

    def test_format_string_missing_data(self):
        """Test formatting a string with placeholders for which there is no data."""
        format_string = "Temperature: {temp}°F, Condition: {unknown}"
        formatted = self.parser.format_string(format_string, self.test_data)
        self.assertEqual(formatted, "Temperature: 72.5°F, Condition: {unknown}")

    def test_get_supported_placeholders_help(self):
        """Test getting help text for supported placeholders."""
        help_text = FormatStringParser.get_supported_placeholders_help()
        self.assertTrue("Supported Placeholders:" in help_text)
        self.assertTrue("{temp}:" in help_text)
        self.assertTrue("{condition}:" in help_text)


if __name__ == "__main__":
    unittest.main()
