"""Toga-compatible comprehensive tests for taskbar placeholder and data formatting logic."""

import unittest
from accessiweather.format_string_parser import FormatStringParser

class TestTaskbarPlaceholderComprehensive(unittest.TestCase):
    def setUp(self):
        self.parser = FormatStringParser()
        self.nws_test_data = {
            "location": "New York, NY",
            "temp_f": 72.0,
            "condition": "Partly Cloudy"
        }
        self.openmeteo_mapped_data = {
            "location": "Los Angeles, CA",
            "temp_f": 75.0,
            "condition": "Clear Sky"
        }

    def test_default_format_nws_api(self):
        default_format = "{location} {temp_f}°F {condition}"
        result = self.parser.format_string(default_format, self.nws_test_data)
        self.assertIn("New York, NY", result)
        self.assertIn("72.0°F", result)
        self.assertIn("Partly Cloudy", result)

    def test_default_format_openmeteo_api(self):
        default_format = "{location} {temp_f}°F {condition}"
        result = self.parser.format_string(default_format, self.openmeteo_mapped_data)
        self.assertIn("Los Angeles, CA", result)
        self.assertIn("75.0°F", result)
        self.assertIn("Clear Sky", result)


if __name__ == "__main__":
    unittest.main()
