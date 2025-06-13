"""
Comprehensive tests for taskbar placeholder functionality and backward compatibility.

This test suite verifies all supported placeholders work correctly with both NWS and Open-Meteo APIs,
tests edge cases, and ensures backward compatibility with existing placeholder system.
"""

import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.format_string_parser import FormatStringParser
from accessiweather.gui.system_tray import TaskBarIcon
from accessiweather.gui.ui_manager import UIManager


class TestTaskbarPlaceholderComprehensive(unittest.TestCase):
    """Comprehensive test cases for taskbar placeholder functionality."""

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

        # Create test data for NWS API format
        self.nws_test_data = {
            "properties": {
                "temperature": {"value": 72.0, "unitCode": "degF"},
                "dewpoint": {"value": 65.0, "unitCode": "degF"},
                "windSpeed": {"value": 16.0934},  # km/h
                "windDirection": {"value": 225},  # degrees
                "barometricPressure": {"value": 101325, "unitCode": "Pa"},
                "relativeHumidity": {"value": 65, "unitCode": "percent"},
                "textDescription": "Partly Cloudy",
                "visibility": {"value": 16093.4, "unitCode": "m"},
            }
        }

        # Create test data for Open-Meteo API format (after mapping)
        self.openmeteo_mapped_data = {
            "properties": {
                "temperature": {"value": 75.0, "unitCode": "degF"},
                "dewpoint": {"value": 68.0, "unitCode": "degF"},
                "windSpeed": {"value": 12.0},  # km/h
                "windDirection": {"value": 180},  # degrees
                "barometricPressure": {"value": 102000, "unitCode": "Pa"},  # Already in Pa
                "relativeHumidity": {"value": 70, "unitCode": "percent"},
                "textDescription": "Clear Sky",
                "visibility": {
                    "value": None,
                    "unitCode": "m",
                },  # Open-Meteo doesn't provide visibility
            }
        }

        # Create a format string parser
        self.parser = FormatStringParser()

        # Create a UI manager for testing data extraction - patch the _setup_ui method
        mock_notifier = MagicMock()
        with patch.object(UIManager, "_setup_ui"):
            self.ui_manager = UIManager(self.frame, mock_notifier)

    def tearDown(self):
        """Clean up after tests."""
        # Destroy the wx.App
        self.app.Destroy()

    def test_default_format_nws_api(self):
        """Test the default format '{location} {temp} {condition}' with NWS API data."""
        # Extract taskbar data from NWS format
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.nws_test_data)

        # Add location data
        taskbar_data["location"] = "New York, NY"

        # Format with default format string
        default_format = "{location} {temp} {condition}"

        # Create formatted data (simulating what system_tray.py does)
        formatted_data = taskbar_data.copy()
        if "temp_f" in formatted_data and formatted_data["temp_f"] is not None:
            formatted_data["temp"] = f"{formatted_data['temp_f']:.0f}°F"

        result = self.parser.format_string(default_format, formatted_data)

        # Verify the result contains expected components
        self.assertIn("New York, NY", result)
        self.assertIn("72°F", result)
        self.assertIn("Partly Cloudy", result)

    def test_default_format_openmeteo_api(self):
        """Test the default format '{location} {temp} {condition}' with Open-Meteo API data."""
        # Extract taskbar data from Open-Meteo mapped format
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.openmeteo_mapped_data)

        # Add location data
        taskbar_data["location"] = "Los Angeles, CA"

        # Format with default format string
        default_format = "{location} {temp} {condition}"

        # Create formatted data (simulating what system_tray.py does)
        formatted_data = taskbar_data.copy()
        if "temp_f" in formatted_data and formatted_data["temp_f"] is not None:
            formatted_data["temp"] = f"{formatted_data['temp_f']:.0f}°F"

        result = self.parser.format_string(default_format, formatted_data)

        # Verify the result contains expected components
        self.assertIn("Los Angeles, CA", result)
        self.assertIn("75°F", result)
        self.assertIn("Clear Sky", result)

    def test_all_supported_placeholders_nws(self):
        """Test all supported placeholders with NWS API data."""
        # Extract taskbar data
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.nws_test_data)
        taskbar_data["location"] = "Test Location"

        # Test each supported placeholder
        supported_placeholders = FormatStringParser.SUPPORTED_PLACEHOLDERS.keys()

        for placeholder in supported_placeholders:
            format_string = f"{{{placeholder}}}"
            result = self.parser.format_string(format_string, taskbar_data)

            # Should not contain the placeholder itself (unless data is missing)
            if placeholder in ["uv", "visibility", "high", "low", "precip", "precip_chance"]:
                # These might not be available in basic NWS current conditions
                # They should either be "None" or the placeholder itself (if missing)
                self.assertTrue(
                    result == "None" or result == f"{{{placeholder}}}",
                    f"Placeholder {placeholder} returned unexpected value: {result}",
                )
            else:
                # These should have actual values
                self.assertNotEqual(
                    result, f"{{{placeholder}}}", f"Placeholder {placeholder} was not replaced"
                )

    def test_all_supported_placeholders_openmeteo(self):
        """Test all supported placeholders with Open-Meteo API data."""
        # Extract taskbar data
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.openmeteo_mapped_data)
        taskbar_data["location"] = "Test Location"

        # Test each supported placeholder
        supported_placeholders = FormatStringParser.SUPPORTED_PLACEHOLDERS.keys()

        for placeholder in supported_placeholders:
            format_string = f"{{{placeholder}}}"
            result = self.parser.format_string(format_string, taskbar_data)

            # Should not contain the placeholder itself (unless data is missing)
            if placeholder in ["uv", "visibility", "high", "low", "precip", "precip_chance"]:
                # These might not be available in Open-Meteo current conditions
                # They should either be "None" or the placeholder itself (if missing)
                self.assertTrue(
                    result == "None" or result == f"{{{placeholder}}}",
                    f"Placeholder {placeholder} returned unexpected value: {result}",
                )
            else:
                # These should have actual values
                self.assertNotEqual(
                    result, f"{{{placeholder}}}", f"Placeholder {placeholder} was not replaced"
                )

    def test_edge_case_missing_location_data(self):
        """Test handling when location data is missing."""
        # Test with NWS data but no location
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.nws_test_data)
        # Don't add location data

        format_string = "{location} {temp} {condition}"
        result = self.parser.format_string(format_string, taskbar_data)

        # Location should be empty string, not None
        self.assertIn(" ", result)  # Should have spaces between placeholders
        self.assertNotIn("None", result)

    def test_edge_case_api_failure_data(self):
        """Test handling when API returns incomplete or failed data."""
        # Test with empty/invalid data
        empty_data: dict = {}
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(empty_data)

        format_string = "{temp} {condition}"
        result = self.parser.format_string(format_string, taskbar_data)

        # Should handle gracefully without crashing
        self.assertIsInstance(result, str)

    def test_backward_compatibility_existing_formats(self):
        """Test that existing custom format strings continue to work."""
        # Test various format strings that users might have configured
        test_formats = [
            "{temp} {condition}",
            "{location}: {temp}, {wind_dir} {wind_speed}",
            "Temp: {temp_f}°F, Feels: {feels_like}",
            "{condition} - {humidity}% humidity",
            "{location} | {temp} | {pressure}",
        ]

        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.nws_test_data)
        taskbar_data["location"] = "Test City"

        # Create formatted data (simulating system_tray.py formatting)
        formatted_data = taskbar_data.copy()
        if "temp_f" in formatted_data and formatted_data["temp_f"] is not None:
            formatted_data["temp"] = f"{formatted_data['temp_f']:.0f}°F"
        if "wind_speed" in formatted_data and formatted_data["wind_speed"] is not None:
            formatted_data["wind_speed"] = f"{formatted_data['wind_speed']:.1f} mph"

        for format_string in test_formats:
            with self.subTest(format_string=format_string):
                result = self.parser.format_string(format_string, formatted_data)

                # Should not contain any unresolved placeholders
                self.assertNotIn("{", result)
                self.assertNotIn("}", result)

                # Should be a reasonable length (not empty, not too long)
                self.assertGreater(len(result), 0)
                self.assertLess(len(result), 200)

    def test_wind_placeholder_combinations(self):
        """Test wind-related placeholders work correctly."""
        # Test with NWS data
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.nws_test_data)

        # Test individual wind placeholders
        wind_speed_result = self.parser.format_string("{wind_speed}", taskbar_data)
        wind_dir_result = self.parser.format_string("{wind_dir}", taskbar_data)
        wind_combined_result = self.parser.format_string("{wind}", taskbar_data)

        # Verify wind direction is converted from degrees to cardinal direction
        self.assertIn("SW", wind_dir_result)  # 225 degrees = SW

        # Verify wind speed is converted from km/h to mph
        self.assertIsNotNone(taskbar_data.get("wind_speed"))
        self.assertNotEqual(wind_speed_result, "{wind_speed}")

        # Verify combined wind placeholder includes both direction and speed
        self.assertIn("SW", wind_combined_result)
        self.assertIn("mph", wind_combined_result)

    def test_temperature_unit_handling(self):
        """Test temperature placeholders respect unit preferences."""
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.nws_test_data)

        # Test that both Fahrenheit and Celsius values are available
        self.assertIsNotNone(taskbar_data.get("temp_f"))
        self.assertIsNotNone(taskbar_data.get("temp_c"))

        # Test specific temperature placeholders
        temp_f_result = self.parser.format_string("{temp_f}", taskbar_data)
        temp_c_result = self.parser.format_string("{temp_c}", taskbar_data)

        self.assertNotEqual(temp_f_result, "{temp_f}")
        self.assertNotEqual(temp_c_result, "{temp_c}")

    def test_pressure_unit_conversion(self):
        """Test pressure values are converted correctly."""
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.nws_test_data)

        # Pressure should be converted from Pa to inHg
        pressure_result = self.parser.format_string("{pressure}", taskbar_data)
        self.assertNotEqual(pressure_result, "{pressure}")

        # Should be a reasonable pressure value in inHg (typically 28-32)
        pressure_value = taskbar_data.get("pressure")
        if pressure_value is not None:
            self.assertGreater(pressure_value, 25)
            self.assertLess(pressure_value, 35)

    def test_openmeteo_specific_limitations(self):
        """Test handling of Open-Meteo API limitations."""
        taskbar_data = self.ui_manager._extract_nws_data_for_taskbar(self.openmeteo_mapped_data)

        # Open-Meteo doesn't provide visibility data
        visibility_result = self.parser.format_string("{visibility}", taskbar_data)
        self.assertTrue(visibility_result in ["None", "{visibility}"])

        # Open-Meteo doesn't provide UV index in current conditions
        uv_result = self.parser.format_string("{uv}", taskbar_data)
        self.assertTrue(uv_result in ["None", "{uv}"])

    def test_format_string_validation_comprehensive(self):
        """Test comprehensive format string validation."""
        # Test valid format strings
        valid_formats = [
            "{temp}",
            "{location} {temp} {condition}",
            "Weather: {condition}, Temp: {temp_f}°F",
            "{wind_dir} wind at {wind_speed}",
            "Humidity: {humidity}%, Pressure: {pressure}",
        ]

        for format_string in valid_formats:
            with self.subTest(format_string=format_string):
                is_valid, error = self.parser.validate_format_string(format_string)
                self.assertTrue(is_valid, f"Format '{format_string}' should be valid: {error}")
                self.assertIsNone(error)

        # Test invalid format strings
        invalid_formats = [
            "{temp",  # Missing closing brace
            "temp}",  # Missing opening brace
            "{invalid_placeholder}",  # Unsupported placeholder
            "{temp} {unknown} {condition}",  # Mix of valid and invalid
        ]

        for format_string in invalid_formats:
            with self.subTest(format_string=format_string):
                is_valid, error = self.parser.validate_format_string(format_string)
                self.assertFalse(is_valid, f"Format '{format_string}' should be invalid")
                self.assertIsNotNone(error)

    def test_data_standardization_consistency(self):
        """Test that data standardization produces consistent results."""
        # Test NWS data standardization
        nws_data = self.ui_manager._extract_nws_data_for_taskbar(self.nws_test_data)

        # Test Open-Meteo data standardization
        openmeteo_data = self.ui_manager._extract_nws_data_for_taskbar(self.openmeteo_mapped_data)

        # Both should have the same keys
        self.assertEqual(set(nws_data.keys()), set(openmeteo_data.keys()))

        # Both should have standardized structure
        expected_keys = {
            "temp",
            "temp_f",
            "temp_c",
            "feels_like",
            "feels_like_f",
            "feels_like_c",
            "condition",
            "weather_code",
            "wind_speed",
            "wind_dir",
            "wind",
            "humidity",
            "pressure",
            "uv",
            "visibility",
            "precip",
            "location",
        }

        self.assertEqual(set(nws_data.keys()), expected_keys)
        self.assertEqual(set(openmeteo_data.keys()), expected_keys)

    def test_error_handling_malformed_data(self):
        """Test error handling with malformed API data."""
        # Test with completely invalid data
        malformed_data_cases: list = [
            None,
            {},
            {"properties": None},
            {"properties": {}},
            {"properties": {"temperature": "invalid"}},
            {"properties": {"temperature": {"value": "not_a_number"}}},
        ]

        for malformed_data in malformed_data_cases:
            with self.subTest(data=malformed_data):
                # Should not crash and should return standardized empty data
                result = self.ui_manager._extract_nws_data_for_taskbar(malformed_data)
                self.assertIsInstance(result, dict)

                # Should have all expected keys
                expected_keys = {
                    "temp",
                    "temp_f",
                    "temp_c",
                    "feels_like",
                    "feels_like_f",
                    "feels_like_c",
                    "condition",
                    "weather_code",
                    "wind_speed",
                    "wind_dir",
                    "wind",
                    "humidity",
                    "pressure",
                    "uv",
                    "visibility",
                    "precip",
                    "location",
                }
                self.assertEqual(set(result.keys()), expected_keys)

    def test_integration_with_system_tray(self):
        """Test integration with the actual TaskBarIcon system."""
        # Create a TaskBarIcon instance
        with patch("wx.adv.TaskBarIcon"):
            taskbar_icon = TaskBarIcon(self.frame)
            taskbar_icon.SetIcon = MagicMock()

            # Test with NWS data
            nws_data = self.ui_manager._extract_nws_data_for_taskbar(self.nws_test_data)
            nws_data["location"] = "Test Location"

            # Update weather data
            taskbar_icon.update_weather_data(nws_data)

            # Verify that SetIcon was called (meaning formatting worked)
            taskbar_icon.SetIcon.assert_called()

            # Test with Open-Meteo data
            openmeteo_data = self.ui_manager._extract_nws_data_for_taskbar(
                self.openmeteo_mapped_data
            )
            openmeteo_data["location"] = "Test Location 2"

            # Update weather data
            taskbar_icon.update_weather_data(openmeteo_data)

            # Verify that SetIcon was called again
            self.assertEqual(taskbar_icon.SetIcon.call_count, 2)


if __name__ == "__main__":
    unittest.main()
