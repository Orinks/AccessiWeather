"""
Integration tests for taskbar placeholder functionality with real API data structures.

This test suite uses actual API response structures to verify that the placeholder
system works correctly with real data from both NWS and Open-Meteo APIs.
"""

import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.format_string_parser import FormatStringParser
from accessiweather.gui.ui_manager import UIManager
from accessiweather.openmeteo_mapper import OpenMeteoMapper


class TestTaskbarPlaceholderIntegration(unittest.TestCase):
    """Integration test cases for taskbar placeholder functionality with real API data."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock wx.App
        self.app = wx.App()

        # Create a mock frame
        self.frame = MagicMock()
        self.frame.config = {
            "settings": {
                "taskbar_icon_text_enabled": True,
                "taskbar_icon_text_format": "{location} {temp} {condition}",
                "temperature_unit": "fahrenheit",
            }
        }

        # Real NWS API response structure (simplified)
        self.real_nws_data = {
            "properties": {
                "@id": "https://api.weather.gov/stations/KORD/observations/latest",
                "timestamp": "2024-01-15T15:53:00+00:00",
                "temperature": {"value": 1.1, "unitCode": "wmoUnit:degC", "qualityControl": "qc:V"},
                "dewpoint": {"value": -2.2, "unitCode": "wmoUnit:degC", "qualityControl": "qc:V"},
                "windDirection": {
                    "value": 270,
                    "unitCode": "wmoUnit:degree_(angle)",
                    "qualityControl": "qc:V",
                },
                "windSpeed": {"value": 4.1, "unitCode": "wmoUnit:m_s-1", "qualityControl": "qc:V"},
                "windGust": {"value": None, "unitCode": "wmoUnit:m_s-1", "qualityControl": "qc:Z"},
                "barometricPressure": {
                    "value": 102790,
                    "unitCode": "wmoUnit:Pa",
                    "qualityControl": "qc:V",
                },
                "seaLevelPressure": {
                    "value": None,
                    "unitCode": "wmoUnit:Pa",
                    "qualityControl": "qc:Z",
                },
                "visibility": {"value": 16093, "unitCode": "wmoUnit:m", "qualityControl": "qc:V"},
                "maxTemperatureLast24Hours": {
                    "value": None,
                    "unitCode": "wmoUnit:degC",
                    "qualityControl": "qc:Z",
                },
                "minTemperatureLast24Hours": {
                    "value": None,
                    "unitCode": "wmoUnit:degC",
                    "qualityControl": "qc:Z",
                },
                "precipitationLastHour": {
                    "value": None,
                    "unitCode": "wmoUnit:mm",
                    "qualityControl": "qc:Z",
                },
                "precipitationLast3Hours": {
                    "value": None,
                    "unitCode": "wmoUnit:mm",
                    "qualityControl": "qc:Z",
                },
                "precipitationLast6Hours": {
                    "value": None,
                    "unitCode": "wmoUnit:mm",
                    "qualityControl": "qc:Z",
                },
                "relativeHumidity": {
                    "value": 87.4,
                    "unitCode": "wmoUnit:percent",
                    "qualityControl": "qc:V",
                },
                "windChill": {"value": None, "unitCode": "wmoUnit:degC", "qualityControl": "qc:Z"},
                "heatIndex": {"value": None, "unitCode": "wmoUnit:degC", "qualityControl": "qc:Z"},
                "cloudLayers": [{"base": {"value": 457, "unitCode": "wmoUnit:m"}, "amount": "OVC"}],
                "textDescription": "Overcast",
            }
        }

        # Real Open-Meteo API response structure (simplified)
        self.real_openmeteo_data = {
            "latitude": 41.85,
            "longitude": -87.65,
            "generationtime_ms": 0.123,
            "utc_offset_seconds": -21600,
            "timezone": "America/Chicago",
            "timezone_abbreviation": "CST",
            "elevation": 180.0,
            "current_units": {
                "time": "iso8601",
                "interval": "seconds",
                "temperature_2m": "°F",
                "relative_humidity_2m": "%",
                "apparent_temperature": "°F",
                "is_day": "",
                "precipitation": "inch",
                "weather_code": "wmo code",
                "cloud_cover": "%",
                "pressure_msl": "hPa",
                "surface_pressure": "hPa",
                "wind_speed_10m": "mph",
                "wind_direction_10m": "°",
                "wind_gusts_10m": "mph",
            },
            "current": {
                "time": "2024-01-15T15:00",
                "interval": 900,
                "temperature_2m": 34.2,
                "relative_humidity_2m": 87,
                "apparent_temperature": 28.1,
                "is_day": 1,
                "precipitation": 0.0,
                "weather_code": 3,
                "cloud_cover": 100,
                "pressure_msl": 1028.1,
                "surface_pressure": 1010.2,
                "wind_speed_10m": 9.2,
                "wind_direction_10m": 270,
                "wind_gusts_10m": 15.7,
            },
        }

        # Create a format string parser
        self.parser = FormatStringParser()

        # Create a UI manager for testing data extraction - patch the _setup_ui method
        mock_notifier = MagicMock()
        with patch.object(UIManager, "_setup_ui"):
            self.ui_manager = UIManager(self.frame, mock_notifier)

        # Create Open-Meteo mapper
        self.openmeteo_mapper = OpenMeteoMapper()

    def tearDown(self):
        """Clean up after tests."""
        # Destroy the wx.App
        self.app.Destroy()

    def test_real_nws_data_extraction(self):
        """Test placeholder functionality with real NWS API data structure."""
        # Extract taskbar data from real NWS format
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.real_nws_data)

        # Add location data (would normally come from the API call context)
        taskbar_data["location"] = "Chicago, IL"

        # Test default format
        default_format = "{location} {temp} {condition}"

        # Create formatted data (simulating what system_tray.py does)
        formatted_data = taskbar_data.copy()
        if "temp_f" in formatted_data and formatted_data["temp_f"] is not None:
            formatted_data["temp"] = f"{formatted_data['temp_f']:.0f}°F"

        result = self.parser.format_string(default_format, formatted_data)

        # Verify the result contains expected components
        self.assertIn("Chicago, IL", result)
        self.assertIn("°F", result)
        self.assertIn("Overcast", result)

        # Verify specific placeholders work
        temp_result = self.parser.format_string("{temp_f}", taskbar_data)
        self.assertNotEqual(temp_result, "{temp_f}")

        condition_result = self.parser.format_string("{condition}", taskbar_data)
        self.assertEqual(condition_result, "Overcast")

        humidity_result = self.parser.format_string("{humidity}", taskbar_data)
        self.assertNotEqual(humidity_result, "{humidity}")

    def test_real_openmeteo_data_extraction(self):
        """Test placeholder functionality with real Open-Meteo API data structure."""
        # Map Open-Meteo data to NWS-like format
        mapped_data = self.openmeteo_mapper.map_current_conditions(self.real_openmeteo_data)

        # Extract taskbar data from mapped format
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(mapped_data)

        # Add location data (would normally come from geocoding)
        taskbar_data["location"] = "Chicago, IL"

        # Test default format
        default_format = "{location} {temp} {condition}"

        # Create formatted data (simulating what system_tray.py does)
        formatted_data = taskbar_data.copy()
        if "temp_f" in formatted_data and formatted_data["temp_f"] is not None:
            formatted_data["temp"] = f"{formatted_data['temp_f']:.0f}°F"

        result = self.parser.format_string(default_format, formatted_data)

        # Verify the result contains expected components
        self.assertIn("Chicago, IL", result)
        self.assertIn("°F", result)
        # Weather code 3 should map to some condition
        self.assertNotEqual(formatted_data.get("condition", ""), "")

        # Verify specific placeholders work
        temp_result = self.parser.format_string("{temp_f}", taskbar_data)
        self.assertNotEqual(temp_result, "{temp_f}")

        wind_result = self.parser.format_string("{wind}", taskbar_data)
        self.assertIn("W", wind_result)  # 270 degrees = W
        self.assertIn("mph", wind_result)

    def test_api_comparison_consistency(self):
        """Test that both APIs produce consistent placeholder results."""
        # Extract data from both APIs
        nws_data = self.ui_manager._extract_nws_data_for_taskbar(self.real_nws_data)
        nws_data["location"] = "Test Location"

        mapped_openmeteo = self.openmeteo_mapper.map_current_conditions(self.real_openmeteo_data)
        openmeteo_data = self.ui_manager._extract_nws_data_for_taskbar(mapped_openmeteo)
        openmeteo_data["location"] = "Test Location"

        # Both should have the same structure
        self.assertEqual(set(nws_data.keys()), set(openmeteo_data.keys()))

        # Test that the same format string works with both
        test_format = "{location}: {temp_f}°F, {condition}, {humidity}% humidity"

        nws_result = self.parser.format_string(test_format, nws_data)
        openmeteo_result = self.parser.format_string(test_format, openmeteo_data)

        # Both should be valid strings without unresolved placeholders
        self.assertNotIn("{", nws_result)
        self.assertNotIn("}", nws_result)
        self.assertNotIn("{", openmeteo_result)
        self.assertNotIn("}", openmeteo_result)

        # Both should contain the expected components
        for result in [nws_result, openmeteo_result]:
            self.assertIn("Test Location", result)
            self.assertIn("°F", result)
            self.assertIn("% humidity", result)

    def test_edge_case_real_data_missing_fields(self):
        """Test handling of real API data with missing or null fields."""
        # Create a version of NWS data with some missing fields
        incomplete_nws_data = {
            "properties": {
                "temperature": {"value": 20.0, "unitCode": "wmoUnit:degC"},
                "textDescription": "Clear",
                # Missing wind, pressure, humidity data
            }
        }

        # Should handle gracefully
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(incomplete_nws_data)
        taskbar_data["location"] = "Test Location"

        # Test various format strings
        test_formats = [
            "{location} {temp} {condition}",
            "{temp_f}°F {wind_dir} {wind_speed}",
            "{condition} - {humidity}% - {pressure}",
        ]

        for format_string in test_formats:
            with self.subTest(format_string=format_string):
                result = self.parser.format_string(format_string, taskbar_data)

                # Should not crash and should be a valid string
                self.assertIsInstance(result, str)
                self.assertGreater(len(result), 0)


if __name__ == "__main__":
    unittest.main()
